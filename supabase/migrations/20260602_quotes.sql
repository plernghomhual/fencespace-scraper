CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_quotes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_hash text NOT NULL,
    quote_excerpt text NOT NULL CHECK (char_length(quote_excerpt) <= 320),
    speaker text NOT NULL,
    fencer_id uuid REFERENCES public.fs_fencers(id),
    event text,
    tournament text,
    source text NOT NULL,
    source_site text NOT NULL,
    source_title text NOT NULL,
    source_url text NOT NULL,
    published_at timestamptz,
    language text NOT NULL DEFAULT 'unknown',
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (quote_hash)
);

CREATE INDEX IF NOT EXISTS idx_fs_quotes_fencer
    ON public.fs_quotes (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_quotes_source_url
    ON public.fs_quotes (source_url);

CREATE INDEX IF NOT EXISTS idx_fs_quotes_published_at
    ON public.fs_quotes (published_at);

ALTER TABLE public.fs_quotes ENABLE ROW LEVEL SECURITY;
