"""Video insights built from public data. Every money/forecast number here is an ESTIMATE:
YouTube only shows real revenue and per-country views to the channel owner."""
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from core import ytapi
from core.yt_helper import extract_info_safe

# ─── Earnings model ───
# Typical creator RPM (USD the creator keeps per 1,000 views, after YouTube's 45% share)
# for a mostly US/UK audience, by YouTube category. Sources: public creator reports; wide on purpose.
CATEGORY_RPM = {
    "Music": (0.5, 2.0), "Gaming": (1.0, 3.5), "Entertainment": (1.0, 3.5), "Comedy": (1.0, 3.0),
    "People & Blogs": (1.5, 4.0), "Film & Animation": (1.0, 3.5), "Sports": (1.5, 4.0),
    "Pets & Animals": (1.0, 3.0), "Travel & Events": (2.0, 5.0), "Autos & Vehicles": (3.0, 7.0),
    "Howto & Style": (2.0, 5.0), "Education": (3.0, 8.0), "Science & Technology": (4.0, 10.0),
    "News & Politics": (2.0, 5.0), "Nonprofits & Activism": (1.0, 3.0),
}
DEFAULT_RPM = (1.0, 4.0)
FINANCE_RPM = (6.0, 15.0)
FINANCE_WORDS = {"invest", "investing", "investment", "stock", "stocks", "crypto", "bitcoin", "trading", "finance",
                 "money", "credit", "loan", "insurance", "mortgage", "tax", "taxes", "budget", "income", "wealth",
                 "passive", "dividend", "etf", "forex", "business", "realestate", "salary"}
SHORTS_RPM = (0.03, 0.10)

# How much an audience from each country is worth compared with a US audience.
COUNTRY_FACTOR = {
    "US": 1.0, "CA": 0.9, "AU": 0.95, "GB": 0.85, "NZ": 0.8, "DE": 0.85, "CH": 0.95, "NO": 0.9, "DK": 0.85,
    "SE": 0.8, "NL": 0.8, "IE": 0.8, "AT": 0.75, "BE": 0.7, "FR": 0.65, "JP": 0.7, "KR": 0.6, "SG": 0.6,
    "AE": 0.6, "IT": 0.5, "ES": 0.45, "PL": 0.35, "SA": 0.4, "MX": 0.3, "BR": 0.3, "AR": 0.2, "TR": 0.2,
    "RU": 0.15, "ZA": 0.3, "PH": 0.15, "ID": 0.15, "VN": 0.12, "IN": 0.2, "PK": 0.12, "BD": 0.1, "EG": 0.12,
    "NG": 0.12,
}
# Used when the channel's country is unknown: the video's spoken language.
LANGUAGE_FACTOR = {
    "en": 0.75, "de": 0.85, "fr": 0.65, "ja": 0.7, "ko": 0.6, "nl": 0.8, "sv": 0.8, "no": 0.85, "da": 0.85,
    "it": 0.5, "es": 0.35, "pt": 0.3, "pl": 0.35, "tr": 0.2, "ru": 0.15, "ar": 0.3, "hi": 0.2, "bn": 0.12,
    "ta": 0.2, "te": 0.2, "mr": 0.2, "ur": 0.12, "id": 0.15, "vi": 0.12, "th": 0.2, "tl": 0.15,
}

MIDROLL_MIN_SECONDS = 8 * 60
SHORT_MAX_SECONDS = 180


def _now():
    return time.time()


def _round_money(value):
    if value >= 1000:
        return round(value, -2) if value >= 10000 else round(value, -1)
    return round(value, 2)


def estimate_earnings(info, channel=None, video_extra=None, sponsor_seconds=0):
    """Range of what the video has likely earned from ads, plus how the range was built."""
    views = info.get("view_count") or 0
    duration = info.get("duration") or 0
    category = (info.get("categories") or [None])[0]
    text = " ".join([info.get("title") or ""] + (info.get("tags") or [])).lower()
    page_url = info.get("original_url") or info.get("webpage_url") or ""
    is_short = bool(duration) and (duration <= 60 or (duration <= SHORT_MAX_SECONDS and "/shorts/" in page_url))
    factors = []

    if is_short:
        low, high = SHORTS_RPM
        factors.append("Shorts pay from a shared pool, roughly $0.03–$0.10 per 1,000 views")
    else:
        if any(w in re.findall(r"[a-z]+", text) for w in FINANCE_WORDS):
            low, high = FINANCE_RPM
            factors.append("Money/business topic: advertisers pay the most here")
        else:
            low, high = CATEGORY_RPM.get(category, DEFAULT_RPM)
            factors.append(f"Category “{category or 'unknown'}”: about ${low:g}–${high:g} per 1,000 views for a US audience")

        country = (channel or {}).get("country")
        language = (video_extra or {}).get("audio_language") or info.get("language") or ""
        language = language.split("-")[0].lower()
        if country and country in COUNTRY_FACTOR:
            f = COUNTRY_FACTOR[country]
            factors.append(f"Channel country {country}: audience worth about {f:.0%} of a US audience")
        elif language in LANGUAGE_FACTOR:
            f = LANGUAGE_FACTOR[language]
            factors.append(f"Spoken language “{language}”: audience worth about {f:.0%} of a US audience")
        else:
            f = 0.5
            factors.append("Audience country unknown: assumed a mixed worldwide audience")
        low, high = low * f, high * f

        if duration >= MIDROLL_MIN_SECONDS:
            high *= 1.3
            factors.append("8 minutes or longer, so mid-roll ads are allowed")
        if (video_extra or {}).get("made_for_kids") or (channel or {}).get("made_for_kids"):
            low, high = low * 0.3, high * 0.4
            factors.append("Made for kids: personalised ads are off, so earnings drop sharply")
        if category == "Music":
            factors.append("Music: much of this usually goes to the label and songwriters")

    subscribers = info.get("channel_follower_count")
    monetized_likely = not subscribers or subscribers >= 1000
    if not monetized_likely:
        factors.append("Under 1,000 subscribers: the channel probably can’t run ads yet")

    age_days = max((_now() - (info.get("timestamp") or _now())) / 86400, 1)
    result = {
        "currency": "USD",
        "rpm": [round(low, 2), round(high, 2)],
        "total": [_round_money(views / 1000 * low), _round_money(views / 1000 * high)],
        "per_day": [_round_money(views / age_days / 1000 * low), _round_money(views / age_days / 1000 * high)],
        "monetized_likely": monetized_likely,
        "factors": factors,
    }
    if sponsor_seconds:
        # Integrations are usually priced at ~$10–$30 per 1,000 expected views
        result["sponsorship"] = [_round_money(views / 1000 * 10), _round_money(views / 1000 * 30)]
    return result


# ─── Forecast ───
def forecast(info):
    """Views likely gained in the next 30 days, assuming growth slows like most videos do.

    Lifetime views tend to grow like t^a (a ≈ 0.25–0.5): fast at first, then a long tail."""
    views = info.get("view_count")
    ts = info.get("timestamp")
    if not views or not ts:
        return None
    age = max((_now() - ts) / 86400, 0.5)
    low_a, high_a = (0.25, 0.5) if age > 30 else (0.35, 0.65)
    gain = lambda a: views * (((age + 30) / age) ** a - 1)
    return {
        "age_days": round(age, 1),
        "views_per_day_lifetime": round(views / age),
        "next_30_days": [int(gain(low_a)), int(gain(high_a))],
        "stage": "launch" if age < 3 else "growing" if age < 30 else "settling" if age < 365 else "long tail",
    }


# ─── Best moments from the "most replayed" heatmap ───
def best_moments(info, limit=3):
    heatmap = info.get("heatmap") or []
    if len(heatmap) < 10:
        return {"available": False, "heatmap": [], "moments": []}
    values = [h["value"] for h in heatmap]
    mean = sum(values) / len(values)
    # The first seconds always spike (everyone starts there), so ignore the first 3% for peaks
    skip = max(1, len(heatmap) // 33)
    candidates = []
    for i in range(skip, len(heatmap)):
        left = values[i - 1]
        right = values[i + 1] if i + 1 < len(values) else -1
        if values[i] >= left and values[i] >= right and values[i] > mean * 1.15:
            candidates.append(i)
    candidates.sort(key=lambda i: values[i], reverse=True)

    picked = []
    min_gap = max(3, len(heatmap) // 12)
    for i in candidates:
        if all(abs(i - j) >= min_gap for j in picked):
            picked.append(i)
        if len(picked) == limit:
            break

    duration = info.get("duration") or heatmap[-1]["end_time"]
    moments = []
    for i in sorted(picked):
        # Widen to the neighbouring segments that are still well above average
        lo = hi = i
        while lo > skip and values[lo - 1] > mean * 1.1 and i - lo < 4:
            lo -= 1
        while hi + 1 < len(values) and values[hi + 1] > mean * 1.1 and hi - i < 4:
            hi += 1
        start = max(0, heatmap[lo]["start_time"] - 2)
        end = min(duration, heatmap[hi]["end_time"] + 2)
        moments.append({
            "start": round(start, 1), "end": round(end, 1), "peak": round(heatmap[i]["start_time"], 1),
            "strength": round(values[i] / mean, 1),
            "chapter": _chapter_at(info, heatmap[i]["start_time"]),
        })
    return {
        "available": True,
        "heatmap": [round(v, 3) for v in values],
        "segment_seconds": round(heatmap[0]["end_time"] - heatmap[0]["start_time"], 2),
        "moments": moments,
    }


def _chapter_at(info, t):
    for ch in info.get("chapters") or []:
        if (ch.get("start_time") or 0) <= t < (ch.get("end_time") or math.inf):
            return ch.get("title")
    return None


# ─── SEO checklist ───
def seo_report(info):
    title = info.get("title") or ""
    desc = info.get("description") or ""
    tags = info.get("tags") or []
    duration = info.get("duration") or 0
    title_words = {w for w in re.findall(r"\w+", title.lower()) if len(w) > 3}
    tag_words = {w for t in tags for w in re.findall(r"\w+", t.lower())}
    hashtags = re.findall(r"#\w+", desc)
    max_height = max((f.get("height") or 0 for f in info.get("formats") or []), default=0)

    checks = [
        ("Title length", 20 <= len(title) <= 70, 15, f"{len(title)} characters (best: 20–70, so it isn’t cut off)"),
        ("Title isn’t shouting", not (title.isupper() and len(title) > 10), 5, "Mostly lowercase reads as more trustworthy"),
        ("Tags match the title", bool(title_words & tag_words), 10, f"{len(tags)} tags" if tags else "No tags found"),
        ("Enough tags", len(tags) >= 5, 5, "5 or more helps YouTube understand the topic"),
        ("Detailed description", len(desc) >= 250, 15, f"{len(desc)} characters (aim for 250+)"),
        ("Title words in description", any(w in desc.lower() for w in title_words), 10, "Repeating key title words helps search"),
        ("Hashtags", 1 <= len(hashtags) <= 15, 5, f"{len(hashtags)} hashtags (1–15 is the sweet spot)"),
        ("Chapters", bool(info.get("chapters")) or duration < 300, 15,
         f"{len(info.get('chapters') or [])} chapters" if duration >= 300 else "Short video, chapters not needed"),
        ("Creator-made captions", bool(info.get("subtitles")), 10, f"{len(info.get('subtitles') or {})} languages"),
        ("HD quality", max_height >= 1080, 10, f"Up to {max_height}p" if max_height else "Unknown"),
    ]
    total = sum(p for _, _, p, _ in checks)
    score = sum(p for _, ok, p, _ in checks if ok)
    return {
        "score": round(score / total * 100),
        "checks": [{"label": label, "passed": ok, "detail": detail} for label, ok, _, detail in checks],
    }


# ─── Engagement ───
def engagement(info, dislikes=None):
    views = info.get("view_count") or 0
    likes = info.get("like_count")
    comments = info.get("comment_count")
    if not views:
        return None
    like_rate = likes / views if likes is not None else None
    result = {
        "like_rate": round(like_rate * 100, 2) if like_rate is not None else None,
        "comment_rate": round(comments / views * 1000, 2) if comments is not None else None,
        "verdict": None,
    }
    if like_rate is not None:
        result["verdict"] = ("exceptional" if like_rate >= 0.06 else "strong" if like_rate >= 0.035
                             else "typical" if like_rate >= 0.015 else "low")
    if dislikes and dislikes.get("dislikes") is not None and likes:
        total = likes + dislikes["dislikes"]
        result["dislikes"] = dislikes["dislikes"]
        result["approval"] = round(likes / total * 100, 1) if total else None
    return result


# ─── Free outside sources ───
SPONSORBLOCK = "https://sponsor.ajay.app/api/skipSegments"
SEGMENT_LABELS = {"sponsor": "Paid sponsor", "selfpromo": "Self-promotion", "interaction": "Subscribe reminder",
                  "intro": "Intro", "outro": "Outro / end cards", "music_offtopic": "Non-music section",
                  "preview": "Preview / recap", "filler": "Filler"}


def sponsor_segments(video_id):
    try:
        r = requests.get(SPONSORBLOCK, params={"videoID": video_id, "categories": str(list(SEGMENT_LABELS)).replace("'", '"')},
                         timeout=6)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return [{"category": s["category"], "label": SEGMENT_LABELS.get(s["category"], s["category"]),
                 "start": round(s["segment"][0], 1), "end": round(s["segment"][1], 1)} for s in r.json()]
    except Exception:
        return None  # unknown, not "none"


def dislike_estimate(video_id):
    try:
        r = requests.get("https://returnyoutubedislikeapi.com/votes", params={"videoId": video_id}, timeout=6)
        r.raise_for_status()
        data = r.json()
        return {"dislikes": data.get("dislikes"), "rating": data.get("rating")}
    except Exception:
        return None


# ─── Everything for one video ───
def video_insights(url):
    info = extract_info_safe(url)
    vid = info.get("id")
    with ThreadPoolExecutor(max_workers=4) as pool:
        sponsor_f = pool.submit(sponsor_segments, vid)
        dislike_f = pool.submit(dislike_estimate, vid)
        channel_f = pool.submit(lambda: ytapi.channel(info["channel_id"]) if ytapi.enabled() and info.get("channel_id") else None)
        extra_f = pool.submit(lambda: ytapi.video(vid) if ytapi.enabled() else None)
        segments, dislikes = sponsor_f.result(), dislike_f.result()
        channel, extra = _safe(channel_f), _safe(extra_f)

    sponsor_seconds = sum(s["end"] - s["start"] for s in segments or [] if s["category"] == "sponsor")
    duration = info.get("duration") or 0
    earnings = estimate_earnings(info, channel, extra, sponsor_seconds)
    outlook = forecast(info)
    if outlook:
        low_rpm, high_rpm = earnings["rpm"]
        low_views, high_views = outlook["next_30_days"]
        earnings["next_30_days"] = [_round_money(low_views / 1000 * low_rpm), _round_money(high_views / 1000 * high_rpm)]
    return {
        "video_id": vid,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "channel_url": info.get("channel_url"),
        "channel_id": info.get("channel_id"),
        "duration_seconds": duration,
        "published": info.get("timestamp"),
        "views": info.get("view_count"),
        "earnings": earnings,
        "forecast": outlook,
        "engagement": engagement(info, dislikes),
        "moments": best_moments(info),
        "seo": seo_report(info),
        "sponsor_segments": segments,
        "sponsor_seconds": round(sponsor_seconds),
        "technical": {
            "max_height": max((f.get("height") or 0 for f in info.get("formats") or []), default=0) or None,
            "fps": info.get("fps"),
            "hdr": (info.get("dynamic_range") or "SDR") != "SDR",
            "language": info.get("language"),
            "caption_languages": sorted((info.get("subtitles") or {}).keys()),
            "embeddable": info.get("playable_in_embed"),
            "age_restricted": (info.get("age_limit") or 0) > 0,
            "live": info.get("live_status"),
            "made_for_kids": (extra or {}).get("made_for_kids"),
            "topics": (extra or {}).get("topics") or [],
        },
        "data_api": ytapi.enabled(),
    }


def _safe(future):
    try:
        return future.result()
    except Exception as e:
        print(f"⚠️ [DATA API] {e}")
        return None
