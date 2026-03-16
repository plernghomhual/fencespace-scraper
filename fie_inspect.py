import requests
import re
import json

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# Step 1: Get a session cookie by loading the page
print("Getting session...")
page = s.get("https://fie.org/competitions", timeout=15)
print(f"Page status: {page.status_code}")
print(f"Cookies: {dict(s.cookies)}")

# Step 2: Look for CSRF token in the page HTML
csrf = None
for pattern in [
    r'csrf[_-]?token["\s]*[:=]["\s]*([a-zA-Z0-9_\-]+)',
    r'_token["\s]*value=["\s]*([a-zA-Z0-9_\-]+)',
    r'meta name="csrf-token" content="([^"]+)"',
]:
    match = re.search(pattern, page.text, re.IGNORECASE)
    if match:
        csrf = match.group(1)
        print(f"CSRF found: {csrf[:30]}...")
        break

if not csrf:
    print("No CSRF found in HTML")

# Step 3: Try the endpoint with session + CSRF in headers
headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://fie.org/competitions",
    "Origin": "https://fie.org",
}
if csrf:
    headers["X-CSRF-TOKEN"] = csrf
    headers["X-XSRF-TOKEN"] = csrf

payload = {"name": "", "status": "upcoming", "gender": [], "weapon": [], "type": [], "page": 1}
res = s.post("https://fie.org/competitions/search", headers=headers, json=payload, timeout=15)

print(f"\nPost status: {res.status_code}")
print(f"Content-Type: {res.headers.get('content-type')}")
try:
    data = res.json()
    print(f"Keys: {list(data.keys())}")
    comps = data.get('competitions', data.get('data', []))
    print(f"Count: {len(comps)}")
    if comps:
        print(f"Sample: {json.dumps(comps[0], indent=2)}")
except:
    print(f"Not JSON: {res.text[:300]}")
