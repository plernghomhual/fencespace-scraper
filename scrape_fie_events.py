"""
Forward-looking FIE event discovery.
Fetches upcoming and current-season events not yet in fs_tournaments,
covering the current season and the next two seasons.
"""
import calendar
import os
import re
import time
from datetime import datetime, timezone

import requests
from supabase import create_client

from run_logger import ScraperRunLogger
from scripts.rate_limiter import RateLimiter as _RateLimiter

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

LOOK_AHEAD_YEARS = int(os.environ.get("FIE_EVENTS_LOOK_AHEAD", "2"))
REQUEST_DELAY = float(os.environ.get("FIE_EVENTS_DELAY", "0.5"))
_fie_limiter = _RateLimiter(default_rps=2.0, jitter=0.2, backoff=5.0)

COMP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}


def clean_text(value) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_country(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"\s+", " ", text.upper().replace(".", ""))
    country_map = {
        "_AIN": "Russia", "AIN_": "Russia", "AIN": "Russia",
        "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
        "FIE": "FIE",
        "USA": "United States", "US": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "GBR": "Great Britain", "GREAT BRITAIN": "Great Britain",
        "KOREA": "South Korea", "KOR": "South Korea",
        "HONG KONG, CHINA": "Hong Kong", "HONG KONG CHINA": "Hong Kong",
        "MACAO, CHINA": "Macau", "MACAO CHINA": "Macau",
        "TURKIYE": "Turkey", "TÜRKIYE": "Turkey", "TÜRKİYE": "Turkey",
        "COTE D'IVOIRE": "Côte d'Ivoire", "COTE DIVOIRE": "Côte d'Ivoire",
    }
    return country_map.get(key, text.title())


def parse_date(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def normalize_date_range(start_date, end_date):
    if start_date and end_date and end_date < start_date:
        return start_date, start_date
    return start_date, end_date


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)"})
    try:
        s.get("https://fie.org/competitions", timeout=15)
    except Exception:
        pass
    return s


def fetch_month(session: requests.Session, year: int, month: int, status: str) -> list[dict] | None:
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{year}-{month:02d}-01"
    to_date = f"{year}-{month:02d}-{last_day:02d}"
    payload = {
        "name": "", "status": status, "gender": [], "weapon": [], "type": [],
        "season": year, "level": "", "competitionCategory": "",
        "fromDate": from_date, "toDate": to_date, "fetchPage": 1,
    }
    for attempt in range(1, 3):
        try:
            res = session.post(
                "https://fie.org/competitions/search",
                headers=COMP_HEADERS,
                json=payload,
                timeout=20,
            )
            if res.status_code == 200 and res.text.strip():
                return res.json().get("items", [])
        except Exception as exc:
            print(f"  Fetch {year}-{month:02d} attempt {attempt} failed: {exc}")
            if attempt < 2:
                time.sleep(2)
    return None


def competition_row(c: dict) -> dict:
    start_date, end_date = normalize_date_range(
        parse_date(c.get("startDate")),
        parse_date(c.get("endDate")),
    )
    return {
        "fie_id": c.get("competitionId"),
        "season": c.get("season"),
        "name": c.get("name"),
        "location": c.get("location"),
        "country": normalize_country(c.get("country")),
        "federation": c.get("federation"),
        "flag": c.get("flag"),
        "start_date": start_date,
        "end_date": end_date,
        "weapon": c.get("weapon"),
        "weapons": c.get("weapons", []),
        "gender": c.get("gender"),
        "category": c.get("category"),
        "categories": c.get("categories", []),
        "type": c.get("type"),
        "has_results": bool(c.get("hasResults")),
        "is_sub_competition": bool(c.get("isSubCompetition")),
        "is_link": bool(c.get("isLink")),
    }


def scrape_fie_events():
    print(f"FIE events discovery starting - {datetime.now(timezone.utc).isoformat()}")
    run_log = ScraperRunLogger("scrape_fie_events").start()

    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    session = make_session()
    all_items: dict[str, dict] = {}

    for year in range(current_year, current_year + LOOK_AHEAD_YEARS + 1):
        print(f"Fetching season {year}...")
        for month in range(1, 13):
            if year == current_year and month < current_month:
                continue
            status = "" if year > current_year or month >= current_month else "passed"
            items = fetch_month(session, year, month, status)
            if items is None:
                session = make_session()
                time.sleep(1)
                items = fetch_month(session, year, month, status) or []
            for item in items:
                comp_id = item.get("competitionId")
                if comp_id:
                    all_items[str(comp_id)] = item
            if items:
                print(f"  {year}-{month:02d}: {len(items)} items")
            _fie_limiter.wait("fie.org")

    print(f"Fetched {len(all_items)} unique FIE competitions")
    if not all_items:
        run_log.complete(written=0)
        return

    rows = [competition_row(c) for c in all_items.values()]

    # Load existing fie_ids to count new vs updated
    existing_fie_ids: set[str] = set()
    for i in range(0, len(rows), 500):
        batch_ids = [r["fie_id"] for r in rows[i : i + 500] if r.get("fie_id")]
        data = (
            supabase.table("fs_tournaments")
            .select("fie_id")
            .in_("fie_id", batch_ids)
            .execute()
            .data
            or []
        )
        for row in data:
            if row.get("fie_id"):
                existing_fie_ids.add(str(row["fie_id"]))

    new_count = sum(1 for r in rows if str(r.get("fie_id", "")) not in existing_fie_ids)

    for i in range(0, len(rows), 100):
        supabase.table("fs_tournaments").upsert(
            rows[i : i + 100], on_conflict="fie_id"
        ).execute()

    run_log.complete(written=len(rows), metadata={"new": new_count, "updated": len(rows) - new_count})
    print(f"Done - upserted {len(rows)} competitions ({new_count} new, {len(rows) - new_count} updated)")


if __name__ == "__main__":
    scrape_fie_events()
