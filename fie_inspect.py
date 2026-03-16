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


def fetch_competitions(status, season):
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": "", "toDate": "", "fetchPage": page,
        }
        res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
        items = res.json().get('items', [])
        print(f"  Page {page}: {len(items)} items")
        if not items:
            break
        all_items.extend(items)
        page += 1
    return all_items

all_comps = []
for season in range(2010, 2027):
    print(f"\nFetching season {season}...")
    comps = fetch_competitions(status="passed", season=season)
    print(f"  → {len(comps)} total")
    all_comps.extend(comps)

print("\nFetching upcoming (2026)...")
upcoming = fetch_competitions(status="", season=2026)
print(f"  → {len(upcoming)} total")
all_comps.extend(upcoming)

# Deduplicate by competitionId
seen = set()
unique = []
for c in all_comps:
    if c['competitionId'] not in seen:
        seen.add(c['competitionId'])
        unique.append(c)

print(f"\nGrand total (deduplicated): {len(unique)}")
with open("competitions.json", "w") as f:
    json.dump(unique, f, indent=2)
print("Saved to competitions.json")
