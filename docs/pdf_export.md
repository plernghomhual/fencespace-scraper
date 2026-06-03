# Tournament Results PDF Export

`generate_tournament_pdf.py` creates a readable PDF for one tournament from existing
FenceSpace result tables.

## CLI

```bash
.venv/bin/python generate_tournament_pdf.py \
  00000000-0000-0000-0000-000000000114 \
  --output exports/grand-prix-seoul.pdf
```

Add a bout summary when `fs_bouts` rows are available:

```bash
.venv/bin/python generate_tournament_pdf.py \
  00000000-0000-0000-0000-000000000114 \
  --output exports/grand-prix-seoul.pdf \
  --include-bouts \
  --bout-limit 50
```

Use `--generated-at` for deterministic output in tests or reproducible exports:

```bash
.venv/bin/python generate_tournament_pdf.py \
  00000000-0000-0000-0000-000000000114 \
  --output exports/grand-prix-seoul.pdf \
  --generated-at 2026-06-02T14:30:00Z
```

## Data Sources

- `fs_tournaments`: tournament metadata, dates, location, weapon, gender, and links.
- `fs_competition_details`: optional format, entry count, countries, fees, and prize data.
- `fs_results`: required standings and medalists.
- `fs_bouts`: optional bout summary when `--include-bouts` is used.

The generator validates that the tournament ID is a UUID, fails if the tournament
or result rows are missing, and orders standings and bout summaries deterministically.

## Output Safety

The command writes only to the explicit `--output` path. The output directory must
already exist; the command does not create directories or write helper files.

## Environment

Set Supabase credentials before running:

```bash
export SUPABASE_URL="https://..."
export SUPABASE_SERVICE_KEY="..."
```

`SUPABASE_KEY` is accepted as a fallback for local export workflows.
