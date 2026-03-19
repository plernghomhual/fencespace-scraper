import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

s = requests.Session()
s.headers.update(HEADERS)
s.get("https://fie.org/competitions", timeout=15)

# Fetch the competition page
res = s.get("https://fie.org/competitions/2026/1439", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}")

# Extract all inline JSON blocks
matches = re.findall(r'window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);', res.text, re.DOTALL)
for i, m in enumerate(matches):
    try:
        data = json.loads(m)
        if isinstance(data, dict) and any(k in data for k in ['competitionId', 'hasResults', 'pools', 'rows', 'rankingPdf']):
            print(f"\n=== Block {i} ===")
            print(json.dumps(data, indent=2)[:2000])
    except Exception:
        pass
