import requests
import os
import re

ASKFRED_EMAIL = os.environ["ASKFRED_EMAIL"]
ASKFRED_PASSWORD = os.environ["ASKFRED_PASSWORD"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def askfred_login():
    s = requests.Session()
    s.headers.update(HEADERS)

    # Get login page to extract CSRF token
    res = s.get("https://www.askfred.net/users/sign_in", timeout=15)

    # Extract authenticity_token
    match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', res.text)
    if not match:
        print("Could not find authenticity_token")
        return None

    token = match.group(1)
    print(f"Got CSRF token: {token[:20]}...")

    # Submit login
    res = s.post("https://www.askfred.net/users/sign_in", data={
        "authenticity_token": token,
        "user[email]": ASKFRED_EMAIL,
        "user[password]": ASKFRED_PASSWORD,
        "commit": "Sign in"
    }, timeout=15, allow_redirects=True)

    print(f"Login status: {res.status_code}")
    print(f"Final URL: {res.url}")

    if "sign_in" in res.url:
        print("Login failed — still on sign in page")
        return None

    print("Login successful!")
    return s


def scrape_clubs(s):
    # Try to fetch club directory
    res = s.get("https://www.askfred.net/clubs.json", timeout=15)
    print(f"Clubs status: {res.status_code}")
    print(f"Clubs preview: {res.text[:500]}")


if __name__ == "__main__":
    s = askfred_login()
    if s:
        scrape_clubs(s)
