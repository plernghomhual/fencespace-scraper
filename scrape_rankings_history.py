"""
Captures FIE world rankings for historical seasons into fs_rankings_history.
Skips season/weapon/gender/category combos already scraped unless FORCE mode.
Uses fs_scraper_state to track progress across runs.
"""
import os
import re
import time
from datetime import datetime, timezone

import requests
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORY_START_SEASON = int(os.environ.get("RANKINGS_HISTORY_START_SEASON", "2015"))
HISTORY_END_SEASON = int(os.environ.get("RANKINGS_HISTORY_END_SEASON", "0"))  # 0 = current year
FORCE = os.environ.get("RANKINGS_HISTORY_FORCE", "").lower() in {"1", "true", "yes"}
REQUEST_DELAY = float(os.environ.get("RANKINGS_HISTORY_DELAY", "1.5"))
BATCH_SIZE = 200

STATE_SOURCE = "scrape_rankings_history"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

WEAPON_MAP = {"S": "Sabre", "E": "Epee", "F": "Foil"}
CATEGORY_MAP = {"S": "Senior", "J": "Junior", "C": "Cadet", "V": "Veteran"}

COMBOS = [
    (weapon, gender, category)
    for weapon in WEAPON_MAP
    for gender in ("M", "F")
    for category in CATEGORY_MAP
]


def clean_text(value) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_country(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    country_map = {
        "_AIN": "Russia", "AIN_": "Russia", "AIN": "Russia",
        "USA": "United States", "GBR": "Great Britain",
        "KOR": "South Korea", "HONG KONG, CHINA": "Hong Kong",
        "HONG KONG CHINA": "Hong Kong",
    }
    if key in country_map:
        return country_map[key]
    return text.title() if text else None


def normalize_person_name(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while leading < len(parts) and parts[leading].upper() == parts[leading] and any(c.isalpha() for c in parts[leading]):
        leading += 1
    if 0 < leading < len(parts):
        last = " ".join(parts[:leading]).title()
        first = " ".join(parts[leading:]).title()
        return first if first.lower() == last.lower() else f"{first} {last}"
    trailing = 0
    while trailing < len(parts) and parts[-1 - trailing].upper() == parts[-1 - trailing] and any(c.isalpha() for c in parts[-1 - trailing]):
        trailing += 1
    if 0 < trailing < len(parts):
        first = " ".join(parts[:-trailing]).title()
        last = " ".join(parts[-trailing:]).title()
        return first if first.lower() == last.lower() else f"{first} {last}"
    return text.title()


def combo_done_key(season: int, weapon: str, gender: str, category: str) -> str:
    return f"done:{season}:{weapon}:{gender}:{category}"


def load_done_combos() -> set[str]:
    if FORCE:
        return set()
    state = get_state(STATE_SOURCE, "done_combos")
    if isinstance(state, list):
        return set(state)
    return set()


def save_done_combos(done: set[str]) -> None:
    set_state(STATE_SOURCE, "done_combos", sorted(done))


def fetch_rankings_page(session: requests.Session, weapon: str, gender: str, category: str, season: int, page: int) -> list[dict]:
    payload = {
        "weapon": weapon, "gender": gender, "category": category,
        "country": "", "name": "", "page": page,
        "season": str(season),
    }
    for attempt in range(1, 4):
        try:
            res = session.post("https://fie.org/athletes", json=payload, timeout=20)
            if res.status_code in {429, 500, 502, 503, 504}:
                time.sleep(2 ** attempt)
                continue
            res.raise_for_status()
            data = res.json()
            return data.get("allAthletes") or data.get("topFencers") or []
        except Exception as exc:
            print(f"    Page {page} attempt {attempt} failed: {exc}")
            if attempt < 3:
                time.sleep(2 ** attempt)
    return []


def load_fencer_id_map(fie_ids: list[str]) -> dict[str, int]:
    fencer_map: dict[str, int] = {}
    for i in range(0, len(fie_ids), 200):
        batch = fie_ids[i : i + 200]
        data = (
            supabase.table("fs_fencers")
            .select("id,fie_id")
            .in_("fie_id", batch)
            .execute()
            .data
            or []
        )
        for row in data:
            fie_id = str(row["fie_id"]) if row.get("fie_id") is not None else None
            if fie_id and row.get("id"):
                fencer_map.setdefault(fie_id, row["id"])
    return fencer_map


def scrape_season_combo(session: requests.Session, season: int, weapon: str, gender: str, category: str) -> int:
    gender_label = "Women's" if gender == "F" else "Men's"
    db_category = f"{gender_label} {CATEGORY_MAP[category]}"
    db_weapon = WEAPON_MAP[weapon]

    rows = []
    page = 1
    seen: set[str] = set()

    while True:
        athletes = fetch_rankings_page(session, weapon, gender, category, season, page)
        if not athletes:
            break
        for f in athletes:
            fie_id = str(f.get("id") or "").strip()
            if not fie_id or fie_id in seen:
                continue
            seen.add(fie_id)
            points_raw = f.get("points", "0") or "0"
            try:
                points = float(points_raw)
            except Exception:
                points = 0.0
            rows.append({
                "season": season,
                "weapon": db_weapon,
                "gender": gender_label,
                "category": db_category,
                "fie_fencer_id": fie_id,
                "rank": f.get("rank"),
                "points": points,
                "name": normalize_person_name(f.get("name")),
                "country": normalize_country(f.get("country")),
            })
        if len(athletes) < 100:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    if not rows:
        return 0

    fie_ids = [r["fie_fencer_id"] for r in rows]
    fencer_map = load_fencer_id_map(fie_ids)
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        row["fencer_id"] = fencer_map.get(row["fie_fencer_id"])
        row["scraped_at"] = now

    for i in range(0, len(rows), BATCH_SIZE):
        supabase.table("fs_rankings_history").upsert(
            rows[i : i + BATCH_SIZE],
            on_conflict="season,weapon,gender,category,fie_fencer_id",
        ).execute()

    return len(rows)


def scrape_rankings_history():
    print(f"Rankings history scraper starting - {datetime.now(timezone.utc).isoformat()}")
    run_log = ScraperRunLogger("scrape_rankings_history").start()

    current_year = datetime.now(timezone.utc).year
    end_season = HISTORY_END_SEASON if HISTORY_END_SEASON else current_year
    seasons = list(range(HISTORY_START_SEASON, end_season + 1))

    done_combos = load_done_combos()
    print(f"Seasons {HISTORY_START_SEASON}–{end_season} × {len(COMBOS)} combos; {len(done_combos)} already done")

    session = requests.Session()
    session.headers.update(HEADERS)

    total_written = 0
    total_skipped = 0
    total_failed = 0

    for season in seasons:
        for weapon, gender, category in COMBOS:
            key = combo_done_key(season, weapon, gender, category)
            if key in done_combos:
                total_skipped += 1
                continue

            gender_label = "Women's" if gender == "F" else "Men's"
            label = f"{season} {gender_label} {CATEGORY_MAP[category]} {WEAPON_MAP[weapon]}"
            print(f"  {label}")
            try:
                count = scrape_season_combo(session, season, weapon, gender, category)
                print(f"    Wrote {count} rows")
                total_written += count
                done_combos.add(key)
                save_done_combos(done_combos)
            except Exception as exc:
                print(f"    Failed: {exc}")
                total_failed += 1

            time.sleep(REQUEST_DELAY)

    run_log.complete(written=total_written, failed=total_failed, skipped=total_skipped)
    print(
        f"\nDone - written={total_written}, skipped={total_skipped}, failed={total_failed}"
    )


if __name__ == "__main__":
    scrape_rankings_history()
