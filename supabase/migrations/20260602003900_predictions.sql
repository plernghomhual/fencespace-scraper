CREATE TABLE IF NOT EXISTS public.fs_predictions (
    id text PRIMARY KEY,
    target_event_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    target_event_key text NOT NULL,
    target_event_name text NOT NULL,
    target_event_date date,
    target_tier text CHECK (target_tier IS NULL OR target_tier IN ('Olympics', 'Worlds')),
    target_weapon text,
    target_category text,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fie_fencer_id text,
    fencer_name text,
    country text,
    prediction_rank integer NOT NULL CHECK (prediction_rank > 0),
    probability numeric(12,8) NOT NULL CHECK (probability >= 0 AND probability <= 1),
    score numeric(12,4) NOT NULL CHECK (score >= 0),
    factors jsonb NOT NULL DEFAULT '{}'::jsonb,
    model_version text NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    caveats text[] NOT NULL DEFAULT '{}'::text[],
    analytics_label text NOT NULL DEFAULT 'sports analytics - not betting advice or a guarantee'
        CHECK (analytics_label = 'sports analytics - not betting advice or a guarantee')
);

CREATE INDEX IF NOT EXISTS idx_fs_predictions_event_rank
    ON public.fs_predictions(target_event_key, prediction_rank);

CREATE INDEX IF NOT EXISTS idx_fs_predictions_fencer
    ON public.fs_predictions(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_predictions_generated_at
    ON public.fs_predictions(generated_at DESC);

ALTER TABLE public.fs_predictions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.fs_prediction_backtests (
    id text PRIMARY KEY,
    target_event_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    target_event_key text NOT NULL,
    target_event_name text NOT NULL,
    target_event_date date,
    target_weapon text,
    target_category text,
    model_version text NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    candidates_count integer NOT NULL DEFAULT 0 CHECK (candidates_count >= 0),
    actuals_count integer NOT NULL DEFAULT 0 CHECK (actuals_count >= 0),
    top1_hit boolean,
    podium_recall numeric(8,6) CHECK (podium_recall IS NULL OR (podium_recall >= 0 AND podium_recall <= 1)),
    mean_abs_rank_error numeric(12,4) CHECK (mean_abs_rank_error IS NULL OR mean_abs_rank_error >= 0),
    brier_score numeric(12,8) CHECK (brier_score IS NULL OR brier_score >= 0),
    expected_vs_actual jsonb NOT NULL DEFAULT '{}'::jsonb,
    caveats text[] NOT NULL DEFAULT '{}'::text[]
);

CREATE INDEX IF NOT EXISTS idx_fs_prediction_backtests_event
    ON public.fs_prediction_backtests(target_event_key);

CREATE INDEX IF NOT EXISTS idx_fs_prediction_backtests_generated_at
    ON public.fs_prediction_backtests(generated_at DESC);

ALTER TABLE public.fs_prediction_backtests ENABLE ROW LEVEL SECURITY;
