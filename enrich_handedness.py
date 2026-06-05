from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from scripts.rate_limiter import RateLimiter
except Exception:  # pragma: no cover - script remains usable without the helper.
    RateLimiter = None

try:
    from compute_transfers import country_key as transfer_country_key
except Exception:  # pragma: no cover - fallback is enough for standalone parsing tests.
    transfer_country_key = None  # type: ignore[assignment]


SOURCE = "enrich_handedness"
FIE_BASE_URL = "https://fie.org/athletes"
SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_HAND_PROPERTY = "P552"
WIKIDATA_FIE_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")

MAX_FENCERS = int(os.environ.get("HANDEDNESS_FENCER_LIMIT", "500"))
REQUEST_DELAY = float(os.environ.get("HANDEDNESS_REQUEST_DELAY", "1.0"))
BATCH_SELECT_SIZE = int(os.environ.get("HANDEDNESS_SELECT_BATCH_SIZE", "1000"))
UPSERT_BATCH_SIZE = int(os.environ.get("HANDEDNESS_UPSERT_BATCH_SIZE", "100"))
WIKIDATA_PAGE_SIZE = int(os.environ.get("HANDEDNESS_WIKIDATA_PAGE_SIZE", "5000"))

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "FenceSpace-Handedness/1.0 (https://fencespace.app)",
}
SPARQL_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace-Handedness/1.0 (https://fencespace.app)",
}

SOURCE_CONFIDENCE = {
    "wikidata": 0.98,
    "fie_profile": 0.95,
    "federation_profile": 0.85,
    "public_athlete_page": 0.80,
}
SOURCE_TYPES = set(SOURCE_CONFIDENCE)

HAND_LABEL_ALIASES = [
    "Handedness",
    "Dominant hand",
    "Fencing hand",
    "Weapon hand",
    "Hand",
    "Main dominante",
    "Main",
    "Mano dominante",
    "Mano",
    "Mao dominante",
    "Mao",
    "Uso de las manos",
]
HAND_LABEL_KEYS = set()

LEFT_VALUES = {
    "l",
    "handl",
    "left",
    "lefthanded",
    "lefthandedness",
    "lefty",
    "gauche",
    "maingauche",
    "gaucher",
    "gauchere",
    "izquierda",
    "manoizquierda",
    "izquierdo",
    "zurdo",
    "zurda",
    "sinistra",
    "manosinistra",
    "sinistro",
    "mancino",
    "mancina",
    "links",
    "linkshandig",
    "canhoto",
    "canhota",
    "esquerda",
    "esquerdo",
}
RIGHT_VALUES = {
    "r",
    "handr",
    "right",
    "righthanded",
    "righthandedness",
    "righty",
    "droite",
    "maindroite",
    "droitier",
    "droitiere",
    "derecha",
    "manoderecha",
    "derecho",
    "diestro",
    "diestra",
    "destra",
    "manodestra",
    "destro",
    "rechts",
    "rechtshandig",
    "direita",
    "direito",
}
AMBIDEXTROUS_VALUES = {
    "ambidextrous",
    "ambidextrousness",
    "ambidexterity",
    "ambidextre",
    "ambidiestro",
    "ambidiestra",
    "ambidestro",
    "ambidestra",
    "beidhandig",
}
UNKNOWN_VALUES = {
    "unknown",
    "unk",
    "na",
    "n/a",
    "notavailable",
    "notspecified",
    "notstated",
    "unspecified",
    "inconnu",
    "inconnue",
    "desconocido",
    "desconocida",
    "desconhecido",
    "desconhecida",
    "unbekannt",
    "nonrenseigne",
}
WIKIDATA_HAND_IDS = {
    "Q789447": "left",
    "Q3039938": "right",
    "Q457332": "ambidextrous",
}

FENCER_SELECT_CANDIDATES = [
    "id,name,country,fie_id,wikipedia_url,federation_profile_url,metadata",
    "id,name,country,fie_id,wikipedia_url,metadata",
    "id,name,country,fie_id,metadata",
]
IDENTITY_COLUMNS = "fs_fencer_row_ids,fie_ids"


def _build_label_keys() -> set[str]:
    return {_compact_key(label) for label in HAND_LABEL_ALIASES}


@dataclass(frozen=True)
class HandednessObservation:
    handedness: str
    source_url: str
    source_type: str
    confidence: float
    metadata: dict[str, Any]
    fencer_id: str | None = None
    fie_id: str | None = None
    wikidata_id: str | None = None
    name: str | None = None
    country: str | None = None


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _ascii_text(value: Any) -> str:
    text = clean_text(value) or ""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _spaced_key(value: Any) -> str:
    text = _ascii_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _compact_key(value: Any) -> str:
    return _spaced_key(value).replace(" ", "")


HAND_LABEL_KEYS = _build_label_keys()


def normalize_handedness(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    spaced = _spaced_key(text)
    compact = spaced.replace(" ", "")
    if compact in LEFT_VALUES:
        return "left"
    if compact in RIGHT_VALUES:
        return "right"
    if compact in AMBIDEXTROUS_VALUES:
        return "ambidextrous"
    if compact in UNKNOWN_VALUES or spaced in UNKNOWN_VALUES:
        return "unknown"
    return None


def _is_hand_label(value: Any) -> bool:
    return _compact_key(value) in HAND_LABEL_KEYS


def _profile_confidence(source_type: str, handedness: str) -> float:
    confidence = SOURCE_CONFIDENCE[source_type]
    if handedness == "unknown":
        return min(confidence, 0.4)
    return confidence


def _make_observation(
    *,
    handedness: str,
    source_url: str,
    source_type: str,
    label: str,
    raw_value: str,
    parser: str,
) -> HandednessObservation:
    return HandednessObservation(
        handedness=handedness,
        source_url=source_url,
        source_type=source_type,
        confidence=_profile_confidence(source_type, handedness),
        metadata={
            "label": label,
            "raw_value": raw_value,
            "parser": parser,
        },
    )


def _candidate_from_cells(cells: list[Any], parser: str):
    if len(cells) < 2:
        return
    label = clean_text(cells[0].get_text(" ", strip=True))
    raw_value = clean_text(cells[1].get_text(" ", strip=True))
    if label and raw_value and _is_hand_label(label):
        yield label, raw_value, parser


def _iter_visible_label_candidates(page_html: str):
    soup = BeautifulSoup(page_html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for item in soup.select(".ProfileInfo-item"):
        spans = item.find_all("span")
        yield from _candidate_from_cells(spans, "profile_info_item")

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        label = clean_text(dt.get_text(" ", strip=True))
        raw_value = clean_text(dd.get_text(" ", strip=True))
        if label and raw_value and _is_hand_label(label):
            yield label, raw_value, "definition_list"

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            cells = row.find_all(["th", "td"])
        yield from _candidate_from_cells(cells, "table_row")

    lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if _is_hand_label(line):
            yield line, lines[index + 1], "visible_text_pair"

    label_pattern = "|".join(
        re.escape(label) for label in sorted(HAND_LABEL_ALIASES, key=len, reverse=True)
    )
    combined_re = re.compile(rf"^\s*({label_pattern})\s*[:\-]?\s+(.+?)\s*$", re.I)
    for line in lines:
        match = combined_re.match(line)
        if match and _is_hand_label(match.group(1)):
            yield match.group(1), match.group(2), "visible_text_line"


def _iter_window_json_blocks(page_html: str):
    decoder = json.JSONDecoder()
    skip_names = {
        "__translations__",
        "dataLayer",
        "_headToHead",
        "_tabRanking",
        "_tabResults",
        "_tabOpponents",
    }
    for match in re.finditer(r"window\.([A-Za-z0-9_$]+)\s*=", page_html or ""):
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


def _iter_json_label_candidates(page_html: str):
    def scalar(value: Any) -> str | None:
        if isinstance(value, (str, int, float)):
            return clean_text(value)
        return None

    def walk(value: Any):
        if isinstance(value, dict):
            label = next(
                (
                    clean_text(value.get(key))
                    for key in ("label", "name", "title", "key")
                    if clean_text(value.get(key))
                ),
                None,
            )
            raw_value = next(
                (
                    scalar(value.get(key))
                    for key in ("value", "text", "answer", "displayValue")
                    if scalar(value.get(key))
                ),
                None,
            )
            if label and raw_value and _is_hand_label(label):
                yield label, raw_value, "json_label_value"

            for raw_key, raw_item in value.items():
                key_label = clean_text(raw_key)
                direct_value = scalar(raw_item)
                if key_label and direct_value and _is_hand_label(key_label):
                    yield key_label, direct_value, "json_direct_key"
                if isinstance(raw_item, (dict, list)):
                    yield from walk(raw_item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    for block in _iter_window_json_blocks(page_html):
        yield from walk(block)


def parse_profile_handedness(
    page_html: str,
    *,
    source_url: str,
    source_type: str,
) -> HandednessObservation | None:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source_type}")

    for label, raw_value, parser in _iter_visible_label_candidates(page_html):
        handedness = normalize_handedness(raw_value)
        if handedness:
            return _make_observation(
                handedness=handedness,
                source_url=source_url,
                source_type=source_type,
                label=label,
                raw_value=raw_value,
                parser=parser,
            )

    for label, raw_value, parser in _iter_json_label_candidates(page_html):
        handedness = normalize_handedness(raw_value)
        if handedness:
            return _make_observation(
                handedness=handedness,
                source_url=source_url,
                source_type=source_type,
                label=label,
                raw_value=raw_value,
                parser=parser,
            )
    return None


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    return clean_text((binding.get(key) or {}).get("value"))


def wikidata_entity_id(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1] or None


def parse_wikidata_binding(binding: dict[str, Any]) -> HandednessObservation | None:
    wikidata_id = wikidata_entity_id(binding_value(binding, "athlete"))
    if not wikidata_id:
        return None

    hand_id = wikidata_entity_id(binding_value(binding, "hand"))
    handedness = WIKIDATA_HAND_IDS.get(hand_id or "")
    hand_label = binding_value(binding, "handLabel")
    if not handedness:
        handedness = normalize_handedness(hand_label)
    if not handedness:
        return None

    return HandednessObservation(
        handedness=handedness,
        source_url=f"https://www.wikidata.org/wiki/{wikidata_id}",
        source_type="wikidata",
        confidence=_profile_confidence("wikidata", handedness),
        metadata={
            "wikidata_property": WIKIDATA_HAND_PROPERTY,
            "hand_id": hand_id,
            "hand_label": hand_label,
        },
        wikidata_id=wikidata_id,
        fie_id=binding_value(binding, "fie_id"),
        name=binding_value(binding, "athleteLabel"),
        country=binding_value(binding, "countryLabel"),
    )


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


def _country_key(value: Any) -> str:
    if transfer_country_key is not None:
        return transfer_country_key(value)
    key = _compact_key(value)
    aliases = {
        "usa": "usa",
        "unitedstates": "usa",
        "unitedstatesofamerica": "usa",
        "us": "usa",
        "france": "france",
    }
    return aliases.get(key, key)


def _name_key(value: Any) -> str:
    spaced = _spaced_key(value)
    if not spaced:
        return ""
    return " ".join(sorted(spaced.split()))


def build_identity_maps(
    identities: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    row_groups: dict[str, set[str]] = defaultdict(set)
    fie_groups: dict[str, set[str]] = defaultdict(set)

    for identity in identities:
        row_ids = set()
        for raw_row_id in identity.get("fs_fencer_row_ids") or []:
            row_id = clean_text(raw_row_id)
            if row_id:
                row_ids.add(row_id)
        if not row_ids:
            continue
        for row_id in row_ids:
            row_groups[row_id].update(row_ids)
        for fie_id in identity.get("fie_ids") or []:
            clean_fie_id = clean_text(fie_id)
            if clean_fie_id:
                fie_groups[clean_fie_id].update(row_ids)
    return row_groups, fie_groups


def build_fencer_indexes(fencers: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    by_fie_id: dict[str, set[str]] = defaultdict(set)
    by_wikidata_id: dict[str, set[str]] = defaultdict(set)
    by_name_country: dict[tuple[str, str], set[str]] = defaultdict(set)

    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        if not fencer_id:
            continue
        by_id[fencer_id] = fencer

        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id:
            by_fie_id[fie_id].add(fencer_id)

        metadata = ensure_metadata(fencer.get("metadata"))
        wikidata_id = clean_text(fencer.get("wikidata_id")) or clean_text(
            metadata.get("wikidata_id")
        )
        if wikidata_id:
            by_wikidata_id[wikidata_id].add(fencer_id)

        name = _name_key(fencer.get("name"))
        country = _country_key(fencer.get("country"))
        if name and country:
            by_name_country[(name, country)].add(fencer_id)

    return {
        "by_id": by_id,
        "by_fie_id": by_fie_id,
        "by_wikidata_id": by_wikidata_id,
        "by_name_country": by_name_country,
    }


def expand_with_identity(
    fencer_ids: set[str],
    *,
    fie_id: str | None,
    row_groups: dict[str, set[str]],
    fie_groups: dict[str, set[str]],
) -> set[str]:
    expanded = set(fencer_ids)
    for fencer_id in list(fencer_ids):
        expanded.update(row_groups.get(fencer_id, {fencer_id}))
    if fie_id:
        expanded.update(fie_groups.get(fie_id, set()))
    return expanded


def match_observation_to_fencers(
    observation: HandednessObservation,
    *,
    indexes: dict[str, Any],
    row_groups: dict[str, set[str]],
    fie_groups: dict[str, set[str]],
    ambiguous_log: list[dict[str, Any]],
) -> set[str]:
    fie_id = clean_text(observation.fie_id)
    matched: set[str] = set()

    fencer_id = clean_text(observation.fencer_id)
    if fencer_id and fencer_id in indexes["by_id"]:
        matched.add(fencer_id)

    wikidata_id = clean_text(observation.wikidata_id)
    if wikidata_id:
        matched.update(indexes["by_wikidata_id"].get(wikidata_id, set()))
    if fie_id:
        matched.update(indexes["by_fie_id"].get(fie_id, set()))
    if matched:
        return expand_with_identity(
            matched, fie_id=fie_id, row_groups=row_groups, fie_groups=fie_groups
        )

    name = _name_key(observation.name)
    country = _country_key(observation.country)
    if not name or not country:
        return set()

    candidates = set(indexes["by_name_country"].get((name, country), set()))
    if len(candidates) == 1:
        return expand_with_identity(
            candidates, fie_id=fie_id, row_groups=row_groups, fie_groups=fie_groups
        )
    if len(candidates) > 1:
        ambiguous_log.append(
            {
                "name": observation.name,
                "country": observation.country,
                "source_url": observation.source_url,
                "candidate_fencer_ids": sorted(candidates),
                "reason": "ambiguous_name_country_match",
            }
        )
    return set()


def build_handedness_rows(
    observation: HandednessObservation,
    fencer_ids: set[str],
    *,
    collected_at: str | None = None,
) -> list[dict[str, Any]]:
    collected = collected_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for fencer_id in sorted(fencer_ids):
        metadata = dict(observation.metadata)
        metadata.update(
            {
                "source_type": observation.source_type,
            }
        )
        if observation.wikidata_id:
            metadata["wikidata_id"] = observation.wikidata_id
        if observation.fie_id:
            metadata["fie_id"] = observation.fie_id
        if observation.name:
            metadata["source_name"] = observation.name
        if observation.country:
            metadata["source_country"] = observation.country

        rows.append(
            {
                "fencer_id": fencer_id,
                "handedness": observation.handedness,
                "source_url": observation.source_url,
                "confidence": round(float(observation.confidence), 2),
                "collected_at": collected,
                "metadata": metadata,
            }
        )
    return rows


def upsert_handedness_rows(
    supabase,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> int:
    if dry_run or not rows:
        return 0
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        supabase.table("fs_fencer_handedness").upsert(
            batch, on_conflict="fencer_id,source_url"
        ).execute()
        written += len(batch)
    return written


def get_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    try:
        from supabase import create_client
    except Exception as exc:
        raise RuntimeError("supabase package is required.") from exc
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(supabase_url, supabase_key)


def fetch_all(client, table: str, columns: str, *, page_size: int = BATCH_SELECT_SIZE):
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def fetch_optional(client, table: str, columns: str) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns)
    except Exception as exc:
        print(f"Optional table {table} unavailable: {exc}")
        return []


def fetch_fencers(client, *, limit: int = MAX_FENCERS) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in FENCER_SELECT_CANDIDATES:
        try:
            return (
                client.table("fs_fencers")
                .select(columns)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not load fs_fencers: {last_error}")


def _metadata_urls(metadata: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    urls: list[str] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str))
    return urls


def profile_sources_for_fencer(fencer: dict[str, Any]) -> list[tuple[str, str]]:
    metadata = ensure_metadata(fencer.get("metadata"))
    sources: list[tuple[str, str]] = []

    fie_id = clean_text(fencer.get("fie_id"))
    if fie_id:
        sources.append(("fie_profile", f"{FIE_BASE_URL}/{fie_id}"))

    federation_urls = [
        clean_text(fencer.get("federation_profile_url")),
        *_metadata_urls(
            metadata,
            (
                "federation_profile_url",
                "federation_bio_url",
                "national_federation_profile_url",
            ),
        ),
    ]
    public_urls = [
        clean_text(fencer.get("wikipedia_url")),
        *_metadata_urls(
            metadata,
            ("wikipedia_url", "public_athlete_url", "public_profile_url"),
        ),
    ]

    for url in federation_urls:
        if url:
            sources.append(("federation_profile", url))
    for url in public_urls:
        if url:
            sources.append(("public_athlete_page", url))

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source_type, url in sources:
        key = (source_type, url)
        if key not in seen:
            deduped.append(key)
            seen.add(key)
    return deduped


def _wait_for_url(url: str, limiter) -> str:
    domain = urlparse(url).netloc or "default"
    if limiter:
        limiter.wait(domain)
    elif REQUEST_DELAY > 0:
        time.sleep(REQUEST_DELAY)
    return domain


def fetch_profile_observations(
    fencers: list[dict[str, Any]],
    *,
    session: requests.Session,
    limiter=None,
) -> tuple[list[HandednessObservation], int]:
    observations: list[HandednessObservation] = []
    failed = 0

    for fencer in fencers:
        metadata = ensure_metadata(fencer.get("metadata"))
        for source_type, url in profile_sources_for_fencer(fencer):
            domain = _wait_for_url(url, limiter)
            try:
                response = session.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    failed += 1
                    if limiter:
                        limiter.record_failure(domain)
                    continue
                if limiter:
                    limiter.record_success(domain)
                observation = parse_profile_handedness(
                    response.text, source_url=url, source_type=source_type
                )
                if observation:
                    observations.append(
                        replace(
                            observation,
                            fencer_id=clean_text(fencer.get("id")),
                            fie_id=clean_text(fencer.get("fie_id")),
                            wikidata_id=clean_text(metadata.get("wikidata_id")),
                            name=clean_text(fencer.get("name")),
                            country=clean_text(fencer.get("country")),
                        )
                    )
            except Exception as exc:
                failed += 1
                if limiter:
                    limiter.record_failure(domain)
                print(f"Profile fetch failed for {url}: {exc}")

    return observations, failed


def build_wikidata_query(offset: int) -> str:
    return f"""
SELECT ?athlete ?athleteLabel ?fie_id ?countryLabel ?hand ?handLabel WHERE {{
  ?athlete wdt:P641 wd:Q12100 .
  ?athlete wdt:{WIKIDATA_HAND_PROPERTY} ?hand .
  OPTIONAL {{ ?athlete wdt:{WIKIDATA_FIE_PROPERTY} ?fie_id . }}
  OPTIONAL {{ ?athlete wdt:P27 ?country . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en,fr,es,de,it,pt" .
    ?athlete rdfs:label ?athleteLabel .
    ?hand rdfs:label ?handLabel .
    ?country rdfs:label ?countryLabel .
  }}
}}
LIMIT {WIKIDATA_PAGE_SIZE}
OFFSET {offset}
"""


def fetch_wikidata_handedness(
    *,
    session: requests.Session,
    limiter=None,
) -> tuple[list[HandednessObservation], int]:
    observations: list[HandednessObservation] = []
    failed = 0
    offset = 0

    while True:
        domain = _wait_for_url(SPARQL_URL, limiter)
        try:
            response = session.get(
                SPARQL_URL,
                headers=SPARQL_HEADERS,
                params={"query": build_wikidata_query(offset), "format": "json"},
                timeout=45,
            )
            if response.status_code != 200:
                failed += 1
                if limiter:
                    limiter.record_failure(domain)
                break
            if limiter:
                limiter.record_success(domain)
            bindings = response.json().get("results", {}).get("bindings", [])
        except Exception as exc:
            failed += 1
            if limiter:
                limiter.record_failure(domain)
            print(f"Wikidata handedness fetch failed: {exc}")
            break

        for binding in bindings:
            observation = parse_wikidata_binding(binding)
            if observation:
                observations.append(observation)
        if len(bindings) < WIKIDATA_PAGE_SIZE:
            break
        offset += WIKIDATA_PAGE_SIZE

    return observations, failed


def dedupe_handedness_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["fencer_id"], row["source_url"])
        existing = best.get(key)
        if not existing:
            best[key] = row
            continue
        if existing["handedness"] == "unknown" and row["handedness"] != "unknown":
            best[key] = row
        elif float(row["confidence"]) > float(existing["confidence"]):
            best[key] = row
    return list(best.values())


def scrape_handedness(
    supabase,
    *,
    session: requests.Session | None = None,
    limit: int = MAX_FENCERS,
    dry_run: bool = False,
    include_profiles: bool = True,
    include_wikidata: bool = True,
) -> dict[str, Any]:
    session = session or requests.Session()
    limiter = RateLimiter(default_rps=1.0 / REQUEST_DELAY, jitter=0.1, backoff=2.0) if RateLimiter and REQUEST_DELAY > 0 else None

    fencers = fetch_fencers(supabase, limit=limit)
    identities = fetch_optional(supabase, "fs_fencer_identities", IDENTITY_COLUMNS)
    row_groups, fie_groups = build_identity_maps(identities)
    indexes = build_fencer_indexes(fencers)

    observations: list[HandednessObservation] = []
    failed = 0
    if include_profiles:
        profile_observations, profile_failed = fetch_profile_observations(
            fencers, session=session, limiter=limiter
        )
        observations.extend(profile_observations)
        failed += profile_failed
    if include_wikidata:
        wikidata_observations, wikidata_failed = fetch_wikidata_handedness(
            session=session, limiter=limiter
        )
        observations.extend(wikidata_observations)
        failed += wikidata_failed

    ambiguous_log: list[dict[str, Any]] = []
    skipped = 0
    rows: list[dict[str, Any]] = []
    collected_at = datetime.now(timezone.utc).isoformat()
    for observation in observations:
        fencer_ids = match_observation_to_fencers(
            observation,
            indexes=indexes,
            row_groups=row_groups,
            fie_groups=fie_groups,
            ambiguous_log=ambiguous_log,
        )
        if not fencer_ids:
            skipped += 1
            continue
        rows.extend(
            build_handedness_rows(
                observation, fencer_ids, collected_at=collected_at
            )
        )

    rows = dedupe_handedness_rows(rows)
    written = upsert_handedness_rows(supabase, rows, dry_run=dry_run)
    return {
        "fencers_loaded": len(fencers),
        "observations_collected": len(observations),
        "rows_collected": len(rows),
        "rows_written": written,
        "failed": failed,
        "skipped": skipped + len(ambiguous_log),
        "ambiguous_matches": ambiguous_log[:20],
        "ambiguous_match_count": len(ambiguous_log),
        "dry_run": dry_run,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich fencer handedness data.")
    parser.add_argument("--dry-run", action="store_true", help="Parse without upserting handedness rows.")
    parser.add_argument("--limit", type=int, default=MAX_FENCERS, help="Maximum fencers to inspect for profile URLs.")
    parser.add_argument("--skip-profiles", action="store_true", help="Skip FIE/federation/public profile fetching.")
    parser.add_argument("--skip-wikidata", action="store_true", help="Skip Wikidata P552 fetching.")
    return parser.parse_args()


def main() -> None:
    from run_logger import ScraperRunLogger
    from scraper_state import get_state, set_state

    args = parse_args()
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous handedness state: {previous_state}")

        supabase = get_client()
        summary = scrape_handedness(
            supabase,
            limit=args.limit,
            dry_run=args.dry_run,
            include_profiles=not args.skip_profiles,
            include_wikidata=not args.skip_wikidata,
        )
        if not args.dry_run:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        run_log.complete(
            written=summary["rows_written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Handedness enrichment complete: "
            f"{summary['rows_collected']} rows collected, "
            f"{summary['rows_written']} rows written, "
            f"{summary['skipped']} skipped, {summary['failed']} failed"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
