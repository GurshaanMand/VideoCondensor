import errno
import json
import logging
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from video_urls import isValidYoutubeUrl


LOGGER = logging.getLogger("video-condenser")
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("VIDEO_CONDENSER_DATA_DIR", PROJECT_DIR / "runtime" / "jobs")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MAX_CONCURRENT_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
MAX_PENDING_JOBS = max(MAX_CONCURRENT_JOBS, int(os.getenv("MAX_PENDING_JOBS", "2")))
JOB_RETENTION_HOURS = max(1, int(os.getenv("JOB_RETENTION_HOURS", "24")))
JOB_CLEANUP_INTERVAL_SECONDS = max(60, int(os.getenv("JOB_CLEANUP_INTERVAL_SECONDS", "900")))
WORKING_ARTIFACT_NAMES = ("source.*", "*.part", "*.ytdl", "*.partial.mp4", "condensed.mp4")

executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="video-job")
jobs = {}
jobs_lock = Lock()
cleanup_stop = Event()
shutdown_requested = Event()
cleanup_thread = None


class JobInterrupted(RuntimeError):
    pass


class CondenseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2048)
    objective: str = Field(min_length=8, max_length=300)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _job_dir(job_id):
    return DATA_DIR / job_id


def _public_job(job):
    return {
        key: job.get(key)
        for key in (
            "job_id", "status", "progress", "stage", "message", "error",
            "title", "statistics", "created_at", "updated_at", "status_url", "result_url"
        )
        if job.get(key) is not None
    }


def _persist_job(job):
    job_dir = _job_dir(job["job_id"])
    job_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = job_dir / "status.tmp"
    temporary_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    temporary_path.replace(job_dir / "status.json")


def _clean_working_files(job_dir):
    job_dir = Path(job_dir)
    shutil.rmtree(job_dir / "clips", ignore_errors=True)
    for pattern in WORKING_ARTIFACT_NAMES:
        try:
            artifacts = list(job_dir.glob(pattern))
        except OSError:
            LOGGER.warning("Could not inspect working files in %s", job_dir, exc_info=True)
            continue
        for artifact in artifacts:
            try:
                if artifact.is_file():
                    artifact.unlink(missing_ok=True)
            except OSError:
                # Cleanup must never prevent a job from reaching a terminal
                # state. The periodic retention sweep can retry later.
                LOGGER.warning("Could not remove working file %s", artifact, exc_info=True)


def _update_job(job_id, **updates):
    with jobs_lock:
        proposed = dict(jobs[job_id])
        proposed.update(updates)
        proposed["updated_at"] = _now()
        # Commit disk and memory as one locked operation. If the atomic disk
        # write fails, callers still see the last fully persisted state.
        _persist_job(proposed)
        jobs[job_id] = proposed
        return dict(proposed)


def _get_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        return dict(job) if job else None


def _load_existing_jobs():
    for status_path in DATA_DIR.glob("*/status.json"):
        try:
            job = json.loads(status_path.read_text(encoding="utf-8"))
            if not isinstance(job, dict):
                raise ValueError("Job status must be a JSON object.")
            job_id = job.get("job_id")
            if (
                not isinstance(job_id, str)
                or uuid.UUID(job_id).hex != job_id
                or status_path.parent.name != job_id
            ):
                raise ValueError("Job status has an invalid identifier.")

            expected_result_file = status_path.parent / "condensed.mp4"
            expected_result_path = expected_result_file.resolve()
            if job.get("status") in {"queued", "processing"}:
                job.update({
                    "status": "failed",
                    "error": "Processing was interrupted by an application restart.",
                    "stage": "Interrupted",
                    "message": "Submit the video again to retry.",
                    "updated_at": _now(),
                })
                _clean_working_files(status_path.parent)
                _persist_job(job)
            elif job.get("status") == "completed":
                if expected_result_file.is_symlink() or not expected_result_file.is_file():
                    job.update({
                        "status": "failed",
                        "error": "The condensed video file is no longer available.",
                        "stage": "Expired",
                        "message": "Submit the video again to recreate it.",
                        "updated_at": _now(),
                    })
                    _persist_job(job)
                elif job.get("result_path") != str(expected_result_path):
                    # Normalize persisted paths to the current data directory,
                    # which may differ after moving into a container.
                    job["result_path"] = str(expected_result_path)
                    _persist_job(job)
            elif job.get("status") == "failed":
                _clean_working_files(status_path.parent)
            jobs[job["job_id"]] = job
        except (OSError, TypeError, ValueError, KeyError):
            LOGGER.warning("Ignoring unreadable job status: %s", status_path)


def _cleanup_expired_jobs():
    cutoff = time.time() - JOB_RETENTION_HOURS * 3600
    expired = []
    with jobs_lock:
        for job_id, job in jobs.items():
            if job.get("status") not in {"completed", "failed"}:
                continue
            try:
                updated = datetime.fromisoformat(job["updated_at"]).timestamp()
            except (KeyError, TypeError, ValueError):
                continue
            if updated < cutoff:
                expired.append(job_id)
        for job_id in expired:
            jobs.pop(job_id, None)
        known_dirs = set(jobs)

    for job_id in expired:
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)

    for job_dir in DATA_DIR.iterdir():
        if not job_dir.is_dir() or job_dir.name in known_dirs:
            continue
        try:
            stale = job_dir.stat().st_mtime < cutoff
        except OSError:
            continue
        if stale:
            shutil.rmtree(job_dir, ignore_errors=True)


def _cleanup_loop():
    while not cleanup_stop.wait(JOB_CLEANUP_INTERVAL_SECONDS):
        try:
            _cleanup_expired_jobs()
        except Exception:
            LOGGER.exception("Background job cleanup failed")


@asynccontextmanager
async def lifespan(_app):
    global cleanup_thread

    _cleanup_expired_jobs()
    cleanup_stop.clear()
    shutdown_requested.clear()
    cleanup_thread = Thread(target=_cleanup_loop, name="job-cleanup", daemon=True)
    cleanup_thread.start()
    try:
        yield
    finally:
        shutdown_requested.set()
        cleanup_stop.set()
        cleanup_thread.join(timeout=2)
        executor.shutdown(wait=False, cancel_futures=True)
        with jobs_lock:
            queued_job_ids = [
                job_id for job_id, job in jobs.items()
                if job.get("status") == "queued"
            ]
        for job_id in queued_job_ids:
            try:
                _update_job(
                    job_id,
                    status="failed",
                    stage="Interrupted",
                    message="Processing stopped",
                    error="Processing was interrupted by an application shutdown. Submit again to retry.",
                )
            except Exception:
                LOGGER.exception("Could not mark queued job %s as interrupted", job_id)


app = FastAPI(title="Video Condenser", version="1.0.0", lifespan=lifespan)

frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
if frontend_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )


def runPipeline(url, objective, job_dir, progress_callback):
    from pipeline import runPipeline as run_pipeline
    return run_pipeline(url, objective, job_dir, progress_callback)


def _process_job(job_id, url, objective):
    try:
        if shutdown_requested.is_set():
            raise JobInterrupted("Application shutdown interrupted the job.")
        _update_job(
            job_id,
            status="processing",
            progress=2,
            stage="Starting",
            message="Preparing your job",
        )

        def report(progress, stage, message):
            if shutdown_requested.is_set():
                raise JobInterrupted("Application shutdown interrupted the job.")
            _update_job(
                job_id,
                status="processing",
                progress=max(2, min(99, int(progress))),
                stage=stage,
                message=message,
            )

        result = runPipeline(url, objective, _job_dir(job_id), report)
        result_file = Path(result["output_path"])
        result_path = result_file.resolve()
        expected_result_file = _job_dir(job_id) / "condensed.mp4"
        expected_result_path = expected_result_file.resolve()
        if result_path != expected_result_path:
            raise RuntimeError("The processing pipeline returned an unexpected output path.")
        if result_file.is_symlink() or not result_file.is_file() or result_file.stat().st_size == 0:
            raise RuntimeError("The processing pipeline did not produce a video file.")
        if shutdown_requested.is_set():
            raise JobInterrupted("Application shutdown interrupted the job.")
        _update_job(
            job_id,
            status="completed",
            progress=100,
            stage="Ready",
            message="Your condensed video is ready",
            title=result.get("title"),
            statistics=result.get("statistics"),
            result_path=str(result_path),
        )
    except Exception as exc:
        LOGGER.exception("Video job %s failed", job_id)
        message = _friendly_job_error(exc)
        try:
            _clean_working_files(_job_dir(job_id))
        except Exception:
            LOGGER.exception("Unexpected cleanup failure for job %s", job_id)
        try:
            _update_job(
                job_id,
                status="failed",
                stage="Failed",
                message="Processing stopped",
                error=message[-800:],
            )
        except Exception:
            # Preserve the terminal state in memory even if the disk itself is
            # unhealthy and status.json cannot be rewritten.
            LOGGER.exception("Could not persist failed status for job %s", job_id)
            with jobs_lock:
                job = jobs.get(job_id)
                if job:
                    job.update({
                        "status": "failed",
                        "stage": "Failed",
                        "message": "Processing stopped",
                        "error": message[-800:],
                        "updated_at": _now(),
                    })


def _friendly_job_error(exc):
    if isinstance(exc, JobInterrupted):
        return "Processing was interrupted by an application shutdown. Submit again to retry."
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return "The server does not have enough free storage for this video. Try a shorter video."

    text = str(exc).strip()
    lowered = text.lower()
    if "too long" in lowered:
        return text
    if "could not be reached" in lowered or "timed out" in lowered:
        return "YouTube could not be reached. Please retry shortly."
    if "transcript" in lowered or "caption" in lowered:
        return "This video does not have an accessible English transcript. Choose a public video with captions."
    if "403" in lowered or "forbidden" in lowered or "sign in" in lowered or "bot" in lowered:
        return "YouTube blocked the download request. Retry later or configure server-side YouTube cookies."
    if "disk space" in lowered or "no space left" in lowered:
        return "The server does not have enough free storage for this video. Try a shorter video."
    if "ffmpeg" in lowered:
        return "The video renderer could not finish this source video. Try another video."
    return "The video could not be processed. Please try again."


_load_existing_jobs()


@app.get("/health")
def health():
    with jobs_lock:
        active_jobs = sum(job.get("status") in {"queued", "processing"} for job in jobs.values())
    return {"status": "ok", "active_jobs": active_jobs}


@app.post("/condense", status_code=202)
def condense(request: CondenseRequest):
    if not isValidYoutubeUrl(request.url):
        raise HTTPException(status_code=422, detail="Enter a valid public YouTube video URL.")
    if len(request.objective.strip()) < 8:
        raise HTTPException(status_code=422, detail="Describe your objective in at least 8 characters.")

    _cleanup_expired_jobs()
    with jobs_lock:
        active_jobs = sum(job.get("status") in {"queued", "processing"} for job in jobs.values())
        if active_jobs >= MAX_PENDING_JOBS:
            raise HTTPException(
                status_code=429,
                detail="The server is already processing its current job limit. Please retry shortly.",
                headers={"Retry-After": "60"},
            )

        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "Queued",
            "message": "Waiting to start",
            "created_at": _now(),
            "updated_at": _now(),
            "status_url": f"/jobs/{job_id}",
            "result_url": f"/results/{job_id}",
        }
        jobs[job_id] = job
        response_job = dict(job)

    try:
        _persist_job(response_job)
        executor.submit(_process_job, job_id, request.url, request.objective)
    except Exception as exc:
        with jobs_lock:
            jobs.pop(job_id, None)
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            raise HTTPException(status_code=507, detail="The server does not have enough free storage.") from exc
        LOGGER.exception("Could not submit video job")
        raise HTTPException(status_code=503, detail="The server could not accept this job.") from exc

    return _public_job(response_job)


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _public_job(job)


def _video_response(job):
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="The condensed video is not ready yet.")
    result_file = _job_dir(job["job_id"]) / "condensed.mp4"
    result_path = result_file.resolve()
    if result_file.is_symlink() or not result_file.is_file():
        raise HTTPException(status_code=404, detail="The condensed video file is no longer available.")
    return FileResponse(
        result_path,
        media_type="video/mp4",
        headers={"Content-Disposition": 'inline; filename="condensed-video.mp4"'},
    )


@app.get("/results/{job_id}")
def job_result(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _video_response(job)


# This catch-all mount must remain after every API route.
app.mount("/", StaticFiles(directory=PROJECT_DIR / "frontend", html=True), name="frontend")
