import requests, re, json

HEADERS = {"User-Agent": "Mozilla/5.0"}
res = requests.get("https://fie.org/competitions/2026/1459", headers=HEADERS, timeout=15)
matches = re.findall(r'window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);', res.text, re.DOTALL)
for i, m in enumerate(matches):
    try:
        data = json.loads(m)
        if isinstance(data, dict) and 'rows' in data and data['rows']:
            print(f"Block {i} rows sample:")
            print(json.dumps(data['rows'][:3], indent=2))
    except Exception:
        pass
