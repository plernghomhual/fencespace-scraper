CREATE TABLE IF NOT EXISTS public.fs_event_photographers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_key text NOT NULL,
    name text,
    business text,
    website text,
    email text,
    public_contact text,
    regions text[] NOT NULL DEFAULT '{}',
    event_urls text[] NOT NULL DEFAULT '{}',
    tournament_ids uuid[] NOT NULL DEFAULT '{}',
    source_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (normalized_key),
    CONSTRAINT fs_event_photographers_identity_present CHECK (
        NULLIF(BTRIM(COALESCE(name, '')), '') IS NOT NULL
        OR NULLIF(BTRIM(COALESCE(business, '')), '') IS NOT NULL
    )
);

ALTER TABLE public.fs_event_photographers ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_business
    ON public.fs_event_photographers (business);

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_website
    ON public.fs_event_photographers (website);

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_regions
    ON public.fs_event_photographers USING gin (regions);

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_event_urls
    ON public.fs_event_photographers USING gin (event_urls);

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_tournament_ids
    ON public.fs_event_photographers USING gin (tournament_ids);

CREATE INDEX IF NOT EXISTS idx_fs_event_photographers_metadata
    ON public.fs_event_photographers USING gin (metadata);
