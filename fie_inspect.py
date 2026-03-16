import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/competitions",
}

payloads = [
    {"name": "", "status": "upcoming", "gender": [], "weapon": [], "type": [], "page": 1},
    {"name": "", "status": "results", "gender": [], "weapon": [], "type": [], "page": 1},
    {"name": "", "status": "upcoming", "page": 1, "season": "2026"},
]

for payload in payloads:
    res = requests.post(
        "https://fie.org/competitions/search",
        headers=HEADERS,
        json=payload,
        timeout=15
    )
    print(f"\nPayload: {payload}")
    print(f"Status: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    try:
        data = res.json()
        print(f"Keys: {list(data.keys())}")
        competitions = data.get('competitions', data.get('allCompetitions', data.get('data', [])))
        print(f"Competitions found: {len(competitions)}")
        if competitions:
            print(f"Sample: {competitions[0]}")
    except:
        print(f"Not JSON: {res.text[:200]}")
