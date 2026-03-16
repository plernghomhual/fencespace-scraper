import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/fencers", headers=HEADERS, timeout=15)
soup = BeautifulSoup(res.text, "html.parser")

# Look for any API calls or data endpoints in the JS
scripts = soup.find_all("script")
print(f"Scripts found: {len(scripts)}")
for i, s in enumerate(scripts):
    src = s.get("src", "")
    content = s.string or ""
    if any(x in content.lower() for x in ["api", "fetch", "axios", "endpoint", "fencer", "athlete", "ranking"]):
        print(f"\nScript {i} (src={src}):")
        print(content[:800])

# Also look for any inline JSON data
json_patterns = re.findall(r'window\.__.*?=\s*({.*?});', res.text, re.DOTALL)
for p in json_patterns[:3]:
    print(f"\nInline JSON: {p[:500]}")
