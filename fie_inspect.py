import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
text = res.text

# Find the ranking container code specifically
idx = text.find("athletes-ranking-container")
if idx > 0:
    # Get a large chunk around it
    print(text[idx:idx+3000])
