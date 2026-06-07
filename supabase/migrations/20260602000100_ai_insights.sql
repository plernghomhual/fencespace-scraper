CREATE TABLE IF NOT EXISTS public.fs_ai_insights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    insight_type text NOT NULL,
    summary text NOT NULL CHECK (length(trim(summary)) > 0),
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(evidence_json) = 'object'),
    confidence numeric(4,3) NOT NULL
        CHECK (confidence >= 0 AND confidence <= 1),
    provider text NOT NULL DEFAULT 'rules',
    model text,
    rule_version text,
    generated_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT fs_ai_insights_entity_type_check
        CHECK (entity_type IN ('fencer', 'fencer_pair')),
    CONSTRAINT fs_ai_insights_type_check
        CHECK (insight_type IN ('performance_summary', 'fencer_comparison')),
    CONSTRAINT fs_ai_insights_unique
        UNIQUE (entity_type, entity_id, insight_type)
);

ALTER TABLE public.fs_ai_insights ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_ai_insights_entity_idx
    ON public.fs_ai_insights (entity_type, insight_type, generated_at DESC);

CREATE INDEX IF NOT EXISTS fs_ai_insights_generated_idx
    ON public.fs_ai_insights (generated_at DESC);

CREATE INDEX IF NOT EXISTS fs_ai_insights_evidence_gin_idx
    ON public.fs_ai_insights USING gin (evidence_json);

CREATE INDEX IF NOT EXISTS fs_ai_insights_metadata_gin_idx
    ON public.fs_ai_insights USING gin (metadata);

COMMENT ON TABLE public.fs_ai_insights IS
    'Deterministic, evidence-backed product insight summaries for fencing entities.';

COMMENT ON COLUMN public.fs_ai_insights.evidence_json IS
    'Object containing sentence-level evidence, source tables, and cited values for the summary.';
