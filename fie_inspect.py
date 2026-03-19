import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

res = requests.get("https://fie.org/competitions/2026/113", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}")

# Look for any inline JSON with competition data
matches = re.findall(r'window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);', res.text, re.DOTALL)
for i, m in enumerate(matches[:5]):
    print(f"\nInline data {i}: {m[:500]}")

# Look for the competition ID in any format
for pattern in [r'"id"\s*:\s*(\d+)', r'"competitionId"\s*:\s*(\d+)', r'"fieId"\s*:\s*(\d+)']:
    found = re.findall(pattern, res.text)
    if found:
        print(f"\nPattern {pattern}: {found[:5]}")

# Print a chunk of HTML around any numeric ID
idx = res.text.find('113')
if idx > 0:
    print(f"\nHTML around '113': {res.text[max(0,idx-200):idx+200]}")
