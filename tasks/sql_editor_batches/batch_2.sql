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

-- BEGIN 20260601_career_stats.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_career_stats (
    fencer_id uuid PRIMARY KEY REFERENCES public.fs_fencers(id),
    total_competitions integer DEFAULT 0,
    gold_medals integer DEFAULT 0,
    silver_medals integer DEFAULT 0,
    bronze_medals integer DEFAULT 0,
    top8_count integer DEFAULT 0,
    best_rank integer,
    avg_rank numeric(5,2),
    worst_rank integer,
    weapons_used jsonb,
    categories_competed jsonb,
    first_season text,
    last_season text,
    total_touches_scored integer DEFAULT 0,
    total_touches_received integer DEFAULT 0,
    touch_differential integer DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE public.fs_fencer_career_stats ENABLE ROW LEVEL SECURITY;
-- END 20260601_career_stats.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_career_stats.sql', now(), '1d094b680478685b2ebed087376b491a39f78b8684ccff7a16fc84e171590ae3', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_club_reviews.sql
CREATE TABLE IF NOT EXISTS public.fs_club_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_name text NOT NULL,
    normalized_club_name text NOT NULL,
    city text NOT NULL,
    country text NOT NULL,
    source text NOT NULL,
    rating numeric,
    review_count integer,
    review_summary text,
    source_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_club_reviews_rating_check
        CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT fs_club_reviews_review_count_check
        CHECK (review_count IS NULL OR review_count >= 0),
    CONSTRAINT fs_club_reviews_unique_source
        UNIQUE (normalized_club_name, city, country, source)
);

CREATE INDEX IF NOT EXISTS fs_club_reviews_lookup_idx
    ON public.fs_club_reviews (normalized_club_name, city, country);

CREATE INDEX IF NOT EXISTS fs_club_reviews_source_idx
    ON public.fs_club_reviews (source, scraped_at DESC);
-- END 20260601_club_reviews.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_club_reviews.sql', now(), '7fdc20f396171f6eca6bb3d9b9e5bdb5a7d947ecabdb47fed96350f8a2d1bdb7', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_competition_details.sql
CREATE TABLE IF NOT EXISTS public.fs_competition_details (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid UNIQUE REFERENCES public.fs_tournaments(id),
    format_type text,
    pool_size integer,
    de_rounds integer,
    entry_fee numeric,
    prize_pool numeric,
    currency text,
    participant_count integer,
    countries_represented integer,
    metadata jsonb DEFAULT '{}'::jsonb,
    scraped_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fs_competition_details_tournament_id_idx
    ON public.fs_competition_details (tournament_id);
-- END 20260601_competition_details.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_competition_details.sql', now(), '18c2914e9858fd5be7fa363eb05555945cc3604d33767052d4bc4921379e3327', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_coverage_views.sql
DROP FUNCTION IF EXISTS public.refresh_data_quality_views();
DROP MATERIALIZED VIEW IF EXISTS public.v_stale_sources;
DROP MATERIALIZED VIEW IF EXISTS public.v_orphan_results;
DROP MATERIALIZED VIEW IF EXISTS public.v_scraper_health;
DROP MATERIALIZED VIEW IF EXISTS public.v_fencer_source_coverage;

CREATE MATERIALIZED VIEW public.v_fencer_source_coverage AS
SELECT
    'fs_fencers'::text AS source_name,
    COUNT(*)::bigint AS fencer_count
FROM public.fs_fencers
UNION ALL
SELECT
    'fs_national_fed_rankings'::text AS source_name,
    COUNT(DISTINCT COALESCE(
        fencer_id::text,
        NULLIF(fie_id, ''),
        NULLIF(
            lower(trim(COALESCE(name, '') || ':' || COALESCE(country, ''))),
            ':'
        )
    ))::bigint AS fencer_count
FROM public.fs_national_fed_rankings
UNION ALL
SELECT
    'fs_results_linked'::text AS source_name,
    COUNT(DISTINCT fencer_id)::bigint AS fencer_count
FROM public.fs_results
WHERE fencer_id IS NOT NULL;

CREATE UNIQUE INDEX v_fencer_source_coverage_source_name_idx
    ON public.v_fencer_source_coverage (source_name);

CREATE MATERIALIZED VIEW public.v_scraper_health AS
SELECT
    module,
    status,
    started_at,
    completed_at,
    COALESCE(written, 0) AS written,
    COALESCE(failed, 0) AS failed,
    COALESCE(skipped, 0) AS skipped
FROM public.fs_scraper_runs
WHERE started_at >= now() - interval '7 days';

CREATE INDEX v_scraper_health_module_started_idx
    ON public.v_scraper_health (module, started_at DESC);

CREATE MATERIALIZED VIEW public.v_orphan_results AS
SELECT
    COALESCE(t.type, 'unknown')::text AS tournament_type,
    COUNT(*)::bigint AS orphan_count
FROM public.fs_results r
LEFT JOIN public.fs_tournaments t
    ON t.id = r.tournament_id
WHERE r.fencer_id IS NULL
GROUP BY COALESCE(t.type, 'unknown');

CREATE UNIQUE INDEX v_orphan_results_tournament_type_idx
    ON public.v_orphan_results (tournament_type);

CREATE MATERIALIZED VIEW public.v_stale_sources AS
WITH last_success AS (
    SELECT
        module,
        MAX(completed_at) AS last_run
    FROM public.fs_scraper_runs
    WHERE status = 'completed'
      AND completed_at IS NOT NULL
    GROUP BY module
)
SELECT
    module,
    last_run
FROM last_success
WHERE last_run < now() - interval '48 hours';

CREATE UNIQUE INDEX v_stale_sources_module_idx
    ON public.v_stale_sources (module);

GRANT SELECT ON public.fs_fencers TO service_role;
GRANT SELECT ON public.fs_national_fed_rankings TO service_role;
GRANT SELECT ON public.fs_results TO service_role;
GRANT SELECT ON public.fs_tournaments TO service_role;
GRANT SELECT ON public.fs_scraper_runs TO service_role;

ALTER MATERIALIZED VIEW public.v_fencer_source_coverage OWNER TO service_role;
ALTER MATERIALIZED VIEW public.v_scraper_health OWNER TO service_role;
ALTER MATERIALIZED VIEW public.v_orphan_results OWNER TO service_role;
ALTER MATERIALIZED VIEW public.v_stale_sources OWNER TO service_role;

CREATE OR REPLACE FUNCTION public.refresh_data_quality_views()
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW public.v_fencer_source_coverage;
    REFRESH MATERIALIZED VIEW public.v_scraper_health;
    REFRESH MATERIALIZED VIEW public.v_orphan_results;
    REFRESH MATERIALIZED VIEW public.v_stale_sources;
END;
$$;

REVOKE ALL ON FUNCTION public.refresh_data_quality_views() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.refresh_data_quality_views() FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_data_quality_views() TO service_role;

REVOKE ALL ON public.v_fencer_source_coverage FROM anon, authenticated;
REVOKE ALL ON public.v_scraper_health FROM anon, authenticated;
REVOKE ALL ON public.v_orphan_results FROM anon, authenticated;
REVOKE ALL ON public.v_stale_sources FROM anon, authenticated;

GRANT SELECT ON public.v_fencer_source_coverage TO service_role;
GRANT SELECT ON public.v_scraper_health TO service_role;
GRANT SELECT ON public.v_orphan_results TO service_role;
GRANT SELECT ON public.v_stale_sources TO service_role;
-- END 20260601_coverage_views.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_coverage_views.sql', now(), 'c37e768972a7e8e046f5b515af95de286842cab67b97f79c6af69efe68101a1b', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_equipment.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_equipment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES public.fs_fencers(id),
    brand text NOT NULL,
    equipment_type text,
    sponsor_name text,
    source text,
    source_url text,
    confidence text DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_fencer_id_idx
    ON public.fs_fencer_equipment (fencer_id);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_brand_idx
    ON public.fs_fencer_equipment (brand);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_source_idx
    ON public.fs_fencer_equipment (source);
-- END 20260601_equipment.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_equipment.sql', now(), '871911a45fee02cd40dc1200a8d8de0da5ab4018ae27339ac32a1a9a51c4de72', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
