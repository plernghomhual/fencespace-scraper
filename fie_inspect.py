import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/js/athletes.js", headers=HEADERS, timeout=15)
text = res.text

# Find fencerSearch function
idx = text.find("fencerSearch")
if idx > 0:
    print(text[idx:idx+2000])

# Also find axios calls specifically
axios_calls = re.findall(r'axios\.[a-z]+\([^)]{0,200}\)', text)
print("\nAxios calls found:")
for call in axios_calls[:10]:
    print(call)

# Find any URL with athletes in it
athlete_urls = re.findall(r'["\`]/athletes[a-zA-Z0-9/_\-?=&]*["\`]', text)
print("\nAthlete URLs found:")
for u in set(athlete_urls):
    print(u)
