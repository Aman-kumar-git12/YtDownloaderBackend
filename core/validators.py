import re
from urllib.parse import urlparse

YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
THUMBNAIL_HOSTS = ("ytimg.com", "ggpht.com", "googleusercontent.com")

AUDIO_FORMATS = ("mp3", "m4a", "wav", "flac", "aac")
VIDEO_TARGET_RE = re.compile(r"^\d{2,4}p?$", re.IGNORECASE)
THUMBNAIL_TARGET_RE = re.compile(r"^[\w-]{1,40}$")
# "<language>:<manual|auto>:<srt|vtt>", e.g. "en:manual:srt" or "en-orig:auto:vtt"
SUBTITLE_TARGET_RE = re.compile(r"^[\w-]{1,20}:(manual|auto):(srt|vtt)$")


def _host_matches(url, allowed_domains):
    """True if url is http(s) and its host is one of allowed_domains or a subdomain of one."""
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def is_youtube_url(url):
    return _host_matches(url, YOUTUBE_HOSTS)


def is_thumbnail_url(url):
    return _host_matches(url, THUMBNAIL_HOSTS)


def is_valid_target(kind, target):
    target = (target or "").strip()
    if kind == "video":
        return bool(VIDEO_TARGET_RE.match(target))
    if kind == "audio":
        return target.lower() in AUDIO_FORMATS
    if kind == "thumbnail":
        return bool(THUMBNAIL_TARGET_RE.match(target))
    if kind == "subtitles":
        return bool(SUBTITLE_TARGET_RE.match(target))
    return False
