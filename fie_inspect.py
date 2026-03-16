import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

# FIE has a JSON API for full rankings
urls = [
    "https://fie.org/fencers?weapon=S&gender=M&category=S&page=1&json=1",
    "https://fie.org/fencers.json?weapon=S&gender=M&category=S",
    "https://fie.org/api/v1/athletes?weapon=S&gender=M&category=S",
    "https://fie.org/fencers?weapon=S&gender=M&category=S&format=json",
]

for url in urls:
    res = requests.get(url, headers=HEADERS, timeout=15)
    print(f"\n{url}")
    print(f"Status: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    print(f"First 300 chars: {res.text[:300]}")
