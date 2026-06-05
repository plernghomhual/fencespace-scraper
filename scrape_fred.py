"""
USA domestic FRED results scraper.

Probe summary, 2026-06-01:
  - https://fred.usafencing.org: DNS did not resolve.
  - https://fred.fencing.org: certificate mismatch and parked/fingerprint page; no
    public tournament/results application found.
  - https://www.askfred.net: public HTML listings plus tournament-level
    /tournaments/{uuid}/results.csv exports. /api and /graphql returned 404.

API type: HTML plus CSV.
Auth required: no for public result listings and CSV exports. Login is only needed
for organizer/member workflows.
"""

import csv
import hashlib
import html
import os
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any
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

SOURCE = "fred"
BASE_URL = os.environ.get("FRED_BASE_URL", "https://www.askfred.net").rstrip("/")
BATCH_SIZE = int(os.environ.get("FRED_BATCH_SIZE", "100"))
START_PAGE = int(os.environ.get("FRED_START_PAGE", "1"))
MAX_RESULT_PAGES = int(os.environ.get("FRED_MAX_RESULT_PAGES", "5"))
MAX_TOURNAMENTS = int(os.environ.get("FRED_MAX_TOURNAMENTS", "0"))
REQUEST_DELAY_MIN = float(os.environ.get("FRED_DELAY_MIN", "0.5"))
REQUEST_DELAY_MAX = float(os.environ.get("FRED_DELAY_MAX", "1.5"))
RETRY_ATTEMPTS = int(os.environ.get("FRED_RETRY_ATTEMPTS", "3"))
INCREMENTAL = os.environ.get("FRED_INCREMENTAL", "1") != "0"

UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,text/csv,application/json,*/*;q=0.8",
    "Referer": BASE_URL,
}


@dataclass(frozen=True)
class TournamentRef:
    tournament_id: str
    name: str
    results_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "").replace("\xa0", " "))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def title_case(value: Any) -> str | None:
    text = clean_text(value)
    return text.title() if text else None


def normalize_name_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()
    country_map = {
        "US": "United States",
        "USA": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "AMERICA": "United States",
    }
    return country_map.get(key, title_case(text))


def country_key(value: Any) -> str:
    return normalize_name_key(normalize_country(value))


def normalize_person_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        first = title_case(first) or ""
        last = title_case(last) or ""
        if first and last:
            return first if first.lower() == last.lower() else f"{first} {last}"
        return first or last or None
    return title_case(text)


def name_from_parts(first_name: Any, last_name: Any) -> str | None:
    first = title_case(first_name)
    last = title_case(last_name)
    if first and last:
        return first if first.lower() == last.lower() else f"{first} {last}"
    return first or last


def to_int(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except Exception:
        return None


def normalize_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower()
    if key in {"sabre", "saber"}:
        return "Sabre"
    if key == "epee":
        return "Epee"
    if key == "foil":
        return "Foil"
    return title_case(text)


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"[^a-z]+", " ", text.lower()).strip()
    if key in {"men", "mens", "male"}:
        return "Men"
    if key in {"women", "womens", "female"}:
        return "Women"
    if key in {"mixed", "mix"}:
        return "Mixed"
    return title_case(text)


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def clean_usa_fencing_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"\D+", "", text)
    return digits or None


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


session = make_session()


def polite_sleep() -> None:
    if REQUEST_DELAY_MAX <= 0:
        return
    time.sleep(random.uniform(max(0, REQUEST_DELAY_MIN), REQUEST_DELAY_MAX))


def request_get(
    path_or_url: str,
    *,
    params: dict[str, Any] | None = None,
    accept: str | None = None,
) -> requests.Response | None:
    global session

    url = path_or_url if path_or_url.startswith("http") else urljoin(f"{BASE_URL}/", path_or_url.lstrip("/"))
    headers = {}
    if accept:
        headers["Accept"] = accept

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            print(f"  Connection error fetching {url} (attempt {attempt}/{RETRY_ATTEMPTS}): {exc}")
            session = make_session()
        except requests.exceptions.RequestException as exc:
            print(f"  Request error fetching {url} (attempt {attempt}/{RETRY_ATTEMPTS}): {exc}")
        if attempt < RETRY_ATTEMPTS:
            time.sleep(min(2 * attempt, 8))
    return None


def parse_total_pages(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b\d+\s+of\s+(\d+)\s+pages\b", text, re.I)
    return int(match.group(1)) if match else None


def _path_from_href(href: str) -> str:
    parsed = urlparse(href)
    path = parsed.path if parsed.scheme or parsed.netloc else href.split("?", 1)[0]
    return path.rstrip("/")


def parse_results_index(html_text: str) -> tuple[list[TournamentRef], int | None]:
    soup = BeautifulSoup(html_text, "html.parser")
    refs: list[TournamentRef] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        path = _path_from_href(link["href"])
        match = re.fullmatch(rf"/tournaments/({UUID_RE})/results", path)
        if not match:
            continue

        tournament_id = match.group(1)
        if tournament_id in seen:
            continue

        name = clean_text(link.get_text(" ", strip=True))
        if not name or name.lower() in {"results", "view results", "view full results"}:
            name = f"FRED Tournament {tournament_id}"
        refs.append(
            TournamentRef(
                tournament_id=tournament_id,
                name=name,
                results_path=f"/tournaments/{tournament_id}/results",
            )
        )
        seen.add(tournament_id)

    return refs, parse_total_pages(soup)


def discover_tournaments() -> list[TournamentRef]:
    print(
        "Discovering public FRED result pages "
        f"from page {START_PAGE} for up to {MAX_RESULT_PAGES} page(s)"
    )
    refs: list[TournamentRef] = []
    seen: set[str] = set()
    last_page = START_PAGE + MAX_RESULT_PAGES - 1

    for page in range(START_PAGE, last_page + 1):
        response = request_get("/results", params={"has_results": "true", "page": page})
        polite_sleep()
        if response is None:
            print(f"  Page {page}: failed after retries")
            continue
        if response.status_code != 200:
            print(f"  Page {page}: HTTP {response.status_code}, skipping")
            continue

        page_refs, total_pages = parse_results_index(response.text)
        for ref in page_refs:
            if ref.tournament_id not in seen:
                refs.append(ref)
                seen.add(ref.tournament_id)

        total_label = f" of {total_pages}" if total_pages else ""
        print(f"  Page {page}{total_label}: {len(page_refs)} tournament result links")

        if total_pages and page >= total_pages:
            break
        if MAX_TOURNAMENTS and len(refs) >= MAX_TOURNAMENTS:
            refs = refs[:MAX_TOURNAMENTS]
            break

    print(f"Discovered {len(refs)} unique public FRED tournaments with results")
    return refs


def parse_event_cards(html_text: str) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    event_map: dict[str, dict[str, Any]] = {}

    for card in soup.select(".card"):
        header = card.select_one(".card-header") or card
        span = header.find("span")
        event_name = clean_text(span.get_text(" ", strip=True) if span else None)
        if not event_name:
            continue

        result_link = card.find("a", href=re.compile(rf"/tournaments/{UUID_RE}/results/({UUID_RE})"))
        round_link = header.find("a", href=re.compile(rf"^/events/({UUID_RE})"))
        if not round_link:
            round_link = card.find("a", href=re.compile(rf"^/events/({UUID_RE})(?:\?|$)"))

        event_id = None
        event_path = None
        if result_link:
            event_match = re.search(rf"/results/({UUID_RE})", result_link["href"])
            event_id = event_match.group(1) if event_match else None
            event_path = result_link["href"]
        elif round_link:
            event_match = re.search(rf"/events/({UUID_RE})", round_link["href"])
            event_id = event_match.group(1) if event_match else None
            event_path = round_link["href"]
        if not event_id:
            continue

        round_event_id = None
        if round_link:
            round_match = re.search(rf"/events/({UUID_RE})", round_link["href"])
            round_event_id = round_match.group(1) if round_match else None

        event_map[normalize_name_key(event_name)] = {
            "event_id": event_id,
            "source_id": f"fred:{event_id}",
            "event_name": event_name,
            "event_path": event_path,
            "round_event_id": round_event_id,
            "round_event_path": round_link["href"] if round_link else None,
        }

    return event_map


def parse_csv_results(csv_text: str) -> list[dict[str, str | None]]:
    reader = csv.DictReader(StringIO(csv_text))
    rows: list[dict[str, str | None]] = []
    for row in reader:
        cleaned: dict[str, str | None] = {}
        for key, value in row.items():
            cleaned_key = clean_text(key)
            if not cleaned_key:
                continue
            cleaned[cleaned_key] = clean_text(value)
        rows.append(cleaned)
    return rows


def csv_rows_for_tournament(ref: TournamentRef) -> list[dict[str, str | None]]:
    response = request_get(
        f"/tournaments/{ref.tournament_id}/results.csv",
        accept="text/csv, */*;q=0.5",
    )
    polite_sleep()
    if response is None:
        print(f"    CSV fetch failed for {ref.name}")
        return []
    if response.status_code != 200:
        print(f"    CSV fetch HTTP {response.status_code} for {ref.name}")
        return []
    rows = parse_csv_results(response.text)
    print(f"    CSV rows: {len(rows)}")
    return rows


def event_cards_for_tournament(ref: TournamentRef) -> dict[str, dict[str, Any]]:
    response = request_get(ref.results_path)
    polite_sleep()
    if response is None or response.status_code != 200:
        status = response.status_code if response is not None else "failed"
        print(f"    Result page fetch {status}; event ids will fall back to stable hashes")
        return {}
    event_map = parse_event_cards(response.text)
    print(f"    Event cards: {len(event_map)}")
    return event_map


def group_csv_rows(
    rows: list[dict[str, Any]],
    event_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        tournament_name = clean_text(row.get("Tournament"))
        event_name = clean_text(row.get("Event"))
        if not tournament_name or not event_name:
            continue

        event_info = event_map.get(normalize_name_key(event_name), {})
        fallback_id = stable_hash(f"{tournament_name}|{event_name}")
        event_id = event_info.get("event_id") or fallback_id
        source_id = f"fred:{event_id}"

        if source_id not in grouped:
            grouped[source_id] = {
                "source_id": source_id,
                "event_id": event_id,
                "event_name": event_info.get("event_name") or event_name,
                "event_path": event_info.get("event_path"),
                "round_event_id": event_info.get("round_event_id"),
                "round_event_path": event_info.get("round_event_path"),
                "tournament_name": tournament_name,
                "rows": [],
            }
        grouped[source_id]["rows"].append(row)

    return grouped


def build_tournament_rows(
    ref: TournamentRef,
    grouped_events: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for source_id, event in grouped_events.items():
        first = event["rows"][0]
        event_date = normalize_date(first.get("Date"))
        season = event_date[:4] if event_date else None
        event_name = event["event_name"]
        tournament_name = event["tournament_name"] or ref.name

        rows.append(
            {
                "source_id": source_id,
                "season": season,
                "name": f"{tournament_name}: {event_name}"[:180],
                "location": None,
                "country": "United States",
                "weapon": normalize_weapon(first.get("Weapon")),
                "gender": normalize_gender(first.get("Event Gender")),
                "category": clean_text(first.get("Age Resitrction") or first.get("Age Restriction")),
                "start_date": event_date,
                "end_date": event_date,
                "type": "FRED",
                "has_results": True,
                "is_sub_competition": False,
                "metadata": {
                    "source": SOURCE,
                    "api_type": "html_csv",
                    "auth_required": False,
                    "base_url": BASE_URL,
                    "fred_tournament_uuid": ref.tournament_id,
                    "fred_event_id": event.get("event_id"),
                    "fred_event_path": event.get("event_path"),
                    "fred_round_event_id": event.get("round_event_id"),
                    "fred_round_event_path": event.get("round_event_path"),
                    "fred_event_name": event_name,
                    "fred_tournament_name": tournament_name,
                    "fred_results_path": ref.results_path,
                    "fred_event_rating": clean_text(first.get("Event Rating")),
                    "fred_event_size": to_int(first.get("Event Size")),
                    "fred_rating_restriction": clean_text(first.get("Rating Restriction")),
                },
                "updated_at": utc_now(),
            }
        )

    return rows


def _metadata_ids(metadata: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    ids: list[str] = []
    for key in (
        "usafencing_id",
        "usa_fencing_id",
        "usfa_number",
        "fred_usfa_number",
        "askfred_usfa_number",
        "member_number",
    ):
        value = clean_usa_fencing_id(metadata.get(key))
        if value:
            ids.append(value)
    return ids


def _row_usa_ids(row: dict[str, Any]) -> list[str]:
    ids = _metadata_ids(row.get("metadata"))
    for key in ("usafencing_id", "usa_fencing_id", "usfa_number", "member_number"):
        value = clean_usa_fencing_id(row.get(key))
        if value:
            ids.append(value)
    return list(dict.fromkeys(ids))


def build_fencer_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_usa_id: dict[str, dict[str, Any]] = {}
    by_name_country: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in rows:
        name = clean_text(row.get("name"))
        ckey = country_key(row.get("country"))
        if name and ckey:
            by_name_country.setdefault((normalize_name_key(name), ckey), []).append(row)
        for usa_id in _row_usa_ids(row):
            by_usa_id.setdefault(usa_id, row)

    return {"usa_id": by_usa_id, "name_country": by_name_country}


def fetch_fencer_index() -> dict[str, Any]:
    require_supabase()
    print("Loading fs_fencers for USA Fencing ID and name/country matching...")
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        data = (
            supabase.table("fs_fencers")  # type: ignore[union-attr]
            .select("id,fie_id,name,country,metadata")
            .range(start, start + page_size - 1)
            .execute()
            .data
        )
        rows.extend(data or [])
        if not data or len(data) < page_size:
            break
        start += page_size
    print(f"Loaded {len(rows)} fencer rows")
    return build_fencer_index(rows)


def match_fencer(
    fencer_index: dict[str, Any],
    name: str | None,
    country: str | None = "United States",
    usa_fencing_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    usa_id = clean_usa_fencing_id(usa_fencing_id)
    if usa_id:
        matched = fencer_index.get("usa_id", {}).get(usa_id)
        if matched:
            return matched, "usa_fencing_id"

    if not name or normalize_country(country) != "United States":
        return None, None

    candidates = fencer_index.get("name_country", {}).get((normalize_name_key(name), country_key(country)), [])
    if len(candidates) == 1:
        return candidates[0], "exact_name_country"
    return None, None


def result_fencer_key(source_id: str, row: dict[str, Any], name: str, club: str | None) -> str:
    usa_id = clean_usa_fencing_id(row.get("Usfa Number"))
    if usa_id:
        return f"fred:usfa:{usa_id}"
    fallback = f"{source_id}|{normalize_name_key(name)}|{normalize_name_key(club)}"
    return f"fred:name:{stable_hash(fallback)}"


def collect_result_rows(
    grouped_events: dict[str, dict[str, Any]],
    tournament_ids: dict[str, int],
    fencer_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    result_rows: list[dict[str, Any]] = []
    unmatched: list[str] = []
    unmatched_seen: set[str] = set()

    for source_id, event in grouped_events.items():
        tournament_id = tournament_ids.get(source_id)
        if not tournament_id:
            print(f"    Missing fs_tournaments id for {source_id}; skipping event results")
            continue

        for row in event["rows"]:
            name = name_from_parts(row.get("Competitor First Name"), row.get("Competitor Last Name"))
            rank = to_int(row.get("Place"))
            if not name or rank is None:
                continue

            club = clean_text(row.get("Club"))
            usa_id = clean_usa_fencing_id(row.get("Usfa Number"))
            matched, match_method = match_fencer(fencer_index, name, "United States", usa_id)
            if not matched and name not in unmatched_seen:
                unmatched.append(name)
                unmatched_seen.add(name)

            rating_before = clean_text(row.get("Rating Before Event"))
            rating_earned = clean_text(row.get("Rating Earned"))

            fred_fencer_key = result_fencer_key(source_id, row, name, club)
            result_rows.append(
                {
                    "tournament_id": tournament_id,
                    "fencer_id": matched.get("id") if matched else None,
                    "fie_fencer_id": None,  # fs_results.fie_fencer_id is INTEGER; FRED keys are non-numeric strings
                    "rank": rank,
                    "placement": rank,
                    "name": name,
                    "country": "United States",
                    "nationality": "United States",
                    "metadata": {
                        "source": SOURCE,
                        "source_id": source_id,
                        "fred_fencer_key": fred_fencer_key,
                        "fred_event_id": event.get("event_id"),
                        "fred_event_name": event.get("event_name"),
                        "fred_event_path": event.get("event_path"),
                        "fred_round_event_id": event.get("round_event_id"),
                        "fred_tournament_name": event.get("tournament_name"),
                        "fred_usfa_number": usa_id,
                        "fred_club": club,
                        "fred_rating_before_event": rating_before,
                        "fred_rating_earned": rating_earned,
                        "fred_event_rating": clean_text(row.get("Event Rating")),
                        "fred_event_size": to_int(row.get("Event Size")),
                        "fred_rating_restriction": clean_text(row.get("Rating Restriction")),
                        "fred_age_restriction": clean_text(
                            row.get("Age Resitrction") or row.get("Age Restriction")
                        ),
                        "match_method": match_method,
                    },
                    "updated_at": utc_now(),
                }
            )

    return result_rows, unmatched


def require_supabase() -> None:
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")


def batch_upsert(
    table: str,
    rows: list[dict[str, Any]],
    *,
    on_conflict: str,
    batch_size: int = BATCH_SIZE,
) -> None:
    require_supabase()
    for i in range(0, len(rows), batch_size):
        supabase.table(table).upsert(rows[i : i + batch_size], on_conflict=on_conflict).execute()  # type: ignore[union-attr]


def fetch_tournament_id_map(source_ids: list[str]) -> dict[str, int]:
    require_supabase()
    ids: dict[str, int] = {}
    for i in range(0, len(source_ids), BATCH_SIZE):
        chunk = source_ids[i : i + BATCH_SIZE]
        result = supabase.table("fs_tournaments").select("id,source_id").in_("source_id", chunk).execute()  # type: ignore[union-attr]
        for row in result.data or []:
            ids[row["source_id"]] = row["id"]
    return ids


def upsert_tournaments(rows: list[dict[str, Any]]) -> dict[str, int]:
    if not rows:
        return {}

    try:
        batch_upsert("fs_tournaments", rows, on_conflict="source_id")
    except Exception as exc:
        message = str(exc)
        if "42P10" not in message and "no unique or exclusion constraint" not in message.lower():
            raise
        print(
            "    fs_tournaments has no unique constraint on source_id; "
            "falling back to select-existing + insert-new."
        )
        source_ids = [row["source_id"] for row in rows]
        existing = set(fetch_tournament_id_map(source_ids))
        new_rows = [row for row in rows if row["source_id"] not in existing]
        for i in range(0, len(new_rows), BATCH_SIZE):
            supabase.table("fs_tournaments").insert(new_rows[i : i + BATCH_SIZE]).execute()  # type: ignore[union-attr]

    return fetch_tournament_id_map([row["source_id"] for row in rows])


def upsert_results(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    try:
        batch_upsert("fs_results", rows, on_conflict="tournament_id,name")
        return
    except Exception as exc:
        message = str(exc)
        if "unique" not in message.lower() and "constraint" not in message.lower() and "42P10" not in message:
            raise
        raise RuntimeError(
            "fs_results requires a unique conflict target on (tournament_id, name); "
            "refusing to delete existing FRED rows as a fallback."
        ) from exc


def fetch_existing_fred_source_ids() -> set[str]:
    require_supabase()
    existing: set[str] = set()
    start = 0
    page_size = 1000
    while True:
        rows = (
            supabase.table("fs_tournaments")  # type: ignore[union-attr]
            .select("source_id")
            .like("source_id", "fred:%")
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        for row in rows:
            if row.get("source_id"):
                existing.add(row["source_id"])
        if len(rows) < page_size:
            break
        start += page_size
    return existing


def scrape_tournament(
    ref: TournamentRef,
    fencer_index: dict[str, Any],
    existing_source_ids: set[str] | None = None,
) -> tuple[int, int, int]:
    print(f"\n  Scraping {ref.name} ({ref.tournament_id})")
    csv_rows = csv_rows_for_tournament(ref)
    if not csv_rows:
        print("    No CSV result rows found")
        return 0, 0, 0

    event_map = event_cards_for_tournament(ref)
    grouped_events = group_csv_rows(csv_rows, event_map)
    if not grouped_events:
        print("    No event groups found")
        return 0, 0, 0

    if INCREMENTAL and existing_source_ids is not None:
        new_events = {key: value for key, value in grouped_events.items() if key not in existing_source_ids}
        skipped = len(grouped_events) - len(new_events)
        if skipped:
            print(f"    Incremental: skipping {skipped} already-scraped event(s), {len(new_events)} new")
        if not new_events:
            return 0, skipped, 0
        grouped_events = new_events

    tournament_rows = build_tournament_rows(ref, grouped_events)
    tournament_ids = upsert_tournaments(tournament_rows)
    print(f"    Upserted {len(tournament_rows)} FRED event tournament rows")

    result_rows, unmatched = collect_result_rows(grouped_events, tournament_ids, fencer_index)
    upsert_results(result_rows)
    print(f"    Upserted {len(result_rows)} results; unmatched fencers: {len(unmatched)}")
    if unmatched:
        print(f"    Unmatched sample: {', '.join(unmatched[:10])}")

    return len(result_rows), 0, len(unmatched)


def main() -> None:
    require_supabase()
    print(f"FRED scraper starting - {utc_now()}")
    print(
        "Settings: "
        f"base_url={BASE_URL}, start_page={START_PAGE}, max_pages={MAX_RESULT_PAGES}, "
        f"max_tournaments={MAX_TOURNAMENTS or 'none'}, delay={REQUEST_DELAY_MIN}-{REQUEST_DELAY_MAX}s, "
        f"incremental={INCREMENTAL}"
    )

    run_log = ScraperRunLogger("scrape_fred").start()
    try:
        fencer_index = fetch_fencer_index()
        existing_source_ids = fetch_existing_fred_source_ids() if INCREMENTAL else None
        if existing_source_ids is not None:
            print(f"Incremental mode: {len(existing_source_ids)} existing FRED event source IDs loaded")

        done_tournament_ids = set(get_state(SOURCE, "done_tournament_ids") or [])
        tournament_refs = discover_tournaments()

        total_results = 0
        total_unmatched = 0
        skipped = 0
        failed = 0

        for index, ref in enumerate(tournament_refs, start=1):
            print(f"\nTournament {index}/{len(tournament_refs)}")
            try:
                results_count, skipped_count, unmatched_count = scrape_tournament(
                    ref,
                    fencer_index,
                    existing_source_ids,
                )
                if results_count == 0:
                    skipped += skipped_count or 1
                else:
                    total_results += results_count
                    total_unmatched += unmatched_count
                    done_tournament_ids.add(ref.tournament_id)
                    set_state(SOURCE, "done_tournament_ids", sorted(done_tournament_ids))
            except Exception as exc:
                failed += 1
                print(f"    Error scraping {ref.name}: {exc}")

        run_log.complete(
            written=total_results,
            failed=failed,
            skipped=skipped,
            metadata={"unmatched_fencers": total_unmatched},
        )
        print(
            "\nFRED scraper complete - "
            f"results={total_results}, unmatched_fencers={total_unmatched}, "
            f"skipped={skipped}, failed_tournaments={failed}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


def scrape_fred() -> None:
    main()


if __name__ == "__main__":
    main()
