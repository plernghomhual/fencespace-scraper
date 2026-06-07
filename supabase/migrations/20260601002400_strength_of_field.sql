CREATE TABLE IF NOT EXISTS public.fs_competition_strength (
    tournament_id uuid PRIMARY KEY REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    avg_world_rank numeric,
    top8_count integer NOT NULL DEFAULT 0 CHECK (top8_count >= 0),
    top16_count integer NOT NULL DEFAULT 0 CHECK (top16_count >= 0),
    total_fie_ranked integer NOT NULL DEFAULT 0 CHECK (total_fie_ranked >= 0),
    strength_score numeric,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (top8_count <= top16_count),
    CHECK (top16_count <= total_fie_ranked)
);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_score
ON public.fs_competition_strength (strength_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_avg_rank
ON public.fs_competition_strength (avg_world_rank ASC NULLS LAST);
