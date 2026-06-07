-- Rich public fencer projection for athlete pages.
--
-- The view is keyed by fs_fencer_identities so duplicate fs_fencers source
-- rows for the same athlete collapse to one public athlete row. Public output
-- intentionally omits source internals, scraper metadata, private handles, and
-- raw identity member arrays.

ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS bio text,
    ADD COLUMN IF NOT EXISTS bio_text text,
    ADD COLUMN IF NOT EXISTS birth_date date,
    ADD COLUMN IF NOT EXISTS date_of_birth date,
    ADD COLUMN IF NOT EXISTS birth_place text,
    ADD COLUMN IF NOT EXISTS nationality text,
    ADD COLUMN IF NOT EXISTS gender text,
    ADD COLUMN IF NOT EXISTS headshot_url text,
    ADD COLUMN IF NOT EXISTS wikipedia_url text,
    ADD COLUMN IF NOT EXISTS national_rank integer,
    ADD COLUMN IF NOT EXISTS national_rank_points numeric,
    ADD COLUMN IF NOT EXISTS national_rank_source text,
    ADD COLUMN IF NOT EXISTS national_rank_season text;

CREATE OR REPLACE VIEW public.v_fencer_public
WITH (security_barrier = true, security_invoker = true) AS
WITH identity_members AS (
    SELECT
        i.id AS identity_id,
        i.canonical_name AS identity_name,
        i.country AS identity_country,
        f.id AS fencer_id,
        f.name,
        f.country,
        f.nationality,
        f.gender,
        f.weapon,
        f.category,
        f.world_rank,
        f.fie_points,
        f.national_rank,
        f.national_rank_points,
        f.national_rank_source,
        f.national_rank_season,
        f.bio,
        f.bio_text,
        f.birth_date,
        f.date_of_birth,
        f.birth_place,
        f.image_url,
        f.headshot_url,
        f.wikipedia_url,
        f.updated_at
    FROM public.fs_fencer_identities i
    JOIN public.fs_fencers f
        ON f.id = ANY(i.fs_fencer_row_ids)
),
standalone_members AS (
    SELECT
        f.id AS identity_id,
        f.name AS identity_name,
        f.country AS identity_country,
        f.id AS fencer_id,
        f.name,
        f.country,
        f.nationality,
        f.gender,
        f.weapon,
        f.category,
        f.world_rank,
        f.fie_points,
        f.national_rank,
        f.national_rank_points,
        f.national_rank_source,
        f.national_rank_season,
        f.bio,
        f.bio_text,
        f.birth_date,
        f.date_of_birth,
        f.birth_place,
        f.image_url,
        f.headshot_url,
        f.wikipedia_url,
        f.updated_at
    FROM public.fs_fencers f
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.fs_fencer_identities i
        WHERE f.id = ANY(i.fs_fencer_row_ids)
    )
),
member_rows AS (
    SELECT * FROM identity_members
    UNION ALL
    SELECT * FROM standalone_members
),
ranked_members AS (
    SELECT
        m.*,
        row_number() OVER (
            PARTITION BY identity_id
            ORDER BY
                CASE
                    WHEN NULLIF(btrim(COALESCE(m.identity_name, m.name)), '') IS NOT NULL
                    THEN 0 ELSE 1
                END,
                CASE
                    WHEN m.world_rank IS NOT NULL AND m.world_rank > 0
                    THEN 0 ELSE 1
                END,
                m.world_rank ASC NULLS LAST,
                CASE
                    WHEN NULLIF(btrim(COALESCE(m.image_url, m.headshot_url)), '') IS NOT NULL
                    THEN 0 ELSE 1
                END,
                m.updated_at DESC NULLS LAST,
                m.fencer_id
        ) AS member_rank
    FROM member_rows m
),
identity_summary AS (
    SELECT
        identity_id,
        (array_agg(fencer_id ORDER BY member_rank))[1] AS primary_fencer_id,
        COALESCE(
            (array_agg(NULLIF(btrim(identity_name), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(identity_name), '') IS NOT NULL))[1],
            (array_agg(NULLIF(btrim(name), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(name), '') IS NOT NULL))[1]
        ) AS display_name,
        COALESCE(
            (array_agg(NULLIF(btrim(identity_country), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(identity_country), '') IS NOT NULL))[1],
            (array_agg(NULLIF(btrim(country), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(country), '') IS NOT NULL))[1]
        ) AS country,
        (array_agg(NULLIF(btrim(nationality), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(nationality), '') IS NOT NULL))[1] AS nationality,
        (array_agg(NULLIF(btrim(gender), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(gender), '') IS NOT NULL))[1] AS gender,
        MIN(world_rank) FILTER (WHERE world_rank IS NOT NULL AND world_rank > 0) AS world_rank,
        MAX(fie_points) FILTER (WHERE fie_points IS NOT NULL) AS fie_points,
        (array_agg(national_rank ORDER BY national_rank ASC NULLS LAST, member_rank)
            FILTER (WHERE national_rank IS NOT NULL))[1] AS national_rank,
        (array_agg(national_rank_points ORDER BY national_rank ASC NULLS LAST, member_rank)
            FILTER (WHERE national_rank_points IS NOT NULL))[1] AS national_rank_points,
        (array_agg(NULLIF(btrim(national_rank_source), '') ORDER BY national_rank ASC NULLS LAST, member_rank)
            FILTER (WHERE NULLIF(btrim(national_rank_source), '') IS NOT NULL))[1] AS national_rank_source,
        (array_agg(NULLIF(btrim(national_rank_season), '') ORDER BY national_rank ASC NULLS LAST, member_rank)
            FILTER (WHERE NULLIF(btrim(national_rank_season), '') IS NOT NULL))[1] AS national_rank_season,
        COALESCE(
            (array_agg(NULLIF(btrim(bio), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(bio), '') IS NOT NULL))[1],
            (array_agg(NULLIF(btrim(bio_text), '') ORDER BY member_rank)
                FILTER (WHERE NULLIF(btrim(bio_text), '') IS NOT NULL))[1]
        ) AS bio,
        COALESCE(
            (array_agg(birth_date::text ORDER BY member_rank)
                FILTER (WHERE birth_date IS NOT NULL))[1],
            (array_agg(date_of_birth::text ORDER BY member_rank)
                FILTER (WHERE date_of_birth IS NOT NULL))[1]
        ) AS birth_date,
        (array_agg(NULLIF(btrim(birth_place), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(birth_place), '') IS NOT NULL))[1] AS birth_place,
        (array_agg(NULLIF(btrim(image_url), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(image_url), '') IS NOT NULL))[1] AS image_url,
        (array_agg(NULLIF(btrim(headshot_url), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(headshot_url), '') IS NOT NULL))[1] AS headshot_url,
        (array_agg(NULLIF(btrim(wikipedia_url), '') ORDER BY member_rank)
            FILTER (WHERE NULLIF(btrim(wikipedia_url), '') IS NOT NULL))[1] AS wikipedia_url,
        MAX(updated_at) AS updated_at
    FROM ranked_members
    GROUP BY identity_id
),
weapon_category_summary AS (
    SELECT
        identity_id,
        array_agg(DISTINCT NULLIF(btrim(weapon), ''))
            FILTER (WHERE NULLIF(btrim(weapon), '') IS NOT NULL) AS weapons,
        array_agg(DISTINCT NULLIF(btrim(category), ''))
            FILTER (WHERE NULLIF(btrim(category), '') IS NOT NULL) AS categories
    FROM member_rows
    GROUP BY identity_id
),
stats_by_identity AS (
    SELECT
        identity_id,
        SUM(total_bouts) AS total_bouts,
        SUM(wins) AS wins,
        SUM(losses) AS losses,
        SUM(touches_scored) AS touches_scored,
        SUM(touches_received) AS touches_received,
        CASE
            WHEN SUM(total_bouts) > 0
            THEN round((SUM(wins)::numeric / SUM(total_bouts)::numeric) * 100, 2)
            ELSE 0
        END AS win_pct,
        MAX(longest_win_streak) AS longest_win_streak,
        MAX(last_bout_at) AS last_bout_at
    FROM public.fs_fencer_stats
    GROUP BY identity_id
),
career_by_identity AS (
    SELECT
        m.identity_id,
        MAX(c.total_competitions) AS total_competitions,
        MAX(c.gold_medals) AS gold_medals,
        MAX(c.silver_medals) AS silver_medals,
        MAX(c.bronze_medals) AS bronze_medals,
        MAX(c.top8_count) AS top8_count,
        MIN(c.best_rank) AS best_rank,
        MIN(c.avg_rank) AS avg_rank,
        MAX(c.total_touches_scored) AS career_touches_scored,
        MAX(c.total_touches_received) AS career_touches_received,
        MAX(c.touch_differential) AS career_touch_differential
    FROM member_rows m
    LEFT JOIN public.fs_fencer_career_stats c
        ON c.fencer_id = m.fencer_id
    GROUP BY m.identity_id
),
latest_trajectory AS (
    SELECT
        fencer_identity_id AS identity_id,
        source,
        season,
        weapon,
        gender,
        category,
        rank,
        points,
        rank_delta,
        points_delta,
        row_number() OVER (
            PARTITION BY fencer_identity_id
            ORDER BY season DESC, updated_at DESC, rank ASC
        ) AS ranking_row
    FROM public.fs_ranking_history_trajectory
)
SELECT
    s.identity_id AS id,
    s.display_name AS name,
    s.country,
    array_to_string(COALESCE(wc.weapons, ARRAY[]::text[]), ', ') AS weapon,
    array_to_string(COALESCE(wc.categories, ARRAY[]::text[]), ', ') AS category,
    s.world_rank,
    s.fie_points,
    s.image_url,
    s.primary_fencer_id,
    s.display_name,
    s.nationality,
    s.gender,
    COALESCE(wc.weapons, ARRAY[]::text[]) AS weapons,
    COALESCE(wc.categories, ARRAY[]::text[]) AS categories,
    array_to_string(COALESCE(wc.weapons, ARRAY[]::text[]), ', ') AS weapon_summary,
    array_to_string(COALESCE(wc.categories, ARRAY[]::text[]), ', ') AS category_summary,
    s.bio,
    s.birth_date,
    s.birth_place,
    s.headshot_url,
    s.wikipedia_url,
    jsonb_strip_nulls(jsonb_build_object(
        'image_url', s.image_url,
        'headshot_url', s.headshot_url,
        'wikipedia_url', s.wikipedia_url
    )) AS media_urls,
    s.national_rank,
    s.national_rank_points,
    s.national_rank_source,
    s.national_rank_season,
    jsonb_strip_nulls(jsonb_build_object(
        'world_rank', s.world_rank,
        'fie_points', s.fie_points,
        'national_rank', s.national_rank,
        'national_rank_points', s.national_rank_points,
        'national_rank_source', s.national_rank_source,
        'national_rank_season', s.national_rank_season,
        'latest_source', lt.source,
        'latest_season', lt.season,
        'latest_weapon', lt.weapon,
        'latest_gender', lt.gender,
        'latest_category', lt.category,
        'latest_rank', lt.rank,
        'latest_points', lt.points,
        'rank_delta', lt.rank_delta,
        'points_delta', lt.points_delta
    )) AS ranking_summary,
    COALESCE(st.total_bouts, 0) AS total_bouts,
    COALESCE(st.wins, 0) AS wins,
    COALESCE(st.losses, 0) AS losses,
    COALESCE(st.win_pct, 0) AS win_pct,
    c.total_competitions,
    c.gold_medals,
    c.silver_medals,
    c.bronze_medals,
    c.top8_count,
    jsonb_strip_nulls(jsonb_build_object(
        'total_bouts', COALESCE(st.total_bouts, 0),
        'wins', COALESCE(st.wins, 0),
        'losses', COALESCE(st.losses, 0),
        'win_pct', COALESCE(st.win_pct, 0),
        'touches_scored', st.touches_scored,
        'touches_received', st.touches_received,
        'longest_win_streak', st.longest_win_streak,
        'last_bout_at', st.last_bout_at,
        'total_competitions', c.total_competitions,
        'gold_medals', c.gold_medals,
        'silver_medals', c.silver_medals,
        'bronze_medals', c.bronze_medals,
        'top8_count', c.top8_count,
        'best_rank', c.best_rank,
        'avg_rank', c.avg_rank,
        'career_touches_scored', c.career_touches_scored,
        'career_touches_received', c.career_touches_received,
        'career_touch_differential', c.career_touch_differential
    )) AS stats_summary,
    s.updated_at
FROM identity_summary s
LEFT JOIN weapon_category_summary wc
    ON wc.identity_id = s.identity_id
LEFT JOIN stats_by_identity st
    ON st.identity_id = s.identity_id
LEFT JOIN career_by_identity c
    ON c.identity_id = s.identity_id
LEFT JOIN latest_trajectory lt
    ON lt.identity_id = s.identity_id
   AND lt.ranking_row = 1;

COMMENT ON VIEW public.v_fencer_public IS
    'Anonymous-safe fencer projection for athlete pages; one row per canonical identity with public bio, media, rank, and stats summaries.';

REVOKE ALL ON public.v_fencer_public FROM PUBLIC;
GRANT SELECT ON public.v_fencer_public TO anon, authenticated;
