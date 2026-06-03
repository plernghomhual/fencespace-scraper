CREATE TABLE IF NOT EXISTS public.fs_transfer_values (
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    season integer NOT NULL,
    value_score numeric(5,2),
    score_components jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence numeric(4,2) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_transfer_values_unique
        UNIQUE (fencer_id, season),
    CONSTRAINT fs_transfer_values_score_range
        CHECK (value_score IS NULL OR (value_score >= 0 AND value_score <= 100)),
    CONSTRAINT fs_transfer_values_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1)
);

COMMENT ON TABLE public.fs_transfer_values IS
    'Internal non-monetary transfer impact score from public sport data only. It is not a person valuation and excludes private, medical, financial, contract, academic, and consent-sensitive context.';

COMMENT ON COLUMN public.fs_transfer_values.value_score IS
    'Transparent non-monetary score from public ranking, performance, age, category, and form signals.';

COMMENT ON COLUMN public.fs_transfer_values.score_components IS
    'JSON object containing scored or missing status per signal plus ethical and product limitations.';

CREATE INDEX IF NOT EXISTS fs_transfer_values_season_score_idx
    ON public.fs_transfer_values (season, value_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS fs_transfer_values_confidence_idx
    ON public.fs_transfer_values (confidence DESC);

CREATE INDEX IF NOT EXISTS fs_transfer_values_updated_idx
    ON public.fs_transfer_values (updated_at DESC);

ALTER TABLE public.fs_transfer_values ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_transfer_values FROM anon, authenticated;
