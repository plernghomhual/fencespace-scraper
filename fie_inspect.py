import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Try to find a completed competition page
# First let's search for completed competitions on FIE
s = requests.Session()
s.headers.update(HEADERS)
s.get("https://fie.org/competitions", timeout=15)

res = s.post("https://fie.org/competitions/search", headers={
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}, json={
    "name": "", "status": "passed", "gender": [], "weapon": [], "type": [],
    "season": 2026, "level": "", "competitionCategory": "", 
    "fromDate": "2026-01-01", "toDate": "2026-03-01", "fetchPage": 1,
}, timeout=15)

items = res.json().get('items', [])
print(f"Found {len(items)} completed competitions")
for item in items[:5]:
    print(f"competitionId: {item.get('competitionId')} | name: {item.get('name')} | hasResults: {item.get('hasResults')}")
