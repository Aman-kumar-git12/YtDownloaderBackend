from datetime import timedelta
from core.yt_helper import extract_info_safe

# yt-dlp often stores missing fields as None (not absent), so every lookup below
# uses `info.get(key) or default` instead of `info.get(key, default)`.

def format_upload_date(raw):
    """'20240305' -> '2024-03-05' (ISO). Returns None if missing/malformed."""
    if raw and len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return None

def format_duration(seconds):
    return str(timedelta(seconds=int(seconds))) if seconds else None

def fetch_metadata(url):
    info = extract_info_safe(url, download=False)

    desc = info.get('description') or ''
    desc_snippet = desc.replace('\n', ' ')[:100] + ('...' if len(desc) > 100 else '') if desc else 'None'

    live_status = 'Currently Live' if info.get('is_live') else 'Was Live (VOD)' if info.get('was_live') else 'Never Live'

    chapters = info.get('chapters') or []
    chapters_preview = [
        f"{timedelta(seconds=int(chap.get('start_time') or 0))}: {chap.get('title') or 'Untitled'}"
        for chap in chapters[:3]
    ]

    # Fetch highest resolution thumbnail
    thumbnails = info.get('thumbnails') or []
    max_thumbnail_url = info.get('thumbnail')
    valid_thumbs = [t for t in thumbnails if t.get('width') and t.get('height')]
    if valid_thumbs:
        max_thumbnail_url = max(valid_thumbs, key=lambda t: t['width'] * t['height']).get('url')
    elif thumbnails:
        max_thumbnail_url = thumbnails[-1].get('url')

    return {
        "title": info.get('title') or 'Unknown',
        "video_id": info.get('id') or 'Unknown',
        "url": info.get('webpage_url') or url,
        "channel": info.get('uploader') or info.get('channel') or 'Unknown',
        "channel_url": info.get('channel_url') or '',
        "subscribers": info.get('channel_follower_count'),
        "upload_date": format_upload_date(info.get('upload_date')),
        "duration": format_duration(info.get('duration')),
        "views": info.get('view_count'),
        "likes": info.get('like_count'),
        "comments": info.get('comment_count'),
        "description_snippet": desc_snippet,
        "tags": info.get('tags') or [],
        "categories": info.get('categories') or [],
        "privacy": (info.get('availability') or 'unknown').replace('_', ' ').capitalize(),
        "license": info.get('license') or 'Standard',
        "age_restricted": (info.get('age_limit') or 0) > 0,
        "live_status": live_status,
        "total_chapters": len(chapters),
        "chapters_preview": chapters_preview,
        "total_formats": len(info.get('formats') or []),
        "subtitles": list((info.get('subtitles') or {}).keys()),
        "thumbnail": max_thumbnail_url,
    }
