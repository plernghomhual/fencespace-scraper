CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Headshot duplicate candidates are for manual review only.
-- Privacy limitation: image hashes and face-recognition distances can still be
-- sensitive biometric signals. This table must not store raw images or face
-- embeddings, and candidates must not be used to auto-merge identities or
-- delete images.
CREATE TABLE IF NOT EXISTS public.fs_headshot_duplicate_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_key text NOT NULL UNIQUE,
    source_fencer_a_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE RESTRICT,
    source_fencer_b_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE RESTRICT,
    source_image_a_id text NOT NULL,
    source_image_b_id text NOT NULL,
    image_a_url text,
    image_b_url text,
    match_type text NOT NULL CHECK (
        match_type IN (
            'identical_url',
            'identical_local_path',
            'content_hash',
            'perceptual_hash',
            'face_embedding'
        )
    ),
    confidence numeric(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'confirmed_duplicate', 'rejected', 'needs_more_evidence')
    ),
    privacy_notes text NOT NULL DEFAULT
        'Manual review required. Hashes and optional face matching can be wrong and privacy-sensitive; do not auto-merge identities or delete images from this table.',
    reviewer_id uuid,
    reviewed_at timestamptz,
    reviewer_notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_headshot_duplicate_reviews_distinct_fencers
        CHECK (source_fencer_a_id <> source_fencer_b_id)
);

CREATE INDEX IF NOT EXISTS fs_headshot_duplicate_reviews_status_idx
    ON public.fs_headshot_duplicate_reviews (status, confidence DESC);

CREATE INDEX IF NOT EXISTS fs_headshot_duplicate_reviews_source_a_idx
    ON public.fs_headshot_duplicate_reviews (source_fencer_a_id);

CREATE INDEX IF NOT EXISTS fs_headshot_duplicate_reviews_source_b_idx
    ON public.fs_headshot_duplicate_reviews (source_fencer_b_id);

CREATE INDEX IF NOT EXISTS fs_headshot_duplicate_reviews_match_type_idx
    ON public.fs_headshot_duplicate_reviews (match_type);

COMMENT ON TABLE public.fs_headshot_duplicate_reviews IS
    'Privacy-sensitive manual review queue for possible duplicate fencer headshots. Rows are evidence only and must not trigger automatic identity merges or image deletion.';

COMMENT ON COLUMN public.fs_headshot_duplicate_reviews.confidence IS
    'Heuristic confidence score from URL, content hash, perceptual hash, and optional face embedding evidence. Human review remains required.';

COMMENT ON COLUMN public.fs_headshot_duplicate_reviews.evidence IS
    'Auditable source metadata, hash distances, source image IDs, and matcher details. Do not store raw images or face embeddings.';

COMMENT ON COLUMN public.fs_headshot_duplicate_reviews.status IS
    'Manual review workflow status. pending rows require inspection before any downstream action.';

ALTER TABLE public.fs_headshot_duplicate_reviews ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_headshot_duplicate_reviews FROM anon, authenticated;
