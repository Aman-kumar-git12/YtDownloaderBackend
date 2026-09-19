import os
import yt_dlp

def get_base_ydl_opts(extra_opts=None):
    cookie_path = os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt')
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }
    
    if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 10:
        opts['cookiefile'] = cookie_path

    if extra_opts:
        opts.update(extra_opts)

    return opts

def extract_info_safe(url, download=False, extra_opts=None):
    # Tested Working combinations for cloud/datacenter IPs (excluding broken 'ios' client)
    client_combos = [
        ['mweb', 'android'],
        ['web_embedded', 'android'],
        ['tv_embedded', 'mweb'],
        ['android', 'mweb'],
        ['web', 'mweb']
    ]

    last_err = None
    for combo in client_combos:
        opts = get_base_ydl_opts(extra_opts)
        opts['extractor_args'] = {
            'youtube': {
                'player_client': combo
            }
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
