CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_ranking_history_trajectory (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_identity_id uuid NOT NULL REFERENCES public.fs_fencer_identities(id),
    fencer_id          uuid REFERENCES public.fs_fencers(id),
    source             text NOT NULL,
    season             text NOT NULL,
    weapon             text NOT NULL,
    gender             text NOT NULL,
    category           text NOT NULL,
    rank               integer NOT NULL,
    points             numeric,
    rank_delta         integer,
    points_delta       numeric,
    trend_window       text NOT NULL DEFAULT 'season',
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_ranking_history_trajectory_unique
        UNIQUE (fencer_identity_id, source, season, weapon, gender, category, trend_window),
    CONSTRAINT fs_ranking_history_trajectory_rank_positive
        CHECK (rank > 0),
    CONSTRAINT fs_ranking_history_trajectory_points_nonnegative
        CHECK (points IS NULL OR points >= 0),
    CONSTRAINT fs_ranking_history_trajectory_season_format
        CHECK (
            CASE
                WHEN season ~ '^\d{4}-\d{4}$'
                THEN substring(season FROM 6 FOR 4)::integer = substring(season FROM 1 FOR 4)::integer + 1
                ELSE false
            END
        ),
    CONSTRAINT fs_ranking_history_trajectory_trend_window_present
        CHECK (btrim(trend_window) <> '')
);

COMMENT ON TABLE public.fs_ranking_history_trajectory IS
    'Normalized multi-source ranking history rows for fencer sparklines and projection engines.';

COMMENT ON COLUMN public.fs_ranking_history_trajectory.season IS
    'Normalized fencing season in YYYY-YYYY format, matching season_utils.normalize_season().';

COMMENT ON COLUMN public.fs_ranking_history_trajectory.points IS
    'Nullable because some ranking sources publish rank-only data.';

CREATE INDEX IF NOT EXISTS fs_ranking_history_trajectory_detail_idx
    ON public.fs_ranking_history_trajectory
        (fencer_identity_id, source, weapon, gender, category, trend_window, season);

CREATE INDEX IF NOT EXISTS fs_ranking_history_trajectory_fencer_idx
    ON public.fs_ranking_history_trajectory (fencer_id, season, source)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_ranking_history_trajectory_projection_idx
    ON public.fs_ranking_history_trajectory
        (source, weapon, gender, category, season, rank);
