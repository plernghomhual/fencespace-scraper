CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_sponsorships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES public.fs_fencers(id),
    fencer_name text NOT NULL,
    fie_id text,
    country text,
    sponsor_brand text NOT NULL,
    normalized_brand text NOT NULL,
    category text NOT NULL,
    start_date date,
    end_date date,
    status text NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('active', 'expired', 'unknown')),
    evidence_text text NOT NULL,
    source_url text NOT NULL,
    source_type text NOT NULL,
    linked_equipment_brand text,
    confidence text NOT NULL DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fs_sponsorships_fencer_id_idx
    ON public.fs_sponsorships (fencer_id);

CREATE INDEX IF NOT EXISTS fs_sponsorships_normalized_brand_idx
    ON public.fs_sponsorships (normalized_brand);

CREATE INDEX IF NOT EXISTS fs_sponsorships_category_idx
    ON public.fs_sponsorships (category);

CREATE INDEX IF NOT EXISTS fs_sponsorships_status_idx
    ON public.fs_sponsorships (status);

CREATE INDEX IF NOT EXISTS fs_sponsorships_source_type_idx
    ON public.fs_sponsorships (source_type);

ALTER TABLE public.fs_sponsorships ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_sponsorships FROM anon, authenticated;
GRANT SELECT ON public.fs_sponsorships TO authenticated;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'fs_sponsorships'
          AND policyname = 'subscriber_select_fs_sponsorships'
    ) THEN
        CREATE POLICY subscriber_select_fs_sponsorships
        ON public.fs_sponsorships
        FOR SELECT
        TO authenticated
        USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
    END IF;
END $$;
