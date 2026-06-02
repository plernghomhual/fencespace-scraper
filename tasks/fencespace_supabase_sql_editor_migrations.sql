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

-- BEGIN 20260529_national_fed_rankings.sql
CREATE TABLE IF NOT EXISTS fs_national_fed_rankings (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source      text NOT NULL,
    season      text NOT NULL,
    weapon      text NOT NULL,
    gender      text NOT NULL,
    category    text NOT NULL,
    rank        integer NOT NULL,
    name        text,
    country     text,
    club        text,
    points      numeric,
    fencer_id   uuid REFERENCES fs_fencers(id),
    fie_id      text,
    metadata    jsonb NOT NULL DEFAULT '{}',
    scraped_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_national_fed_rankings_unique
        UNIQUE (source, season, weapon, gender, category, rank)
);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_source_idx
    ON fs_national_fed_rankings (source, season);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_fencer_idx
    ON fs_national_fed_rankings (fencer_id)
    WHERE fencer_id IS NOT NULL;
-- END 20260529_national_fed_rankings.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260529_national_fed_rankings.sql', now(), '53c7980c650cf61c40ab7bb70253a377012a9de318487c5a49f61a8b43d67ce6', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601032714_country_club_rankings.sql
CREATE TABLE IF NOT EXISTS public.fs_country_depth (
    country             text NOT NULL,
    weapon              text NOT NULL,
    category            text NOT NULL,
    fencers_in_top16    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top16 >= 0),
    fencers_in_top32    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top32 >= 0),
    fencers_in_top64    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top64 >= 0),
    total_ranked        integer NOT NULL DEFAULT 0 CHECK (total_ranked >= 0),
    avg_world_rank      double precision NOT NULL DEFAULT 0,
    updated_at          timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    PRIMARY KEY (country, weapon, category),
    CHECK (fencers_in_top16 <= fencers_in_top32),
    CHECK (fencers_in_top32 <= fencers_in_top64),
    CHECK (fencers_in_top64 <= total_ranked)
);

CREATE INDEX IF NOT EXISTS fs_country_depth_weapon_category_idx
    ON public.fs_country_depth (weapon, category);

CREATE INDEX IF NOT EXISTS fs_country_depth_top64_idx
    ON public.fs_country_depth (weapon, category, fencers_in_top64 DESC);

ALTER TABLE public.fs_country_depth ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.fs_club_rankings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club            text NOT NULL,
    country         text NOT NULL,
    weapon          text NOT NULL,
    total_fencers   integer NOT NULL DEFAULT 0 CHECK (total_fencers >= 0),
    avg_rank        double precision NOT NULL DEFAULT 0,
    total_points    double precision NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_club_rankings_unique UNIQUE (club, country, weapon)
);

CREATE INDEX IF NOT EXISTS fs_club_rankings_country_weapon_idx
    ON public.fs_club_rankings (country, weapon);

CREATE INDEX IF NOT EXISTS fs_club_rankings_points_idx
    ON public.fs_club_rankings (weapon, total_points DESC, avg_rank ASC);

ALTER TABLE public.fs_club_rankings ENABLE ROW LEVEL SECURITY;
-- END 20260601032714_country_club_rankings.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601032714_country_club_rankings.sql', now(), '3966a60d3d56bd9d8b4b1ae1e48f3280f9c5047198cf0ad584e222ec855a26eb', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601033334_wikipedia_bios.sql
ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS bio_text text,
    ADD COLUMN IF NOT EXISTS wikipedia_url text,
    ADD COLUMN IF NOT EXISTS birth_place text,
    ADD COLUMN IF NOT EXISTS nickname text,
    ADD COLUMN IF NOT EXISTS height text,
    ADD COLUMN IF NOT EXISTS weight text;
-- END 20260601033334_wikipedia_bios.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601033334_wikipedia_bios.sql', now(), '115a51bd3860fc1fa0ea91ee7abc931b4138d0f39252bf9ff649a9008d5114cd', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_api_keys.sql
-- API key table for fs_api.py authentication.
-- Read by service_role only (RLS enabled, no authenticated policy).

CREATE TABLE IF NOT EXISTS public.fs_api_keys (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text        NOT NULL UNIQUE,
    name        text,
    active      boolean     NOT NULL DEFAULT true,
    revoked     boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_api_keys ENABLE ROW LEVEL SECURITY;

-- No SELECT policy for authenticated/anon — service_role bypasses RLS.
REVOKE ALL ON public.fs_api_keys FROM anon, authenticated;
-- END 20260601_api_keys.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_api_keys.sql', now(), '0d414672314ff94ad30cf73332f1b4b5ea40a1aacfbbc51eaa29e9872ce47779', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_camps.sql
CREATE TABLE IF NOT EXISTS public.fs_training_camps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organizer text,
    city text,
    country text,
    start_date date,
    end_date date,
    coaches text[],
    cost numeric,
    currency text DEFAULT 'USD',
    weapons_covered text[],
    max_participants integer,
    source_url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (name, organizer, start_date, end_date),
    CONSTRAINT fs_training_camps_date_order CHECK (
        start_date IS NULL OR end_date IS NULL OR end_date >= start_date
    )
);

ALTER TABLE public.fs_training_camps ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_dates
    ON public.fs_training_camps (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_location
    ON public.fs_training_camps (country, city);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_weapons
    ON public.fs_training_camps USING gin (weapons_covered);
-- END 20260601_camps.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_camps.sql', now(), '9369f1d95cd26ccc602de8a80788124c90158bc16e4f412f4650cc0417cf2792', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

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

-- BEGIN 20260601_equipment_reviews.sql
CREATE TABLE IF NOT EXISTS public.fs_equipment_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name text NOT NULL,
    brand text NOT NULL,
    category text,
    rating numeric(3,1),
    review_count integer,
    price numeric,
    currency text DEFAULT 'USD',
    source text,
    url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    CONSTRAINT fs_equipment_reviews_url_unique UNIQUE (url),
    CONSTRAINT fs_equipment_reviews_rating_check
        CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT fs_equipment_reviews_review_count_check
        CHECK (review_count IS NULL OR review_count >= 0),
    CONSTRAINT fs_equipment_reviews_price_check
        CHECK (price IS NULL OR price >= 0)
);

ALTER TABLE public.fs_equipment_reviews ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_reviews TO service_role;

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_source_idx
    ON public.fs_equipment_reviews (source, scraped_at DESC);

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_brand_category_idx
    ON public.fs_equipment_reviews (brand, category);
-- END 20260601_equipment_reviews.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_equipment_reviews.sql', now(), 'e22f12efcdad2a23d69e3b6b2ab84ba3c1d2e94f38c1f7d62147be408df0faf6', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_fencer_identities.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- fs_fencers.fie_id stores FIE's external athlete identifier as text/numeric
-- data, while fs_fencers.id is the Supabase UUID row identifier.
CREATE TABLE IF NOT EXISTS fs_fencer_identities (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name     text,
    country            text,
    fie_ids            text[] NOT NULL DEFAULT '{}',
    fs_fencer_row_ids  uuid[] NOT NULL DEFAULT '{}',
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_identities_has_rows
        CHECK (cardinality(fs_fencer_row_ids) > 0)
);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_country_idx
    ON fs_fencer_identities (country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_identities_fie_ids_idx
    ON fs_fencer_identities USING gin (fie_ids);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_row_ids_idx
    ON fs_fencer_identities USING gin (fs_fencer_row_ids);
-- END 20260601_fencer_identities.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_fencer_identities.sql', now(), 'cb2d3960a9dbe7483121d66557c59fb1889223ee6bcebe287f264a595dc2f705', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_head_to_head.sql
CREATE TABLE IF NOT EXISTS public.fs_head_to_head (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_a_id uuid REFERENCES public.fs_fencers(id),
    fencer_b_id uuid REFERENCES public.fs_fencers(id),
    weapon text NOT NULL,
    a_wins integer DEFAULT 0,
    b_wins integer DEFAULT 0,
    a_touches integer DEFAULT 0,
    b_touches integer DEFAULT 0,
    bouts_total integer DEFAULT 0,
    last_meeting_date date,
    last_winner_id uuid REFERENCES public.fs_fencers(id),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (fencer_a_id, fencer_b_id, weapon)
);
-- END 20260601_head_to_head.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_head_to_head.sql', now(), '8f763ce48a7da80682cba661487729ddd2cba6f789672b8c0d4655e20a96e892', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_longevity.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_longevity (
    fencer_id uuid PRIMARY KEY REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    first_competition_date date,
    last_competition_date date,
    first_season integer,
    last_season integer,
    career_years integer,
    competitions_per_season numeric(8,2),
    status text NOT NULL DEFAULT 'unknown',
    updated_at timestamptz DEFAULT now(),
    CHECK (career_years IS NULL OR career_years >= 0),
    CHECK (competitions_per_season IS NULL OR competitions_per_season >= 0),
    CHECK (status IN ('active', 'likely_retired', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_status
    ON public.fs_fencer_longevity(status);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_last_competition
    ON public.fs_fencer_longevity(last_competition_date);

ALTER TABLE public.fs_fencer_longevity ENABLE ROW LEVEL SECURITY;
-- END 20260601_longevity.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_longevity.sql', now(), '79916553336ac34dc21e0f35bfc564e546f08b2d90e910f3f0061bcfb8ce00a1', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_medal_tables.sql
CREATE TABLE IF NOT EXISTS public.fs_medal_tables (
    id text PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN ('country', 'fencer', 'tier_country')),
    country text,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    tier text CHECK (tier IS NULL OR tier IN ('Olympics', 'Worlds', 'GP', 'WC', 'Continental')),
    gold integer NOT NULL DEFAULT 0 CHECK (gold >= 0),
    silver integer NOT NULL DEFAULT 0 CHECK (silver >= 0),
    bronze integer NOT NULL DEFAULT 0 CHECK (bronze >= 0),
    total integer NOT NULL DEFAULT 0 CHECK (total >= 0 AND total = gold + silver + bronze),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_medal_tables_scope_fields CHECK (
        (
            scope = 'country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NULL
        )
        OR (
            scope = 'fencer'
            AND country IS NULL
            AND fencer_id IS NOT NULL
            AND tier IS NULL
        )
        OR (
            scope = 'tier_country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_scope_total
    ON public.fs_medal_tables(scope, total DESC);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_country
    ON public.fs_medal_tables(country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_fencer_id
    ON public.fs_medal_tables(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_tier_country
    ON public.fs_medal_tables(tier, country)
    WHERE tier IS NOT NULL;

ALTER TABLE public.fs_medal_tables ENABLE ROW LEVEL SECURITY;
-- END 20260601_medal_tables.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_medal_tables.sql', now(), 'f7fd559b4cc1312145c60544aa90cf4bdd2e11cdf42325897a12558f98305d9d', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

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

-- BEGIN 20260601_referees.sql
CREATE TABLE IF NOT EXISTS fs_referees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    fie_license_id text UNIQUE,
    category text,
    certification_level text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fs_coaches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    federation text,
    national_team_role text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fs_fencer_coach_relationship (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    coach_id uuid REFERENCES fs_coaches(id),
    start_date date,
    end_date date,
    current boolean DEFAULT true,
    metadata jsonb DEFAULT '{}',
    UNIQUE (fencer_id, coach_id)
);

CREATE INDEX IF NOT EXISTS fs_referees_country_idx
    ON fs_referees (country);

CREATE INDEX IF NOT EXISTS fs_referees_weapons_idx
    ON fs_referees USING gin (weapons);

CREATE INDEX IF NOT EXISTS fs_coaches_country_idx
    ON fs_coaches (country);

CREATE INDEX IF NOT EXISTS fs_coaches_federation_idx
    ON fs_coaches (federation);

CREATE INDEX IF NOT EXISTS fs_coaches_weapons_idx
    ON fs_coaches USING gin (weapons);

CREATE INDEX IF NOT EXISTS fs_fencer_coach_relationship_fencer_idx
    ON fs_fencer_coach_relationship (fencer_id);

CREATE INDEX IF NOT EXISTS fs_fencer_coach_relationship_coach_idx
    ON fs_fencer_coach_relationship (coach_id);
-- END 20260601_referees.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_referees.sql', now(), '5776b7939b3e45b81b501828c0bf951c2c481da990e503a0eba8338674c680f5', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_scholarships.sql
CREATE TABLE IF NOT EXISTS public.fs_college_scholarships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    college_name text NOT NULL,
    division text,
    conference text,
    weapons text[],
    gender_teams text[],
    roster_size integer,
    scholarship_slots integer,
    head_coach text,
    coach_email text,
    website text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (college_name)
);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_division_idx
    ON public.fs_college_scholarships (division);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_scraped_at_idx
    ON public.fs_college_scholarships (scraped_at);
-- END 20260601_scholarships.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_scholarships.sql', now(), '2b8388e27006c6e49b292229d40c18c301607a5f3b83e0a59fdd9370ef9068a2', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_social_media.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_fencer_social_media (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    platform text NOT NULL CHECK (platform IN ('instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')),
    handle text,
    url text NOT NULL,
    source text DEFAULT 'wikidata',
    verified boolean DEFAULT false,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    UNIQUE (fencer_id, platform)
);

CREATE INDEX IF NOT EXISTS fs_fencer_social_media_fencer_idx
    ON fs_fencer_social_media (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_social_media_platform_idx
    ON fs_fencer_social_media (platform);
-- END 20260601_social_media.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_social_media.sql', now(), 'af32ab25a70ad246d33a2c746724e0fefb3fbfc5d9852fd65b4769a6a6fc79c3', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_specialization.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_specialization (
    fencer_id               text            NOT NULL PRIMARY KEY,
    classification          text            NOT NULL,
    primary_weapon          text,
    weapons                 jsonb           NOT NULL DEFAULT '[]',
    total_results           integer         NOT NULL DEFAULT 0,
    total_competitions      integer         NOT NULL DEFAULT 0,
    ranked_results          integer         NOT NULL DEFAULT 0,
    avg_rank                double precision,
    best_rank               integer,
    worst_rank              integer,
    medal_count             integer         NOT NULL DEFAULT 0,
    medals_per_competition  double precision,
    per_weapon              jsonb           NOT NULL DEFAULT '{}',
    season_primary_weapons  jsonb           NOT NULL DEFAULT '{}',
    changed_primary_weapon  boolean         NOT NULL DEFAULT false,
    weapon_switches         jsonb           NOT NULL DEFAULT '[]',
    categories              jsonb           NOT NULL DEFAULT '[]',
    computed_at             timestamptz     NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_fencer_specialization ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fencer_specialization FROM anon, authenticated;
GRANT SELECT ON public.fs_fencer_specialization TO authenticated;

DROP POLICY IF EXISTS subscriber_fencer_specialization_read ON public.fs_fencer_specialization;
CREATE POLICY subscriber_fencer_specialization_read ON public.fs_fencer_specialization
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
-- END 20260601_specialization.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_specialization.sql', now(), 'dd23fea49ee564c4d90a67b982cfd40bedb5ce1033b5e61f6a15d7880f056b76', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_strength_of_field.sql
CREATE TABLE IF NOT EXISTS public.fs_competition_strength (
    tournament_id uuid PRIMARY KEY REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    avg_world_rank numeric,
    top8_count integer NOT NULL DEFAULT 0 CHECK (top8_count >= 0),
    top16_count integer NOT NULL DEFAULT 0 CHECK (top16_count >= 0),
    total_fie_ranked integer NOT NULL DEFAULT 0 CHECK (total_fie_ranked >= 0),
    strength_score numeric,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (top8_count <= top16_count),
    CHECK (top16_count <= total_fie_ranked)
);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_score
ON public.fs_competition_strength (strength_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_avg_rank
ON public.fs_competition_strength (avg_world_rank ASC NULLS LAST);
-- END 20260601_strength_of_field.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_strength_of_field.sql', now(), '6b739aaa3649e6cb9c3406450b0c8d19e10771916fb62ce9eb77d51a61713704', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_transfers.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_transfers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id      uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    from_country   text NOT NULL,
    to_country     text NOT NULL,
    season         text NOT NULL,
    competition_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    source         text NOT NULL,
    confirmed      boolean NOT NULL DEFAULT false,
    metadata       jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fs_fencer_transfers_country_changed
        CHECK (from_country <> to_country)
);

ALTER TABLE public.fs_fencer_transfers ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_fencer_season_idx
    ON public.fs_fencer_transfers (fencer_id, season);

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_confirmed_idx
    ON public.fs_fencer_transfers (confirmed);

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_competition_idx
    ON public.fs_fencer_transfers (competition_id)
    WHERE competition_id IS NOT NULL;
-- END 20260601_transfers.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_transfers.sql', now(), 'd6dc7d4fb10d6fd8cb9ed066e99dafc232a32a8adcc6d75e14d7ece253227738', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_venues.sql
CREATE TABLE IF NOT EXISTS public.fs_venues (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name               text NOT NULL,
    city               text NOT NULL,
    country            text NOT NULL,
    latitude           double precision CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude          double precision CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    country_code       text,
    competitions_count integer NOT NULL DEFAULT 0 CHECK (competitions_count >= 0),
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_venues_unique UNIQUE (name, city, country)
);

CREATE INDEX IF NOT EXISTS fs_venues_city_country_idx
    ON public.fs_venues (city, country);

CREATE INDEX IF NOT EXISTS fs_venues_country_code_idx
    ON public.fs_venues (country_code)
    WHERE country_code IS NOT NULL;
-- END 20260601_venues.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_venues.sql', now(), '57408c8233187f1b6104c0ee3aefd32f6d606f9a2ef342c1f1e53dc9b5df5db9', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260602_fred_result_dedup.sql
-- Dedup index for FRED/AskFRED result rows where fie_fencer_id is NULL.
-- These scrapers use (tournament_id, name) as the natural key since fencers
-- are matched by USA Fencing ID or name but fie_fencer_id is not populated.
-- This prevents duplicate rows from multi-run incremental scraping.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fs_results_tournament_name_nofieid
    ON public.fs_results (tournament_id, lower(name))
    WHERE fie_fencer_id IS NULL
      AND metadata ? 'fred_fencer_key';
-- END 20260602_fred_result_dedup.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260602_fred_result_dedup.sql', now(), 'caa8771cfcb600f462ec806c2beb4bcb467e5764016738420c00c52dc2c38a4e', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_rls_agent_tables.sql
-- RLS for all agent-created tables not covered by 20260601_rls_policies.sql.
-- Pattern mirrors the base RLS migration: subscriber JWT required for SELECT.

-- ── Enable RLS ──────────────────────────────────────────────────────────────

ALTER TABLE public.fs_fencer_career_stats          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_rankings_trends              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_venues                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_medal_tables                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_competition_strength         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_transfers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_longevity             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_performance_analysis  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_name_variants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_social_media          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_competition_details          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_country_depth                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_club_rankings                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_equipment             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_training_camps               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_college_scholarships         ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_articles                            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_referees                            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_coaches                             ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_fencer_coach_relationship           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_club_reviews                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_equipment_reviews            ENABLE ROW LEVEL SECURITY;
-- Internal dedup table — enable RLS, no read policy (service_role only)
ALTER TABLE fs_fencer_identities                   ENABLE ROW LEVEL SECURITY;

-- ── Revoke defaults ─────────────────────────────────────────────────────────

REVOKE ALL ON public.fs_fencer_career_stats         FROM anon, authenticated;
REVOKE ALL ON public.fs_rankings_trends             FROM anon, authenticated;
REVOKE ALL ON public.fs_venues                      FROM anon, authenticated;
REVOKE ALL ON public.fs_medal_tables                FROM anon, authenticated;
REVOKE ALL ON public.fs_competition_strength        FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_transfers            FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_longevity            FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_performance_analysis FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_name_variants        FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_social_media         FROM anon, authenticated;
REVOKE ALL ON public.fs_competition_details         FROM anon, authenticated;
REVOKE ALL ON public.fs_country_depth               FROM anon, authenticated;
REVOKE ALL ON public.fs_club_rankings               FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_equipment            FROM anon, authenticated;
REVOKE ALL ON public.fs_training_camps              FROM anon, authenticated;
REVOKE ALL ON public.fs_college_scholarships        FROM anon, authenticated;
REVOKE ALL ON fs_articles                           FROM anon, authenticated;
REVOKE ALL ON fs_referees                           FROM anon, authenticated;
REVOKE ALL ON fs_coaches                            FROM anon, authenticated;
REVOKE ALL ON fs_fencer_coach_relationship          FROM anon, authenticated;
REVOKE ALL ON public.fs_club_reviews                FROM anon, authenticated;
REVOKE ALL ON public.fs_equipment_reviews           FROM anon, authenticated;
REVOKE ALL ON fs_fencer_identities                  FROM anon, authenticated;

-- ── Grant SELECT to authenticated (RLS policies enforce subscriber check) ───

GRANT SELECT ON public.fs_fencer_career_stats         TO authenticated;
GRANT SELECT ON public.fs_rankings_trends             TO authenticated;
GRANT SELECT ON public.fs_venues                      TO authenticated;
GRANT SELECT ON public.fs_medal_tables                TO authenticated;
GRANT SELECT ON public.fs_competition_strength        TO authenticated;
GRANT SELECT ON public.fs_fencer_transfers            TO authenticated;
GRANT SELECT ON public.fs_fencer_longevity            TO authenticated;
GRANT SELECT ON public.fs_fencer_performance_analysis TO authenticated;
GRANT SELECT ON public.fs_fencer_name_variants        TO authenticated;
GRANT SELECT ON public.fs_fencer_social_media         TO authenticated;
GRANT SELECT ON public.fs_competition_details         TO authenticated;
GRANT SELECT ON public.fs_country_depth               TO authenticated;
GRANT SELECT ON public.fs_club_rankings               TO authenticated;
GRANT SELECT ON public.fs_fencer_equipment            TO authenticated;
GRANT SELECT ON public.fs_training_camps              TO authenticated;
GRANT SELECT ON public.fs_college_scholarships        TO authenticated;
GRANT SELECT ON fs_articles                           TO authenticated;
GRANT SELECT ON fs_referees                           TO authenticated;
GRANT SELECT ON fs_coaches                            TO authenticated;
GRANT SELECT ON fs_fencer_coach_relationship          TO authenticated;
GRANT SELECT ON public.fs_club_reviews                TO authenticated;
GRANT SELECT ON public.fs_equipment_reviews           TO authenticated;

-- ── Subscriber-only SELECT policies ─────────────────────────────────────────

DO $$
DECLARE
    tbl text;
    tbls text[] := ARRAY[
        'fs_fencer_career_stats',
        'fs_rankings_trends',
        'fs_venues',
        'fs_medal_tables',
        'fs_competition_strength',
        'fs_fencer_transfers',
        'fs_fencer_longevity',
        'fs_fencer_performance_analysis',
        'fs_fencer_name_variants',
        'fs_fencer_social_media',
        'fs_competition_details',
        'fs_country_depth',
        'fs_club_rankings',
        'fs_fencer_equipment',
        'fs_training_camps',
        'fs_college_scholarships',
        'fs_articles',
        'fs_referees',
        'fs_coaches',
        'fs_fencer_coach_relationship',
        'fs_club_reviews',
        'fs_equipment_reviews'
    ];
BEGIN
    FOREACH tbl IN ARRAY tbls LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS subscriber_%1$s_read ON %1$s;
             CREATE POLICY subscriber_%1$s_read ON %1$s
             FOR SELECT TO authenticated
             USING (((SELECT auth.jwt()) -> ''app_metadata'' ->> ''role'') = ''subscriber'');',
            tbl
        );
    END LOOP;
END $$;
-- END 20260601_rls_agent_tables.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_rls_agent_tables.sql', now(), 'd36b2c774fbf5a43dd7197375f734903cc1d4d93c12e2e7bc54fa2b4bff63b11', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_rls_policies.sql
-- Supabase RLS and public-read projections.
--
-- Subscriber JWT shape expected by these policies:
-- {
--   "app_metadata": {
--     "role": "subscriber"
--   }
-- }
--
-- Authorization must use app_metadata/raw_app_meta_data, because editable
-- profile metadata can be changed by authenticated users. Existing JWTs must
-- be refreshed before app_metadata role changes take effect.

ALTER TABLE public.fs_fencers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_tournaments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_national_fed_rankings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_head_to_head ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_rankings_history ENABLE ROW LEVEL SECURITY;

-- Public-safe views expose only fields intended for anonymous readers. These
-- are fixed projection views, because anon has no direct base-table SELECT.
CREATE OR REPLACE VIEW public.v_fencer_public
WITH (security_barrier = true, security_invoker = true) AS
SELECT
    id,
    name,
    country,
    weapon,
    category,
    world_rank,
    fie_points,
    image_url
FROM public.fs_fencers;

CREATE OR REPLACE VIEW public.v_tournament_public
WITH (security_barrier = true, security_invoker = true) AS
SELECT
    id,
    name,
    season,
    start_date,
    end_date,
    country,
    weapon,
    category,
    type
FROM public.fs_tournaments;

COMMENT ON VIEW public.v_fencer_public IS
    'Anonymous-safe fencer projection; excludes profile/body/metadata fields.';
COMMENT ON VIEW public.v_tournament_public IS
    'Anonymous-safe tournament projection.';

-- Revoke direct anonymous reads from base tables; grant read access only
-- through the public-safe projections above.
REVOKE ALL ON public.fs_fencers FROM anon;
REVOKE ALL ON public.fs_tournaments FROM anon;
REVOKE ALL ON public.fs_results FROM anon;
REVOKE ALL ON public.fs_national_fed_rankings FROM anon;
REVOKE ALL ON public.fs_head_to_head FROM anon;
REVOKE ALL ON public.fs_rankings_history FROM anon;

REVOKE ALL ON public.v_fencer_public FROM PUBLIC;
REVOKE ALL ON public.v_tournament_public FROM PUBLIC;
GRANT SELECT ON public.v_fencer_public TO anon, authenticated;
GRANT SELECT ON public.v_tournament_public TO anon, authenticated;

-- Authenticated requests still need SELECT grants; RLS policies below limit
-- base-table reads to subscriber JWTs.
REVOKE ALL ON public.fs_fencers FROM authenticated;
REVOKE ALL ON public.fs_tournaments FROM authenticated;
REVOKE ALL ON public.fs_results FROM authenticated;
REVOKE ALL ON public.fs_national_fed_rankings FROM authenticated;
REVOKE ALL ON public.fs_head_to_head FROM authenticated;
REVOKE ALL ON public.fs_rankings_history FROM authenticated;

GRANT SELECT ON public.fs_fencers TO authenticated;
GRANT SELECT ON public.fs_tournaments TO authenticated;
GRANT SELECT ON public.fs_results TO authenticated;
GRANT SELECT ON public.fs_national_fed_rankings TO authenticated;
GRANT SELECT ON public.fs_head_to_head TO authenticated;
GRANT SELECT ON public.fs_rankings_history TO authenticated;

DROP POLICY IF EXISTS subscriber_fencers_read ON public.fs_fencers;
CREATE POLICY subscriber_fencers_read ON public.fs_fencers
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

DROP POLICY IF EXISTS subscriber_tournaments_read ON public.fs_tournaments;
CREATE POLICY subscriber_tournaments_read ON public.fs_tournaments
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

DROP POLICY IF EXISTS subscriber_results_read ON public.fs_results;
CREATE POLICY subscriber_results_read ON public.fs_results
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

DROP POLICY IF EXISTS subscriber_national_fed_rankings_read
ON public.fs_national_fed_rankings;
CREATE POLICY subscriber_national_fed_rankings_read
ON public.fs_national_fed_rankings
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

DROP POLICY IF EXISTS subscriber_head_to_head_read ON public.fs_head_to_head;
CREATE POLICY subscriber_head_to_head_read ON public.fs_head_to_head
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

DROP POLICY IF EXISTS subscriber_rankings_history_read ON public.fs_rankings_history;
CREATE POLICY subscriber_rankings_history_read ON public.fs_rankings_history
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
-- END 20260601_rls_policies.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_rls_policies.sql', now(), 'd4c380fe82fc1102523de66cd777e5add379777aea6b1b7401b90053ae134238', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
