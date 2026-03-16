import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
res = requests.get("https://fie.org/js/competitions.js", headers=HEADERS, timeout=15)
text = res.text

# Find the full competitions/search block — get more context around it
print("=== Full POST block ===")
for m in re.finditer(r'competitions/search', text):
    idx = m.start()
    print(text[max(0, idx-300):idx+600])
    print("\n---\n")

# Look for axios defaults or interceptors
print("=== Axios defaults/interceptors ===")
for keyword in ['defaults.headers', 'interceptors', 'common[', 'withCredentials']:
    for m in re.finditer(re.escape(keyword), text):
        idx = m.start()
        print(f"\n[{keyword}]")
        print(text[max(0, idx-100):idx+300])
        print("---")

# Look for season select options to find valid season values
print("\n=== Season values ===")
for m in re.finditer(r'season', text):
    idx = m.start()
    snippet = text[max(0, idx-50):idx+150]
    if any(c.isdigit() for c in snippet):
        print(snippet)
        print("---")
