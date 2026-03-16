import os
import json
import requests
from supabase import create_client, Client
from datetime import datetime
import time

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

WEAPONS = [
    {"weapon": "S", "gender": "M", "label": "Men's Sabre"},
    {"weapon": "S", "gender": "F", "label": "Women's Sabre"},
    {"weapon": "E", "gender": "M", "label": "Men's Epee"},
    {"weapon": "E", "gender": "F", "label": "Women's Epee"},
    {"weapon": "F", "gender": "M", "label": "Men's Foil"},
    {"weapon": "F", "gender": "F", "label": "Women's Foil"},
]

WEAPON_MAP = {"S": "Sabre", "E": "Epee", "F": "Foil"}


def scrape_rankings(weapon: str, gender: str, label: str):
    print(f"Scraping {label}...")
    page = 1
    total = 0

    while True:
        payload = {
            "weapon": weapon,
            "gender": gender,
            "category": "S",
            "country": "",
            "name": "",
            "page": page,
        }

        try:
            res = requests.post(
                "https://fie.org/athletes",
                headers=HEADERS,
                json=payload,
                timeout=15
            )
            res.raise_for_status()
            data = res.json()
            athletes = data.get("allAthletes", [])

            if not athletes:
                break

            for f in athletes:
                fie_id = str(f.get("id", ""))
                name = f.get("name", "").strip()
                country = f.get("country", "").strip()
                rank = f.get("rank")
                points_raw = f.get("points", "0") or "0"
                points = int(float(points_raw))
                gender_label = "Women's" if gender == "F" else "Men's"

                if not name or not fie_id:
                    continue

                fencer_data = {
                    "fie_id": fie_id,
                    "name": name,
                    "country": country,
                    "weapon": WEAPON_MAP.get(weapon, weapon),
                    "category": f"{gender_label} Senior",
                    "world_rank": rank,
                    "fie_points": points,
                    "updated_at": datetime.utcnow().isoformat(),
                }

                supabase.table("fs_fencers").upsert(
                    fencer_data,
                    on_conflict="fie_id,weapon"
                ).execute()

            total += len(athletes)
            print(f"  Page {page} — {len(athletes)} fencers (total: {total})")

            if len(athletes) < 100:
                break

            page += 1
            time.sleep(1)

        except Exception as e:
            print(f"Error on page {page}: {e}")
            break

    print(f"Done — {label}: {total} fencers")


def main():
    print(f"FenceSquare scraper starting — {datetime.utcnow().isoformat()}")
    for w in WEAPONS:
        scrape_rankings(w["weapon"], w["gender"], w["label"])
        time.sleep(2)
    print("Scraper complete")


if __name__ == "__main__":
    main()
