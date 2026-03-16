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


def fetch_chunk(s, status, season, weapon, gender):
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status,
            "gender": [gender] if gender else [],
            "weapon": [weapon] if weapon else [],
            "type": [], "season": season, "level": "",
            "competitionCategory": "", "fromDate": "", "toDate": "",
            "fetchPage": page,
        }
        try:
            res = s.post("https://fie.org/competitions/search", headers=POST_HEADERS, json=payload, timeout=15)
            if res.status_code != 200 or not res.text.strip():
                return None  # signal failure
            items = res.json().get('items', [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < 300:
                break  # last page
            page += 1
        except Exception:
            return None
    return all_items


weapons = ["foil", "epee", "sabre"]
genders = ["men", "women"]

seen = set()
unique = []

for season in range(2010, 2027):
    print(f"\n=== Season {season} ===")
    s = make_session()
    for weapon in weapons:
        for gender in genders:
            result = fetch_chunk(s, "passed", season, weapon, gender)
            if result is None:
                print(f"  {weapon}/{gender}: failed, retrying with new session...")
                s = make_session()
                time.sleep(2)
                result = fetch_chunk(s, "passed", season, weapon, gender)
            count = 0
            for c in (result or []):
                if c['competitionId'] not in seen:
                    seen.add(c['competitionId'])
                    unique.append(c)
                    count += 1
            print(f"  {weapon}/{gender}: {len(result or [])} fetched, {count} new")

# Upcoming
print("\n=== Upcoming ===")
s = make_session()
for weapon in weapons:
    for gender in genders:
        result = fetch_chunk(s, "", 2026, weapon, gender)
        for c in (result or []):
            if c['competitionId'] not in seen:
                seen.add(c['competitionId'])
                unique.append(c)

print(f"\nGrand total (deduplicated): {len(unique)}")
with open("competitions.json", "w") as f:
    json.dump(unique, f, indent=2)
print("Saved to competitions.json")
