CREATE TABLE IF NOT EXISTS public.fs_bout_anomalies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bout_id uuid REFERENCES public.fs_bouts(id) ON DELETE CASCADE,
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    anomaly_type text NOT NULL CHECK (
        anomaly_type IN (
            'scoreline_outlier',
            'ranking_result_delta',
            'repeated_unusual_pattern',
            'public_betting_data_mismatch'
        )
    ),
    score numeric(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    confidence_level text NOT NULL CHECK (confidence_level IN ('low', 'medium', 'high')),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence) = 'object'),
    model_version text NOT NULL,
    reviewed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_bout_anomalies_evidence_has_note
        CHECK (evidence ? 'integrity_note'),
    CONSTRAINT fs_bout_anomalies_unique_signal
        UNIQUE (bout_id, anomaly_type, model_version)
);

ALTER TABLE public.fs_bout_anomalies ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_bout_anomalies_review
ON public.fs_bout_anomalies (reviewed, score DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fs_bout_anomalies_tournament
ON public.fs_bout_anomalies (tournament_id, anomaly_type);

CREATE INDEX IF NOT EXISTS idx_fs_bout_anomalies_fencer
ON public.fs_bout_anomalies (fencer_id, anomaly_type);
