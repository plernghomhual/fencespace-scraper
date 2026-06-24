import io
import os
import re
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "scrape_doping"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
BATCH_SIZE = 100
DEFAULT_RATE_LIMIT_SECONDS = 1.0

# TODO: This URL returns 404 — update when FIE publishes a new sanctions PDF.
FIE_SANCTIONS_URL = "https://static.fie.org/uploads/39/196318-SANCTIONS.pdf"
FIE_CLEAN_SPORT_URL = "https://fie.org/fie/documents/clean-sport/11"
ITA_ANNA_KUN_URL = (
    "https://ita.sport/news/the-ita-has-notified-fencer-anna-kun-hungary-of-a-"
    "potential-anti-doping-rule-violation/"
)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

COUNTRY_ALIASES = {
    "HUNGARY": "HUN",
    "HUN": "HUN",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "USA": "USA",
    "FRANCE": "FRA",
    "FRA": "FRA",
}

DATE_FIELDS = ("athlete_date_of_birth", "date_of_birth", "birth_date", "dob")


@dataclass(frozen=True)
class DopingSource:
    url: str
    source_kind: str
    authority: str


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


DEFAULT_SOURCES = [
    DopingSource(
        url=FIE_SANCTIONS_URL,
        source_kind="fie_sanctions_pdf",
        authority="FIE",
    ),
    DopingSource(
        url=FIE_CLEAN_SPORT_URL,
        source_kind="fie_clean_sport",
        authority="FIE",
    ),
    DopingSource(
        url=ITA_ANNA_KUN_URL,
        source_kind="ita_news",
        authority="International Testing Agency/FIE",
    ),
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_country(value: str | None) -> str | None:
    text = clean_text(value).strip("() ")
    if not text:
        return None
    upper = text.upper()
    if re.fullmatch(r"[A-Z]{3}", upper):
        return upper
    return COUNTRY_ALIASES.get(upper, upper if len(upper) <= 3 else text)


def parse_public_date(value: str | None) -> str | None:
    text = clean_text(value)
    match = re.search(
        r"\b(?P<day>\d{1,2})\s+"
        r"(?P<month>January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+"
        r"(?P<year>20\d{2})\b",
        text,
        flags=re.I,
    )
    if not match:
        return None
    month = MONTHS[match.group("month").lower()]
    return f"{int(match.group('year')):04d}-{month:02d}-{int(match.group('day')):02d}"


def strip_honorific(name: str) -> str:
    return clean_text(re.sub(r"^(?:Ms|Mr|Mrs|Miss|Dr)\.?\s+", "", name, flags=re.I))


def parse_athlete_country(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"\b(?:fencer|athlete)\s+(?:Ms|Mr|Mrs|Miss|Dr)?\.?\s*"
        r"(?P<name>[A-Z][A-Za-z' .-]+?)\s*\((?P<country>[A-Za-z ]{3,30})\)",
        r"(?:^|\n)\s*(?:Ms|Mr|Mrs|Miss|Dr)?\.?\s*"
        r"(?P<name>[A-Z][A-Za-z' .-]+?)\s*\((?P<country>[A-Za-z ]{3,30})\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return strip_honorific(match.group("name")), normalize_country(match.group("country"))
    return None, None


def infer_test_type(text: str) -> str | None:
    lowered = clean_text(text).casefold()
    if "whereabouts" in lowered or "missed test" in lowered:
        return "whereabouts_failures"
    if "adverse analytical finding" in lowered:
        return "adverse_analytical_finding"
    if "sample" in lowered:
        return "sample_collection"
    return None


def classify_case_text(text: str) -> tuple[str, str, str | None, str]:
    lowered = clean_text(text).casefold()
    if "did not commit" in lowered or "case is dismissed" in lowered or "no anti-doping rule violation" in lowered:
        return "cleared_case", "cleared", None, "cleared_public_case"
    if "appeal" in lowered or "court of arbitration for sport" in lowered:
        status = "appeal_pending" if any(term in lowered for term in ("pending", "not final", "stayed")) else "appealed"
        return "appeal", status, None, "appeal_public_case"
    if "potential anti-doping rule violation" in lowered:
        return "potential_adrv", "under_review", None, "potential_adrv_not_a_sanction"
    return "sanction", "resolved", extract_sanction_summary(text), "official_public_sanction"


def extract_sanction_summary(text: str) -> str | None:
    cleaned = clean_text(text)
    match = re.search(
        r"(Period of Ineligibility.+?)(?:;|\.|$)",
        cleaned,
        flags=re.I,
    )
    if match:
        return clean_text(match.group(1))
    if "sanction" in cleaned.casefold():
        return cleaned[:1000]
    return None


def base_record(
    *,
    athlete_name: str,
    athlete_country: str | None,
    record_date: str | None,
    record_type: str,
    case_status: str,
    test_type: str | None,
    sanction: str | None,
    authority: str,
    source_url: str,
    source_kind: str,
    metadata: dict | None = None,
) -> dict:
    # Public anti-doping data is legally sensitive: only store source-backed labels,
    # never private test history or inferred allegations.
    return {
        "fencer_id": None,
        "athlete_name": athlete_name,
        "athlete_country": athlete_country,
        "record_date": record_date,
        "record_type": record_type,
        "case_status": case_status,
        "test_type": test_type,
        "sanction": sanction,
        "authority": authority,
        "source_url": source_url,
        "source_kind": source_kind,
        "metadata": metadata or {},
        "scraped_at": datetime.now(UTC).isoformat(),
    }


def build_official_case_record(
    *,
    athlete_name: str,
    athlete_country: str | None,
    record_date: str | None,
    text: str,
    authority: str,
    source_url: str,
    source_kind: str = "official_case",
) -> dict:
    record_type, case_status, sanction, legal_note = classify_case_text(text)
    return base_record(
        athlete_name=athlete_name,
        athlete_country=normalize_country(athlete_country),
        record_date=record_date,
        record_type=record_type,
        case_status=case_status,
        test_type=infer_test_type(text),
        sanction=sanction,
        authority=authority,
        source_url=source_url,
        source_kind=source_kind,
        metadata={"source_kind": source_kind, "legal_note": legal_note},
    )


def parse_fie_sanctions_pdf_text(text: str, *, source_url: str = FIE_SANCTIONS_URL) -> list[dict]:
    match = re.search(r"\bADVRs?\b.*", text, flags=re.I | re.S)
    if not match:
        return []
    section = match.group(0)
    athlete_name, athlete_country = parse_athlete_country(section)
    if not athlete_name:
        return []

    decision_line = re.search(
        r"Decision of the (?P<authority>FIE Doping Disciplinary Tribunal) of "
        r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+20\d{2})",
        section,
        flags=re.I,
    )
    authority = (
        "FIE Doping Disciplinary Tribunal"
        if decision_line
        else "FIE"
    )
    record_date = parse_public_date(decision_line.group("date") if decision_line else section)

    rule_match = re.search(r"\b(Art\.\s*2\.\d+\s+FIE ADR[^;\n]+)", section, flags=re.I)
    sanction_text = ""
    sanction_match = re.search(r"Sanctions?:\s*(?P<sanction>.+)", section, flags=re.I | re.S)
    if sanction_match:
        sanction_text = clean_text(sanction_match.group("sanction")).replace("-Period", "Period")

    return [
        base_record(
            athlete_name=athlete_name,
            athlete_country=athlete_country,
            record_date=record_date,
            record_type="sanction",
            case_status="resolved",
            test_type=infer_test_type(section),
            sanction=sanction_text or None,
            authority=authority,
            source_url=source_url,
            source_kind="fie_sanctions_pdf",
            metadata={
                "source_kind": "fie_sanctions_pdf",
                "rule_violation": clean_text(rule_match.group(1)) if rule_match else None,
                "public_record_scope": "FIE ADVR sanctions section",
            },
        )
    ]


def parse_ita_news_article_text(text: str, *, source_url: str = ITA_ANNA_KUN_URL) -> dict:
    athlete_name, athlete_country = parse_athlete_country(text)
    if not athlete_name:
        name_match = re.search(r"fencer\s+([A-Z][A-Za-z' .-]+?)\s+of\s+", text)
        athlete_name = clean_text(name_match.group(1)) if name_match else "Unknown Athlete"
    record_date = parse_public_date(text)
    return build_official_case_record(
        athlete_name=athlete_name,
        athlete_country=athlete_country,
        record_date=record_date,
        text=text,
        authority="International Testing Agency/FIE",
        source_url=source_url,
        source_kind="ita_news",
    )


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def fetch_source(source: DopingSource) -> FetchedContent:
    response = requests.get(
        source.url,
        headers=HEADERS,
        timeout=25,
        allow_redirects=True,
    )
    if response.status_code == 404 and source.source_kind == "fie_sanctions_pdf":
        print(
            f"[scrape_doping] WARNING: FIE sanctions PDF URL returned 404 — "
            f"URL may have changed. Update FIE_SANCTIONS_URL in scrape_doping.py. "
            f"URL: {source.url}"
        )
        raise requests.exceptions.HTTPError(
            f"404 for {source.url}", response=response
        )
    response.raise_for_status()
    return FetchedContent(
        content=response.content,
        content_type=response.headers.get("content-type", ""),
        final_url=response.url,
    )


def html_to_text(content: bytes) -> str:
    soup = BeautifulSoup(content.decode("utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def parse_fetched_content(source: DopingSource, fetched: FetchedContent) -> list[dict]:
    content_type = fetched.content_type.lower()
    if source.source_kind == "fie_sanctions_pdf":
        if "pdf" in content_type or fetched.content.startswith(b"%PDF"):
            text = extract_pdf_text(fetched.content)
        else:
            text = fetched.content.decode("utf-8", errors="replace")
        rows = parse_fie_sanctions_pdf_text(text, source_url=fetched.final_url or source.url)
    elif source.source_kind == "ita_news":
        text = html_to_text(fetched.content) if "html" in content_type else fetched.content.decode("utf-8", errors="replace")
        row = parse_ita_news_article_text(text, source_url=fetched.final_url or source.url)
        rows = [] if row["athlete_name"] == "Unknown Athlete" else [row]
    else:
        # Current FIE Clean Sport page has a public placeholder rather than rows.
        # Returning no rows avoids manufacturing a "no doping history" record.
        rows = []

    for row in rows:
        row["source_url"] = fetched.final_url or row.get("source_url") or source.url
        row["metadata"] = {key: value for key, value in (row.get("metadata") or {}).items() if value is not None}
    return rows


def candidate_date(row: dict) -> str | None:
    for field in DATE_FIELDS:
        value = row.get(field)
        if value:
            return str(value)
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict):
        for field in DATE_FIELDS:
            value = metadata.get(field)
            if value:
                return str(value)
    return None


def query_fencers_by_fie_id(client, fie_id: str) -> list[dict]:
    return (
        client.table("fs_fencers")
        .select("id,fie_id,name,country,date_of_birth,metadata")
        .eq("fie_id", str(fie_id))
        .limit(20)
        .execute()
        .data
        or []
    )


def query_fencers_by_name_country(client, name: str, country: str) -> list[dict]:
    return (
        client.table("fs_fencers")
        .select("id,fie_id,name,country,date_of_birth,metadata")
        .ilike("name", name)
        .eq("country", country)
        .limit(20)
        .execute()
        .data
        or []
    )


def fencer_birth_date(candidate: dict) -> str | None:
    for field in ("date_of_birth", "birth_date", "dob"):
        value = candidate.get(field)
        if value:
            return str(value)
    metadata = candidate.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("fie_date_of_birth") or metadata.get("date_of_birth")
        if value:
            return str(value)
    return None


def with_match_metadata(row: dict, *, status: str, method: str, candidates: list[dict] | None = None) -> dict:
    matched = dict(row)
    metadata = dict(matched.get("metadata") or {})
    metadata["match_status"] = status
    metadata["match_method"] = method
    if candidates:
        metadata["match_candidates"] = [candidate.get("id") for candidate in candidates if candidate.get("id")]
    matched["metadata"] = metadata
    return matched


def attach_fencer_match(client, row: dict, warn: Callable[[str], None] = print) -> dict:
    if not client:
        return with_match_metadata({**row, "fencer_id": None}, status="unmatched", method="no_client")

    metadata = row.get("metadata") or {}
    fie_id = row.get("fie_id") or (metadata.get("fie_id") if isinstance(metadata, dict) else None)
    if fie_id:
        candidates = query_fencers_by_fie_id(client, str(fie_id))
        if len(candidates) == 1:
            matched = with_match_metadata(row, status="matched", method="fie_id")
            matched["fencer_id"] = candidates[0].get("id")
            return matched
        if candidates:
            warn(f"ambiguous anti-doping fencer match for fie_id={fie_id}: {[row.get('id') for row in candidates]}")
            matched = with_match_metadata(row, status="ambiguous", method="fie_id", candidates=candidates)
            matched["fencer_id"] = None
            return matched

    name = clean_text(row.get("athlete_name"))
    country = normalize_country(row.get("athlete_country"))
    if not name or not country:
        return with_match_metadata({**row, "fencer_id": None}, status="unmatched", method="missing_identity")

    candidates = query_fencers_by_name_country(client, name, country)
    birth_date = candidate_date(row)
    if birth_date:
        candidates = [candidate for candidate in candidates if fencer_birth_date(candidate) == birth_date]
        if len(candidates) == 1:
            matched = with_match_metadata(row, status="matched", method="name_country_date")
            matched["fencer_id"] = candidates[0].get("id")
            return matched
        if candidates:
            warn(
                "ambiguous anti-doping fencer match "
                f"for name={name!r} country={country!r} date={birth_date!r}: "
                f"{[candidate.get('id') for candidate in candidates]}"
            )
            matched = with_match_metadata(row, status="ambiguous", method="name_country_date", candidates=candidates)
            matched["fencer_id"] = None
            return matched
        return with_match_metadata({**row, "fencer_id": None}, status="unmatched", method="name_country_date")

    if len(candidates) > 1:
        warn(f"ambiguous anti-doping fencer match for name={name!r} country={country!r}: {[row.get('id') for row in candidates]}")
        matched = with_match_metadata(row, status="ambiguous", method="name_country", candidates=candidates)
        matched["fencer_id"] = None
        return matched

    # A single name+country hit is stored as source evidence only. Anti-doping
    # linkage needs an explicit ID or birth-date-level corroboration.
    return with_match_metadata({**row, "fencer_id": None}, status="unmatched", method="insufficient_identity_evidence")


def dedupe_key(row: dict) -> tuple[str, str, str, str]:
    return (
        clean_text(row.get("source_url")).casefold(),
        clean_text(row.get("athlete_name")).casefold(),
        clean_text(row.get("record_type")).casefold(),
        clean_text(row.get("record_date")).casefold(),
    )


def dedupe_records(rows: Iterable[dict]) -> list[dict]:
    chosen: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = dedupe_key(row)
        if not key[0] or not key[1] or not key[2]:
            continue
        chosen.setdefault(key, row)
    return list(chosen.values())


def batch_upsert_doping_records(client, rows: list[dict]) -> tuple[int, int]:
    if not client or not rows:
        return 0, 0
    matched_rows = [attach_fencer_match(client, row) for row in rows]
    ambiguous = sum(1 for row in matched_rows if (row.get("metadata") or {}).get("match_status") == "ambiguous")
    for index in range(0, len(matched_rows), BATCH_SIZE):
        batch = matched_rows[index : index + BATCH_SIZE]
        client.table("fs_anti_doping_records").upsert(
            batch,
            on_conflict="source_url,athlete_name,record_type,record_date",
        ).execute()
    return len(matched_rows), ambiguous


def scrape_doping(
    *,
    client=None,
    sources: Iterable[DopingSource] | None = None,
    fetcher: Callable[[DopingSource], FetchedContent] = fetch_source,
    sleeper: Callable[[float], None] = time.sleep,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    log_run: bool = True,
    update_state: bool = True,
) -> dict:
    source_list = list(sources or DEFAULT_SOURCES)
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    parsed_rows: list[dict] = []
    failed = 0
    skipped = 0
    ambiguous = 0

    try:
        for index, source in enumerate(source_list):
            try:
                fetched = fetcher(source)
                rows = parse_fetched_content(source, fetched)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.url}: {exc}")
                rows = []

            if not rows:
                skipped += 1
            parsed_rows.extend(rows)

            if index < len(source_list) - 1 and rate_limit_seconds > 0:
                sleeper(rate_limit_seconds)

        rows = dedupe_records(parsed_rows)
        written, ambiguous = batch_upsert_doping_records(client, rows) if client else (0, 0)
        summary = {
            "sources": len(source_list),
            "parsed": len(parsed_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "ambiguous": ambiguous,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_doping()
    print(
        "anti-doping records: "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped, {summary['ambiguous']} ambiguous"
    )


if __name__ == "__main__":
    main()
