CREATE TABLE IF NOT EXISTS public.fs_youth_talent_analytics (
    fencer_id            text PRIMARY KEY,
    age_band             text NOT NULL DEFAULT 'unknown',
    category             text NOT NULL DEFAULT 'Unknown',
    feature_summary      jsonb NOT NULL DEFAULT '{}',
    outlier_score        numeric(5,2) NOT NULL DEFAULT 0,
    label                text NOT NULL DEFAULT 'insufficient public evidence',
    confidence           text NOT NULL DEFAULT 'low',
    low_confidence_flags jsonb NOT NULL DEFAULT '[]',
    explanation          text NOT NULL,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_youth_talent_score_check
        CHECK (outlier_score >= 0 AND outlier_score <= 100),
    CONSTRAINT fs_youth_talent_label_check
        CHECK (
            label IN (
                'early-career outlier',
                'monitor with more public results',
                'insufficient public evidence'
            )
        ),
    CONSTRAINT fs_youth_talent_confidence_check
        CHECK (confidence IN ('high', 'medium', 'low'))
);

COMMENT ON TABLE public.fs_youth_talent_analytics IS
    'Privacy-conscious early-career analytics computed from public competition and ranking results only; conservative labels are not a prediction and exact birthdates or private age details are not stored.';

COMMENT ON COLUMN public.fs_youth_talent_analytics.age_band IS
    'Broad category-derived band such as youth, cadet, junior, u23, mixed-youth, or unknown.';

COMMENT ON COLUMN public.fs_youth_talent_analytics.feature_summary IS
    'Aggregated public result/ranking features and interpretation limits, without exact birthdates or private age attributes.';

COMMENT ON COLUMN public.fs_youth_talent_analytics.outlier_score IS
    '0-100 public-evidence score for early-career outlier detection; use with explanation and confidence flags.';

COMMENT ON COLUMN public.fs_youth_talent_analytics.explanation IS
    'Human-readable rationale and privacy/interpretation limits; not a prediction of future performance.';

ALTER TABLE public.fs_youth_talent_analytics ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_youth_talent_score_idx
    ON public.fs_youth_talent_analytics (outlier_score DESC);

CREATE INDEX IF NOT EXISTS fs_youth_talent_label_idx
    ON public.fs_youth_talent_analytics (label, confidence);

CREATE INDEX IF NOT EXISTS fs_youth_talent_updated_idx
    ON public.fs_youth_talent_analytics (updated_at DESC);
