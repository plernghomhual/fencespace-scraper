import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/competitions.js", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}")
print(f"Length: {len(res.text)}")

# Find POST calls
for keyword in [".post(", "axios", "/competitions", "search", "fetch("]:
    indices = [m.start() for m in re.finditer(re.escape(keyword), res.text)]
    if indices:
        print(f"\n--- '{keyword}' found {len(indices)} times ---")
        for idx in indices[:3]:
            print(f"\n...{res.text[max(0,idx-100):idx+300]}...")
