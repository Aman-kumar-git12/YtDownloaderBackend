import yt_dlp
import os
from core.yt_helper import extract_info_safe, get_base_ydl_opts

def fetch_video_resolutions(url):
    info = extract_info_safe(url, download=False)
    
    title = info.get('title', 'Unknown Title')
    formats = info.get('formats', [])
    
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
                
    sorted_heights = sorted(height_sizes.keys(), reverse=True)
    
    resolutions = {}
    for h in sorted_heights:
        size_bytes = height_sizes[h]
        if size_bytes > 0:
            size_mb = size_bytes / (1024 * 1024)
            resolutions[f"{h}p"] = f"{size_mb:.1f} MB"
        else:
            resolutions[f"{h}p"] = "Unknown"
            
    return {
        "title": title,
        "resolutions": resolutions
    }

def download_video(url, resolution_str, progress_hook=None):
    # resolution_str should be something like "1080" or "1080p"
    resolution = resolution_str.replace("p", "")
    
    format_selector = f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best'
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    os.makedirs(out_dir, exist_ok=True)
    
    extra = {
        'format': format_selector,
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(out_dir, '%(title)s_%(height)sp.%(ext)s'),
    }
    if progress_hook:
        extra['progress_hooks'] = [progress_hook]

    info = extract_info_safe(url, download=True, extra_opts=extra)
    if info.get('requested_downloads'):
        filepath = info['requested_downloads'][0]['filepath']
        if os.path.exists(filepath):
            return os.path.basename(filepath)
    opts = get_base_ydl_opts(extra)
    with yt_dlp.YoutubeDL(opts) as ydl:
        filename = ydl.prepare_filename(info)
        return os.path.basename(filename)

def interactive_download(url):
    print("\nFetching video information safely...")
    try:
        data = fetch_video_resolutions(url)
        print(f"\nConnected to: {data['title']}")
        
        resolutions = data['resolutions']
        if not resolutions:
            print("No video formats found.")
            return
            
        print("\nFetched Qualities Dictionary:")
        print(resolutions)
            
        print("\nAvailable Qualities:")
        res_list = list(resolutions.keys())
        for i, res in enumerate(res_list):
            print(f"[{i + 1}] {res} (~{resolutions[res]})")
            
        choice = input("\nEnter the number of the quality you want to download: ")
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(res_list):
                target_res = res_list[choice_idx]
            else:
                target_res = res_list[0]
        except ValueError:
            target_res = res_list[0]
            
        print(f"\nDownloading in {target_res}...")
        download_video(url, target_res)
        print("\n🎉 HD Video Download Completed Successfully!")
        
    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    link = input("Enter the YouTube Video URL: ")
    interactive_download(link)
