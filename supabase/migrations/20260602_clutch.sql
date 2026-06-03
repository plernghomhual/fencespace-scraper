CREATE TABLE IF NOT EXISTS public.fs_fencer_clutch_metrics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    fie_id text,
    fencer_name text,
    country text,
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    event_name text NOT NULL,
    weapon text,
    category text,
    pool_performance numeric(10,4) NOT NULL,
    elimination_performance numeric(10,4) NOT NULL,
    expected_result numeric(10,4) NOT NULL,
    actual_result numeric(10,4) NOT NULL,
    delta numeric(10,4) NOT NULL,
    confidence numeric(6,4) NOT NULL,
    pool_bouts integer NOT NULL DEFAULT 0 CHECK (pool_bouts >= 0),
    elimination_bouts integer NOT NULL DEFAULT 0 CHECK (elimination_bouts >= 0),
    rank_value integer,
    rank_source text,
    historical_performance numeric(10,4),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_clutch_metrics_unique
        UNIQUE (fencer_id, tournament_id),
    CONSTRAINT fs_fencer_clutch_metrics_score_bounds
        CHECK (
            pool_performance BETWEEN 0 AND 1
            AND elimination_performance BETWEEN 0 AND 1
            AND expected_result BETWEEN 0 AND 1
            AND actual_result BETWEEN 0 AND 1
            AND confidence BETWEEN 0 AND 1
        )
);

ALTER TABLE public.fs_fencer_clutch_metrics ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_clutch_metrics_delta_idx
    ON public.fs_fencer_clutch_metrics (delta DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_clutch_metrics_event_idx
    ON public.fs_fencer_clutch_metrics (tournament_id, confidence DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_clutch_metrics_fencer_idx
    ON public.fs_fencer_clutch_metrics (fencer_id, updated_at DESC);
