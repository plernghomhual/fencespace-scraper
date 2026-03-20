import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Check usafencing.org/clubs
res = requests.get("https://www.usafencing.org/clubs", headers=HEADERS, timeout=15)
print("=== usafencing.org/clubs ===")
print(res.text[:2000])

print("\n\n=== member.usafencing.org/clubs ===")
res2 = requests.get("https://member.usafencing.org/clubs", headers=HEADERS, timeout=15)
print(res2.text[:2000])

# Also check for any XHR endpoints on fencingtracker
print("\n\n=== fencingtracker.com ===")
res3 = requests.get("https://www.fencingtracker.com", headers=HEADERS, timeout=15)
# Look for API endpoints in the JS
api_urls = re.findall(r'["\'](/api/[^"\']+)["\']', res3.text)
print("API endpoints found:", api_urls[:20])
