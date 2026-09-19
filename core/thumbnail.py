import yt_dlp
import os
import requests
from core.yt_helper import extract_info_safe

def fetch_thumbnail_options(url):
    info = extract_info_safe(url, download=False)
        
    title = info.get('title', 'Unknown Title')
    thumbnails = info.get('thumbnails', [])
    
    valid_thumbnails = []
    for t in thumbnails:
        width = t.get('width')
        height = t.get('height')
        if width and height:
            res_str = f"{width}x{height}"
            sort_val = width * height
            valid_thumbnails.append({
                'resolution': res_str,
                'url': t.get('url'),
                'sort_val': sort_val
            })
            
    valid_thumbnails.sort(key=lambda x: x['sort_val'], reverse=True)
    
    seen_res = set()
    unique_thumbnails = []
    for t in valid_thumbnails:
        if t['resolution'] not in seen_res:
            seen_res.add(t['resolution'])
            unique_thumbnails.append(t)
            
    if not unique_thumbnails:
        for t in thumbnails:
            unique_thumbnails.append({
                'resolution': t.get('id', 'Unknown'),
                'url': t.get('url')
            })
            
    # Compute sizes
    qualities_dict = {}
    url_dict = {}
    for t in unique_thumbnails:
        res = t['resolution']
        url_dict[res] = t['url']
        try:
            head_resp = requests.head(t['url'], timeout=3)
            size_bytes = int(head_resp.headers.get('Content-Length', 0))
            if size_bytes > 0:
                qualities_dict[res] = f"{size_bytes / 1024:.1f} KB"
            else:
                qualities_dict[res] = "Unknown"
        except:
            qualities_dict[res] = "Unknown"
            
    return {
        "title": title,
        "resolutions": qualities_dict,
        "urls": url_dict
    }

def download_thumbnail(target_url, target_res, title):
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    os.makedirs(out_dir, exist_ok=True)
    
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    filename = os.path.join(out_dir, f"{safe_title}_{target_res}.jpg")
    
    response = requests.get(target_url, timeout=20)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        return True, filename
    else:
        return False, None

def interactive_thumbnail_download(url):
    print("\nFetching thumbnail information safely...")
    try:
        data = fetch_thumbnail_options(url)
        print(f"\nConnected to: {data['title']}")
        
        resolutions = data['resolutions']
        urls = data['urls']
        
        if not resolutions:
            print("No high-quality thumbnails found.")
            return
            
        print("Calculating exact file sizes...")
        print("\nFetched Thumbnail Qualities Dictionary:")
        print(resolutions)
        
        print("\nAvailable Thumbnail Resolutions:")
        res_list = list(resolutions.keys())
        for i, res in enumerate(res_list):
            size_str = resolutions[res]
            if size_str != "Unknown":
                print(f"[{i + 1}] {res} (~{size_str})")
            else:
                print(f"[{i + 1}] {res}")
                
        choice = input("\nEnter the number of the thumbnail you want to download: ")
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(res_list):
                target_res = res_list[choice_idx]
            else:
                print("Invalid choice. Defaulting to highest resolution.")
                target_res = res_list[0]
        except ValueError:
            print("Invalid input. Defaulting to highest resolution.")
            target_res = res_list[0]
            
        target_url = urls[target_res]
        
        print(f"\nDownloading {target_res} thumbnail...")
        success, filepath = download_thumbnail(target_url, target_res, data['title'])
        if success:
            print(f"🎉 Thumbnail successfully saved as: {filepath}")
        else:
            print("Failed to download thumbnail.")
            
    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    link = input("Enter the YouTube Video URL: ")
    interactive_thumbnail_download(link)
