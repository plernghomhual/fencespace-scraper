import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# AskFRED public API - club directory
res = requests.get(
    "https://api.askfred.net/v1/club",
    headers=HEADERS,
    timeout=15
)
print(f"Status: {res.status_code}")
print(f"Response preview: {res.text[:1000]}")
