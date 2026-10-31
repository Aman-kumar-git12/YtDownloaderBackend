import os
from core.yt_helper import extract_info_safe, find_output_file


def _track_name(entries, lang):
    for entry in entries or []:
        if entry.get('name'):
            return entry['name']
    return lang


def get_subtitle_tracks(info):
    """Uploaded subtitles in every language, plus YouTube's auto-generated
    captions in the video's own language (the auto-translated ones are skipped)."""
    tracks = []
    for lang, entries in (info.get('subtitles') or {}).items():
        if lang != 'live_chat':
            tracks.append({"id": f"{lang}:manual", "name": _track_name(entries, lang), "auto": False})

    auto = info.get('automatic_captions') or {}
    original = [lang for lang in auto if lang.endswith('-orig')]
    if not original and info.get('language') in auto:
        original = [info['language']]
    for lang in original:
        name = _track_name(auto[lang], lang).replace(' (Original)', '')
        tracks.append({"id": f"{lang}:auto", "name": name, "auto": True})
    return tracks


def fetch_subtitle_tracks(url):
    info = extract_info_safe(url, download=False)
    return {"title": info.get('title') or 'Unknown Title', "tracks": get_subtitle_tracks(info)}


def download_subtitles(url, target, out_dir):
    lang, source, fmt = target.split(':')
    extra = {
        'skip_download': True,
        'writesubtitles': source == 'manual',
        'writeautomaticsub': source == 'auto',
        'subtitleslangs': [lang],
        'subtitlesformat': 'vtt/best',
        'outtmpl': os.path.join(out_dir, '%(title).150B.%(ext)s'),
    }
    if fmt == 'srt':
        extra['postprocessors'] = [{'key': 'FFmpegSubtitlesConvertor', 'format': 'srt', 'when': 'before_dl'}]

    extract_info_safe(url, download=True, extra_opts=extra)
    return find_output_file(out_dir)
