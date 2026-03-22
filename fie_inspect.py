import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

res = requests.get(
    "https://member.usafencing.org/clubs",
    params={
        "q": "", "division": "", "state": "", "club_type": "",
        "sort": "", "lat": "", "lon": "", "page": 1,
        "perPage": 50, "distance": 1
    },
    headers=HEADERS,
    timeout=15
)

data = res.json()
pages = data["indexData"]["pages"]
print(f"Total pages: {pages['count']}")
print(f"Per page: {pages['perPage']}")
print(f"Has more: {pages['hasMorePages']}")
print(f"Total clubs estimate: {pages['count'] * 50}")

# Show sample club fields
models = data["indexData"]["models"]
if models:
    print(f"\nSample club keys: {list(models[0].keys())}")
    print(f"First club: {models[0]['name']} — {models[0].get('publicAddress', {}).get('city_state', '')}")
