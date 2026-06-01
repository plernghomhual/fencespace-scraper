from __future__ import annotations

import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "scrape_physical_stats"
FIE_BASE_URL = "https://fie.org/athletes"
WIKIPEDIA_REST_BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/html"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
MAX_FENCERS = int(os.environ.get("PHYSICAL_STATS_LIMIT", "1000"))
REQUEST_DELAY_SECONDS = float(os.environ.get("PHYSICAL_STATS_DELAY", "0.5"))
FORCE_RESCRAPE = os.environ.get("PHYSICAL_STATS_FORCE_RESCRAPE", "").lower() in {"1", "true", "yes"}
FORCE_RESCRAPE_AFTER_DAYS = int(os.environ.get("PHYSICAL_STATS_RESCRAPE_AFTER_DAYS", "0"))

HEADERS = {
    "User-Agent": os.environ.get(
        "PHYSICAL_STATS_USER_AGENT",
        "FenceSpace-Scraper/physical-stats (+https://fencespace.app)",
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}

PHYSICAL_FIELDS = ("height", "weight", "reach")
SELECT_COLUMNS = "id,fie_id,name,country,height,weight,reach,metadata"


@dataclass(frozen=True)
class PhysicalStats:
    height: int | None = None
    weight: int | None = None
    reach: int | None = None

    def fields_found(self) -> list[str]:
        return [field for field in PHYSICAL_FIELDS if getattr(self, field) is not None]

    def has_any(self) -> bool:
        return bool(self.fields_found())


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_label(value: Any) -> str:
    text = clean_text(value) or ""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


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


def _round_number(value: float) -> int:
    return int(round(value))


def _valid_centimeters(value: int | None) -> int | None:
    if value is None:
        return None
    return value if 90 <= value <= 260 else None


def _valid_kilograms(value: int | None) -> int | None:
    if value is None:
        return None
    return value if 30 <= value <= 180 else None


def parse_centimeters(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.lower().replace(",", ".")

    match = re.search(r"(\d+(?:\.\d+)?)\s*cm\b", normalized)
    if match:
        return _valid_centimeters(_round_number(float(match.group(1))))

    match = re.search(r"(\d+(?:\.\d+)?)\s*m\b", normalized)
    if match:
        return _valid_centimeters(_round_number(float(match.group(1)) * 100))

    match = re.search(r"(\d+)\s*(?:ft|feet|foot|')\s*(\d+(?:\.\d+)?)?\s*(?:in|inches|\"|”)?", normalized)
    if match:
        feet = float(match.group(1))
        inches = float(match.group(2) or 0)
        return _valid_centimeters(_round_number((feet * 12 + inches) * 2.54))

    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:in|inch|inches)\b", normalized)
    if match:
        return _valid_centimeters(_round_number(float(match.group(1)) * 2.54))

    match = re.fullmatch(r"\d+(?:\.\d+)?", normalized)
    if match:
        number = float(normalized)
        if 1.0 <= number <= 2.6:
            return _valid_centimeters(_round_number(number * 100))
        return _valid_centimeters(_round_number(number))

    return None


def parse_kilograms(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.lower().replace(",", ".")

    match = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", normalized)
    if match:
        return _valid_kilograms(_round_number(float(match.group(1))))

    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|pound|pounds)\b", normalized)
    if match:
        return _valid_kilograms(_round_number(float(match.group(1)) * 0.45359237))

    match = re.fullmatch(r"\d+(?:\.\d+)?", normalized)
    if match:
        return _valid_kilograms(_round_number(float(normalized)))

    return None


def _local_extract_profile_info(page_html: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for item in re.findall(
        r'<div\b[^>]*class="[^"]*ProfileInfo-item[^"]*"[^>]*>(.*?)</div>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        spans = re.findall(r"<span\b[^>]*>(.*?)</span>", item, flags=re.IGNORECASE | re.DOTALL)
        if len(spans) < 2:
            continue
        label = clean_text(spans[0])
        value = clean_text(spans[1])
        if label and value:
            info[normalize_label(label)] = value
    return info


def _local_extract_label_value_pairs(page_html: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for block in re.findall(
        r'<p\b[^>]*class="[^"]*AthleteBio-body[^"]*"[^>]*>(.*?)</p>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        label_match = re.search(
            r'<span\b[^>]*class="[^"]*AthleteBio-label[^"]*"[^>]*>(.*?)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        value_match = re.search(
            r'<span\b[^>]*class="[^"]*Bio-stat[^"]*"[^>]*>(.*?)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not label_match or not value_match:
            continue
        label = clean_text(label_match.group(1))
        value = clean_text(value_match.group(1))
        if label and value:
            pairs.append((label, value))
    return pairs


def _local_find_pair_value(pairs: list[tuple[str, str]], wanted_labels: list[str]) -> str | None:
    wanted = [normalize_label(label) for label in wanted_labels]
    for target in wanted:
        for label, value in pairs:
            if normalize_label(label) == target and value:
                return value
    return None


def _local_iter_window_json_blocks(page_html: str):
    decoder = json.JSONDecoder()
    skip_names = {"__translations__", "dataLayer", "_headToHead", "_tabRanking", "_tabResults", "_tabOpponents"}
    for match in re.finditer(r"window\.([A-Za-z0-9_$]+)\s*=", page_html):
        name = match.group(1)
        if name in skip_names:
            continue
        offset = match.end()
        while offset < len(page_html) and page_html[offset].isspace():
            offset += 1
        if offset >= len(page_html) or page_html[offset] not in "[{":
            continue
        try:
            block, _ = decoder.raw_decode(page_html[offset:])
            yield block
        except Exception:
            continue


def _athlete_profile_helpers():
    try:
        from scrape_athlete_profiles import (  # type: ignore
            extract_label_value_pairs,
            extract_profile_info,
            find_pair_value,
            iter_window_json_blocks,
        )

        return extract_profile_info, extract_label_value_pairs, find_pair_value, iter_window_json_blocks
    except Exception:
        return (
            _local_extract_profile_info,
            _local_extract_label_value_pairs,
            _local_find_pair_value,
            _local_iter_window_json_blocks,
        )


def _stats_from_json_blocks(page_html: str, iter_json_blocks: Callable[[str], Iterable[Any]]) -> PhysicalStats:
    values: dict[str, int | None] = {"height": None, "weight": None, "reach": None}
    key_groups = {
        "height": {"height", "bodyheight", "stature"},
        "weight": {"weight", "bodyweight"},
        "reach": {"reach", "armreach", "wingspan"},
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for raw_key, raw_value in value.items():
                key = normalize_label(raw_key)
                scalar = raw_value if isinstance(raw_value, (str, int, float)) else None
                if scalar is not None:
                    if values["height"] is None and key in key_groups["height"]:
                        values["height"] = parse_centimeters(scalar)
                    elif values["weight"] is None and key in key_groups["weight"]:
                        values["weight"] = parse_kilograms(scalar)
                    elif values["reach"] is None and key in key_groups["reach"]:
                        values["reach"] = parse_centimeters(scalar)
                if isinstance(raw_value, (dict, list)):
                    walk(raw_value)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for block in iter_json_blocks(page_html):
        walk(block)

    return PhysicalStats(**values)


def parse_fie_physical_stats(page_html: str) -> PhysicalStats:
    extract_profile_info, extract_label_value_pairs, find_pair_value, iter_window_json_blocks = _athlete_profile_helpers()
    pairs = extract_label_value_pairs(page_html)
    summary = extract_profile_info(page_html)
    json_stats = _stats_from_json_blocks(page_html, iter_window_json_blocks)

    height = (
        parse_centimeters(find_pair_value(pairs, ["Height", "Body height", "Stature"]))
        or parse_centimeters(summary.get("height"))
        or json_stats.height
    )
    weight = (
        parse_kilograms(find_pair_value(pairs, ["Weight", "Body weight"]))
        or parse_kilograms(summary.get("weight"))
        or json_stats.weight
    )
    reach = (
        parse_centimeters(find_pair_value(pairs, ["Reach", "Arm reach", "Wingspan"]))
        or parse_centimeters(summary.get("reach"))
        or json_stats.reach
    )

    return PhysicalStats(height=height, weight=weight, reach=reach)


def parse_wikipedia_infobox(page_html: str) -> PhysicalStats:
    soup = BeautifulSoup(page_html, "html.parser")
    for selector in ("sup.reference", "style", "script"):
        for node in soup.select(selector):
            node.decompose()

    values: dict[str, int | None] = {"height": None, "weight": None, "reach": None}
    tables = soup.select("table.infobox, table[class*=infobox]")
    rows = []
    for table in tables or soup.find_all("table"):
        rows.extend(table.find_all("tr"))

    for row in rows:
        label_node = row.find("th")
        value_node = row.find("td")
        if not label_node or not value_node:
            continue
        label = normalize_label(label_node.get_text(" ", strip=True))
        value = value_node.get_text(" ", strip=True)
        if "height" in label and values["height"] is None:
            values["height"] = parse_centimeters(value)
        elif "weight" in label and values["weight"] is None:
            values["weight"] = parse_kilograms(value)
        elif "reach" in label and values["reach"] is None:
            values["reach"] = parse_centimeters(value)

    return PhysicalStats(**values)


def merge_source_stats(source_stats: Iterable[tuple[str, PhysicalStats]]) -> tuple[PhysicalStats, dict[str, str]]:
    merged: dict[str, int | None] = {"height": None, "weight": None, "reach": None}
    sources: dict[str, str] = {}
    for source, stats in source_stats:
        for field in PHYSICAL_FIELDS:
            value = getattr(stats, field)
            if value is not None and merged[field] is None:
                merged[field] = value
                sources[field] = source
    return PhysicalStats(**merged), sources


def is_missing_value(value: Any) -> bool:
    return value is None or clean_text(value) in (None, "0")


def build_update_payload(
    row: dict[str, Any],
    stats: PhysicalStats,
    sources: dict[str, str],
    *,
    attempted_at: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    metadata = ensure_metadata(row.get("metadata"))
    fields_found = stats.fields_found()
    fields_written: list[str] = []
    payload: dict[str, Any] = {}

    for field in PHYSICAL_FIELDS:
        value = getattr(stats, field)
        if value is None or not is_missing_value(row.get(field)):
            continue
        payload[field] = value
        fields_written.append(field)
        source = sources.get(field)
        if source:
            metadata[f"{field}_source"] = source

    if fields_written:
        status = "updated"
    elif fields_found:
        status = "already_populated"
    else:
        status = "no_physical_stats"

    scrape_info: dict[str, Any] = {
        "attempted_at": attempted_at,
        "status": status,
        "fields_found": fields_found,
        "fields_written": fields_written,
    }
    if sources:
        scrape_info["sources"] = sources
    if errors:
        scrape_info["errors"] = [error[:500] for error in errors]

    metadata["physical_stats_attempted_at"] = attempted_at
    metadata["physical_stats_scrape"] = scrape_info
    payload["metadata"] = metadata
    return payload


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)


def query_missing_physical_stats(client: Any, limit: int = MAX_FENCERS) -> list[dict[str, Any]]:
    result = (
        client.table("fs_fencers")
        .select(SELECT_COLUMNS)
        .or_("height.is.null,weight.is.null,reach.is.null")
        .limit(limit)
        .execute()
    )
    return result.data or []


def was_already_attempted(row: dict[str, Any]) -> bool:
    if FORCE_RESCRAPE:
        return False
    metadata = ensure_metadata(row.get("metadata"))
    attempted_at_str = metadata.get("physical_stats_attempted_at")
    if not attempted_at_str:
        scrape_info = metadata.get("physical_stats_scrape")
        if isinstance(scrape_info, dict):
            attempted_at_str = scrape_info.get("attempted_at")
    if not attempted_at_str:
        return False
    if FORCE_RESCRAPE_AFTER_DAYS > 0:
        try:
            attempted_at = datetime.fromisoformat(str(attempted_at_str).replace("Z", "+00:00"))
            if attempted_at.tzinfo is None:
                attempted_at = attempted_at.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - attempted_at).days < FORCE_RESCRAPE_AFTER_DAYS
        except Exception:
            return True
    return True


def fetch_fie_physical_stats(fie_id: str, session: requests.Session | None = None) -> PhysicalStats:
    clean_id = clean_text(fie_id)
    if not clean_id:
        return PhysicalStats()
    http = session or requests.Session()
    response = http.get(f"{FIE_BASE_URL}/{quote(clean_id)}", headers=HEADERS, timeout=20)
    if response.status_code != 200:
        return PhysicalStats()
    return parse_fie_physical_stats(response.text)


def _metadata_text(row: dict[str, Any], *keys: str) -> str | None:
    metadata = ensure_metadata(row.get("metadata"))
    for key in keys:
        value = clean_text(row.get(key))
        if value:
            return value
        value = clean_text(metadata.get(key))
        if value:
            return value
    return None


def _title_from_wikipedia_url(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    if not parsed.path:
        return None
    if "/wiki/" in parsed.path:
        return unquote(parsed.path.rsplit("/wiki/", 1)[-1])
    return None


def wikipedia_title_from_row(row: dict[str, Any], session: requests.Session | None = None) -> str | None:
    title = _metadata_text(row, "wikipedia_title", "wikipedia_page", "enwiki_title")
    if title:
        return title.replace(" ", "_")

    url_title = _title_from_wikipedia_url(_metadata_text(row, "wikipedia_url", "enwiki_url"))
    if url_title:
        return url_title.replace(" ", "_")

    qid = _metadata_text(row, "wikidata_id")
    if not qid:
        return None
    qid = qid.strip()
    if not re.fullmatch(r"Q\d+", qid, flags=re.IGNORECASE):
        return None

    http = session or requests.Session()
    response = http.get(WIKIDATA_ENTITY_URL.format(qid=qid.upper()), headers=HEADERS, timeout=20)
    if response.status_code != 200:
        return None
    data = response.json()
    entity = data.get("entities", {}).get(qid.upper(), {})
    title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
    return title.replace(" ", "_") if title else None


def fetch_wikipedia_physical_stats(row: dict[str, Any], session: requests.Session | None = None) -> PhysicalStats:
    http = session or requests.Session()
    title = wikipedia_title_from_row(row, http)
    if not title:
        return PhysicalStats()
    response = http.get(f"{WIKIPEDIA_REST_BASE_URL}/{quote(title, safe='')}", headers=HEADERS, timeout=20)
    if response.status_code != 200:
        return PhysicalStats()
    return parse_wikipedia_infobox(response.text)


def scrape_physical_stats(
    *,
    client: Any | None = None,
    fie_fetcher: Callable[[str], PhysicalStats] | None = None,
    wikipedia_fetcher: Callable[[dict[str, Any]], PhysicalStats] | None = None,
    limit: int = MAX_FENCERS,
    log_run: bool = True,
    update_state: bool = True,
    now: Callable[[], str] | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    timestamp = now or (lambda: datetime.now(timezone.utc).isoformat())
    session = requests.Session()
    session.headers.update(HEADERS)
    fie_fetcher = fie_fetcher or (lambda fie_id: fetch_fie_physical_stats(fie_id, session))
    wikipedia_fetcher = wikipedia_fetcher or (lambda row: fetch_wikipedia_physical_stats(row, session))

    previous_run = get_state(SOURCE, "last_run") if update_state else None
    summary = {
        "queried": 0,
        "processed": 0,
        "written": 0,
        "failed": 0,
        "skipped": 0,
        "previous_run": previous_run,
        "field_counts": {"height": 0, "weight": 0, "reach": 0},
    }

    try:
        rows = query_missing_physical_stats(client, limit=limit)
        summary["queried"] = len(rows)

        for row in rows:
            if was_already_attempted(row):
                summary["skipped"] += 1
                continue

            row_id = clean_text(row.get("id"))
            if not row_id:
                summary["failed"] += 1
                continue

            errors: list[str] = []
            source_stats: list[tuple[str, PhysicalStats]] = []
            fie_id = clean_text(row.get("fie_id"))
            if fie_id:
                try:
                    source_stats.append(("fie_athlete_profile", fie_fetcher(fie_id)))
                except Exception as exc:
                    errors.append(f"fie:{exc}")

            try:
                source_stats.append(("wikipedia_infobox", wikipedia_fetcher(row)))
            except Exception as exc:
                errors.append(f"wikipedia:{exc}")

            stats, sources = merge_source_stats(source_stats)
            attempted_at = timestamp()
            payload = build_update_payload(row, stats, sources, attempted_at=attempted_at, errors=errors)

            try:
                client.table("fs_fencers").update(payload).eq("id", row_id).execute()
            except Exception:
                summary["failed"] += 1
                continue

            summary["processed"] += 1
            written_fields = [field for field in PHYSICAL_FIELDS if field in payload]
            if written_fields:
                summary["written"] += 1
                for field in written_fields:
                    summary["field_counts"][field] += 1
            else:
                summary["skipped"] += 1

            if REQUEST_DELAY_SECONDS > 0 and (fie_id or _metadata_text(row, "wikipedia_title", "wikidata_id")):
                time.sleep(REQUEST_DELAY_SECONDS)

        if update_state:
            final_at = timestamp()
            set_state(SOURCE, "last_run", final_at)
            set_state(SOURCE, "last_summary", summary)

        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


if __name__ == "__main__":
    result = scrape_physical_stats()
    print(json.dumps(result, sort_keys=True))
