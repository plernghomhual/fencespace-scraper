import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

# Try FIE's actual API endpoint
urls = [
    "https://fie.org/api/athletes?weapon=s&gender=m&category=S&page=1",
    "https://fie.org/en/athletes",
    "https://fie.org/fencers",
    "https://fie.org/rankings",
]

for url in urls:
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        print(f"\n{url}")
        print(f"Status: {res.status_code}")
        print(f"Content-Type: {res.headers.get('content-type', 'unknown')}")
        print(f"First 500 chars: {res.text[:500]}")
    except Exception as e:
        print(f"{url} — Error: {e}")
