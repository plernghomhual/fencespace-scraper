CREATE TABLE IF NOT EXISTS public.fs_sponsorship_matches (
    brand text NOT NULL,
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    match_score numeric(5,2) NOT NULL,
    score_components jsonb NOT NULL DEFAULT '{}',
    confidence text NOT NULL DEFAULT 'low',
    explanation text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (brand, fencer_id),
    CONSTRAINT fs_sponsorship_matches_score_check
        CHECK (match_score >= 0 AND match_score <= 100),
    CONSTRAINT fs_sponsorship_matches_confidence_check
        CHECK (confidence IN ('high', 'medium', 'low'))
);

ALTER TABLE public.fs_sponsorship_matches ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_sponsorship_matches TO service_role;

CREATE INDEX IF NOT EXISTS fs_sponsorship_matches_fencer_idx
    ON public.fs_sponsorship_matches (fencer_id);

CREATE INDEX IF NOT EXISTS fs_sponsorship_matches_score_idx
    ON public.fs_sponsorship_matches (match_score DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS fs_sponsorship_matches_confidence_idx
    ON public.fs_sponsorship_matches (confidence, updated_at DESC);
