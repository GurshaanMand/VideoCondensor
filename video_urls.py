import re
from urllib.parse import parse_qs, urlparse


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def extractYoutubeVideoId(url: str):
    """Return an 11-character YouTube video id for common public URL forms."""
    try:
        parsed = urlparse(url.strip())
    except (AttributeError, ValueError):
        return None

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    host = parsed.hostname.lower() if parsed.hostname else ""
    candidate = None

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            parts = parsed.path.strip("/").split("/")
            candidate = parts[1] if len(parts) > 1 else None

    if candidate and VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def isValidYoutubeUrl(url: str) -> bool:
    return extractYoutubeVideoId(url) is not None


def is_valid_youtube_url(url: str) -> bool:
    return isValidYoutubeUrl(url)
