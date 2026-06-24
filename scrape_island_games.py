"""
Island Games and Oceania fencing results scraper.

Probe findings (2026-06-01):
  - islandgames.net redirects to iiga.org. The current IIGA sports/results pages
    and Guernsey 2023 results page list no fencing sport or fencing result links.
  - Olympedia has Olympic and Youth Olympic fencing pages, but no Island Games
    fencing result pages were found.
  - Oceania public result coverage is available through Australian Fencing
    Federation tournament pages such as:
      /tournament/2019-oceania-open-championships/
    Event pages contain a "Final Results" heading followed by an HTML table.

Source IDs:
  - island_games:{edition_id}:{event_code}
  - oceania:{year}:{event_code}
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "island_games_oceania"
ISLAND_GAMES_BASE = "https://www.iiga.org"
ISLAND_GAMES_PROBE_URLS = [
    "https://islandgames.net/",
    "https://www.iiga.org/results.html",
    "https://results.guernsey2023.gg/",
]
OCEANIA_RESULTS_URL = "https://www.ausfencing.org/results/"
OCEANIA_BASE = "https://www.ausfencing.org"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

OCEANIA_SEED_TOURNAMENTS = [
    "https://www.ausfencing.org/tournament/2022-oceania-cadet-championships/",
    "https://www.ausfencing.org/tournament/2019-oceania-open-championships/",
    "https://www.ausfencing.org/tournament/2018-oceania-junior-championships/",
    "https://www.ausfencing.org/tournament/2015-oceania-open-championships/",
    "https://www.ausfencing.org/tournament/2014-oceania-veteran-championships/",
    "https://www.ausfencing.org/tournament/2014-oceania-junior-championships/",
    "https://www.ausfencing.org/tournament/2010-oceania-veteran-championships/",
]

_GENERIC_HEADINGS = {
    "results",
    "final results",
    "results after poules",
    "poules",
    "tableau",
    "fencers",
}


def _clean_text(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _plain(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text


def slugify(text: str) -> str:
    text = _plain(_clean_text(text)).lower()
    text = text.replace("'", "")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    return slugify(path.rsplit("/", 1)[-1])


def _extract_year(text: str) -> str | None:
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else None


def _infer_category(text: str, default: str | None = None) -> str:
    plain = _plain(text).lower()
    under = re.search(r"\b(?:u|under)\s*(\d{2})\b", plain)
    if under:
        return f"U{under.group(1)}"
    if "cadet" in plain:
        return "Cadet"
    if "junior" in plain:
        return "Junior"
    if "veteran" in plain or "vets" in plain:
        return "Veteran"
    if "senior" in plain or "open" in plain:
        return "Senior"
    return default or "Senior"


def classify_event(event_name: str, default_category: str | None = None) -> dict:
    """Classify a fencing event label into weapon, gender, team, and category."""
    plain = _plain(event_name).lower()

    weapon = None
    if re.search(r"\bepee\b", plain):
        weapon = "Epee"
    elif re.search(r"\bfoil\b", plain):
        weapon = "Foil"
    elif re.search(r"\bsabre\b|\bsaber\b", plain):
        weapon = "Sabre"

    gender = None
    if re.search(r"\bwomen\b|\bwoman\b|\bwomens\b|\bfemale\b|\bgirls?\b", plain):
        gender = "Women"
    elif re.search(r"\bmen\b|\bmens\b|\bmale\b|\bboys?\b", plain):
        gender = "Men"

    return {
        "weapon": weapon,
        "gender": gender,
        "team": bool(re.search(r"\bteams?\b", plain)),
        "category": _infer_category(event_name, default=default_category),
    }


def _parse_rank(raw: str) -> int | None:
    text = _clean_text(raw)
    if not text or text.upper() in {"DNS", "DNF", "DQ", "DSQ", "BYE"}:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _parse_medal(raw: str | None, rank: int | None) -> str | None:
    text = _clean_text(raw).lower()
    if text in {"gold", "g"}:
        return "Gold"
    if text in {"silver", "s"}:
        return "Silver"
    if text in {"bronze", "b"}:
        return "Bronze"
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _smart_title(text: str) -> str:
    words = []
    for word in _clean_text(text).split():
        words.append(word.title() if word.isupper() else word)
    return " ".join(words)


def _normalize_name(text: str) -> str:
    text = _clean_text(text)
    if "," not in text:
        return _smart_title(text)
    surname, given = text.split(",", 1)
    return _clean_text(f"{_smart_title(given)} {_smart_title(surname)}")


def _normalize_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _plain(_clean_text(text)).lower())


def _column_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, header in enumerate(headers):
        key = _normalize_header(header)
        if key in {"rank", "position", "pos", "place"} and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in {"name", "competitor", "athlete", "fencer", "team"} and "name" not in mapping:
            mapping["name"] = idx
        elif key in {"country", "statecountry", "island", "nation", "noc"} and "country" not in mapping:
            mapping["country"] = idx
        elif key in {"medal", "medals"} and "medal" not in mapping:
            mapping["medal"] = idx
        elif key in {"category", "age", "agecategory", "class"} and "category" not in mapping:
            mapping["category"] = idx
    return mapping


def _table_rows(table) -> list[list[str]]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    return rows


def _parse_result_table(table, classification: dict) -> list[dict]:
    rows = []
    col_map: dict[str, int] = {}

    for cells in _table_rows(table):
        detected = _column_map(cells)
        if {"rank", "name"}.issubset(detected):
            col_map = detected
            continue
        if not col_map or "rank" not in col_map or "name" not in col_map:
            continue

        needed = max(col_map.values())
        if len(cells) <= needed:
            continue

        rank = _parse_rank(cells[col_map["rank"]])
        name = _normalize_name(cells[col_map["name"]])
        if rank is None or not name:
            continue

        country = cells[col_map["country"]] if "country" in col_map else None
        category = cells[col_map["category"]] if "category" in col_map else classification["category"]
        medal_raw = cells[col_map["medal"]] if "medal" in col_map else None

        rows.append(
            {
                "rank": rank,
                "name": name,
                "country": _clean_text(country) or None,
                "medal": _parse_medal(medal_raw, rank),
                "weapon": classification["weapon"],
                "gender": classification["gender"],
                "category": _infer_category(category or "", default=classification["category"]),
            }
        )
    return rows


def _event_heading_before_table(table) -> str:
    heading = table.find_previous(["h1", "h2", "h3", "h4", "h5", "caption"])
    while heading is not None:
        text = _clean_text(heading.get_text(" ", strip=True))
        if text and text.lower() not in _GENERIC_HEADINGS:
            return text
        heading = heading.find_previous(["h1", "h2", "h3", "h4", "h5", "caption"])
    return ""


def parse_island_games_result_page(
    html: str,
    *,
    edition_id: str,
    edition_name: str | None = None,
    page_url: str | None = None,
) -> list[dict]:
    """Parse a structured Island Games fencing result page if one is found."""
    soup = BeautifulSoup(html or "", "html.parser")
    page_text = soup.get_text(" ", strip=True)
    if not re.search(r"\bfencing\b|\bfoil\b|\bepee\b|\bepée\b|\bsabre\b|\bsaber\b", _plain(page_text), re.I):
        return []

    events = []
    seen: set[str] = set()
    for table in soup.find_all("table"):
        event_name = _event_heading_before_table(table)
        classification = classify_event(event_name)
        if not classification["weapon"] or not classification["gender"]:
            continue
        rows = _parse_result_table(table, classification)
        if not rows:
            continue
        event_code = slugify(event_name)
        if event_code in seen:
            continue
        seen.add(event_code)
        year = _extract_year(" ".join(filter(None, [edition_name, page_text])))
        events.append(
            {
                "source": "island_games",
                "source_id": f"island_games:{edition_id}:{event_code}",
                "edition_id": edition_id,
                "edition_name": edition_name,
                "year": year,
                "event_code": event_code,
                "event_name": event_name,
                "url": page_url,
                "weapon": classification["weapon"],
                "gender": classification["gender"],
                "team": classification["team"],
                "category": classification["category"],
                "rows": rows,
            }
        )
    return events


def parse_oceania_tournament_page(html: str, *, page_url: str) -> list[dict]:
    """Parse an AFF Oceania tournament page into event page descriptors."""
    soup = BeautifulSoup(html or "", "html.parser")
    title = _clean_text((soup.find("h1") or soup.find("title") or soup).get_text(" ", strip=True))
    year = _extract_year(title) or _extract_year(page_url)
    default_category = _infer_category(title)
    events = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        event_name = _clean_text(link.get_text(" ", strip=True))
        href = link["href"]
        if "/competitions/" not in href:
            continue
        classification = classify_event(event_name, default_category=default_category)
        if not year or not classification["weapon"] or not classification["gender"]:
            continue

        url = urljoin(page_url, href)
        event_code = _slug_from_url(url) or slugify(event_name)
        if event_code in seen:
            continue
        seen.add(event_code)

        events.append(
            {
                "source": "oceania",
                "source_id": f"oceania:{year}:{event_code}",
                "year": year,
                "event_code": event_code,
                "event_name": event_name,
                "url": url,
                "weapon": classification["weapon"],
                "gender": classification["gender"],
                "team": classification["team"],
                "category": classification["category"],
                "rows": [],
            }
        )
    return events


def _find_final_results_table(soup: BeautifulSoup):
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        if _clean_text(heading.get_text(" ", strip=True)).lower() == "final results":
            return heading.find_next("table")
    return None


def parse_oceania_result_page(
    html: str,
    *,
    year: str,
    event_code: str,
    event_name: str,
    category: str | None = None,
    url: str | None = None,
) -> dict | None:
    """Parse an AFF Oceania event page, using only the final placing table."""
    classification = classify_event(event_name, default_category=category)
    if not classification["weapon"] or not classification["gender"]:
        return None

    soup = BeautifulSoup(html or "", "html.parser")
    table = _find_final_results_table(soup)
    if not table:
        return None

    rows = _parse_result_table(table, classification)
    if not rows:
        return None

    return {
        "source": "oceania",
        "source_id": f"oceania:{year}:{event_code}",
        "year": str(year),
        "event_code": event_code,
        "event_name": event_name,
        "url": url,
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "team": classification["team"],
        "category": classification["category"],
        "rows": rows,
    }


def _get(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep((2**attempt) * (5 if response.status_code == 429 else 1))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2**attempt)
    return None


def discover_oceania_tournaments() -> list[str]:
    html = _get(OCEANIA_RESULTS_URL)
    if not html:
        return OCEANIA_SEED_TOURNAMENTS

    soup = BeautifulSoup(html, "html.parser")
    urls = []
    seen = set()
    for link in soup.find_all("a", href=True):
        text = _clean_text(link.get_text(" ", strip=True))
        href = link["href"]
        if "/tournament/" not in href:
            continue
        if not re.search(r"\boceania\b.*\bchampionships?\b", text, re.I):
            continue
        url = urljoin(OCEANIA_RESULTS_URL, href)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls or OCEANIA_SEED_TOURNAMENTS


def fetch_oceania_events() -> list[dict]:
    events = []
    for tournament_url in discover_oceania_tournaments():
        html = _get(tournament_url)
        if not html:
            continue
        for event in parse_oceania_tournament_page(html, page_url=tournament_url):
            detail_html = _get(event["url"])
            if not detail_html:
                continue
            parsed = parse_oceania_result_page(
                detail_html,
                year=event["year"],
                event_code=event["event_code"],
                event_name=event["event_name"],
                category=event["category"],
                url=event["url"],
            )
            if parsed:
                events.append(parsed)
            time.sleep(REQUEST_DELAY)
        time.sleep(REQUEST_DELAY)
    return events


def _edition_id_from_url(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    slug = _slug_from_url(url)
    return slug or host.split(".")[0] or "unknown"


def fetch_island_games_events() -> list[dict]:
    """Probe official Island Games pages; returns [] while no fencing pages exist."""
    events = []
    for url in ISLAND_GAMES_PROBE_URLS:
        html = _get(url)
        if not html:
            continue
        events.extend(
            parse_island_games_result_page(
                html,
                edition_id=_edition_id_from_url(url),
                edition_name=None,
                page_url=url,
            )
        )
        time.sleep(REQUEST_DELAY)
    return events


def _match_fencer(name: str, country: str | None):
    try:
        query = supabase.table("fs_fencers").select("id").ilike("name", name)  # type: ignore[union-attr]
        if country:
            query = query.eq("country", country)
        rows = query.limit(2).execute().data
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_tournament(event: dict):
    row = {
        "source_id": event["source_id"],
        "name": f"{event.get('edition_name') or event.get('year') or 'Island/Oceania'} - {event['event_name']}",
        "season": event.get("year"),
        "type": event["source"],
        "weapon": event["weapon"],
        "gender": event["gender"],
        "category": event.get("category") or "Senior",
        "country": None,
        "has_results": bool(event.get("rows")),
        "metadata": {
            "source": event["source"],
            "event_code": event["event_code"],
            "event_name": event["event_name"],
            "team": event.get("team", False),
            "url": event.get("url"),
            "edition_id": event.get("edition_id"),
            "edition_name": event.get("edition_name"),
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def upsert_results(tournament_id, event: dict) -> int:
    db_rows = []
    for row in event.get("rows", []):
        if row["rank"] is None:
            continue
        fencer_id = None
        if not event.get("team"):
            fencer_id = _match_fencer(row["name"], row.get("country"))
        db_rows.append(
            {
                "tournament_id": tournament_id,
                "name": row["name"],
                "nationality": row.get("country"),
                "rank": row["rank"],
                "medal": row.get("medal"),
                "fencer_id": fencer_id,
                "metadata": {
                    "source_id": event["source_id"],
                    "event_code": event["event_code"],
                    "weapon": row.get("weapon"),
                    "gender": row.get("gender"),
                    "category": row.get("category"),
                },
            }
        )

    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for idx in range(0, len(db_rows), 100):
        batch = db_rows[idx : idx + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def import_events(events: list[dict], done_ids: set[str]) -> tuple[int, int, int]:
    written = failed = skipped = 0
    for event in events:
        source_id = event["source_id"]
        if source_id in done_ids:
            skipped += 1
            continue
        if not event.get("rows"):
            skipped += 1
            continue

        tournament_id = upsert_tournament(event)
        if not tournament_id:
            failed += 1
            continue

        count = upsert_results(tournament_id, event)
        if count == 0:
            failed += 1
            continue

        done_ids.add(source_id)
        set_state(SOURCE, "done_source_ids", sorted(done_ids))
        written += 1
    return written, failed, skipped


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_island_games").start()
    try:
        print(f"Island Games/Oceania scraper starting - {datetime.now(UTC).isoformat()}")
        done_ids = set(get_state(SOURCE, "done_source_ids") or [])

        island_events = fetch_island_games_events()
        oceania_events = fetch_oceania_events()
        events = island_events + oceania_events
        print(f"  Island Games events: {len(island_events)}")
        print(f"  Oceania events: {len(oceania_events)}")

        written, failed, skipped = import_events(events, done_ids)
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
