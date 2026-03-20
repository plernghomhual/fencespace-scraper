import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Try the actual askfred.net endpoints
for url in [
    "https://askfred.net/api/v1/clubs",
    "https://askfred.net/clubs.json",
    "https://www.askfred.net/Info/clubs.php",
]:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"{url} → {res.status_code} — {res.text[:200]}")
    except Exception as e:
        print(f"{url} → ERROR: {e}")
