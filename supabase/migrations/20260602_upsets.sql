CREATE TABLE IF NOT EXISTS public.fs_upsets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    upset_key text NOT NULL UNIQUE,
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    event_id text,
    event_key text NOT NULL,
    weapon text,
    gender text,
    category text,
    upset_type text NOT NULL CHECK (
        upset_type IN (
            'round_upset',
            'high_rank_defeated',
            'lowest_seed_to_medal'
        )
    ),
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_name text,
    fencer_country text,
    opponent_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    opponent_name text,
    opponent_country text,
    fencer_seed integer CHECK (fencer_seed IS NULL OR fencer_seed > 0),
    opponent_seed integer CHECK (opponent_seed IS NULL OR opponent_seed > 0),
    fencer_rank integer CHECK (fencer_rank IS NULL OR fencer_rank > 0),
    opponent_rank integer CHECK (opponent_rank IS NULL OR opponent_rank > 0),
    seed_source text,
    rank_source text,
    round_name text,
    round_order integer,
    bout_order integer,
    expected_outcome text NOT NULL,
    actual_outcome text NOT NULL,
    upset_score numeric NOT NULL CHECK (upset_score >= 0),
    evidence jsonb NOT NULL DEFAULT '{}',
    metadata jsonb NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fs_upsets_tournament_event
ON public.fs_upsets (tournament_id, event_key);

CREATE INDEX IF NOT EXISTS idx_fs_upsets_type_score
ON public.fs_upsets (upset_type, upset_score DESC);

CREATE INDEX IF NOT EXISTS idx_fs_upsets_fencer
ON public.fs_upsets (fencer_id);

CREATE INDEX IF NOT EXISTS idx_fs_upsets_evidence
ON public.fs_upsets USING gin (evidence);
