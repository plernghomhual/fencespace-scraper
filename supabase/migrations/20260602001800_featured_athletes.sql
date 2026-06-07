CREATE TABLE IF NOT EXISTS public.fs_featured_athlete_candidates (
    candidate_key text PRIMARY KEY,
    identity_id uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    display_name text NOT NULL,
    country text,
    weapon text,
    score numeric(8,3) NOT NULL CHECK (score >= 0),
    reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    rank_context jsonb NOT NULL DEFAULT '{}'::jsonb,
    recency jsonb NOT NULL DEFAULT '{}'::jsonb,
    selected boolean NOT NULL DEFAULT false,
    selection_rank integer CHECK (selection_rank IS NULL OR selection_rank > 0),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_featured_athlete_candidates_reasons_array
        CHECK (jsonb_typeof(reasons) = 'array'),
    CONSTRAINT fs_featured_athlete_candidates_rank_context_object
        CHECK (jsonb_typeof(rank_context) = 'object'),
    CONSTRAINT fs_featured_athlete_candidates_recency_object
        CHECK (jsonb_typeof(recency) = 'object')
);

CREATE INDEX IF NOT EXISTS fs_featured_athlete_candidates_score_idx
    ON public.fs_featured_athlete_candidates (selected, score DESC, selection_rank);

CREATE INDEX IF NOT EXISTS fs_featured_athlete_candidates_diversity_idx
    ON public.fs_featured_athlete_candidates (country, weapon, score DESC)
    WHERE selected = true;

CREATE INDEX IF NOT EXISTS fs_featured_athlete_candidates_updated_idx
    ON public.fs_featured_athlete_candidates (updated_at DESC);

ALTER TABLE public.fs_featured_athlete_candidates ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_featured_athlete_candidates FROM anon, authenticated;
GRANT SELECT ON public.fs_featured_athlete_candidates TO authenticated;

DROP POLICY IF EXISTS subscriber_featured_athlete_candidates_read
ON public.fs_featured_athlete_candidates;
CREATE POLICY subscriber_featured_athlete_candidates_read
ON public.fs_featured_athlete_candidates
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');

CREATE OR REPLACE VIEW public.v_featured_athletes_public
WITH (security_barrier = true) AS
SELECT
    candidate_key,
    identity_id,
    fencer_id,
    display_name,
    country,
    weapon,
    score,
    reasons,
    rank_context,
    recency,
    selection_rank,
    updated_at
FROM public.fs_featured_athlete_candidates
WHERE selected = true;

REVOKE ALL ON public.v_featured_athletes_public FROM PUBLIC;
GRANT SELECT ON public.v_featured_athletes_public TO anon, authenticated;
