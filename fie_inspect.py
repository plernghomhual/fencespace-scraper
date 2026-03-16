import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Check the HTML page for radio button values
res = requests.get("https://fie.org/competitions", headers=HEADERS, timeout=15)

print("=== Radio button values ===")
for m in re.finditer(r'radio[^>]*value=["\']([^"\']+)["\']', res.text, re.IGNORECASE):
    print(m.group(0)[:200])

print("\n=== Input values near 'status' ===")
for m in re.finditer(r'status', res.text, re.IGNORECASE):
    idx = m.start()
    print(res.text[max(0,idx-100):idx+200])
    print("---")

# Also try status as 1/0 or other values
s = requests.Session()
s.headers.update(HEADERS)
s.get("https://fie.org/competitions", timeout=15)

post_headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}

for status in ["1", "0", "active", "all", "past", "future", 1, 0]:
    payload = {"name": "", "status": status, "gender": [], "weapon": [], "type": [],
               "season": 2026, "level": "", "competitionCategory": "", "fromDate": "", "toDate": "", "fetchPage": 1}
    res2 = s.post("https://fie.org/competitions/search", headers=post_headers, json=payload, timeout=15)
    try:
        data = res2.json()
        count = len(data.get('competitions', data.get('data', data.get('results', []))))
        print(f"status={repr(status)} → {res2.status_code}, count={count}")
    except:
        print(f"status={repr(status)} → {res2.status_code}, not JSON")
