import os
import shutil
from contextlib import asynccontextmanager

# ─── Load .env BEFORE anything else ───
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())


from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional

from pydantic import BaseModel
from starlette.background import BackgroundTask
import uvicorn

from core.metadata import fetch_metadata
from core.video import fetch_video_resolutions, download_video
from core.audio import fetch_audio_formats, download_audio
from core.thumbnail import fetch_thumbnail_options, download_thumbnail
from core.subtitles import fetch_subtitle_tracks, download_subtitles
from core.validators import is_youtube_url, is_valid_target
from core.rate_limit import RateLimiter
from core.jobs import JobManager, QueueFullError
from core.yt_helper import cookie_status, recent_errors
from core import keepalive, warp, ytapi
from core.insights import video_insights
from core.channel_report import channel_report
from core.comment_insights import comment_insights
from core.transcript_insights import transcript_insights
from core.errors import friendly_error
import yt_dlp

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

# ─── Limits (all overridable from .env) ───
lookup_limit = RateLimiter(int(os.getenv("RATE_LIMIT_LOOKUPS_PER_MINUTE", 30)), 60)
# Comments are the slowest lookup (one request per 20 comments), so they get a tighter limit
heavy_limit = RateLimiter(int(os.getenv("RATE_LIMIT_HEAVY_PER_MINUTE", 8)), 60)
download_limit = RateLimiter(int(os.getenv("RATE_LIMIT_DOWNLOADS_PER_HOUR", 20)), 3600)
jobs = JobManager(
    DOWNLOADS_DIR,
    max_workers=int(os.getenv("MAX_CONCURRENT_DOWNLOADS", 2)),
    max_pending=int(os.getenv("MAX_PENDING_DOWNLOADS", 10)),
    ttl_seconds=int(os.getenv("FILE_TTL_SECONDS", 900)),
    error_formatter=friendly_error,
)


@asynccontextmanager
async def lifespan(app):
    jobs.cleanup()
    jobs.start_janitor()
    warp.start_in_background()
    keepalive.start()
    yield


app = FastAPI(title="YouTube Downloader API", lifespan=lifespan)

# ─── CORS: read frontend URL from env ───
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Support comma-separated origins for multiple frontends (e.g. dev + prod)
# (browsers send the origin without a trailing slash, so strip any from the env value)
allowed_origins = [origin.strip().rstrip("/") for origin in FRONTEND_URL.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    target: str
    # Optional clip, in seconds (video and audio only)
    start: Optional[float] = None
    end: Optional[float] = None


def require_youtube_url(url: str):
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Only YouTube links (youtube.com / youtu.be) are supported.")
    return url.strip()


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
    return {
        "status": "ok" if healthy else "degraded",
        "dependencies": dependencies,
        "cookies": cookie_status(),
        "proxy_configured": bool(os.getenv("YOUTUBE_PROXY")),
        "warp": {**warp.status, "active": bool(warp.proxy_url())},
        "keep_alive": keepalive.status,
        "trust_proxy": os.getenv("TRUST_PROXY") == "1",
        "youtube_data_api": ytapi.enabled(),
        "recent_youtube_errors": list(recent_errors),
    }


def run_lookup(label, fetch, url, count_key):
    url = require_youtube_url(url)
    try:
        data = fetch(url)
        print(f"✅ [{label} SUCCESS] Fetched {len(data.get(count_key) or {})} options for: '{data.get('title', 'Video')}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [{label} ERROR] {e}")
        raise HTTPException(status_code=500, detail=friendly_error(e))

@app.get("/api/metadata", dependencies=[Depends(lookup_limit)])
def get_metadata(url: str):
    url = require_youtube_url(url)
    try:
        data = fetch_metadata(url)
        print(f"✅ [METADATA SUCCESS] Fetched metadata for: '{data.get('title', 'Video')}'")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [METADATA ERROR] {e}")
        raise HTTPException(status_code=500, detail=friendly_error(e))

@app.get("/api/video/resolutions", dependencies=[Depends(lookup_limit)])
def get_video_res(url: str):
    return run_lookup("VIDEO RESOLUTIONS", fetch_video_resolutions, url, "resolutions")

@app.get("/api/audio/formats", dependencies=[Depends(lookup_limit)])
def get_audio_fmt(url: str):
    return run_lookup("AUDIO FORMATS", fetch_audio_formats, url, "formats")

@app.get("/api/thumbnail/resolutions", dependencies=[Depends(lookup_limit)])
def get_thumb_res(url: str):
    return run_lookup("THUMBNAIL", fetch_thumbnail_options, url, "resolutions")

@app.get("/api/subtitles", dependencies=[Depends(lookup_limit)])
def get_subtitles(url: str):
    return run_lookup("SUBTITLES", fetch_subtitle_tracks, url, "tracks")


# ─── Insights (estimates and analysis from public data) ───

def run_insight(label, build, url):
    url = require_youtube_url(url)
    try:
        data = build(url)
        print(f"📊 [{label}] {url}")
        return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ [{label} ERROR] {e}")
        raise HTTPException(status_code=500, detail=friendly_error(e))

@app.get("/api/insights", dependencies=[Depends(lookup_limit)])
def get_insights(url: str):
    return run_insight("INSIGHTS", video_insights, url)

@app.get("/api/insights/channel", dependencies=[Depends(lookup_limit)])
def get_channel_insights(url: str):
    return run_insight("CHANNEL INSIGHTS", channel_report, url)

@app.get("/api/insights/transcript", dependencies=[Depends(lookup_limit)])
def get_transcript_insights(url: str):
    return run_insight("TRANSCRIPT INSIGHTS", transcript_insights, url)

@app.get("/api/insights/comments", dependencies=[Depends(heavy_limit)])
def get_comment_insights(url: str):
    return run_insight("COMMENT INSIGHTS", comment_insights, url)


# ─── Downloads run as background jobs ───
# POST /api/download/<kind>          -> {"task_id": ...} immediately
# GET  /api/download/progress/<id>   -> poll until status is "completed" or "error"
# GET  /api/files/<id>               -> the file (deleted from the server once sent)

DOWNLOADERS = {
    "video": lambda url, target, clip: lambda out_dir, hook: download_video(url, target, out_dir, hook, clip),
    "audio": lambda url, target, clip: lambda out_dir, hook: download_audio(url, target, out_dir, hook, clip),
    "thumbnail": lambda url, target, clip: lambda out_dir, hook: download_thumbnail(url, target, out_dir),
    "subtitles": lambda url, target, clip: lambda out_dir, hook: download_subtitles(url, target, out_dir),
}
CLIPPABLE = ("video", "audio")


def read_clip(kind, req):
    if req.start is None and req.end is None:
        return None
    if kind not in CLIPPABLE:
        raise HTTPException(status_code=400, detail="Only video and audio downloads can be clipped.")
    if req.start is None or req.end is None or not 0 <= req.start < req.end:
        raise HTTPException(status_code=400, detail="Pick a clip start time that's before the end time.")
    return (req.start, req.end)

@app.post("/api/download/{kind}", dependencies=[Depends(download_limit)])
def start_download(kind: str, req: DownloadRequest):
    if kind not in DOWNLOADERS:
        raise HTTPException(status_code=404, detail="Unknown download type")
    url = require_youtube_url(req.url)
    target = req.target.strip()
    if not is_valid_target(kind, target):
        raise HTTPException(status_code=400, detail=f"Invalid {kind} option: '{target}'")
    clip = read_clip(kind, req)
    try:
        task_id = jobs.submit(kind, DOWNLOADERS[kind](url, target, clip))
    except QueueFullError as e:
        raise HTTPException(status_code=503, detail=str(e))
    print(f"⏳ [{kind.upper()} DOWNLOAD QUEUED] {target} → task {task_id[:8]}")
    return {"success": True, "task_id": task_id}

@app.get("/api/download/progress/{task_id}")
def get_download_progress(task_id: str):
    job = jobs.public_view(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="This download has expired or does not exist.")
    return job

@app.get("/api/files/{task_id}")
def serve_file(task_id: str):
    """Send a finished download to the browser, then delete it from the server."""
    job = jobs.get(task_id)
    if not job or job["status"] != "completed" or not os.path.isfile(job["path"] or ""):
        raise HTTPException(status_code=404, detail="File not found or already downloaded.")
    print(f"📦 [FILE SERVED SUCCESS] Delivered to browser: '{job['filename']}'")
    return FileResponse(
        job["path"],
        filename=job["filename"],
        media_type='application/octet-stream',
        background=BackgroundTask(jobs.release, task_id),
    )

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 Backend starting on {host}:{port}")
    print(f"🔗 Allowing CORS from: {allowed_origins}")
    uvicorn.run("server:app", host=host, port=port, reload=True)
