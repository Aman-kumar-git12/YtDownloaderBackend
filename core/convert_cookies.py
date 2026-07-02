import json
import os

def convert_json_to_netscape(json_file, txt_file):
    if not os.path.exists(json_file):
        print(f"File {json_file} does not exist.")
        return
        
    with open(json_file, 'r') as f:
        cookies = json.load(f)
    
    with open(txt_file, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# This is a generated file!  Do not edit.\n\n")
        
        for cookie in cookies:
            domain = cookie.get('domain', '')
            include_subdomains = 'TRUE' if domain.startswith('.') else 'FALSE'
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            expiration = str(int(cookie.get('expirationDate', 0)))
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            
            f.write(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n")
    print(f"Successfully converted cookies to {txt_file}")

if __name__ == "__main__":
    convert_json_to_netscape('/Users/amankumar/Downloads/www_youtube_com_cookies.json', '/Users/amankumar/Desktop/yt/youtube_cookies.txt')
