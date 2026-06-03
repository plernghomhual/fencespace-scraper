"""Scrape FIE Satellite and Challenge-series tournament results."""

from __future__ import annotations

import calendar
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

try:
    from scripts.rate_limiter import RateLimiter as _RateLimiter
except ImportError:  # pragma: no cover - tests use NoopRateLimiter directly.
    _RateLimiter = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FIE_BASE = "https://fie.org"
SOURCE = "scrape_fie_satellite"
PAGE_SIZE = 1000
BATCH_SIZE = 100
EARLIEST_SEASON = int(os.environ.get("FIE_SATELLITE_EARLIEST_SEASON", "2003"))
DEFAULT_LIMIT = int(os.environ.get("FIE_SATELLITE_LIMIT", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

SEARCH_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{FIE_BASE}/competitions",
}

WEAPON_MAP = {"epee": "Epee", "foil": "Foil", "sabre": "Sabre"}
GENDER_MAP = {"men": "Men", "women": "Women"}
CATEGORY_MAP = {"senior": "Senior", "junior": "Junior", "cadet": "Cadet", "veteran": "Veteran"}

COUNTRY_MAP = {
    "_AIN": "Russia",
    "AIN_": "Russia",
    "AIN": "Russia",
    "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
    "FIE": "FIE",
    "USA": "United States",
    "US": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "GBR": "Great Britain",
    "GREAT BRITAIN": "Great Britain",
    "KOR": "South Korea",
    "KOREA": "South Korea",
    "HKG": "Hong Kong",
    "HONG KONG, CHINA": "Hong Kong",
    "HONG KONG CHINA": "Hong Kong",
    "MAC": "Macau",
    "MACAO, CHINA": "Macau",
    "MACAO CHINA": "Macau",
    "TUR": "Turkey",
    "TURKIYE": "Turkey",
    "T\u00dcRKIYE": "Turkey",
    "T\u00dcRK\u0130YE": "Turkey",
    "COTE D'IVOIRE": "Cote d'Ivoire",
    "COTE DIVOIRE": "Cote d'Ivoire",
    "DEN": "Denmark",
    "FRA": "France",
    "ITA": "Italy",
    "GER": "Germany",
    "HUN": "Hungary",
    "JPN": "Japan",
    "CHN": "China",
    "POL": "Poland",
    "ESP": "Spain",
    "BRA": "Brazil",
    "CAN": "Canada",
    "MEX": "Mexico",
    "UKR": "Ukraine",
    "ROU": "Romania",
    "CZE": "Czech Republic",
    "SVK": "Slovakia",
    "SWE": "Sweden",
    "NOR": "Norway",
    "FIN": "Finland",
    "EST": "Estonia",
    "ISR": "Israel",
    "EGY": "Egypt",
    "TUN": "Tunisia",
}

TARGET_RE = re.compile(r"\b(satellite|challenge)\b", re.IGNORECASE)


supabase = None


def discover_url_id_for_tournament(session, tournament_row: dict[str, Any], rate_limiter) -> str | None:
    from discover_competition_urls import discover_url_id_for_tournament as helper

    return helper(session, tournament_row, rate_limiter)


def _default_logger_factory():
    from run_logger import ScraperRunLogger

    return ScraperRunLogger


def _get_state(source: str, key: str) -> Any:
    from scraper_state import get_state

    return get_state(source, key)


def _set_state(source: str, key: str, value: Any) -> None:
    from scraper_state import set_state

    set_state(source, key, value)


@dataclass(frozen=True)
class ScrapeSummary:
    tournaments_written: int = 0
    results_written: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    unmatched: int = 0


class NoopRateLimiter:
    def wait(self, *args, **kwargs) -> None:
        return None

    def record_success(self, *args, **kwargs) -> None:
        return None

    def record_failure(self, *args, **kwargs) -> None:
        return None


def make_rate_limiter():
    if _RateLimiter is None:
        return NoopRateLimiter()
    return _RateLimiter(default_rps=1.0, jitter=0.15, backoff=5.0)


def get_supabase_client():
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    return text or None


def title_case(value: Any) -> str | None:
    text = clean_text(value)
    return text.title() if text else None


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )


def normalized_key(value: Any) -> str:
    text = _strip_accents(clean_text(value) or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    return COUNTRY_MAP.get(key, title_case(text))


def country_key(value: Any) -> str:
    return normalized_key(normalize_country(value) or value)


def normalize_fie_date(date_str: Any) -> str | None:
    text = clean_text(date_str)
    if not text:
        return None
    try:
        day, month, year = text.split("-")
        if len(year) != 4:
            return None
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except ValueError:
        return None


def normalize_person_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while (
        leading < len(parts)
        and any(char.isalpha() for char in parts[leading])
        and parts[leading].upper() == parts[leading]
    ):
        leading += 1
    if 0 < leading < len(parts):
        last = title_case(" ".join(parts[:leading]))
        first = title_case(" ".join(parts[leading:]))
        return first if first and last and first.casefold() == last.casefold() else f"{first} {last}"

    trailing = 0
    while (
        trailing < len(parts)
        and any(char.isalpha() for char in parts[-1 - trailing])
        and parts[-1 - trailing].upper() == parts[-1 - trailing]
    ):
        trailing += 1
    if 0 < trailing < len(parts):
        first = title_case(" ".join(parts[:-trailing]))
        last = title_case(" ".join(parts[-trailing:]))
        return first if first and last and first.casefold() == last.casefold() else f"{first} {last}"
    return title_case(text)


def to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def normalize_fie_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = clean_text(value)
    if not text:
        return None
    number = to_int(text)
    return str(number) if number is not None else text


def target_series(comp: dict[str, Any]) -> str | None:
    fields = [
        comp.get("level"),
        comp.get("competitionCategory"),
        comp.get("categoryName"),
        comp.get("name"),
    ]
    haystack = " ".join(clean_text(field) or "" for field in fields)
    match = TARGET_RE.search(haystack)
    if not match:
        return None
    return match.group(1).casefold()


def is_satellite_challenge_competition(comp: dict[str, Any]) -> bool:
    return target_series(comp) in {"satellite", "challenge"}


def filter_satellite_challenge_competitions(competitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [comp for comp in competitions if is_satellite_challenge_competition(comp)]


def should_check_result_page(comp: dict[str, Any]) -> bool:
    if not is_satellite_challenge_competition(comp):
        return bool(comp.get("hasResults"))
    return bool(comp.get("hasResults")) or bool(normalize_fie_date(comp.get("endDate")))


def fie_source_id(comp: dict[str, Any], season: int) -> str:
    competition_id = normalize_fie_id(comp.get("competitionId")) or clean_text(comp.get("id")) or "unknown"
    return f"fie:satellite_challenge:{season}:{competition_id}"


def _mapped_value(mapping: dict[str, str], value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return mapping.get(text.casefold(), text)


def competition_to_tournament_row(comp: dict[str, Any], season: int) -> dict[str, Any]:
    competition_id = normalize_fie_id(comp.get("competitionId"))
    start_date = normalize_fie_date(comp.get("startDate"))
    end_date = normalize_fie_date(comp.get("endDate"))
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date
    source_url = f"{FIE_BASE}/competitions/{season}/{competition_id}" if competition_id else None
    series = target_series(comp)

    return {
        "source_id": fie_source_id(comp, season),
        "fie_id": to_int(competition_id) if competition_id and competition_id.isdigit() else competition_id,
        "competition_url_id": competition_id,
        "name": clean_text(comp.get("name")),
        "season": str(season),
        "country": normalize_country(comp.get("country")),
        "location": clean_text(comp.get("location")),
        "start_date": start_date,
        "end_date": end_date,
        "weapon": _mapped_value(WEAPON_MAP, comp.get("weapon")),
        "gender": _mapped_value(GENDER_MAP, comp.get("gender")),
        "category": _mapped_value(CATEGORY_MAP, comp.get("category")),
        "type": clean_text(comp.get("type")),
        "source_url": source_url,
        "has_results": bool(comp.get("hasResults")) or should_check_result_page(comp),
        "metadata": {
            "scraped_by": SOURCE,
            "source": "fie",
            "target_series": series,
            "source_has_results": comp.get("hasResults"),
            "fie_level": comp.get("level"),
            "competition_category": comp.get("competitionCategory"),
            "raw_country": comp.get("country"),
            "result_probe_required": should_check_result_page(comp) and not bool(comp.get("hasResults")),
        },
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(f"{FIE_BASE}/competitions", timeout=15)
    except requests.RequestException as exc:
        print(f"  Warning: FIE session setup failed: {exc}")
    return session


def _wait(rate_limiter, domain: str = "fie.org") -> None:
    try:
        rate_limiter.wait(domain)
    except TypeError:
        rate_limiter.wait()


def _record_success(rate_limiter, domain: str = "fie.org") -> None:
    if hasattr(rate_limiter, "record_success"):
        rate_limiter.record_success(domain)


def _record_failure(rate_limiter, domain: str = "fie.org") -> None:
    if hasattr(rate_limiter, "record_failure"):
        rate_limiter.record_failure(domain)


def fetch_competitions(
    session: requests.Session,
    season: int,
    *,
    from_date: str = "",
    to_date: str = "",
    max_pages: int = 20,
    rate_limiter=None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    limiter = rate_limiter or NoopRateLimiter()
    for page in range(1, max_pages + 1):
        payload = {
            "name": "",
            "status": "passed",
            "gender": [],
            "weapon": [],
            "type": [],
            "season": season,
            "level": "",
            "competitionCategory": "",
            "fromDate": from_date,
            "toDate": to_date,
            "fetchPage": page,
        }
        try:
            _wait(limiter)
            response = session.post(
                f"{FIE_BASE}/competitions/search",
                headers=SEARCH_HEADERS,
                json=payload,
                timeout=20,
            )
            if response.status_code != 200 or not response.text.strip():
                print(f"    FIE search HTTP {response.status_code}: season={season} page={page}")
                _record_failure(limiter)
                break
            data = response.json()
            items = data.get("items") or []
            if not items:
                break
            results.extend(item for item in items if isinstance(item, dict))
            page_size = max(to_int(data.get("pageSize")) or len(items), 1)
            if len(items) < page_size:
                break
            _record_success(limiter)
        except (requests.RequestException, ValueError) as exc:
            print(f"    FIE search failed: season={season} page={page}: {exc}")
            _record_failure(limiter)
            break
    return results


def fetch_competitions_by_month(
    session: requests.Session,
    season: int,
    *,
    rate_limiter=None,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for month in range(1, 13):
        from_date = f"{season}-{month:02d}-01"
        to_date = f"{season}-{month:02d}-{calendar.monthrange(season, month)[1]}"
        for comp in fetch_competitions(
            session,
            season,
            from_date=from_date,
            to_date=to_date,
            max_pages=5,
            rate_limiter=rate_limiter,
        ):
            competition_id = normalize_fie_id(comp.get("competitionId"))
            if competition_id:
                by_id[competition_id] = comp
        time.sleep(0.1)
    return list(by_id.values())


def fetch_target_competitions(session: requests.Session, season: int, *, rate_limiter=None) -> list[dict[str, Any]]:
    competitions = fetch_competitions(session, season, rate_limiter=rate_limiter)
    if not competitions:
        competitions = fetch_competitions_by_month(session, season, rate_limiter=rate_limiter)
    return filter_satellite_challenge_competitions(competitions)


def extract_window_blocks(html: str) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    decoder = json.JSONDecoder()
    for match in re.finditer(r"window\.(?P<name>[_A-Za-z0-9]+)\s*=\s*", html or ""):
        offset = match.end()
        while offset < len(html) and html[offset].isspace():
            offset += 1
        if offset >= len(html) or html[offset] not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(html[offset:])
        except json.JSONDecodeError:
            continue
        blocks[match.group("name")] = value
    return blocks


def _result_row_score(rows: Any) -> int:
    if not isinstance(rows, list):
        return 0
    return sum(
        1
        for row in rows
        if isinstance(row, dict) and clean_text(row.get("name")) and to_int(row.get("rank")) is not None
    )


def _candidate_rows_from_value(value: Any) -> list[list[dict[str, Any]]]:
    candidates: list[list[dict[str, Any]]] = []
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list):
            candidates.append([row for row in rows if isinstance(row, dict)])
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                candidates.extend(_candidate_rows_from_value(nested))
    elif isinstance(value, list):
        if value and all(isinstance(row, dict) for row in value):
            candidates.append(value)
        for nested in value:
            if isinstance(nested, (dict, list)):
                candidates.extend(_candidate_rows_from_value(nested))
    return candidates


def candidate_result_rows(window_blocks: dict[str, Any]) -> list[dict[str, Any]]:
    best_rows: list[dict[str, Any]] = []
    best_score = 0
    for value in window_blocks.values():
        for rows in _candidate_rows_from_value(value):
            score = _result_row_score(rows)
            if score > best_score:
                best_score = score
                best_rows = rows
    return best_rows


def fetch_result_rows(
    session: requests.Session,
    season: int,
    competition_url_id: Any,
    rate_limiter=None,
) -> list[dict[str, Any]]:
    competition_id = normalize_fie_id(competition_url_id)
    if not competition_id:
        return []
    limiter = rate_limiter or NoopRateLimiter()
    url = f"{FIE_BASE}/competitions/{season}/{competition_id}"
    try:
        _wait(limiter)
        response = session.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if response.status_code != 200 or not response.text.strip():
            print(f"    FIE result page HTTP {response.status_code}: {url}")
            _record_failure(limiter)
            return []
        rows = candidate_result_rows(extract_window_blocks(response.text))
        _record_success(limiter)
        return rows
    except requests.RequestException as exc:
        print(f"    FIE result fetch failed {url}: {exc}")
        _record_failure(limiter)
        return []


def _add_index(index: dict[Any, list[dict[str, Any]]], key: Any, candidate: dict[str, Any]) -> None:
    if key is not None:
        index.setdefault(key, []).append(candidate)


def _first_row_id(row_ids: Any) -> str | None:
    if isinstance(row_ids, list):
        for row_id in row_ids:
            text = clean_text(row_id)
            if text:
                return text
    return clean_text(row_ids)


def _candidate(candidate_id: Any, *, fie_id: Any = None, name: Any = None, country: Any = None, tier: str) -> dict[str, Any] | None:
    fencer_id = clean_text(candidate_id)
    if not fencer_id:
        return None
    return {
        "id": fencer_id,
        "fie_id": normalize_fie_id(fie_id),
        "name": clean_text(name),
        "country": normalize_country(country),
        "tier": tier,
    }


def build_fencer_index(
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]] | None = None,
) -> dict[str, dict[Any, list[dict[str, Any]]]]:
    index: dict[str, dict[Any, list[dict[str, Any]]]] = {
        "by_fie_id": {},
        "by_identity_name_country": {},
        "by_name_country": {},
    }

    for row in fencers:
        candidate = _candidate(
            row.get("id"),
            fie_id=row.get("fie_id"),
            name=row.get("name"),
            country=row.get("country"),
            tier="fencer",
        )
        if not candidate:
            continue
        if candidate.get("fie_id"):
            _add_index(index["by_fie_id"], candidate["fie_id"], candidate)
        if candidate.get("name") and candidate.get("country"):
            key = (normalized_key(candidate["name"]), country_key(candidate["country"]))
            _add_index(index["by_name_country"], key, candidate)

    for row in identities or []:
        row_id = _first_row_id(row.get("fs_fencer_row_ids"))
        candidate = _candidate(
            row_id,
            name=row.get("canonical_name"),
            country=row.get("country"),
            tier="identity",
        )
        if not candidate:
            continue
        for fie_id in row.get("fie_ids") or []:
            normalized = normalize_fie_id(fie_id)
            if normalized:
                fie_candidate = dict(candidate)
                fie_candidate["fie_id"] = normalized
                _add_index(index["by_fie_id"], normalized, fie_candidate)
        if candidate.get("name") and candidate.get("country"):
            key = (normalized_key(candidate["name"]), country_key(candidate["country"]))
            _add_index(index["by_identity_name_country"], key, candidate)
    return index


def _resolve_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_id = {candidate["id"]: candidate for candidate in candidates if candidate.get("id")}
    unique = list(by_id.values())
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    fie_ids = {candidate.get("fie_id") for candidate in unique if candidate.get("fie_id")}
    if len(fie_ids) == 1:
        return sorted(unique, key=lambda candidate: candidate["id"])[0]
    return None


def match_fencer(row: dict[str, Any], fencer_index: dict[str, dict[Any, list[dict[str, Any]]]]) -> tuple[str | None, str | None]:
    fie_id = normalize_fie_id(row.get("fencerId") or row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id:
        candidate = _resolve_candidates(fencer_index["by_fie_id"].get(fie_id, []))
        if candidate:
            return candidate["id"], "fie_id"

    name = normalize_person_name(row.get("name"))
    country = normalize_country(row.get("country") or row.get("nationality"))
    if name and country:
        key = (normalized_key(name), country_key(country))
        candidate = _resolve_candidates(fencer_index["by_identity_name_country"].get(key, []))
        if candidate:
            return candidate["id"], "identity_name_country"
        candidate = _resolve_candidates(fencer_index["by_name_country"].get(key, []))
        if candidate:
            return candidate["id"], "name_country"
    return None, None


def dedupe_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        fencer_key = row.get("fencer_id") or row.get("fie_fencer_id") or row.get("name")
        key = (row.get("tournament_id"), fencer_key, row.get("rank"))
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def parse_result_rows(
    *,
    tournament_id: str,
    raw_rows: list[dict[str, Any]],
    fencer_index: dict[str, dict[Any, list[dict[str, Any]]]],
    source_url: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parsed: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for raw in raw_rows or []:
        if not isinstance(raw, dict):
            continue
        rank = to_int(raw.get("rank"))
        name = normalize_person_name(raw.get("name"))
        if rank is None or not name:
            continue

        fencer_id, match_tier = match_fencer(raw, fencer_index)
        fie_id = normalize_fie_id(raw.get("fencerId") or raw.get("fie_fencer_id") or raw.get("fie_id"))
        country = normalize_country(raw.get("country") or raw.get("nationality"))
        if not fencer_id:
            unmatched.append(
                {
                    "tournament_id": tournament_id,
                    "name": name,
                    "country": country,
                    "fie_fencer_id": fie_id,
                    "rank": rank,
                    "reason": "no_fencer_match",
                    "source_url": source_url,
                }
            )
            continue

        parsed.append(
            {
                "tournament_id": tournament_id,
                "fencer_id": fencer_id,
                "fie_fencer_id": fie_id,
                "name": name,
                "nationality": normalize_country(raw.get("nationality")),
                "country": country,
                "rank": rank,
                "placement": rank,
                "victory": to_int(raw.get("victory")),
                "matches": to_int(raw.get("matches")),
                "td": to_int(raw.get("td")),
                "tr": to_int(raw.get("tr")),
                "diff": to_int(raw.get("diff")),
                "metadata": {
                    "source": SOURCE,
                    "source_url": source_url,
                    "raw_name": clean_text(raw.get("name")),
                    "raw_country": clean_text(raw.get("country") or raw.get("nationality")),
                    "fencer_match_tier": match_tier,
                },
            }
        )
    return dedupe_result_rows(parsed), unmatched


def fetch_paginated(client, table_name: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = client.table(table_name).select(columns).range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def fetch_fencer_rows(client) -> list[dict[str, Any]]:
    return fetch_paginated(client, "fs_fencers", "id,fie_id,name,country")


def fetch_identity_rows(client) -> list[dict[str, Any]]:
    try:
        return fetch_paginated(
            client,
            "fs_fencer_identities",
            "id,canonical_name,country,fie_ids,fs_fencer_row_ids",
        )
    except Exception as exc:
        print(f"  Identity table unavailable; matching without identities: {exc}")
        return []


def resolve_competition_url_id(session, tournament_row: dict[str, Any], rate_limiter) -> str | None:
    discovered = discover_url_id_for_tournament(session, tournament_row, rate_limiter)
    return normalize_fie_id(discovered or tournament_row.get("competition_url_id") or tournament_row.get("fie_id"))


def fetch_tournament_id_map(client, source_ids: list[str]) -> dict[str, str]:
    id_map: dict[str, str] = {}
    if not source_ids:
        return id_map
    for i in range(0, len(source_ids), BATCH_SIZE):
        batch = source_ids[i : i + BATCH_SIZE]
        rows = client.table("fs_tournaments").select("id,source_id").in_("source_id", batch).execute().data or []
        for row in rows:
            if row.get("source_id") and row.get("id"):
                id_map[row["source_id"]] = row["id"]
    return id_map


def _insert_missing_tournament_rows(client, rows: list[dict[str, Any]]) -> None:
    existing = fetch_tournament_id_map(client, [row["source_id"] for row in rows if row.get("source_id")])
    new_rows = [row for row in rows if row.get("source_id") not in existing]
    for i in range(0, len(new_rows), BATCH_SIZE):
        client.table("fs_tournaments").insert(new_rows[i : i + BATCH_SIZE]).execute()


def upsert_tournament_rows(client, rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {}
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            client.table("fs_tournaments").upsert(batch, on_conflict="source_id").execute()
    except Exception as exc:
        message = str(exc).lower()
        if "no unique" in message or "no exclusion" in message or ("constraint" in message and "on conflict" in message):
            print(f"  Tournament upsert unsupported for source_id; inserting missing rows: {exc}")
            _insert_missing_tournament_rows(client, rows)
        else:
            print(f"  Tournament upsert failed; retrying without fie_id: {exc}")
            fallback_rows = []
            for row in rows:
                fallback = dict(row)
                fallback["fie_id"] = None
                fallback_rows.append(fallback)
            for i in range(0, len(fallback_rows), BATCH_SIZE):
                client.table("fs_tournaments").upsert(
                    fallback_rows[i : i + BATCH_SIZE],
                    on_conflict="source_id",
                ).execute()
    return fetch_tournament_id_map(client, [row["source_id"] for row in rows if row.get("source_id")])


def replace_results(client, tournament_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    old_rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table("fs_results")
            .select("*")
            .eq("tournament_id", tournament_id)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        old_rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            client.table("fs_results").insert(rows[i : i + BATCH_SIZE]).execute()
    except Exception as exc:
        print(f"  Results insert failed for {tournament_id}; restoring old rows: {exc}")
        client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
        for i in range(0, len(old_rows), BATCH_SIZE):
            client.table("fs_results").insert(old_rows[i : i + BATCH_SIZE]).execute()
        return 0
    return len(rows)


def remember_done_competition(source_id: str) -> None:
    done = {str(value) for value in (_get_state(SOURCE, "done_competition_source_ids") or [])}
    done.add(source_id)
    _set_state(SOURCE, "done_competition_source_ids", sorted(done))


def write_summary_state(summary: ScrapeSummary, unmatched_samples: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _set_state(
        SOURCE,
        "summary",
        {
            "completed_at": now,
            "tournaments_written": summary.tournaments_written,
            "results_written": summary.results_written,
            "processed": summary.processed,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "unmatched": summary.unmatched,
            "unmatched_samples": unmatched_samples[:25],
        },
    )


def log_unmatched_rows(unmatched: list[dict[str, Any]], tournament_name: str | None = None) -> None:
    for row in unmatched[:25]:
        label = tournament_name or row.get("tournament_id")
        print(
            "    Unmatched FIE result row "
            f"tournament={label} rank={row.get('rank')} "
            f"name={row.get('name')} country={row.get('country')} "
            f"fie_fencer_id={row.get('fie_fencer_id')} reason={row.get('reason')}"
        )
    if len(unmatched) > 25:
        print(f"    ... {len(unmatched) - 25} additional unmatched rows omitted from stdout")


def season_range(current_year: int | None = None) -> list[int]:
    current = current_year or datetime.now(timezone.utc).year
    return list(range(EARLIEST_SEASON, current + 1))


def process_competitions(
    *,
    client,
    session,
    competitions: list[dict[str, Any]],
    season: int,
    fencer_index: dict[str, dict[Any, list[dict[str, Any]]]],
    rate_limiter=None,
    limit: int = 0,
    update_state: bool = True,
) -> tuple[ScrapeSummary, list[dict[str, Any]]]:
    limiter = rate_limiter or NoopRateLimiter()
    rows = [competition_to_tournament_row(comp, season) for comp in competitions]
    id_map = upsert_tournament_rows(client, rows)
    tournaments_written = len(rows)
    results_written = failed = skipped = unmatched_count = 0
    unmatched_samples: list[dict[str, Any]] = []
    done = {str(value) for value in (_get_state(SOURCE, "done_competition_source_ids") or [])} if update_state else set()
    processed = 0

    for comp, tournament_row in zip(competitions, rows):
        if limit and processed >= limit:
            skipped += 1
            continue

        source_id = tournament_row["source_id"]
        if source_id in done:
            skipped += 1
            continue

        tournament_id = id_map.get(source_id)
        if not tournament_id:
            print(f"  Missing tournament id for {source_id}")
            failed += 1
            continue

        processed += 1
        url_id = resolve_competition_url_id(session, tournament_row, limiter)
        if not url_id:
            print(f"  Missing competition URL id for {tournament_row.get('name') or source_id}")
            skipped += 1
            continue

        source_url = f"{FIE_BASE}/competitions/{season}/{url_id}"
        client.table("fs_tournaments").update(
            {
                "competition_url_id": url_id,
                "source_url": source_url,
            }
        ).eq("id", tournament_id).execute()

        if not should_check_result_page(comp):
            skipped += 1
            continue

        raw_rows = fetch_result_rows(session, season, url_id, limiter)
        if not raw_rows:
            skipped += 1
            continue

        result_rows, unmatched = parse_result_rows(
            tournament_id=tournament_id,
            raw_rows=raw_rows,
            fencer_index=fencer_index,
            source_url=source_url,
        )
        if unmatched:
            unmatched_count += len(unmatched)
            unmatched_samples.extend(unmatched)
            log_unmatched_rows(unmatched, tournament_row.get("name"))

        if not result_rows:
            skipped += 1
            continue

        written = replace_results(client, tournament_id, result_rows)
        if written != len(result_rows):
            failed += 1
            continue

        results_written += written
        client.table("fs_tournaments").update(
            {
                "has_results": True,
                "results_check_failures": 0,
                "results_unavailable": False,
            }
        ).eq("id", tournament_id).execute()
        if update_state:
            remember_done_competition(source_id)

    return (
        ScrapeSummary(
            tournaments_written=tournaments_written,
            results_written=results_written,
            processed=processed,
            failed=failed,
            skipped=skipped,
            unmatched=unmatched_count,
        ),
        unmatched_samples,
    )


def combine_summaries(summaries: list[ScrapeSummary]) -> ScrapeSummary:
    return ScrapeSummary(
        tournaments_written=sum(summary.tournaments_written for summary in summaries),
        results_written=sum(summary.results_written for summary in summaries),
        processed=sum(summary.processed for summary in summaries),
        failed=sum(summary.failed for summary in summaries),
        skipped=sum(summary.skipped for summary in summaries),
        unmatched=sum(summary.unmatched for summary in summaries),
    )


def scrape_fie_satellite(
    *,
    client=None,
    session=None,
    seasons: list[int] | None = None,
    limit: int = DEFAULT_LIMIT,
    logger_factory=None,
    rate_limiter=None,
    log_run: bool = True,
    update_state: bool = True,
) -> ScrapeSummary:
    if log_run and logger_factory is None:
        logger_factory = _default_logger_factory()
    run_log = logger_factory(SOURCE).start() if log_run else None
    try:
        db = client or get_supabase_client()
        http = session or make_session()
        limiter = rate_limiter or make_rate_limiter()

        fencer_index = build_fencer_index(fetch_fencer_rows(db), fetch_identity_rows(db))
        requested_seasons = seasons or season_range()
        summaries: list[ScrapeSummary] = []
        unmatched_samples: list[dict[str, Any]] = []
        remaining_limit = limit

        for season in requested_seasons:
            print(f"FIE Satellite/Challenge season {season}")
            competitions = fetch_target_competitions(http, season, rate_limiter=limiter)
            if not competitions:
                summaries.append(ScrapeSummary(skipped=1))
                continue
            season_summary, season_unmatched = process_competitions(
                client=db,
                session=http,
                competitions=competitions,
                season=season,
                fencer_index=fencer_index,
                rate_limiter=limiter,
                limit=remaining_limit,
                update_state=update_state,
            )
            summaries.append(season_summary)
            unmatched_samples.extend(season_unmatched)
            if limit:
                remaining_limit = max(0, remaining_limit - season_summary.processed)
                if remaining_limit == 0:
                    break

        summary = combine_summaries(summaries)
        if update_state:
            write_summary_state(summary, unmatched_samples)
        if run_log:
            run_log.complete(
                written=summary.results_written,
                failed=summary.failed,
                skipped=summary.skipped,
                metadata={
                    "tournaments_written": summary.tournaments_written,
                    "processed": summary.processed,
                    "unmatched": summary.unmatched,
                    "unmatched_samples": unmatched_samples[:25],
                },
            )
        print(
            "Done - "
            f"tournaments={summary.tournaments_written}, results={summary.results_written}, "
            f"failed={summary.failed}, skipped={summary.skipped}, unmatched={summary.unmatched}"
        )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> ScrapeSummary:
    return scrape_fie_satellite()


if __name__ == "__main__":
    main()
