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
    "Origin": "https://fie.org",
}

# Season is an int (2026 = "2025/2026"), -1 = all
for season in [2026, 2025, -1, 0]:
    payload = {
        "name": "",
        "status": "upcoming",
        "gender": [],
        "weapon": [],
        "type": [],
        "season": season,
        "level": "",
        "competitionCategory": "",
        "fromDate": "",
        "toDate": "",
        "fetchPage": 1,
    }
    res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
    print(f"season={season} → {res.status_code}")
    if res.status_code == 200:
        try:
            data = res.json()
            comps = data.get('competitions', data.get('data', data.get('results', [])))
            print(f"  ✅ Count: {len(comps)}")
            if comps:
                print(f"  Sample: {json.dumps(comps[0], indent=2)}")
        except:
            print(f"  Body: {res.text[:200]}")
    else:
        print(f"  Body: {res.text[:100]}")
