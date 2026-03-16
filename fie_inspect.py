import requests
import json
import time


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    s.get("https://fie.org/competitions", timeout=15)
    return s


POST_HEADERS = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}


def fetch_competitions(status, season):
    s = make_session()
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": "", "toDate": "", "fetchPage": page,
        }
        try:
            res = s.post("https://fie.org/competitions/search", headers=POST_HEADERS, json=payload, timeout=15)
            if res.status_code != 200 or not res.text.strip():
                print(f"  Page {page}: empty/error ({res.status_code}), refreshing session...")
                s = make_session()
                time.sleep(1)
                continue
            data = res.json()
            items = data.get("items", [])
            print(f"  Page {page}: {len(items)} items")
            if not items:
                break
            all_items.extend(items)
            page += 1
        except Exception as e:
            print(f"  Page {page}: error {e}, refreshing session...")
            s = make_session()
            time.sleep(2)
    return all_items


all_comps = []
for season in range(2010, 2027):
    print(f"\nFetching season {season}...")
    comps = fetch_competitions(status="passed", season=season)
    print(f"  → {len(comps)} total")
    all_comps.extend(comps)

print("\nFetching upcoming...")
upcoming = fetch_competitions(status="", season=2026)
print(f"  → {len(upcoming)} total")
all_comps.extend(upcoming)

# Deduplicate
seen = set()
unique = [c for c in all_comps if not (c["competitionId"] in seen or seen.add(c["competitionId"]))]

print(f"\nGrand total (deduplicated): {len(unique)}")
with open("competitions.json", "w") as f:
    json.dump(unique, f, indent=2)
print("Saved to competitions.json")
