# BigQuery Export

`export_bigquery.py` exports FenceSpace Supabase tables into either BigQuery or local dry-run artifacts for data science workflows.

## Source Credentials

The exporter reads from Supabase:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

`SUPABASE_KEY` is accepted as a fallback for local tooling, but `SUPABASE_SERVICE_KEY` is preferred.

## BigQuery Credentials

Cloud export is optional. Without BigQuery configuration, the exporter automatically writes local dry-run files instead of attempting a cloud write.

Set these variables for BigQuery writes:

- `BIGQUERY_PROJECT`: Google Cloud project ID.
- `BIGQUERY_DATASET`: BigQuery dataset name.
- `GOOGLE_APPLICATION_CREDENTIALS`: path to a service-account JSON key, or use Application Default Credentials.

Optional:

- `BIGQUERY_LOCATION`: dataset/job location, such as `US`.
- `BIGQUERY_TABLE_PREFIX`: prefix applied to destination table names.

Use `--cloud` to require a cloud writer. If the Google SDK or credentials are unavailable, `--cloud` fails instead of falling back to dry-run.

## Dry-Run Export

Dry-run mode is safe without Google credentials and does not write to BigQuery:

```bash
.venv/bin/python export_bigquery.py --dry-run --output-dir bigquery_export
```

Dry-run mode writes:

- `<table>.schema.json`: BigQuery field schema with explicit type and mode.
- `<table>.chunk-000001.jsonl`: newline-delimited JSON payload rows.

When `BIGQUERY_PROJECT` or `BIGQUERY_DATASET` is missing, dry-run is selected automatically.

## Tables

Default export tables:

- `fs_fencers`
- `fs_tournaments`
- `fs_results`
- `fs_bouts`
- `fs_rankings_history`

Analytics tables:

- `fs_country_depth`
- `fs_club_rankings`
- `fs_fencer_career_stats`
- `fs_head_to_head`
- `fs_rankings_trends`
- `fs_competition_strength`
- `fs_fencer_specialization`
- `fs_fencer_performance_analysis`
- `fs_fencer_transfers`
- `fs_national_fed_rankings`

Run only analytics:

```bash
.venv/bin/python export_bigquery.py --analytics --dry-run
```

Run one table:

```bash
.venv/bin/python export_bigquery.py --table fencers --dry-run
```

Run all configured tables:

```bash
.venv/bin/python export_bigquery.py --all --dry-run
```

## Dataset And Table Naming

BigQuery destination is:

```text
<BIGQUERY_PROJECT>.<BIGQUERY_DATASET>.<BIGQUERY_TABLE_PREFIX><source_table>
```

By default, destination table names match Supabase table names, for example:

```text
fencespace-analytics.ds_exports.fs_fencers
```

With `BIGQUERY_TABLE_PREFIX=staging_`, the destination becomes:

```text
fencespace-analytics.ds_exports.staging_fs_fencers
```

## Chunking And State

The exporter pages Supabase with `.range()` and writes one export chunk at a time. It does not load an entire source table into memory.

Defaults:

- `--page-size 1000`
- `--chunk-size 5000`
- `--retries 2`

Progress is recorded in `fs_scraper_state` under keys like:

```text
source = export_bigquery
key = progress:fs_fencers
```

Each progress value stores destination table, source offset, rows written, chunk count, and completion status. Use `--resume` to resume an incomplete table from the saved offset. Use `--no-state` for local tests or one-off runs that should not write state.

## Schema And Nullable Handling

Schemas are explicit in `export_bigquery.py`. Payload builders project source rows into a stable column list and coerce BigQuery types:

- UUIDs and IDs become `STRING`.
- Numeric analytics values become `NUMERIC`.
- Counts and ranks become `INTEGER`.
- Dates and timestamps are normalized to ISO strings.
- JSON metadata stays JSON when possible.
- Missing nullable fields are exported as `null`.

Rows missing required identifier or key fields are skipped instead of causing the full table export to fail.
