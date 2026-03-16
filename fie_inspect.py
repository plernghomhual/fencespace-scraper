import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

payload = {
    "weapon": "S",
    "gender": "M",
    "category": "S",
    "country": "",
    "name": "",
    "page": 1,
}

res = requests.post("https://fie.org/athletes", headers=HEADERS, json=payload, timeout=15)
data = res.json()
athletes = data.get("allAthletes", [])

# Show first 15 with their ranks
print(f"Total returned: {len(athletes)}")
print("\nFirst 15 fencers:")
for a in athletes[:15]:
    print(f"Rank: {a.get('rank')} | Name: {a.get('name')} | Points: {a.get('points')}")
