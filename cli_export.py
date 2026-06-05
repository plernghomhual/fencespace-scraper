#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
DEFAULT_PAGE_SIZE = 1000


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _apply_eq(query, column: str, value: Any):
    if value is None or value == "":
        return query
    return query.eq(column, value)


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _csv_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def write_output(rows: list[dict[str, Any]], output_format: str, output_path: str | None) -> None:
    if output_format == "json":
        content = json.dumps(rows, indent=2, sort_keys=True) + "\n"
    else:
        buffer = sys.stdout if output_path is None else None
        if buffer is None:
            from io import StringIO

            buffer = StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=_csv_fieldnames(rows))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _jsonable_value(value) for key, value in row.items()})
        content = "" if output_path is None else buffer.getvalue()  # type: ignore[union-attr]

    if output_path:
        Path(output_path).write_text(content)
    elif output_format == "json":
        sys.stdout.write(content)


def fetch_rows(client, table_name: str, configure, page_size: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table_name).select("*")
        if configure:
            query = configure(query)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        print(f"Fetched {len(rows)} rows", file=sys.stderr)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def configure_fencers(args):
    def configure(query):
        query = _apply_eq(query, "country", args.country)
        query = _apply_eq(query, "weapon", args.weapon)
        return _apply_eq(query, "category", args.category)

    return configure


def configure_tournaments(args):
    def configure(query):
        query = _apply_eq(query, "season", args.season)
        query = _apply_eq(query, "type", args.type)
        return _apply_eq(query, "country", args.country)

    return configure


def configure_rankings(args):
    def configure(query):
        query = _apply_eq(query, "season", args.season)
        query = _apply_eq(query, "weapon", args.weapon)
        query = _apply_eq(query, "gender", args.gender)
        return _apply_eq(query, "category", args.category)

    return configure


def configure_h2h(args):
    def configure(query):
        query = query.or_(f"fencer_a_id.eq.{args.fencer},fencer_b_id.eq.{args.fencer}")
        if args.min_bouts:
            query = query.gte("bouts_total", args.min_bouts)
        return query

    return configure


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", help="Output file path. Defaults to stdout.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export FenceSpace data from Supabase")
    sub = parser.add_subparsers(dest="command", required=True)

    fencers = sub.add_parser("fencers", help="Export fencers")
    add_common_args(fencers)
    fencers.add_argument("--country")
    fencers.add_argument("--weapon")
    fencers.add_argument("--category")

    tournaments = sub.add_parser("tournaments", help="Export tournaments")
    add_common_args(tournaments)
    tournaments.add_argument("--season", type=int)
    tournaments.add_argument("--type")
    tournaments.add_argument("--country")

    rankings = sub.add_parser("rankings", help="Export ranking history")
    add_common_args(rankings)
    rankings.add_argument("--season", type=int)
    rankings.add_argument("--weapon")
    rankings.add_argument("--gender")
    rankings.add_argument("--category")

    h2h = sub.add_parser("h2h", help="Export head-to-head rows for a fencer")
    add_common_args(h2h)
    h2h.add_argument("--fencer", required=True)
    h2h.add_argument("--min-bouts", type=int, default=0)

    return parser


def command_config(args):
    if args.command == "fencers":
        return "fs_fencers", configure_fencers(args)
    if args.command == "tournaments":
        return "fs_tournaments", configure_tournaments(args)
    if args.command == "rankings":
        return "fs_rankings_history", configure_rankings(args)
    if args.command == "h2h":
        return "fs_head_to_head", configure_h2h(args)
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.page_size < 1:
        parser.error("--page-size must be positive")

    table_name, configure = command_config(args)
    rows = fetch_rows(get_supabase_client(), table_name, configure, args.page_size)
    write_output(rows, args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
