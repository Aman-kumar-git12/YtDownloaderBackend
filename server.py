from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
import urllib.parse

from core.metadata import fetch_metadata
from core.video import fetch_video_resolutions, download_video
from core.audio import fetch_audio_formats, download_audio
from core.thumbnail import fetch_thumbnail_options, download_thumbnail

app = FastAPI(title="YouTube Downloader API")

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/api/metadata")
def get_metadata(url: str):
    try:
        data = fetch_metadata(url)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video/resolutions")
def get_video_res(url: str):
    try:
        data = fetch_video_resolutions(url)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio/formats")
def get_audio_fmt(url: str):
    try:
        data = fetch_audio_formats(url)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/thumbnail/resolutions")
def get_thumb_res(url: str):
    try:
        data = fetch_thumbnail_options(url)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/video")
def dl_video(req: DownloadRequest):
    try:
        filename = download_video(req.url, req.target)
        if filename:
            return {"success": True, "filename": filename}
        raise Exception("Download completed but could not determine filename")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/audio")
def dl_audio(req: DownloadRequest):
    try:
        filename = download_audio(req.url, req.target)
        if filename:
            return {"success": True, "filename": filename}
        raise Exception("Download completed but could not determine filename")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/thumbnail")
def dl_thumbnail(req: DownloadRequest):
    try:
        success, filepath = download_thumbnail(req.url, req.target, req.title)
        if success and filepath:
            return {"success": True, "filename": os.path.basename(filepath)}
        raise Exception("Thumbnail download failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{filename:path}")
def serve_file(filename: str):
    """Serve a downloaded file to the browser for saving to device."""
    decoded = urllib.parse.unquote(filename)
    filepath = os.path.join(DOWNLOADS_DIR, decoded)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        filepath,
        filename=decoded,
        media_type='application/octet-stream'
    )

# Simple helper to load .env file manually (avoids pip install python-dotenv)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key.strip()] = val.strip()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("server:app", host=host, port=port, reload=True)

