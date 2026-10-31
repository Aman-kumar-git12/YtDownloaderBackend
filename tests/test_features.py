from core.subtitles import get_subtitle_tracks
from core.validators import is_valid_target


def test_subtitle_tracks_skip_auto_translations():
    info = {
        "subtitles": {"en": [{"name": "English"}], "live_chat": [{}]},
        "automatic_captions": {"en-orig": [{"name": "English (Original)"}], "fr": [{"name": "French"}], "de": [{}]},
    }
    assert get_subtitle_tracks(info) == [
        {"id": "en:manual", "name": "English", "auto": False},
        {"id": "en-orig:auto", "name": "English", "auto": True},
    ]


def test_subtitle_targets():
    assert is_valid_target("subtitles", "en:manual:srt")
    assert is_valid_target("subtitles", "pt-BR:auto:vtt")
    assert not is_valid_target("subtitles", "en:manual:exe")
    assert not is_valid_target("subtitles", "../x:manual:srt")


def test_clip_validation(client):
    body = {"url": "https://youtu.be/x", "target": "720p"}
    assert client.post("/api/download/video", json={**body, "start": 20, "end": 10}).status_code == 400
    assert client.post("/api/download/video", json={**body, "start": 5}).status_code == 400
    assert client.post("/api/download/thumbnail", json={"url": "https://youtu.be/x", "target": "1280x720", "start": 0, "end": 5}).status_code == 400


def test_clip_is_passed_to_the_downloader(client, monkeypatch):
    import server
    seen = {}

    def fake(url, target, out_dir, hook, clip):
        seen["clip"] = clip
        raise RuntimeError("stop")

    monkeypatch.setattr(server, "download_audio", fake)
    assert client.post("/api/download/audio", json={"url": "https://youtu.be/x", "target": "mp3", "start": 30, "end": 45.5}).status_code == 200
    import time
    for _ in range(50):
        if "clip" in seen:
            break
        time.sleep(0.02)
    assert seen["clip"] == (30, 45.5)


def test_keep_alive_is_off_without_a_public_url(monkeypatch):
    from core import keepalive
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    keepalive.status["enabled"] = False
    keepalive.start()
    assert keepalive.status["enabled"] is False
