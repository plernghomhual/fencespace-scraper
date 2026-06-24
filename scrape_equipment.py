from __future__ import annotations

import html
import json
import os
import re
import time
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_equipment"
FIE_BASE_URL = "https://fie.org/athletes"
MAX_FENCERS = int(os.environ.get("EQUIPMENT_FENCER_LIMIT", "1000"))
REQUEST_DELAY_SECONDS = float(os.environ.get("EQUIPMENT_REQUEST_DELAY", "1.0"))
UPSERT_BATCH_SIZE = int(os.environ.get("EQUIPMENT_UPSERT_BATCH_SIZE", "100"))

HEADERS = {
    "User-Agent": "FenceSpace/1.0 equipment scraper",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SELECT_COLUMN_CANDIDATES = [
    "id,name,fie_id,country,bio_text,wikipedia_url,federation_profile_url,metadata",
    "id,name,fie_id,country,bio_text,metadata",
    "id,name,fie_id,country,metadata",
]

PROFILE_SOURCES = {"fie_profile", "federation_profile"}
SHORT_ALIASES = {"AF", "LP", "OK", "SG"}

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "Allstar": ("Allstar", "Allstar Uhlmann"),
    "Uhlmann": ("Uhlmann",),
    "Leon Paul": ("Leon Paul", "LP"),
    "Prieur": ("Prieur",),
    "Absolute Fencing": ("Absolute Fencing", "AF"),
    "Negrini": ("Negrini",),
    "FWF": ("FWF",),
    "Carmimari": ("Carmimari",),
    "Blaise Frères": ("Blaise Frères", "Blaise Freres"),
    "Triplette": ("Triplette",),
    "Versari": ("Versari",),
    "Favero": ("Favero",),
    "SG": ("SG",),
    "OK": ("OK",),
    "Dynamo": ("Dynamo",),
    "PBT": ("PBT",),
    "Blue Gauntlet": ("Blue Gauntlet",),
    "Victory": ("Victory",),
    "Wuxi": ("Wuxi",),
}

SPONSOR_RE = re.compile(
    r"\b(sponsor(?:ed|ship|s)?|partner(?:ed|s)?|ambassador|supported by|outfitted by)\b",
    re.IGNORECASE,
)
UNRELATED_SUBJECT_RE = re.compile(
    r"\b(another|different|other|opponent|rival)\s+(athlete|fencer|teammate)\b",
    re.IGNORECASE,
)

EQUIPMENT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("mask", "mask"),
    ("visor", "mask"),
    ("jacket", "jacket"),
    ("uniform", "jacket"),
    ("plastron", "jacket"),
    ("knickers", "jacket"),
    ("lame", "jacket"),
    ("lamé", "jacket"),
    ("weapon", "weapon"),
    ("blade", "weapon"),
    ("foil", "weapon"),
    ("epee", "weapon"),
    ("épée", "weapon"),
    ("sabre", "weapon"),
    ("saber", "weapon"),
    ("grip", "weapon"),
)

_supabase = None


@dataclass(frozen=True)
class EquipmentMention:
    brand: str
    equipment_type: str | None
    sponsor_name: str | None
    source: str
    source_url: str | None
    confidence: str
    metadata: dict[str, Any]


def get_supabase():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def clean_text(value: Any) -> str:
    raw = "" if value is None else str(value)
    text = html.unescape(raw).replace("\xa0", " ")
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def compare_text(value: str) -> str:
    text = strip_accents(unicodedata.normalize("NFKC", value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_in_text(text: str, fencer_name: str | None) -> bool:
    if not fencer_name:
        return True
    normalized_text = compare_text(text)
    normalized_name = compare_text(fencer_name)
    if not normalized_name:
        return True
    if normalized_name in normalized_text:
        return True
    parts = [part for part in normalized_name.split() if len(part) > 1]
    if len(parts) >= 2 and " ".join(reversed(parts)) in normalized_text:
        return True
    return len(parts) >= 2 and all(part in normalized_text for part in parts)


def sentence_window(text: str, position: int) -> str:
    start_candidates = [text.rfind(mark, 0, position) for mark in ".!?\n"]
    start = max(start_candidates)
    start = 0 if start < 0 else start + 1
    end_candidates = [idx for idx in (text.find(mark, position) for mark in ".!?\n") if idx >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end].strip()


def context_window(text: str, position: int, radius: int = 220) -> str:
    return text[max(0, position - radius) : min(len(text), position + radius)].strip()


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if alias in SHORT_ALIASES:
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def iter_brand_hits(text: str) -> Iterable[tuple[str, str, re.Match[str]]]:
    aliases: list[tuple[str, str]] = []
    for brand, brand_aliases in BRAND_ALIASES.items():
        for alias in brand_aliases:
            aliases.append((brand, alias))
    aliases.sort(key=lambda item: len(item[1]), reverse=True)

    for brand, alias in aliases:
        for match in alias_pattern(alias).finditer(text):
            yield brand, alias, match


def nearest_equipment_type(text: str, brand_position: int) -> str | None:
    best: tuple[int, str] | None = None
    for keyword, equipment_type in EQUIPMENT_KEYWORDS:
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", re.IGNORECASE)
        for match in pattern.finditer(text):
            distance = abs(match.start() - brand_position)
            if best is None or distance < best[0]:
                best = (distance, equipment_type)
    return best[1] if best else None


def nearest_pattern_distance(pattern: re.Pattern[str], text: str, position: int) -> int | None:
    distances = [abs(match.start() - position) for match in pattern.finditer(text)]
    return min(distances) if distances else None


def equipment_type_for_brand(sentence: str, brand_position: int) -> str | None:
    equipment_type = nearest_equipment_type(sentence, brand_position)
    sponsor_distance = nearest_pattern_distance(SPONSOR_RE, sentence, brand_position)
    if sponsor_distance is not None:
        equipment_distance = min(
            (
                abs(match.start() - brand_position)
                for keyword, _equipment_type in EQUIPMENT_KEYWORDS
                for match in re.finditer(
                    rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])",
                    sentence,
                    flags=re.IGNORECASE,
                )
            ),
            default=None,
        )
        if equipment_distance is None or sponsor_distance <= equipment_distance:
            return None
    return equipment_type


def has_required_name_context(text: str, source: str, fencer_name: str | None, position: int) -> bool:
    if not fencer_name or source in PROFILE_SOURCES:
        return True
    sentence = sentence_window(text, position)
    if UNRELATED_SUBJECT_RE.search(sentence):
        return False
    return name_in_text(sentence, fencer_name) or name_in_text(context_window(text, position, radius=360), fencer_name)


def mention_confidence(sentence: str, equipment_type: str | None) -> str:
    if SPONSOR_RE.search(sentence):
        return "high"
    if equipment_type:
        return "medium"
    return "low"


def extract_equipment_mentions(
    text: str,
    *,
    fencer_name: str | None = None,
    source: str,
    source_url: str | None = None,
) -> list[EquipmentMention]:
    cleaned = clean_text(text)
    if not cleaned:
        return []

    mentions: list[EquipmentMention] = []
    seen: set[tuple[str, str | None, str, str | None]] = set()
    occupied_spans: list[tuple[int, int, str]] = []

    for brand, alias, match in iter_brand_hits(cleaned):
        if any(match.start() >= start and match.end() <= end and brand != existing for start, end, existing in occupied_spans):
            continue

        sentence = sentence_window(cleaned, match.start())
        context = context_window(cleaned, match.start())
        equipment_type = equipment_type_for_brand(sentence, match.start() - (cleaned.find(sentence) if sentence else 0))
        has_signal = SPONSOR_RE.search(sentence) is not None or equipment_type is not None

        if alias in SHORT_ALIASES and not has_signal:
            continue
        if not has_required_name_context(cleaned, source, fencer_name, match.start()):
            continue
        if not has_signal and not name_in_text(context, fencer_name):
            continue

        sponsor_name = brand if SPONSOR_RE.search(sentence) else None
        key = (brand, equipment_type, source, source_url)
        if key in seen:
            continue
        seen.add(key)
        occupied_spans.append((match.start(), match.end(), brand))
        mentions.append(
            EquipmentMention(
                brand=brand,
                equipment_type=equipment_type,
                sponsor_name=sponsor_name,
                source=source,
                source_url=source_url,
                confidence=mention_confidence(sentence, equipment_type),
                metadata={
                    "matched_alias": alias,
                    "context": context[:300],
                    "fencer_name": fencer_name,
                },
            )
        )

    return mentions


def deterministic_equipment_id(
    fencer_id: str,
    brand: str,
    equipment_type: str | None,
    source: str,
    source_url: str | None,
) -> str:
    raw_key = "|".join([fencer_id, brand, equipment_type or "", source, source_url or ""])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace:equipment:{raw_key}"))


def build_equipment_rows(fencer: dict[str, Any], mentions: list[EquipmentMention]) -> list[dict[str, Any]]:
    fencer_id = clean_text(fencer.get("id"))
    if not fencer_id:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str, str | None]] = set()
    for mention in mentions:
        key = (mention.brand, mention.equipment_type, mention.source, mention.source_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": deterministic_equipment_id(
                    fencer_id,
                    mention.brand,
                    mention.equipment_type,
                    mention.source,
                    mention.source_url,
                ),
                "fencer_id": fencer_id,
                "brand": mention.brand,
                "equipment_type": mention.equipment_type,
                "sponsor_name": mention.sponsor_name,
                "source": mention.source,
                "source_url": mention.source_url,
                "confidence": mention.confidence,
                "metadata": dict(mention.metadata),
            }
        )
    return rows


def load_fencers(client, limit: int = MAX_FENCERS) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in SELECT_COLUMN_CANDIDATES:
        try:
            return client.table("fs_fencers").select(columns).limit(limit).execute().data or []
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def fetch_url(session: requests.Session, url: str) -> str | None:
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        print(f"  Fetch failed for {url}: {exc}")
        return None
    if response.status_code != 200:
        print(f"  HTTP {response.status_code} for {url}")
        return None
    return response.text


def value_from_row_or_metadata(row: dict[str, Any], keys: Iterable[str]) -> Any:
    metadata = metadata_dict(row)
    for key in keys:
        value = row.get(key)
        if value:
            return value
        value = metadata.get(key)
        if value:
            return value
    return None


def federation_profile_urls(row: dict[str, Any]) -> list[str]:
    metadata = metadata_dict(row)
    keys = [
        "federation_profile_url",
        "national_federation_profile_url",
        "federation_url",
        "profile_url",
    ]
    urls: list[str] = []
    for key in keys:
        for source in (row, metadata):
            value = source.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.append(value)
    for key in ("federation_profile_urls", "profile_urls"):
        value = metadata.get(key)
        if isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str) and item.startswith(("http://", "https://")))
    return sorted(set(urls))


def wikipedia_source_url(row: dict[str, Any]) -> str | None:
    value = value_from_row_or_metadata(row, ["wikipedia_url", "wiki_url"])
    return value if isinstance(value, str) else None


def source_texts_for_fencer(
    fencer: dict[str, Any],
    session: requests.Session,
    *,
    fetch_fie: bool = True,
    fetch_federation: bool = True,
) -> list[tuple[str, str | None, str]]:
    sources: list[tuple[str, str | None, str]] = []
    bio_text = clean_text(fencer.get("bio_text") or metadata_dict(fencer).get("bio_text"))
    if bio_text:
        sources.append(("wikipedia_bio", wikipedia_source_url(fencer), bio_text))

    fie_id = clean_text(fencer.get("fie_id"))
    if fetch_fie and fie_id:
        url = f"{FIE_BASE_URL}/{fie_id}"
        text = fetch_url(session, url)
        if text:
            sources.append(("fie_profile", url, text))

    if fetch_federation:
        for url in federation_profile_urls(fencer):
            text = fetch_url(session, url)
            if text:
                sources.append(("federation_profile", url, text))

    return sources


def upsert_equipment_rows(client, rows: list[dict[str, Any]], batch_size: int = UPSERT_BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_fencer_equipment").upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Equipment upsert batch {index // batch_size} failed: {exc}")
            for row in batch:
                try:
                    client.table("fs_fencer_equipment").upsert([row], on_conflict="id").execute()
                    written += 1
                except Exception as row_exc:
                    failed += 1
                    print(f"    Equipment upsert failed for {row.get('id')}: {row_exc}")
    return written, failed


def scrape_fencer_equipment(
    fencers: list[dict[str, Any]],
    session: requests.Session,
    *,
    fetch_fie: bool = True,
    fetch_federation: bool = True,
    sleeper=time.sleep,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for fencer in fencers:
        fencer_name = clean_text(fencer.get("name"))
        if not fencer_name:
            skipped += 1
            continue

        source_rows: list[dict[str, Any]] = []
        for source, source_url, text in source_texts_for_fencer(
            fencer,
            session,
            fetch_fie=fetch_fie,
            fetch_federation=fetch_federation,
        ):
            mentions = extract_equipment_mentions(
                text,
                fencer_name=fencer_name,
                source=source,
                source_url=source_url,
            )
            source_rows.extend(build_equipment_rows(fencer, mentions))

        if source_rows:
            rows.extend(source_rows)
        else:
            skipped += 1
        sleeper(REQUEST_DELAY_SECONDS)
    return rows, skipped


def run(
    client=None,
    session: requests.Session | None = None,
    *,
    limit: int = MAX_FENCERS,
    fetch_fie: bool = True,
    fetch_federation: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase()
    session = session or requests.Session()
    session.headers.update(HEADERS)
    run_log = ScraperRunLogger(SOURCE).start()

    try:
        previous_state = get_state(SOURCE, "last_run")
        fencers = load_fencers(client, limit=limit)
        rows, skipped = scrape_fencer_equipment(
            fencers,
            session,
            fetch_fie=fetch_fie,
            fetch_federation=fetch_federation,
        )
        written, failed = upsert_equipment_rows(client, rows) if rows else (0, 0)
        summary = {
            "ran_at": datetime.now(UTC).isoformat(),
            "previous_run": previous_state,
            "fencers_scanned": len(fencers),
            "equipment_rows_found": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main() -> None:
    summary = run()
    print(
        "Equipment scrape complete: scanned={fencers_scanned}, found={equipment_rows_found}, "
        "written={written}, failed={failed}, skipped={skipped}".format(**summary)
    )


if __name__ == "__main__":
    main()
