-- Per-season fencer aggregates are keyed by fs_fencer_identities so duplicate
-- fs_fencers rows for the same person do not create duplicate stat rows.
--
-- season is the FIE end-year integer used by season_utils.season_from_string();
-- for example, 2026 represents the 2025-2026 season.
CREATE TABLE IF NOT EXISTS public.fs_fencer_season_stats (
    fencer_identity_id uuid NOT NULL REFERENCES public.fs_fencer_identities(id) ON DELETE CASCADE,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    season integer NOT NULL,
    weapon text NOT NULL,
    gender text NOT NULL,
    category text NOT NULL,
    starts integer NOT NULL DEFAULT 0,
    best_finish integer,
    medals integer NOT NULL DEFAULT 0,
    gold_medals integer NOT NULL DEFAULT 0,
    silver_medals integer NOT NULL DEFAULT 0,
    bronze_medals integer NOT NULL DEFAULT 0,
    top8_count integer NOT NULL DEFAULT 0,
    top16_count integer NOT NULL DEFAULT 0,
    top32_count integer NOT NULL DEFAULT 0,
    bouts integer NOT NULL DEFAULT 0,
    wins integer NOT NULL DEFAULT 0,
    losses integer NOT NULL DEFAULT 0,
    touches_scored integer NOT NULL DEFAULT 0,
    touches_received integer NOT NULL DEFAULT 0,
    touches integer GENERATED ALWAYS AS (touches_scored + touches_received) STORED,
    win_pct numeric(5,2) GENERATED ALWAYS AS (
        CASE
            WHEN bouts = 0 THEN 0
            ELSE round((wins::numeric / bouts::numeric) * 100, 2)
        END
    ) STORED,
    rank_delta integer,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_season_stats_pkey
        PRIMARY KEY (fencer_identity_id, season, weapon, gender, category),
    CONSTRAINT fs_fencer_season_stats_season_check
        CHECK (season BETWEEN 1900 AND 2200),
    CONSTRAINT fs_fencer_season_stats_best_finish_check
        CHECK (best_finish IS NULL OR best_finish > 0),
    CONSTRAINT fs_fencer_season_stats_counts_non_negative CHECK (
        starts >= 0
        AND medals >= 0
        AND gold_medals >= 0
        AND silver_medals >= 0
        AND bronze_medals >= 0
        AND top8_count >= 0
        AND top16_count >= 0
        AND top32_count >= 0
        AND bouts >= 0
        AND wins >= 0
        AND losses >= 0
        AND touches_scored >= 0
        AND touches_received >= 0
    ),
    CONSTRAINT fs_fencer_season_stats_result_bounds CHECK (
        medals = gold_medals + silver_medals + bronze_medals
        AND medals <= top8_count
        AND top8_count <= top16_count
        AND top16_count <= top32_count
        AND top32_count <= starts
    ),
    CONSTRAINT fs_fencer_season_stats_bout_totals
        CHECK (bouts = wins + losses)
);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_season_stats_fencer_detail
    ON public.fs_fencer_season_stats
    (fencer_identity_id, season DESC, weapon, gender, category);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_season_stats_fencer_row_detail
    ON public.fs_fencer_season_stats (fencer_id, season DESC)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_fencer_season_stats_leaderboard
    ON public.fs_fencer_season_stats
    (season, weapon, gender, category, win_pct DESC, best_finish ASC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_season_stats_medal_leaderboard
    ON public.fs_fencer_season_stats
    (season, weapon, gender, category, medals DESC, top8_count DESC);

ALTER TABLE public.fs_fencer_season_stats ENABLE ROW LEVEL SECURITY;
