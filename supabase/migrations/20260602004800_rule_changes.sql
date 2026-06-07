CREATE TABLE IF NOT EXISTS public.fs_rule_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_key text NOT NULL UNIQUE,
    effective_date date,
    effective_season text,
    weapons_affected text[] NOT NULL DEFAULT ARRAY[]::text[],
    categories_affected text[] NOT NULL DEFAULT ARRAY[]::text[],
    rule_area text NOT NULL,
    summary text NOT NULL,
    source_url text NOT NULL,
    source_type text NOT NULL CHECK (
        source_type IN (
            'fie_rulebook',
            'fie_congress_decision',
            'federation_summary',
            'historical_archive',
            'manual_seed'
        )
    ),
    source_title text,
    evidence_quote text,
    affected_competition_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    affected_seasons text[] NOT NULL DEFAULT ARRAY[]::text[],
    impact_analysis_status text NOT NULL DEFAULT 'not_analyzed' CHECK (
        impact_analysis_status IN ('not_analyzed', 'tested_with_caveats')
    ),
    impact_summary text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_rule_changes_source_url_required CHECK (
        length(btrim(source_url)) > 0 AND source_url ~ '^https?://'
    ),
    CONSTRAINT fs_rule_changes_summary_required CHECK (length(btrim(summary)) > 0),
    CONSTRAINT fs_rule_changes_effective_required CHECK (
        effective_date IS NOT NULL OR effective_season IS NOT NULL
    ),
    CONSTRAINT fs_rule_changes_no_untested_impact_claims CHECK (
        impact_summary IS NULL OR impact_analysis_status = 'tested_with_caveats'
    )
);

ALTER TABLE public.fs_rule_changes ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_rule_changes_effective_date_idx
    ON public.fs_rule_changes (effective_date);

CREATE INDEX IF NOT EXISTS fs_rule_changes_effective_season_idx
    ON public.fs_rule_changes (effective_season);

CREATE INDEX IF NOT EXISTS fs_rule_changes_rule_area_idx
    ON public.fs_rule_changes (rule_area);

CREATE INDEX IF NOT EXISTS fs_rule_changes_source_type_idx
    ON public.fs_rule_changes (source_type);

CREATE INDEX IF NOT EXISTS fs_rule_changes_weapons_idx
    ON public.fs_rule_changes USING gin (weapons_affected);

CREATE INDEX IF NOT EXISTS fs_rule_changes_categories_idx
    ON public.fs_rule_changes USING gin (categories_affected);

CREATE INDEX IF NOT EXISTS fs_rule_changes_affected_seasons_idx
    ON public.fs_rule_changes USING gin (affected_seasons);
