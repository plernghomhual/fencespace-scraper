import os
import time
from datetime import UTC, datetime, timezone

import requests

from run_logger import ScraperRunLogger
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}


def scrape_usafencing_clubs():
    print(f"USA Fencing club scraper starting — {datetime.now(UTC).isoformat()}")
    run_log = ScraperRunLogger("scrape_clubs").start()

    page = 1
    total_scraped = 0
    total_failed = 0
    max_pages = 100  # safety cap

    try:
        while page <= max_pages:
            # Fetch page — separate try so an HTTP error doesn't abort the whole run
            try:
                res = requests.get(
                    "https://member.usafencing.org/clubs",
                    params={
                        "q": "",
                        "division": "",
                        "state": "",
                        "club_type": "",
                        "sort": "name",
                        "page": page,
                        "perPage": 50
                    },
                    headers=HEADERS,
                    timeout=15
                )
            except Exception as e:
                print(f"  Page {page} — network error: {e}")
                total_failed += 1
                break

            if res.status_code != 200:
                print(f"  Page {page} — HTTP {res.status_code}, stopping")
                break

            try:
                data = res.json()
            except Exception as e:
                print(f"  Page {page} — JSON parse error: {e}")
                total_failed += 1
                break

            index_data = data.get("indexData", {})
            models = index_data.get("models", [])
            pages = index_data.get("pages", {})

            if page == 1:
                total_count = pages.get("total") or pages.get("count") or "unknown"
                print(f"  Total clubs reported by API: {total_count}")

            if not models:
                print(f"  Page {page} — no models returned, stopping")
                break

            rows = []
            for c in models:
                # Skip clubs with no ID — can't upsert without conflict target
                if not c.get("id"):
                    continue
                addr = c.get("publicAddress", {}) or {}
                division = c.get("division", {}) or {}
                region = c.get("region", {}) or {}

                rows.append({
                    "name": (c.get("name") or "").strip(),
                    "country": "USA",
                    "city": addr.get("city", ""),
                    "state": addr.get("state", ""),
                    "zip": addr.get("zip", ""),
                    "address": addr.get("formatted_address", ""),
                    "website": c.get("website", ""),
                    "instagram": c.get("instagram", ""),
                    "twitter": c.get("twitter", ""),
                    "facebook": c.get("facebook", ""),
                    "logo_url": c.get("default_logo", ""),
                    "division": division.get("label", ""),
                    "region": region.get("label", ""),
                    "usafencing_id": c.get("id"),
                    "usafencing_slug": c.get("slug", ""),
                    "is_active": not c.get("inactive", False),
                    "updated_at": datetime.now(UTC).isoformat()
                })

            # Upsert on usafencing_id — separate try so a DB error doesn't abort pagination
            if rows:
                try:
                    for i in range(0, len(rows), 50):
                        supabase.table("fs_clubs").upsert(
                            rows[i:i+50],
                            on_conflict="usafencing_id"
                        ).execute()
                    total_scraped += len(rows)
                except Exception as e:
                    print(f"  Page {page} — upsert error: {e}")
                    total_failed += len(rows)

            has_more = pages.get("hasMorePages", False)
            print(f"  Page {page} — {len(rows)} clubs (total so far: {total_scraped}) hasMore: {has_more}")

            if not has_more:
                break

            page += 1
            time.sleep(0.5)

    except Exception as exc:
        run_log.error(str(exc))
        raise

    print(f"\nDone — {total_scraped} clubs scraped across {page} pages, {total_failed} failed")

    result = supabase.table("fs_clubs").select("id", count="exact").eq("country", "USA").execute()
    print(f"DB verification — {result.count} US clubs in fs_clubs")

    run_log.complete(written=total_scraped, failed=total_failed)


if __name__ == "__main__":
    scrape_usafencing_clubs()
