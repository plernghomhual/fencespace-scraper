import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

sources = [
    # FencingTracker
    "https://www.fencingtracker.com",
    "https://www.fencingtracker.com/api",
    "https://www.fencingtracker.com/results",
    "https://www.fencingtracker.com/clubs",
    # USA Fencing
    "https://www.usafencing.org/clubs",
    "https://www.usafencing.org/find-a-club",
    "https://member.usafencing.org/clubs",
    "https://member.usafencing.org/api/clubs",
]

for url in sources:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"{url} → {res.status_code} — {res.text[:150]}")
    except Exception as e:
        print(f"{url} → ERROR: {type(e).__name__}")
