import os
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


def test_playlist_links_are_rejected(monkeypatch):
    from core import yt_helper

    monkeypatch.setattr(yt_helper, "_extract_with_fallbacks",
                        lambda url, download, extra_opts: {"_type": "playlist", "entries": []})
    try:
        yt_helper.extract_info_safe("https://www.youtube.com/playlist?list=PL123")
    except ValueError as e:
        assert "single video" in str(e)
    else:
        raise AssertionError("playlist was not rejected")


def test_only_the_video_is_fetched_from_mix_links():
    from core.yt_helper import get_base_ydl_opts

    assert get_base_ydl_opts(use_cookies=False)["noplaylist"] is True


def test_read_only_cookie_file_is_copied_somewhere_writable(tmp_path, monkeypatch):
    from core import yt_helper

    secret = tmp_path / "youtube_cookies.txt"
    secret.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n")
    secret.chmod(0o444)
    monkeypatch.delenv("YOUTUBE_COOKIES_TEXT", raising=False)
    monkeypatch.setenv("YOUTUBE_COOKIE_FILE", str(secret))
    monkeypatch.setattr(yt_helper, "_cookie_copy", None)

    cookiefile = yt_helper.get_base_ydl_opts()["cookiefile"]

    assert cookiefile != str(secret)
    assert os.access(cookiefile, os.W_OK)
    assert open(cookiefile).read() == secret.read_text()
