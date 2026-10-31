"""Optional YouTube Data API v3 client (set YOUTUBE_API_KEY; free quota is 10,000 units/day).

Adds data yt-dlp can't see: channel creation date and country, total channel views,
video count, topics, made-for-kids, and exact publish times of recent uploads.
Every call here costs 1 quota unit. Without a key the insights still work, with less detail.
"""
import os

import requests

API = "https://www.googleapis.com/youtube/v3"


def enabled():
    return bool(os.getenv("YOUTUBE_API_KEY"))


def _get(resource, **params):
    params["key"] = os.getenv("YOUTUBE_API_KEY")
    r = requests.get(f"{API}/{resource}", params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("items") or []


def _topic_name(url):
    # "https://en.wikipedia.org/wiki/Video_game_culture" -> "Video game culture"
    return url.rsplit("/", 1)[-1].replace("_", " ")


def channel(channel_id):
    items = _get("channels", part="snippet,statistics,topicDetails,contentDetails,status", id=channel_id)
    if not items:
        return None
    c = items[0]
    sn, st = c.get("snippet", {}), c.get("statistics", {})
    return {
        "created": sn.get("publishedAt"),
        "country": sn.get("country"),
        "default_language": sn.get("defaultLanguage"),
        "total_views": int(st["viewCount"]) if st.get("viewCount") else None,
        "subscribers": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount") or 0),
        "video_count": int(st["videoCount"]) if st.get("videoCount") else None,
        "topics": [_topic_name(t) for t in (c.get("topicDetails") or {}).get("topicCategories", [])],
        "made_for_kids": (c.get("status") or {}).get("madeForKids"),
        "uploads_playlist": (c.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads"),
    }


def recent_uploads(uploads_playlist, limit=50):
    """Exact publish time, views, likes, comments and duration for recent uploads."""
    ids = [i["contentDetails"]["videoId"] for i in
           _get("playlistItems", part="contentDetails", playlistId=uploads_playlist, maxResults=min(limit, 50))]
    if not ids:
        return []
    out = []
    for v in _get("videos", part="snippet,statistics,contentDetails", id=",".join(ids)):
        st = v.get("statistics", {})
        out.append({
            "id": v["id"],
            "title": v["snippet"]["title"],
            "published": v["snippet"]["publishedAt"],
            "views": int(st.get("viewCount") or 0),
            "likes": int(st["likeCount"]) if st.get("likeCount") else None,
            "comments": int(st["commentCount"]) if st.get("commentCount") else None,
            "duration": _iso_duration(v["contentDetails"].get("duration")),
        })
    return out


def video(video_id):
    items = _get("videos", part="status,snippet,topicDetails", id=video_id)
    if not items:
        return None
    v = items[0]
    return {
        "made_for_kids": (v.get("status") or {}).get("madeForKids"),
        "audio_language": v["snippet"].get("defaultAudioLanguage"),
        "topics": [_topic_name(t) for t in (v.get("topicDetails") or {}).get("topicCategories", [])],
    }


def _iso_duration(value):
    """'PT1H2M3S' -> 3723"""
    import re
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s
