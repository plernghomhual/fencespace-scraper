import requests
import json
import time
from datetime import date


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


def fetch_range(s, from_date, to_date, status="passed"):
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": 0, "level": "", "competitionCategory": "",
            "fromDate": from_date, "toDate": to_date, "fetchPage": page,
        }
        try:
            res = s.post("https://fie.org/competitions/search", headers=POST_HEADERS, json=payload, timeout=15)
            if res.status_code != 200 or not res.text.strip():
                return None
            items = res.json().get('items', [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < 300:
                break
            if page >= 20:
                print(f"    ⚠️  Hit page cap for {from_date}–{to_date}, may be truncated!")
                break
            page += 1
        except Exception as e:
            print(f"    Error: {e}")
            return None
    return all_items


seen = set()
unique = []

s = make_session()

# Go month by month from 2010 to now
from datetime import timedelta
import calendar

for year in range(2010, 2027):
    for month in range(1, 13):
        if year == 2026 and month > 12:
            break
        last_day = calendar.monthrange(year, month)[1]
        from_d = f"{str(year).zfill(4)}-{str(month).zfill(2)}-01"
        to_d   = f"{str(year).zfill(4)}-{str(month).zfill(2)}-{str(last_day).zfill(2)}"

        result = fetch_range(s, from_d, to_d)
        if result is None:
            s = make_session()
            time.sleep(1)
            result = fetch_range(s, from_d, to_d) or []

        new = 0
        for c in result:
            if c['competitionId'] not in seen:
                seen.add(c['competitionId'])
                unique.append(c)
                new += 1

        if result:
            print(f"{from_d}: {len(result)} fetched, {new} new (total: {len(unique)})")

# Upcoming
print("\nFetching upcoming...")
result = fetch_range(s, "", "", status="") or []
for c in result:
    if c['competitionId'] not in seen:
        seen.add(c['competitionId'])
        unique.append(c)

print(f"\nGrand total: {len(unique)}")
with open("competitions.json", "w") as f:
    json.dump(unique, f, indent=2)
print("Saved to competitions.json")
