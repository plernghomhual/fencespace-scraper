import requests
import json

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
s.get("https://fie.org/competitions", timeout=15)

headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}


def fetch_competitions(status="passed", season=2025):
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": "", "toDate": "", "fetchPage": page,
        }
        res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
        data = res.json()
        items = data.get('items', [])
        print(f"  Page {page}: {len(items)} items")
        if not items:
            break
        all_items.extend(items)
        page += 1
        if page > 20:  # safety cap
            break
    return all_items

print("Fetching 2025 season...")
comps_2025 = fetch_competitions(status="passed", season=2025)
print(f"Total 2025: {len(comps_2025)}")

print("\nFetching 2026 season...")
comps_2026 = fetch_competitions(status="passed", season=2026)
print(f"Total 2026: {len(comps_2026)}")

print("\nFetching upcoming...")
upcoming = fetch_competitions(status="", season=2026)
print(f"Total upcoming: {len(upcoming)}")

all_comps = comps_2025 + comps_2026 + upcoming
print(f"\nGrand total: {len(all_comps)}")
print(f"\nSample keys: {list(all_comps[0].keys())}")

with open("competitions.json", "w") as f:
    json.dump(all_comps, f, indent=2)
print("Saved to competitions.json")
