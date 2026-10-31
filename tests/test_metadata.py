from core import metadata


def test_handles_none_fields(monkeypatch):
    # yt-dlp often returns keys with None values (live streams, private stats...)
    info = {key: None for key in (
        "title", "id", "webpage_url", "uploader", "channel_url", "channel_follower_count",
        "upload_date", "duration", "view_count", "like_count", "comment_count", "description",
        "tags", "categories", "availability", "license", "age_limit", "chapters",
        "formats", "subtitles", "thumbnails", "is_live", "was_live",
    )}
    monkeypatch.setattr(metadata, "extract_info_safe", lambda url, download=False: info)

    data = metadata.fetch_metadata("https://youtu.be/x")

    assert data["title"] == "Unknown"
    assert data["duration"] is None
    assert data["upload_date"] is None
    assert data["privacy"] == "Unknown"
    assert data["age_restricted"] is False
    assert data["tags"] == [] and data["subtitles"] == []


def test_keeps_zero_counts_and_formats_values(monkeypatch):
    info = {
        "title": "T", "view_count": 0, "like_count": 0, "upload_date": "20240305",
        "duration": 192.5, "availability": "public", "age_limit": 18,
        "chapters": [{"start_time": 61.2, "title": "Intro"}],
    }
    monkeypatch.setattr(metadata, "extract_info_safe", lambda url, download=False: info)

    data = metadata.fetch_metadata("https://youtu.be/x")

    assert data["views"] == 0 and data["likes"] == 0
    assert data["upload_date"] == "2024-03-05"
    assert data["duration"] == "0:03:12"
    assert data["privacy"] == "Public"
    assert data["age_restricted"] is True
    assert data["chapters_preview"] == ["0:01:01: Intro"]


def test_format_upload_date_rejects_garbage():
    assert metadata.format_upload_date("2024") is None
    assert metadata.format_upload_date("abcdefgh") is None
