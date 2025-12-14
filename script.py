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
    
    # Initialize lists (start with header)
    live_lines = ["#EXTM3U"]
    series_lines = ["#EXTM3U"]
    movie_lines = ["#EXTM3U"]
    
    for i in range(len(lines)):
        line = lines[i]
        
        if line.startswith("#EXTINF"):
            # GLOBAL FILTER: Must contain "Telugu"
            if "Telugu" in line or "Teulugu" in line:
                url = lines[i+1].strip() if i + 1 < len(lines) else ""
                
                # 1. SERIES CHECK (S01 E02 pattern)
                if re.search(r"S\d+\s*E\d+", line, re.IGNORECASE):
                    series_lines.append(line)
                    series_lines.append(url)
                
                # 2. LIVE CHECK (Strictly .ts extension)
                elif url.lower().endswith(".ts"):
                    live_lines.append(line)
                    live_lines.append(url)
                    
                # 3. MOVIES CHECK (Everything else)
                else:
                    movie_lines.append(line)
                    movie_lines.append(url)

    # Save Files
    save_file(file_live, live_lines)
    save_file(file_series, series_lines)
    save_file(file_movies, movie_lines)

def save_file(filename, data_list):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(data_list))
    print(f"Saved {filename}: {len(data_list)//2} channels.")

# --- Configuration ---
m3u_url = "https://webhop.live/get.php?username=juno123&password=juno123&type=m3u_plus&output=ts"
output_live = "TeluguLive.m3u"
output_series = "TeluguSeries.m3u"
output_movies = "TeluguMovies.m3u"

if __name__ == "__main__":
    filter_and_split_playlist(m3u_url, output_live, output_series, output_movies)
