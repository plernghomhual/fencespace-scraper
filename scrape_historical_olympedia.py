"""Historical pre-2000 Olympedia fencing result crawler.

Probe evidence from this repo (2026-06-01/02):
  - Olympedia fencing index: /sports/FEN
  - Edition fencing pages: /editions/{edition_id}/sports/FEN
  - Result pages: /results/{result_id}

The crawler is intentionally conservative: individual rows are written only
when a fencer can be matched explicitly by FIE ID, Olympedia athlete ID, or a
unique canonical name+country identity. Unmatched rows are logged for later
reconciliation instead of creating null-fencer result orphans.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

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


SOURCE = "historical_olympedia"
OLYMPEDIA_BASE = "https://www.olympedia.org"
SPORT_URL = f"{OLYMPEDIA_BASE}/sports/FEN"
REQUEST_DELAY = 2.0
UNMATCHED_LOG_PATH = Path("historical_olympedia_unmatched.log")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MEDALS_BY_RANK = {1: "Gold", 2: "Silver", 3: "Bronze"}
MEDALS = {"Gold", "Silver", "Bronze"}
HISTORICAL_COUNTRY_CODES = {
    "ANZ",
    "BOH",
    "EUN",
    "FRG",
    "GDR",
    "TCH",
    "URS",
    "YUG",
}

COUNTRY_ALIASES = {
    "australasia": "ANZ",
    "bohemia": "BOH",
    "czech republic": "CZE",
    "czechoslovakia": "TCH",
    "east germany": "GDR",
    "france": "FRA",
    "germany": "GER",
    "great britain": "GBR",
    "hungary": "HUN",
    "italy": "ITA",
    "poland": "POL",
    "roc": "ROC",
    "russia": "RUS",
    "russian federation": "RUS",
    "soviet union": "URS",
    "unified team": "EUN",
    "united states": "USA",
    "united states of america": "USA",
    "ussr": "URS",
    "west germany": "FRG",
    "yugoslavia": "YUG",
}

WEAPON_PATTERNS = [
    (re.compile(r"\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen'?s\b|\bfemale\b|\bgirls?\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen'?s\b|\bmale\b|\bboys?\b", re.I), "Men"),
    (re.compile(r"\bmixed\b", re.I), "Mixed"),
]


def clean_text(value: Any) -> str:
    text = html.unescape("" if value is None else str(value))
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def ascii_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def canonical_name_key(value: Any) -> str:
    text = ascii_key(value).casefold()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _extract_year(value: str | None) -> int | None:
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", value or "")
    return int(match.group(1)) if match else None


def _rank_to_int(value: Any, previous_rank: int | None = None) -> int | None:
    text = clean_text(value)
    if not text:
        return previous_rank
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return MEDALS_BY_RANK.get(rank)


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    upper = text.upper()
    if re.fullmatch(r"[A-Z0-9]{3}", upper):
        return upper
    return COUNTRY_ALIASES.get(canonical_name_key(text))


def _country_from_cell(cell) -> tuple[str | None, str | None]:
    country_name = clean_text(cell.get_text(" ")) if cell else None
    country_code = None
    if cell:
        link = cell.find("a", href=re.compile(r"/countries/[A-Z0-9]{3}"))
        if link:
            match = re.search(r"/countries/([A-Z0-9]{3})", link.get("href", ""))
            if match:
                country_code = match.group(1)
    return country_code or normalize_country(country_name), country_name or country_code


def classify_event(event_name: str) -> dict[str, Any]:
    key = ascii_key(event_name)
    weapon = next((weapon for pattern, weapon in WEAPON_PATTERNS if pattern.search(key)), None)
    gender = next((gender for pattern, gender in GENDER_PATTERNS if pattern.search(key)), None)
    team = bool(re.search(r"\bteam\b|\bteams\b", key, re.I))
    return {"weapon": weapon, "gender": gender, "team": team, "category": "Senior"}


def parse_sport_index(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    editions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=re.compile(r"^/editions/\d+/sports/FEN$")):
        href = link.get("href", "")
        match = re.search(r"/editions/(\d+)/sports/FEN", href)
        if not match:
            continue
        edition_id = match.group(1)
        if edition_id in seen:
            continue

        row = link.find_parent("tr")
        edition_name = None
        if row:
            edition_link = row.find("a", href=re.compile(rf"^/editions/{edition_id}$"))
            edition_name = clean_text(edition_link.get_text(" ")) if edition_link else None
        edition_name = edition_name or clean_text(link.get_text(" "))
        row_text = clean_text(row.get_text(" ")) if row else edition_name
        year = _extract_year(edition_name) or _extract_year(row_text)
        if not year or year >= 2000:
            continue

        seen.add(edition_id)
        editions.append(
            {
                "edition_id": edition_id,
                "edition_name": edition_name,
                "year": year,
                "url": urljoin(OLYMPEDIA_BASE, href),
            }
        )
    return editions


def parse_edition_events(html_text: str, edition: dict[str, Any]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    events: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=re.compile(r"^/results/\d+$")):
        href = link.get("href", "")
        match = re.search(r"/results/(\d+)", href)
        if not match:
            continue
        result_id = match.group(1)
        if result_id in seen:
            continue

        event_name = clean_text(link.get_text(" "))
        classification = classify_event(event_name)
        if not classification["weapon"] or not classification["gender"]:
            continue

        row = link.find_parent("tr")
        cells = row.find_all(["td", "th"]) if row else []
        event_date = None
        if len(cells) > 1:
            event_date = clean_text(cells[1].get_text(" ")) or None

        seen.add(result_id)
        source_url = urljoin(OLYMPEDIA_BASE, href)
        source_id = f"olympedia:{edition['edition_id']}:{result_id}"
        events.append(
            {
                "source_id": source_id,
                "result_id": result_id,
                "edition_id": edition["edition_id"],
                "edition_name": edition["edition_name"],
                "year": edition["year"],
                "event_name": event_name,
                "event": event_name,
                "tournament": f"{edition['edition_name']} - {event_name}",
                "date": event_date,
                "classification": classification,
                "source_url": source_url,
                "metadata": {
                    "source": SOURCE,
                    "edition_id": edition["edition_id"],
                    "edition_name": edition["edition_name"],
                    "result_id": result_id,
                    "source_url": source_url,
                    "team": classification["team"],
                },
            }
        )
    return events


def _header_map(cells) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        label = canonical_name_key(cell.get_text(" "))
        if any(token in label for token in ("rank", "pos", "place")):
            mapping.setdefault("rank", idx)
        elif any(token in label for token in ("competitor", "athlete", "fencer", "team", "name")):
            mapping.setdefault("name", idx)
        elif any(token in label for token in ("noc", "country", "nation")):
            mapping.setdefault("country", idx)
        elif "medal" in label:
            mapping.setdefault("medal", idx)
    return mapping


def _candidate_result_tables(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        classes = set(table.get("class") or [])
        if "biodata" in classes:
            continue
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = rows[0].find_all(["td", "th"])
        mapping = _header_map(header_cells)
        if {"rank", "name", "country"}.issubset(mapping):
            yield table, mapping
            continue
        if len(header_cells) >= 3 and ("table" in classes or "table-striped" in classes):
            yield table, {"rank": 0, "name": 1, "country": 2, "medal": 3}


def parse_result_rows(html_text: str, event: dict[str, Any]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    team = bool((event.get("classification") or {}).get("team"))

    for table, mapping in _candidate_result_tables(soup):
        rows = table.find_all("tr")
        result_rows: list[dict[str, Any]] = []
        previous_rank: int | None = None
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells or len(cells) <= max(mapping.values()):
                continue

            medal = None
            if "medal" in mapping and mapping["medal"] < len(cells):
                medal_text = clean_text(cells[mapping["medal"]].get_text(" "))
                medal = medal_text if medal_text in MEDALS else None

            rank = _rank_to_int(cells[mapping["rank"]].get_text(" "), previous_rank)
            if rank is None:
                continue
            previous_rank = rank

            name_cell = cells[mapping["name"]]
            name = clean_text(name_cell.get_text(" "))
            if not name:
                continue

            athlete_id = None
            athlete_link = name_cell.find("a", href=re.compile(r"/athletes/\d+"))
            if athlete_link:
                match = re.search(r"/athletes/(\d+)", athlete_link.get("href", ""))
                athlete_id = match.group(1) if match else None

            country_code, country_name = _country_from_cell(cells[mapping["country"]])
            if team and country_name == country_code:
                country_name = name
            medal = medal or _medal_for_rank(rank)
            result_rows.append(
                {
                    "rank": rank,
                    "medal": medal,
                    "name": name,
                    "country": country_code,
                    "country_name": country_name,
                    "team": team,
                    "athlete_id": athlete_id,
                    "source_url": event.get("source_url"),
                }
            )
        if result_rows:
            return result_rows
    return []


def _metadata_value(metadata: Any, key: str) -> Any:
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _put_unique(index: dict[str, Any], bucket: str, key: str | tuple[str, str], row: dict[str, Any]) -> None:
    if not key:
        return
    current = index[bucket].get(key)
    if current is None:
        index[bucket][key] = row
        return
    if current.get("id") != row.get("id"):
        index[bucket][key] = None


def build_fencer_index(rows: list[dict[str, Any]]) -> dict[str, dict[Any, Any]]:
    index: dict[str, dict[Any, Any]] = {"fie": {}, "athlete": {}, "canonical": {}}
    for row in rows:
        if not row.get("id"):
            continue

        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            _put_unique(index, "fie", fie_id, row)

        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        metadata = metadata or {}
        athlete_id = clean_text(row.get("olympedia_athlete_id") or metadata.get("olympedia_athlete_id"))
        if athlete_id:
            _put_unique(index, "athlete", athlete_id, row)

        country = normalize_country(row.get("country") or row.get("nationality"))
        name_key = canonical_name_key(row.get("canonical_name") or row.get("name"))
        if country and name_key:
            _put_unique(index, "canonical", (name_key, country), row)
    return index


def match_result_fencer(
    row: dict[str, Any],
    fencer_index: dict[str, dict[Any, Any]],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if row.get("team"):
        return None, "team_result", None

    fie_id = clean_text(row.get("fie_fencer_id"))
    if fie_id:
        matched = fencer_index.get("fie", {}).get(fie_id)
        if matched:
            return matched, "fie_id", None
        if fie_id in fencer_index.get("fie", {}):
            return None, None, "ambiguous_fie_id"

    athlete_id = clean_text(row.get("athlete_id"))
    if athlete_id:
        matched = fencer_index.get("athlete", {}).get(athlete_id)
        if matched:
            return matched, "olympedia_athlete_id", None
        if athlete_id in fencer_index.get("athlete", {}):
            return None, None, "ambiguous_olympedia_athlete_id"

    country = normalize_country(row.get("country"))
    name_key = canonical_name_key(row.get("name"))
    if country and name_key:
        key = (name_key, country)
        matched = fencer_index.get("canonical", {}).get(key)
        if matched:
            return matched, "canonical_name_country", None
        if key in fencer_index.get("canonical", {}):
            return None, None, "ambiguous_canonical_name_country"

    return None, None, "unmatched_individual_fencer"


def build_result_rows(
    tournament_id: str,
    event: dict[str, Any],
    result_rows: list[dict[str, Any]],
    fencer_index: dict[str, dict[Any, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    db_rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for row in result_rows:
        if row.get("rank") is None:
            continue
        matched, match_method, reason = match_result_fencer(row, fencer_index)
        if not row.get("team") and not matched:
            unmatched.append(
                {
                    "source_id": event["source_id"],
                    "source_url": event.get("source_url") or row.get("source_url"),
                    "name": row.get("name"),
                    "country": row.get("country"),
                    "athlete_id": row.get("athlete_id"),
                    "fie_fencer_id": row.get("fie_fencer_id"),
                    "reason": reason or "unmatched_individual_fencer",
                }
            )
            continue

        country = normalize_country(row.get("country"))
        metadata = {
            "source": SOURCE,
            "source_id": event["source_id"],
            "event_name": event.get("event_name") or event.get("event"),
            "source_url": event.get("source_url") or row.get("source_url"),
            "country_name": row.get("country_name"),
            "team": bool(row.get("team")),
            "athlete_id": row.get("athlete_id"),
            "fie_fencer_id": row.get("fie_fencer_id"),
            "match_method": match_method,
            "historical_country_code": country in HISTORICAL_COUNTRY_CODES,
        }
        db_rows.append(
            {
                "tournament_id": tournament_id,
                "fencer_id": matched.get("id") if matched else None,
                "fie_fencer_id": clean_text(matched.get("fie_id")) if matched and matched.get("fie_id") else row.get("fie_fencer_id"),
                "name": row.get("name"),
                "country": country,
                "nationality": country,
                "rank": row.get("rank"),
                "placement": row.get("rank"),
                "medal": row.get("medal"),
                "metadata": metadata,
                "updated_at": now,
            }
        )
    return db_rows, unmatched


def build_tournament_row(event: dict[str, Any]) -> dict[str, Any]:
    classification = event.get("classification") or {}
    return {
        "source_id": event["source_id"],
        "name": event.get("tournament") or f"{event.get('edition_name')} - {event.get('event_name')}",
        "season": str(event.get("year") or ""),
        "type": "Olympic Historical",
        "weapon": classification.get("weapon"),
        "gender": classification.get("gender"),
        "category": classification.get("category") or "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            **(event.get("metadata") or {}),
            "source": SOURCE,
            "event_name": event.get("event_name"),
            "source_url": event.get("source_url"),
            "team": classification.get("team"),
        },
    }


def upsert_tournament(event: dict[str, Any]) -> str | None:
    row = build_tournament_row(event)
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        if result.data and result.data[0].get("id"):
            return result.data[0]["id"]
        selected = (
            supabase.table("fs_tournaments")  # type: ignore[union-attr]
            .select("id")
            .eq("source_id", row["source_id"])
            .limit(1)
            .execute()
        )
        return selected.data[0]["id"] if selected.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {row['source_id']}: {exc}")
        return None


def log_unmatched_rows(rows: list[dict[str, Any]], path: Path = UNMATCHED_LOG_PATH) -> None:
    if not rows:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({**row, "logged_at": timestamp}, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def upsert_results(
    tournament_id: str,
    event: dict[str, Any],
    result_rows: list[dict[str, Any]],
    fencer_index: dict[str, dict[Any, Any]],
) -> int:
    db_rows, unmatched = build_result_rows(tournament_id, event, result_rows, fencer_index)
    log_unmatched_rows(unmatched)
    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for start in range(0, len(db_rows), 100):
        batch = db_rows[start : start + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed for {event['source_id']}: {exc}")
    return written if written == len(db_rows) else 0


def load_fencer_index() -> dict[str, dict[Any, Any]]:
    if supabase is None:
        return {"fie": {}, "athlete": {}, "canonical": {}}
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        data = (
            supabase.table("fs_fencers")
            .select("id,fie_id,name,country,metadata")
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(data)
        if len(data) < page_size:
            break
        start += page_size
    return build_fencer_index(rows)


class OlympediaClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def get(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                response = self.session.get(url, headers=HEADERS, timeout=30)
            except requests.RequestException as exc:
                print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
                time.sleep(2**attempt)
                continue
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            if response.status_code == 429:
                time.sleep((2**attempt) * 10)
                continue
            if response.status_code in {500, 502, 503, 504}:
                time.sleep(2**attempt)
                continue
            print(f"  HTTP {response.status_code} for {url}")
            return None
        return None


def discover_events(fetcher: Any, sleep_fn: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
    index_html = fetcher.get(SPORT_URL)
    if not index_html:
        return []
    events: list[dict[str, Any]] = []
    for edition in parse_sport_index(index_html):
        page_html = fetcher.get(edition["url"])
        sleep_fn(REQUEST_DELAY)
        if not page_html:
            continue
        events.extend(parse_edition_events(page_html, edition))
    return events


def crawl_historical_olympedia(
    fetcher: Any,
    done_source_ids: set[str] | None = None,
    process_event: Callable[[dict[str, Any], list[dict[str, Any]]], int] | None = None,
    persist_done: Callable[[set[str]], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    done = set(done_source_ids or set())
    stats = {"written": 0, "failed": 0, "skipped": 0}
    events = discover_events(fetcher, sleep_fn=sleep_fn)

    for event in events:
        if event["source_id"] in done:
            stats["skipped"] += 1
            continue

        html_text = fetcher.get(event["source_url"])
        sleep_fn(REQUEST_DELAY)
        if not html_text:
            stats["skipped"] += 1
            continue

        rows = parse_result_rows(html_text, event)
        if not rows:
            stats["skipped"] += 1
            continue

        try:
            written = process_event(event, rows) if process_event else len(rows)
        except Exception as exc:
            print(f"  Failed processing {event['source_id']}: {exc}")
            stats["failed"] += 1
            continue

        if written:
            stats["written"] += 1
            done.add(event["source_id"])
            if persist_done:
                persist_done(done)
        else:
            stats["failed"] += 1
    return stats


def _write_event(event: dict[str, Any], rows: list[dict[str, Any]], fencer_index: dict[str, dict[Any, Any]]) -> int:
    tournament_id = upsert_tournament(event)
    if not tournament_id:
        return 0
    return upsert_results(tournament_id, event, rows, fencer_index)


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY or supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_historical_olympedia").start()
    try:
        print(f"Historical Olympedia scraper starting - {datetime.now(timezone.utc).isoformat()}")
        fencer_index = load_fencer_index()
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])

        stats = crawl_historical_olympedia(
            fetcher=OlympediaClient(),
            done_source_ids=done_source_ids,
            process_event=lambda event, rows: _write_event(event, rows, fencer_index),
            persist_done=lambda done: set_state(SOURCE, "done_source_ids", sorted(done)),
            sleep_fn=time.sleep,
        )
        set_state(
            SOURCE,
            "last_run",
            {
                **stats,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": SOURCE,
            },
        )
        run_log.complete(written=stats["written"], failed=stats["failed"], skipped=stats["skipped"])
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
