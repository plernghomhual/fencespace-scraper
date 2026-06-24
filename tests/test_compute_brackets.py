import os
import sys
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
TOURNAMENT_ID = "10000000-0000-0000-0000-000000000001"

F1 = "00000000-0000-0000-0000-000000000001"
F2 = "00000000-0000-0000-0000-000000000002"
F3 = "00000000-0000-0000-0000-000000000003"
F4 = "00000000-0000-0000-0000-000000000004"
F5 = "00000000-0000-0000-0000-000000000005"
F6 = "00000000-0000-0000-0000-000000000006"
F7 = "00000000-0000-0000-0000-000000000007"
F8 = "00000000-0000-0000-0000-000000000008"
F9 = "00000000-0000-0000-0000-000000000009"
F10 = "00000000-0000-0000-0000-000000000010"
F11 = "00000000-0000-0000-0000-000000000011"
F12 = "00000000-0000-0000-0000-000000000012"


def tournament(**overrides):
    row = {
        "id": TOURNAMENT_ID,
        "name": "World Cup Foil",
        "weapon": "Foil",
        "gender": "Men",
        "category": "Senior",
        "metadata": {
            "source": "fie",
            "source_url": "https://fie.org/competitions/2026/123",
        },
    }
    row.update(overrides)
    return row


def result(fencer_id, event_key="men-foil", **metadata):
    event_metadata = {
        "event_key": event_key,
        "weapon": metadata.pop("weapon", "Foil"),
        "gender": metadata.pop("gender", "Men"),
        "category": metadata.pop("category", "Senior"),
        "source": metadata.pop("source", "fie-results"),
    }
    event_metadata.update(metadata)
    return {
        "id": f"result-{fencer_id[-2:]}-{event_key}",
        "tournament_id": TOURNAMENT_ID,
        "fencer_id": fencer_id,
        "rank": 1,
        "metadata": event_metadata,
    }


def bout(
    bout_id,
    round_name,
    order,
    fencer_a,
    fencer_b,
    score_a=None,
    score_b=None,
    winner_id=None,
    event_key="men-foil",
    **metadata,
):
    bout_metadata = {
        "event_key": event_key,
        "bout_order": order,
        "piste": metadata.pop("piste", None),
        "source": metadata.pop("source", "fie-tableau"),
    }
    bout_metadata.update(metadata)
    return {
        "id": bout_id,
        "tournament_id": TOURNAMENT_ID,
        "fencer_a_id": fencer_a,
        "fencer_b_id": fencer_b,
        "score_a": score_a,
        "score_b": score_b,
        "round": round_name,
        "winner_id": winner_id,
        "metadata": {k: v for k, v in bout_metadata.items() if v is not None},
    }


def complete_eight_person_bouts():
    return [
        bout("qf-1", "Tableau of 8", 1, F1, F8, 15, 6, F1, seed_a=1, seed_b=8),
        bout("qf-2", "Tableau of 8", 2, F4, F5, 15, 14, F4, seed_a=4, seed_b=5),
        bout("qf-3", "Tableau of 8", 3, F3, F6, 13, 15, F6, seed_a=3, seed_b=6),
        bout("qf-4", "Tableau of 8", 4, F2, F7, 15, 8, F2, seed_a=2, seed_b=7),
        bout("sf-1", "Tableau of 4", 1, F1, F4, 15, 12, F1),
        bout("sf-2", "Tableau of 4", 2, F6, F2, 9, 15, F2),
        bout("final", "Final", 1, F1, F2, 15, 13, F1, piste="Blue"),
    ]


def all_results():
    return [result(fencer) for fencer in (F1, F2, F3, F4, F5, F6, F7, F8)]


def test_builds_complete_eight_person_bracket_from_ordered_elimination_bouts():
    from compute_brackets import build_tournament_bracket_rows

    rows, skip_reason = build_tournament_bracket_rows(
        tournament(), complete_eight_person_bouts(), all_results(), updated_at=NOW
    )

    assert skip_reason is None
    assert len(rows) == 7
    assert [row["round_order"] for row in rows] == [1, 1, 1, 1, 2, 2, 3]
    assert [row["bout_order"] for row in rows] == [1, 2, 3, 4, 1, 2, 1]

    first = rows[0]
    assert first["tournament_id"] == TOURNAMENT_ID
    assert first["event_key"] == "men-foil"
    assert first["weapon"] == "Foil"
    assert first["gender"] == "Men"
    assert first["category"] == "Senior"
    assert first["round_name"] == "Tableau of 8"
    assert first["fencer_a_id"] == F1
    assert first["fencer_b_id"] == F8
    assert first["score_a"] == 15
    assert first["score_b"] == 6
    assert first["winner_id"] == F1
    assert first["seed_a"] == 1
    assert first["seed_b"] == 8
    assert first["source"] == "fie-tableau"
    assert first["is_bye"] is False
    assert first["metadata"]["source_bout_id"] == "qf-1"
    assert first["metadata"]["source_url"] == "https://fie.org/competitions/2026/123"
    assert first["updated_at"] == NOW

    final = rows[-1]
    assert final["round_name"] == "Final"
    assert final["piste"] == "Blue"
    assert final["bracket_key"] == f"{TOURNAMENT_ID}:men-foil:3:1"


def test_preserves_explicit_byes_without_fabricating_missing_opponents():
    from compute_brackets import build_tournament_bracket_rows

    rows, skip_reason = build_tournament_bracket_rows(
        tournament(),
        [
            bout(
                "bye-qf-1",
                "Tableau of 8",
                1,
                F1,
                None,
                None,
                None,
                F1,
                is_bye=True,
                seed_a=1,
            ),
            bout("qf-2", "Tableau of 8", 2, F4, F5, 15, 14, F4),
            bout("sf-1", "Tableau of 4", 1, F1, F4, 15, 10, F1),
            bout("final", "Final", 1, F1, F2, 15, 13, F1),
        ],
        all_results(),
        updated_at=NOW,
    )

    assert skip_reason is None
    bye = rows[0]
    assert bye["is_bye"] is True
    assert bye["fencer_a_id"] == F1
    assert bye["fencer_b_id"] is None
    assert bye["score_a"] is None
    assert bye["score_b"] is None
    assert bye["winner_id"] == F1


def test_dedupes_same_round_position_and_keeps_most_complete_bout():
    from compute_brackets import build_tournament_bracket_rows

    rows, skip_reason = build_tournament_bracket_rows(
        tournament(),
        [
            bout("qf-1-incomplete", "Tableau of 8", 1, F1, F8, None, None, None),
            bout("qf-1-complete", "Tableau of 8", 1, F1, F8, 15, 6, F1),
            bout("sf-1", "Tableau of 4", 1, F1, F4, 15, 12, F1),
            bout("final", "Final", 1, F1, F2, 15, 13, F1),
        ],
        all_results(),
        updated_at=NOW,
    )

    assert skip_reason is None
    assert len(rows) == 3
    first = rows[0]
    assert first["score_a"] == 15
    assert first["score_b"] == 6
    assert first["winner_id"] == F1
    assert first["metadata"]["source_bout_id"] == "qf-1-complete"


def test_keeps_partial_rows_and_derives_winner_only_when_scores_prove_it():
    from compute_brackets import build_tournament_bracket_rows

    rows, skip_reason = build_tournament_bracket_rows(
        tournament(),
        [
            bout("sf-1", "Semifinal", 1, F1, F4, 15, 12, None),
            bout("sf-2", "Semifinal", 2, F2, F6, None, None, None),
            bout("final", "Final", 1, F1, F2, None, None, None),
        ],
        all_results(),
        updated_at=NOW,
    )

    assert skip_reason is None
    assert rows[0]["winner_id"] == F1
    assert rows[1]["winner_id"] is None
    assert rows[1]["score_a"] is None
    assert rows[1]["score_b"] is None
    assert rows[2]["winner_id"] is None


def test_groups_multiple_events_by_result_metadata_when_bouts_have_no_event_key():
    from compute_brackets import build_tournament_bracket_rows

    results = [
        result(F1, "men-foil", weapon="Foil", gender="Men"),
        result(F2, "men-foil", weapon="Foil", gender="Men"),
        result(F3, "men-foil", weapon="Foil", gender="Men"),
        result(F4, "men-foil", weapon="Foil", gender="Men"),
        result(F9, "women-epee", weapon="Epee", gender="Women"),
        result(F10, "women-epee", weapon="Epee", gender="Women"),
        result(F11, "women-epee", weapon="Epee", gender="Women"),
        result(F12, "women-epee", weapon="Epee", gender="Women"),
    ]
    bouts = [
        bout("mf-sf-1", "Semifinal", 1, F1, F4, 15, 9, F1, event_key=None),
        bout("mf-final", "Final", 1, F1, F2, 15, 11, F1, event_key=None),
        bout("we-sf-1", "Semifinal", 1, F9, F12, 15, 13, F9, event_key=None),
        bout("we-final", "Final", 1, F9, F10, 12, 15, F10, event_key=None),
    ]

    rows, skip_reason = build_tournament_bracket_rows(
        tournament(weapon=None, gender=None), bouts, results, updated_at=NOW
    )

    assert skip_reason is None
    by_event: dict[Any, Any] = {}
    for row in rows:
        by_event.setdefault(row["event_key"], []).append(row)

    assert set(by_event) == {"men-foil", "women-epee"}
    assert {row["weapon"] for row in by_event["men-foil"]} == {"Foil"}
    assert {row["gender"] for row in by_event["women-epee"]} == {"Women"}
    assert len(by_event["men-foil"]) == 2
    assert len(by_event["women-epee"]) == 2


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.rows = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.name, []))
            return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FakeRunLogger:
    instances: list["FakeRunLogger"] = []

    def __init__(self, module):
        self.module = module
        self.completed: list[dict[str, Any]] = []
        self.errors = []
        FakeRunLogger.instances.append(self)

    def start(self):
        return self

    def complete(self, **kwargs):
        self.completed.append(kwargs)

    def error(self, exc_str):
        self.errors.append(exc_str)


def test_compute_brackets_upserts_with_idempotent_conflict_key_and_counts(monkeypatch):
    import compute_brackets

    client = FakeSupabase(
        {
            "fs_tournaments": [tournament()],
            "fs_results": all_results(),
            "fs_bouts": complete_eight_person_bouts(),
        }
    )
    monkeypatch.setattr(compute_brackets, "set_state", lambda *args, **kwargs: None)

    summary = compute_brackets.compute_brackets(
        client=client,
        page_size=50,
        updated_at=NOW,
        log_run=False,
        update_state=True,
    )

    assert summary["written"] == 7
    assert summary["skipped"] == 0
    assert summary["failed"] == 0
    assert summary["tournaments_read"] == 1
    assert summary["bouts_read"] == 7
    assert summary["results_read"] == 8
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_tournament_brackets"
    assert upsert["on_conflict"] == "tournament_id,event_key,round_order,bout_order"
    assert len(upsert["rows"]) == 7
    assert all(row["bracket_key"] for row in upsert["rows"])


def test_compute_brackets_logs_skipped_tournament_when_round_or_order_evidence_is_missing(
    monkeypatch,
):
    import compute_brackets

    FakeRunLogger.instances = []
    client = FakeSupabase(
        {
            "fs_tournaments": [tournament()],
            "fs_results": all_results(),
            "fs_bouts": [
                bout("pool-1", "Pool 1", 1, F1, F2, 5, 3, F1),
                bout("unordered-qf", "Tableau of 8", None, F3, F4, 15, 14, F3),
            ],
        }
    )
    monkeypatch.setattr(compute_brackets, "ScraperRunLogger", FakeRunLogger)
    monkeypatch.setattr(compute_brackets, "set_state", lambda *args, **kwargs: None)

    summary = compute_brackets.compute_brackets(
        client=client,
        page_size=50,
        updated_at=NOW,
        log_run=True,
        update_state=True,
    )

    assert summary["written"] == 0
    assert summary["skipped"] == 1
    assert summary["failed"] == 0
    assert summary["skipped_tournaments"] == [
        {
            "tournament_id": TOURNAMENT_ID,
            "reason": "missing_bout_order",
        }
    ]
    assert client.upserts == []
    assert FakeRunLogger.instances[0].module == "compute_brackets"
    assert FakeRunLogger.instances[0].completed[0]["written"] == 0
    assert FakeRunLogger.instances[0].completed[0]["skipped"] == 1
    assert FakeRunLogger.instances[0].completed[0]["failed"] == 0


def test_compute_brackets_tracks_failed_tournaments_separately_from_skips(monkeypatch):
    import compute_brackets

    client = FakeSupabase(
        {
            "fs_tournaments": [tournament()],
            "fs_results": all_results(),
            "fs_bouts": complete_eight_person_bouts(),
        }
    )
    monkeypatch.setattr(compute_brackets, "set_state", lambda *args, **kwargs: None)

    def broken_builder(*args, **kwargs):
        raise RuntimeError("bad bracket")

    monkeypatch.setattr(compute_brackets, "build_tournament_bracket_rows", broken_builder)

    summary = compute_brackets.compute_brackets(
        client=client,
        page_size=50,
        updated_at=NOW,
        log_run=False,
        update_state=True,
    )

    assert summary["written"] == 0
    assert summary["skipped"] == 0
    assert summary["failed"] == 1
    assert summary["skipped_tournaments"] == []
    assert summary["failed_tournaments"] == [
        {
            "tournament_id": TOURNAMENT_ID,
            "reason": "bad bracket",
        }
    ]


def test_main_returns_no_credential_summary_without_creating_client(monkeypatch, capsys):
    import compute_brackets

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    summary = compute_brackets.main()

    assert summary["no_credentials"] is True
    assert summary["written"] == 0
    assert "SUPABASE_URL and SUPABASE_SERVICE_KEY are not set" in capsys.readouterr().out
