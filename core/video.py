import os
from core.yt_helper import apply_clip, extract_info_safe, find_output_file, name_clip

def fetch_video_resolutions(url):
    info = extract_info_safe(url, download=False)

    title = info.get('title') or 'Unknown Title'
    formats = info.get('formats') or []

    best_audio_size = 0
    for f in formats:
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            size = f.get('filesize') or f.get('filesize_approx') or 0
            if size > best_audio_size:
                best_audio_size = size

    height_sizes = {}
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'):
            h = f.get('height')
            size = f.get('filesize') or f.get('filesize_approx') or 0
            if f.get('acodec') == 'none':
                size += best_audio_size
            if h not in height_sizes or size > height_sizes[h]:
                height_sizes[h] = size

    resolutions = {}
    for h in sorted(height_sizes, reverse=True):
        size_bytes = height_sizes[h]
        resolutions[f"{h}p"] = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes > 0 else "Unknown"

    return {
        "title": title,
        "resolutions": resolutions
    }

def download_video(url, resolution_str, out_dir, progress_hook=None, clip=None):
    # resolution_str should be something like "1080" or "1080p"
    resolution = int(resolution_str.lower().rstrip("p"))

    extra = {
        'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best',
        # Prefer H.264 video + AAC audio so the merged MP4 plays everywhere
        # (QuickTime/iOS can't play VP9/AV1 + Opus inside an .mp4).
        'format_sort': ['res', 'vcodec:h264', 'acodec:aac'],
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(out_dir, '%(title).150B_%(height)sp.%(ext)s'),
    }
    if progress_hook:
        extra['progress_hooks'] = [progress_hook]
    apply_clip(url, extra, clip)

    extract_info_safe(url, download=True, extra_opts=extra)
    return name_clip(find_output_file(out_dir), clip)
