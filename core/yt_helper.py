import os
import threading
import time
import yt_dlp

# Metadata lookups are cached so switching tabs (or starting a download) doesn't
# re-run a slow yt-dlp extraction and trigger YouTube's bot checks.
INFO_CACHE_TTL = int(os.getenv('INFO_CACHE_TTL_SECONDS', 300))
INFO_CACHE_MAX = 50
_info_cache = {}
_info_cache_lock = threading.Lock()

TEMP_SUFFIXES = ('.part', '.ytdl', '.temp', '.tmp')

def get_base_ydl_opts(extra_opts=None, use_cookies=True):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    # Support Proxy via environment variable (e.g. YOUTUBE_PROXY or HTTP_PROXY)
    proxy = os.getenv('YOUTUBE_PROXY') or os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')
    if proxy:
        opts['proxy'] = proxy

    # Support inline cookies from environment variable (e.g. YOUTUBE_COOKIES_TEXT)
    cookies_text = os.getenv('YOUTUBE_COOKIES_TEXT')
    cookie_path = os.getenv(
        'YOUTUBE_COOKIE_FILE',
        os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt'),
    )

    if use_cookies:
        if cookies_text:
            env_cookie_file = os.path.join(os.path.dirname(__file__), 'env_cookies.txt')
            try:
                with open(env_cookie_file, 'w') as f:
                    f.write(cookies_text)
                opts['cookiefile'] = env_cookie_file
            except Exception:
                pass
        elif os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 10:
            opts['cookiefile'] = cookie_path

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

    info = _extract_with_fallbacks(url, download, extra_opts)

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

def _extract_with_fallbacks(url, download, extra_opts):
    # Verified Working client combinations for cloud/datacenter IPs
    client_combos = [
        ['mweb', 'android'],
        ['web_embedded', 'android'],
        ['android', 'mweb'],
        ['web', 'mweb']
    ]

    last_err = None

    # Step 1: Try with cookies (if provided)
    for combo in client_combos:
        opts = get_base_ydl_opts(extra_opts, use_cookies=True)
        opts['extractor_args'] = {'youtube': {'player_client': combo}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception as e:
            last_err = e
            continue

    # Step 2: Fallback WITHOUT cookies (bypasses expired/invalid cookie blocks on cloud IPs)
    for combo in client_combos:
        opts = get_base_ydl_opts(extra_opts, use_cookies=False)
        opts['extractor_args'] = {'youtube': {'player_client': combo}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
