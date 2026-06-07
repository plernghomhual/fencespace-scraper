CREATE TABLE IF NOT EXISTS public.fs_fencing_stores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    brand text,
    source text NOT NULL,
    website text,
    city text,
    country text,
    address text,
    latitude numeric,
    longitude numeric,
    phone text,
    email text,
    source_url text,
    dedupe_key text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dedupe_key),
    CONSTRAINT fs_fencing_stores_latitude_range CHECK (
        latitude IS NULL OR (latitude >= -90 AND latitude <= 90)
    ),
    CONSTRAINT fs_fencing_stores_longitude_range CHECK (
        longitude IS NULL OR (longitude >= -180 AND longitude <= 180)
    )
);

ALTER TABLE public.fs_fencing_stores ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_fencing_stores_country_city
    ON public.fs_fencing_stores (country, city);

CREATE INDEX IF NOT EXISTS idx_fs_fencing_stores_source
    ON public.fs_fencing_stores (source);

CREATE INDEX IF NOT EXISTS idx_fs_fencing_stores_scraped_at
    ON public.fs_fencing_stores (scraped_at);
