import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

res = requests.get("https://fie.org/competitions/2026/113", headers=HEADERS, timeout=15)

# Get all inline data blocks
matches = re.findall(r'window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);', res.text, re.DOTALL)
for i, m in enumerate(matches):
    try:
        data = json.loads(m)
        print(f"\n=== Block {i} (type: {type(data).__name__}, len: {len(str(m))}) ===")
        print(json.dumps(data, indent=2)[:1000])
    except Exception:
        pass

# Also look for results-specific JS file
scripts = re.findall(r'<script src="([^"]*)"', res.text)
print("\nScript files:")
for s in scripts:
    if 'competition' in s.lower() or 'result' in s.lower():
        print(s)
