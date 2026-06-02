-- FenceSpace Supabase SQL Editor migration bundle
-- Generated from supabase/migrations with RLS migrations ordered last.
CREATE TABLE IF NOT EXISTS public.fs_schema_migrations (
    id serial PRIMARY KEY,
    filename text UNIQUE NOT NULL,
    applied_at timestamptz DEFAULT now(),
    hash text,
    success boolean DEFAULT true
);
ALTER TABLE public.fs_schema_migrations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.fs_schema_migrations FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.fs_schema_migrations FROM authenticated;
    END IF;
END $$;

-- BEGIN 20260601_name_variants.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_fencer_name_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL,
    name text NOT NULL,
    script text NOT NULL CHECK (script IN ('Latin', 'Hangul', 'Cyrillic', 'CJK', 'Arabic', 'Other')),
    source text NOT NULL,
    country text,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fencer_name_variants_unique
    ON fs_fencer_name_variants(fencer_id, name, script);

CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_fencer
    ON fs_fencer_name_variants(fencer_id);

CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_name
    ON fs_fencer_name_variants(name);
-- END 20260601_name_variants.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_name_variants.sql', now(), '4b1ace658ba18e60057b0b4b82a73bb2596709f025f2b983d1ef0d19ada6258f', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_news.sql
CREATE TABLE IF NOT EXISTS fs_articles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text UNIQUE NOT NULL,
    source text NOT NULL,
    source_site text NOT NULL,
    published_at timestamptz,
    category text NOT NULL CHECK (category IN ('competition_report', 'injury', 'transfer', 'rule_change', 'general')),
    summary text,
    related_fencer_ids uuid[],
    content_hash text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
-- END 20260601_news.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_news.sql', now(), 'dffb68fb29c883c2452426213f60503bb058e22b977b342f9ea0aac9754671d1', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_performance_analysis.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_performance_analysis (
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    weapon text NOT NULL,
    competitions_count integer NOT NULL DEFAULT 0 CHECK (competitions_count >= 0),
    avg_delta numeric(10,2),
    stddev_delta numeric(10,2),
    overperformance_rate numeric(5,2),
    clutch_score numeric(10,2),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_performance_analysis_unique
        UNIQUE (fencer_id, weapon)
);

ALTER TABLE public.fs_fencer_performance_analysis ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_performance_analysis_clutch_idx
    ON public.fs_fencer_performance_analysis (clutch_score DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_performance_analysis_updated_idx
    ON public.fs_fencer_performance_analysis (updated_at DESC);
-- END 20260601_performance_analysis.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_performance_analysis.sql', now(), 'f86f7a63bd45f207275f7a8db050e7e95de8320d939d35f21bf1a61323224a26', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_physical_stats.sql
ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS height integer,
    ADD COLUMN IF NOT EXISTS weight integer,
    ADD COLUMN IF NOT EXISTS reach integer;

COMMENT ON COLUMN public.fs_fencers.height IS 'Fencer height in centimeters, when available.';
COMMENT ON COLUMN public.fs_fencers.weight IS 'Fencer weight in kilograms, when available.';
COMMENT ON COLUMN public.fs_fencers.reach IS 'Fencer reach in centimeters, when available.';
-- END 20260601_physical_stats.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_physical_stats.sql', now(), '1ba1301fa5f791dee03aa958e336b52a66a940bb1017ce48364c596e330d0070', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_rankings_trends.sql
CREATE TABLE IF NOT EXISTS public.fs_rankings_trends (
    fencer_id             text NOT NULL,
    weapon                text NOT NULL,
    category              text NOT NULL,
    season                integer NOT NULL,
    rank                  integer NOT NULL,
    previous_rank         integer,
    rank_change           integer,
    points                numeric,
    previous_points       numeric,
    points_change         numeric,
    trend_direction       text NOT NULL,
    projected_next_rank   integer,
    projected_next_points numeric,
    computed_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_rankings_trends_pkey
        PRIMARY KEY (fencer_id, weapon, category, season),
    CONSTRAINT fs_rankings_trends_direction_check
        CHECK (trend_direction IN ('up', 'down', 'stable', 'new'))
);

COMMENT ON COLUMN public.fs_rankings_trends.fencer_id IS
    'FIE fencer identifier copied from fs_rankings_history.fie_fencer_id.';

CREATE INDEX IF NOT EXISTS fs_rankings_trends_direction_idx
    ON public.fs_rankings_trends (trend_direction, season);
-- END 20260601_rankings_trends.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_rankings_trends.sql', now(), '85ca683907eb70da27d14f4494dbf3e6770396ca923e8666dc3a39b0c087ed4a', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
