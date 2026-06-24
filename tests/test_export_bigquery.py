import importlib
import json
import os
import sys
from decimal import Decimal
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.selected = None
        self.start = 0
        self.end = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        rows = self.client.tables.get(self.table_name, [])
        return FakeResponse(rows[self.start : cast(int, self.end) + 1])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.ranges = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class RecordingWriter:
    dry_run = False

    def __init__(self, fail_first=False):
        self.fail_first = fail_first
        self.calls = []
        self.attempts = 0

    def prepare_table(self, config):
        self.prepared = config.key

    def load_rows(self, config, rows, chunk_index):
        self.attempts += 1
        if self.fail_first and self.attempts == 1:
            raise RuntimeError("transient load failure")
        copied = [dict(row) for row in rows]
        self.calls.append((config.key, chunk_index, copied))
        return len(copied)


def load_module(monkeypatch):
    sys.modules.pop("export_bigquery", None)
    monkeypatch.delenv("BIGQUERY_PROJECT", raising=False)
    monkeypatch.delenv("BIGQUERY_DATASET", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    return importlib.import_module("export_bigquery")


def test_schema_mapping_has_explicit_types_and_nullable_modes(monkeypatch):
    module = load_module(monkeypatch)

    fencer_schema = {column.name: column for column in module.schema_for("fencers")}
    assert fencer_schema["id"].bq_type == "STRING"
    assert fencer_schema["id"].mode == "REQUIRED"
    assert fencer_schema["world_rank"].bq_type == "INTEGER"
    assert fencer_schema["world_rank"].mode == "NULLABLE"
    assert fencer_schema["metadata"].bq_type == "JSON"

    analytics_schema = {
        column.name: column for column in module.schema_for("competition_strength")
    }
    assert analytics_schema["tournament_id"].bq_type == "STRING"
    assert analytics_schema["tournament_id"].mode == "REQUIRED"
    assert analytics_schema["top8_count"].bq_type == "INTEGER"
    assert analytics_schema["top8_count"].mode == "REQUIRED"
    assert analytics_schema["strength_score"].bq_type == "NUMERIC"
    assert analytics_schema["strength_score"].mode == "NULLABLE"


def test_payload_builders_coerce_types_and_missing_nullable_fields(monkeypatch):
    module = load_module(monkeypatch)

    payload = module.build_fencer_payload(
        {
            "id": 123,
            "fie_id": 456,
            "name": "Alex Lee",
            "world_rank": "12",
            "fie_points": Decimal("98.50"),
            "date_of_birth": "",
            "metadata": '{"seed": 3}',
        }
    )

    assert payload["id"] == "123"
    assert payload["fie_id"] == "456"
    assert payload["world_rank"] == 12
    assert payload["fie_points"] == "98.50"
    assert payload["date_of_birth"] is None
    assert payload["image_url"] is None
    assert payload["metadata"] == {"seed": 3}

    analytics = module.build_analytics_payload(
        "competition_strength",
        {
            "tournament_id": "t1",
            "top8_count": "2",
            "top16_count": 4,
            "total_fie_ranked": 16,
            "strength_score": Decimal("87.25"),
        },
    )
    assert analytics["top8_count"] == 2
    assert analytics["strength_score"] == "87.25"
    assert analytics["avg_world_rank"] is None


def test_dry_run_exports_schema_and_jsonl_without_google_credentials(tmp_path, monkeypatch):
    module = load_module(monkeypatch)
    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": "f1", "name": "Alex Lee", "world_rank": "1"},
                {"id": "f2", "name": "Mina Park", "world_rank": "2"},
            ]
        }
    )
    writer = module.build_writer(output_dir=tmp_path, dry_run=False)

    summary = module.export_table(
        "fencers",
        client=client,
        writer=writer,
        page_size=1,
        chunk_size=1,
        update_state=False,
        log_run=False,
    )

    assert summary == {
        "table": "fencers",
        "source_table": "fs_fencers",
        "destination_table": "fs_fencers",
        "rows_read": 2,
        "rows_written": 2,
        "failed": 0,
        "skipped": 0,
        "chunks": 2,
        "dry_run": True,
    }
    schema = json.loads((tmp_path / "fs_fencers.schema.json").read_text())
    assert {"name": "world_rank", "type": "INTEGER", "mode": "NULLABLE"} in schema
    chunks = sorted(tmp_path.glob("fs_fencers.chunk-*.jsonl"))
    assert len(chunks) == 2
    assert json.loads(chunks[0].read_text().splitlines()[0])["world_rank"] == 1


def test_export_table_streams_pages_chunks_and_tracks_state(monkeypatch):
    module = load_module(monkeypatch)
    rows = [{"id": f"f{i}", "name": f"Fencer {i}"} for i in range(5)]
    client = FakeSupabase({"fs_fencers": rows})
    writer = RecordingWriter()
    state_updates = []

    summary = module.export_table(
        "fencers",
        client=client,
        writer=writer,
        page_size=2,
        chunk_size=2,
        state_setter=lambda source, key, value: state_updates.append((source, key, value)),
        log_run=False,
    )

    assert client.ranges == [
        ("fs_fencers", 0, 1),
        ("fs_fencers", 2, 3),
        ("fs_fencers", 4, 5),
    ]
    assert [len(call[2]) for call in writer.calls] == [2, 2, 1]
    assert [call[1] for call in writer.calls] == [1, 2, 3]
    assert summary["rows_written"] == 5
    assert summary["chunks"] == 3
    assert state_updates[-1] == (
        "export_bigquery",
        "progress:fs_fencers",
        {
            "destination_table": "fs_fencers",
            "offset": 5,
            "rows_written": 5,
            "chunks": 3,
            "completed": True,
        },
    )


def test_failed_chunk_is_retried_before_progress_is_recorded(monkeypatch):
    module = load_module(monkeypatch)
    client = FakeSupabase({"fs_fencers": [{"id": "f1", "name": "Alex Lee"}]})
    writer = RecordingWriter(fail_first=True)
    state_updates = []

    summary = module.export_table(
        "fencers",
        client=client,
        writer=writer,
        page_size=1,
        chunk_size=1,
        retries=2,
        state_setter=lambda source, key, value: state_updates.append((source, key, value)),
        log_run=False,
    )

    assert writer.attempts == 2
    assert summary["rows_written"] == 1
    assert summary["failed"] == 0
    assert state_updates[0][2]["offset"] == 1
    assert state_updates[0][2]["completed"] is False


def test_validation_skips_include_capped_diagnostics(monkeypatch):
    module = load_module(monkeypatch)
    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": "f1", "name": "Alex Lee"},
                {"id": "", "name": "Missing Id", "metadata": {"private": "not logged"}},
            ]
        }
    )
    writer = RecordingWriter()

    summary = module.export_table(
        "fencers",
        client=client,
        writer=writer,
        page_size=2,
        chunk_size=2,
        update_state=False,
        log_run=False,
    )

    assert summary["rows_read"] == 2
    assert summary["rows_written"] == 1
    assert summary["skipped"] == 1
    assert summary["validation_errors"] == [{"source_offset": 1, "row_id": None, "error": "id is required"}]
    assert "private" not in json.dumps(summary["validation_errors"])


def test_resume_continues_from_saved_offset_and_chunk_number(monkeypatch):
    module = load_module(monkeypatch)
    rows = [{"id": f"f{i}", "name": f"Fencer {i}"} for i in range(4)]
    client = FakeSupabase({"fs_fencers": rows})
    writer = RecordingWriter()
    state_updates = []

    def fake_get_state(source, key):
        assert (source, key) == ("export_bigquery", "progress:fs_fencers")
        return {
            "offset": 2,
            "rows_written": 2,
            "chunks": 1,
            "completed": False,
        }

    summary = module.export_table(
        "fencers",
        client=client,
        writer=writer,
        page_size=2,
        chunk_size=2,
        resume=True,
        state_getter=fake_get_state,
        state_setter=lambda source, key, value: state_updates.append((source, key, value)),
        log_run=False,
    )

    assert client.ranges == [("fs_fencers", 2, 3), ("fs_fencers", 4, 5)]
    assert writer.calls[0][1] == 2
    assert summary["rows_read"] == 2
    assert summary["rows_written"] == 4
    assert summary["chunks"] == 2
    assert state_updates[-1][2] == {
        "destination_table": "fs_fencers",
        "offset": 4,
        "rows_written": 4,
        "chunks": 2,
        "completed": True,
    }
