import os
import tempfile
import threading
import time
from collections import deque

import yt_dlp

# Metadata lookups are cached so switching tabs (or starting a download) doesn't
# re-run a slow yt-dlp extraction and trigger YouTube's bot checks.
INFO_CACHE_TTL = int(os.getenv('INFO_CACHE_TTL_SECONDS', 300))
INFO_CACHE_MAX = 50
_info_cache = {}
_info_cache_lock = threading.Lock()

TEMP_SUFFIXES = ('.part', '.ytdl', '.temp', '.tmp')

_cookie_copy = None
_cookie_lock = threading.Lock()

def _writable_cookie_file():
    """yt-dlp writes refreshed cookies back to the cookie file, which fails on read-only
    mounts like Render's /etc/secrets. Copy the configured cookies (YOUTUBE_COOKIES_TEXT or
    YOUTUBE_COOKIE_FILE) to a temp file once per process and let yt-dlp keep it updated."""
    global _cookie_copy
    with _cookie_lock:
        if _cookie_copy and os.path.exists(_cookie_copy):
            return _cookie_copy

        content = os.getenv('YOUTUBE_COOKIES_TEXT')
        if not content:
            path = os.getenv('YOUTUBE_COOKIE_FILE', os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt'))
            if not (os.path.exists(path) and os.path.getsize(path) > 10):
                return None
            with open(path) as f:
                content = f.read()

        dest = os.path.join(tempfile.gettempdir(), 'yt_dlp_cookies.txt')
        with open(dest, 'w') as f:
            f.write(content.replace('\r\n', '\n'))
        _cookie_copy = dest
        return dest

def get_base_ydl_opts(extra_opts=None, use_cookies=True):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        # A watch link copied from a Mix/playlist carries "&list=..."; only fetch the video.
        'noplaylist': True,
        # If the link is a playlist/channel, list it cheaply so it can be rejected below.
        'extract_flat': 'in_playlist',
        'socket_timeout': 20,
        'retries': 3,
        'extractor_retries': 1,
    }

    # Support Proxy via environment variable (e.g. YOUTUBE_PROXY or HTTP_PROXY)
    proxy = os.getenv('YOUTUBE_PROXY') or os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')
    if proxy:
        opts['proxy'] = proxy

    if use_cookies:
        cookie_file = _writable_cookie_file()
        if cookie_file:
            opts['cookiefile'] = cookie_file

    if extra_opts:
        opts.update(extra_opts)

    return opts

def extract_info_safe(url, download=False, extra_opts=None):
    cacheable = not download and not extra_opts
    if cacheable:
        with _info_cache_lock:
            entry = _info_cache.get(url)
            if entry and time.time() - entry[0] < INFO_CACHE_TTL:
                return entry[1]

    if download:
        # Check what the link points to before downloading anything (usually cached)
        extract_info_safe(url)

    info = _extract_with_fallbacks(url, download, extra_opts)
    if info and info.get('_type') in ('playlist', 'multi_video'):
        raise ValueError("Playlists and channels aren't supported. Please paste a link to a single video.")

    if cacheable and info:
        with _info_cache_lock:
            if len(_info_cache) >= INFO_CACHE_MAX:
                oldest = min(_info_cache, key=lambda k: _info_cache[k][0])
                del _info_cache[oldest]
            _info_cache[url] = (time.time(), info)
    return info

def find_output_file(out_dir):
    """Return the finished file yt-dlp left in a job folder (ignores partial/temp files)."""
    files = [
        os.path.join(out_dir, name) for name in os.listdir(out_dir)
        if not name.startswith('.') and not name.endswith(TEMP_SUFFIXES)
    ]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise RuntimeError("Download finished but no output file was produced")
    return max(files, key=os.path.getmtime)

# None = let yt-dlp pick its default clients, which return the full format list.
# The forced combos only return a single low-quality stream but sometimes get
# through when YouTube blocks the defaults on cloud IPs.
CLIENT_COMBOS = [None, ['web_embedded', 'android'], ['mweb', 'android']]

# Errors that no other client/cookie combination will fix
PERMANENT_ERRORS = ('Video unavailable', 'Private video', 'has been removed',
                    'members-only', 'Join this channel', 'not available in your country')

recent_errors = deque(maxlen=10)

def _extract_with_fallbacks(url, download, extra_opts):
    has_cookies = 'cookiefile' in get_base_ydl_opts()
    attempts = [(combo, True) for combo in CLIENT_COMBOS] if has_cookies else []
    attempts += [(combo, False) for combo in CLIENT_COMBOS]

    last_err = None
    for combo, use_cookies in attempts:
        opts = get_base_ydl_opts(extra_opts, use_cookies=use_cookies)
        if combo:
            opts['extractor_args'] = {'youtube': {'player_client': combo}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception as e:
            last_err = e
            label = f"clients={combo or 'default'} cookies={'yes' if use_cookies else 'no'}"
            recent_errors.append({"time": time.strftime('%H:%M:%S'), "attempt": label, "error": str(e)[:300]})
            print(f"⚠️ [YT ATTEMPT FAILED] {label}: {str(e)[:200]}")
            if any(msg in str(e) for msg in PERMANENT_ERRORS):
                break

    if last_err:
        raise last_err

def cookie_status():
    """Describe the configured cookies without revealing them (shown on /health)."""
    path = get_base_ydl_opts().get('cookiefile')
    if not path:
        return {"configured": False}
    try:
        with open(path) as f:
            lines = [l for l in f if l.strip() and not l.startswith('#')]
    except OSError as e:
        return {"configured": True, "valid": False, "error": str(e)}
    names = {l.split('\t')[5] for l in lines if len(l.split('\t')) == 7}
    return {
        "configured": True,
        "source": "YOUTUBE_COOKIES_TEXT" if os.getenv('YOUTUBE_COOKIES_TEXT') else "file",
        "valid_lines": sum(1 for l in lines if len(l.split('\t')) == 7),
        "invalid_lines": sum(1 for l in lines if len(l.split('\t')) != 7),
        "logged_in": bool({'LOGIN_INFO', '__Secure-3PSID'} & names),
    }
