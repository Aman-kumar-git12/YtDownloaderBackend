# YT Downloader — Backend

FastAPI service that wraps [yt-dlp](https://github.com/yt-dlp/yt-dlp) to fetch YouTube metadata and download video, audio and thumbnails. The React frontend lives in the separate `YtDownloaderWeb` repo.

> **Personal / educational use only.** Downloading from YouTube may violate its Terms of Service. Only download content you have the right to, and don't expose a public instance without the limits below.

## Requirements

- Python 3.11+
- **FFmpeg** (merges video + audio, converts audio formats)
- **Node.js** (or Deno/Bun): yt-dlp uses it to solve YouTube's JavaScript challenges

Check them with `GET /health`. It reports `degraded` if either is missing.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py            # http://localhost:8001, docs at /docs
```

There is also a terminal client: `python main.py` (with the server running).

## Run with Docker

```bash
docker build -t yt-backend .
docker run -p 8001:8001 --env-file .env yt-backend
```

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/metadata?url=` | Title, channel, stats, tags, chapters… |
| GET | `/api/video/resolutions?url=` | Available resolutions with estimated sizes |
| GET | `/api/audio/formats?url=` | MP3 / M4A / WAV / FLAC / AAC with estimated sizes |
| GET | `/api/thumbnail/resolutions?url=` | Thumbnail sizes (with preview URLs) |
| GET | `/api/subtitles?url=` | Uploaded subtitles in every language, plus auto-generated captions in the video's language |
| POST | `/api/download/{video\|audio\|thumbnail\|subtitles}` | Body `{"url", "target"}`, plus optional `"start"`/`"end"` seconds to clip video or audio → `{"task_id"}` |
| GET | `/api/download/progress/{task_id}` | `status` (`queued` → `downloading` → `processing` → `completed` / `error`), `percent`, `speed`, `filename`, `error` |
| GET | `/api/files/{task_id}` | The finished file. **Deleted from the server after it's sent.** |

### Insights

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/insights?url=` | Estimated earnings (range, per day, next 30 days, sponsor deal), 30-day view forecast, engagement and approval (estimated dislikes), most-replayed moments, SEO checklist, SponsorBlock segments, technical facts |
| GET | `/api/insights/channel?url=` | How the video compares with the channel's last 30 uploads (outlier score), breakouts, upload rhythm, views by video length, Shorts vs long videos; with a Data API key also channel age, country, total views, topics and best posting day |
| GET | `/api/insights/comments?url=` | Mood, top questions, recurring words, top comment and likely audience languages from the top 150 comments (slow: ~10 s, limited to 8/min) |
| GET | `/api/insights/transcript?url=` | Speaking pace, talking time, topics, the first 30 seconds and whether it repeats the title |

**Everything about money and audience countries is an estimate.** YouTube only shows real revenue and per-country views to the channel owner. The web app's "Your real numbers" card lets owners sign in with Google to see their own (see the frontend README).

Earnings use typical creator RPM by category (higher for money/business topics), adjusted for the channel's country (or the spoken language), Shorts, video length (mid-rolls at 8+ min) and made-for-kids. The forecast assumes lifetime views grow like `t^a` with `a` between 0.25 and 0.5.

Optional: set `YOUTUBE_API_KEY` (free, 10,000 units a day; each channel report costs about 3) for channel creation date, country, topics, made-for-kids and exact posting times. Create one at https://console.cloud.google.com → APIs & Services → enable **YouTube Data API v3** → Credentials → API key.

Downloads run as background jobs, so long videos don't hit proxy request timeouts: start a job, poll progress, then fetch the file. `target` is a resolution like `720p`, an audio format like `mp3`, a thumbnail size like `1280x720`, or a subtitle track like `en:manual:srt` / `en-orig:auto:vtt`. MP3, M4A and FLAC downloads get title/artist tags and the thumbnail as cover art.

## Keep-awake on Render's free plan

Render stops free services after 15 idle minutes. When `RENDER_EXTERNAL_URL` is set (Render sets it automatically), the server pings its own `/health` every 10 minutes so visitors don't wait for a cold start. One always-on service uses about 744 of the 750 free instance hours per month. Disable with `KEEP_ALIVE=0`.

## Safety limits

- Only `youtube.com` / `youtu.be` URLs are accepted (blocks SSRF via yt-dlp's generic extractor).
- Thumbnail URLs are looked up server-side; clients can't make the server fetch arbitrary URLs.
- Per-IP rate limits on lookups and downloads (in-memory). **Behind a reverse proxy set `TRUST_PROXY=1`**, otherwise all users share the proxy's IP and one limit.
- Each job writes to its own `downloads/<task_id>/` folder; files are deleted once served or after `FILE_TTL_SECONDS`.
- Limited concurrent / queued jobs (`MAX_CONCURRENT_DOWNLOADS`, `MAX_PENDING_DOWNLOADS`).

All limits are configurable. See `.env.example`.

Jobs and rate limits are kept in memory, so run a **single worker process**. Use Redis if you ever need to scale out.

## Cookies

Cloud IPs are often bot-checked by YouTube. You can supply cookies via `YOUTUBE_COOKIES_TEXT` (Netscape format) or a file at `core/youtube_cookies.txt`. Both are git-ignored. Use a throwaway account: cookies grant full access to that Google account.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
