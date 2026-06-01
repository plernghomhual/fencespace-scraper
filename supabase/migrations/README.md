# Schema Migrations

SQL migrations live in this directory and are managed by `scripts/migrate.py`.

## Environment

Read-only commands (`list`, `dry-run`, `status`) use the Supabase API to read
`fs_schema_migrations`:

```bash
export SUPABASE_URL="https://..."
export SUPABASE_SERVICE_KEY="..."
```

`apply` also needs direct Postgres access through the local `psql` command:

```bash
export SUPABASE_DB_URL="postgresql://..."
```

`DATABASE_URL` is accepted as a fallback when `SUPABASE_DB_URL` is not set.

## Commands

List migrations and show applied state:

```bash
python scripts/migrate.py list
```

Preview pending migrations without applying SQL:

```bash
python scripts/migrate.py dry-run
```

Apply all pending migrations in filename order:

```bash
python scripts/migrate.py apply
```

Each file is passed to `psql` with `ON_ERROR_STOP=1` and `--single-transaction`.

Show the latest applied migration and pending count:

```bash
python scripts/migrate.py status
```

Generate a new dated migration:

```bash
python scripts/migrate.py generate --name add_table
```

This creates `YYYYMMDD_add_table.sql` using a small SQL template.

## Tracking Table

The CLI records successful and failed migration attempts in:

```sql
CREATE TABLE IF NOT EXISTS fs_schema_migrations (
    id serial PRIMARY KEY,
    filename text UNIQUE NOT NULL,
    applied_at timestamptz DEFAULT now(),
    hash text,
    success boolean DEFAULT true
);
```

`apply` creates the tracking table before running pending migration files.

## Hash Safety

Every applied file is tracked by SHA-256 hash. If an applied migration file is
edited later, `list`, `dry-run`, `status`, and `apply` report an error instead
of continuing. Add a new migration file for follow-up schema changes.

## Filename Rules

Generated migrations use `YYYYMMDD_description.sql`. Existing timestamped files
such as `YYYYMMDDHHMMSS_description.sql` are also listed and applied in
lexicographic filename order.
