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
WITH (security_barrier = true) AS
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
WITH (security_barrier = true) AS
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
