CREATE TABLE IF NOT EXISTS public.fs_fencer_similarity (
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    similar_fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    score numeric(7,5) NOT NULL CHECK (score >= 0 AND score <= 1),
    confidence numeric(7,5) NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    sample_size integer NOT NULL DEFAULT 0 CHECK (sample_size >= 0),
    factor_breakdown jsonb NOT NULL DEFAULT '{}'::jsonb,
    model_version text NOT NULL DEFAULT 'public_sports_similarity_v1',
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_similarity_distinct_check
        CHECK (fencer_id <> similar_fencer_id),
    CONSTRAINT fs_fencer_similarity_order_check
        CHECK (fencer_id < similar_fencer_id),
    CONSTRAINT fs_fencer_similarity_pkey
        PRIMARY KEY (fencer_id, similar_fencer_id)
);

COMMENT ON TABLE public.fs_fencer_similarity IS
    'Deterministic fencer similarity pairs computed from public sports data only.';

COMMENT ON COLUMN public.fs_fencer_similarity.factor_breakdown IS
    'Per-factor scores, missing factors, source feature confidence, and model metadata.';

CREATE INDEX IF NOT EXISTS fs_fencer_similarity_fencer_score_idx
    ON public.fs_fencer_similarity (fencer_id, score DESC, confidence DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_similarity_similar_score_idx
    ON public.fs_fencer_similarity (similar_fencer_id, score DESC, confidence DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_similarity_updated_idx
    ON public.fs_fencer_similarity (updated_at DESC);

ALTER TABLE public.fs_fencer_similarity ENABLE ROW LEVEL SECURITY;
