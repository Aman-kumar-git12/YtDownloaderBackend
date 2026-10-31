import os
import requests
import sys
import time

BASE_URL = "http://127.0.0.1:8001"

def run_download(kind, url, target):
    """Start a background download job, show progress, then save the file to the current folder."""
    resp = requests.post(f"{BASE_URL}/api/download/{kind}", json={"url": url, "target": target})
    if not resp.ok:
        print("Download failed:", resp.json().get("detail"))
        return None
    task_id = resp.json()["task_id"]

    while True:
        time.sleep(1)
        job = requests.get(f"{BASE_URL}/api/download/progress/{task_id}").json()
        status = job.get("status")
        if status == "completed":
            break
        if status == "error" or status is None:
            print(f"\nDownload failed: {job.get('error') or job.get('detail')}")
            return None
        print(f"\r⏳ {status} {job.get('percent', 0)}% {job.get('speed') or ''}   ", end="", flush=True)

    filepath = os.path.abspath(os.path.basename(job["filename"]))
    with requests.get(f"{BASE_URL}/api/files/{task_id}", stream=True) as file_resp:
        file_resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in file_resp.iter_content(1024 * 1024):
                f.write(chunk)
    print()
    return filepath

def get_metadata(url):
    print("\nFetching comprehensive video metadata via API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/metadata", params={"url": url}).json()
        if not resp.get("success"):
            print("Error:", resp.get("detail"))
            return
            
        data = resp["data"]
        
        print("\n" + "="*50)
        print(" " * 15 + "VIDEO METADATA")
        print("="*50)
        
        print(f"📌 Title        : {data['title']}")
        print(f"🆔 Video ID     : {data['video_id']} ({data['url']})")
        print(f"👤 Channel      : {data['channel']} ({data['channel_url']})")
        
        subs = data['subscribers']
        print(f"👥 Subscribers  : {subs:,}" if subs is not None else "👥 Subscribers  : Hidden/Unknown")
        print(f"📅 Upload Date  : {data['upload_date'] or 'Unknown'}")
        print(f"⏱️  Duration     : {data['duration'] or 'Unknown'}")
        
        views = data['views']
        print(f"👁️  Views        : {views:,}" if views is not None else "👁️  Views        : Hidden")
        
        likes = data['likes']
        print(f"👍 Likes        : {likes:,}" if likes is not None else "👍 Likes        : Hidden/Unknown")
        
        comments = data['comments']
        print(f"💬 Comments     : {comments:,}" if comments is not None else "💬 Comments     : Hidden/Unknown")
        print(f"📖 Description  : {data['description_snippet']}")
        
        tags = data['tags']
        tags_str = ", ".join(tags[:5]) + ("..." if len(tags) > 5 else "")
        print(f"🏷️  Tags         : {tags_str if tags else 'None'}")
        
        cats = data['categories']
        print(f"📁 Category     : {', '.join(cats) if cats else 'None'}")
        
        print(f"🔓 Privacy      : {data['privacy']}")
        print(f"📜 License      : {data['license']}")
        print(f"🔞 Age Restricted: {'Yes' if data['age_restricted'] else 'No'}")
        print(f"🔴 Live Status  : {data['live_status']}")
        
        total_ch = data['total_chapters']
        if total_ch > 0:
            print(f"🔖 Chapters     : {total_ch} chapters found")
            for chap in data['chapters_preview']:
                print(f"                  - {chap}")
            if total_ch > 3:
                print(f"                  ...and {total_ch - 3} more")
        else:
            print(f"🔖 Chapters     : None")
            
        print(f"⚙️  Total Formats: {data['total_formats']} streams available")
        subs_list = data['subtitles']
        print(f"📝 Subtitles    : {', '.join(subs_list) if subs_list else 'None'}")
        
        print("="*50 + "\n")
        
    except Exception as e:
        print("\n[API Error] Is the FastAPI server running on port 8001?")
        print(f"Details: {e}")

def get_video(url):
    print("\nFetching video information via API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/video/resolutions", params={"url": url}).json()
        if not resp.get("success"):
            print("Error:", resp.get("detail"))
            return
            
        data = resp["data"]
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
            
        print(f"\nCommanding API to download {target_res}...")
        filepath = run_download("video", url, target_res)
        if filepath:
            print(f"\n🎉 HD Video Download Completed Successfully! Saved at: {filepath}")
            
    except Exception as e:
        print("\n[API Error] Is the FastAPI server running on port 8001?")
        print(f"Details: {e}")

def get_audio(url):
    print("\nFetching audio information via API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/audio/formats", params={"url": url}).json()
        if not resp.get("success"):
            print("Error:", resp.get("detail"))
            return
            
        data = resp["data"]
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
                target_format = "MP3"
        except ValueError:
            target_format = "MP3"
            
        print(f"\nCommanding API to download and convert to {target_format}...")
        filepath = run_download("audio", url, target_format)
        if filepath:
            print(f"\n🎉 Audio Download Completed Successfully! Saved at: {filepath}")
            
    except Exception as e:
        print("\n[API Error] Is the FastAPI server running on port 8001?")
        print(f"Details: {e}")

def get_thumbnail(url):
    print("\nFetching thumbnail information via API...")
    try:
        resp = requests.get(f"{BASE_URL}/api/thumbnail/resolutions", params={"url": url}).json()
        if not resp.get("success"):
            print("Error:", resp.get("detail"))
            return
            
        data = resp["data"]
        print(f"\nConnected to: {data['title']}")
        
        resolutions = data['resolutions']
        
        if not resolutions:
            print("No high-quality thumbnails found.")
            return
            
        print("Calculating exact file sizes via API...")
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
                target_res = res_list[0]
        except ValueError:
            target_res = res_list[0]
            
        print(f"\nCommanding API to download {target_res} thumbnail...")
        filepath = run_download("thumbnail", url, target_res)
        if filepath:
            print(f"🎉 Thumbnail successfully saved at: {filepath}")
            
    except Exception as e:
        print("\n[API Error] Is the FastAPI server running on port 8001?")
        print(f"Details: {e}")

def main():
    print("=== API-Driven YouTube Downloader ===")
    
    # Check if server is running first
    try:
        requests.get(f"{BASE_URL}/docs", timeout=2)
    except:
        print("\n[!] WARNING: FastAPI Server is not reachable at 127.0.0.1:8001.")
        print("Please open a new terminal and run: `python server.py`\n")
        sys.exit(1)
        
    link = input("Enter the YouTube Video URL: ")
    
    print("\nWhat would you like to do?")
    print("1. Print Video Metadata")
    print("2. Download Video Thumbnail")
    print("3. Download Video")
    print("4. Download Audio")
    print("5. Do All")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == '1':
        get_metadata(link)
    elif choice == '2':
        get_thumbnail(link)
    elif choice == '3':
        get_video(link)
    elif choice == '4':
        get_audio(link)
    elif choice == '5':
        get_metadata(link)
        get_thumbnail(link)
        get_video(link)
        get_audio(link)
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
