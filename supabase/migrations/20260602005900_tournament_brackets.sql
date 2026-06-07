CREATE TABLE IF NOT EXISTS public.fs_tournament_brackets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    event_id text,
    event_key text NOT NULL,
    weapon text,
    gender text,
    category text,
    round_name text NOT NULL,
    round_size integer,
    round_order integer NOT NULL,
    bout_order integer NOT NULL,
    bracket_key text NOT NULL,
    fencer_a_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_a_name text,
    fencer_a_country text,
    seed_a integer,
    fencer_a_seed integer GENERATED ALWAYS AS (seed_a) STORED,
    fencer_b_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fencer_b_name text,
    fencer_b_country text,
    seed_b integer,
    fencer_b_seed integer GENERATED ALWAYS AS (seed_b) STORED,
    score_a integer,
    score_b integer,
    scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    winner_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    piste text,
    source text NOT NULL DEFAULT 'unknown',
    source_url text,
    is_bye boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_tournament_brackets_recompute_key
        UNIQUE (tournament_id, event_key, round_order, bout_order),
    CONSTRAINT fs_tournament_brackets_bracket_key_unique
        UNIQUE (bracket_key),
    CONSTRAINT fs_tournament_brackets_round_order_positive
        CHECK (round_order > 0),
    CONSTRAINT fs_tournament_brackets_bout_order_positive
        CHECK (bout_order > 0),
    CONSTRAINT fs_tournament_brackets_round_size_positive
        CHECK (round_size IS NULL OR round_size > 0),
    CONSTRAINT fs_tournament_brackets_score_a_nonnegative
        CHECK (score_a IS NULL OR score_a >= 0),
    CONSTRAINT fs_tournament_brackets_score_b_nonnegative
        CHECK (score_b IS NULL OR score_b >= 0),
    CONSTRAINT fs_tournament_brackets_seed_a_positive
        CHECK (seed_a IS NULL OR seed_a > 0),
    CONSTRAINT fs_tournament_brackets_seed_b_positive
        CHECK (seed_b IS NULL OR seed_b > 0)
);

ALTER TABLE public.fs_tournament_brackets ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_tournament_brackets_tournament_round
    ON public.fs_tournament_brackets (tournament_id, round_order, bout_order);

CREATE INDEX IF NOT EXISTS idx_fs_tournament_brackets_tournament_event_id
    ON public.fs_tournament_brackets (tournament_id, event_id);

CREATE INDEX IF NOT EXISTS idx_fs_tournament_brackets_tournament_filters
    ON public.fs_tournament_brackets (tournament_id, weapon, gender, category);

CREATE INDEX IF NOT EXISTS idx_fs_tournament_brackets_updated_at
    ON public.fs_tournament_brackets (updated_at);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_tournament_brackets TO service_role;
