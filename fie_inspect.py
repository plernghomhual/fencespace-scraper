import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
text = res.text

# Get everything around getValuesRankings
idx = text.find("getValuesRankings")
if idx > 0:
    print("getValuesRankings context:")
    print(text[idx:idx+2000])

# Also find fetchFencers full context
idx2 = text.find("fetchFencers")
if idx2 > 0:
    print("\nfetchFencers context:")
    print(text[idx2:idx2+2000])
