#!/usr/bin/env python3
"""Small Supabase schema migration CLI."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
TRACKING_TABLE = "fs_schema_migrations"
TRACKING_COLUMNS = "filename,applied_at,hash,success"
MIGRATION_FILENAME_RE = re.compile(r"^\d{8}(?:\d{6})?_[A-Za-z0-9][A-Za-z0-9_-]*\.sql$")

TRACKING_TABLE_SQL = """CREATE TABLE IF NOT EXISTS fs_schema_migrations (
    id serial PRIMARY KEY,
    filename text UNIQUE NOT NULL,
    applied_at timestamptz DEFAULT now(),
    hash text,
    success boolean DEFAULT true
);
ALTER TABLE fs_schema_migrations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON fs_schema_migrations FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON fs_schema_migrations FROM authenticated;
    END IF;
END $$;
"""

SqlExecutor = Callable[[str], None]


@dataclass(frozen=True)
class MigrationFile:
    path: Path
    filename: str
    hash: str

    def read_sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


class MigrationHashMismatch(Exception):
    def __init__(self, messages: list[str]):
        super().__init__("\n".join(messages))
        self.messages = messages


def current_date_prefix() -> str:
    return date.today().strftime("%Y%m%d")


def migration_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_migrations(migrations_dir: Path) -> list[MigrationFile]:
    if not migrations_dir.exists():
        return []

    migrations = []
    for path in migrations_dir.iterdir():
        if path.is_file() and MIGRATION_FILENAME_RE.match(path.name):
            migrations.append(MigrationFile(path=path, filename=path.name, hash=migration_hash(path)))
    return sorted(migrations, key=lambda migration: migration.filename)


def slugify_migration_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise ValueError("migration name must contain at least one letter or number")
    return slug


def migration_template(slug: str) -> str:
    created_at = datetime.now(timezone.utc).isoformat()
    return (
        f"-- Migration: {slug}\n"
        f"-- Created: {created_at}\n\n"
        "-- Write migration SQL below.\n"
    )


def build_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    from supabase import create_client

    return create_client(url, key)


def build_psql_executor() -> SqlExecutor:
    database_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL or DATABASE_URL must be set to apply migrations.")

    psql = shutil.which("psql")
    if not psql:
        raise RuntimeError("psql command not found; install PostgreSQL client tools to apply migrations.")

    def execute(sql: str) -> None:
        result = subprocess.run(
            [psql, database_url, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-1"],
            input=sql,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"psql exited with {result.returncode}"
            raise RuntimeError(detail)

    return execute


def tracking_table_missing(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        TRACKING_TABLE in message
        and (
            "does not exist" in message
            or "not found" in message
            or "schema cache" in message
            or "pgrst" in message
        )
    )


def fetch_migration_rows(client: Any) -> list[dict[str, Any]]:
    try:
        result = client.table(TRACKING_TABLE).select(TRACKING_COLUMNS).execute()
    except Exception as exc:
        if tracking_table_missing(exc):
            return []
        raise

    rows = list(result.data or [])
    return sorted(rows, key=lambda row: str(row.get("filename") or ""))


def row_is_success(row: dict[str, Any] | None) -> bool:
    return bool(row and row.get("success", True) is not False)


def rows_by_filename(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["filename"]): row
        for row in rows
        if row.get("filename")
    }


def validate_applied_hashes(migrations: list[MigrationFile], rows: list[dict[str, Any]]) -> None:
    by_filename = rows_by_filename(rows)
    messages: list[str] = []
    for migration in migrations:
        row = by_filename.get(migration.filename)
        if not row_is_success(row):
            continue
        if row is None:
            continue
        stored_hash = row.get("hash")
        if stored_hash and stored_hash != migration.hash:
            messages.append(
                "ERROR: applied migration hash mismatch for "
                f"{migration.filename} (database={stored_hash}, current={migration.hash})"
            )
    if messages:
        raise MigrationHashMismatch(messages)


def pending_migrations(migrations: list[MigrationFile], rows: list[dict[str, Any]]) -> list[MigrationFile]:
    by_filename = rows_by_filename(rows)
    return [
        migration
        for migration in migrations
        if not row_is_success(by_filename.get(migration.filename))
    ]


def record_migration(client: Any, migration: MigrationFile, *, success: bool) -> None:
    row = {
        "filename": migration.filename,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "hash": migration.hash,
        "success": success,
    }
    client.table(TRACKING_TABLE).upsert(row, on_conflict="filename").execute()


def status_for_migration(migration: MigrationFile, rows: list[dict[str, Any]]) -> str:
    row = rows_by_filename(rows).get(migration.filename)
    if row_is_success(row):
        return "applied"
    if row:
        return "failed"
    return "pending"


def command_list(migrations_dir: Path, client: Any, stdout: TextIO) -> int:
    migrations = discover_migrations(migrations_dir)
    rows = fetch_migration_rows(client)
    validate_applied_hashes(migrations, rows)

    if not migrations:
        print("No migration files found.", file=stdout)
        return 0

    by_filename = rows_by_filename(rows)
    for migration in migrations:
        status = status_for_migration(migration, rows)
        row = by_filename.get(migration.filename) or {}
        applied_at = row.get("applied_at")
        suffix = f" ({applied_at})" if applied_at and status == "applied" else ""
        print(f"[{status}] {migration.filename}{suffix}", file=stdout)
    return 0


def command_dry_run(migrations_dir: Path, client: Any, stdout: TextIO) -> int:
    migrations = discover_migrations(migrations_dir)
    rows = fetch_migration_rows(client)
    validate_applied_hashes(migrations, rows)

    pending = pending_migrations(migrations, rows)
    if not pending:
        print("No pending migrations.", file=stdout)
        return 0

    print(f"Would apply {len(pending)} migration(s):", file=stdout)
    for migration in pending:
        print(f"  {migration.filename}", file=stdout)
    return 0


def command_status(migrations_dir: Path, client: Any, stdout: TextIO) -> int:
    migrations = discover_migrations(migrations_dir)
    rows = fetch_migration_rows(client)
    validate_applied_hashes(migrations, rows)

    applied = sorted(
        str(row["filename"])
        for row in rows
        if row.get("filename") and row_is_success(row)
    )
    pending = pending_migrations(migrations, rows)

    print(f"Last migration applied: {applied[-1] if applied else 'none'}", file=stdout)
    print(f"Pending migrations: {len(pending)}", file=stdout)
    return 0


def command_generate(migrations_dir: Path, name: str, stdout: TextIO) -> int:
    migrations_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify_migration_name(name)
    filename = f"{current_date_prefix()}_{slug}.sql"
    path = migrations_dir / filename
    if path.exists():
        raise FileExistsError(f"migration already exists: {path}")

    path.write_text(migration_template(slug), encoding="utf-8")
    print(f"Created migration: {filename}", file=stdout)
    return 0


def command_apply(
    migrations_dir: Path,
    client: Any,
    sql_executor: SqlExecutor | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    migrations = discover_migrations(migrations_dir)
    rows = fetch_migration_rows(client)
    validate_applied_hashes(migrations, rows)
    pending = pending_migrations(migrations, rows)

    if not pending:
        print("No pending migrations.", file=stdout)
        return 0

    sql_executor = sql_executor or build_psql_executor()
    sql_executor(TRACKING_TABLE_SQL)

    applied_count = 0
    for migration in pending:
        print(f"Applying {migration.filename}...", file=stdout)
        try:
            sql_executor(migration.read_sql())
        except Exception as exc:
            try:
                record_migration(client, migration, success=False)
            except Exception as record_exc:
                print(f"ERROR: failed to record failed migration {migration.filename}: {record_exc}", file=stderr)
            print(f"ERROR: failed to apply {migration.filename}: {exc}", file=stderr)
            return 1

        try:
            record_migration(client, migration, success=True)
        except Exception as exc:
            print(f"ERROR: applied {migration.filename} but failed to record it: {exc}", file=stderr)
            return 1

        applied_count += 1
        print(f"Applied {migration.filename}", file=stdout)

    print(f"Applied {applied_count} migration(s).", file=stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage FenceSpace Supabase SQL migrations.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=DEFAULT_MIGRATIONS_DIR,
        help="Directory containing migration SQL files.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List migration files and applied status.")
    subparsers.add_parser("apply", help="Apply all unapplied migrations in filename order.")
    subparsers.add_parser("dry-run", help="Show unapplied migrations without applying them.")
    subparsers.add_parser("status", help="Show last applied migration and pending count.")

    generate_parser = subparsers.add_parser("generate", help="Create a new dated migration file.")
    generate_parser.add_argument("--name", required=True, help="Migration description, e.g. add_table.")

    return parser


def main(
    argv: list[str] | None = None,
    *,
    client: Any | None = None,
    sql_executor: SqlExecutor | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "generate":
            return command_generate(args.migrations_dir, args.name, stdout)

        client = client or build_supabase_client()

        if args.command == "list":
            return command_list(args.migrations_dir, client, stdout)
        if args.command == "dry-run":
            return command_dry_run(args.migrations_dir, client, stdout)
        if args.command == "status":
            return command_status(args.migrations_dir, client, stdout)
        if args.command == "apply":
            return command_apply(args.migrations_dir, client, sql_executor, stdout, stderr)
    except MigrationHashMismatch as exc:
        for message in exc.messages:
            print(message, file=stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
