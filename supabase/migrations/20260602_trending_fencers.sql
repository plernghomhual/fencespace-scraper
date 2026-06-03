CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_trending_fencers (
    fencer_id             uuid        NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    week_start            date        NOT NULL,
    score                 numeric(8,2) NOT NULL DEFAULT 0,
    rank_delta            integer,
    recent_results_score  numeric(8,2) NOT NULL DEFAULT 0,
    social_score          numeric(8,2) NOT NULL DEFAULT 0,
    reasons               jsonb       NOT NULL DEFAULT '[]',
    updated_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (fencer_id, week_start),
    CONSTRAINT fs_trending_fencers_score_nonnegative
        CHECK (score >= 0),
    CONSTRAINT fs_trending_fencers_recent_results_score_bounds
        CHECK (recent_results_score >= 0 AND recent_results_score <= 100),
    CONSTRAINT fs_trending_fencers_social_score_bounds
        CHECK (social_score >= 0 AND social_score <= 5),
    CONSTRAINT fs_trending_fencers_reasons_array
        CHECK (jsonb_typeof(reasons) = 'array')
);

CREATE INDEX IF NOT EXISTS fs_trending_fencers_week_score_idx
    ON public.fs_trending_fencers (week_start DESC, score DESC);

CREATE INDEX IF NOT EXISTS fs_trending_fencers_rank_delta_idx
    ON public.fs_trending_fencers (week_start DESC, rank_delta DESC)
    WHERE rank_delta IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_trending_fencers_updated_idx
    ON public.fs_trending_fencers (updated_at DESC);

ALTER TABLE public.fs_trending_fencers ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_trending_fencers FROM anon, authenticated;
GRANT SELECT ON public.fs_trending_fencers TO authenticated;

DROP POLICY IF EXISTS authenticated_trending_fencers_read ON public.fs_trending_fencers;
CREATE POLICY authenticated_trending_fencers_read
ON public.fs_trending_fencers
FOR SELECT TO authenticated
USING (true);
