import errno
import os
import shutil
import subprocess
from pathlib import Path


FFMPEG_TIMEOUT_SECONDS = max(60, int(os.getenv("FFMPEG_TIMEOUT_SECONDS", "3600")))
MIN_FREE_SPACE_BYTES = int(max(1.0, float(os.getenv("MIN_FREE_SPACE_GB", "5"))) * 1024 ** 3)


def _kept_ranges(topics, join_gap=0.35):
    ranges = sorted(
        (float(seg.start), float(seg.end))
        for topic in topics
        for seg in topic
        if seg.keep and float(seg.end) > float(seg.start)
    )

    merged = []
    for start, end in ranges:
        if merged and start <= merged[-1][1] + join_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _run_ffmpeg(command):
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is not installed in the application environment.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Unknown FFmpeg error").strip()[-1200:]
        raise RuntimeError(f"FFmpeg could not render the condensed video: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"FFmpeg exceeded its {FFMPEG_TIMEOUT_SECONDS}-second safety timeout."
        ) from exc


def _ensure_render_space(directory, required_bytes=0):
    free_bytes = shutil.disk_usage(directory).free
    required_bytes = MIN_FREE_SPACE_BYTES + max(0, int(required_bytes))
    if free_bytes < required_bytes:
        raise OSError(
            errno.ENOSPC,
            "Not enough free disk space remains to render the condensed video.",
        )


def stitchVideo(topics, source_path, output_path, progress_callback=None):
    """Render kept transcript ranges and concatenate them into one MP4."""
    source_path = Path(source_path).resolve()
    output_path = Path(output_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source video does not exist: {source_path}")

    kept_ranges = _kept_ranges(topics)
    if not kept_ranges:
        raise ValueError("No video sections were selected for the final cut.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_output_path = output_path.with_name(f"{output_path.stem}.partial{output_path.suffix}")
    clip_dir = output_path.parent / "clips"
    if clip_dir.exists():
        shutil.rmtree(clip_dir)
    clip_dir.mkdir(parents=True)
    partial_output_path.unlink(missing_ok=True)

    clip_paths = []
    try:
        for index, (start, end) in enumerate(kept_ranges):
            _ensure_render_space(output_path.parent)
            clip_path = clip_dir / f"clip_{index:04d}.mp4"
            duration = max(0.05, end - start)
            _run_ffmpeg([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start:.3f}",
                "-i", str(source_path),
                "-t", f"{duration:.3f}",
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                "-avoid_negative_ts", "make_zero",
                str(clip_path),
            ])
            clip_paths.append(clip_path)
            if progress_callback:
                progress_callback(index + 1, len(kept_ranges) + 1)

        if len(clip_paths) == 1:
            shutil.move(str(clip_paths[0]), str(partial_output_path))
        else:
            # Concatenation temporarily needs both every clip and a second copy
            # of their combined bytes for the final MP4.
            _ensure_render_space(
                output_path.parent,
                required_bytes=sum(path.stat().st_size for path in clip_paths),
            )
            concat_file = clip_dir / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{path.as_posix()}'\n" for path in clip_paths),
                encoding="utf-8"
            )
            _run_ffmpeg([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-movflags", "+faststart",
                str(partial_output_path),
            ])

        if progress_callback:
            progress_callback(len(kept_ranges) + 1, len(kept_ranges) + 1)
        if not partial_output_path.is_file() or partial_output_path.stat().st_size == 0:
            raise RuntimeError("The final condensed video was not created.")
        partial_output_path.replace(output_path)
    except Exception:
        partial_output_path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(clip_dir, ignore_errors=True)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("The final condensed video was not created.")

    return {
        "kept_sections": len(kept_ranges),
        "condensed_duration_seconds": round(sum(end - start for start, end in kept_ranges), 2),
        "output_bytes": output_path.stat().st_size,
    }
