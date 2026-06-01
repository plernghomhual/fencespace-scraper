-- Scraper Run Status (last 24h per module)
WITH recent_runs AS (
    SELECT
        module,
        started_at,
        completed_at,
        status,
        COALESCE(written, 0) AS written,
        COALESCE(failed, 0) AS failed,
        COALESCE(skipped, 0) AS skipped,
        ROW_NUMBER() OVER (
            PARTITION BY module
            ORDER BY started_at DESC
        ) AS run_rank
    FROM public.fs_scraper_runs
    WHERE started_at >= now() - interval '24 hours'
)
SELECT
    module,
    started_at AS last_run_started_at,
    completed_at AS last_run_completed_at,
    status,
    written,
    failed,
    skipped,
    CASE
        WHEN completed_at IS NULL AND status <> 'running' THEN 'red'
        WHEN COALESCE(completed_at, started_at) < now() - interval '48 hours' THEN 'grey'
        WHEN status IN ('completed', 'success') THEN 'green'
        WHEN status = 'completed_with_errors' THEN 'yellow'
        WHEN status = 'error' THEN 'red'
        ELSE 'yellow'
    END AS dashboard_color
FROM recent_runs
WHERE run_rank = 1
ORDER BY module;

-- Data Counts (fencers, tournaments, results per source)
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

SELECT
    COALESCE(season::text, 'unknown') AS season,
    COUNT(*)::bigint AS tournament_count
FROM public.fs_tournaments
GROUP BY COALESCE(season::text, 'unknown')
ORDER BY season DESC;

SELECT
    COALESCE(t.type, 'unknown') AS competition_type,
    COUNT(r.*)::bigint AS result_count
FROM public.fs_results r
LEFT JOIN public.fs_tournaments t
    ON t.id = r.tournament_id
GROUP BY COALESCE(t.type, 'unknown')
ORDER BY result_count DESC;

SELECT
    COALESCE(t.type, 'unknown') AS competition_type,
    COUNT(r.*)::bigint AS orphan_result_count
FROM public.fs_results r
LEFT JOIN public.fs_tournaments t
    ON t.id = r.tournament_id
WHERE r.fencer_id IS NULL
GROUP BY COALESCE(t.type, 'unknown')
ORDER BY orphan_result_count DESC;

-- Stale Sources (last success > 48h ago)
WITH last_success AS (
    SELECT
        module,
        MAX(completed_at) AS last_success_at
    FROM public.fs_scraper_runs
    WHERE status IN ('completed', 'success')
      AND completed_at IS NOT NULL
    GROUP BY module
)
SELECT
    module,
    last_success_at,
    now() - last_success_at AS stale_for
FROM last_success
WHERE last_success_at < now() - interval '48 hours'
ORDER BY last_success_at ASC;

-- Error Rate Per Module
SELECT
    module,
    COUNT(*)::bigint AS total_runs,
    COUNT(*) FILTER (
        WHERE status = 'error'
           OR status = 'completed_with_errors'
           OR COALESCE(failed, 0) > 0
    )::bigint AS error_runs,
    ROUND(
        COUNT(*) FILTER (
            WHERE status = 'error'
               OR status = 'completed_with_errors'
               OR COALESCE(failed, 0) > 0
        )::numeric
        / NULLIF(COUNT(*), 0),
        4
    ) AS error_rate
FROM public.fs_scraper_runs
WHERE started_at >= now() - interval '7 days'
GROUP BY module
ORDER BY error_rate DESC NULLS LAST, total_runs DESC;
