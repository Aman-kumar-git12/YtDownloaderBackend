"""What viewers are saying: mood, top questions, recurring words and likely audience languages."""
from collections import Counter

from core.cache import TTLCache
from core.text_tools import (LANGUAGE_COUNTRIES, LANGUAGE_NAMES, detect_language, sentiment, top_keywords)
from core.yt_helper import extract_info_safe

MAX_COMMENTS = 150
_cache = TTLCache(ttl_seconds=1800, max_entries=50)


def _fetch_comments(url):
    info = extract_info_safe(url, extra_opts={
        'getcomments': True,
        'extractor_args': {'youtube': {'max_comments': [str(MAX_COMMENTS), str(MAX_COMMENTS), '0', '0'],
                                       'comment_sort': ['top']}},
    })
    return info, [c for c in (info.get('comments') or []) if c.get('text')]


def comment_insights(url):
    return _cache.get_or_compute(url, lambda: analyse(*_fetch_comments(url)))


def analyse(info, comments):
    if not comments:
        return {"sampled": 0, "total": info.get("comment_count")}

    moods = Counter(sentiment(c["text"]) for c in comments)
    n = len(comments)

    questions = sorted((c for c in comments if "?" in c["text"] and not c.get("author_is_uploader")),
                       key=lambda c: c.get("like_count") or 0, reverse=True)[:5]

    title_words = [w for w in (info.get("title") or "").split()]
    languages = Counter(lang for lang in (detect_language(c["text"]) for c in comments) if lang)
    detected = sum(languages.values())

    return {
        "sampled": n,
        "total": info.get("comment_count"),
        "mood": {
            "positive": round(moods[1] / n * 100),
            "neutral": round(moods[0] / n * 100),
            "negative": round(moods[-1] / n * 100),
        },
        "questions": [{"text": _short(c["text"]), "likes": c.get("like_count") or 0} for c in questions],
        "keywords": top_keywords([c["text"] for c in comments], limit=12, exclude=title_words),
        "top_comment": _comment(max(comments, key=lambda c: c.get("like_count") or 0)),
        "pinned": _comment(next((c for c in comments if c.get("is_pinned")), None)),
        "creator_replies": sum(1 for c in comments if c.get("author_is_uploader")),
        "languages": [
            {"code": code, "name": LANGUAGE_NAMES.get(code, code), "share": round(count / detected * 100),
             "likely_countries": LANGUAGE_COUNTRIES.get(code, [])}
            for code, count in languages.most_common(6)
        ] if detected else [],
    }


def _short(text, limit=220):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _comment(c):
    return {"text": _short(c["text"]), "likes": c.get("like_count") or 0, "author": c.get("author")} if c else None
