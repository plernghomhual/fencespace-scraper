import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
text = res.text

# Find full getValuesRankings function definition
idx = text.find("function getValuesRankings")
if idx > 0:
    print(text[idx:idx+1000])
else:
    # Try alternate patterns
    idx = text.find("getValuesRankings = function")
    if idx > 0:
        print(text[idx:idx+1000])
    else:
        # Search all occurrences
        for m in re.finditer(r'getValuesRankings', text):
            print(f"\nAt {m.start()}:")
            print(text[m.start():m.start()+500])
