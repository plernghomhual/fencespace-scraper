-- Core schema contract for fresh non-production rebuilds.
--
-- This migration is intentionally non-destructive. It creates the base tables
-- that later visible migrations assume already exist, plus the conflict targets
-- used by importer upserts. It is not a production data cleanup script; if a
-- live database has duplicate rows that violate these unique indexes, resolve
-- the duplicates in staging before applying this contract in production.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fie_id text,
    usafencing_id text,
    name text NOT NULL,
    country text,
    nationality text,
    weapon text,
    gender text,
    category text,
    world_rank integer,
    fie_points numeric,
    image_url text,
    club text,
    birth_date date,
    source text,
    source_id text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_fencer_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id uuid,
    canonical_name text,
    country text,
    fie_ids text[] NOT NULL DEFAULT '{}',
    fencer_ids text[] NOT NULL DEFAULT '{}',
    fs_fencer_row_ids uuid[] NOT NULL DEFAULT '{}',
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_tournaments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text,
    source_id text,
    name text NOT NULL,
    season integer,
    start_date date,
    end_date date,
    date date,
    country text,
    weapon text,
    gender text,
    category text,
    type text,
    competition_url_id text,
    source_url text,
    source_confidence text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fie_fencer_id integer,
    name text,
    country text,
    nationality text,
    rank integer,
    placement integer,
    medal text,
    points numeric,
    season integer,
    weapon text,
    gender text,
    category text,
    victory integer,
    matches integer,
    td integer,
    tr integer,
    diff integer,
    source text,
    source_id text,
    source_confidence text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_bouts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    fencer_a_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_b_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    winner_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_a text,
    fencer_b text,
    score_a integer,
    score_b integer,
    round text,
    bout_order integer,
    season integer,
    weapon text,
    gender text,
    category text,
    source text,
    source_id text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_rankings_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fie_fencer_id integer,
    name text,
    country text,
    rank integer,
    points numeric,
    season integer,
    weapon text,
    gender text,
    category text,
    ranking_date date,
    source text,
    source_id text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_scraper_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module text,
    source text,
    status text NOT NULL DEFAULT 'running',
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    written integer NOT NULL DEFAULT 0,
    failed integer NOT NULL DEFAULT 0,
    skipped integer NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_scraper_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    key text NOT NULL,
    value jsonb NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS fs_fencers_source_source_id_key
    ON public.fs_fencers (source, source_id)
    WHERE source IS NOT NULL AND source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_tournaments_source_id_key
    ON public.fs_tournaments (source_id)
    WHERE source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_tournaments_source_source_id_key
    ON public.fs_tournaments (source, source_id)
    WHERE source IS NOT NULL AND source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_results_tournament_name_key
    ON public.fs_results (tournament_id, name);

CREATE UNIQUE INDEX IF NOT EXISTS fs_results_tournament_fencer_key
    ON public.fs_results (tournament_id, fencer_id);

CREATE UNIQUE INDEX IF NOT EXISTS fs_results_source_id_key
    ON public.fs_results (source_id)
    WHERE source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_bouts_id_key
    ON public.fs_bouts (id);

CREATE UNIQUE INDEX IF NOT EXISTS fs_bouts_source_id_key
    ON public.fs_bouts (source_id)
    WHERE source_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_scraper_state_source_key_key
    ON public.fs_scraper_state (source, key);

CREATE INDEX IF NOT EXISTS fs_results_tournament_rank_idx
    ON public.fs_results (tournament_id, rank);

CREATE INDEX IF NOT EXISTS fs_bouts_tournament_idx
    ON public.fs_bouts (tournament_id);

CREATE INDEX IF NOT EXISTS fs_rankings_history_fencer_idx
    ON public.fs_rankings_history (fencer_id, season DESC);

ALTER TABLE public.fs_fencers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_tournaments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_bouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_rankings_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_scraper_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_scraper_state ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fencers FROM anon;
REVOKE ALL ON public.fs_fencer_identities FROM anon;
REVOKE ALL ON public.fs_tournaments FROM anon;
REVOKE ALL ON public.fs_results FROM anon;
REVOKE ALL ON public.fs_bouts FROM anon;
REVOKE ALL ON public.fs_rankings_history FROM anon;
REVOKE ALL ON public.fs_scraper_runs FROM anon;
REVOKE ALL ON public.fs_scraper_state FROM anon;
