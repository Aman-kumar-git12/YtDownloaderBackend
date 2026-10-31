import os
import time

import server


def test_rejects_non_youtube_urls(client):
    for path in ("/api/metadata", "/api/video/resolutions", "/api/audio/formats", "/api/thumbnail/resolutions"):
        resp = client.get(path, params={"url": "http://169.254.169.254/latest/meta-data"})
        assert resp.status_code == 400, path


def test_thumbnail_download_does_not_accept_arbitrary_urls(client):
    resp = client.post("/api/download/thumbnail", json={"url": "http://169.254.169.254/", "target": "1280x720"})
    assert resp.status_code == 400


def test_rejects_invalid_targets(client):
    resp = client.post("/api/download/audio", json={"url": "https://youtu.be/x", "target": "exe"})
    assert resp.status_code == 400
    resp = client.post("/api/download/zip", json={"url": "https://youtu.be/x", "target": "1"})
    assert resp.status_code == 404


def test_download_flow_serves_file_once(client, monkeypatch):
    def fake_download(url, target, out_dir, hook):
        path = os.path.join(out_dir, f"My Video_{target}.mp4")
        with open(path, "wb") as f:
            f.write(b"video-bytes")
        return path

    monkeypatch.setattr(server, "download_video", fake_download)

    resp = client.post("/api/download/video", json={"url": "https://youtu.be/x", "target": "720p"})
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    for _ in range(100):
        progress = client.get(f"/api/download/progress/{task_id}").json()
        if progress["status"] == "completed":
            break
        time.sleep(0.02)
    assert progress["filename"] == "My Video_720p.mp4"

    file_resp = client.get(f"/api/files/{task_id}")
    assert file_resp.status_code == 200
    assert file_resp.content == b"video-bytes"
    assert "My%20Video_720p.mp4" in file_resp.headers["content-disposition"] or "My Video_720p.mp4" in file_resp.headers["content-disposition"]

    # Deleted after being served
    assert client.get(f"/api/files/{task_id}").status_code == 404
    assert client.get(f"/api/download/progress/{task_id}").status_code == 404


def test_files_endpoint_rejects_unknown_ids(client):
    assert client.get("/api/files/..%2F.env").status_code == 404
    assert client.get("/api/files/" + "0" * 32).status_code == 404


def test_lookup_rate_limit(client, monkeypatch):
    monkeypatch.setattr(server.lookup_limit, "limit", 2)
    monkeypatch.setattr(server, "fetch_audio_formats", lambda url: {"title": "t", "formats": {}})

    codes = [client.get("/api/audio/formats", params={"url": "https://youtu.be/x"}).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
