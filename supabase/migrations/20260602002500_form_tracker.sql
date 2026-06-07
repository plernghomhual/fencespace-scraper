CREATE TABLE IF NOT EXISTS public.fs_fencer_form (
    fencer_id          uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    weapon             text NOT NULL,
    last_competitions  jsonb NOT NULL DEFAULT '[]',
    form_score         numeric(6,2) NOT NULL DEFAULT 0,
    trend_direction    text NOT NULL DEFAULT 'stable',
    recent_medals      integer NOT NULL DEFAULT 0,
    recent_avg_rank    numeric(8,2),
    metadata           jsonb NOT NULL DEFAULT '{}',
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_form_unique UNIQUE (fencer_id, weapon),
    CONSTRAINT fs_fencer_form_trend_direction_check
        CHECK (trend_direction IN ('improving', 'declining', 'stable')),
    CONSTRAINT fs_fencer_form_recent_medals_non_negative
        CHECK (recent_medals >= 0),
    CONSTRAINT fs_fencer_form_score_bounds
        CHECK (form_score >= 0 AND form_score <= 100)
);

CREATE INDEX IF NOT EXISTS fs_fencer_form_weapon_score_idx
    ON public.fs_fencer_form (weapon, form_score DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_form_trend_idx
    ON public.fs_fencer_form (trend_direction, weapon);

CREATE INDEX IF NOT EXISTS fs_fencer_form_updated_idx
    ON public.fs_fencer_form (updated_at DESC);

ALTER TABLE public.fs_fencer_form ENABLE ROW LEVEL SECURITY;
