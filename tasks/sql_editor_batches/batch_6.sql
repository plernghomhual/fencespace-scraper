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
