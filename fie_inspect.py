import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"}

url = "https://fie.org/en/athletes?weapon=s&gender=m&category=S&ranking=1&page=1"
res = requests.get(url, headers=HEADERS, timeout=15)
soup = BeautifulSoup(res.text, "html.parser")

# Print all tables found
tables = soup.find_all("table")
print(f"Tables found: {len(tables)}")
for i, t in enumerate(tables):
    print(f"\nTable {i} classes: {t.get('class')}")
    rows = t.find_all("tr")
    print(f"Rows: {len(rows)}")
    if rows:
        print(f"First row: {rows[0]}")

# Also print first 3000 chars of raw HTML
print("\n\nRAW HTML SNIPPET:")
print(res.text[:3000])
