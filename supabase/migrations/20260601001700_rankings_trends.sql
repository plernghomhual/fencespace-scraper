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
