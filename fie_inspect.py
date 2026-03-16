import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}

# Try different payload structures for filtered rankings
payloads = [
    {"weapon": "S", "gender": "M", "category": "S", "page": 1, "ranking": 1},
    {"weapon": "S", "gender": "M", "category": "S", "perPage": 100},
    {"weapon": "S", "gender": "M", "category": "S", "rank_from": 1, "rank_to": 100},
    {"weapon": "S", "gender": "M", "category": "S", "page": 1, "ranked": True},
]

for payload in payloads:
    res = requests.post(
        "https://fie.org/athletes/search",
        headers=HEADERS,
        json=payload,
        timeout=15
    )
    data = res.json()
    athletes = data.get("allAthletes", data.get("athletes", data.get("data", [])))

    # Check if any have rank/points
    ranked = [a for a in athletes if a.get("rank") or a.get("points")]
    print(f"\nPayload: {payload}")
    print(f"Total returned: {len(athletes)}")
    print(f"With rank/points: {len(ranked)}")
    if ranked:
        print(f"Sample: {ranked[0]}")
