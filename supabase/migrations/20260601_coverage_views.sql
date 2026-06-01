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
