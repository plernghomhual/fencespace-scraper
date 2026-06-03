from __future__ import annotations

import os
import re
import time
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scrape_equipment import (
    BRAND_ALIASES,
    HEADERS as EQUIPMENT_HEADERS,
    extract_equipment_mentions,
    metadata_dict,
)

try:
    from scripts.rate_limiter import RateLimiter
except Exception:  # pragma: no cover - import fallback for minimal environments
    RateLimiter = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_equipment_trends"
FIE_BASE_URL = "https://fie.org/athletes"
PAGE_SIZE = int(os.environ.get("EQUIPMENT_TRENDS_PAGE_SIZE", "1000"))
UPSERT_BATCH_SIZE = int(os.environ.get("EQUIPMENT_TRENDS_UPSERT_BATCH_SIZE", "200"))
REQUEST_DELAY_SECONDS = float(os.environ.get("EQUIPMENT_TRENDS_REQUEST_DELAY", "1.0"))
FETCH_FIE_PROFILES = os.environ.get("EQUIPMENT_TRENDS_FETCH_FIE", "").casefold() in {"1", "true", "yes"}
MAX_PROFILE_FETCHES = int(os.environ.get("EQUIPMENT_TRENDS_PROFILE_LIMIT", "100"))

CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.6, "low": 0.25}
VALID_CONFIDENCE = set(CONFIDENCE_WEIGHTS)

EQUIPMENT_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "mask": ("mask", "visor"),
    "weapon": ("weapon", "blade", "grip", "foil", "epee", "sabre", "saber"),
    "uniform": (
        "jacket",
        "uniform",
        "plastron",
        "knickers",
        "lame",
        "electric jacket",
        "clothing",
    ),
    "glove": ("glove", "gloves"),
    "shoes": ("shoe", "shoes", "footwear"),
    "body cord": ("body cord", "bodycord", "cord"),
    "scoring": ("scoring", "box", "reel", "machine"),
    "bag": ("bag", "case"),
    "sponsor": ("sponsor", "sponsorship", "partner", "ambassador"),
}

WEAPON_ALIASES = {
    "epee": "Epee",
    "foil": "Foil",
    "sabre": "Sabre",
    "saber": "Sabre",
}

TIER_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Olympic Games", ("olympic games", "olympics")),
    ("World Championships", ("world championships", "world championship")),
    ("World Cup", ("world cup",)),
    ("Grand Prix", ("grand prix",)),
    ("Zonal Championships", ("zonal", "continental championships", "european championships", "asian championships")),
    ("National", ("national",)),
)

_supabase = None
_fie_limiter = RateLimiter(default_rps=0.67, jitter=0.2, backoff=5.0) if RateLimiter else None


@dataclass(frozen=True)
class BrandCatalog:
    aliases: dict[str, str]


@dataclass(frozen=True)
class ProfileEquipmentEvidence:
    brand: str
    equipment_category: str
    source: str
    source_url: str | None
    confidence: str
    metadata: dict[str, Any]


def get_supabase_client():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def normalize_key(value: Any) -> str:
    text = strip_accents(unicodedata.normalize("NFKC", clean_text(value) or "")).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_key(value: Any) -> str:
    return normalize_key(value).replace(" ", "")


def title_brand(value: str) -> str:
    words = []
    for word in normalize_key(value).split():
        if len(word) <= 3 and word.isalpha():
            words.append(word.upper())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def build_brand_catalog(product_rows: Iterable[dict[str, Any]]) -> BrandCatalog:
    aliases: dict[str, str] = {}
    for canonical, canonical_aliases in BRAND_ALIASES.items():
        aliases[normalize_key(canonical)] = canonical
        for alias in canonical_aliases:
            aliases[normalize_key(alias)] = canonical

    for row in product_rows:
        brand = clean_text(row.get("brand"))
        if not brand:
            continue
        canonical = normalize_brand(brand, BrandCatalog(aliases)) if aliases else title_brand(brand)
        aliases.setdefault(normalize_key(canonical), canonical)
        aliases.setdefault(normalize_key(brand), canonical)

    return BrandCatalog(aliases=aliases)


def normalize_brand(value: Any, catalog: BrandCatalog) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in catalog.aliases:
        return catalog.aliases[key]

    compact = key.replace(" ", "")
    for alias_key, canonical in sorted(catalog.aliases.items(), key=lambda item: len(item[0]), reverse=True):
        alias_compact = alias_key.replace(" ", "")
        if not alias_compact:
            continue
        if compact == alias_compact or compact.startswith(alias_compact) or alias_compact in compact:
            return canonical
    return title_brand(text)


def normalize_equipment_category(value: Any, *, sponsor: bool = False) -> str | None:
    if sponsor and not value:
        return "sponsor"
    key = normalize_key(value)
    if not key:
        return "sponsor" if sponsor else None
    for category, aliases in EQUIPMENT_CATEGORY_ALIASES.items():
        if any(normalize_key(alias) in key for alias in aliases):
            return category
    return key


def normalize_weapon(value: Any) -> str | None:
    key = normalize_key(value)
    if not key:
        return None
    for alias, weapon in WEAPON_ALIASES.items():
        if alias in key.split() or alias == key:
            return weapon
    return None


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def confidence_bucket(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def strongest_confidence(values: Iterable[Any]) -> str:
    best = "low"
    best_score = CONFIDENCE_WEIGHTS[best]
    for value in values:
        confidence = clean_text(value) or "low"
        score = CONFIDENCE_WEIGHTS.get(confidence, 0.0)
        if score > best_score:
            best = confidence
            best_score = score
    return best


def normalized_country(value: Any) -> str | None:
    text = clean_text(value)
    return normalize_key(text) if text else None


def name_variants(value: Any) -> set[str]:
    name = normalize_key(value)
    if not name:
        return set()
    variants = {name}
    parts = name.split()
    if len(parts) >= 2:
        variants.add(" ".join(reversed(parts)))
    return variants


def deterministic_uuid(namespace: str, parts: Iterable[Any]) -> str:
    raw = "|".join(clean_text(part) or "" for part in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace:{namespace}:{raw}"))


def normalize_event_tier(tournament: dict[str, Any] | None) -> str | None:
    if not tournament:
        return None
    metadata = metadata_dict(tournament)
    direct = clean_text(tournament.get("tier")) or clean_text(metadata.get("tier"))
    if direct:
        return direct

    haystack = " ".join(
        clean_text(value) or ""
        for value in (
            tournament.get("competition_type"),
            tournament.get("type"),
            metadata.get("competition_type"),
            metadata.get("event_tier"),
            tournament.get("name"),
            tournament.get("category"),
        )
    ).casefold()
    for tier, patterns in TIER_ALIASES:
        if any(pattern in haystack for pattern in patterns):
            return tier

    event_type = clean_text(tournament.get("type")) or clean_text(metadata.get("type"))
    return event_type


def result_country(result: dict[str, Any]) -> str | None:
    return clean_text(result.get("country")) or clean_text(result.get("nationality"))


def result_rank(result: dict[str, Any]) -> int | None:
    return coerce_int(result.get("rank")) or coerce_int(result.get("placement"))


def extract_profile_evidence(
    text: str,
    *,
    fencer_name: str | None,
    source: str,
    source_url: str | None = None,
    brand_catalog: BrandCatalog,
) -> list[ProfileEquipmentEvidence]:
    evidence: list[ProfileEquipmentEvidence] = []
    for mention in extract_equipment_mentions(
        text,
        fencer_name=fencer_name,
        source=source,
        source_url=source_url,
    ):
        if mention.confidence == "low":
            continue
        brand = normalize_brand(mention.brand, brand_catalog)
        category = normalize_equipment_category(
            mention.equipment_type,
            sponsor=bool(mention.sponsor_name),
        )
        if not brand or not category:
            continue
        evidence.append(
            ProfileEquipmentEvidence(
                brand=brand,
                equipment_category=category,
                source=source,
                source_url=source_url,
                confidence=mention.confidence,
                metadata=dict(mention.metadata),
            )
        )
    return evidence


def equipment_row_to_source(row: dict[str, Any], brand_catalog: BrandCatalog) -> tuple[dict[str, Any] | None, bool]:
    confidence = clean_text(row.get("confidence")) or "medium"
    if confidence not in VALID_CONFIDENCE or confidence == "low":
        return None, True

    brand = normalize_brand(row.get("brand"), brand_catalog)
    category = normalize_equipment_category(
        row.get("equipment_type") or row.get("equipment_category") or metadata_dict(row).get("equipment_category"),
        sponsor=bool(row.get("sponsor_name")),
    )
    fencer_id = clean_text(row.get("fencer_id"))
    if not brand or not category or not fencer_id:
        return None, True

    return (
        {
            "equipment_evidence_id": clean_text(row.get("id")) or clean_text(row.get("equipment_evidence_id")),
            "fencer_id": fencer_id,
            "brand": brand,
            "equipment_category": category,
            "source": clean_text(row.get("source")) or "fs_fencer_equipment",
            "source_url": clean_text(row.get("source_url")),
            "confidence": confidence,
            "metadata": metadata_dict(row),
        },
        False,
    )


def profile_evidence_to_source(
    fencer: dict[str, Any],
    mention: ProfileEquipmentEvidence,
) -> dict[str, Any] | None:
    fencer_id = clean_text(fencer.get("id"))
    if not fencer_id:
        return None
    return {
        "equipment_evidence_id": deterministic_uuid(
            "equipment-profile-evidence",
            [fencer_id, mention.brand, mention.equipment_category, mention.source, mention.source_url],
        ),
        "fencer_id": fencer_id,
        "brand": mention.brand,
        "equipment_category": mention.equipment_category,
        "source": mention.source,
        "source_url": mention.source_url,
        "confidence": mention.confidence,
        "metadata": dict(mention.metadata),
    }


def build_fencer_indexes(fencers: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    by_fie_id: dict[str, str] = {}
    name_country: dict[tuple[str, str], set[str]] = defaultdict(set)
    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        if not fencer_id:
            continue
        by_id[fencer_id] = fencer
        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id:
            by_fie_id[fie_id] = fencer_id
        country = normalized_country(fencer.get("country") or fencer.get("nationality"))
        if country:
            for variant in name_variants(fencer.get("name")):
                name_country[(variant, country)].add(fencer_id)
    return {"by_id": by_id, "by_fie_id": by_fie_id, "name_country": name_country}


def matched_fencer_ids(result: dict[str, Any], indexes: dict[str, Any]) -> list[str]:
    matches: list[str] = []
    fencer_id = clean_text(result.get("fencer_id"))
    if fencer_id and fencer_id in indexes["by_id"]:
        matches.append(fencer_id)

    fie_id = clean_text(result.get("fie_fencer_id"))
    if fie_id and fie_id in indexes["by_fie_id"]:
        matches.append(indexes["by_fie_id"][fie_id])

    country = normalized_country(result_country(result))
    if country:
        for variant in name_variants(result.get("name")):
            candidates = indexes["name_country"].get((variant, country), set())
            if len(candidates) == 1:
                matches.extend(candidates)

    seen: set[str] = set()
    unique: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)
    return unique


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def evidence_weapon(
    result: dict[str, Any],
    tournament: dict[str, Any] | None,
    fencer: dict[str, Any] | None,
) -> str | None:
    return (
        normalize_weapon(result.get("weapon"))
        or normalize_weapon(tournament.get("weapon") if tournament else None)
        or normalize_weapon(fencer.get("weapon") if fencer else None)
    )


def build_evidence_rows(
    equipment_rows: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    *,
    brand_catalog: BrandCatalog,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = updated_at or utc_now()
    indexes = build_fencer_indexes(fencers)
    tournaments_by_id = tournament_lookup(tournaments)
    source_by_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = 0

    for raw_row in equipment_rows:
        source_row, was_skipped = equipment_row_to_source(raw_row, brand_catalog)
        if was_skipped:
            skipped += 1
            continue
        if source_row:
            source_by_fencer[source_row["fencer_id"]].append(source_row)

    evidence_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for result in results:
        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        rank = result_rank(result)
        result_id = clean_text(result.get("id"))
        result_name = clean_text(result.get("name"))
        for fencer_id in matched_fencer_ids(result, indexes):
            fencer = indexes["by_id"].get(fencer_id)
            weapon = evidence_weapon(result, tournament, fencer)
            if not weapon:
                skipped += len(source_by_fencer.get(fencer_id, []))
                continue
            event_tier = normalize_event_tier(tournament)
            for source_row in source_by_fencer.get(fencer_id, []):
                evidence_id = deterministic_uuid(
                    "equipment-trend-evidence",
                    [
                        source_row.get("equipment_evidence_id"),
                        fencer_id,
                        tournament_id,
                        result_id or result_name,
                        rank,
                        source_row["brand"],
                        source_row["equipment_category"],
                        weapon,
                        event_tier,
                    ],
                )
                if evidence_id in seen_ids:
                    continue
                seen_ids.add(evidence_id)
                metadata = dict(source_row.get("metadata") or {})
                metadata["equipment_evidence_id"] = source_row.get("equipment_evidence_id")
                metadata["matched_result_country"] = result_country(result)
                evidence_rows.append(
                    {
                        "id": evidence_id,
                        "brand": source_row["brand"],
                        "equipment_category": source_row["equipment_category"],
                        "weapon": weapon,
                        "event_tier": event_tier,
                        "fencer_id": fencer_id,
                        "result_id": result_id,
                        "tournament_id": tournament_id,
                        "result_rank": rank,
                        "result_name": result_name,
                        "source": source_row["source"],
                        "source_url": source_row.get("source_url"),
                        "evidence_type": "profile_or_sponsor_text",
                        "confidence": source_row["confidence"],
                        "metadata": metadata,
                        "updated_at": now,
                    }
                )

    return evidence_rows, skipped


def aggregate_trend_rows(evidence_rows: list[dict[str, Any]], updated_at: str | None = None) -> list[dict[str, Any]]:
    now = updated_at or utc_now()
    grouped: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for row in evidence_rows:
        key = (row["brand"], row["equipment_category"], row["weapon"], row.get("event_tier"))
        group = grouped.setdefault(
            key,
            {
                "brand": row["brand"],
                "equipment_category": row["equipment_category"],
                "weapon": row["weapon"],
                "event_tier": row.get("event_tier"),
                "evidence_ids": set(),
                "result_ids": set(),
                "win_count": 0,
                "podium_count": 0,
                "top8_count": 0,
                "sources": set(),
                "confidence_scores": [],
                "confidences": [],
            },
        )
        group["evidence_ids"].add(row["id"] if row.get("id") else deterministic_uuid("equipment-evidence-inline", row.values()))
        result_id = clean_text(row.get("result_id")) or clean_text(row.get("result_name"))
        if result_id:
            group["result_ids"].add(result_id)
        rank = coerce_int(row.get("result_rank"))
        if rank == 1:
            group["win_count"] += 1
        if rank is not None and rank <= 3:
            group["podium_count"] += 1
        if rank is not None and rank <= 8:
            group["top8_count"] += 1
        source = clean_text(row.get("source"))
        if source:
            group["sources"].add(source)
        group["confidence_scores"].append(CONFIDENCE_WEIGHTS.get(row.get("confidence"), 0.0))
        group["confidences"].append(row.get("confidence"))

    trends: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items()):
        confidence_scores = group["confidence_scores"]
        score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        trends.append(
            {
                "id": deterministic_uuid("equipment-trend", key),
                "brand": group["brand"],
                "equipment_category": group["equipment_category"],
                "weapon": group["weapon"],
                "event_tier": group["event_tier"],
                "evidence_count": len(group["evidence_ids"]),
                "result_count": len(group["result_ids"]),
                "win_count": group["win_count"],
                "podium_count": group["podium_count"],
                "top8_count": group["top8_count"],
                "confidence": strongest_confidence(group["confidences"]),
                "confidence_score": round(score, 3),
                "sources": sorted(group["sources"]),
                "metadata": {"aggregation": "brand_equipment_weapon_event_tier"},
                "updated_at": now,
            }
        )
    return trends


def fetch_all(client, table_name: str, select_candidates: tuple[str, ...], page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in select_candidates:
        rows: list[dict[str, Any]] = []
        offset = 0
        try:
            while True:
                page = (
                    client.table(table_name)
                    .select(columns)
                    .range(offset, offset + page_size - 1)
                    .execute()
                    .data
                    or []
                )
                rows.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
            return rows
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def fetch_optional_all(client, table_name: str, select_candidates: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table_name, select_candidates)
    except Exception as exc:
        print(f"  Optional table read failed for {table_name}: {exc}")
        return []


def fetch_fie_profile_text(session: requests.Session, fie_id: Any) -> str | None:
    fie_id_text = clean_text(fie_id)
    if not fie_id_text:
        return None
    if _fie_limiter:
        _fie_limiter.wait("fie.org")
    else:
        time.sleep(REQUEST_DELAY_SECONDS)
    url = f"{FIE_BASE_URL}/{fie_id_text}"
    try:
        response = session.get(url, headers=EQUIPMENT_HEADERS, timeout=20)
    except requests.RequestException as exc:
        print(f"  FIE profile fetch failed for {url}: {exc}")
        return None
    if response.status_code != 200:
        print(f"  FIE profile HTTP {response.status_code} for {url}")
        return None
    return response.text


def fetch_profile_equipment_rows(
    fencers: list[dict[str, Any]],
    *,
    brand_catalog: BrandCatalog,
    session: requests.Session | None = None,
    limit: int = MAX_PROFILE_FETCHES,
) -> list[dict[str, Any]]:
    session = session or requests.Session()
    profile_rows: list[dict[str, Any]] = []
    fetched = 0
    for fencer in fencers:
        if fetched >= limit:
            break
        fie_id = clean_text(fencer.get("fie_id"))
        fencer_name = clean_text(fencer.get("name"))
        if not fie_id or not fencer_name:
            continue
        source_url = f"{FIE_BASE_URL}/{fie_id}"
        text = fetch_fie_profile_text(session, fie_id)
        fetched += 1
        if not text:
            continue
        for mention in extract_profile_evidence(
            text,
            fencer_name=fencer_name,
            source="fie_profile",
            source_url=source_url,
            brand_catalog=brand_catalog,
        ):
            row = profile_evidence_to_source(fencer, mention)
            if row:
                profile_rows.append(row)
    return profile_rows


def upsert_rows(client, table_name: str, rows: list[dict[str, Any]], batch_size: int = UPSERT_BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table(table_name).upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {table_name} upsert batch {index // batch_size} failed: {exc}")
    return written, failed


EQUIPMENT_SELECTS = (
    "id,fencer_id,brand,equipment_type,sponsor_name,source,source_url,confidence,metadata",
    "id,fencer_id,brand,equipment_type,source,source_url,confidence,metadata",
)
PRODUCT_SELECTS = (
    "brand,category,product_name,url,source,metadata",
    "brand,category,product_name,url,source",
)
FENCER_SELECTS = (
    "id,name,fie_id,country,nationality,weapon,category,metadata",
    "id,name,fie_id,country,weapon,category,metadata",
    "id,name,fie_id,country,metadata",
)
RESULT_SELECTS = (
    "id,tournament_id,fencer_id,fie_fencer_id,rank,placement,medal,name,country,nationality,weapon,metadata,updated_at",
    "id,tournament_id,fencer_id,fie_fencer_id,rank,placement,medal,name,country,nationality,metadata",
    "tournament_id,fencer_id,fie_fencer_id,rank,placement,medal,name,country,nationality,metadata",
    "tournament_id,fencer_id,rank,placement,medal,name,nationality,metadata",
)
TOURNAMENT_SELECTS = (
    "id,name,weapon,gender,category,type,tier,competition_type,season,start_date,end_date,metadata",
    "id,name,weapon,gender,category,type,season,start_date,end_date,metadata",
    "id,name,weapon,category,type,metadata",
)


def run(
    client=None,
    *,
    log_run: bool = True,
    fetch_fie_profiles: bool = FETCH_FIE_PROFILES,
    session: requests.Session | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    now = updated_at or utc_now()

    try:
        previous_state = get_state(SOURCE, "last_run")
        equipment_rows = fetch_all(client, "fs_fencer_equipment", EQUIPMENT_SELECTS)
        product_rows = fetch_optional_all(client, "fs_equipment_reviews", PRODUCT_SELECTS)
        fencers = fetch_all(client, "fs_fencers", FENCER_SELECTS)
        results = fetch_all(client, "fs_results", RESULT_SELECTS)
        tournaments = fetch_all(client, "fs_tournaments", TOURNAMENT_SELECTS)

        brand_catalog = build_brand_catalog(product_rows)
        if fetch_fie_profiles:
            profile_rows = fetch_profile_equipment_rows(
                fencers,
                brand_catalog=brand_catalog,
                session=session,
            )
            equipment_rows.extend(profile_rows)

        evidence_rows, skipped = build_evidence_rows(
            equipment_rows,
            fencers,
            results,
            tournaments,
            brand_catalog=brand_catalog,
            updated_at=now,
        )
        trend_rows = aggregate_trend_rows(evidence_rows, updated_at=now)

        client.table("fs_equipment_trend_evidence")
        client.table("fs_equipment_trends")

        evidence_written = evidence_failed = trend_written = trend_failed = 0
        if evidence_rows:
            evidence_written, evidence_failed = upsert_rows(client, "fs_equipment_trend_evidence", evidence_rows)
        if trend_rows:
            trend_written, trend_failed = upsert_rows(client, "fs_equipment_trends", trend_rows)

        failed = evidence_failed + trend_failed
        written = evidence_written + trend_written
        summary = {
            "status": "ok" if evidence_rows else "no_public_data",
            "ran_at": now,
            "previous_run": previous_state,
            "equipment_rows_read": len(equipment_rows),
            "product_rows_read": len(product_rows),
            "fencers_read": len(fencers),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "evidence_rows_found": len(evidence_rows),
            "trend_rows_found": len(trend_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
        set_state(SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = run()
    print(
        "Equipment trends complete: status={status}, evidence={evidence_rows_found}, "
        "trends={trend_rows_found}, written={written}, failed={failed}, skipped={skipped}".format(**summary)
    )


if __name__ == "__main__":
    main()
