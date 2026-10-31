import pytest

from core.validators import is_thumbnail_url, is_valid_target, is_youtube_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/shorts/abc",
    "https://m.youtube.com/watch?v=abc",
    "https://music.youtube.com/watch?v=abc",
    "http://youtu.be/dQw4w9WgXcQ",
    "  https://youtu.be/abc  ",
])
def test_accepts_youtube_urls(url):
    assert is_youtube_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com/watch?v=abc",
    "https://youtube.com.evil.com/watch",
    "https://evilyoutube.com/watch",
    "https://evil.com/?next=youtube.com",
    "http://youtube.com@169.254.169.254/latest/meta-data",
    "http://169.254.169.254/latest/meta-data",
    "file:///etc/passwd",
    "ftp://youtube.com/x",
    "youtube.com/watch?v=abc",
    "",
    None,
])
def test_rejects_non_youtube_urls(url):
    assert not is_youtube_url(url)


def test_thumbnail_hosts():
    assert is_thumbnail_url("https://i.ytimg.com/vi/abc/maxresdefault.jpg")
    assert not is_thumbnail_url("http://localhost:8001/api/files/x")
    assert not is_thumbnail_url("https://i.ytimg.com.evil.com/a.jpg")


def test_targets():
    assert is_valid_target("video", "1080p")
    assert is_valid_target("video", "720")
    assert not is_valid_target("video", "1080p; rm -rf /")
    assert is_valid_target("audio", "MP3")
    assert not is_valid_target("audio", "exe")
    assert is_valid_target("thumbnail", "1280x720")
    assert not is_valid_target("thumbnail", "../../etc")
