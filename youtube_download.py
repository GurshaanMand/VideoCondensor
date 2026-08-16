import os
import shutil
import time
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled


MAX_VIDEO_DURATION_SECONDS = max(60, int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "10800")))
MIN_FREE_SPACE_GB = max(1.0, float(os.getenv("MIN_FREE_SPACE_GB", "5")))
MIN_FREE_SPACE_BYTES = int(MIN_FREE_SPACE_GB * 1024 ** 3)
ESTIMATED_WORKING_SET_MULTIPLIER = 3


class VideoTooLong(DownloadCancelled):
    maximum_hours = MAX_VIDEO_DURATION_SECONDS / 3600
    msg = f"This video is too long. The current limit is {maximum_hours:g} hours."


class DownloadLogger:
    def debug(self, message):
        if not message.startswith("[debug] "):
            self.info(message)

    def info(self, message):
        pass

    def warning(self, message):
        print(f"[yt-dlp] {message}")

    def error(self, message):
        print(f"[yt-dlp] {message}")


def downloadYoutubeVideo(url, job_dir, progress_callback=None):
    """Download one public YouTube video and return its local path + metadata."""
    job_dir = Path(job_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)

    def report(progress, stage, message):
        if progress_callback:
            progress_callback(progress, stage, message)

    last_report = {"percent": None, "time": 0.0}

    def ensure_capacity(required_bytes=0):
        free_bytes = shutil.disk_usage(job_dir).free
        required_with_reserve = max(
            MIN_FREE_SPACE_BYTES,
            int(required_bytes) * ESTIMATED_WORKING_SET_MULTIPLIER,
        )
        if free_bytes < required_with_reserve:
            required_gb = required_with_reserve / 1024 ** 3
            free_gb = free_bytes / 1024 ** 3
            raise OSError(
                28,
                f"Not enough free disk space to process this video "
                f"({free_gb:.1f} GB free; approximately {required_gb:.1f} GB required).",
            )

    def reject_oversized_video(info, *, incomplete):
        if incomplete:
            return None
        duration = info.get("duration")
        if duration and float(duration) > MAX_VIDEO_DURATION_SECONDS:
            maximum_hours = MAX_VIDEO_DURATION_SECONDS / 3600
            VideoTooLong.maximum_hours = maximum_hours
            VideoTooLong.msg = f"This video is too long. The current limit is {maximum_hours:g} hours."
            raise VideoTooLong()
        filesize = info.get("filesize") or info.get("filesize_approx") or 0
        ensure_capacity(filesize)
        return None

    def progress_hook(event):
        if event.get("status") == "downloading":
            total = event.get("total_bytes") or event.get("total_bytes_estimate")
            downloaded = event.get("downloaded_bytes", 0)
            if total:
                ensure_capacity(total)
            fraction = downloaded / total if total else 0
            percent = max(0, min(100, round(fraction * 100)))
            now = time.monotonic()
            if percent != last_report["percent"] and now - last_report["time"] >= 0.75:
                report(5 + round(fraction * 20), "Downloading video", f"Downloaded {percent}%")
                last_report.update(percent=percent, time=now)
        elif event.get("status") == "finished":
            report(26, "Preparing video", "Combining video and audio")

    options = {
        "format": "bv*[height<=720]+ba/b[height<=720]/best",
        "merge_output_format": "mp4",
        "outtmpl": {"default": str(job_dir / "source.%(ext)s")},
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "overwrites": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "progress_hooks": [progress_hook],
        "match_filter": reject_oversized_video,
        "logger": DownloadLogger(),
        "js_runtimes": {"deno": {}},
    }

    cookies_file = os.getenv("YTDLP_COOKIES_FILE")
    if cookies_file:
        options["cookiefile"] = cookies_file

    ensure_capacity()
    report(4, "Downloading video", "Connecting to YouTube")
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    requested_downloads = info.get("requested_downloads") or []
    reported_paths = [
        Path(download.get("filepath", ""))
        for download in requested_downloads
        if download.get("filepath")
    ]
    if info.get("filepath"):
        reported_paths.append(Path(info["filepath"]))

    candidates = [path for path in reported_paths if path.is_file()]
    if not candidates:
        candidates = [
            path for path in job_dir.glob("source.*")
            if path.is_file() and not path.name.endswith((".part", ".ytdl"))
        ]
    if not candidates:
        raise RuntimeError("YouTube download finished without producing a video file.")

    source_path = max(candidates, key=lambda path: path.stat().st_size)
    report(28, "Reading transcript", "Video downloaded")
    return {
        "source_path": str(source_path),
        "title": info.get("title") or "YouTube video",
        "duration": info.get("duration"),
        "video_id": info.get("id"),
    }
