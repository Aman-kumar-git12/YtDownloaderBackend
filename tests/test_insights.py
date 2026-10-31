import time

from core import insights
from core.channel_report import _by_length, _upload_rhythm, outlier_label
from core.comment_insights import analyse as analyse_comments
from core.text_tools import detect_language, sentiment, top_keywords
from core.transcript_insights import _parse_json3, analyse as analyse_transcript


def video(**extra):
    base = {"id": "abc", "title": "How to invest your first salary", "view_count": 100_000, "like_count": 4_000,
            "comment_count": 300, "duration": 900, "categories": ["Education"], "language": "en",
            "timestamp": time.time() - 100 * 86400, "channel_follower_count": 50_000, "tags": ["invest", "money"]}
    return {**base, **extra}


# ─── text tools ───
def test_language_detection():
    assert detect_language("bhai ye video bahut accha hai") == "hi-latn"
    assert detect_language("यह वीडियो बहुत अच्छा है") == "hi"
    assert detect_language("this is the best video and you know it") == "en"
    assert detect_language("que video tan bueno, muy bien explicado") == "es"
    assert detect_language("12345 !!!") is None


def test_sentiment_handles_negation_and_emoji():
    assert sentiment("I love this, amazing") == 1
    assert sentiment("this is not good") == -1
    assert sentiment("total clickbait") == -1
    assert sentiment("🔥🔥") == 1
    assert sentiment("watched on tuesday") == 0


def test_keywords_skip_stopwords_and_excluded():
    texts = ["python tutorial is great", "great python course", "python rocks"]
    words = [k["word"] for k in top_keywords(texts, exclude=["rocks"])]
    assert words[0] == "python" and "great" in words and "is" not in words


# ─── earnings / forecast / engagement ───
def test_finance_topic_uses_higher_rpm():
    finance = insights.estimate_earnings(video())
    music = insights.estimate_earnings(video(title="Song", tags=[], categories=["Music"]))
    assert finance["rpm"][1] > music["rpm"][1]
    assert finance["total"][0] < finance["total"][1]


def test_country_lowers_rpm_and_kids_and_shorts():
    us = insights.estimate_earnings(video(), channel={"country": "US"})
    india = insights.estimate_earnings(video(), channel={"country": "IN"})
    assert india["rpm"][1] < us["rpm"][1]
    kids = insights.estimate_earnings(video(), video_extra={"made_for_kids": True})
    assert kids["rpm"][1] < insights.estimate_earnings(video())["rpm"][1]
    short = insights.estimate_earnings(video(duration=45))
    assert short["rpm"] == list(insights.SHORTS_RPM)


def test_small_channels_flagged_and_sponsorship_added():
    assert insights.estimate_earnings(video(channel_follower_count=300))["monetized_likely"] is False
    assert "sponsorship" in insights.estimate_earnings(video(), sponsor_seconds=40)


def test_forecast_and_engagement():
    f = insights.forecast(video())
    assert f["stage"] == "settling" and 0 < f["next_30_days"][0] < f["next_30_days"][1]
    assert insights.forecast(video(timestamp=None)) is None
    e = insights.engagement(video(), {"dislikes": 1000})
    assert e["like_rate"] == 4.0 and e["verdict"] == "strong" and e["approval"] == 80.0


def test_best_moments_skip_the_opening_spike():
    values = [1.0] + [0.2] * 40 + [0.9] + [0.2] * 58
    heatmap = [{"start_time": i * 6, "end_time": (i + 1) * 6, "value": v} for i, v in enumerate(values)]
    result = insights.best_moments({"heatmap": heatmap, "duration": 600,
                                    "chapters": [{"start_time": 200, "end_time": 300, "title": "The good bit"}]})
    assert result["available"]
    assert [m["peak"] for m in result["moments"]] == [246]
    assert result["moments"][0]["chapter"] == "The good bit"
    assert insights.best_moments({})["available"] is False


def test_seo_report_scores_checks():
    bare = insights.seo_report({"title": "x", "duration": 900})
    good = insights.seo_report({
        "title": "How to invest your first salary", "duration": 900, "tags": ["invest", "salary", "a", "b", "c"],
        "description": "How to invest your salary " + "x" * 300 + " #money", "chapters": [{}],
        "subtitles": {"en": []}, "formats": [{"height": 1080}],
    })
    assert bare["score"] < 30 < 90 < good["score"]


# ─── channel ───
def test_upload_rhythm_and_length_buckets():
    now = time.time()
    videos = [{"timestamp": now - d * 86400, "views": v, "duration": dur}
              for d, v, dur in [(1, 100, 200), (8, 300, 600), (15, 200, 700), (22, 100, 2000), (29, 100, 650)]]
    rhythm = _upload_rhythm(videos, exact=True)
    assert rhythm["per_week"] == 1.0 and rhythm["consistency"] == "very regular" and rhythm["status"] == "active"
    rows = {r["label"]: r for r in _by_length(videos, median=100)}
    assert rows["5–15 min"]["videos"] == 3 and rows["5–15 min"]["vs_channel"] == 2.0
    assert outlier_label(4) == "breakout" and outlier_label(0.3) == "below usual"


# ─── comments / transcript ───
def test_comment_analysis():
    comments = [
        {"text": "I love this video, amazing", "like_count": 50},
        {"text": "How did you edit this?", "like_count": 30},
        {"text": "bhai bahut accha video hai", "like_count": 5},
        {"text": "worst clickbait ever", "like_count": 1, "is_pinned": True},
    ]
    result = analyse_comments({"title": "My video", "comment_count": 4}, comments)
    assert result["mood"] == {"positive": 25, "neutral": 50, "negative": 25}
    assert result["questions"][0]["text"] == "How did you edit this?"
    assert result["top_comment"]["likes"] == 50 and result["pinned"]["likes"] == 1
    assert {l["code"] for l in result["languages"]} == {"en", "hi-latn"}
    assert analyse_comments({}, [])["sampled"] == 0


def test_transcript_analysis():
    raw = '{"events":[{"tStartMs":0,"dDurationMs":30000,"segs":[{"utf8":"today we invest money"}]},' \
          '{"tStartMs":30000,"dDurationMs":30000,"segs":[{"utf8":"investing money is simple"}]},{"tStartMs":60000}]}'
    lines = _parse_json3(raw)
    assert len(lines) == 2
    result = analyse_transcript({"title": "Invest money wisely", "duration": 60}, lines)
    assert result["word_count"] == 8 and result["words_per_minute"] == 8 and result["speech_share"] == 100
    assert result["title_words_in_first_minute"]["found"] == ["invest", "money"]
    assert result["hook"].startswith("today we invest")


def test_insight_endpoints_reject_bad_urls(client):
    for path in ("/api/insights", "/api/insights/channel", "/api/insights/comments", "/api/insights/transcript"):
        assert client.get(path, params={"url": "https://evil.example/watch?v=x"}).status_code == 400


def test_insight_endpoint_returns_data(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "video_insights", lambda url: {"title": "ok"})
    r = client.get("/api/insights", params={"url": "https://youtu.be/abc"})
    assert r.status_code == 200 and r.json()["data"]["title"] == "ok"


def test_music_transcripts_do_not_quote_lyrics():
    lines = [(0, 10, "some words sung here"), (10, 20, "more words")]
    result = analyse_transcript({"title": "Song", "duration": 20, "categories": ["Music"]}, lines)
    assert result["hook"] == ""


def test_transcript_tries_the_next_track_and_reports_blocking(monkeypatch):
    from core import transcript_insights as ti
    info = {"title": "Talk", "duration": 60, "language": "en",
            "subtitles": {"en": [{"ext": "json3", "url": "u1"}], "fr": [{"ext": "json3", "url": "u2"}]}}
    monkeypatch.setattr(ti, "extract_info_safe", lambda url: info)
    good = '{"events":[{"tStartMs":0,"dDurationMs":60000,"segs":[{"utf8":"hello there friends"}]}]}'

    def fetch(url):
        if url == "u1":
            raise RuntimeError("HTTP Error 429")
        return good
    monkeypatch.setattr(ti, "fetch_url_text", fetch)
    assert ti._build("x")["word_count"] == 3

    monkeypatch.setattr(ti, "fetch_url_text", lambda url: (_ for _ in ()).throw(RuntimeError("403")))
    assert ti._build("x") == {"available": False, "reason": "blocked"}
