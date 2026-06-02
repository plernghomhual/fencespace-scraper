-- FenceSpace Supabase SQL Editor migration bundle
-- Generated from supabase/migrations with RLS migrations ordered last.
CREATE TABLE IF NOT EXISTS public.fs_schema_migrations (
    id serial PRIMARY KEY,
    filename text UNIQUE NOT NULL,
    applied_at timestamptz DEFAULT now(),
    hash text,
    success boolean DEFAULT true
);
ALTER TABLE public.fs_schema_migrations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.fs_schema_migrations FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.fs_schema_migrations FROM authenticated;
    END IF;
END $$;

-- BEGIN 20260529_national_fed_rankings.sql
CREATE TABLE IF NOT EXISTS fs_national_fed_rankings (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source      text NOT NULL,
    season      text NOT NULL,
    weapon      text NOT NULL,
    gender      text NOT NULL,
    category    text NOT NULL,
    rank        integer NOT NULL,
    name        text,
    country     text,
    club        text,
    points      numeric,
    fencer_id   uuid REFERENCES fs_fencers(id),
    fie_id      text,
    metadata    jsonb NOT NULL DEFAULT '{}',
    scraped_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_national_fed_rankings_unique
        UNIQUE (source, season, weapon, gender, category, rank)
);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_source_idx
    ON fs_national_fed_rankings (source, season);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_fencer_idx
    ON fs_national_fed_rankings (fencer_id)
    WHERE fencer_id IS NOT NULL;
-- END 20260529_national_fed_rankings.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260529_national_fed_rankings.sql', now(), '53c7980c650cf61c40ab7bb70253a377012a9de318487c5a49f61a8b43d67ce6', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601032714_country_club_rankings.sql
CREATE TABLE IF NOT EXISTS public.fs_country_depth (
    country             text NOT NULL,
    weapon              text NOT NULL,
    category            text NOT NULL,
    fencers_in_top16    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top16 >= 0),
    fencers_in_top32    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top32 >= 0),
    fencers_in_top64    integer NOT NULL DEFAULT 0 CHECK (fencers_in_top64 >= 0),
    total_ranked        integer NOT NULL DEFAULT 0 CHECK (total_ranked >= 0),
    avg_world_rank      double precision NOT NULL DEFAULT 0,
    updated_at          timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    PRIMARY KEY (country, weapon, category),
    CHECK (fencers_in_top16 <= fencers_in_top32),
    CHECK (fencers_in_top32 <= fencers_in_top64),
    CHECK (fencers_in_top64 <= total_ranked)
);

CREATE INDEX IF NOT EXISTS fs_country_depth_weapon_category_idx
    ON public.fs_country_depth (weapon, category);

CREATE INDEX IF NOT EXISTS fs_country_depth_top64_idx
    ON public.fs_country_depth (weapon, category, fencers_in_top64 DESC);

ALTER TABLE public.fs_country_depth ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.fs_club_rankings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club            text NOT NULL,
    country         text NOT NULL,
    weapon          text NOT NULL,
    total_fencers   integer NOT NULL DEFAULT 0 CHECK (total_fencers >= 0),
    avg_rank        double precision NOT NULL DEFAULT 0,
    total_points    double precision NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_club_rankings_unique UNIQUE (club, country, weapon)
);

CREATE INDEX IF NOT EXISTS fs_club_rankings_country_weapon_idx
    ON public.fs_club_rankings (country, weapon);

CREATE INDEX IF NOT EXISTS fs_club_rankings_points_idx
    ON public.fs_club_rankings (weapon, total_points DESC, avg_rank ASC);

ALTER TABLE public.fs_club_rankings ENABLE ROW LEVEL SECURITY;
-- END 20260601032714_country_club_rankings.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601032714_country_club_rankings.sql', now(), '3966a60d3d56bd9d8b4b1ae1e48f3280f9c5047198cf0ad584e222ec855a26eb', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601033334_wikipedia_bios.sql
ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS bio_text text,
    ADD COLUMN IF NOT EXISTS wikipedia_url text,
    ADD COLUMN IF NOT EXISTS birth_place text,
    ADD COLUMN IF NOT EXISTS nickname text,
    ADD COLUMN IF NOT EXISTS height text,
    ADD COLUMN IF NOT EXISTS weight text;
-- END 20260601033334_wikipedia_bios.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601033334_wikipedia_bios.sql', now(), '115a51bd3860fc1fa0ea91ee7abc931b4138d0f39252bf9ff649a9008d5114cd', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_api_keys.sql
-- API key table for fs_api.py authentication.
-- Read by service_role only (RLS enabled, no authenticated policy).

CREATE TABLE IF NOT EXISTS public.fs_api_keys (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text        NOT NULL UNIQUE,
    name        text,
    active      boolean     NOT NULL DEFAULT true,
    revoked     boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_api_keys ENABLE ROW LEVEL SECURITY;

-- No SELECT policy for authenticated/anon — service_role bypasses RLS.
REVOKE ALL ON public.fs_api_keys FROM anon, authenticated;
-- END 20260601_api_keys.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_api_keys.sql', now(), '0d414672314ff94ad30cf73332f1b4b5ea40a1aacfbbc51eaa29e9872ce47779', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_camps.sql
CREATE TABLE IF NOT EXISTS public.fs_training_camps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organizer text,
    city text,
    country text,
    start_date date,
    end_date date,
    coaches text[],
    cost numeric,
    currency text DEFAULT 'USD',
    weapons_covered text[],
    max_participants integer,
    source_url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (name, organizer, start_date, end_date),
    CONSTRAINT fs_training_camps_date_order CHECK (
        start_date IS NULL OR end_date IS NULL OR end_date >= start_date
    )
);

ALTER TABLE public.fs_training_camps ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_dates
    ON public.fs_training_camps (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_location
    ON public.fs_training_camps (country, city);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_weapons
    ON public.fs_training_camps USING gin (weapons_covered);
-- END 20260601_camps.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_camps.sql', now(), '9369f1d95cd26ccc602de8a80788124c90158bc16e4f412f4650cc0417cf2792', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
