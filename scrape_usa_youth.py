"""
USA Y12/Y14 public FRED youth national-circuit result scraper.

Probe summary, 2026-06-02:
  - Current public FRED result pages are available on https://www.askfred.net
    under UUID routes such as /tournaments/{uuid}/results and CSV exports at
    /tournaments/{uuid}/results.csv. Public pages expose Y12/Y14 event names,
    final placements, fencer names, clubs, ratings, dates, and source links.
  - Linked USA Fencing member-detail tournament pages are treated as final
    authority/private-session pages and are not fetched by this scraper.
  - Local shell network probing was blocked by sandbox DNS, and escalated retry
    was unavailable due the Codex usage-limit approval gate. Browser evidence
    confirmed current public FRED HTML shape; blocked endpoints are recorded
    as probe stubs instead of scraped.

This module intentionally does not import the legacy askfred_scraper.py.
"""

from __future__ import annotations

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
from typing import Any, Callable
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

SOURCE = "usa_youth"
FRED_BASE_URL = os.environ.get("USA_YOUTH_FRED_BASE_URL", "https://www.askfred.net").rstrip("/")
BATCH_SIZE = int(os.environ.get("USA_YOUTH_BATCH_SIZE", "100"))
START_PAGE = int(os.environ.get("USA_YOUTH_START_PAGE", "1"))
MAX_RESULT_PAGES = int(os.environ.get("USA_YOUTH_MAX_RESULT_PAGES", "5"))
MAX_TOURNAMENTS = int(os.environ.get("USA_YOUTH_MAX_TOURNAMENTS", "0"))
REQUEST_DELAY_MIN = float(os.environ.get("USA_YOUTH_DELAY_MIN", "0.5"))
REQUEST_DELAY_MAX = float(os.environ.get("USA_YOUTH_DELAY_MAX", "1.5"))
RETRY_ATTEMPTS = int(os.environ.get("USA_YOUTH_RETRY_ATTEMPTS", "3"))
INCREMENTAL = os.environ.get("USA_YOUTH_INCREMENTAL", "1") != "0"

UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,text/csv,application/json,*/*;q=0.8",
    "Referer": FRED_BASE_URL,
}

PUBLIC_PROBE_URL = f"{FRED_BASE_URL}/results?has_results=true&page=1"
BLOCKED_SOURCE_STUBS = [
    {
        "url": "https://member.usafencing.org/details/tournaments/{id}",
        "reason": "linked final authority pages may require member/session access; scraper does not fetch them",
    },
    {
        "url": "https://fred.usafencing.org/",
        "reason": "no public result application confirmed during probe; scraper uses public FRED result exports instead",
    },
    {
        "url": "https://fred.fencing.org/",
        "reason": "no public result application confirmed during probe; scraper uses public FRED result exports instead",
    },
]


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


def normalize_name_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_identity_text(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    return re.sub(r"\s+", " ", text).strip() or None


def title_case(value: Any) -> str | None:
    text = clean_text(value)
    return text.title() if text else None


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
    }
    return country_map.get(key, title_case(text))


def country_key(value: Any) -> str | None:
    country = normalize_country(value)
    return normalize_identity_text(country) if country else None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_name_key(text)
    if key in {"saber", "sabre"}:
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
    if key in {"women", "womens", "female", "girls", "girl"}:
        return "Women"
    if key in {"men", "mens", "male", "boys", "boy"}:
        return "Men"
    if key in {"mixed", "mix"}:
        return "Mixed"
    return title_case(text)


def normalize_age_group(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(
        r"\b(?:Y\s*-?\s*(12|14)|Youth\s*-?\s*(12|14)|Under\s+(12|14)|U\s*-?\s*(12|14))\b",
        text,
        re.I,
    )
    if not match:
        return None
    age = next(group for group in match.groups() if group)
    return f"Y{age}"


def normalize_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def to_int(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _path_from_href(href: str) -> str:
    parsed = urlparse(href)
    path = parsed.path if parsed.scheme or parsed.netloc else href.split("?", 1)[0]
    return path.rstrip("/")


def _source_url(path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    if path_or_url.startswith("http"):
        return path_or_url
    return urljoin(f"{FRED_BASE_URL}/", path_or_url.lstrip("/"))


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

    url = path_or_url if path_or_url.startswith("http") else urljoin(f"{FRED_BASE_URL}/", path_or_url.lstrip("/"))
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


def _event_lookup_keys(event_name: str) -> set[str]:
    keys = {normalize_name_key(event_name)}
    age_group = normalize_age_group(event_name)
    if not age_group:
        return keys

    age = age_group[1:]
    template = re.sub(
        r"\b(?:Y\s*-?\s*(?:12|14)|Youth\s*-?\s*(?:12|14)|Under\s+(?:12|14)|U\s*-?\s*(?:12|14))\b",
        "{AGE}",
        event_name,
        flags=re.I,
    )
    for label in (f"Y{age}", f"Y-{age}", f"Youth {age}", f"Youth-{age}", f"Under {age}"):
        keys.add(normalize_name_key(template.replace("{AGE}", label)))
    return keys


def parse_total_pages(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b\d+\s+of\s+(\d+)\s+pages\b", text, re.I)
    return int(match.group(1)) if match else None


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
        refs.append(TournamentRef(tournament_id=tournament_id, name=name, results_path=path))
        seen.add(tournament_id)

    return refs, parse_total_pages(soup)


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

        event_info = {
            "event_id": event_id,
            "source_id": f"{SOURCE}:fred:{event_id}",
            "event_name": event_name,
            "event_path": event_path,
            "source_url": _source_url(event_path),
            "round_event_id": round_event_id,
            "round_event_path": round_link["href"] if round_link else None,
        }
        for key in _event_lookup_keys(event_name):
            event_map[key] = event_info

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


def is_youth_national_circuit_tournament(tournament_name: Any) -> bool:
    name = clean_text(tournament_name) or ""
    if re.search(r"\bSYC\b|Super Youth Circuit", name, re.I):
        return True
    if re.search(r"\bNAC\b|National Championships?|Summer Nationals?", name, re.I):
        return True
    return False


def _event_age_group(row: dict[str, Any], event_name: str) -> str | None:
    return normalize_age_group(
        row.get("Age Restriction")
        or row.get("Age Resitrction")
        or row.get("Age")
        or event_name
    )


def group_youth_csv_rows(
    rows: list[dict[str, Any]],
    event_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        tournament_name = clean_text(row.get("Tournament"))
        event_name = clean_text(row.get("Event"))
        if not tournament_name or not event_name:
            continue
        if not is_youth_national_circuit_tournament(tournament_name):
            continue

        age_group = _event_age_group(row, event_name)
        if age_group not in {"Y12", "Y14"}:
            continue

        event_info = event_map.get(normalize_name_key(event_name), {})
        fallback_id = stable_hash(f"{tournament_name}|{event_name}")
        event_id = event_info.get("event_id") or fallback_id
        source_id = event_info.get("source_id") or f"{SOURCE}:fred:{event_id}"
        source_url = event_info.get("source_url")

        if source_id not in grouped:
            grouped[source_id] = {
                "source_id": source_id,
                "event_id": event_id,
                "event_name": event_info.get("event_name") or event_name,
                "event_path": event_info.get("event_path"),
                "source_url": source_url,
                "round_event_id": event_info.get("round_event_id"),
                "round_event_path": event_info.get("round_event_path"),
                "tournament_name": tournament_name,
                "age_group": age_group,
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
        tournament_name = event["tournament_name"] or ref.name
        event_name = event["event_name"]
        source_url = event.get("source_url") or _source_url(ref.results_path)

        rows.append(
            {
                "source_id": source_id,
                "season": event_date[:4] if event_date else None,
                "name": f"{tournament_name}: {event_name}"[:180],
                "location": None,
                "country": "United States",
                "weapon": normalize_weapon(first.get("Weapon")) or normalize_weapon(event_name),
                "gender": normalize_gender(first.get("Event Gender")) or normalize_gender(event_name),
                "category": event["age_group"],
                "start_date": event_date,
                "end_date": event_date,
                "type": "FRED Youth",
                "has_results": True,
                "is_sub_competition": False,
                "metadata": {
                    "source": SOURCE,
                    "api_type": "public_html_csv",
                    "fred_platform": "public_fred",
                    "auth_required": False,
                    "base_url": FRED_BASE_URL,
                    "source_url": source_url,
                    "fred_tournament_uuid": ref.tournament_id,
                    "fred_results_path": ref.results_path,
                    "fred_event_id": event.get("event_id"),
                    "fred_event_path": event.get("event_path"),
                    "fred_event_name": event_name,
                    "fred_round_event_id": event.get("round_event_id"),
                    "fred_round_event_path": event.get("round_event_path"),
                    "fred_tournament_name": tournament_name,
                    "fred_event_size": to_int(first.get("Event Size")),
                    "fred_rating_restriction": clean_text(first.get("Rating Restriction")),
                    "minor_data_policy": "public_results_only_no_profile_scraping",
                },
                "updated_at": utc_now(),
            }
        )

    return rows


def _clean_fie_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"\D+", "", text)
    return digits or text


def _extract_fie_id(row: dict[str, Any]) -> str | None:
    for key in ("FIE ID", "Fie ID", "FIE Number", "fie_id", "fieId"):
        fie_id = _clean_fie_id(row.get(key))
        if fie_id:
            return fie_id
    return None


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


def _row_name(row: dict[str, Any]) -> str | None:
    return (
        name_from_parts(row.get("Competitor First Name"), row.get("Competitor Last Name"))
        or normalize_person_name(row.get("Fencer"))
        or normalize_person_name(row.get("Name"))
        or normalize_person_name(row.get("Competitor"))
    )


def _row_rank(row: dict[str, Any]) -> int | None:
    for key in ("Place", "Pl", "Rank", "Placement"):
        rank = to_int(row.get(key))
        if rank is not None:
            return rank
    return None


def _row_club(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("Club") or row.get("Club(s)") or row.get("Club/Division"))


def _row_division(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("Division") or row.get("Div"))


def _row_points(row: dict[str, Any]) -> float | None:
    for key in ("Points", "National Points", "NRPS Points"):
        points = to_float(row.get(key))
        if points is not None:
            return points
    return None


def _row_medal(row: dict[str, Any], rank: int | None) -> str | None:
    explicit = clean_text(row.get("Medal"))
    if explicit:
        key = explicit.lower()
        if key in {"gold", "silver", "bronze"}:
            return key.title()
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _candidate(candidate_id: str, method: str, source: str) -> dict[str, str]:
    return {"id": candidate_id, "method": method, "source": source}


def _add_candidate(index: dict[Any, list[dict[str, str]]], key: Any, candidate: dict[str, str]) -> None:
    if not key:
        return
    bucket = index.setdefault(key, [])
    if candidate not in bucket:
        bucket.append(candidate)


def _identity_row_id(identity: dict[str, Any]) -> str | None:
    row_ids = identity.get("fs_fencer_row_ids") or identity.get("fencer_ids") or []
    if isinstance(row_ids, str):
        row_ids = [row_ids]
    row_ids = [clean_text(row_id) for row_id in row_ids]
    row_ids = sorted(row_id for row_id in row_ids if row_id)
    return row_ids[0] if row_ids else None


def build_fencer_index(
    fencer_rows: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_fie_id: dict[str, list[dict[str, str]]] = {}
    by_name_country: dict[tuple[str, str], list[dict[str, str]]] = {}

    for row in fencer_rows or []:
        fencer_id = clean_text(row.get("id"))
        if not fencer_id:
            continue
        fie_id = _clean_fie_id(row.get("fie_id"))
        if fie_id:
            _add_candidate(by_fie_id, fie_id, _candidate(fencer_id, "fie_id", "fs_fencers"))
        name_key = normalize_identity_text(row.get("name"))
        ckey = country_key(row.get("country"))
        if name_key and ckey:
            _add_candidate(by_name_country, (name_key, ckey), _candidate(fencer_id, "exact_name_country", "fs_fencers"))

    for identity in identity_rows or []:
        fencer_id = _identity_row_id(identity)
        if not fencer_id:
            continue
        for fie_id in identity.get("fie_ids") or []:
            cleaned = _clean_fie_id(fie_id)
            if cleaned:
                _add_candidate(by_fie_id, cleaned, _candidate(fencer_id, "identity_fie_id", "fs_fencer_identities"))
        name_key = normalize_identity_text(identity.get("canonical_name"))
        ckey = country_key(identity.get("country"))
        if name_key and ckey:
            _add_candidate(
                by_name_country,
                (name_key, ckey),
                _candidate(fencer_id, "identity_name_country", "fs_fencer_identities"),
            )

    return {"fie_id": by_fie_id, "name_country": by_name_country}


def _resolve_candidate(
    candidates: list[dict[str, str]],
    method_priority: tuple[str, ...],
) -> tuple[dict[str, str] | None, str | None]:
    if not candidates:
        return None, None
    candidate_ids = {candidate["id"] for candidate in candidates}
    if len(candidate_ids) != 1:
        return None, "ambiguous_match"
    by_method = {candidate["method"]: candidate for candidate in candidates}
    for method in method_priority:
        if method in by_method:
            return by_method[method], None
    return candidates[0], None


def match_fencer(
    fencer_index: dict[str, Any],
    *,
    name: str | None,
    country: str | None = "United States",
    fie_id: str | None = None,
) -> tuple[dict[str, str] | None, str | None, str | None]:
    cleaned_fie_id = _clean_fie_id(fie_id)
    if cleaned_fie_id:
        matched, reason = _resolve_candidate(
            fencer_index.get("fie_id", {}).get(cleaned_fie_id, []),
            ("fie_id", "identity_fie_id"),
        )
        if matched:
            return matched, matched["method"], None
        if reason:
            return None, None, reason

    name_key = normalize_identity_text(name)
    ckey = country_key(country)
    if not name_key or not ckey:
        return None, None, "missing_name_country"
    matched, reason = _resolve_candidate(
        fencer_index.get("name_country", {}).get((name_key, ckey), []),
        ("identity_name_country", "exact_name_country"),
    )
    if matched:
        return matched, matched["method"], None
    return None, None, reason or "no_explicit_match"


def collect_result_rows(
    grouped_events: dict[str, dict[str, Any]],
    tournament_ids: dict[str, int],
    fencer_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result_rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    unmatched_seen: set[tuple[Any, ...]] = set()

    for source_id, event in grouped_events.items():
        tournament_id = tournament_ids.get(source_id)
        if not tournament_id:
            print(f"    Missing fs_tournaments id for {source_id}; skipping event results")
            continue

        for row in event["rows"]:
            name = _row_name(row)
            rank = _row_rank(row)
            if not name or rank is None:
                continue
            club = _row_club(row)
            division = _row_division(row)
            fie_id = _extract_fie_id(row)
            matched, match_method, unmatched_reason = match_fencer(
                fencer_index,
                name=name,
                country="United States",
                fie_id=fie_id,
            )
            if not matched:
                unmatched_key = (name, club, division, event.get("source_url"), unmatched_reason)
                if unmatched_key not in unmatched_seen:
                    unmatched.append(
                        {
                            "name": name,
                            "club": club,
                            "division": division,
                            "event": event.get("event_name"),
                            "source_url": event.get("source_url"),
                            "reason": unmatched_reason or "no_explicit_match",
                        }
                    )
                    unmatched_seen.add(unmatched_key)
                continue

            points = _row_points(row)
            result_rows.append(
                {
                    "tournament_id": tournament_id,
                    "fencer_id": matched["id"],
                    "fie_fencer_id": fie_id,
                    "rank": rank,
                    "placement": rank,
                    "name": name,
                    "country": "United States",
                    "nationality": "United States",
                    "medal": _row_medal(row, rank),
                    "metadata": {
                        "source": SOURCE,
                        "source_id": source_id,
                        "source_url": event.get("source_url"),
                        "fred_platform": "public_fred",
                        "fred_event_id": event.get("event_id"),
                        "fred_event_name": event.get("event_name"),
                        "fred_event_path": event.get("event_path"),
                        "fred_round_event_id": event.get("round_event_id"),
                        "fred_tournament_name": event.get("tournament_name"),
                        "fred_club": club,
                        "fred_division": division,
                        "fred_points": points,
                        "fred_rating_before_event": clean_text(row.get("Rating Before Event")),
                        "fred_rating_earned": clean_text(row.get("Rating Earned")),
                        "fred_event_rating": clean_text(row.get("Event Rating")),
                        "fred_event_size": to_int(row.get("Event Size")),
                        "fred_age_group": event.get("age_group"),
                        "fie_id_available": bool(fie_id),
                        "match_method": match_method,
                        "minor_data_policy": "public_results_only_no_profile_scraping",
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
    batch_upsert("fs_tournaments", rows, on_conflict="source_id")
    return fetch_tournament_id_map([row["source_id"] for row in rows])


def upsert_results(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    if any(not row.get("fencer_id") for row in rows):
        raise ValueError("USA youth results require fencer_id; unmatched rows must be logged and skipped")

    try:
        batch_upsert("fs_results", rows, on_conflict="tournament_id,fencer_id")
    except Exception as exc:
        message = str(exc).lower()
        if "42p10" not in message and "no unique" not in message and "constraint" not in message:
            raise
        batch_upsert("fs_results", rows, on_conflict="tournament_id,name")


def _fetch_all(table: str, columns: str, page_size: int = 1000) -> list[dict[str, Any]]:
    require_supabase()
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        batch = (
            supabase.table(table)  # type: ignore[union-attr]
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def fetch_fencer_index() -> dict[str, Any]:
    fencers = _fetch_all("fs_fencers", "id,fie_id,name,country")
    try:
        identities = _fetch_all("fs_fencer_identities", "id,canonical_name,country,fie_ids,fs_fencer_row_ids")
    except Exception as exc:
        print(f"  fs_fencer_identities unavailable; falling back to fs_fencers only: {exc}")
        identities = []
    return build_fencer_index(fencers, identities)


def fetch_existing_source_ids() -> set[str]:
    if supabase is None:
        return set()
    existing: set[str] = set()
    start = 0
    page_size = 1000
    while True:
        rows = (
            supabase.table("fs_tournaments")
            .select("source_id")
            .like("source_id", f"{SOURCE}:fred:%")
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
    print(f"    Event cards: {len({info['source_id'] for info in event_map.values()})}")
    return event_map


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
    grouped_events = group_youth_csv_rows(csv_rows, event_map)
    if not grouped_events:
        print("    No Y12/Y14 national-circuit event groups found")
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
    print(f"    Upserted {len(tournament_rows)} youth event tournament rows")

    result_rows, unmatched = collect_result_rows(grouped_events, tournament_ids, fencer_index)
    upsert_results(result_rows)
    print(f"    Upserted {len(result_rows)} matched results; unmatched/skipped youth rows: {len(unmatched)}")
    if unmatched:
        sample = ", ".join(row["name"] for row in unmatched[:10] if row.get("name"))
        print(f"    Unmatched sample: {sample}")

    return len(result_rows), 0, len(unmatched)


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

        print(f"  Page {page}{f' of {total_pages}' if total_pages else ''}: {len(page_refs)} result links")
        if total_pages and page >= total_pages:
            break
        if MAX_TOURNAMENTS and len(refs) >= MAX_TOURNAMENTS:
            refs = refs[:MAX_TOURNAMENTS]
            break

    print(f"Discovered {len(refs)} unique public FRED tournaments with results")
    return refs


def probe_sources(
    *,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
    fetch_public: bool = False,
) -> dict[str, Any]:
    """Return dry-run source probe evidence without fetching private endpoints."""
    public_entry: dict[str, Any] = {
        "url": PUBLIC_PROBE_URL,
        "kind": "public_fred_results_index",
        "status_code": None,
    }
    if fetch_public:
        if fetcher is None:
            def fetcher(url: str) -> dict[str, Any]:
                response = requests.get(url, headers=HEADERS, timeout=15)
                return {"status_code": response.status_code, "url": response.url, "public": response.status_code == 200}

        public_entry.update(fetcher(PUBLIC_PROBE_URL))

    return {
        "public_sources": [public_entry],
        "blocked_sources": list(BLOCKED_SOURCE_STUBS),
        "privacy": {
            "minor_profile_scraping": False,
            "private_member_endpoint_fetching": False,
            "policy": "only parse public tournament result pages and CSV exports",
        },
    }


def main() -> None:
    require_supabase()
    print(f"USA youth FRED scraper starting - {utc_now()}")
    print(
        "Settings: "
        f"base_url={FRED_BASE_URL}, start_page={START_PAGE}, max_pages={MAX_RESULT_PAGES}, "
        f"max_tournaments={MAX_TOURNAMENTS or 'none'}, delay={REQUEST_DELAY_MIN}-{REQUEST_DELAY_MAX}s, "
        f"incremental={INCREMENTAL}"
    )

    run_log = ScraperRunLogger("scrape_usa_youth").start()
    try:
        fencer_index = fetch_fencer_index()
        existing_source_ids = fetch_existing_source_ids() if INCREMENTAL else None
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
            metadata={
                "unmatched_youth_rows": total_unmatched,
                "probe_sources": probe_sources(fetch_public=False),
            },
        )
        print(
            "\nUSA youth FRED scraper complete - "
            f"results={total_results}, unmatched_youth_rows={total_unmatched}, "
            f"skipped={skipped}, failed_tournaments={failed}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


def scrape_usa_youth() -> None:
    main()


if __name__ == "__main__":
    main()
