import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

s = requests.Session()
s.headers.update(HEADERS)
s.get("https://fie.org/competitions", timeout=15)

# Search multiple months to find ones with actual results
for month_start, month_end in [
    ("2026-01-01", "2026-02-01"),
    ("2025-12-01", "2026-01-01"),
    ("2025-11-01", "2025-12-01"),
    ("2025-10-01", "2025-11-01"),
]:
    res = s.post("https://fie.org/competitions/search", headers={
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://fie.org/competitions",
    }, json={
        "name": "", "status": "passed", "gender": [], "weapon": [], "type": [],
        "season": 2026, "level": "", "competitionCategory": "",
        "fromDate": month_start, "toDate": month_end, "fetchPage": 1,
    }, timeout=15)

    items = res.json().get('items', [])
    with_results = [i for i in items if i.get('hasResults') == 1]
    print(f"{month_start}: {len(items)} total, {len(with_results)} with results")
    for item in with_results[:3]:
        print(f"  competitionId: {item.get('competitionId')} | name: {item.get('name')} | weapon: {item.get('weapon')} | gender: {item.get('gender')}")
