import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import io
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / 'docker' / '.env'

if not load_dotenv(dotenv_path=env_path):
    print(f"WARNING: Could not load .env file at: {env_path}")

# supabase cloud storage credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "csv_uploads"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_game_details(appid): #fetch technical details from the steam api
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english" #api json
        res = requests.get(url, timeout=10)
        data = res.json()
        
        if data[str(appid)]['success']:
            details = data[str(appid)]['data']
            
            dev = details.get('developers', ['N/A'])[0]
            pub = details.get('publishers', ['N/A'])[0]
            gen = [g['description'] for g in details.get('genres', [])]
            primary_genre = gen[0] if gen else "N/A"
            cats = [c['description'] for c in details.get('categories', [])]
            primary_category = cats[0] if cats else "N/A"

            #metacritic score
            metacritic = details['metacritic']['score'] if 'metacritic' in details else "N/A"
            
            #platform compatibility
            platforms_dict = details.get('platforms', {})
            supported_list = [p.capitalize() for p, supported in platforms_dict.items() if supported]
            platforms_str = ", ".join(supported_list) if supported_list else "N/A"
            
            #price and system storage parsing via regex
            price_info = details.get('price_overview', {})
            price_real = price_info.get('final', 0) / 100.0 if price_info else 0.0
            
            pc_reqs = details.get('pc_requirements', {}).get('minimum', '')
            clean_text = re.sub(r'<[^>]+>', ' ', pc_reqs)
            storage_match = re.search(r'(\d+)\s*(GB|gb|MB|mb)', clean_text)
            storage = storage_match.group(0) if storage_match else "N/A"
            
            return dev, pub, primary_genre, primary_category, price_real, storage, metacritic, platforms_str
    except:
        pass
    return "N/A", "N/A", "N/A", "N/A", 0.0, "N/A", 0, "N/A"

def scrape_steam_data():
    all_games = []
    for start in range(0, 550, 50):
        url = f"https://store.steampowered.com/search/results/?query&start={start}&count=50&infinite=1"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        
        print(f"LOG: Processing items {start} to {start+50}...")
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.json()['results_html'], 'html.parser')
            rows = soup.select('a.search_result_row')
            
            for row in rows:
                appid = row['data-ds-appid']
                title = row.find('span', class_='title').text.strip()
                
                #review summary parsing
                review_span = row.select_one('.search_review_summary')
                review_summary = "N/A"
                if review_span and review_span.has_attr('data-tooltip-html'):
                    review_summary = review_span['data-tooltip-html'].split('<br>')[0]

                #enrichment via technical api call
                dev, pub, gen, cat, price, storage, meta, platforms = get_game_details(appid)
                
                all_games.append({
                    "Transaction_ID": f"TX_{int(time.time())}_{len(all_games)}",
                    "AppID": appid,
                    "Game_Title": title,
                    "Developer": dev,
                    "Publisher": pub,
                    "Genre": gen,
                    "Category": cat,
                    "Metacritic_Score": meta,
                    "Supported_Platforms": platforms,
                    "Review_Summary": review_summary,
                    "Storage": storage,
                    "Price_EUR": price,
                    "Steam_Link": f"https://store.steampowered.com/app/{appid}",
                    "Release_Date": row.find('div', class_='search_released').text.strip() or "N/A"
                })
                time.sleep(0.1) 
            
            print(f"LOG: Currently at {len(all_games)} items.")
            if len(all_games) >= 300: break
            
        except Exception as e:
            print(f"ERROR: {e}")
            break
            
    return all_games

def start_crawler():
    print("STATUS: Steam technical crawler is active (Target: 300 records).")
    while True:
        data = scrape_steam_data()
        if len(data) >= 300:
            df = pd.DataFrame(data)
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            
            filename = f"steam_data_300_{int(time.time())}.csv"
            try:
                #upload generated csv to supabase bucket
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=filename,
                    file=csv_buf.getvalue().encode('utf-8'),
                    file_options={"content-type": "text/csv"}
                )
                print(f"SUCCESS: {filename} uploaded with {len(df)} records.")
            except Exception as e:
                print(f"FAIL: {e}")
        
        print("LOG: Cycle complete. Waiting 100 seconds.")
        time.sleep(100)

if __name__ == "__main__":
    start_crawler() 