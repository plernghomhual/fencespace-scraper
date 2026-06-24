"""
scrape_fed_canada.py — Canadian Fencing Federation (CFF / Escrime Canada) rankings scraper.

Data source: https://rankingapi.fencing.ca/api/rankings/published
  — A public REST API (no auth required) backing the React SPA at ranking.fencing.ca.
  — Returns all published rankings in a single response.
  — Each entry has: weapon (epee/fleuret/sabre), gender (M/F), ageCategory.code,
    and a ranks[] array of {position, points, player{firstName, lastName, club, ...}}.

Weapon mapping:
  epee    -> Epee
  fleuret -> Foil  (French name used by CFF)
  sabre   -> Sabre

Gender mapping: M -> Men, F -> Women
Category codes: senior, junior, cadet (and veteran variants — not included in RANKING_COMBOS)
"""

import time
from datetime import UTC, datetime, timezone

import requests

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from season_utils import season_to_string

SOURCE = "cff_canada"
COUNTRY = "CAN"
REQUEST_DELAY = 0.0  # single-request API — no per-page delay needed
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "application/json",
    "Origin": "https://ranking.fencing.ca",
    "Referer": "https://ranking.fencing.ca/",
}

API_URL = "https://rankingapi.fencing.ca/api/rankings/published"

# CFF uses "fleuret" for Foil and gender codes M/F
_WEAPON_MAP = {
    "epee": "Epee",
    "fleuret": "Foil",
    "sabre": "Sabre",
}
_GENDER_MAP = {
    "M": "Men",
    "F": "Women",
}

RANKING_COMBOS = {
    ("Foil",  "Men",   "Senior"),
    ("Foil",  "Women", "Senior"),
    ("Epee",  "Men",   "Senior"),
    ("Epee",  "Women", "Senior"),
    ("Sabre", "Men",   "Senior"),
    ("Sabre", "Women", "Senior"),
    ("Foil",  "Men",   "Junior"),
    ("Foil",  "Women", "Junior"),
    ("Epee",  "Men",   "Junior"),
    ("Epee",  "Women", "Junior"),
    ("Sabre", "Men",   "Junior"),
    ("Sabre", "Women", "Junior"),
}


def parse_cff_rankings(data: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    """
    Parse the JSON response from /api/rankings/published.

    Returns a dict keyed by (weapon, gender, category) tuples matching RANKING_COMBOS.
    Each value is a list of dicts: {rank, name, club, points}.
    """
    results: dict[tuple[str, str, str], list[dict]] = {}

    for item in data:
        raw_weapon = (item.get("weapon") or "").lower().strip()
        raw_gender = (item.get("gender") or "").upper().strip()
        age_cat = item.get("ageCategory") or {}
        if isinstance(age_cat, dict):
            raw_category = (age_cat.get("code") or "").lower().strip()
        else:
            raw_category = str(age_cat).lower().strip()

        weapon = _WEAPON_MAP.get(raw_weapon)
        gender = _GENDER_MAP.get(raw_gender)
        # Normalize category: "senior " -> "Senior", "junior" -> "Junior"
        if raw_category == "senior":
            category = "Senior"
        elif raw_category == "junior":
            category = "Junior"
        else:
            category = None

        if not weapon or not gender or not category:
            continue

        combo = (weapon, gender, category)
        if combo not in RANKING_COMBOS:
            continue

        rows = []
        for rank_entry in item.get("ranks", []):
            player = rank_entry.get("player") or {}
            first = (player.get("firstName") or "").strip()
            last = (player.get("lastName") or "").strip()
            # Capitalize each word for consistent name formatting
            name = f"{first.title()} {last.title()}".strip()
            if not name or name == " ":
                continue

            position = rank_entry.get("position")
            try:
                rank = int(position)
            except (TypeError, ValueError):
                continue

            points_raw = rank_entry.get("points")
            try:
                points = float(points_raw) if points_raw is not None else None
            except (TypeError, ValueError):
                points = None

            club_raw = (player.get("club") or "").strip() or None

            rows.append({
                "rank": rank,
                "name": name,
                "club": club_raw,
                "points": points,
            })

        results[combo] = rows

    return results


def fetch_all_rankings() -> list[dict] | None:
    """Fetch all published rankings from the CFF API in one request."""
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [cff] Fetch failed: {exc}")
        return None


def current_season() -> str:
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def main():
    run_log = ScraperRunLogger("scrape_fed_canada").start()
    season = current_season()
    print(f"CFF Canada rankings — season {season}")
    total_written = total_failed = 0

    raw_data = fetch_all_rankings()
    if not raw_data:
        run_log.error("Failed to fetch CFF rankings API")
        print("FAILED — could not reach CFF API")
        return

    parsed_by_combo = parse_cff_rankings(raw_data)

    for weapon, gender, category in sorted(RANKING_COMBOS):
        combo = (weapon, gender, category)
        print(f"  {weapon} {gender} {category}...")
        parsed = parsed_by_combo.get(combo)

        if not parsed:
            print(f"    No data found for combo")
            total_failed += 1
            continue

        rows = [
            build_ranking_row(
                source=SOURCE,
                season=season,
                weapon=weapon,
                gender=gender,
                category=category,
                rank=r["rank"],
                name=r["name"],
                country=COUNTRY,
                club=r.get("club"),
                points=r.get("points"),
            )
            for r in parsed
        ]
        n = write_rankings(rows, source=SOURCE, season=season)
        print(f"    Written {n} rows")
        total_written += n

    run_log.complete(written=total_written, failed=total_failed)
    print(f"Done — written={total_written}, failed={total_failed}")


if __name__ == "__main__":
    main()
