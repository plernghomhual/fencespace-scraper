import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/athletes?weapon=S&gender=M&category=S", headers=HEADERS, timeout=15)
print(f"Status: {res.status_code}")
print(f"Final URL: {res.url}")

# Look for any inline JSON data
matches = re.findall(r'window\.__\w+\s*=\s*(\[.*?\]|\{.*?\});', res.text, re.DOTALL)
for i, m in enumerate(matches[:5]):
    print(f"\nInline data {i}: {m[:400]}")

# Print raw HTML chunk around "fencer" or "athlete" keywords
idx = res.text.lower().find("fencer")
if idx > 0:
    print(f"\nHTML around 'fencer': {res.text[idx-100:idx+400]}")

idx2 = res.text.lower().find("ranking")
if idx2 > 0:
    print(f"\nHTML around 'ranking': {res.text[idx2-100:idx2+400]}")

print(f"\nFull HTML length: {len(res.text)}")
print(f"\nLast 1000 chars: {res.text[-1000:]}")
