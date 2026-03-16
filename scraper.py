import os
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE = "https://fie.org"

WEAPONS = [
    {"name": "Sabre", "gender": "m", "fie_code": "s"},
    {"name": "Epee", "gender": "m", "fie_code": "e"},
    {"name": "Foil", "gender": "m", "fie_code": "f"},
    {"name": "Sabre", "gender": "f", "fie_code": "s"},
    {"name": "Epee", "gender": "f", "fie_code": "e"},
    {"name": "Foil", "gender": "f", "fie_code": "f"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"
}


def scrape_rankings(weapon: dict):
    gender = weapon["gender"]
    code = weapon["fie_code"]
    weapon_name = weapon["name"]
    category = "Women's" if gender == "f" else "Men's"

    url = f"{FIE_BASE}/en/athletes?weapon={code}&gender={gender}&category=S&ranking=1&page=1"
    print(f"Scraping {category} {weapon_name} rankings...")

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table.athletes-table tbody tr")
        if not rows:
            print(f"No rows found for {category} {weapon_name}")
            return

        for row in rows:
            cols = row.select("td")
            if len(cols) < 4:
                continue

            rank = cols[0].get_text(strip=True)
            name = cols[1].get_text(strip=True)
            country = cols[2].get_text(strip=True)
            points = cols[3].get_text(strip=True).replace(",", "")
            fie_id = row.get("data-athlete-id", None)

            if not name or not rank:
                continue

            try:
                rank_int = int(rank)
                points_int = int(points) if points.isdigit() else 0
            except ValueError:
                continue

            fencer_data = {
                "name": name,
                "country": country,
                "weapon": weapon_name,
                "category": f"{category} Senior",
                "world_rank": rank_int,
                "fie_points": points_int,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if fie_id:
                fencer_data["fie_id"] = fie_id

            # Upsert by fie_id if available, otherwise by name + weapon
            if fie_id:
                supabase.table("fs_fencers").upsert(
                    fencer_data,
                    on_conflict="fie_id"
                ).execute()
            else:
                existing = supabase.table("fs_fencers").select("id").eq("name", name).eq("weapon", weapon_name).execute()
                if existing.data:
                    supabase.table("fs_fencers").update(fencer_data).eq("name", name).eq("weapon", weapon_name).execute()
                else:
                    supabase.table("fs_fencers").insert(fencer_data).execute()

        print(f"Done — {category} {weapon_name}")
        time.sleep(2)  # be polite to FIE's servers

    except Exception as e:
        print(f"Error scraping {category} {weapon_name}: {e}")


def scrape_tournaments():
    print("Scraping upcoming tournaments...")
    url = f"{FIE_BASE}/en/competitions"

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table.competitions-table tbody tr")
        if not rows:
            print("No tournament rows found")
            return

        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue

            name = cols[0].get_text(strip=True)
            weapon = cols[1].get_text(strip=True)
            category = cols[2].get_text(strip=True)
            location = cols[3].get_text(strip=True)
            date_str = cols[4].get_text(strip=True)
            fie_id = row.get("data-competition-id", None)

            if not name:
                continue

            tournament_data = {
                "name": name,
                "weapon": weapon,
                "category": category,
                "location": location,
                "status": "upcoming",
                "updated_at": datetime.utcnow().isoformat(),
            }

            if fie_id:
                tournament_data["fie_id"] = fie_id
                supabase.table("fs_tournaments").upsert(
                    tournament_data,
                    on_conflict="fie_id"
                ).execute()
            else:
                existing = supabase.table("fs_tournaments").select("id").eq("name", name).execute()
                if not existing.data:
                    supabase.table("fs_tournaments").insert(tournament_data).execute()

        print("Tournaments done")

    except Exception as e:
        print(f"Error scraping tournaments: {e}")


def main():
    print(f"FenceSquare scraper starting — {datetime.utcnow().isoformat()}")
    for weapon in WEAPONS:
        scrape_rankings(weapon)
    scrape_tournaments()
    print("Scraper complete")


if __name__ == "__main__":
    main()
