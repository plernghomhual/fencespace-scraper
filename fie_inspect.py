import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
text = res.text

# Find everything around "search" that looks like an HTTP call
for keyword in [".post(", ".get(", "fetch(", "XMLHttpRequest", "$.ajax", "http.post", "http.get"]:
    indices = [m.start() for m in re.finditer(re.escape(keyword), text)]
    if indices:
        print(f"\n--- '{keyword}' found {len(indices)} times ---")
        for idx in indices[:5]:
            print(f"\n...{text[max(0,idx-150):idx+300]}...")
