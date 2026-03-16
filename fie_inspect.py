import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

res = requests.get("https://fie.org/js/competitions.js", headers=HEADERS, timeout=15)
text = res.text

# Search for all URL strings that look like API endpoints
urls = re.findall(r'["\`](/[-a-zA-Z0-9/_]+)["\`]', text)
unique_urls = sorted(set(urls))
print("=== URL-like strings ===")
for u in unique_urls:
    if any(k in u for k in ['competition', 'search', 'api', 'fetch', 'athlete', 'ranking', 'result']):
        print(u)

# Search around any .post( or axios.post calls
print("\n=== POST calls ===")
for m in re.finditer(r'\.post\s*\(', text):
    idx = m.start()
    print(f"\n{text[max(0,idx-50):idx+400]}")
    print("---")

# Search for 'search' string usages
print("\n=== 'search' contexts ===")
for m in re.finditer(r'"search"|\'search\'', text):
    idx = m.start()
    print(f"\n{text[max(0,idx-100):idx+200]}")
    print("---")
