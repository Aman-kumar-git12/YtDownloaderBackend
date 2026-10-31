import os
from core.yt_helper import apply_clip, extract_info_safe, find_output_file, name_clip

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

# Formats that can carry title/artist tags and cover art
TAGGABLE_FORMATS = ("mp3", "m4a", "flac")

def download_audio(url, target_format, out_dir, progress_hook=None, clip=None):
    target_format = target_format.lower()
    postprocessors = [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': target_format,
        'preferredquality': '192',
    }]
    extra = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(out_dir, '%(title).150B.%(ext)s'),
        'postprocessors': postprocessors,
    }
    if target_format in TAGGABLE_FORMATS:
        # Title/artist tags and the video thumbnail as cover art, so the file
        # shows up properly in music apps
        extra['writethumbnail'] = True
        postprocessors.insert(0, {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg', 'when': 'before_dl'})
        postprocessors.append({'key': 'FFmpegMetadata', 'add_metadata': True})
        postprocessors.append({'key': 'EmbedThumbnail'})
    if progress_hook:
        extra['progress_hooks'] = [progress_hook]
    apply_clip(url, extra, clip)

    extract_info_safe(url, download=True, extra_opts=extra)
    return name_clip(find_output_file(out_dir), clip)
