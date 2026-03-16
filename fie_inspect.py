import requests
import re
import json

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

page = s.get("https://fie.org/competitions", timeout=15)
print(f"Cookies: {dict(s.cookies)}")

# Check for any hidden token anywhere in the page
for pattern in [r'token["\s:=]+([a-zA-Z0-9_\-]{20,})', r'"_csrf"\s*:\s*"([^"]+)"', r'xsrf["\s:=]+([a-zA-Z0-9_\-]{20,})']:
    m = re.search(pattern, page.text, re.IGNORECASE)
    if m:
        print(f"Token found: {m.group(1)[:40]}")

# Try 1: form-encoded (not JSON)
print("\n--- Test 1: form-encoded ---")
res = s.post(
    "https://fie.org/competitions/search",
    headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://fie.org/competitions"},
    data={"name": "", "status": "upcoming", "season": "", "level": ""},
    timeout=15
)
print(f"Status: {res.status_code}")
print(f"Body: {res.text[:300]}")

# Try 2: GET instead of POST
print("\n--- Test 2: GET with params ---")
res2 = s.get(
    "https://fie.org/competitions/search",
    headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://fie.org/competitions"},
    params={"name": "", "status": "upcoming", "season": "", "level": ""},
    timeout=15
)
print(f"Status: {res2.status_code}")
print(f"Body: {res2.text[:300]}")

# Try 3: check if there's a /api/ prefix
print("\n--- Test 3: /api/competitions/search ---")
res3 = s.post(
    "https://fie.org/api/competitions/search",
    headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
    json={"name": "", "status": "upcoming", "season": "", "level": ""},
    timeout=15
)
print(f"Status: {res3.status_code}")
print(f"Body: {res3.text[:300]}")
