#!/usr/bin/env python3
"""Export FenceSpace Supabase tables to BigQuery or local dry-run artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "export_bigquery"
DEFAULT_PAGE_SIZE = 1000
DEFAULT_CHUNK_SIZE = 5000
DEFAULT_RETRIES = 2
DEFAULT_OUTPUT_DIR = "bigquery_export"
VALIDATION_DIAGNOSTIC_LIMIT = 50


@dataclass(frozen=True)
class Column:
    name: str
    bq_type: str
    mode: str = "NULLABLE"

    def as_json(self) -> dict[str, str]:
        return {"name": self.name, "type": self.bq_type, "mode": self.mode}


@dataclass(frozen=True)
class ExportConfig:
    key: str
    source_table: str
    destination_table: str
    schema: tuple[Column, ...]


class RowValidationError(ValueError):
    """Raised when a source row cannot satisfy the explicit export schema."""


def c(name: str, bq_type: str, mode: str = "NULLABLE") -> Column:
    return Column(name=name, bq_type=bq_type, mode=mode)


FENCER_SCHEMA = (
    c("id", "STRING", "REQUIRED"),
    c("fie_id", "STRING"),
    c("name", "STRING"),
    c("country", "STRING"),
    c("nationality", "STRING"),
    c("weapon", "STRING"),
    c("category", "STRING"),
    c("world_rank", "INTEGER"),
    c("fie_points", "NUMERIC"),
    c("national_rank", "INTEGER"),
    c("national_rank_points", "NUMERIC"),
    c("national_rank_source", "STRING"),
    c("national_rank_season", "STRING"),
    c("club", "STRING"),
    c("image_url", "STRING"),
    c("date_of_birth", "DATE"),
    c("birth_date", "DATE"),
    c("birth_place", "STRING"),
    c("bio_source", "STRING"),
    c("hand", "STRING"),
    c("height", "INTEGER"),
    c("metadata", "JSON"),
    c("updated_at", "TIMESTAMP"),
)

TOURNAMENT_SCHEMA = (
    c("id", "STRING", "REQUIRED"),
    c("source_id", "STRING"),
    c("name", "STRING"),
    c("season", "INTEGER"),
    c("type", "STRING"),
    c("weapon", "STRING"),
    c("gender", "STRING"),
    c("category", "STRING"),
    c("country", "STRING"),
    c("location", "STRING"),
    c("city", "STRING"),
    c("start_date", "DATE"),
    c("end_date", "DATE"),
    c("competition_url_id", "STRING"),
    c("results_url", "STRING"),
    c("has_results", "BOOLEAN"),
    c("results_unavailable", "BOOLEAN"),
    c("organizer", "STRING"),
    c("entry_deadline", "DATE"),
    c("format", "STRING"),
    c("quota", "INTEGER"),
    c("latitude", "FLOAT"),
    c("longitude", "FLOAT"),
    c("metadata", "JSON"),
    c("created_at", "TIMESTAMP"),
    c("updated_at", "TIMESTAMP"),
)

RESULT_SCHEMA = (
    c("id", "STRING"),
    c("tournament_id", "STRING", "REQUIRED"),
    c("fencer_id", "STRING"),
    c("fie_fencer_id", "STRING"),
    c("name", "STRING"),
    c("country", "STRING"),
    c("nationality", "STRING"),
    c("rank", "INTEGER"),
    c("placement", "INTEGER"),
    c("medal", "STRING"),
    c("weapon", "STRING"),
    c("gender", "STRING"),
    c("category", "STRING"),
    c("victory", "INTEGER"),
    c("matches", "INTEGER"),
    c("td", "INTEGER"),
    c("tr", "INTEGER"),
    c("diff", "INTEGER"),
    c("points", "NUMERIC"),
    c("seed", "INTEGER"),
    c("metadata", "JSON"),
    c("updated_at", "TIMESTAMP"),
)

BOUT_SCHEMA = (
    c("id", "STRING"),
    c("tournament_id", "STRING", "REQUIRED"),
    c("fencer_a_id", "STRING"),
    c("fencer_b_id", "STRING"),
    c("fie_fencer_id_a", "STRING"),
    c("fie_fencer_id_b", "STRING"),
    c("winner_id", "STRING"),
    c("score_a", "INTEGER"),
    c("score_b", "INTEGER"),
    c("round", "STRING"),
    c("weapon", "STRING"),
    c("bout_date", "DATE"),
    c("metadata", "JSON"),
    c("updated_at", "TIMESTAMP"),
)

RANKING_SCHEMA = (
    c("id", "STRING"),
    c("fencer_id", "STRING"),
    c("fie_fencer_id", "STRING"),
    c("season", "INTEGER", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("gender", "STRING"),
    c("category", "STRING", "REQUIRED"),
    c("rank", "INTEGER", "REQUIRED"),
    c("points", "NUMERIC"),
    c("name", "STRING"),
    c("country", "STRING"),
    c("metadata", "JSON"),
    c("updated_at", "TIMESTAMP"),
)

COUNTRY_DEPTH_SCHEMA = (
    c("country", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("category", "STRING", "REQUIRED"),
    c("fencers_in_top16", "INTEGER", "REQUIRED"),
    c("fencers_in_top32", "INTEGER", "REQUIRED"),
    c("fencers_in_top64", "INTEGER", "REQUIRED"),
    c("total_ranked", "INTEGER", "REQUIRED"),
    c("avg_world_rank", "FLOAT", "REQUIRED"),
    c("updated_at", "TIMESTAMP"),
)

CLUB_RANKINGS_SCHEMA = (
    c("id", "STRING", "REQUIRED"),
    c("club", "STRING", "REQUIRED"),
    c("country", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("total_fencers", "INTEGER", "REQUIRED"),
    c("avg_rank", "FLOAT", "REQUIRED"),
    c("total_points", "FLOAT", "REQUIRED"),
    c("updated_at", "TIMESTAMP"),
)

CAREER_STATS_SCHEMA = (
    c("fencer_id", "STRING", "REQUIRED"),
    c("total_competitions", "INTEGER"),
    c("gold_medals", "INTEGER"),
    c("silver_medals", "INTEGER"),
    c("bronze_medals", "INTEGER"),
    c("top8_count", "INTEGER"),
    c("best_rank", "INTEGER"),
    c("avg_rank", "NUMERIC"),
    c("worst_rank", "INTEGER"),
    c("weapons_used", "JSON"),
    c("categories_competed", "JSON"),
    c("first_season", "STRING"),
    c("last_season", "STRING"),
    c("total_touches_scored", "INTEGER"),
    c("total_touches_received", "INTEGER"),
    c("touch_differential", "INTEGER"),
    c("updated_at", "TIMESTAMP"),
)

HEAD_TO_HEAD_SCHEMA = (
    c("fencer_a_id", "STRING", "REQUIRED"),
    c("fencer_b_id", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("a_wins", "INTEGER"),
    c("b_wins", "INTEGER"),
    c("a_touches", "INTEGER"),
    c("b_touches", "INTEGER"),
    c("bouts_total", "INTEGER"),
    c("last_meeting_date", "DATE"),
    c("last_winner_id", "STRING"),
    c("updated_at", "TIMESTAMP"),
)

RANKINGS_TRENDS_SCHEMA = (
    c("fencer_id", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("category", "STRING", "REQUIRED"),
    c("season", "INTEGER", "REQUIRED"),
    c("rank", "INTEGER", "REQUIRED"),
    c("previous_rank", "INTEGER"),
    c("rank_change", "INTEGER"),
    c("points", "NUMERIC"),
    c("previous_points", "NUMERIC"),
    c("points_change", "NUMERIC"),
    c("trend_direction", "STRING", "REQUIRED"),
    c("projected_next_rank", "INTEGER"),
    c("projected_next_points", "NUMERIC"),
    c("computed_at", "TIMESTAMP"),
)

COMPETITION_STRENGTH_SCHEMA = (
    c("tournament_id", "STRING", "REQUIRED"),
    c("avg_world_rank", "NUMERIC"),
    c("top8_count", "INTEGER", "REQUIRED"),
    c("top16_count", "INTEGER", "REQUIRED"),
    c("total_fie_ranked", "INTEGER", "REQUIRED"),
    c("strength_score", "NUMERIC"),
    c("updated_at", "TIMESTAMP"),
)

FENCER_SPECIALIZATION_SCHEMA = (
    c("fencer_id", "STRING", "REQUIRED"),
    c("classification", "STRING", "REQUIRED"),
    c("primary_weapon", "STRING"),
    c("weapons", "JSON", "REQUIRED"),
    c("total_results", "INTEGER", "REQUIRED"),
    c("total_competitions", "INTEGER", "REQUIRED"),
    c("ranked_results", "INTEGER", "REQUIRED"),
    c("avg_rank", "FLOAT"),
    c("best_rank", "INTEGER"),
    c("worst_rank", "INTEGER"),
    c("medal_count", "INTEGER", "REQUIRED"),
    c("medals_per_competition", "FLOAT"),
    c("per_weapon", "JSON", "REQUIRED"),
    c("season_primary_weapons", "JSON", "REQUIRED"),
    c("changed_primary_weapon", "BOOLEAN", "REQUIRED"),
    c("weapon_switches", "JSON", "REQUIRED"),
    c("categories", "JSON", "REQUIRED"),
    c("computed_at", "TIMESTAMP"),
)

FENCER_PERFORMANCE_SCHEMA = (
    c("fencer_id", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("competitions_count", "INTEGER", "REQUIRED"),
    c("avg_delta", "NUMERIC"),
    c("stddev_delta", "NUMERIC"),
    c("overperformance_rate", "NUMERIC"),
    c("clutch_score", "NUMERIC"),
    c("updated_at", "TIMESTAMP"),
)

FENCER_TRANSFERS_SCHEMA = (
    c("id", "STRING", "REQUIRED"),
    c("fencer_id", "STRING", "REQUIRED"),
    c("from_country", "STRING", "REQUIRED"),
    c("to_country", "STRING", "REQUIRED"),
    c("season", "STRING", "REQUIRED"),
    c("competition_id", "STRING"),
    c("source", "STRING", "REQUIRED"),
    c("confirmed", "BOOLEAN", "REQUIRED"),
    c("metadata", "JSON"),
)

NATIONAL_FED_RANKINGS_SCHEMA = (
    c("id", "STRING", "REQUIRED"),
    c("source", "STRING", "REQUIRED"),
    c("season", "STRING", "REQUIRED"),
    c("weapon", "STRING", "REQUIRED"),
    c("gender", "STRING", "REQUIRED"),
    c("category", "STRING", "REQUIRED"),
    c("rank", "INTEGER", "REQUIRED"),
    c("name", "STRING"),
    c("country", "STRING"),
    c("club", "STRING"),
    c("points", "NUMERIC"),
    c("fencer_id", "STRING"),
    c("fie_id", "STRING"),
    c("metadata", "JSON"),
    c("scraped_at", "TIMESTAMP"),
)

EXPORTS: dict[str, ExportConfig] = {
    "fencers": ExportConfig("fencers", "fs_fencers", "fs_fencers", FENCER_SCHEMA),
    "tournaments": ExportConfig(
        "tournaments", "fs_tournaments", "fs_tournaments", TOURNAMENT_SCHEMA
    ),
    "results": ExportConfig("results", "fs_results", "fs_results", RESULT_SCHEMA),
    "bouts": ExportConfig("bouts", "fs_bouts", "fs_bouts", BOUT_SCHEMA),
    "rankings": ExportConfig(
        "rankings", "fs_rankings_history", "fs_rankings_history", RANKING_SCHEMA
    ),
    "country_depth": ExportConfig(
        "country_depth", "fs_country_depth", "fs_country_depth", COUNTRY_DEPTH_SCHEMA
    ),
    "club_rankings": ExportConfig(
        "club_rankings", "fs_club_rankings", "fs_club_rankings", CLUB_RANKINGS_SCHEMA
    ),
    "career_stats": ExportConfig(
        "career_stats",
        "fs_fencer_career_stats",
        "fs_fencer_career_stats",
        CAREER_STATS_SCHEMA,
    ),
    "head_to_head": ExportConfig(
        "head_to_head", "fs_head_to_head", "fs_head_to_head", HEAD_TO_HEAD_SCHEMA
    ),
    "rankings_trends": ExportConfig(
        "rankings_trends",
        "fs_rankings_trends",
        "fs_rankings_trends",
        RANKINGS_TRENDS_SCHEMA,
    ),
    "competition_strength": ExportConfig(
        "competition_strength",
        "fs_competition_strength",
        "fs_competition_strength",
        COMPETITION_STRENGTH_SCHEMA,
    ),
    "fencer_specialization": ExportConfig(
        "fencer_specialization",
        "fs_fencer_specialization",
        "fs_fencer_specialization",
        FENCER_SPECIALIZATION_SCHEMA,
    ),
    "fencer_performance_analysis": ExportConfig(
        "fencer_performance_analysis",
        "fs_fencer_performance_analysis",
        "fs_fencer_performance_analysis",
        FENCER_PERFORMANCE_SCHEMA,
    ),
    "fencer_transfers": ExportConfig(
        "fencer_transfers",
        "fs_fencer_transfers",
        "fs_fencer_transfers",
        FENCER_TRANSFERS_SCHEMA,
    ),
    "national_fed_rankings": ExportConfig(
        "national_fed_rankings",
        "fs_national_fed_rankings",
        "fs_national_fed_rankings",
        NATIONAL_FED_RANKINGS_SCHEMA,
    ),
}

ANALYTICS_EXPORT_KEYS = tuple(
    key
    for key in EXPORTS
    if key
    not in {
        "fencers",
        "tournaments",
        "results",
        "bouts",
        "rankings",
    }
)


def schema_for(table_key: str) -> tuple[Column, ...]:
    return config_for(table_key).schema


def config_for(table_key: str) -> ExportConfig:
    try:
        return EXPORTS[table_key]
    except KeyError as exc:
        choices = ", ".join(sorted(EXPORTS))
        raise ValueError(f"Unsupported export table {table_key!r}; choose one of: {choices}") from exc


def _clean_optional(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _coerce_string(value: Any) -> str | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, datetime):
        return _coerce_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _coerce_integer(value: Any) -> int | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise RowValidationError(f"cannot coerce {value!r} to INTEGER") from exc


def _coerce_float(value: Any) -> float | None:
    value = _clean_optional(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RowValidationError(f"cannot coerce {value!r} to FLOAT") from exc


def _coerce_numeric(value: Any) -> str | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    try:
        return format(Decimal(str(value)), "f")
    except Exception as exc:
        raise RowValidationError(f"cannot coerce {value!r} to NUMERIC") from exc


def _coerce_boolean(value: Any) -> bool | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise RowValidationError(f"cannot coerce {value!r} to BOOLEAN")


def _coerce_date(value: Any) -> str | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return text


def _coerce_timestamp(value: Any) -> str | None:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime_time.min, tzinfo=timezone.utc).isoformat()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return text


def _coerce_json(value: Any) -> Any:
    value = _clean_optional(value)
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def coerce_value(value: Any, column: Column) -> Any:
    coerced: Any
    if column.bq_type == "STRING":
        coerced = _coerce_string(value)
    elif column.bq_type == "INTEGER":
        coerced = _coerce_integer(value)
    elif column.bq_type == "FLOAT":
        coerced = _coerce_float(value)
    elif column.bq_type == "NUMERIC":
        coerced = _coerce_numeric(value)
    elif column.bq_type == "BOOLEAN":
        coerced = _coerce_boolean(value)
    elif column.bq_type == "DATE":
        coerced = _coerce_date(value)
    elif column.bq_type == "TIMESTAMP":
        coerced = _coerce_timestamp(value)
    elif column.bq_type == "JSON":
        coerced = _coerce_json(value)
    else:
        raise RowValidationError(f"unsupported BigQuery type {column.bq_type!r}")

    if column.mode == "REQUIRED" and coerced is None:
        raise RowValidationError(f"{column.name} is required")
    return coerced


def build_payload(table_key: str, row: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in schema_for(table_key):
        payload[column.name] = coerce_value(row.get(column.name), column)
    return payload


def build_fencer_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_payload("fencers", row)


def build_tournament_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_payload("tournaments", row)


def build_result_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_payload("results", row)


def build_bout_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_payload("bouts", row)


def build_ranking_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_payload("rankings", row)


def build_analytics_payload(table_key: str, row: dict[str, Any]) -> dict[str, Any]:
    if table_key not in ANALYTICS_EXPORT_KEYS:
        raise ValueError(f"{table_key!r} is not an analytics export key")
    return build_payload(table_key, row)


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


class DryRunWriter:
    dry_run = True

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR, reason: str | None = None):
        self.output_dir = Path(output_dir)
        self.reason = reason

    def prepare_table(self, config: ExportConfig) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        schema_path = self.output_dir / f"{config.destination_table}.schema.json"
        schema_path.write_text(
            json.dumps([column.as_json() for column in config.schema], indent=2) + "\n"
        )

    def load_rows(
        self, config: ExportConfig, rows: list[dict[str, Any]], chunk_index: int
    ) -> int:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{config.destination_table}.chunk-{chunk_index:06d}.jsonl"
        with path.open("w") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")
        return len(rows)


class BigQueryWriter:
    dry_run = False

    def __init__(
        self,
        project: str,
        dataset: str,
        *,
        location: str | None = None,
        table_prefix: str = "",
    ):
        from google.cloud import bigquery

        self.bigquery = bigquery
        self.project = project
        self.dataset = dataset
        self.location = location
        self.table_prefix = table_prefix
        self.client = bigquery.Client(project=project, location=location)

    def table_name(self, config: ExportConfig) -> str:
        return f"{self.table_prefix}{config.destination_table}"

    def table_id(self, config: ExportConfig) -> str:
        return f"{self.project}.{self.dataset}.{self.table_name(config)}"

    def _schema_fields(self, config: ExportConfig):
        return [
            self.bigquery.SchemaField(column.name, column.bq_type, mode=column.mode)
            for column in config.schema
        ]

    def prepare_table(self, config: ExportConfig) -> None:
        dataset_ref = self.bigquery.Dataset(f"{self.project}.{self.dataset}")
        if self.location:
            dataset_ref.location = self.location
        self.client.create_dataset(dataset_ref, exists_ok=True)
        table = self.bigquery.Table(self.table_id(config), schema=self._schema_fields(config))
        self.client.create_table(table, exists_ok=True)

    def load_rows(
        self, config: ExportConfig, rows: list[dict[str, Any]], chunk_index: int
    ) -> int:
        job_config = self.bigquery.LoadJobConfig(
            schema=self._schema_fields(config),
            source_format=self.bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=False,
            write_disposition=(
                self.bigquery.WriteDisposition.WRITE_TRUNCATE
                if chunk_index == 1
                else self.bigquery.WriteDisposition.WRITE_APPEND
            ),
        )
        job = self.client.load_table_from_json(
            rows, self.table_id(config), job_config=job_config
        )
        job.result()
        return len(rows)


def build_writer(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
    force_cloud: bool = False,
) -> DryRunWriter | BigQueryWriter:
    project = os.environ.get("BIGQUERY_PROJECT")
    dataset = os.environ.get("BIGQUERY_DATASET")
    location = os.environ.get("BIGQUERY_LOCATION")
    table_prefix = os.environ.get("BIGQUERY_TABLE_PREFIX", "")

    if dry_run or not project or not dataset:
        if force_cloud and not dry_run:
            raise RuntimeError("BIGQUERY_PROJECT and BIGQUERY_DATASET must be set for cloud export")
        reason = None if dry_run else "BIGQUERY_PROJECT or BIGQUERY_DATASET is not set"
        return DryRunWriter(output_dir, reason=reason)

    try:
        return BigQueryWriter(
            project=project,
            dataset=dataset,
            location=location,
            table_prefix=table_prefix,
        )
    except Exception as exc:
        if force_cloud:
            raise
        return DryRunWriter(output_dir, reason=str(exc))


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def _load_rows_with_retry(
    writer: Any,
    config: ExportConfig,
    rows: list[dict[str, Any]],
    chunk_index: int,
    retries: int,
) -> int:
    max_attempts = max(1, retries + 1)
    for attempt in range(1, max_attempts + 1):
        try:
            return writer.load_rows(config, rows, chunk_index)
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(min(2 ** (attempt - 1), 30))
    raise RuntimeError("unreachable retry state")


def _record_progress(
    state_setter,
    config: ExportConfig,
    *,
    offset: int,
    rows_written: int,
    chunks: int,
    completed: bool,
) -> None:
    if not state_setter:
        return
    state_setter(
        SOURCE,
        f"progress:{config.source_table}",
        {
            "destination_table": config.destination_table,
            "offset": offset,
            "rows_written": rows_written,
            "chunks": chunks,
            "completed": completed,
        },
    )


def _resume_progress(state_getter, config: ExportConfig) -> dict[str, int]:
    progress = {"offset": 0, "rows_written": 0, "chunks": 0}
    if not state_getter:
        return progress
    state = state_getter(SOURCE, f"progress:{config.source_table}")
    if not isinstance(state, dict) or state.get("completed"):
        return progress
    for key in progress:
        try:
            progress[key] = max(0, int(state.get(key) or 0))
        except (TypeError, ValueError):
            progress[key] = 0
    return progress


def export_table(
    table_key: str,
    *,
    client=None,
    writer=None,
    page_size: int = DEFAULT_PAGE_SIZE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    retries: int = DEFAULT_RETRIES,
    update_state: bool = True,
    state_getter=get_state,
    state_setter=set_state,
    log_run: bool = True,
    resume: bool = False,
) -> dict[str, Any]:
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if retries < 0:
        raise ValueError("retries must not be negative")

    config = config_for(table_key)
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    rows_read = failed = skipped = 0
    resume_progress = _resume_progress(state_getter, config) if resume else {
        "offset": 0,
        "rows_written": 0,
        "chunks": 0,
    }
    start_offset = resume_progress["offset"]
    rows_written = resume_progress["rows_written"]
    chunks = resume_progress["chunks"]
    source_rows_consumed = 0
    chunk: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []

    try:
        client = client or get_supabase_client()
        writer = writer or build_writer()
        writer.prepare_table(config)

        offset = start_offset
        while True:
            page = (
                client.table(config.source_table)
                .select("*")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
                or []
            )
            if not page:
                break

            rows_read += len(page)
            for row in page:
                source_rows_consumed += 1
                try:
                    chunk.append(build_payload(config.key, row))
                except RowValidationError as exc:
                    skipped += 1
                    if len(validation_errors) < VALIDATION_DIAGNOSTIC_LIMIT:
                        validation_errors.append(
                            {
                                "source_offset": start_offset + source_rows_consumed - 1,
                                "row_id": row.get("id") or None,
                                "error": str(exc),
                            }
                        )
                    continue

                if len(chunk) >= chunk_size:
                    chunks += 1
                    rows_written += _load_rows_with_retry(
                        writer, config, chunk, chunks, retries
                    )
                    chunk = []
                    if update_state:
                        _record_progress(
                            state_setter,
                            config,
                            offset=start_offset + source_rows_consumed,
                            rows_written=rows_written,
                            chunks=chunks,
                            completed=False,
                        )

            if len(page) < page_size:
                break
            offset += page_size

        if chunk:
            chunks += 1
            rows_written += _load_rows_with_retry(writer, config, chunk, chunks, retries)
            if update_state:
                _record_progress(
                    state_setter,
                    config,
                    offset=start_offset + source_rows_consumed,
                    rows_written=rows_written,
                    chunks=chunks,
                    completed=False,
                )

        summary = {
            "table": config.key,
            "source_table": config.source_table,
            "destination_table": config.destination_table,
            "rows_read": rows_read,
            "rows_written": rows_written,
            "failed": failed,
            "skipped": skipped,
            "chunks": chunks,
            "dry_run": bool(getattr(writer, "dry_run", False)),
        }
        if validation_errors:
            summary["validation_errors"] = validation_errors
        if update_state:
            _record_progress(
                state_setter,
                config,
                offset=start_offset + source_rows_consumed,
                rows_written=rows_written,
                chunks=chunks,
                completed=True,
            )
        if run_log:
            run_log.complete(
                written=rows_written,
                failed=failed,
                skipped=skipped,
                metadata=summary,
            )
        return summary
    except Exception as exc:
        failed = 1
        if run_log:
            run_log.error(str(exc))
        raise


def export_tables(
    table_keys: list[str] | tuple[str, ...],
    *,
    client=None,
    writer=None,
    page_size: int = DEFAULT_PAGE_SIZE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    retries: int = DEFAULT_RETRIES,
    update_state: bool = True,
    log_run: bool = True,
    resume: bool = False,
) -> list[dict[str, Any]]:
    client = client or get_supabase_client()
    writer = writer or build_writer()
    summaries = []
    for table_key in table_keys:
        summaries.append(
            export_table(
                table_key,
                client=client,
                writer=writer,
                page_size=page_size,
                chunk_size=chunk_size,
                retries=retries,
                update_state=update_state,
                log_run=log_run,
                resume=resume,
            )
        )
    return summaries


def selected_tables(args) -> list[str]:
    if args.all:
        return list(EXPORTS)
    if args.analytics:
        return list(ANALYTICS_EXPORT_KEYS)
    if args.table:
        return args.table
    return ["fencers", "tournaments", "results", "bouts", "rankings"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export FenceSpace tables to BigQuery")
    parser.add_argument(
        "--table",
        action="append",
        choices=sorted(EXPORTS),
        help="Export one table key. Repeat for multiple tables.",
    )
    parser.add_argument("--analytics", action="store_true", help="Export analytics tables only.")
    parser.add_argument("--all", action="store_true", help="Export all configured tables.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--dry-run", action="store_true", help="Write local schema/JSONL only.")
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Require a BigQuery cloud writer instead of falling back to dry-run.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from saved fs_scraper_state offset.")
    parser.add_argument(
        "--no-state",
        action="store_true",
        help="Do not write fs_scraper_state progress records.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    writer = build_writer(
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        force_cloud=args.cloud,
    )
    client = get_supabase_client()
    summaries = export_tables(
        selected_tables(args),
        client=client,
        writer=writer,
        page_size=args.page_size,
        chunk_size=args.chunk_size,
        retries=args.retries,
        update_state=not args.no_state,
        resume=args.resume,
    )
    for summary in summaries:
        print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
