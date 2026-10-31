import os
from core.yt_helper import extract_info_safe, find_output_file

# (format, description, approx KB per second of audio)
AUDIO_FORMATS = [
    ("mp3", "Best for general compatibility", 24),
    ("m4a", "Best for Apple devices / iTunes", 24),
    ("wav", "Uncompressed lossless audio (Large file)", 176),
    ("flac", "Compressed lossless audio", 100),
    ("aac", "Advanced Audio Coding", 24),
]

def fetch_audio_formats(url):
    info = extract_info_safe(url, download=False)

    title = info.get('title') or 'Unknown Title'
    duration = info.get('duration') or 0

    formats_dict = {}
    details_dict = {}
    for fmt, desc, kb_per_sec in AUDIO_FORMATS:
        fmt_upper = fmt.upper()
        size_mb = duration * kb_per_sec / 1024
        formats_dict[fmt_upper] = f"~{size_mb:.1f} MB" if size_mb > 0 else "Unknown"
        details_dict[fmt_upper] = desc

    return {
        "title": title,
        "formats": formats_dict,
        "details": details_dict
    }

def download_audio(url, target_format, out_dir, progress_hook=None):
    extra = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(out_dir, '%(title).150B.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': target_format.lower(),
            'preferredquality': '192',
        }],
    }
    if progress_hook:
        extra['progress_hooks'] = [progress_hook]

    extract_info_safe(url, download=True, extra_opts=extra)
    return find_output_file(out_dir)
