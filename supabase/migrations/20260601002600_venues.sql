CREATE TABLE IF NOT EXISTS public.fs_venues (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name               text NOT NULL,
    city               text NOT NULL,
    country            text NOT NULL,
    latitude           double precision CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude          double precision CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    country_code       text,
    competitions_count integer NOT NULL DEFAULT 0 CHECK (competitions_count >= 0),
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_venues_unique UNIQUE (name, city, country)
);

CREATE INDEX IF NOT EXISTS fs_venues_city_country_idx
    ON public.fs_venues (city, country);

CREATE INDEX IF NOT EXISTS fs_venues_country_code_idx
    ON public.fs_venues (country_code)
    WHERE country_code IS NOT NULL;
