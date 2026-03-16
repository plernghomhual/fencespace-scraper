import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

res = requests.get("https://fie.org/competitions", headers=HEADERS, timeout=15)

# Look for inline JSON data
matches = re.findall(r'window\.__\w+\s*=\s*(\[.*?\]|\{.*?\});', res.text, re.DOTALL)
for i, m in enumerate(matches[:5]):
    print(f"\nInline data {i}: {m[:400]}")

# Look for JS files
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', res.text)
print("\nScript files:")
for s in scripts:
    print(s)

# Look for any competition/event data
idx = res.text.lower().find("competition")
if idx > 0:
    print(f"\nHTML around 'competition': {res.text[idx:idx+300]}")
