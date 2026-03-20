import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

s = requests.Session()
s.headers.update(HEADERS)
r0 = s.get("https://fie.org/athletes", timeout=15)
print(f"GET /athletes status: {r0.status_code}")
print(f"Cookies after GET: {dict(s.cookies)}")

res = s.post("https://fie.org/athletes", headers={
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/athletes",
}, json={
    "weapon": "S", "gender": "M", "category": "S",
    "season": "2026", "page": 1
}, timeout=15)

print(f"POST status: {res.status_code}")
print(f"Response preview: {res.text[:500]}")

data = res.json()
print(f"Top-level keys: {list(data.keys())}")
athletes = data.get("athletes", data.get("items", []))
print(f"Athletes count: {len(athletes)}")
if athletes:
    print("Keys:", list(athletes[0].keys()))
    print(json.dumps(athletes[0], indent=2))
