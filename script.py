import requests
import re
from collections import defaultdict

def filter_and_split_playlist(url, file_live, file_series, file_movies, file_tvshows):
    print(f"Downloading playlist from: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading playlist: {e}")
        return

    lines = content.splitlines()
    
    # Storage
    live_items = []
    movie_items = []
    
    # Dictionary Key: (Show Name, Season Number) | Value: List of items
    season_grouping = defaultdict(list)
    
    DEFAULT_LOGO = "https://tvtelugu.github.io/images/tvtelugu.png"
    
    for i in range(len(lines)):
        line = lines[i]
        
        if line.startswith("#EXTINF"):
            if "telugu" in line.lower() or "teulugu" in line.lower():
                
                url = lines[i+1].strip() if i + 1 < len(lines) else ""
                
                # --- CATEGORY DETECTION ---
                is_live = "/live/" in url
                is_movie = "/movie/" in url
                is_series = "/series/" in url
                
                if not (is_live or is_movie or is_series):
                    if url.endswith(".ts"): is_live = True
                    elif re.search(r"S\d+|E\d+", line, re.IGNORECASE): is_series = True
                    else: is_movie = True

                # --- 1. METADATA CLEANING ---
                line = line.replace('tvg-id=""', '')
                line = re.sub(r'group-title=".*?"', '', line)
                line = re.sub(r'tvg-name=".*?"', '', line)

                # --- 2. SEPARATE NAME ---
                parts = line.rsplit(',', 1)
                
                if len(parts) == 2:
                    meta_data = parts[0]
                    name = parts[1]
                    
                    # --- 3. LOGO FIX ---
                    if 'tvg-logo=""' in meta_data:
                        meta_data = meta_data.replace('tvg-logo=""', f'tvg-logo="{DEFAULT_LOGO}"')
                    elif 'tvg-logo=' not in meta_data:
                        meta_data = f'{meta_data} tvg-logo="{DEFAULT_LOGO}"'
                    
                    meta_data = " ".join(meta_data.split())

                    # --- 4. PRE-ANALYSIS (Movies) ---
                    is_cam = False
                    year = 0
                    if is_movie:
                        if re.search(r'\(Cam\)|Cam', name, re.IGNORECASE): is_cam = True
                        
                        # --- IMPROVED YEAR DETECTION ---
                        # Logic: Find ALL years (19xx or 20xx) and take the LAST one.
                        # This fixes "Aliens 2042 (2023)" -> Picks 2023, not 2042.
                        year_matches = re.findall(r'\b(?:19|20)\d{2}\b', name)
                        if year_matches:
                            year = int(year_matches[-1])

                    # --- 5. CLEAN THE NAME ---
                    patterns = [
                        r"Telugu:\s*", r"TELUGU:\s*",
                        r"\(\s*Telugu\s*\)",  
                        r"Cric\s*[|]*", r"Tl\s*[|]*", r"In:\s*",       
                        r"24/7\s*:*", r"\(FHD\)", r"\(4K\)", r"⁴ᵏ", r"\|+"           
                    ]
                    for pattern in patterns:
                        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)

                    if is_movie:
                        name = re.sub(r"\bTelugu\b", " ", name, flags=re.IGNORECASE)

                    # --- 6. FORMATTING ---
                    name = name.replace("_", " ").replace("-", " ").replace(".", "").replace('"', ',')
                    name = " ".join(name.split())
                    name = name.title() 

                    replacements = {
                        r"\bHd\b": "HD", r"\bSd\b": "SD", r"\bTv\b": "TV",
                        r"\(Cam\)": "(CAM)", r"\bCam\b": "CAM"    
                    }
                    for pattern, replacement in replacements.items():
                        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)

                    line = f"{meta_data},{name}"

                # --- STREAM ID EXTRACTION ---
                try:
                    stream_id = int(re.findall(r'/(\d+)(?:\.[a-zA-Z0-9]+)?$', url)[0])
                except:
                    stream_id = 0

                item_data = {
                    'line': line,
                    'url': url,
                    'stream_id': stream_id,
                    'year': year if is_movie else 0,
                    'is_cam': is_cam if is_movie else False,
                    'clean_name': name.lower().replace("(cam)", "").replace("cam", "").strip(),
                    'display_name': name 
                }

                # --- DISTRIBUTION ---
                if is_live:
                    live_items.append((line, url))
                    
                elif is_movie:
                    movie_items.append(item_data)
                    
                elif is_series:
                    match_season = re.search(r'^(.*?)\s*S(\d+)', item_data['display_name'], re.IGNORECASE)
                    
                    if match_season:
                        show_name = match_season.group(1).strip().lower()
                        season_num = match_season.group(2)
                    else:
                        match_episode = re.search(r'^(.*?)\s*E\d+', item_data['display_name'], re.IGNORECASE)
                        if match_episode:
                            show_name = match_episode.group(1).strip().lower()
                            season_num = "00"
                        else:
                            show_name = item_data['display_name'].strip().lower()
                            season_num = "00"
                    
                    season_grouping[(show_name, season_num)].append(item_data)

    # ==========================
    #      POST-PROCESSING
    # ==========================

    # --- 1. MOVIES (Sort & Dedup) ---
    # Sort: Year (Desc) -> StreamID (Desc)
    movie_items.sort(key=lambda x: (x['year'], x['stream_id']), reverse=True)
    
    final_movies = []
    seen_movies = {}
    
    for item in movie_items:
        base_name = item['clean_name']
        if base_name not in seen_movies:
            seen_movies[base_name] = item
            final_movies.append(item)
        else:
            existing = seen_movies[base_name]
            # If current item is NOT cam, but existing IS cam, swap them (upgrade quality)
            # BUT: If both are same quality, we keep the FIRST one found (which is the Newest because we sorted by StreamID)
            if existing['is_cam'] and not item['is_cam']:
                if existing in final_movies: final_movies.remove(existing)
                final_movies.append(item)
                seen_movies[base_name] = item

    movie_list_save = [(x['line'], x['url']) for x in final_movies]

    # --- 2. SERIES & TV SHOWS ---
    all_groups = []

    for key, episodes in season_grouping.items():
        episodes.sort(key=lambda x: x['stream_id'], reverse=True)
        latest_id = episodes[0]['stream_id'] if episodes else 0
        all_groups.append({
            'episodes': episodes,
            'latest_id': latest_id,
            'count': len(episodes)
        })

    all_groups.sort(key=lambda x: x['latest_id'], reverse=True)

    series_list_save = []
    tvshows_list_save = []

    for group in all_groups:
        formatted_episodes = [(x['line'], x['url']) for x in group['episodes']]
        if group['count'] > 20:
            tvshows_list_save.extend(formatted_episodes)
        else:
            series_list_save.extend(formatted_episodes)

    # --- SAVING ---
    save_file(file_live, live_items)
    save_file(file_movies, movie_list_save)
    save_file(file_series, series_list_save)
    save_file(file_tvshows, tvshows_list_save)

def save_file(filename, items_list):
    lines_to_save = ["#EXTM3U"]
    for info, url in items_list:
        lines_to_save.append(info)
        lines_to_save.append(url)
        
    if len(items_list) > 0:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_save))
        print(f"Saved {filename}: {len(items_list)} channels.")
    else:
        print(f"No channels found for {filename}.")

# ==========================================
#              CONFIGURATION
# ==========================================

HOST_URL = "https://webhop.live"
USERNAME = "juno123"
PASSWORD = "juno123"

m3u_url = f"{HOST_URL}/get.php?username={USERNAME}&password={PASSWORD}&type=m3u_plus&output=ts"

output_live = "Live.m3u"
output_movies = "Movies.m3u"
output_series = "Web Series.m3u"
output_tvshows = "TV Shows.m3u"

if __name__ == "__main__":
    filter_and_split_playlist(m3u_url, output_live, output_series, output_movies, output_tvshows)
