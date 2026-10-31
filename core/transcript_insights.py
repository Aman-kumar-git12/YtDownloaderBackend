"""What the video says: speaking pace, topics, how strong the opening hook is."""
import json
import time

from core.cache import TTLCache
from core.text_tools import top_keywords, words
from core.yt_helper import extract_info_safe, fetch_url_text, recent_errors

_cache = TTLCache(ttl_seconds=1800, max_entries=50)
HOOK_SECONDS = 30


def _caption_tracks(info):
    """Caption tracks to try, best first: creator captions in the video's language,
    then the original automatic captions. -> [(source, language, json3_url)]"""
    lang = (info.get("language") or "en").split("-")[0]
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    found, seen = [], set()
    for source, tracks, keys in (
        ("creator", manual, [k for k in manual if k.split("-")[0] == lang] + list(manual)),
        ("automatic", auto, [k for k in auto if k.endswith("-orig")] + [k for k in auto if k.split("-")[0] == lang]),
    ):
        for key in keys:
            fmt = next((f for f in tracks.get(key) or [] if f.get("ext") == "json3"), None)
            if fmt and fmt["url"] not in seen:
                seen.add(fmt["url"])
                found.append((source, key, fmt["url"]))
    return found


def _pick_track(info):
    tracks = _caption_tracks(info)
    return tracks[0] if tracks else None


def _parse_json3(raw):
    """-> [(start_seconds, end_seconds, text)]"""
    lines = []
    for ev in json.loads(raw).get("events") or []:
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).replace("\n", " ").strip()
        if text:
            start = ev.get("tStartMs", 0) / 1000
            lines.append((start, start + ev.get("dDurationMs", 0) / 1000, text))
    return lines


def transcript_insights(url):
    # A blocked fetch is temporary, so don't remember it
    return _cache.get_or_compute(url, lambda: _build(url), should_cache=lambda r: r.get("reason") != "blocked")


MAX_TRACK_ATTEMPTS = 3


def _build(url):
    info = extract_info_safe(url)
    tracks = _caption_tracks(info)
    if not tracks:
        return {"available": False, "reason": "none"}
    last_error = None
    for source, lang, track_url in tracks[:MAX_TRACK_ATTEMPTS]:
        try:
            lines = _parse_json3(fetch_url_text(track_url))
        except Exception as e:  # blocked, rate limited, or not JSON
            last_error = e
            recent_errors.append({"time": time.strftime('%H:%M:%S'), "attempt": f"captions {lang}", "error": str(e)[:300]})
            continue
        if lines:
            return analyse(info, lines, source, lang)
    if last_error:
        print(f"⚠️ [TRANSCRIPT] captions couldn't be fetched: {last_error}")
        return {"available": False, "reason": "blocked"}
    return {"available": False, "reason": "empty"}


def analyse(info, lines, source="automatic", lang=None):
    all_text = " ".join(t for _, _, t in lines)
    word_list = words(all_text)
    duration = info.get("duration") or lines[-1][1]
    # Merge overlapping caption windows to measure how much of the video has speech
    speech, cur_start, cur_end = 0.0, None, None
    for start, end, _ in sorted(lines):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                speech += cur_end - cur_start
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    speech += (cur_end - cur_start) if cur_end is not None else 0
    speech = min(speech, duration) if duration else speech

    wpm = round(len(word_list) / (speech / 60)) if speech > 30 else None
    # Song captions are lyrics; don't republish them as the "hook" quote
    is_music = "Music" in (info.get("categories") or [])
    hook = "" if is_music else " ".join(t for s, _, t in lines if s < HOOK_SECONDS)
    first_minute = set(words(" ".join(t for s, _, t in lines if s < 60)))
    title_words = [w for w in words(info.get("title") or "") if len(w) > 3]
    promised = [w for w in title_words if w in first_minute]

    return {
        "available": True,
        "source": source,
        "language": lang,
        "word_count": len(word_list),
        "words_per_minute": wpm,
        "pace": None if wpm is None else "slow" if wpm < 110 else "relaxed" if wpm < 140 else "conversational" if wpm < 170 else "fast",
        "speech_share": round(speech / duration * 100) if duration else None,
        "keywords": top_keywords([t for _, _, t in lines], limit=15),
        "hook": hook[:600],
        "title_words_in_first_minute": {"found": promised, "total": len(title_words)},
        "reading_minutes": round(len(word_list) / 238, 1),
    }
