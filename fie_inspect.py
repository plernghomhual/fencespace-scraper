import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

# Try different season values
seasons = ["2026", "2025", "2025-2026", "2024-2025", "1"]

for season in seasons:
    payload = {
        "weapon": "S",
        "gender": "M",
        "category": "S",
        "country": "",
        "name": "",
        "page": 1,
        "season": season,
    }

    res = requests.post("https://fie.org/athletes", headers=HEADERS, json=payload, timeout=15)
    data = res.json()
    athletes = data.get("allAthletes", [])

    ranks = [a.get('rank') for a in athletes[:10]]
    print(f"\nSeason '{season}': first 10 ranks = {ranks}")
