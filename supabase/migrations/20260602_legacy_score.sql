CREATE TABLE IF NOT EXISTS public.fs_fencer_legacy_scores (
    identity_id uuid PRIMARY KEY REFERENCES public.fs_fencer_identities(id) ON DELETE CASCADE,
    canonical_name text,
    country text,
    legacy_score numeric(12,2) NOT NULL DEFAULT 0 CHECK (legacy_score >= 0),
    medal_points numeric(12,2) NOT NULL DEFAULT 0 CHECK (medal_points >= 0),
    result_points numeric(12,2) NOT NULL DEFAULT 0 CHECK (result_points >= 0),
    competition_count integer NOT NULL DEFAULT 0 CHECK (competition_count >= 0),
    result_count integer NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    gold_medals integer NOT NULL DEFAULT 0 CHECK (gold_medals >= 0),
    silver_medals integer NOT NULL DEFAULT 0 CHECK (silver_medals >= 0),
    bronze_medals integer NOT NULL DEFAULT 0 CHECK (bronze_medals >= 0),
    individual_medals integer NOT NULL DEFAULT 0 CHECK (individual_medals >= 0),
    team_medals integer NOT NULL DEFAULT 0 CHECK (team_medals >= 0),
    score_components jsonb NOT NULL DEFAULT '{}'::jsonb,
    medal_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    tier_weights jsonb NOT NULL DEFAULT '{}'::jsonb,
    first_season integer,
    last_season integer,
    active_span_years integer,
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_fencer_legacy_scores_score_total
        CHECK (legacy_score = medal_points + result_points),
    CONSTRAINT fs_fencer_legacy_scores_medal_total
        CHECK (individual_medals + team_medals = gold_medals + silver_medals + bronze_medals),
    CONSTRAINT fs_fencer_legacy_scores_active_span
        CHECK (
            (first_season IS NULL AND last_season IS NULL AND active_span_years IS NULL)
            OR (
                first_season IS NOT NULL
                AND last_season IS NOT NULL
                AND last_season >= first_season
                AND active_span_years = last_season - first_season + 1
            )
        )
);

CREATE INDEX IF NOT EXISTS fs_fencer_legacy_scores_score_idx
    ON public.fs_fencer_legacy_scores (legacy_score DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_legacy_scores_country_score_idx
    ON public.fs_fencer_legacy_scores (country, legacy_score DESC)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_legacy_scores_updated_at_idx
    ON public.fs_fencer_legacy_scores (updated_at DESC);

ALTER TABLE public.fs_fencer_legacy_scores ENABLE ROW LEVEL SECURITY;
