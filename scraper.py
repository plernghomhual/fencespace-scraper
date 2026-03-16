import os
import re
import json
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from datetime import datetime
import time

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

WEAPON_MAP = {"S": "Sabre", "E": "Epee", "F": "Foil"}

QUERIES = [
    {"weapon": "S", "gender": "M"},
    {"weapon": "S", "gender": "F"},
    {"weapon": "E", "gender": "M"},
    {"weapon": "E", "gender": "F"},
    {"weapon": "F", "gender": "M"},
    {"weapon": "F", "gender": "F"},
]


def scrape_rankings(weapon: str, gender: str):
    url = f"https://fie.org/fencers?weapon={weapon}&gender={gender}&category=S"
    gender_label = "Women's" if gender == "F" else "Men's"
    weapon_label = WEAPON_MAP.get(weapon, weapon)
    print(f"Scraping {gender_label} {weapon_label}...")

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()

        # Extract window._topFencers JSON
        match = re.search(r'window\._topFencers\s*=\s*(\[.*?\]);', res.text, re.DOTALL)
        if not match:
            print(f"No _topFencers data found for {gender_label} {weapon_label}")
            return

        fencers = json.loads(match.group(1))
        print(f"Found {len(fencers)} fencers")

        for f in fencers:
            fie_id = str(f.get("id", ""))
            name = f.get("name", "").strip()
            country = f.get("country", "").strip()
            rank = f.get("rank")
            points_raw = f.get("points", "0")
            points = int(float(points_raw)) if points_raw else 0
            hand = f.get("hand", "")
            dob = f.get("date", None)

            if not name:
                continue

            fencer_data = {
                "fie_id": fie_id,
                "name": name,
                "country": country,
                "weapon": weapon_label,
                "category": f"{gender_label} Senior",
                "world_rank": rank,
                "fie_points": points,
                "updated_at": datetime.utcnow().isoformat(),
            }

            supabase.table("fs_fencers").upsert(
                fencer_data,
                on_conflict="fie_id"
            ).execute()

        print(f"Done — {gender_label} {weapon_label} ({len(fencers)} fencers)")
        time.sleep(2)

    except Exception as e:
        print(f"Error scraping {gender_label} {weapon_label}: {e}")


def main():
    print(f"FenceSquare scraper starting — {datetime.utcnow().isoformat()}")
    for q in QUERIES:
        scrape_rankings(q["weapon"], q["gender"])
    print("Scraper complete")


if __name__ == "__main__":
    main()
