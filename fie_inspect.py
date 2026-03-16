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

payload = {
    "name": "", "status": "passed", "gender": [], "weapon": [], "type": [],
    "season": 2025, "level": "", "competitionCategory": "",
    "fromDate": "", "toDate": "", "fetchPage": 1,
}

res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)
print(f"Status: {res.status_code}")
print(f"Content-Type: {res.headers.get('content-type')}")
print(f"Full body ({len(res.text)} chars):")
print(res.text[:2000])
