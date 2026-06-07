-- Fencer stats are keyed by fs_fencer_identities so one physical fencer has
-- one stats row per weapon/category even when fs_fencers has duplicate source
-- rows for the same person.
--
-- No foreign key is declared to fs_bouts because this table stores aggregate
-- snapshots, not individual bout rows, and historical/live bout column names
-- have differed across migrations.
CREATE TABLE IF NOT EXISTS public.fs_fencer_stats (
    identity_id uuid NOT NULL REFERENCES public.fs_fencer_identities(id) ON DELETE CASCADE,
    weapon text NOT NULL,
    category text NOT NULL,
    total_bouts integer NOT NULL DEFAULT 0,
    wins integer NOT NULL DEFAULT 0,
    losses integer NOT NULL DEFAULT 0,
    touches_scored integer NOT NULL DEFAULT 0,
    touches_received integer NOT NULL DEFAULT 0,
    win_pct numeric(5,2) GENERATED ALWAYS AS (
        CASE
            WHEN total_bouts = 0 THEN 0
            ELSE round((wins::numeric / total_bouts::numeric) * 100, 2)
        END
    ) STORED,
    -- Positive values are win streaks; negative values are loss streaks.
    current_streak integer NOT NULL DEFAULT 0,
    longest_win_streak integer NOT NULL DEFAULT 0,
    last_bout_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_stats_pk PRIMARY KEY (identity_id, weapon, category),
    CONSTRAINT fs_fencer_stats_counts_non_negative CHECK (
        total_bouts >= 0
        AND wins >= 0
        AND losses >= 0
        AND touches_scored >= 0
        AND touches_received >= 0
    ),
    CONSTRAINT fs_fencer_stats_win_loss_total CHECK (total_bouts = wins + losses),
    CONSTRAINT fs_fencer_stats_streak_bounds CHECK (
        abs(current_streak) <= total_bouts
        AND longest_win_streak >= 0
        AND longest_win_streak <= wins
    )
);

CREATE INDEX IF NOT EXISTS fs_fencer_stats_identity_recent_idx
    ON public.fs_fencer_stats (identity_id, last_bout_at DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_stats_weapon_category_win_pct_idx
    ON public.fs_fencer_stats (weapon, category, win_pct DESC)
    WHERE total_bouts > 0;

CREATE INDEX IF NOT EXISTS fs_fencer_stats_updated_idx
    ON public.fs_fencer_stats (updated_at DESC);

ALTER TABLE public.fs_fencer_stats ENABLE ROW LEVEL SECURITY;
