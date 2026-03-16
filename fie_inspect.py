import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)

# Search for ranking-related strings
text = res.text

# Find anything near "ranking" or "points"
for keyword in ["ranking", "points", "rank", "/api/", "axios.get", "axios.post", "$http"]:
    indices = [m.start() for m in re.finditer(keyword, text, re.IGNORECASE)]
    if indices:
        print(f"\n--- '{keyword}' found {len(indices)} times ---")
        # Show context around first 3 occurrences
        for idx in indices[:3]:
            snippet = text[max(0, idx-100):idx+200]
            print(f"\n...{snippet}...")
