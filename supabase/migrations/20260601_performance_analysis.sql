CREATE TABLE IF NOT EXISTS public.fs_fencer_performance_analysis (
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    weapon text NOT NULL,
    competitions_count integer NOT NULL DEFAULT 0 CHECK (competitions_count >= 0),
    avg_delta numeric(10,2),
    stddev_delta numeric(10,2),
    overperformance_rate numeric(5,2),
    clutch_score numeric(10,2),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_performance_analysis_unique
        UNIQUE (fencer_id, weapon)
);

ALTER TABLE public.fs_fencer_performance_analysis ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_performance_analysis_clutch_idx
    ON public.fs_fencer_performance_analysis (clutch_score DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_performance_analysis_updated_idx
    ON public.fs_fencer_performance_analysis (updated_at DESC);
