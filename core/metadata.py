import yt_dlp
import os
from datetime import timedelta

def fetch_metadata(url):
    info_opts = {
        'cookiefile': os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt'),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'quiet': True,
        'no_warnings': True
    }
    
    with yt_dlp.YoutubeDL(info_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    duration_sec = info.get('duration', 0)
    duration_str = str(timedelta(seconds=duration_sec))
    
    desc = info.get('description', '')
    desc_snippet = desc.replace('\n', ' ')[:100] + ('...' if len(desc) > 100 else '') if desc else 'None'
    
    was_live = info.get('was_live')
    is_live = info.get('is_live')
    live_status = 'Currently Live' if is_live else 'Was Live (VOD)' if was_live else 'Never Live'
    
    chapters = info.get('chapters')
    chapters_preview = []
    if chapters:
        for chap in chapters[:3]:
            start_time = str(timedelta(seconds=int(chap.get('start_time', 0))))
            chapters_preview.append(f"{start_time}: {chap.get('title', 'Untitled')}")
            
    # Fetch highest resolution thumbnail
    thumbnails = info.get('thumbnails', [])
    max_thumbnail_url = None
    if thumbnails:
        valid_thumbs = [t for t in thumbnails if t.get('width') and t.get('height')]
        if valid_thumbs:
            valid_thumbs.sort(key=lambda x: x['width'] * x['height'], reverse=True)
            max_thumbnail_url = valid_thumbs[0].get('url')
        else:
            max_thumbnail_url = thumbnails[-1].get('url')
            
    return {
        "title": info.get('title', 'Unknown'),
        "video_id": info.get('id', 'Unknown'),
        "url": info.get('webpage_url', 'Unknown'),
        "channel": info.get('uploader', 'Unknown'),
        "channel_url": info.get('channel_url', ''),
        "subscribers": info.get('channel_follower_count'),
        "upload_date": info.get('upload_date', 'Unknown'),
        "duration": duration_str,
        "views": info.get('view_count'),
        "likes": info.get('like_count'),
        "comments": info.get('comment_count'),
        "description_snippet": desc_snippet,
        "tags": info.get('tags', []),
        "categories": info.get('categories', []),
        "privacy": info.get('availability', 'Unknown').capitalize(),
        "license": info.get('license', 'Standard'),
        "age_restricted": info.get('age_limit', 0) > 0,
        "live_status": live_status,
        "total_chapters": len(chapters) if chapters else 0,
        "chapters_preview": chapters_preview,
        "total_formats": len(info.get('formats', [])),
        "subtitles": list(info.get('subtitles', {}).keys()),
        "thumbnail": max_thumbnail_url
    }

def fetch_and_print_metadata(url):
    print("\nFetching comprehensive video metadata safely...")
    try:
        data = fetch_metadata(url)
        
        print("\n" + "="*50)
        print(" " * 15 + "VIDEO METADATA")
        print("="*50)
        
        print(f"📌 Title        : {data['title']}")
        print(f"🆔 Video ID     : {data['video_id']} ({data['url']})")
        print(f"👤 Channel      : {data['channel']} ({data['channel_url']})")
        
        subs = data['subscribers']
        print(f"👥 Subscribers  : {subs:,}" if subs else "👥 Subscribers  : Hidden/Unknown")
        print(f"📅 Upload Date  : {data['upload_date']} (YYYYMMDD)")
        print(f"⏱️  Duration     : {data['duration']}")
        
        views = data['views']
        print(f"👁️  Views        : {views:,}" if views else "👁️  Views        : Hidden")
        
        likes = data['likes']
        print(f"👍 Likes        : {likes:,}" if likes else "👍 Likes        : Hidden/Unknown")
        
        comments = data['comments']
        print(f"💬 Comments     : {comments:,}" if comments else "💬 Comments     : Hidden/Unknown")
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
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    link = input("Enter the YouTube Video URL: ")
    fetch_and_print_metadata(link)
