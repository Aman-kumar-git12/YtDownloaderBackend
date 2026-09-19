import yt_dlp
import os
from core.yt_helper import extract_info_safe, get_base_ydl_opts

def fetch_audio_formats(url):
    info = extract_info_safe(url, download=False)
        
    title = info.get('title', 'Unknown Title')
    duration = info.get('duration') or 0
    
    audio_formats = [
        ("mp3", "Best for general compatibility", duration * 24 / 1024),
        ("m4a", "Best for Apple devices / iTunes", duration * 24 / 1024),
        ("wav", "Uncompressed lossless audio (Large file)", duration * 176 / 1024),
        ("flac", "Compressed lossless audio", duration * 100 / 1024),
        ("aac", "Advanced Audio Coding", duration * 24 / 1024)
    ]
    
    formats_dict = {}
    details_dict = {}
    for fmt, desc, size_mb in audio_formats:
        fmt_upper = fmt.upper()
        if size_mb > 0:
            formats_dict[fmt_upper] = f"{size_mb:.1f} MB"
        else:
            formats_dict[fmt_upper] = "Unknown"
        details_dict[fmt_upper] = desc
            
    return {
        "title": title,
        "formats": formats_dict,
        "details": details_dict
    }

def download_audio(url, target_format, progress_hook=None):
    target_format = target_format.lower()
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    os.makedirs(out_dir, exist_ok=True)
    
    extra = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(out_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': target_format,
            'preferredquality': '192',
        }],
    }
    if progress_hook:
        extra['progress_hooks'] = [progress_hook]

    info = extract_info_safe(url, download=True, extra_opts=extra)
    opts = get_base_ydl_opts(extra)
    with yt_dlp.YoutubeDL(opts) as ydl:
        base = os.path.splitext(os.path.basename(ydl.prepare_filename(info)))[0]
        final_filename = f"{base}.{target_format}"
        final_filepath = os.path.join(out_dir, final_filename)
        if os.path.exists(final_filepath):
            return final_filename
        if info.get('requested_downloads'):
            filepath = info['requested_downloads'][0]['filepath']
            if os.path.exists(filepath):
                return os.path.basename(filepath)
        return final_filename

def interactive_audio_download(url):
    print("\nFetching audio information safely...")
    try:
        data = fetch_audio_formats(url)
        print(f"\nConnected to: {data['title']}")
        
        formats = data['formats']
        details = data['details']
        
        print("\nFetched Audio Qualities Dictionary:")
        print(formats)
        
        print("\nAvailable Audio Formats:")
        fmt_list = list(formats.keys())
        for i, fmt in enumerate(fmt_list):
            size_str = formats[fmt]
            desc = details[fmt]
            if size_str != "Unknown":
                print(f"[{i + 1}] {fmt} (~{size_str}) - {desc}")
            else:
                print(f"[{i + 1}] {fmt} - {desc}")
            
        choice = input("\nEnter the number of the format you want to download: ")
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(fmt_list):
                target_format = fmt_list[choice_idx]
            else:
                print("Invalid choice. Defaulting to MP3.")
                target_format = "MP3"
        except ValueError:
            print("Invalid input. Defaulting to MP3.")
            target_format = "MP3"
            
        print(f"\nDownloading and converting to {target_format}...")
        download_audio(url, target_format)
        print(f"\n🎉 Audio Download Completed Successfully! Saved as {target_format}")
        
    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    link = input("Enter the YouTube Video URL: ")
    interactive_audio_download(link)
