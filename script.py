# File: script.py
import requests
import re

def filter_and_split_playlist(url, file_live, file_series, file_movies):
    print(f"Downloading playlist from: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading playlist: {e}")
        return

    lines = content.splitlines()
    
    # Lists to store pairs: [(info_line, url_line), ...]
    live_items = []
    series_items = []
    movie_items = []
    
    for i in range(len(lines)):
        line = lines[i]
        
        if line.startswith("#EXTINF"):
            # GLOBAL FILTER: Check if original line contains "Telugu"
            if "Telugu" in line or "Teulugu" in line:
                
                # --- GLOBAL CLEANING (Applies to ALL) ---
                
                # 1. Remove (Telugu) and (telugu)
                line = line.replace("(Telugu)", " ").replace("(telugu)", " ")
                
                # 2. Remove empty tvg-id=""
                line = line.replace('tvg-id=""', '')

                # 3. Remove group-title="..." completely
                line = re.sub(r'group-title=".*?"', '', line)

                # 4. Clean up extra double spaces
                line = " ".join(line.split()) 
                
                # Get the URL (next line)
                url = lines[i+1].strip() if i + 1 < len(lines) else ""
                
                # Create the item pair with the CLEANED line
                item = (line, url)
                
                # --- CLASSIFICATION LOGIC ---
                
                # 1. SERIES CHECK (S01 E02 pattern)
                if re.search(r"S\d+\s*E\d+", line, re.IGNORECASE):
                    series_items.append(item)
                
                # 2. LIVE CHECK (Strictly .ts extension)
                elif url.lower().endswith(".ts"):
                    live_items.append(item)
                    
                # 3. MOVIES CHECK (Everything else)
                else:
                    movie_items.append(item)

    # --- SORTING LOGIC ---
    # Reverse Series and Movies to show LATEST added first
    series_items.reverse()
    movie_items.reverse()

    # --- SAVING ---
    save_file(file_live, live_items)
    save_file(file_series, series_items)
    save_file(file_movies, movie_items)

def save_file(filename, items_list):
    lines_to_save = ["#EXTM3U"]
    
    for info, url in items_list:
        lines_to_save.append(info)
        lines_to_save.append(url)
        
    if len(items_list) > 0:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_save))
        print(f"Saved {filename}: {len(items_list)} channels (Latest First).")
    else:
        print(f"No channels found for {filename}.")

# --- Configuration ---
m3u_url = "https://webhop.live/get.php?username=juno123&password=juno123&type=m3u_plus&output=ts"
output_live = "TeluguLive.m3u"
output_series = "TeluguSeries.m3u"
output_movies = "TeluguMovies.m3u"

if __name__ == "__main__":
    filter_and_split_playlist(m3u_url, output_live, output_series, output_movies)
