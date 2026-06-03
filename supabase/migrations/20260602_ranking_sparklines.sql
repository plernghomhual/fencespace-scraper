-- Compact public-safe ranking history for athlete page sparklines.
--
-- Agent 16's multi-source fs_ranking_history_trajectory table is not present
-- in this checkout. The current canonical FIE trajectory table is
-- fs_rankings_history, so this projection materializes it with source = 'fie'.

CREATE MATERIALIZED VIEW IF NOT EXISTS public.v_ranking_sparklines AS
WITH source_rows AS (
    SELECT
        NULLIF(r.fie_fencer_id::text, '') AS fie_fencer_id,
        'fie'::text AS source,
        r.season::integer AS season,
        NULLIF(r.weapon::text, '') AS weapon,
        NULLIF(r.gender::text, '') AS gender,
        NULLIF(r.category::text, '') AS category,
        r.rank::integer AS rank,
        r.points::numeric AS points,
        r.scraped_at AS scraped_at,
        r.scraped_at AS updated_at,
        r.name AS name
    FROM public.fs_rankings_history r
    WHERE NULLIF(r.fie_fencer_id::text, '') IS NOT NULL
      AND r.season IS NOT NULL
      AND NULLIF(r.weapon::text, '') IS NOT NULL
      AND NULLIF(r.gender::text, '') IS NOT NULL
      AND NULLIF(r.category::text, '') IS NOT NULL
      AND r.rank IS NOT NULL
      AND r.rank > 0
),
ranked AS (
    SELECT
        source_rows.*,
        row_number() over (
            partition by source, fie_fencer_id, season, weapon, gender, category
            order by scraped_at desc nulls last, rank asc nulls last, points desc nulls last, name asc nulls last
        ) AS rn
    FROM source_rows
),
canonical AS (
    SELECT
        fie_fencer_id,
        source,
        season,
        weapon,
        gender,
        category,
        rank,
        points,
        updated_at
    FROM ranked
    WHERE rn = 1
),
fencer_lookup AS (
    SELECT DISTINCT ON (f.fie_id)
        f.id AS fencer_id,
        f.fie_id
    FROM public.fs_fencers f
    WHERE f.fie_id IS NOT NULL
      AND btrim(f.fie_id) <> ''
    ORDER BY f.fie_id, f.updated_at DESC NULLS LAST, f.id
),
latest AS (
    SELECT DISTINCT ON (fie_fencer_id, source, weapon, gender, category)
        fie_fencer_id,
        source,
        weapon,
        gender,
        category,
        rank AS latest_rank,
        points AS latest_points
    FROM canonical
    ORDER BY fie_fencer_id, source, weapon, gender, category, season DESC, rank ASC NULLS LAST, points DESC NULLS LAST
),
first_seen AS (
    SELECT DISTINCT ON (fie_fencer_id, source, weapon, gender, category)
        fie_fencer_id,
        source,
        weapon,
        gender,
        category,
        rank AS first_rank
    FROM canonical
    ORDER BY fie_fencer_id, source, weapon, gender, category, season ASC, rank ASC NULLS LAST, points DESC NULLS LAST
)
SELECT
    fl.fencer_id,
    c.fie_fencer_id,
    c.source,
    c.weapon,
    c.gender,
    c.category,
    array_agg(c.season ORDER BY c.season ASC, c.rank ASC, c.points DESC NULLS LAST) AS seasons,
    array_agg(c.rank ORDER BY c.season ASC, c.rank ASC, c.points DESC NULLS LAST) AS ranks,
    array_agg(c.points ORDER BY c.season ASC, c.rank ASC, c.points DESC NULLS LAST) AS points,
    jsonb_agg(jsonb_build_object('season', c.season, 'rank', c.rank, 'points', c.points) ORDER BY c.season ASC, c.rank ASC, c.points DESC NULLS LAST) AS history,
    l.latest_rank,
    l.latest_points,
    min(c.rank) AS best_rank,
    max(c.rank) AS worst_rank,
    (f.first_rank - l.latest_rank) AS delta,
    count(*)::integer AS sample_count,
    max(c.updated_at) AS updated_at
FROM canonical c
LEFT JOIN fencer_lookup fl
    ON fl.fie_id = c.fie_fencer_id
JOIN latest l
    ON l.fie_fencer_id = c.fie_fencer_id
   AND l.source = c.source
   AND l.weapon = c.weapon
   AND l.gender = c.gender
   AND l.category = c.category
JOIN first_seen f
    ON f.fie_fencer_id = c.fie_fencer_id
   AND f.source = c.source
   AND f.weapon = c.weapon
   AND f.gender = c.gender
   AND f.category = c.category
GROUP BY
    fl.fencer_id,
    c.fie_fencer_id,
    c.source,
    c.weapon,
    c.gender,
    c.category,
    l.latest_rank,
    l.latest_points,
    f.first_rank
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS v_ranking_sparklines_unique_idx
    ON public.v_ranking_sparklines (fie_fencer_id, source, weapon, gender, category);

CREATE INDEX IF NOT EXISTS v_ranking_sparklines_fencer_idx
    ON public.v_ranking_sparklines (fencer_id, source, weapon, gender, category)
    WHERE fencer_id IS NOT NULL;

COMMENT ON MATERIALIZED VIEW public.v_ranking_sparklines IS
    'Public-safe compact FIE ranking history for athlete page sparklines; excludes source row metadata.';

REVOKE ALL ON public.v_ranking_sparklines FROM PUBLIC;
GRANT SELECT ON public.v_ranking_sparklines TO anon, authenticated;
