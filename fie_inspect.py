import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Try fetching all clubs with empty query
res = requests.get(
    "https://member.usafencing.org/clubs",
    params={
        "q": "",
        "division": "",
        "state": "",
        "club_type": "",
        "sort": "",
        "lat": "",
        "lon": "",
        "page": 1,
        "perPage": 50,
        "distance": 1
    },
    headers={
        **HEADERS,
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest"
    },
    timeout=15
)

print(f"Status: {res.status_code}")
print(f"Content-Type: {res.headers.get('Content-Type')}")
print(res.text[:2000])
