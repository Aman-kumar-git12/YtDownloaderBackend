import os
import yt_dlp

def get_base_ydl_opts(extra_opts=None):
    cookie_path = os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt')
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web']
            }
        }
    }
    
    if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0:
        opts['cookiefile'] = cookie_path

    if extra_opts:
        opts.update(extra_opts)

    return opts

def extract_info_safe(url, download=False, extra_opts=None):
    opts = get_base_ydl_opts(extra_opts)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)
    except Exception as primary_err:
        # Fallback retry with android/mweb player clients if web client gets blocked on cloud server IP
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'mweb', 'ios']
            }
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception:
            raise primary_err
