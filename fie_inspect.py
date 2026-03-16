import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/competitions",
}

payload = {
    "page": 1,
    "season": "2026",
}

res = requests.post(
    "https://fie.org/competitions",
    headers=HEADERS,
    json=payload,
    timeout=15
)

print(f"Status: {res.status_code}")
print(f"Content-Type: {res.headers.get('content-type')}")
print(f"First 1000 chars: {res.text[:1000]}")
