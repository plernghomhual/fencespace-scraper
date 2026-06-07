CREATE TABLE IF NOT EXISTS public.fs_fencer_handedness (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id),
    handedness text NOT NULL,
    source_url text NOT NULL,
    confidence numeric(3,2) NOT NULL DEFAULT 0,
    collected_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (fencer_id, source_url),
    CONSTRAINT fs_fencer_handedness_value_check CHECK (
        handedness IN ('left', 'right', 'ambidextrous', 'unknown')
    ),
    CONSTRAINT fs_fencer_handedness_confidence_check CHECK (
        confidence >= 0 AND confidence <= 1
    )
);

ALTER TABLE public.fs_fencer_handedness ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_fencer_handedness_fencer_id
    ON public.fs_fencer_handedness (fencer_id);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_handedness_handedness
    ON public.fs_fencer_handedness (handedness);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_handedness_collected_at
    ON public.fs_fencer_handedness (collected_at);
