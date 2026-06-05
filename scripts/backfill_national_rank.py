from __future__ import annotations

import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_utils import normalize_season, season_from_string

SOURCE = "backfill_national_rank"
RANKING_TABLE = "fs_national_fed_rankings"
FENCER_TABLE = "fs_fencers"
IDENTITY_TABLE = "fs_fencer_identities"
PAGE_SIZE = 1000
BATCH_SIZE = 100

RANKING_COLUMNS = (
    "id,fencer_id,fie_id,name,country,weapon,gender,category,rank,points,source,season,metadata,scraped_at"
)
FENCER_COLUMNS = (
    "id,fie_id,name,country,weapon,category,national_rank,national_rank_points,"
    "national_rank_source,national_rank_season"
)
IDENTITY_COLUMNS = "id,canonical_name,country,fie_ids,fs_fencer_row_ids,metadata"


STATS_KEYS = (
    "ranking_rows_read",
    "selected_rankings",
    "matched_rankings",
    "unmatched_rankings",
    "skipped_invalid_season",
    "skipped_ambiguous",
    "skipped_incompatible",
    "skipped_stale",
    "skipped_current_conflict",
    "skipped_lower_confidence",
)


@dataclass(frozen=True)
class CandidateUpdate:
    fencer_id: str
    rank: int
    points: float | None
    source: str
    season: str
    season_end: int
    confidence: int

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.fencer_id,
            "national_rank": self.rank,
            "national_rank_points": self.points,
            "national_rank_source": self.source,
            "national_rank_season": self.season,
        }


@dataclass(frozen=True)
class MatchDecision:
    rows: list[dict[str, Any]]
    confidence: int
    reason: str


@dataclass(frozen=True)
class BackfillSummary:
    ranking_rows_read: int = 0
    selected_rankings: int = 0
    matched_rankings: int = 0
    unmatched_rankings: int = 0
    skipped_invalid_season: int = 0
    skipped_ambiguous: int = 0
    skipped_incompatible: int = 0
    skipped_stale: int = 0
    skipped_current_conflict: int = 0
    skipped_lower_confidence: int = 0
    written: int = 0
    failed: int = 0

    @property
    def skipped(self) -> int:
        return self.unmatched_rankings + self.skipped_invalid_season + self.skipped_lower_confidence

    def as_dict(self) -> dict[str, int]:
        return {
            "ranking_rows_read": self.ranking_rows_read,
            "selected_rankings": self.selected_rankings,
            "matched_rankings": self.matched_rankings,
            "unmatched_rankings": self.unmatched_rankings,
            "skipped_invalid_season": self.skipped_invalid_season,
            "skipped_ambiguous": self.skipped_ambiguous,
            "skipped_incompatible": self.skipped_incompatible,
            "skipped_stale": self.skipped_stale,
            "skipped_current_conflict": self.skipped_current_conflict,
            "skipped_lower_confidence": self.skipped_lower_confidence,
            "written": self.written,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def _empty_stats() -> dict[str, int]:
    return {key: 0 for key in STATS_KEYS}


def clean_text(value: Any) -> str | None:
    raw = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", raw.replace("\xa0", " ")).strip()
    return text or None


def normalized_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value) or "").casefold()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value) or "").casefold()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", text)


_COUNTRY_ALIASES: dict[str, str] = {
    "AIN": "Russia", "_AIN": "Russia", "AIN_": "Russia",
    "US": "United States", "USA": "United States",
    "UNITED STATES": "United States", "UNITED STATES OF AMERICA": "United States",
    "GB": "Great Britain", "GBR": "Great Britain", "UK": "Great Britain",
    "CAN": "Canada", "CANADA": "Canada",
    "CHN": "China", "CHINA": "China",
    "FRA": "France", "FRANCE": "France",
    "GER": "Germany", "DEU": "Germany", "GERMANY": "Germany",
    "ITA": "Italy", "ITALIA": "Italy",
    "JPN": "Japan", "JAPAN": "Japan",
    "KOR": "South Korea", "KOREA": "South Korea", "SOUTH KOREA": "South Korea",
    "HKG": "Hong Kong", "HONG KONG, CHINA": "Hong Kong", "HONG KONG CHINA": "Hong Kong",
    "AUS": "Australia", "AUSTRALIA": "Australia",
    "BRA": "Brazil", "BRAZIL": "Brazil",
    "ARG": "Argentina", "ARGENTINA": "Argentina",
    "ESP": "Spain", "SPAIN": "Spain",
    "HUN": "Hungary", "HUNGARY": "Hungary",
    "RUS": "Russia", "RUSSIA": "Russia",
    "POL": "Poland", "POLAND": "Poland",
    "UKR": "Ukraine", "UKRAINE": "Ukraine",
    "EGY": "Egypt", "EGYPT": "Egypt",
    "VEN": "Venezuela", "VENEZUELA": "Venezuela",
    "COL": "Colombia", "COLOMBIA": "Colombia",
    "MEX": "Mexico", "MEXICO": "Mexico",
    "AUT": "Austria", "AUSTRIA": "Austria",
    "BEL": "Belgium", "BELGIUM": "Belgium",
    "SUI": "Switzerland", "SWITZERLAND": "Switzerland",
    "POR": "Portugal", "PORTUGAL": "Portugal",
    "ROU": "Romania", "ROMANIA": "Romania",
    "TUR": "Turkey", "TURKEY": "Turkey", "TURKIYE": "Turkey",
}


def _country_key(value: Any) -> str:
    raw = (clean_text(value) or "").upper().strip()
    canonical = _COUNTRY_ALIASES.get(raw)
    if canonical:
        return normalized_name(canonical)
    return normalized_name(value)


def _season_info(value: Any) -> tuple[str, int] | None:
    try:
        season = normalize_season(value)
        return season, season_from_string(season)
    except (TypeError, ValueError):
        return None


def _ranking_group_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        normalized_name(row.get("source")),
        _country_key(row.get("country")),
        normalized_key(row.get("weapon")),
        normalized_key(row.get("gender")),
        normalized_key(row.get("category")),
    )


def select_latest_rankings(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = _empty_stats()
    stats["ranking_rows_read"] = len(rows)
    grouped_end_years: dict[tuple[str, str, str, str, str], int] = {}
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        season_info = _season_info(row.get("season"))
        if season_info is None:
            stats["skipped_invalid_season"] += 1
            continue
        season, season_end = season_info
        normalized = dict(row)
        normalized["season"] = season
        normalized["_season_end"] = season_end
        key = _ranking_group_key(normalized)
        grouped_end_years[key] = max(grouped_end_years.get(key, season_end), season_end)
        normalized_rows.append(normalized)

    selected = [
        {key: value for key, value in row.items() if key != "_season_end"}
        for row in normalized_rows
        if row["_season_end"] == grouped_end_years[_ranking_group_key(row)]
    ]
    stats["selected_rankings"] = len(selected)
    return selected, stats


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _add(index: dict[Any, list[dict[str, Any]]], key: Any, row: dict[str, Any]) -> None:
    if key in (None, "", (None, None), ("", "")):
        return
    index.setdefault(key, []).append(row)


def _build_match_index(
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
) -> dict[str, Any]:
    fencers_by_id: dict[str, dict[str, Any]] = {}
    fencers_by_fie_id: dict[str, list[dict[str, Any]]] = {}
    fencers_by_name_country: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in fencers:
        row_id = clean_text(row.get("id"))
        if not row_id:
            continue
        fencers_by_id[row_id] = row
        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            _add(fencers_by_fie_id, fie_id, row)
        name = normalized_name(row.get("name"))
        country = _country_key(row.get("country"))
        if name and country:
            _add(fencers_by_name_country, (name, country), row)

    identities_by_row_id: dict[str, dict[str, Any]] = {}
    identities_by_fie_id: dict[str, list[dict[str, Any]]] = {}
    identities_by_name_country: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for identity in identities:
        _raw_row_ids = [clean_text(row_id) for row_id in _as_list(identity.get("fs_fencer_row_ids"))]
        row_ids: list[str] = [row_id for row_id in _raw_row_ids if row_id and row_id in fencers_by_id]
        if not row_ids:
            continue
        normalized_identity = dict(identity)
        normalized_identity["_row_ids"] = row_ids
        for row_id in row_ids:
            identities_by_row_id[row_id] = normalized_identity
        for fie_id in _as_list(identity.get("fie_ids")):
            cleaned = clean_text(fie_id)
            if cleaned:
                _add(identities_by_fie_id, cleaned, normalized_identity)
        name = normalized_name(identity.get("canonical_name"))
        country = _country_key(identity.get("country"))
        if name and country:
            _add(identities_by_name_country, (name, country), normalized_identity)

    return {
        "fencers_by_id": fencers_by_id,
        "fencer_order": {clean_text(row.get("id")): index for index, row in enumerate(fencers)},
        "fencers_by_fie_id": fencers_by_fie_id,
        "fencers_by_name_country": fencers_by_name_country,
        "identities_by_row_id": identities_by_row_id,
        "identities_by_fie_id": identities_by_fie_id,
        "identities_by_name_country": identities_by_name_country,
    }


def _identity_rows(identity: dict[str, Any], index: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        index["fencers_by_id"][row_id]
        for row_id in identity.get("_row_ids", [])
        if row_id in index["fencers_by_id"]
    ]


def _unique_identity(identities: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique = {clean_text(identity.get("id")): identity for identity in identities if clean_text(identity.get("id"))}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        row_id = clean_text(row.get("id"))
        if not row_id or row_id in seen:
            continue
        seen.add(row_id)
        deduped.append(row)
    return deduped


def _weapon_key(value: Any) -> str:
    key = normalized_key(value)
    aliases = {"saber": "sabre"}
    return aliases.get(key, key)


def _gender_key(value: Any) -> str:
    key = normalized_key(value)
    aliases = {"m": "men", "male": "men", "w": "women", "f": "women", "female": "women"}
    return aliases.get(key, key)


def _category_key(value: Any) -> str:
    key = normalized_key(value)
    if key in {"s", "senior", "seniors"}:
        return "senior"
    if key in {"j", "junior", "juniors", "u20", "u21"}:
        return "junior"
    if key in {"c", "cadet", "cadets", "u17", "u18"}:
        return "cadet"
    if key in {"v", "veteran", "veterans", "masters"}:
        return "veteran"
    return key


def _fencer_gender(row: dict[str, Any]) -> str:
    text = normalized_name(f"{clean_text(row.get('gender')) or ''} {clean_text(row.get('category')) or ''}")
    if "women" in text or "female" in text:
        return "women"
    if re.search(r"\bmen\b", text) or "male" in text:
        return "men"
    return ""


def _fencer_category(row: dict[str, Any]) -> str:
    text = normalized_name(row.get("category"))
    for category in ("senior", "junior", "cadet", "veteran"):
        if category in text:
            return category
    return _category_key(text)


def _compatible_with_ranking(fencer: dict[str, Any], ranking: dict[str, Any]) -> bool:
    fencer_weapon = _weapon_key(fencer.get("weapon"))
    ranking_weapon = _weapon_key(ranking.get("weapon"))
    if fencer_weapon and ranking_weapon and fencer_weapon != ranking_weapon:
        return False

    fencer_category = _fencer_category(fencer)
    ranking_category = _category_key(ranking.get("category"))
    if fencer_category and ranking_category and fencer_category != ranking_category:
        return False

    fencer_gender = _fencer_gender(fencer)
    ranking_gender = _gender_key(ranking.get("gender"))
    if fencer_gender and ranking_gender and fencer_gender != ranking_gender:
        return False

    return True


def _resolve_rows(rows: list[dict[str, Any]], *, allow_multiple: bool) -> tuple[list[dict[str, Any]], bool]:
    deduped = _dedupe_rows(rows)
    if len(deduped) <= 1 or allow_multiple:
        return deduped, False
    return [], True


def match_ranking_to_fencers(
    ranking: dict[str, Any],
    index: dict[str, Any],
) -> tuple[MatchDecision | None, str | None]:
    fencer_id = clean_text(ranking.get("fencer_id"))
    if fencer_id and fencer_id in index["fencers_by_id"]:
        identity = index["identities_by_row_id"].get(fencer_id)
        rows = _identity_rows(identity, index) if identity else [index["fencers_by_id"][fencer_id]]
        compatible = [row for row in rows if _compatible_with_ranking(row, ranking)]
        if not compatible:
            return None, "incompatible"
        resolved, ambiguous = _resolve_rows(compatible, allow_multiple=True)
        return MatchDecision(resolved, 4, "fencer_id_identity" if identity else "fencer_id"), None

    fie_id = clean_text(ranking.get("fie_id"))
    if fie_id:
        identity = _unique_identity(index["identities_by_fie_id"].get(fie_id, []))
        if identity:
            compatible = [row for row in _identity_rows(identity, index) if _compatible_with_ranking(row, ranking)]
            if not compatible:
                return None, "incompatible"
            resolved, _ = _resolve_rows(compatible, allow_multiple=True)
            return MatchDecision(resolved, 3, "identity_fie_id"), None

        rows = index["fencers_by_fie_id"].get(fie_id, [])
        if rows:
            compatible = [row for row in rows if _compatible_with_ranking(row, ranking)]
            if not compatible:
                return None, "incompatible"
            resolved, _ = _resolve_rows(compatible, allow_multiple=True)
            return MatchDecision(resolved, 3, "fie_id"), None

    name = normalized_name(ranking.get("name"))
    country = _country_key(ranking.get("country"))
    if name and country:
        identity = _unique_identity(index["identities_by_name_country"].get((name, country), []))
        if identity:
            compatible = [row for row in _identity_rows(identity, index) if _compatible_with_ranking(row, ranking)]
            if not compatible:
                return None, "incompatible"
            resolved, _ = _resolve_rows(compatible, allow_multiple=True)
            return MatchDecision(resolved, 2, "identity_name_country"), None

        rows = index["fencers_by_name_country"].get((name, country), [])
        if rows:
            compatible = [row for row in rows if _compatible_with_ranking(row, ranking)]
            if not compatible:
                return None, "incompatible"
            resolved, ambiguous = _resolve_rows(compatible, allow_multiple=False)
            if ambiguous:
                return None, "ambiguous"
            return MatchDecision(resolved, 1, "name_country"), None

    return None, None


def _to_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _should_update_fencer(fencer: dict[str, Any], candidate: CandidateUpdate) -> tuple[bool, str | None]:
    existing_info = _season_info(fencer.get("national_rank_season"))
    if existing_info is None:
        return True, None

    _existing_season, existing_end = existing_info
    if existing_end > candidate.season_end:
        return False, "stale"
    if existing_end == candidate.season_end:
        existing_source = clean_text(fencer.get("national_rank_source"))
        if existing_source and existing_source != candidate.source:
            return False, "current_conflict"
    return True, None


def _candidate_is_better(incoming: CandidateUpdate, existing: CandidateUpdate) -> bool:
    if incoming.season_end != existing.season_end:
        return incoming.season_end > existing.season_end
    if incoming.confidence != existing.confidence:
        return incoming.confidence > existing.confidence
    if incoming.source != existing.source:
        return incoming.source < existing.source
    return incoming.rank < existing.rank


def build_update_payloads(
    rankings: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = _empty_stats()
    stats["selected_rankings"] = len(rankings)
    index = _build_match_index(fencers, identities)
    best_by_fencer: dict[str, CandidateUpdate] = {}

    for ranking in rankings:
        season_info = _season_info(ranking.get("season"))
        if season_info is None:
            stats["skipped_invalid_season"] += 1
            stats["unmatched_rankings"] += 1
            continue
        season, season_end = season_info
        rank = _to_int(ranking.get("rank"))
        source = clean_text(ranking.get("source"))
        if rank is None or not source:
            stats["unmatched_rankings"] += 1
            continue

        decision, failure_reason = match_ranking_to_fencers(ranking, index)
        if decision is None:
            if failure_reason == "ambiguous":
                stats["skipped_ambiguous"] += 1
            elif failure_reason == "incompatible":
                stats["skipped_incompatible"] += 1
            stats["unmatched_rankings"] += 1
            continue

        accepted = 0
        for fencer in decision.rows:
            fencer_id = clean_text(fencer.get("id"))
            if not fencer_id:
                continue
            candidate = CandidateUpdate(
                fencer_id=fencer_id,
                rank=rank,
                points=_to_float(ranking.get("points")),
                source=source,
                season=season,
                season_end=season_end,
                confidence=decision.confidence,
            )
            should_update, skip_reason = _should_update_fencer(fencer, candidate)
            if not should_update:
                if skip_reason == "stale":
                    stats["skipped_stale"] += 1
                elif skip_reason == "current_conflict":
                    stats["skipped_current_conflict"] += 1
                continue

            existing = best_by_fencer.get(fencer_id)
            if existing is None:
                best_by_fencer[fencer_id] = candidate
                accepted += 1
            elif _candidate_is_better(candidate, existing):
                best_by_fencer[fencer_id] = candidate
                stats["skipped_lower_confidence"] += 1
                accepted += 1
            else:
                stats["skipped_lower_confidence"] += 1

        if accepted:
            stats["matched_rankings"] += 1
        else:
            stats["unmatched_rankings"] += 1

    fencer_order = index["fencer_order"]
    payloads = [
        candidate.payload()
        for candidate in sorted(
            best_by_fencer.values(),
            key=lambda candidate: fencer_order.get(candidate.fencer_id, len(fencer_order)),
        )
    ]
    return payloads, stats


def _fetch_paginated(client: Any, table_name: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        result = client.table(table_name).select(columns).range(start, start + page_size - 1).execute()
        page = result.data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _upsert_batches(client: Any, table_name: str, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        try:
            client.table(table_name).upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"[{SOURCE}] upsert failed for batch starting {start}: {exc}")
    return written, failed


def _summary_from_stats(stats: dict[str, int], *, written: int = 0, failed: int = 0) -> BackfillSummary:
    values = {key: stats.get(key, 0) for key in STATS_KEYS}
    return BackfillSummary(**values, written=written, failed=failed)


def backfill_national_rank(
    client: Any,
    *,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
) -> BackfillSummary:
    rankings = _fetch_paginated(client, RANKING_TABLE, RANKING_COLUMNS, page_size=page_size)
    selected_rankings, stats = select_latest_rankings(rankings)
    if not selected_rankings:
        return _summary_from_stats(stats)

    fencers = _fetch_paginated(client, FENCER_TABLE, FENCER_COLUMNS, page_size=page_size)
    identities = _fetch_paginated(client, IDENTITY_TABLE, IDENTITY_COLUMNS, page_size=page_size)
    payloads, match_stats = build_update_payloads(selected_rankings, fencers, identities)
    stats.update({key: stats.get(key, 0) + match_stats.get(key, 0) for key in STATS_KEYS})
    stats["ranking_rows_read"] = len(rankings)
    stats["selected_rankings"] = len(selected_rankings)

    written, failed = _upsert_batches(client, FENCER_TABLE, payloads, batch_size=batch_size) if payloads else (0, 0)
    return _summary_from_stats(stats, written=written, failed=failed)


def get_supabase():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(supabase_url, supabase_key)


def main() -> BackfillSummary:
    from run_logger import ScraperRunLogger
    from scraper_state import set_state

    logger = ScraperRunLogger(SOURCE).start()
    try:
        summary = backfill_national_rank(get_supabase())
        metadata: dict[str, Any] = dict(summary.as_dict())
        metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
        set_state(SOURCE, "last_run", metadata)
        logger.complete(written=summary.written, failed=summary.failed, skipped=summary.skipped, metadata=metadata)
        print(metadata)
        return summary
    except Exception as exc:
        logger.error(str(exc))
        raise


if __name__ == "__main__":
    main()
