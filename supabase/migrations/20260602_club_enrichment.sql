CREATE TABLE IF NOT EXISTS public.fs_club_enrichment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_name text NOT NULL,
    normalized_club_name text NOT NULL,
    country text NOT NULL,
    website text,
    founding_date text,
    history_summary text,
    notable_alumni jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    enriched_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_club_enrichment_unique
        UNIQUE (normalized_club_name, country),
    CONSTRAINT fs_club_enrichment_alumni_array
        CHECK (jsonb_typeof(notable_alumni) = 'array'),
    CONSTRAINT fs_club_enrichment_source_urls_array
        CHECK (jsonb_typeof(source_urls) = 'array'),
    CONSTRAINT fs_club_enrichment_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS fs_club_enrichment_country_idx
    ON public.fs_club_enrichment (country);

CREATE INDEX IF NOT EXISTS fs_club_enrichment_normalized_idx
    ON public.fs_club_enrichment (normalized_club_name);

ALTER TABLE public.fs_club_enrichment ENABLE ROW LEVEL SECURITY;
