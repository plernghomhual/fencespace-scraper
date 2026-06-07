CREATE TABLE IF NOT EXISTS public.fs_fencer_longevity (
    fencer_id uuid PRIMARY KEY REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    first_competition_date date,
    last_competition_date date,
    first_season integer,
    last_season integer,
    career_years integer,
    competitions_per_season numeric(8,2),
    status text NOT NULL DEFAULT 'unknown',
    updated_at timestamptz DEFAULT now(),
    CHECK (career_years IS NULL OR career_years >= 0),
    CHECK (competitions_per_season IS NULL OR competitions_per_season >= 0),
    CHECK (status IN ('active', 'likely_retired', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_status
    ON public.fs_fencer_longevity(status);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_last_competition
    ON public.fs_fencer_longevity(last_competition_date);

ALTER TABLE public.fs_fencer_longevity ENABLE ROW LEVEL SECURITY;
