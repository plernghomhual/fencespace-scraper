from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - dependency errors surface when a client is required.
    create_client = None


SOURCE = "enrich_coach_history"
REQUEST_DELAY_SECONDS = float(os.environ.get("COACH_HISTORY_DELAY", "1.0"))
BATCH_SIZE = int(os.environ.get("COACH_HISTORY_BATCH_SIZE", "100"))
PAGE_SIZE = int(os.environ.get("COACH_HISTORY_WIKIDATA_PAGE_SIZE", "500"))
SPARQL_URL = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/sparql-results+json,application/json;q=0.9,*/*;q=0.8",
}

FEDERATION_STAFF_SOURCES = [
    {
        "source_type": "federation_staff",
        "country": "USA",
        "federation": "USA Fencing",
        "urls": ["https://www.usafencing.org/national-team-staff"],
    },
    {
        "source_type": "federation_staff",
        "country": "CAN",
        "federation": "Canadian Fencing Federation",
        "urls": ["https://fencing.ca/staff/", "https://fencing.ca/senior-national-team-program-coaches/"],
    },
    {
        "source_type": "federation_staff",
        "country": "GBR",
        "federation": "British Fencing",
        "urls": ["https://www.britishfencing.com/gbr-fencing/gbr-senior/gbr-coaching-panel/"],
    },
]

OFFICIAL_ANNOUNCEMENT_SOURCES = [
    {
        "source_type": "official_announcement",
        "country": "GBR",
        "federation": "British Fencing",
        "urls": ["https://www.britishfencing.com/25-26-gbr-coaches/"],
    },
]

BLOCKED_SOURCE_STUBS = [
    {
        "source_type": "official_announcement",
        "country": None,
        "federation": "FIE",
        "url": "https://fie.org/athletes",
        "blocked": True,
        "reason": "FIE athlete pages do not expose a stable public coach-career endpoint for bulk enrichment.",
    }
]

DATE_PATTERN = (
    r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|"
    r"[A-Za-z]+\s+\d{1,2},\s+\d{4})"
)
PERSON_PATTERN = r"[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+)+"
COACH_ROLE_PATTERN = re.compile(
    r"\b(coach|coaching|trainer|manager|performance\s+lead|entraineur|entraîneur|allenatore|adjoint)\b",
    flags=re.IGNORECASE,
)

SPARQL_QUERY_TEMPLATE = """
SELECT ?coach ?coachLabel ?roleLabel ?teamLabel ?countryLabel
       ?start_time ?end_time ?reference_url ?article WHERE {{
  ?coach wdt:P641 wd:Q12100 .
  ?coach p:P106 ?occupation_statement .
  ?occupation_statement ps:P106 ?role .
  ?role rdfs:label ?roleLabel .
  FILTER(LANG(?roleLabel) = "en")
  FILTER(CONTAINS(LCASE(STR(?roleLabel)), "coach"))
  OPTIONAL {{
    ?coach p:P108 ?team_statement .
    ?team_statement ps:P108 ?team .
    OPTIONAL {{ ?team_statement pq:P580 ?start_time . }}
    OPTIONAL {{ ?team_statement pq:P582 ?end_time . }}
    OPTIONAL {{ ?team_statement prov:wasDerivedFrom/pr:P854 ?reference_url . }}
    OPTIONAL {{ ?team wdt:P17 ?country . }}
  }}
  OPTIONAL {{
    ?article schema:about ?coach ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?coach rdfs:label ?coachLabel .
    ?role rdfs:label ?roleLabel .
    ?team rdfs:label ?teamLabel .
    ?country rdfs:label ?countryLabel .
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""

_supabase = None


def clean_text(value: Any) -> str | None:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def get_client():
    global _supabase
    if _supabase is None:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        if create_client is None:
            raise RuntimeError("supabase package is required.")
        _supabase = create_client(supabase_url, supabase_key)
    return _supabase


def _looks_like_person_name(value: str | None) -> bool:
    text = clean_text(value) or ""
    if not text or len(text) > 90:
        return False
    lowered = text.lower()
    if any(token in lowered for token in ["team", "staff", "program", "office", "email", "@"]):
        return False
    words = [word for word in re.split(r"\s+", text) if word]
    return len(words) >= 2 and any(char.isalpha() for char in text)


def normalize_role_label(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.casefold()
    if "performance lead" in lowered or "high performance" in lowered:
        return "Performance Lead"
    if "assistant" in lowered or "adjoint" in lowered:
        return "Assistant Coach"
    if "head coach" in lowered:
        return "Head Coach"
    if "national coach" in lowered:
        return "National Coach"
    if "manager" in lowered:
        return "Team Manager"
    if "trainer" in lowered:
        return "Trainer"
    if "coach" in lowered or "entraineur" in lowered or "entraîneur" in lowered or "allenatore" in lowered:
        return "Coach"
    return text.title()


def parse_public_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"[+-]?(\d{4}-\d{2}-\d{2})T", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_date_range(value: Any) -> tuple[str | None, str | None]:
    text = clean_text(value)
    if not text:
        return (None, None)
    match = re.search(
        rf"(?:from\s+)?(?P<start>{DATE_PATTERN})\s+(?:-|–|—|to|through|until)\s+(?P<end>{DATE_PATTERN})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return (parse_public_date(match.group("start")), parse_public_date(match.group("end")))
    match = re.search(rf"\bsince\s+(?P<start>{DATE_PATTERN})\b", text, flags=re.IGNORECASE)
    if match:
        return (parse_public_date(match.group("start")), None)
    return (None, None)


def history_id_for(row: dict[str, Any]) -> str:
    # Hash only the fields covered by fs_coach_history_source_unique_idx so that the
    # upsert key always matches the unique constraint and avoids duplicate-key errors.
    key = "|".join(
        clean_text(row.get(part)) or ""
        for part in [
            "coach_name",
            "role",
            "source_url",
            "start_date",
            "end_date",
        ]
    ).casefold()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace.coach-history:{key}"))


def _append_unique(rows: list[dict[str, Any]], row: dict[str, Any] | None) -> None:
    if not row:
        return
    if any(existing.get("id") == row.get("id") for existing in rows):
        return
    rows.append(row)


def build_history_row(
    *,
    coach_name: Any,
    role: Any,
    source_url: str,
    source_type: str,
    country: Any = None,
    team: Any = None,
    club: Any = None,
    coach_id: Any = None,
    start_date: Any = None,
    end_date: Any = None,
    date_range: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    clean_name = clean_text(coach_name)
    if not clean_name or not _looks_like_person_name(clean_name):
        return None
    clean_source_url = clean_text(source_url)
    if not clean_source_url:
        return None
    role_raw = clean_text(role)
    normalized_role = normalize_role_label(role_raw)
    if not normalized_role:
        return None

    parsed_start = parse_public_date(start_date)
    parsed_end = parse_public_date(end_date)
    if not parsed_start and not parsed_end and date_range:
        parsed_start, parsed_end = parse_date_range(date_range)

    row_metadata = ensure_metadata(metadata)
    if role_raw and role_raw != normalized_role:
        row_metadata.setdefault("role_raw", role_raw)

    row = {
        "id": "",
        "coach_id": clean_text(coach_id),
        "coach_name": clean_name,
        "country": clean_text(country),
        "team": clean_text(team),
        "club": clean_text(club),
        "role": normalized_role,
        "start_date": parsed_start,
        "end_date": parsed_end,
        "source_url": clean_source_url,
        "source_type": clean_text(source_type) or "public_source",
        "metadata": row_metadata,
    }
    row["id"] = history_id_for(row)
    return row


def _table_headers(table) -> list[str]:
    headers = table.select("thead th")
    if not headers:
        first_row = table.find("tr")
        headers = first_row.find_all(["th", "td"]) if first_row else []
    return [_norm_key(header.get_text(" ", strip=True)) for header in headers]


def _value_by_header(cells: list[str], headers: list[str], wanted: set[str]) -> str | None:
    for index, header in enumerate(headers):
        if index < len(cells) and header in wanted:
            return clean_text(cells[index])
    return None


def parse_federation_staff_page(
    html: str,
    *,
    country: str | None = None,
    federation: str | None = None,
    source_url: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = _table_headers(table)
        if not headers:
            continue
        body_rows = table.select("tbody tr") or table.find_all("tr")[1:]
        for tr in body_rows:
            cells = [clean_text(cell.get_text(" ", strip=True)) or "" for cell in tr.find_all(["td", "th"])]
            if not cells:
                continue
            name = _value_by_header(cells, headers, {"name", "coach", "staffmember", "staff"})
            role = _value_by_header(cells, headers, {"role", "title", "position", "function", "poste"})
            team = _value_by_header(cells, headers, {"team", "squad", "program", "programme", "weapon", "category"})
            club = _value_by_header(cells, headers, {"club", "academy"})
            date_range = _value_by_header(cells, headers, {"dates", "daterange", "period", "term", "season"})
            start = _value_by_header(cells, headers, {"start", "startdate", "from"})
            end = _value_by_header(cells, headers, {"end", "enddate", "to"})
            role_text = role or " ".join(cells)
            if not COACH_ROLE_PATTERN.search(role_text):
                continue
            _append_unique(
                rows,
                build_history_row(
                    coach_name=name,
                    role=role_text,
                    country=country,
                    team=team,
                    club=club,
                    start_date=start,
                    end_date=end,
                    date_range=date_range,
                    source_url=source_url,
                    source_type="federation_staff",
                    metadata={"federation": federation} if federation else {},
                ),
            )
    return rows


def parse_official_announcement(
    html: str,
    *,
    country: str | None = None,
    federation: str | None = None,
    source_url: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = clean_text(soup.get_text(" ", strip=True)) or ""
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        rf"\b(?:appointed|named|confirmed)\s+(?P<coach>{PERSON_PATTERN})\s+as\s+"
        rf"(?P<role>(?:Head|Assistant|National)?\s*Coach|Team Manager|High Performance Lead|Performance Lead)"
        rf"\s+of\s+(?P<team>.+?)\s+from\s+(?P<start>{DATE_PATTERN})\s+(?:to|through|until)\s+(?P<end>{DATE_PATTERN})",
        flags=re.IGNORECASE,
    )
    fencer_names = sorted(set(re.findall(rf"\bfencer\s+({PERSON_PATTERN})\b", text)))
    for match in pattern.finditer(text):
        metadata = {"federation": federation} if federation else {}
        if len(fencer_names) == 1:
            metadata["fencer_name"] = fencer_names[0]
            metadata["link_evidence"] = "official_announcement_named_fencer"
        team = re.sub(r"^(?:the|a|an)\s+", "", match.group("team").rstrip(" ."), flags=re.IGNORECASE)
        _append_unique(
            rows,
            build_history_row(
                coach_name=match.group("coach"),
                role=match.group("role"),
                country=country,
                team=team,
                start_date=match.group("start"),
                end_date=match.group("end"),
                source_url=source_url,
                source_type="official_announcement",
                metadata=metadata,
            ),
        )
    return rows


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    return clean_text((binding.get(key) or {}).get("value"))


def wikidata_entity_id(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1] or None


def parse_wikidata_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        reference_url = binding_value(binding, "reference_url")
        wikipedia_url = binding_value(binding, "article")
        source_url = reference_url or wikipedia_url
        if not source_url:
            continue
        role = binding_value(binding, "roleLabel") or "Coach"
        if not COACH_ROLE_PATTERN.search(role):
            continue

        coach_url = binding_value(binding, "coach")
        wikidata_id = wikidata_entity_id(coach_url)
        metadata = {
            "wikidata_id": wikidata_id,
            "wikidata_url": coach_url,
        }
        if wikipedia_url:
            metadata["wikipedia_url"] = wikipedia_url
        if reference_url:
            metadata["reference_url"] = reference_url

        _append_unique(
            rows,
            build_history_row(
                coach_name=binding_value(binding, "coachLabel"),
                role=role,
                country=binding_value(binding, "countryLabel"),
                team=binding_value(binding, "teamLabel"),
                club=binding_value(binding, "clubLabel"),
                start_date=binding_value(binding, "start_time"),
                end_date=binding_value(binding, "end_time"),
                source_url=source_url,
                source_type="wikidata",
                metadata=metadata,
            ),
        )
    return rows


def build_sparql_query(*, limit: int = PAGE_SIZE, offset: int = 0) -> str:
    return SPARQL_QUERY_TEMPLATE.format(limit=limit, offset=offset)


def fetch_wikidata_bindings(
    *,
    session: requests.Session | None = None,
    sleeper=time.sleep,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> list[dict[str, Any]]:
    session = session or requests.Session()
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = session.get(
            SPARQL_URL,
            params={"query": build_sparql_query(limit=PAGE_SIZE, offset=offset), "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Wikidata SPARQL error {response.status_code}: {response.text[:500]}")
        bindings = response.json()["results"]["bindings"]
        rows.extend(bindings)
        if len(bindings) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE
        sleeper(request_delay)


def load_source_definitions() -> list[dict[str, Any]]:
    override = os.environ.get("COACH_HISTORY_SOURCE_URLS")
    if override:
        data = json.loads(override)
        if not isinstance(data, list):
            raise ValueError("COACH_HISTORY_SOURCE_URLS must be a JSON list")
        return data
    return [*FEDERATION_STAFF_SOURCES, *OFFICIAL_ANNOUNCEMENT_SOURCES, *BLOCKED_SOURCE_STUBS]


def fetch_source_pages(
    sources: list[dict[str, Any]],
    *,
    session: requests.Session | None = None,
    sleeper=time.sleep,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    session = session or requests.Session()
    pages: list[dict[str, Any]] = []
    summary = {"fetched": 0, "failed": 0, "blocked": 0}

    for source in sources:
        urls = source.get("urls") or ([source.get("url")] if source.get("url") else [])
        if source.get("blocked"):
            summary["blocked"] += max(1, len(urls))
            continue
        for url in urls:
            try:
                response = session.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200 or not response.text:
                    summary["failed"] += 1
                    continue
                pages.append({**source, "url": url, "html": response.text})
                summary["fetched"] += 1
            except Exception as exc:
                print(f"  Failed to fetch {url}: {exc}")
                summary["failed"] += 1
            finally:
                sleeper(request_delay)
    return pages, summary


def parse_source_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in pages:
        source_type = page.get("source_type")
        if source_type == "official_announcement":
            parsed = parse_official_announcement(
                page.get("html") or "",
                country=page.get("country"),
                federation=page.get("federation"),
                source_url=page["url"],
            )
        else:
            parsed = parse_federation_staff_page(
                page.get("html") or "",
                country=page.get("country"),
                federation=page.get("federation"),
                source_url=page["url"],
            )
        for row in parsed:
            _append_unique(rows, row)
    return rows


def match_single_fencer(client, name: str | None, country: str | None) -> str | None:
    clean_name = clean_text(name)
    if not clean_name:
        return None
    try:
        query = client.table("fs_fencers").select("id,name,country").ilike("name", clean_name)
        if country:
            query = query.eq("country", country)
        result = query.limit(2).execute()
        data = result.data or []
        if len(data) == 1:
            return data[0].get("id")
    except Exception as exc:
        print(f"  Fencer match failed for {clean_name}: {exc}")
    return None


def build_fencer_relationship_rows(
    history_rows: list[dict[str, Any]],
    *,
    client,
) -> tuple[list[dict[str, Any]], int]:
    relationship_rows: list[dict[str, Any]] = []
    skipped = 0
    for row in history_rows:
        metadata = ensure_metadata(row.get("metadata"))
        fencer_name = clean_text(metadata.get("fencer_name"))
        if not fencer_name:
            continue
        if metadata.get("link_evidence") != "official_announcement_named_fencer":
            skipped += 1
            continue
        coach_id = clean_text(row.get("coach_id"))
        if not coach_id:
            skipped += 1
            continue
        fencer_id = match_single_fencer(client, fencer_name, clean_text(row.get("country")))
        if not fencer_id:
            skipped += 1
            continue
        end_date = clean_text(row.get("end_date"))
        relationship_rows.append(
            {
                "fencer_id": fencer_id,
                "coach_id": coach_id,
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "current": end_date is None or end_date >= date.today().isoformat(),
                "metadata": {
                    "source_url": row.get("source_url"),
                    "coach_history_id": row.get("id"),
                    "link_evidence": metadata.get("link_evidence"),
                },
            }
        )
    return relationship_rows, skipped


def upsert_coach_history(rows: list[dict[str, Any]], *, client=None) -> dict[str, int]:
    client = client or get_client()
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        normalized = dict(row)
        normalized["metadata"] = ensure_metadata(normalized.get("metadata"))
        normalized["id"] = normalized.get("id") or history_id_for(normalized)
        if not normalized.get("coach_name") or not normalized.get("role") or not normalized.get("source_url"):
            continue
        deduped[normalized["id"]] = normalized

    history_rows = list(deduped.values())
    history_written = 0
    for index in range(0, len(history_rows), BATCH_SIZE):
        batch = history_rows[index : index + BATCH_SIZE]
        client.table("fs_coach_history").upsert(batch, on_conflict="id").execute()
        history_written += len(batch)

    relationship_rows, relationships_skipped = build_fencer_relationship_rows(history_rows, client=client)
    relationships_written = 0
    for index in range(0, len(relationship_rows), BATCH_SIZE):
        batch = relationship_rows[index : index + BATCH_SIZE]
        client.table("fs_fencer_coach_relationship").upsert(batch, on_conflict="fencer_id,coach_id").execute()
        relationships_written += len(batch)

    return {
        "history_written": history_written,
        "relationships_written": relationships_written,
        "relationships_skipped": relationships_skipped,
    }


def enrich_coach_history(
    *,
    client=None,
    sources: list[dict[str, Any]] | None = None,
    html_pages: list[dict[str, Any]] | None = None,
    wikidata_bindings: list[dict[str, Any]] | None = None,
    session: requests.Session | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    client = client or get_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None

    try:
        fetch_summary = {"fetched": 0, "failed": 0, "blocked": 0}
        if html_pages is None:
            html_pages, fetch_summary = fetch_source_pages(sources or load_source_definitions(), session=session)

        rows = parse_source_pages(html_pages)
        raw_bindings = wikidata_bindings if wikidata_bindings is not None else fetch_wikidata_bindings(session=session)
        for row in parse_wikidata_bindings(raw_bindings):
            _append_unique(rows, row)

        upsert_summary = upsert_coach_history(rows, client=client)
        summary = {
            "sources_fetched": fetch_summary["fetched"],
            "sources_failed": fetch_summary["failed"],
            "sources_blocked": fetch_summary["blocked"],
            "history_parsed": len(rows),
            **upsert_summary,
        }

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(
                written=summary["history_written"] + summary["relationships_written"],
                failed=summary["sources_failed"],
                skipped=summary["sources_blocked"] + summary["relationships_skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = enrich_coach_history()
    print(f"Coach history enrichment complete: {summary}")


if __name__ == "__main__":
    main()
