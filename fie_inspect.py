import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

payloads = [
    {"weapon": "S", "gender": "M", "category": "S", "country": "", "name": "", "page": 1},
    {"weapon": "S", "gender": "M", "level": "s", "country": "", "name": "", "page": 1},
    {"weapon": "S", "gender": "M", "category": "S", "season": "2025", "page": 1},
    {"weapon": "S", "gender": "M", "category": "S", "season": "", "country": "", "name": ""},
]

for payload in payloads:
    res = requests.post(
        "https://fie.org/athletes",
        headers=HEADERS,
        json=payload,
        timeout=15
    )
    print(f"\nPayload: {payload}")
    print(f"Status: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    try:
        data = res.json()
        athletes = data.get("allAthletes", data.get("athletes", []))
        ranked = [a for a in athletes if a.get("rank") or a.get("points")]
        print(f"Total: {len(athletes)} | Ranked: {len(ranked)}")
        if ranked:
            print(f"Sample: {ranked[0]}")
        elif athletes:
            print(f"Sample unranked: {athletes[0]}")
    except:
        print(f"Not JSON: {res.text[:200]}")
