import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.table_name, columns))
        return self

    def upsert(self, row, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append({
            "table": self.table_name,
            "row": dict(row),
            "on_conflict": on_conflict,
        })
        return self

    def execute(self):
        if self.operation == "select":
            return FakeResult(self.client.rows)
        if self.operation == "upsert":
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.table_name}")


class FakeSupabase:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


class FakeSqlExecutor:
    def __init__(self):
        self.sql = []

    def __call__(self, sql):
        self.sql.append(sql)


def write_migration(migrations_dir, filename, sql):
    path = migrations_dir / filename
    path.write_text(sql, encoding="utf-8")
    return path


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_list_shows_applied_and_pending_migrations_from_mocked_db(capsys, tmp_path):
    from scripts import migrate

    applied = write_migration(tmp_path, "20260601_existing.sql", "select 1;\n")
    write_migration(tmp_path, "20260602_add_table.sql", "select 2;\n")
    client = FakeSupabase([
        {
            "filename": applied.name,
            "hash": file_hash(applied),
            "success": True,
            "applied_at": "2026-06-01T00:00:00Z",
        }
    ])

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "list"],
        client=client,
        sql_executor=FakeSqlExecutor(),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[applied] 20260601_existing.sql" in output
    assert "[pending] 20260602_add_table.sql" in output
    assert ("fs_schema_migrations", "filename,applied_at,hash,success") in client.selects


def test_generate_creates_dated_slugged_file_in_requested_directory(capsys, tmp_path, monkeypatch):
    from scripts import migrate

    monkeypatch.setattr(migrate, "current_date_prefix", lambda: "20260601")

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "generate", "--name", "add_table"],
        client=FakeSupabase(),
        sql_executor=FakeSqlExecutor(),
    )

    generated = tmp_path / "20260601_add_table.sql"
    assert exit_code == 0
    assert generated.exists()
    assert generated.read_text(encoding="utf-8").startswith("-- Migration: add_table\n")
    assert "Created migration: 20260601_add_table.sql" in capsys.readouterr().out


def test_dry_run_prints_pending_migrations_without_applying(capsys, tmp_path):
    from scripts import migrate

    applied = write_migration(tmp_path, "20260601_existing.sql", "select 1;\n")
    write_migration(tmp_path, "20260602_add_table.sql", "select 2;\n")
    sql_executor = FakeSqlExecutor()
    client = FakeSupabase([
        {
            "filename": applied.name,
            "hash": file_hash(applied),
            "success": True,
        }
    ])

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "dry-run"],
        client=client,
        sql_executor=sql_executor,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Would apply 1 migration(s):" in output
    assert "20260602_add_table.sql" in output
    assert "20260601_existing.sql" not in output
    assert sql_executor.sql == []


def test_apply_executes_pending_sql_and_records_success(capsys, tmp_path):
    from scripts import migrate

    migration = write_migration(
        tmp_path,
        "20260601_add_table.sql",
        "create table example(id serial primary key);\n",
    )
    client = FakeSupabase([])
    sql_executor = FakeSqlExecutor()

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "apply"],
        client=client,
        sql_executor=sql_executor,
    )

    assert exit_code == 0
    assert "Applied 1 migration(s)." in capsys.readouterr().out
    assert "CREATE TABLE IF NOT EXISTS fs_schema_migrations" in sql_executor.sql[0]
    assert "ALTER TABLE fs_schema_migrations ENABLE ROW LEVEL SECURITY" in sql_executor.sql[0]
    assert "REVOKE ALL ON fs_schema_migrations FROM anon" in sql_executor.sql[0]
    assert "REVOKE ALL ON fs_schema_migrations FROM authenticated" in sql_executor.sql[0]
    assert sql_executor.sql[1] == migration.read_text(encoding="utf-8")
    assert client.upserts[0]["table"] == "fs_schema_migrations"
    assert client.upserts[0]["on_conflict"] == "filename"
    assert client.upserts[0]["row"]["filename"] == migration.name
    assert client.upserts[0]["row"]["hash"] == file_hash(migration)
    assert client.upserts[0]["row"]["success"] is True


def test_apply_with_no_pending_migrations_does_not_require_sql_executor(capsys, tmp_path):
    from scripts import migrate

    migration = write_migration(tmp_path, "20260601_existing.sql", "select 1;\n")
    client = FakeSupabase([
        {
            "filename": migration.name,
            "hash": file_hash(migration),
            "success": True,
        }
    ])

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "apply"],
        client=client,
        sql_executor=None,
    )

    assert exit_code == 0
    assert "No pending migrations." in capsys.readouterr().out


def test_status_reports_last_applied_and_pending_count(capsys, tmp_path):
    from scripts import migrate

    applied = write_migration(tmp_path, "20260601_existing.sql", "select 1;\n")
    write_migration(tmp_path, "20260602_add_table.sql", "select 2;\n")
    client = FakeSupabase([
        {
            "filename": applied.name,
            "hash": file_hash(applied),
            "success": True,
        }
    ])

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "status"],
        client=client,
        sql_executor=FakeSqlExecutor(),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Last migration applied: 20260601_existing.sql" in output
    assert "Pending migrations: 1" in output


def test_hash_changes_are_reported_as_errors(capsys, tmp_path):
    from scripts import migrate

    migration = write_migration(tmp_path, "20260601_existing.sql", "select 1;\n")
    client = FakeSupabase([
        {
            "filename": migration.name,
            "hash": "not-the-current-hash",
            "success": True,
        }
    ])

    exit_code = migrate.main(
        ["--migrations-dir", str(tmp_path), "dry-run"],
        client=client,
        sql_executor=FakeSqlExecutor(),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR: applied migration hash mismatch" in captured.err
    assert "20260601_existing.sql" in captured.err
