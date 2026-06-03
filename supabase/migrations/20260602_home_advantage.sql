CREATE TABLE IF NOT EXISTS public.fs_home_advantage_results (
    id text PRIMARY KEY,
    source_result_id text,
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_name text,
    country text NOT NULL,
    fencer_country text,
    tournament_country text,
    home_status text NOT NULL CHECK (home_status IN ('home', 'away', 'unknown')),
    classification_reason text NOT NULL,
    country_resolution_source text,
    country_resolution_reason text,
    weapon text,
    gender text,
    category text,
    competition_tier text,
    expected_placement numeric,
    actual_placement integer NOT NULL CHECK (actual_placement > 0),
    actual_medal text CHECK (
        actual_medal IS NULL OR actual_medal IN ('gold', 'silver', 'bronze')
    ),
    placement_delta numeric,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_home_advantage_results_source_result_unique UNIQUE (source_result_id)
);

CREATE TABLE IF NOT EXISTS public.fs_home_advantage_aggregates (
    id text PRIMARY KEY,
    country text NOT NULL,
    weapon text,
    gender text,
    category text,
    competition_tier text,
    home_status text NOT NULL CHECK (home_status IN ('home', 'away', 'unknown')),
    results_count integer NOT NULL DEFAULT 0 CHECK (results_count >= 0),
    avg_expected_placement numeric,
    avg_actual_placement numeric,
    avg_placement_delta numeric,
    medal_count integer NOT NULL DEFAULT 0 CHECK (medal_count >= 0),
    gold_count integer NOT NULL DEFAULT 0 CHECK (gold_count >= 0),
    silver_count integer NOT NULL DEFAULT 0 CHECK (silver_count >= 0),
    bronze_count integer NOT NULL DEFAULT 0 CHECK (bronze_count >= 0),
    unknown_count integer NOT NULL DEFAULT 0 CHECK (unknown_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.fs_home_advantage_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_home_advantage_aggregates ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_home_advantage_results_home_status
    ON public.fs_home_advantage_results (home_status);

CREATE INDEX IF NOT EXISTS idx_fs_home_advantage_results_country_status
    ON public.fs_home_advantage_results (country, home_status);

CREATE INDEX IF NOT EXISTS idx_fs_home_advantage_results_tournament
    ON public.fs_home_advantage_results (tournament_id);

CREATE INDEX IF NOT EXISTS idx_fs_home_advantage_results_fencer
    ON public.fs_home_advantage_results (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_home_advantage_aggregates_group
    ON public.fs_home_advantage_aggregates (
        country,
        weapon,
        gender,
        category,
        competition_tier,
        home_status
    );
