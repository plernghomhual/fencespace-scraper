import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

# Try the search endpoint with different methods and params
endpoints = [
    ("GET", "https://fie.org/athletes/search?weapon=S&gender=M&category=S&page=1"),
    ("GET", "https://fie.org/athletes/search?weapon=S&gender=M&category=S"),
    ("POST", "https://fie.org/athletes/search"),
]

for method, url in endpoints:
    if method == "GET":
        res = requests.get(url, headers=HEADERS, timeout=15)
    else:
        res = requests.post(url, headers={
            **HEADERS,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }, json={
            "weapon": "S",
            "gender": "M", 
            "category": "S",
            "page": 1
        }, timeout=15)

    print(f"\n{method} {url}")
    print(f"Status: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    print(f"First 500 chars: {res.text[:500]}")
