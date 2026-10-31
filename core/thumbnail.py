import os
import requests
from core.yt_helper import extract_info_safe
from core.validators import is_thumbnail_url

MAX_THUMBNAIL_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = {'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/png': 'png'}

def get_thumbnail_urls(info):
    """Map resolution label -> thumbnail URL, largest first. Only YouTube image hosts are kept."""
    thumbnails = [t for t in (info.get('thumbnails') or []) if is_thumbnail_url(t.get('url') or '')]

    sized = [t for t in thumbnails if t.get('width') and t.get('height')]
    sized.sort(key=lambda t: t['width'] * t['height'], reverse=True)

    urls = {}
    for t in sized:
        urls.setdefault(f"{t['width']}x{t['height']}", t['url'])
    if not urls:
        for t in thumbnails:
            urls.setdefault(str(t.get('id') or 'default'), t['url'])
    return urls

def fetch_thumbnail_options(url):
    info = extract_info_safe(url, download=False)

    qualities_dict = {}
    for res, thumb_url in get_thumbnail_urls(info).items():
        try:
            head_resp = requests.head(thumb_url, timeout=3)
            size_bytes = int(head_resp.headers.get('Content-Length') or 0)
            qualities_dict[res] = f"{size_bytes / 1024:.1f} KB" if size_bytes > 0 else "Unknown"
        except (requests.RequestException, ValueError):
            qualities_dict[res] = "Unknown"

    return {
        "title": info.get('title') or 'Unknown Title',
        "resolutions": qualities_dict,
        "previews": get_thumbnail_urls(info),
    }

def download_thumbnail(video_url, target_res, out_dir):
    # The image URL is looked up server-side from the video, never taken from the
    # client, so this endpoint can't be used to make the server fetch arbitrary URLs.
    info = extract_info_safe(video_url, download=False)
    thumb_url = get_thumbnail_urls(info).get(target_res)
    if not thumb_url:
        raise ValueError(f"Thumbnail size '{target_res}' is not available for this video")

    with requests.get(thumb_url, timeout=20, stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise RuntimeError(f"Thumbnail server returned HTTP {response.status_code}")
        content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip()
        ext = IMAGE_EXTENSIONS.get(content_type)
        if not ext:
            raise RuntimeError(f"Unexpected thumbnail type '{content_type}'")

        data = b''
        for chunk in response.iter_content(64 * 1024):
            data += chunk
            if len(data) > MAX_THUMBNAIL_BYTES:
                raise RuntimeError("Thumbnail is unexpectedly large")

    title = info.get('title') or ''
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "thumbnail"
    filepath = os.path.join(out_dir, f"{safe_title[:150]}_{target_res}.{ext}")
    with open(filepath, 'wb') as f:
        f.write(data)
    return filepath
