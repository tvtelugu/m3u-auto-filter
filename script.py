import requests
import re
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

def filter_and_split_playlist(url, file_live, file_series, file_movies, file_tvshows, file_whats_new):
    print(f"Downloading playlist from: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading playlist: {e}")
        return

    lines = content.splitlines()
    
    live_items = []
    movie_items = []
    
    # Store all "New" candidates here
    # Format: {'name': "Name", 'stream_id': 12345, 'type': "Movie", 'group_key': "clean_name", 'display_name': "Full Name"}
    all_new_content = []
    
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

                # --- CLEANING ---
                line = line.replace('tvg-id=""', '')
                line = re.sub(r'group-title=".*?"', '', line)
                line = re.sub(r'tvg-name=".*?"', '', line)

                parts = line.rsplit(',', 1)
                
                if len(parts) == 2:
                    meta_data = parts[0]
                    name = parts[1]
                    
                    if 'tvg-logo=""' in meta_data:
                        meta_data = meta_data.replace('tvg-logo=""', f'tvg-logo="{DEFAULT_LOGO}"')
                    elif 'tvg-logo=' not in meta_data:
                        meta_data = f'{meta_data} tvg-logo="{DEFAULT_LOGO}"'
                    
                    meta_data = " ".join(meta_data.split())

                    # --- PRE-ANALYSIS ---
                    is_cam = False
                    year = 0
                    if is_movie:
                        if re.search(r'\(Cam\)|Cam', name, re.IGNORECASE): is_cam = True
                        year_matches = re.findall(r'\b(?:19|20)\d{2}\b', name)
                        if year_matches: year = int(year_matches[-1])

                    # --- NAME CLEANING ---
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
                    # For Movies, Group Key is the movie name itself
                    all_new_content.append({
                        'name': name,
                        'stream_id': stream_id,
                        'type': '[Movie]',
                        'group_key': item_data['clean_name']
                    })
                    
                elif is_series:
                    # Logic to find "Show Name" for deduplication
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
                    
                    # For Series, Group Key is the SHOW NAME only.
                    # This ensures "Bigg Boss E50" and "Bigg Boss E51" are grouped, and only newest wins.
                    all_new_content.append({
                        'name': name,
                        'stream_id': stream_id,
                        'type': '[Episode]',
                        'group_key': show_name
                    })
                    
                    season_grouping[(show_name, season_num)].append(item_data)

    # ==========================
    #      POST-PROCESSING
    # ==========================

    # --- 1. MOVIES ---
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
        all_groups.append({'episodes': episodes, 'latest_id': latest_id, 'count': len(episodes)})

    all_groups.sort(key=lambda x: x['latest_id'], reverse=True)
    series_list_save = []
    tvshows_list_save = []
    for group in all_groups:
        formatted_episodes = [(x['line'], x['url']) for x in group['episodes']]
        if group['count'] > 20:
            tvshows_list_save.extend(formatted_episodes)
        else:
            series_list_save.extend(formatted_episodes)

    # --- SAVING M3U FILES ---
    save_file(file_live, live_items)
    save_file(file_movies, movie_list_save)
    save_file(file_series, series_list_save)
    save_file(file_tvshows, tvshows_list_save)

    # --- SAVE WHATS NEW (Intelligent) ---
    save_whats_new(file_whats_new, all_new_content)

def get_ist_timestamp():
    now_utc = datetime.now(timezone.utc)
    ist_offset = timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset
    return now_ist.strftime("%Y-%m-%d %H:%M:%S IST")

def save_file(filename, items_list):
    timestamp = get_ist_timestamp()
    lines_to_save = ["#EXTM3U", f"# Last Updated: {timestamp}", "# Powered By @tvtelugu"]
    for info, url in items_list:
        lines_to_save.append(info)
        lines_to_save.append(url)
    if len(items_list) > 0:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_save))
        print(f"Saved {filename}: {len(items_list)} channels.")
    else:
        print(f"No channels found for {filename}.")

def save_whats_new(filename, items_list):
    # 1. Sort by Stream ID Descending (ABSOLUTE NEWEST FIRST)
    # This guarantees that if "Bigg Boss E51" (ID 100) and "Bigg Boss E50" (ID 99) exist,
    # E51 comes first in the list.
    items_list.sort(key=lambda x: x['stream_id'], reverse=True)
    
    timestamp = get_ist_timestamp()
    lines_to_save = [
        "--------------------------------------------------",
        f"  WHATS NEW - LATEST ADDITIONS",
        f"  Last Updated: {timestamp}",
        f"  Powered By @tvtelugu",
        "--------------------------------------------------",
        ""
    ]
    
    # 2. STRICT DEDUPLICATION
    # We maintain a 'seen' set of group keys (Show Names or Movie Names).
    # Since the list is already sorted by Newest ID, the FIRST time we see "Bigg Boss",
    # it is guaranteed to be the LATEST episode. We skip all subsequent appearances.
    seen_groups = set()
    count = 1
    
    for item in items_list:
        key = item['group_key']
        
        if key not in seen_groups:
            # Found the newest entry for this show/movie
            line = f"{count}. {item['name']} {item['type']}"
            lines_to_save.append(line)
            
            seen_groups.add(key)
            count += 1
            
            # 3. LIMIT LIST SIZE
            # Stop after 100 unique updates to keep the file clean
            if count > 100:
                break

    if len(items_list) > 0:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_to_save))
        print(f"Saved {filename}: {count-1} unique new items.")

# ==========================================
#              CONFIGURATION
# ==========================================

HOST_URL = "https://webhop.live"
USERNAME = "krishna2"
PASSWORD = "krishna2"

m3u_url = f"{HOST_URL}/get.php?username={USERNAME}&password={PASSWORD}&type=m3u_plus&output=ts"

output_live = "Live.m3u"
output_movies = "Movies.m3u"
output_series = "Web Series.m3u"
output_tvshows = "TV Shows.m3u"
output_whats_new = "Whats New.txt"

if __name__ == "__main__":
    filter_and_split_playlist(m3u_url, output_live, output_series, output_movies, output_tvshows, output_whats_new)
