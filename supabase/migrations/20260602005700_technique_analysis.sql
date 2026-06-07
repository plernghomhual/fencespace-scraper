CREATE TABLE IF NOT EXISTS public.fs_fencer_technique_analysis (
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    weapon text NOT NULL,
    pattern_summary text NOT NULL,
    strengths jsonb NOT NULL DEFAULT '[]'::jsonb,
    weaknesses jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence text NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_technique_analysis_unique
        UNIQUE (fencer_id, weapon)
);

ALTER TABLE public.fs_fencer_technique_analysis ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_technique_analysis_confidence_idx
    ON public.fs_fencer_technique_analysis (confidence);

CREATE INDEX IF NOT EXISTS fs_fencer_technique_analysis_updated_idx
    ON public.fs_fencer_technique_analysis (updated_at DESC);
