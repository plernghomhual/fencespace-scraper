"""
Veteran fencing circuit and championship result scraper.

Probe summary (2026-06-02):
  - EVF 2025 Plovdiv results expose static HTML medal rows by weapon and
    Category 1-4 veteran age bucket.
  - EVF circuit/ranking pages and FencingTimeLive schedules are public, but
    current FencingTimeLive result pages require login.
  - FIE veteran entry PDFs are public entry lists, not result tables. FIE
    veteran events can report hasResults=0 even when result sources exist.
"""
from __future__ import annotations

import csv
import os
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

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

SOURCE = "scrape_veterans"
REQUEST_DELAY = float(os.environ.get("VETERANS_REQUEST_DELAY", "0.5"))
BATCH_SIZE = 100
DEFAULT_UNMATCHED_LOG = Path(os.environ.get("VETERANS_UNMATCHED_LOG", "tasks/unmatched_veterans.tsv"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,*/*;q=0.8",
}

EVF_RESULT_SOURCES = [
    {
        "url": "https://www.veteransfencing.eu/fencing/results/ec2025/",
        "source_kind": "evf_static_results",
    },
]

NO_PUBLIC_RESULT_PROBES = [
    "https://www.fencingtimelive.com/tournaments/eventSchedule/98F13C10A47B49FFA2D39E4D47F1EDA8",
    "https://www.veteransfencing.eu/fencing/rankings/",
    "https://www.veteransfencing.eu/fencing/circuit/",
    "https://www.fie.org/competition/2025/1106/entry/pdf?lang=en",
]

COUNTRY_ALIASES = {
    "_AIN": "AIN",
    "A I N": "AIN",
    "USA": "USA",
    "UNITED STATES": "USA",
    "US": "USA",
    "GREAT BRITAIN": "GBR",
    "BRITAIN": "GBR",
    "ENGLAND": "GBR",
}

AGE_CATEGORY_MAP = {
    "category 1": ("V1", "Veteran 40-49"),
    "cat 1": ("V1", "Veteran 40-49"),
    "v1": ("V1", "Veteran 40-49"),
    "40": ("V1", "Veteran 40-49"),
    "40-49": ("V1", "Veteran 40-49"),
    "50": ("V2", "Veteran 50-59"),
    "50-59": ("V2", "Veteran 50-59"),
    "category 2": ("V2", "Veteran 50-59"),
    "cat 2": ("V2", "Veteran 50-59"),
    "v2": ("V2", "Veteran 50-59"),
    "60": ("V3", "Veteran 60-69"),
    "60-69": ("V3", "Veteran 60-69"),
    "category 3": ("V3", "Veteran 60-69"),
    "cat 3": ("V3", "Veteran 60-69"),
    "v3": ("V3", "Veteran 60-69"),
    "70": ("V4", "Veteran 70+"),
    "70+": ("V4", "Veteran 70+"),
    "category 4": ("V4", "Veteran 70+"),
    "cat 4": ("V4", "Veteran 70+"),
    "v4": ("V4", "Veteran 70+"),
}

WEAPON_PATTERNS = [
    (re.compile(r"\bepee\b|\bepee\b|\bszpada\b|\bed\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b|\bfleuret\b|\bfloret\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b|\bszabla\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen's\b|\bdames\b|\bfemmes\b|\bkobiet\b|\bfemale\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen's\b|\bhommes\b|\bmezczyzn\b|\bmale\b", re.I), "Men"),
]

AMBIGUOUS = object()


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2019", "'").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _fold(value: Any) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower()


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "").strip()
    return COUNTRY_ALIASES.get(key, key if re.fullmatch(r"_?[A-Z]{3}", key) else text)


def _title_part(part: str) -> str:
    return "-".join(piece.capitalize() for piece in part.split("-"))


def format_fencer_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        text = f"{first} {last}".strip()
    parts = text.split()
    surname_parts: list[str] = []
    given_parts: list[str] = []
    for part in parts:
        letters = re.sub(r"[^A-Za-z'\-]", "", _fold(part))
        if not given_parts and letters and part.upper() == part:
            surname_parts.append(part)
        else:
            given_parts.append(part)
    if surname_parts and given_parts:
        parts = given_parts + surname_parts
    return " ".join(_title_part(part) for part in parts)


def normalize_name_key(value: Any) -> str | None:
    name = format_fencer_name(value) or clean_text(value)
    if not name:
        return None
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    folded = re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()
    return folded or None


def _normalize_age_category(value: Any) -> tuple[str | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None
    folded = _fold(text)
    match = re.search(r"\bcategory\s*([1-4])\b|\bcat\s*([1-4])\b|\bv\s*([1-4])\b", folded)
    if match:
        key = f"category {next(group for group in match.groups() if group)}"
        return AGE_CATEGORY_MAP[key]
    match = re.search(r"\b(40|50|60|70)(?:\s*[-+]\s*(49|59|69))?\b", folded)
    if match:
        key = f"{match.group(1)}-{match.group(2)}" if match.group(2) else match.group(1)
        return AGE_CATEGORY_MAP.get(key, AGE_CATEGORY_MAP.get(match.group(1), (None, None)))
    return None, None


def _classify_weapon_gender(value: Any) -> tuple[str | None, str | None]:
    folded = _fold(value)
    weapon = next((parsed for pattern, parsed in WEAPON_PATTERNS if pattern.search(folded)), None)
    gender = next((parsed for pattern, parsed in GENDER_PATTERNS if pattern.search(folded)), None)
    return weapon, gender


def _medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _extract_year(value: Any) -> str | None:
    match = re.search(r"\b((?:19|20)\d{2})\b", clean_text(value) or "")
    return match.group(1) if match else None


def _slug(value: Any) -> str:
    folded = normalize_name_key(value) or ""
    return folded.replace(" ", "-")


def _parse_result_line(line: str) -> dict[str, Any] | None:
    match = re.match(r"^(?P<rank>\d+)\s+(?P<body>.+?)\s+(?P<country>_?[A-Z]{3})(?:\s+(?P<trailing>.*))?$", line)
    if not match:
        return None
    rank = int(match.group("rank"))
    body = clean_text(match.group("body"))
    country = normalize_country(match.group("country"))
    trailing = clean_text(match.group("trailing"))
    points = None
    if trailing:
        numeric = re.search(r"[-+]?\d+(?:[,.]\d+)?", trailing)
        if numeric:
            points = float(numeric.group(0).replace(",", "."))
    name = format_fencer_name(body)
    if not name or not country:
        return None
    return {
        "rank": rank,
        "fencer": name,
        "country": country,
        "club": None,
        "points": points,
        "medal": _medal_for_rank(rank),
        "fie_id": None,
    }


def parse_evf_results_page(html: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    lines_raw = [clean_text(line) for line in soup.get_text("\n").splitlines()]
    lines: list[str] = [line for line in lines_raw if line is not None]

    tournament = next((line for line in lines if re.search(r"\bchampionships?\b.*\b(19|20)\d{2}\b", line, re.I)), None)
    tournament = tournament or "EVF Veteran Results"
    season = _extract_year(tournament)

    events: list[dict[str, Any]] = []
    current_weapon = None
    current_gender = None
    current_event: dict[str, Any] | None = None

    for line in lines:
        weapon, gender = _classify_weapon_gender(line)
        if weapon and gender and not re.match(r"^\d+\s+", line):
            current_weapon = weapon
            current_gender = gender
            current_event = None
            continue

        age_code, age_label = _normalize_age_category(line)
        if age_code and age_label and current_weapon and current_gender:
            event_code = f"evf-{season or 'unknown'}-{current_gender.lower()}-{current_weapon.lower()}-{age_code.lower()}"
            current_event = {
                "source_id": f"veterans:{event_code}",
                "event_code": event_code,
                "tournament": tournament,
                "event_name": f"{current_gender} {current_weapon} {age_label}",
                "season": season,
                "date": None,
                "weapon": current_weapon,
                "gender": current_gender,
                "age_category": age_code,
                "category": age_label,
                "source_url": source_url,
                "source_kind": "evf_static_results",
                "results": [],
                "metadata": {
                    "source": SOURCE,
                    "source_url": source_url,
                    "category_family": "Veteran",
                    "age_category": age_code,
                    "raw_category": line,
                },
            }
            events.append(current_event)
            continue

        row = _parse_result_line(line)
        if row and current_event:
            current_event["results"].append(row)

    return [event for event in events if event["results"]]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def should_attempt_fie_results(competition: dict[str, Any]) -> bool:
    if _truthy(competition.get("hasResults")):
        return True
    category = _fold(competition.get("category"))
    if "veteran" in category and clean_text(competition.get("endDate")):
        return True
    return False


def probe_source_text(text: str, url: str) -> dict[str, Any]:
    folded = _fold(text)
    if "need to be logged in" in folded or "you need to be logged in" in folded:
        return {
            "url": url,
            "status": "blocked",
            "reason": "login_required",
            "result_rows_available": False,
        }
    if "number fencer entered" in folded and "date inscription" in folded:
        return {
            "url": url,
            "status": "skipped",
            "reason": "entry_list_not_results",
            "result_rows_available": False,
        }
    if "dropbox" in folded and "official results" in folded:
        return {
            "url": url,
            "status": "blocked",
            "reason": "external_result_pdf_not_fetchable",
            "result_rows_available": False,
        }
    if "ranking lists are compiled" in folded and not re.search(r"\b\d+\s+[A-Z][A-Z'\-]+\s+", text or ""):
        return {
            "url": url,
            "status": "skipped",
            "reason": "no_public_result_rows",
            "result_rows_available": False,
        }
    return {
        "url": url,
        "status": "available",
        "reason": "public_text",
        "result_rows_available": True,
    }


def _add_unique(mapping: dict[Any, Any], key: Any, value: Any, *, allow_duplicate_same_person: bool = False) -> None:
    if not key or not value:
        return
    current = mapping.get(key)
    if current is None:
        mapping[key] = value
        return
    if current == value:
        return
    if allow_duplicate_same_person:
        return
    mapping[key] = AMBIGUOUS


def build_fencer_index(
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]] | None = None,
) -> dict[str, dict[Any, Any]]:
    by_fie: dict[str, Any] = {}
    by_name_country: dict[tuple[str, str], Any] = {}

    for identity in identities or []:
        row_ids = [clean_text(row_id) for row_id in identity.get("fs_fencer_row_ids") or [] if clean_text(row_id)]
        row_id = row_ids[0] if row_ids else clean_text(identity.get("id"))
        if not row_id:
            continue
        country = normalize_country(identity.get("country"))
        name_key = normalize_name_key(identity.get("canonical_name"))
        if name_key and country:
            _add_unique(by_name_country, (name_key, country), row_id)
        for fie_id in identity.get("fie_ids") or []:
            fie_key = clean_text(fie_id)
            _add_unique(by_fie, fie_key, row_id, allow_duplicate_same_person=True)

    for fencer in fencers:
        row_id = clean_text(fencer.get("id"))
        if not row_id:
            continue
        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id:
            _add_unique(by_fie, fie_id, row_id, allow_duplicate_same_person=True)
        country = normalize_country(fencer.get("country") or fencer.get("nationality"))
        name_key = normalize_name_key(fencer.get("name"))
        if name_key and country:
            _add_unique(by_name_country, (name_key, country), row_id)

    return {"by_fie": by_fie, "by_name_country": by_name_country}


def _match_fencer(row: dict[str, Any], index: dict[str, dict[Any, Any]]) -> tuple[str | None, str | None]:
    fie_id = clean_text(row.get("fie_id") or row.get("fie_fencer_id"))
    if fie_id:
        matched = index["by_fie"].get(fie_id)
        if matched and matched is not AMBIGUOUS:
            return matched, "tier_1_fie_id"

    name = row.get("fencer") or row.get("name")
    country = normalize_country(row.get("country") or row.get("nationality"))
    name_key = normalize_name_key(name)
    if name_key and country:
        matched = index["by_name_country"].get((name_key, country))
        if matched and matched is not AMBIGUOUS:
            return matched, "tier_2_canonical_name_country"
    return None, None


def attach_fencer_matches(
    rows: list[dict[str, Any]],
    index: dict[str, dict[Any, Any]],
    source_url: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matched_rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for row in rows:
        fencer_id, tier = _match_fencer(row, index)
        if not fencer_id:
            unmatched.append(
                {
                    "name": row.get("fencer") or row.get("name"),
                    "country": normalize_country(row.get("country") or row.get("nationality")),
                    "fie_id": clean_text(row.get("fie_id") or row.get("fie_fencer_id")),
                    "source_url": source_url,
                    "reason": "no_conservative_match",
                }
            )
            continue
        copied = dict(row)
        metadata = dict(copied.get("metadata") or {})
        metadata["match_tier"] = tier
        if source_url:
            metadata["source_url"] = source_url
        copied["fencer_id"] = fencer_id
        copied["metadata"] = metadata
        matched_rows.append(copied)
    return matched_rows, unmatched


def write_unmatched_log(path: Path, unmatched: list[dict[str, Any]]) -> None:
    if not unmatched:
        return
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        if write_header:
            writer.writerow(["name", "country", "fie_id", "source_url", "reason"])
        for row in unmatched:
            writer.writerow(
                [
                    row.get("name") or "",
                    row.get("country") or "",
                    row.get("fie_id") or "",
                    row.get("source_url") or "",
                    row.get("reason") or "",
                ]
            )


def _fetch_all(client: Any, table: str, columns: str, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        result = client.table(table).select(columns).range(start, start + page_size - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def fetch_fencer_index(client: Any) -> dict[str, dict[Any, Any]]:
    fencers = _fetch_all(client, "fs_fencers", "id,fie_id,name,country,nationality")
    try:
        identities = _fetch_all(
            client,
            "fs_fencer_identities",
            "id,canonical_name,country,fie_ids,fs_fencer_row_ids",
        )
    except Exception:
        identities = []
    return build_fencer_index(fencers, identities)


def build_tournament_row(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": event["source_id"],
        "name": f"{event['tournament']} - {event['event_name']}"[:180],
        "season": event.get("season"),
        "start_date": event.get("date"),
        "end_date": event.get("date"),
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("category"),
        "type": "veteran_circuit",
        "country": None,
        "has_results": True,
        "metadata": {
            **(event.get("metadata") or {}),
            "event_code": event.get("event_code"),
            "event_name": event.get("event_name"),
            "tournament": event.get("tournament"),
            "source_kind": event.get("source_kind"),
        },
    }


def upsert_tournament(client: Any, event: dict[str, Any]) -> str | None:
    row = build_tournament_row(event)
    result = client.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
    return result.data[0]["id"] if result.data else None


def _result_db_row(tournament_id: str, event: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        **(row.get("metadata") or {}),
        "source": SOURCE,
        "source_url": event.get("source_url"),
        "age_category": event.get("age_category"),
        "category": event.get("category"),
        "category_family": "Veteran",
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "club": row.get("club"),
        "points": row.get("points"),
        "fie_id": row.get("fie_id"),
    }
    return {
        "tournament_id": tournament_id,
        "name": row.get("fencer") or row.get("name"),
        "nationality": normalize_country(row.get("country") or row.get("nationality")),
        "rank": row.get("rank"),
        "medal": row.get("medal"),
        "fencer_id": row["fencer_id"],
        "metadata": metadata,
    }


def upsert_results(
    client: Any,
    tournament_id: str,
    event: dict[str, Any],
    fencer_index: dict[str, dict[Any, Any]],
    unmatched_log_path: Path | None = None,
) -> dict[str, int]:
    matched, unmatched = attach_fencer_matches(
        event.get("results") or [],
        fencer_index,
        source_url=event.get("source_url"),
    )
    if unmatched_log_path and unmatched:
        write_unmatched_log(unmatched_log_path, unmatched)

    rows = [_result_db_row(tournament_id, event, row) for row in matched if row.get("rank") is not None]
    if not rows:
        return {"written": 0, "skipped": len(unmatched), "unmatched": len(unmatched)}
    client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        if batch:
            client.table("fs_results").insert(batch).execute()
            written += len(batch)
    return {"written": written, "skipped": len(unmatched), "unmatched": len(unmatched)}


def _get(url: str) -> requests.Response | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            return response
        print(f"  GET {url} -> {response.status_code}")
    except Exception as exc:
        print(f"  GET {url} failed: {exc}")
    return None


def fetch_public_events() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    for source in EVF_RESULT_SOURCES:
        response = _get(source["url"])
        if not response:
            probes.append(
                {
                    "url": source["url"],
                    "status": "blocked",
                    "reason": "fetch_failed",
                    "result_rows_available": False,
                }
            )
            continue
        probe = probe_source_text(response.text, source["url"])
        probes.append(probe)
        if probe["result_rows_available"]:
            events.extend(parse_evf_results_page(response.text, source["url"]))
        time.sleep(REQUEST_DELAY)
    return events, probes


def run(
    client: Any | None = None,
    fetch_events=fetch_public_events,
    unmatched_log_path: Path = DEFAULT_UNMATCHED_LOG,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    client = client or supabase or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or []) if update_state else set()
        fencer_index = fetch_fencer_index(client)
        events, probes = fetch_events()
        written = failed = skipped = 0
        imported_source_ids: set[str] = set()

        for probe in probes:
            if not probe.get("result_rows_available"):
                skipped += 1

        for event in events:
            if event["source_id"] in done_source_ids:
                skipped += 1
                continue
            tournament_id = upsert_tournament(client, event)
            if not tournament_id:
                failed += 1
                continue
            result = upsert_results(client, tournament_id, event, fencer_index, unmatched_log_path)
            written += result["written"]
            skipped += result["skipped"]
            imported_source_ids.add(event["source_id"])

        if update_state:
            set_state(SOURCE, "done_source_ids", sorted(done_source_ids | imported_source_ids))
            set_state(
                SOURCE,
                "last_run",
                {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "written": written,
                    "failed": failed,
                    "skipped": skipped,
                    "probes": probes,
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped)
        return {"written": written, "failed": failed, "skipped": skipped}
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    result = run()
    print(f"Veterans scraper complete: {result}")


if __name__ == "__main__":
    main()
