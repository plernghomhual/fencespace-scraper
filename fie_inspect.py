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

for status in ["passed", "", "upcoming"]:
    for season in [2026, 2025, 0]:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": "", "toDate": "", "fetchPage": 1,
        }
        res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
        try:
            data = res.json()
            comps = data.get('competitions', data.get('data', data.get('results', [])))
            count = len(comps)
            print(f"status={repr(status)}, season={season} → {res.status_code}, count={count}")
            if count > 0:
                print(f"  ✅ SAMPLE: {json.dumps(comps[0], indent=2)}")
        except:
            print(f"status={repr(status)}, season={season} → {res.status_code}, not JSON")
