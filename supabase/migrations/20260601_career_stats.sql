CREATE TABLE IF NOT EXISTS public.fs_fencer_career_stats (
    fencer_id uuid PRIMARY KEY REFERENCES public.fs_fencers(id),
    total_competitions integer DEFAULT 0,
    gold_medals integer DEFAULT 0,
    silver_medals integer DEFAULT 0,
    bronze_medals integer DEFAULT 0,
    top8_count integer DEFAULT 0,
    best_rank integer,
    avg_rank numeric(5,2),
    worst_rank integer,
    weapons_used jsonb,
    categories_competed jsonb,
    first_season text,
    last_season text,
    total_touches_scored integer DEFAULT 0,
    total_touches_received integer DEFAULT 0,
    touch_differential integer DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE public.fs_fencer_career_stats ENABLE ROW LEVEL SECURITY;
