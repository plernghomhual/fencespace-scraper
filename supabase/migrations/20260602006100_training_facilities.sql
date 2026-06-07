CREATE TABLE IF NOT EXISTS public.fs_training_facilities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    type text,
    address text,
    city text,
    country text,
    website text,
    contact_public jsonb DEFAULT '{}',
    weapons text[],
    programs text[],
    lat double precision,
    lon double precision,
    source_url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (name, address, country)
);

ALTER TABLE public.fs_training_facilities ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_training_facilities_country_city
    ON public.fs_training_facilities (country, city);

CREATE INDEX IF NOT EXISTS idx_fs_training_facilities_weapons
    ON public.fs_training_facilities USING gin (weapons);

CREATE INDEX IF NOT EXISTS idx_fs_training_facilities_programs
    ON public.fs_training_facilities USING gin (programs);

CREATE INDEX IF NOT EXISTS idx_fs_training_facilities_scraped_at
    ON public.fs_training_facilities (scraped_at DESC);
