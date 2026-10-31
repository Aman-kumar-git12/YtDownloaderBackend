"""Channel health: how a video compares with the channel's usual, upload rhythm, what works best."""
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone

from core import ytapi
from core.cache import TTLCache
from core.yt_helper import extract_info_safe, extract_tab

RECENT_LIMIT = 30
_cache = TTLCache(ttl_seconds=900, max_entries=50)

DURATION_BUCKETS = [(0, 300, "Under 5 min"), (300, 900, "5–15 min"), (900, 1800, "15–30 min"), (1800, 10 ** 9, "30+ min")]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def _parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def outlier_label(score):
    if score is None:
        return None
    if score >= 3:
        return "breakout"
    if score >= 1.5:
        return "above usual"
    if score >= 0.67:
        return "usual"
    return "below usual"


def channel_report(url):
    info = extract_info_safe(url)
    channel_url = info.get("channel_url")
    if not channel_url:
        raise ValueError("This video doesn't list its channel.")
    report = _cache.get_or_compute(channel_url, lambda: _build(info))
    # The comparison depends on this video, the rest is per channel
    median = report["recent"]["median_views"]
    views = info.get("view_count")
    score = round(views / median, 2) if views is not None and median else None
    oldest = report["recent"]["oldest_timestamp"]
    # An old video has had years to collect views that recent uploads haven't, so say so
    older = bool(oldest and info.get("timestamp") and info["timestamp"] < oldest - 30 * 86400)
    return {**report, "this_video": {"views": views, "outlier_score": score, "label": outlier_label(score),
                                     "older_than_sample": older}}


def _build(info):
    channel_url = info["channel_url"]
    tab_info, videos = extract_tab(channel_url + "/videos", RECENT_LIMIT, approximate_dates=True)
    try:
        _, shorts = extract_tab(channel_url + "/shorts", 15)
    except Exception:
        shorts = []

    api_channel = api_uploads = None
    if ytapi.enabled() and info.get("channel_id"):
        try:
            api_channel = ytapi.channel(info["channel_id"])
            if api_channel and api_channel.get("uploads_playlist"):
                api_uploads = ytapi.recent_uploads(api_channel["uploads_playlist"])
        except Exception as e:
            print(f"⚠️ [DATA API] {e}")

    long_videos = [{"id": v.get("id"), "title": v.get("title"), "views": v.get("view_count"),
                    "duration": v.get("duration"), "timestamp": v.get("timestamp")} for v in videos]
    if api_uploads:
        # Exact times from the API beat the "3 weeks ago" approximations
        exact = {u["id"]: u for u in api_uploads}
        for v in long_videos:
            u = exact.get(v["id"])
            if u:
                v["timestamp"] = _parse_iso(u["published"]).timestamp()
                v["views"] = u["views"]

    views = [v["views"] for v in long_videos if v["views"] is not None]
    median = _median(views)
    subscribers = (api_channel or {}).get("subscribers") or info.get("channel_follower_count") or tab_info.get("channel_follower_count")

    top = sorted([v for v in long_videos if v["views"] is not None], key=lambda v: v["views"], reverse=True)
    breakouts = [dict(v, score=round(v["views"] / median, 1)) for v in top if median and v["views"] >= 3 * median][:5]

    report = {
        "channel": info.get("channel") or info.get("uploader"),
        "channel_url": channel_url,
        "verified": tab_info.get("channel_is_verified"),
        "subscribers": subscribers,
        "recent": {
            "count": len(long_videos),
            "median_views": median,
            "average_views": round(statistics.mean(views)) if views else None,
            "views_per_subscriber": round(median / subscribers, 3) if median and subscribers else None,
            "top": top[:3],
            "breakouts": breakouts,
            "oldest_timestamp": min((v["timestamp"] for v in long_videos if v.get("timestamp")), default=None),
        },
        "upload_rhythm": _upload_rhythm(long_videos, exact=bool(api_uploads)),
        "by_length": _by_length(long_videos, median),
        "shorts_vs_long": {
            "shorts_median_views": _median([s.get("view_count") for s in shorts]),
            "long_median_views": median,
            "shorts_sampled": len(shorts),
        },
        "best_posting": _best_posting(long_videos, median) if api_uploads else None,
        "profile": _profile(api_channel, subscribers),
        "data_api": ytapi.enabled(),
    }
    return report


def _upload_rhythm(videos, exact):
    stamps = sorted((v["timestamp"] for v in videos if v.get("timestamp")), reverse=True)
    if len(stamps) < 2:
        return None
    span_days = max((stamps[0] - stamps[-1]) / 86400, 1)
    per_week = (len(stamps) - 1) / span_days * 7
    gaps = [(a - b) / 86400 for a, b in zip(stamps, stamps[1:])]
    days_since = (time.time() - stamps[0]) / 86400
    consistency = None
    if exact and len(gaps) >= 4 and statistics.mean(gaps) > 0:
        # Coefficient of variation: 0 = clockwork, >1 = very irregular
        cv = statistics.pstdev(gaps) / statistics.mean(gaps)
        consistency = "very regular" if cv < 0.35 else "fairly regular" if cv < 0.75 else "irregular"
    return {
        "per_week": round(per_week, 1),
        "days_since_last": round(days_since, 1),
        "consistency": consistency,
        "exact": exact,
        "status": "active" if days_since < 30 else "slowing down" if days_since < 120 else "inactive",
    }


def _by_length(videos, median):
    rows = []
    for lo, hi, label in DURATION_BUCKETS:
        group = [v["views"] for v in videos if v.get("duration") is not None and v["views"] is not None and lo <= v["duration"] < hi]
        if group:
            m = _median(group)
            rows.append({"label": label, "videos": len(group), "median_views": m,
                         "vs_channel": round(m / median, 2) if median else None})
    return rows


def _best_posting(videos, median):
    """Median performance by weekday and by hour (UTC) of exact publish times."""
    by_day, by_hour = defaultdict(list), defaultdict(list)
    for v in videos:
        if not v.get("timestamp") or v["views"] is None or not median:
            continue
        dt = datetime.fromtimestamp(v["timestamp"], tz=timezone.utc)
        by_day[dt.weekday()].append(v["views"] / median)
        by_hour[dt.hour].append(v["views"] / median)
    days = [{"day": WEEKDAYS[d], "videos": len(r), "vs_channel": round(_median(r), 2)} for d, r in sorted(by_day.items())]
    hours = [{"hour_utc": h, "videos": len(r), "vs_channel": round(_median(r), 2)} for h, r in sorted(by_hour.items())]
    best_day = max((d for d in days if d["videos"] >= 2), key=lambda d: d["vs_channel"], default=None)
    common_hour = max(hours, key=lambda h: h["videos"], default=None)
    return {"days": days, "hours": hours, "best_day": best_day, "usual_hour_utc": common_hour}


def _profile(api_channel, subscribers):
    if not api_channel:
        return None
    created = _parse_iso(api_channel.get("created"))
    age_years = (datetime.now(timezone.utc) - created).days / 365.25 if created else None
    total_views, count = api_channel.get("total_views"), api_channel.get("video_count")
    return {
        "created": created.date().isoformat() if created else None,
        "age_years": round(age_years, 1) if age_years else None,
        "country": api_channel.get("country"),
        "total_views": total_views,
        "video_count": count,
        "views_per_video": round(total_views / count) if total_views and count else None,
        "subscribers_per_year": round(subscribers / age_years) if subscribers and age_years and age_years > 0.1 else None,
        "videos_per_year": round(count / age_years, 1) if count and age_years and age_years > 0.1 else None,
        "topics": api_channel.get("topics") or [],
        "made_for_kids": api_channel.get("made_for_kids"),
    }
