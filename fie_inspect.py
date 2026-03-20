import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

s = requests.Session()
s.headers.update(HEADERS)
s.get("https://fie.org/athletes", timeout=15)

res = s.post("https://fie.org/athletes", headers={
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/athletes",
}, json={
    "weapon": "S", "gender": "M", "category": "S",
    "season": "2026", "page": 1
}, timeout=15)

data = res.json()
athletes = data.get("athletes", data.get("items", []))
if athletes:
    print("Keys:", list(athletes[0].keys()))
    print("Full sample:")
    print(json.dumps(athletes[0], indent=2))
