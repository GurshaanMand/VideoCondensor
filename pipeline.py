from pathlib import Path

from youtube_download import downloadYoutubeVideo


def runPipeline(url, objective, job_dir, progress_callback=None):
    """Download, analyze, and render one Video Condenser job."""
    job_dir = Path(job_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_dir / "condensed.mp4"
    download = None

    try:
        # Validate captions before downloading a potentially multi-gigabyte
        # source that cannot be analyzed.
        from AIVideoCondensor import condenseVideo, fetchTranscript

        if progress_callback:
            progress_callback(3, "Reading transcript", "Checking captions")
        transcript = fetchTranscript(url)

        download = downloadYoutubeVideo(url, job_dir, progress_callback)

        analysis = condenseVideo(
            url,
            objective,
            source_path=download["source_path"],
            output_path=output_path,
            progress_callback=progress_callback,
            transcript=transcript,
        )
        if not analysis.get("success"):
            raise ValueError(analysis.get("error") or "The video could not be condensed.")

        return {
            "output_path": str(output_path),
            "title": download["title"],
            "source_duration_seconds": download.get("duration"),
            "statistics": analysis.get("statistics", {}),
        }
    finally:
        for source_file in job_dir.glob("source.*"):
            if source_file.is_file():
                source_file.unlink(missing_ok=True)
