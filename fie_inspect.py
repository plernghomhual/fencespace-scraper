import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

# Fetch the athletes JS file
res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}")
print(f"Length: {len(res.text)}")

# Look for any URL/endpoint patterns
urls = re.findall(r'["\'](\/[a-zA-Z0-9_\/\-\?=&]+)["\']', res.text)
print("\nURLs found in JS:")
for u in urls:
    if any(x in u.lower() for x in ["api", "athlete", "fencer", "rank", "json", "data"]):
        print(u)

# Print first 2000 chars
print(f"\nFirst 2000 chars:\n{res.text[:2000]}")
