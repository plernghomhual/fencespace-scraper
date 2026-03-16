import requests
import json

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# Get session cookie first
s.get("https://fie.org/competitions", timeout=15)

headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/competitions",
    "Origin": "https://fie.org",
}

# Try different season values
for season in ["2025-2026", "2026", "2025", ""]:
    payload = {
        "name": "",
        "status": "upcoming",
        "gender": [],
        "weapon": [],
        "type": [],
        "season": season,
        "level": "",
    }
    res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
    print(f"Season '{season}' → Status: {res.status_code}, Content-Type: {res.headers.get('content-type','?')}")
    if res.status_code == 200:
        try:
            data = res.json()
            print(f"  Keys: {list(data.keys())}")
            comps = data.get('competitions', data.get('data', data.get('results', [])))
            print(f"  Count: {len(comps)}")
            if comps:
                print(f"  Sample: {json.dumps(comps[0], indent=2)}")
        except:
            print(f"  Not JSON: {res.text[:200]}")
    else:
        print(f"  Body: {res.text[:150]}")
