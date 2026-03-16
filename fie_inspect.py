import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/competitions",
}

urls = [
    ("GET", "https://fie.org/competitions"),
    ("GET", "https://fie.org/competition"),
    ("GET", "https://fie.org/events"),
    ("POST", "https://fie.org/competitions/search"),
    ("POST", "https://fie.org/competition/search"),
    ("GET", "https://fie.org/calendar"),
]

for method, url in urls:
    try:
        if method == "POST":
            res = requests.post(url, headers=HEADERS, json={"page": 1, "season": "2026"}, timeout=10)
        else:
            res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"\n{method} {url}")
        print(f"Status: {res.status_code}")
        print(f"Content-Type: {res.headers.get('content-type', 'unknown')}")
        print(f"First 150 chars: {res.text[:150]}")
    except Exception as e:
        print(f"\n{url} — Error: {e}")
