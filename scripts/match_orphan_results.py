from __future__ import annotations

import csv
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

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SOURCE = "match_orphan_results"
DEFAULT_LOG_PATH = Path(os.environ.get("UNMATCHED_ORPHANS_LOG", "unmatched_orphans.log"))

_supabase = None


@dataclass(frozen=True)
class FencerCandidate:
    id: str
    fie_id: str | None
    name: str | None
    country: str | None
    school: str | None
    olympedia_athlete_id: str | None


@dataclass(frozen=True)
class MatchResult:
    table_name: str
    row_id: str | None
    name: str | None
    country: str | None
    source: str
    matched: bool
    fencer_id: str | None = None
    tier: str | None = None
    reason: str | None = None
    score: float | None = None


def get_supabase():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def clean_text(value: Any) -> str | None:
    raw = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", raw.replace("\xa0", " ")).strip()
    return text or None


def normalized_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value) or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def fuzzy_key(value: Any) -> str:
    text = normalized_name(value)
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def metadata_text(row: dict[str, Any], key: str) -> str | None:
    value = metadata_dict(row).get(key)
    return clean_text(value)


def row_country(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("country") or row.get("nationality"))


def row_fie_id(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("fie_fencer_id") or row.get("fie_id"))


def row_source(row: dict[str, Any], table_name: str) -> str:
    if table_name == "fs_national_fed_rankings":
        return clean_text(row.get("source")) or table_name
    metadata = metadata_dict(row)
    if clean_text(metadata.get("source")):
        return clean_text(metadata.get("source")) or table_name
    if clean_text(metadata.get("school")):
        return "ncaa"
    if clean_text(metadata.get("olympedia_athlete_id")):
        return "olympedia"
    if clean_text(row.get("fie_fencer_id")):
        return "fie"
    return table_name


def school_from_fencer(row: dict[str, Any]) -> str | None:
    metadata = metadata_dict(row)
    return clean_text(metadata.get("school"))


def olympedia_id_from_fencer(row: dict[str, Any]) -> str | None:
    return clean_text(metadata_dict(row).get("olympedia_athlete_id"))


def _add(index: dict[Any, list[FencerCandidate]], key: Any, candidate: FencerCandidate) -> None:
    if key is not None:
        index.setdefault(key, []).append(candidate)


def build_fencer_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    index: dict[str, Any] = {
        "by_fie_id": {},
        "by_exact_name_country": {},
        "by_normalized_name_country": {},
        "by_normalized_name": {},
        "by_country": {},
        "by_school_name": {},
        "by_olympedia_id": {},
    }
    for row in rows:
        fencer_id = clean_text(row.get("id"))
        if not fencer_id:
            continue
        name = clean_text(row.get("name"))
        country = clean_text(row.get("country"))
        fie_id = clean_text(row.get("fie_id"))
        school = school_from_fencer(row)
        olympedia_athlete_id = olympedia_id_from_fencer(row)
        candidate = FencerCandidate(
            id=fencer_id,
            fie_id=fie_id,
            name=name,
            country=country,
            school=school,
            olympedia_athlete_id=olympedia_athlete_id,
        )
        if fie_id:
            _add(index["by_fie_id"], fie_id, candidate)
        if name:
            _add(index["by_normalized_name"], normalized_name(name), candidate)
        if name and country:
            _add(index["by_exact_name_country"], (name, country), candidate)
            _add(index["by_normalized_name_country"], (normalized_name(name), country), candidate)
            _add(index["by_country"], country, candidate)
        if name and school:
            _add(index["by_school_name"], (normalized_name(name), normalized_name(school)), candidate)
        if olympedia_athlete_id:
            _add(index["by_olympedia_id"], olympedia_athlete_id, candidate)
    return index


def _candidate_sort_key(candidate: FencerCandidate) -> tuple[str, str, str]:
    return (candidate.fie_id or "", candidate.country or "", candidate.id)


def resolve_candidate(candidates: list[FencerCandidate]) -> tuple[FencerCandidate | None, bool]:
    by_id = {candidate.id: candidate for candidate in candidates}
    unique = list(by_id.values())
    if not unique:
        return None, False
    if len(unique) == 1:
        return unique[0], False
    fie_ids = {candidate.fie_id for candidate in unique if candidate.fie_id}
    if len(fie_ids) == 1:
        return sorted(unique, key=_candidate_sort_key)[0], False
    return None, True


def levenshtein_ratio(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (left_char != right_char)
            current.append(min(insert, delete, replace))
        previous = current
    distance = previous[-1]
    return 1.0 - (distance / max(len(left), len(right)))


def _matched(row: dict[str, Any], table_name: str, candidate: FencerCandidate, tier: str, score: float | None = None) -> MatchResult:
    return MatchResult(
        table_name=table_name,
        row_id=clean_text(row.get("id")),
        name=clean_text(row.get("name")),
        country=row_country(row),
        source=row_source(row, table_name),
        matched=True,
        fencer_id=candidate.id,
        tier=tier,
        score=score,
    )


def _unmatched(row: dict[str, Any], table_name: str, reason: str) -> MatchResult:
    return MatchResult(
        table_name=table_name,
        row_id=clean_text(row.get("id")),
        name=clean_text(row.get("name")),
        country=row_country(row),
        source=row_source(row, table_name),
        matched=False,
        reason=reason,
    )


def match_orphan_row(row: dict[str, Any], index: dict[str, Any], table_name: str) -> MatchResult:
    name = clean_text(row.get("name"))
    country = row_country(row)
    ambiguous_reason: str | None = None

    fie_id = row_fie_id(row)
    if fie_id:
        candidate, ambiguous = resolve_candidate(index["by_fie_id"].get(fie_id, []))
        if candidate:
            return _matched(row, table_name, candidate, "tier_1_fie_id")
        if ambiguous:
            ambiguous_reason = "ambiguous_fie_id"

    if name and country:
        candidate, ambiguous = resolve_candidate(index["by_exact_name_country"].get((name, country), []))
        if candidate:
            return _matched(row, table_name, candidate, "tier_2_exact_name_country")
        if ambiguous:
            ambiguous_reason = "ambiguous_exact_name_country"

        candidate, ambiguous = resolve_candidate(index["by_normalized_name_country"].get((normalized_name(name), country), []))
        if candidate:
            return _matched(row, table_name, candidate, "tier_3_normalized_name_country")
        if ambiguous:
            ambiguous_reason = "ambiguous_normalized_name_country"

        row_fuzzy_key = fuzzy_key(name)
        scored: list[tuple[float, FencerCandidate]] = []
        for fc in index["by_country"].get(country, []):
            score = levenshtein_ratio(row_fuzzy_key, fuzzy_key(fc.name))
            if score >= 0.85:
                scored.append((score, fc))
        if scored:
            best_score = max(score for score, _candidate in scored)
            best_candidates: list[FencerCandidate] = [fc for score, fc in scored if score == best_score]
            candidate, ambiguous = resolve_candidate(best_candidates)
            if candidate:
                return _matched(row, table_name, candidate, "tier_4_fuzzy_name_country", score=best_score)
            if ambiguous:
                ambiguous_reason = "ambiguous_fuzzy_name_country"
    elif name:
        name_matches = index["by_normalized_name"].get(normalized_name(name), [])
        countries = {candidate.country for candidate in name_matches if candidate.country}
        if len(countries) > 1:
            ambiguous_reason = "ambiguous_name_without_country"

    school = metadata_text(row, "school")
    if name and school:
        candidate, ambiguous = resolve_candidate(index["by_school_name"].get((normalized_name(name), normalized_name(school)), []))
        if candidate:
            return _matched(row, table_name, candidate, "tier_5_ncaa_school")
        if ambiguous:
            ambiguous_reason = "ambiguous_ncaa_school"

    olympedia_athlete_id = metadata_text(row, "olympedia_athlete_id")
    if olympedia_athlete_id:
        candidate, ambiguous = resolve_candidate(index["by_olympedia_id"].get(olympedia_athlete_id, []))
        if candidate:
            return _matched(row, table_name, candidate, "tier_6_olympedia_athlete_id")
        if ambiguous:
            ambiguous_reason = "ambiguous_olympedia_athlete_id"

    return _unmatched(row, table_name, ambiguous_reason or "no_match")


def match_orphan_rows(rows: list[dict[str, Any]], index: dict[str, Any], table_name: str) -> tuple[list[MatchResult], list[MatchResult]]:
    matches: list[MatchResult] = []
    unmatched: list[MatchResult] = []
    for row in rows:
        result = match_orphan_row(row, index, table_name)
        if result.matched:
            matches.append(result)
        else:
            unmatched.append(result)
    return matches, unmatched


def fetch_paginated(client, table_name: str, select_columns: str, *, orphans_only: bool = False, named_only: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        query = client.table(table_name).select(select_columns).range(start, start + page_size - 1)
        if orphans_only:
            query = query.is_("fencer_id", "null")
        if named_only:
            query = query.not_.is_("name", "null")
        page = query.execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def fetch_all_fencers(client) -> list[dict[str, Any]]:
    return fetch_paginated(client, "fs_fencers", "id,fie_id,name,country,club,metadata")


def fetch_result_orphans(client) -> list[dict[str, Any]]:
    try:
        return fetch_paginated(
            client,
            "fs_results",
            "id,fie_fencer_id,name,nationality,country,metadata",
            orphans_only=True,
            named_only=True,
        )
    except Exception as exc:
        if "country" not in str(exc).lower():
            raise
        return fetch_paginated(
            client,
            "fs_results",
            "id,fie_fencer_id,name,nationality,metadata",
            orphans_only=True,
            named_only=True,
        )


def fetch_national_ranking_orphans(client) -> list[dict[str, Any]]:
    return fetch_paginated(
        client,
        "fs_national_fed_rankings",
        "id,fie_id,name,country,source,metadata",
        orphans_only=True,
        named_only=True,
    )


def apply_updates(client, table_name: str, matches: list[MatchResult], batch_size: int = 100) -> int:
    written = 0
    for i in range(0, len(matches), batch_size):
        payload = [
            {"id": match.row_id, "fencer_id": match.fencer_id}
            for match in matches[i:i + batch_size]
            if match.row_id and match.fencer_id
        ]
        if not payload:
            continue
        client.rpc(
            "fs_bulk_update_fencer_matches",
            {"p_table_name": table_name, "p_updates": payload},
        ).execute()
        written += len(payload)
    return written


def write_unmatched_log(path: Path, unmatched: list[MatchResult]) -> None:
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["table", "row_id", "name", "country", "source", "reason"])
        for row in unmatched:
            writer.writerow([
                row.table_name,
                row.row_id or "",
                row.name or "",
                row.country or "",
                row.source,
                row.reason or "no_match",
            ])


def run(client=None, log_path: Path = DEFAULT_LOG_PATH) -> dict[str, Any]:
    client = client or get_supabase()
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        fencer_rows = fetch_all_fencers(client)
        index = build_fencer_index(fencer_rows)

        result_rows = fetch_result_orphans(client)
        ranking_rows = fetch_national_ranking_orphans(client)
        result_matches, result_unmatched = match_orphan_rows(result_rows, index, table_name="fs_results")
        ranking_matches, ranking_unmatched = match_orphan_rows(
            ranking_rows,
            index,
            table_name="fs_national_fed_rankings",
        )

        result_written = apply_updates(client, "fs_results", result_matches)
        ranking_written = apply_updates(client, "fs_national_fed_rankings", ranking_matches)
        unmatched = result_unmatched + ranking_unmatched
        write_unmatched_log(log_path, unmatched)

        total_orphans = len(result_rows) + len(ranking_rows)
        total_written = result_written + ranking_written
        summary = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "previous_run": previous_state,
            "fencers_indexed": len(fencer_rows),
            "result_orphans": len(result_rows),
            "ranking_orphans": len(ranking_rows),
            "matched": total_written,
            "unmatched": len(unmatched),
            "match_rate": (total_written / total_orphans) if total_orphans else 0.0,
            "unmatched_log": str(log_path),
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(written=total_written, failed=0, skipped=len(unmatched), metadata=summary)
        return summary
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main() -> None:
    summary = run()
    print(
        "Matched {matched}/{total} orphans ({rate:.1%}); unmatched log: {log}".format(
            matched=summary["matched"],
            total=summary["result_orphans"] + summary["ranking_orphans"],
            rate=summary["match_rate"],
            log=summary["unmatched_log"],
        )
    )


if __name__ == "__main__":
    main()
