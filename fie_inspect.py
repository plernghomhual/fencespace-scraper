import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

res = requests.get("https://fie.org/js/competitions.js", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}, Length: {len(res.text)}")

# Print the whole file if small, or first 3000 chars
if len(res.text) < 6000:
    print(res.text)
else:
    print("=== FIRST 3000 ===")
    print(res.text[:3000])
    print("=== LAST 1000 ===")
    print(res.text[-1000:])
