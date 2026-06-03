import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
DEFAULT_MAX_NODES = 5000
DEFAULT_MAX_OPPONENTS = 50
SOURCE = "compute_h2h_graph"

BOUT_SELECTS = (
    "id,source_key,tournament_id,weapon,fencer_a,fencer_b,winner_id,score_a,score_b,bout_date,meeting_date,date,played_at",
    "id,tournament_id,weapon,fencer_a,fencer_b,winner_id,score_a,score_b,bout_date,meeting_date,date,played_at",
    "id,tournament_id,fencer_a,fencer_b,winner_id,score_a,score_b",
)
TOURNAMENT_SELECTS = (
    "id,weapon,end_date,date,start_date",
    "id,weapon,end_date",
    "id,weapon",
)
IDENTITY_SELECTS = (
    "id,canonical_name,country,fs_fencer_row_ids",
    "id,canonical_id,canonical_name,country,fs_fencer_row_ids",
    "id,canonical_name,country,fencer_ids",
)
FENCER_SELECTS = (
    "id,name,country",
    "id,name,nationality",
    "id",
)

WEAPON_MAP = {
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
    "s": "Sabre",
    "saber": "Sabre",
    "sabre": "Sabre",
}

SKIP_KEYS = (
    "duplicate_bouts",
    "incomplete_bouts",
    "missing_fencers",
    "missing_weapon",
    "self_bouts",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_uuid(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError):
        return None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(text.casefold(), text.title())


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def round_metric(value: float) -> float:
    return round(value, 4)


def parse_identity_members(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_tournament_lookup(
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): row for key, row in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def build_fencer_lookup(fencers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in fencers
        if row.get("id") is not None
    }


def build_identity_lookup(
    identity_rows: list[dict[str, Any]],
    fencers: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    fencer_lookup = build_fencer_lookup(fencers or [])
    row_to_key: dict[str, str] = {}
    node_info: dict[str, dict[str, Any]] = {}

    for row in identity_rows:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        canonical_member = clean_text(row.get("canonical_id")) or (members[0] if members else None)
        row_id = clean_text(row.get("id"))
        fencer_row = fencer_lookup.get(canonical_member or "") or {}
        fencer_key = row_id or canonical_member
        if not fencer_key:
            continue

        node_info[fencer_key] = {
            "fencer_key": fencer_key,
            "identity_id": normalize_uuid(row_id),
            "fencer_id": normalize_uuid(canonical_member),
            "canonical_name": clean_text(row.get("canonical_name"))
            or clean_text(fencer_row.get("name")),
            "country": clean_text(row.get("country"))
            or clean_text(fencer_row.get("country"))
            or clean_text(fencer_row.get("nationality")),
        }
        row_to_key[fencer_key] = fencer_key
        if canonical_member:
            row_to_key[canonical_member] = fencer_key
        for member in members:
            row_to_key[member] = fencer_key

    for row_id, row in fencer_lookup.items():
        key = row_to_key.get(row_id, row_id)
        existing = node_info.setdefault(
            key,
            {
                "fencer_key": key,
                "identity_id": None,
                "fencer_id": normalize_uuid(row_id),
                "canonical_name": clean_text(row.get("name")),
                "country": clean_text(row.get("country"))
                or clean_text(row.get("nationality")),
            },
        )
        if not existing.get("canonical_name"):
            existing["canonical_name"] = clean_text(row.get("name"))
        if not existing.get("country"):
            existing["country"] = clean_text(row.get("country")) or clean_text(
                row.get("nationality")
            )

    return row_to_key, node_info


def ensure_node_info(
    fencer_id: Any,
    row_to_key: dict[str, str],
    node_info: dict[str, dict[str, Any]],
    fencer_lookup: dict[str, dict[str, Any]],
) -> str | None:
    raw_id = clean_text(fencer_id)
    if not raw_id:
        return None

    key = row_to_key.get(raw_id, raw_id)
    if key not in node_info:
        row = fencer_lookup.get(raw_id, {})
        node_info[key] = {
            "fencer_key": key,
            "identity_id": None,
            "fencer_id": normalize_uuid(raw_id),
            "canonical_name": clean_text(row.get("name")),
            "country": clean_text(row.get("country")) or clean_text(row.get("nationality")),
        }
    return key


def bout_weapon(
    bout: dict[str, Any],
    tournaments_by_id: dict[str, dict[str, Any]],
) -> str | None:
    weapon = normalize_weapon(bout.get("weapon"))
    if weapon:
        return weapon
    tournament_id = bout.get("tournament_id")
    tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id is not None else None
    return normalize_weapon(tournament.get("weapon")) if tournament else None


def bout_dedupe_key(bout: dict[str, Any]) -> tuple[str, str] | None:
    bout_id = clean_text(bout.get("id"))
    if bout_id:
        return ("id", bout_id)
    source_key = clean_text(bout.get("source_key"))
    if source_key:
        tournament_id = clean_text(bout.get("tournament_id")) or ""
        return ("source", f"{tournament_id}:{source_key}")
    return None


def empty_skip_counts() -> dict[str, int]:
    return {key: 0 for key in SKIP_KEYS}


def build_h2h_graph_rows(
    bouts: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    updated_at: str | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_opponents: int = DEFAULT_MAX_OPPONENTS,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = build_tournament_lookup(tournaments)
    fencer_lookup = build_fencer_lookup(fencers)
    row_to_key, node_info = build_identity_lookup(identity_rows, fencers)
    skipped = empty_skip_counts()
    seen_bouts: set[tuple[str, str]] = set()
    adjacency: dict[tuple[str, str], dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"bouts": 0, "wins": 0, "losses": 0})
    )
    nodes_by_weapon: dict[str, set[str]] = defaultdict(set)

    for bout in bouts:
        dedupe_key = bout_dedupe_key(bout)
        if dedupe_key:
            if dedupe_key in seen_bouts:
                skipped["duplicate_bouts"] += 1
                continue
            seen_bouts.add(dedupe_key)

        weapon = bout_weapon(bout, tournaments_by_id)
        if not weapon:
            skipped["missing_weapon"] += 1
            continue

        fencer_a = ensure_node_info(
            bout.get("fencer_a"), row_to_key, node_info, fencer_lookup
        )
        fencer_b = ensure_node_info(
            bout.get("fencer_b"), row_to_key, node_info, fencer_lookup
        )
        if not fencer_a or not fencer_b:
            skipped["missing_fencers"] += 1
            continue
        if fencer_a == fencer_b:
            skipped["self_bouts"] += 1
            continue

        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if score_a is None or score_b is None or score_a == score_b:
            skipped["incomplete_bouts"] += 1
            continue

        a_won = score_a > score_b
        a_stats = adjacency[(weapon, fencer_a)][fencer_b]
        b_stats = adjacency[(weapon, fencer_b)][fencer_a]
        a_stats["bouts"] += 1
        b_stats["bouts"] += 1
        if a_won:
            a_stats["wins"] += 1
            b_stats["losses"] += 1
        else:
            a_stats["losses"] += 1
            b_stats["wins"] += 1
        nodes_by_weapon[weapon].update((fencer_a, fencer_b))

    weighted_by_node = {
        key: sum(edge["bouts"] for edge in opponents.values())
        for key, opponents in adjacency.items()
    }
    max_weight_by_weapon = {
        weapon: max(
            (weighted_by_node.get((weapon, node_key), 0) for node_key in node_keys),
            default=0,
        )
        for weapon, node_keys in nodes_by_weapon.items()
    }

    rows: list[dict[str, Any]] = []
    for (weapon, fencer_key), opponents in adjacency.items():
        graph_size = len(nodes_by_weapon[weapon])
        degree = len(opponents)
        weighted_degree = weighted_by_node[(weapon, fencer_key)]
        wins = sum(edge["wins"] for edge in opponents.values())
        losses = sum(edge["losses"] for edge in opponents.values())
        info = node_info[fencer_key]
        opponent_rows = []
        for opponent_key, edge in sorted(
            opponents.items(),
            key=lambda item: (-item[1]["bouts"], -item[1]["wins"], item[0]),
        )[: max(0, max_opponents)]:
            opponent_info = node_info[opponent_key]
            bouts_total = edge["bouts"]
            opponent_rows.append(
                {
                    "opponent_key": opponent_key,
                    "opponent_identity_id": opponent_info.get("identity_id"),
                    "opponent_fencer_id": opponent_info.get("fencer_id"),
                    "opponent_name": opponent_info.get("canonical_name"),
                    "opponent_country": opponent_info.get("country"),
                    "weapon": weapon,
                    "bouts": bouts_total,
                    "wins": edge["wins"],
                    "losses": edge["losses"],
                    "strength": bouts_total,
                    "win_rate": round_metric(edge["wins"] / bouts_total),
                }
            )

        rows.append(
            {
                "fencer_key": fencer_key,
                "identity_id": info.get("identity_id"),
                "fencer_id": info.get("fencer_id"),
                "canonical_name": info.get("canonical_name"),
                "country": info.get("country"),
                "weapon": weapon,
                "degree": degree,
                "weighted_degree": weighted_degree,
                "total_bouts": weighted_degree,
                "wins": wins,
                "losses": losses,
                "strength": weighted_degree,
                "degree_centrality": round_metric(degree / (graph_size - 1))
                if graph_size > 1
                else 0.0,
                "weighted_degree_centrality": round_metric(
                    weighted_degree / max_weight_by_weapon[weapon]
                )
                if max_weight_by_weapon[weapon]
                else 0.0,
                "opponents": opponent_rows,
                "updated_at": now,
            }
        )

    rows.sort(
        key=lambda row: (
            row["weapon"],
            -row["weighted_degree"],
            -row["degree"],
            row["fencer_key"],
        )
    )
    return rows[: max(0, max_nodes)], skipped


def fetch_all(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
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


def fetch_with_fallbacks(
    client,
    table: str,
    column_options: tuple[str, ...],
    page_size: int = PAGE_SIZE,
    required: bool = True,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if required and last_error:
        raise last_error
    return []


def batch_upsert_graph(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_h2h_graph").upsert(
            batch, on_conflict="fencer_key,weapon"
        ).execute()
        written += len(batch)
    return written


def compute_h2h_graph(
    client=None,
    page_size: int = PAGE_SIZE,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_opponents: int = DEFAULT_MAX_OPPONENTS,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        bouts = fetch_with_fallbacks(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(
            client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size
        )
        identity_rows = fetch_with_fallbacks(
            client,
            "fs_fencer_identities",
            IDENTITY_SELECTS,
            page_size=page_size,
            required=False,
        )
        fencers = fetch_with_fallbacks(
            client, "fs_fencers", FENCER_SELECTS, page_size=page_size, required=False
        )
        graph_rows, skipped = build_h2h_graph_rows(
            bouts,
            tournaments,
            identity_rows,
            fencers,
            updated_at=updated_at,
            max_nodes=max_nodes,
            max_opponents=max_opponents,
        )
        written = batch_upsert_graph(client, graph_rows) if graph_rows else 0
        summary = {
            "bouts_read": len(bouts),
            "tournaments_read": len(tournaments),
            "identity_rows": len(identity_rows),
            "fencers_read": len(fencers),
            "graph_rows": len(graph_rows),
            "written": written,
            "skipped": sum(skipped.values()),
            **skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=summary["skipped"], metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous H2H graph state: {previous_state}")
        client = get_supabase_client()
        summary = compute_h2h_graph(client=client, log_run=False, update_state=False)
        set_state(
            SOURCE,
            "last_run",
            {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
        )
        run_log.complete(
            written=summary["written"],
            failed=0,
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "H2H graph computation complete: "
            f"{summary['graph_rows']} rows built, "
            f"{summary['written']} rows upserted, "
            f"{summary['skipped']} bouts skipped"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
