import os
import shutil
import urllib.parse

# ─── Load .env BEFORE anything else ───
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from core.metadata import fetch_metadata
from core.video import fetch_video_resolutions, download_video
from core.audio import fetch_audio_formats, download_audio
from core.thumbnail import fetch_thumbnail_options, download_thumbnail
import yt_dlp

app = FastAPI(title="YouTube Downloader API")

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

# ─── CORS: read frontend URL from env ───
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Support comma-separated origins for multiple frontends (e.g. dev + prod)
allowed_origins = [origin.strip() for origin in FRONTEND_URL.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    target: str
    title: str = ""
    task_id: str = ""

download_progress = {}


@app.get("/health")
def health_check():
    """Report the deployment dependencies needed for reliable downloads."""
    runtimes = [name for name in ("node", "deno", "bun", "qjs", "quickjs") if shutil.which(name)]
    dependencies = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "javascript_runtime": runtimes[0] if runtimes else None,
        "yt_dlp_version": yt_dlp.version.__version__,
    }
    healthy = dependencies["ffmpeg"] and dependencies["javascript_runtime"]
    return {"status": "ok" if healthy else "degraded", "dependencies": dependencies}

def make_progress_hook(task_id: str):
    def hook(d):
        if not task_id:
            return
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            pct = round((downloaded / total * 100), 1) if total > 0 else 0
            speed = d.get('speed') or 0
            speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 0 else ""
            eta = d.get('eta')
            eta_str = f"{eta}s" if eta is not None else ""
            download_progress[task_id] = {
                "status": "downloading",
                "percent": pct,
                "speed": speed_str,
                "eta": eta_str,
                "elapsed": round(d.get('elapsed', 0), 1)
            }
        elif status == 'finished':
            download_progress[task_id] = {
                "status": "processing",
                "percent": 99.0,
                "speed": "Merging/Processing...",
                "eta": "converting",
                "elapsed": round(d.get('elapsed', 0), 1)
            }
    return hook

@app.get("/api/download/progress/{task_id}")
def get_download_progress(task_id: str):
    return download_progress.get(task_id, {"status": "starting", "percent": 0})

@app.get("/api/metadata")
def get_metadata(url: str):
    try:
        data = fetch_metadata(url)
        title = data.get("title", "Video")
        print(f"✅ [METADATA SUCCESS] Fetched metadata for: '{title}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [METADATA ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video/resolutions")
def get_video_res(url: str):
    try:
        data = fetch_video_resolutions(url)
        title = data.get("title", "Video")
        res_count = len(data.get("resolutions", {}))
        print(f"✅ [VIDEO RESOLUTIONS SUCCESS] Fetched {res_count} resolutions for: '{title}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [VIDEO RESOLUTIONS ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio/formats")
def get_audio_fmt(url: str):
    try:
        data = fetch_audio_formats(url)
        title = data.get("title", "Video")
        fmt_count = len(data.get("formats", {}))
        print(f"✅ [AUDIO FORMATS SUCCESS] Fetched {fmt_count} audio formats for: '{title}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [AUDIO FORMATS ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/thumbnail/resolutions")
def get_thumb_res(url: str):
    try:
        data = fetch_thumbnail_options(url)
        title = data.get("title", "Video")
        count = len(data.get("resolutions", {}))
        print(f"✅ [THUMBNAIL SUCCESS] Fetched {count} thumbnail sizes for: '{title}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [THUMBNAIL ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/video")
def dl_video(req: DownloadRequest):
    try:
        hook = make_progress_hook(req.task_id) if req.task_id else None
        filename = download_video(req.url, req.target, progress_hook=hook)
        if filename:
            if req.task_id:
                download_progress[req.task_id] = {"status": "completed", "percent": 100}
            print(f"🎉 [VIDEO DOWNLOAD SUCCESS] File ready: '{filename}' ({req.target})")
            return {"success": True, "filename": filename}
        raise Exception("Download completed but could not determine filename")
    except Exception as e:
        if req.task_id:
            download_progress[req.task_id] = {"status": "error", "error": str(e)}
        print(f"❌ [VIDEO DOWNLOAD ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/audio")
def dl_audio(req: DownloadRequest):
    try:
        hook = make_progress_hook(req.task_id) if req.task_id else None
        filename = download_audio(req.url, req.target, progress_hook=hook)
        if filename:
            if req.task_id:
                download_progress[req.task_id] = {"status": "completed", "percent": 100}
            print(f"🎉 [AUDIO DOWNLOAD SUCCESS] File ready: '{filename}' ({req.target})")
            return {"success": True, "filename": filename}
        raise Exception("Download completed but could not determine filename")
    except Exception as e:
        if req.task_id:
            download_progress[req.task_id] = {"status": "error", "error": str(e)}
        print(f"❌ [AUDIO DOWNLOAD ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/thumbnail")
def dl_thumbnail(req: DownloadRequest):
    try:
        if req.task_id:
            download_progress[req.task_id] = {"status": "downloading", "percent": 0}
        success, filepath = download_thumbnail(req.url, req.target, req.title)
        if success and filepath:
            fn = os.path.basename(filepath)
            if req.task_id:
                download_progress[req.task_id] = {"status": "completed", "percent": 100}
            print(f"🎉 [THUMBNAIL DOWNLOAD SUCCESS] File ready: '{fn}'")
            return {"success": True, "filename": fn}
        raise Exception("Thumbnail download failed")
    except Exception as e:
        if req.task_id:
            download_progress[req.task_id] = {"status": "error", "error": str(e)}
        print(f"❌ [THUMBNAIL DOWNLOAD ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{filename:path}")
def serve_file(filename: str):
    """Serve a downloaded file to the browser for saving to device."""
    decoded = urllib.parse.unquote(filename)
    if not decoded or os.path.basename(decoded) != decoded:
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = os.path.join(DOWNLOADS_DIR, decoded)
    if not os.path.isfile(filepath):
        print(f"❌ [FILE SERVE ERROR] File not found: '{decoded}'")
        raise HTTPException(status_code=404, detail="File not found")
    print(f"📦 [FILE SERVED SUCCESS] Delivered to browser: '{decoded}'")
    return FileResponse(
        filepath,
        filename=decoded,
        media_type='application/octet-stream'
    )

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 Backend starting on {host}:{port}")
    print(f"🔗 Allowing CORS from: {allowed_origins}")
    uvicorn.run("server:app", host=host, port=port, reload=True)
