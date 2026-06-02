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

-- BEGIN 20260601_equipment_reviews.sql
CREATE TABLE IF NOT EXISTS public.fs_equipment_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name text NOT NULL,
    brand text NOT NULL,
    category text,
    rating numeric(3,1),
    review_count integer,
    price numeric,
    currency text DEFAULT 'USD',
    source text,
    url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    CONSTRAINT fs_equipment_reviews_url_unique UNIQUE (url),
    CONSTRAINT fs_equipment_reviews_rating_check
        CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT fs_equipment_reviews_review_count_check
        CHECK (review_count IS NULL OR review_count >= 0),
    CONSTRAINT fs_equipment_reviews_price_check
        CHECK (price IS NULL OR price >= 0)
);

ALTER TABLE public.fs_equipment_reviews ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_reviews TO service_role;

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_source_idx
    ON public.fs_equipment_reviews (source, scraped_at DESC);

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_brand_category_idx
    ON public.fs_equipment_reviews (brand, category);
-- END 20260601_equipment_reviews.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_equipment_reviews.sql', now(), 'e22f12efcdad2a23d69e3b6b2ab84ba3c1d2e94f38c1f7d62147be408df0faf6', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_fencer_identities.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- fs_fencers.fie_id stores FIE's external athlete identifier as text/numeric
-- data, while fs_fencers.id is the Supabase UUID row identifier.
CREATE TABLE IF NOT EXISTS fs_fencer_identities (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name     text,
    country            text,
    fie_ids            text[] NOT NULL DEFAULT '{}',
    fs_fencer_row_ids  uuid[] NOT NULL DEFAULT '{}',
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_identities_has_rows
        CHECK (cardinality(fs_fencer_row_ids) > 0)
);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_country_idx
    ON fs_fencer_identities (country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_identities_fie_ids_idx
    ON fs_fencer_identities USING gin (fie_ids);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_row_ids_idx
    ON fs_fencer_identities USING gin (fs_fencer_row_ids);
-- END 20260601_fencer_identities.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_fencer_identities.sql', now(), 'cb2d3960a9dbe7483121d66557c59fb1889223ee6bcebe287f264a595dc2f705', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_head_to_head.sql
CREATE TABLE IF NOT EXISTS public.fs_head_to_head (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_a_id uuid REFERENCES public.fs_fencers(id),
    fencer_b_id uuid REFERENCES public.fs_fencers(id),
    weapon text NOT NULL,
    a_wins integer DEFAULT 0,
    b_wins integer DEFAULT 0,
    a_touches integer DEFAULT 0,
    b_touches integer DEFAULT 0,
    bouts_total integer DEFAULT 0,
    last_meeting_date date,
    last_winner_id uuid REFERENCES public.fs_fencers(id),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (fencer_a_id, fencer_b_id, weapon)
);
-- END 20260601_head_to_head.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_head_to_head.sql', now(), '8f763ce48a7da80682cba661487729ddd2cba6f789672b8c0d4655e20a96e892', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_longevity.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_longevity (
    fencer_id uuid PRIMARY KEY REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    first_competition_date date,
    last_competition_date date,
    first_season integer,
    last_season integer,
    career_years integer,
    competitions_per_season numeric(8,2),
    status text NOT NULL DEFAULT 'unknown',
    updated_at timestamptz DEFAULT now(),
    CHECK (career_years IS NULL OR career_years >= 0),
    CHECK (competitions_per_season IS NULL OR competitions_per_season >= 0),
    CHECK (status IN ('active', 'likely_retired', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_status
    ON public.fs_fencer_longevity(status);

CREATE INDEX IF NOT EXISTS idx_fs_fencer_longevity_last_competition
    ON public.fs_fencer_longevity(last_competition_date);

ALTER TABLE public.fs_fencer_longevity ENABLE ROW LEVEL SECURITY;
-- END 20260601_longevity.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_longevity.sql', now(), '79916553336ac34dc21e0f35bfc564e546f08b2d90e910f3f0061bcfb8ce00a1', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_medal_tables.sql
CREATE TABLE IF NOT EXISTS public.fs_medal_tables (
    id text PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN ('country', 'fencer', 'tier_country')),
    country text,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    tier text CHECK (tier IS NULL OR tier IN ('Olympics', 'Worlds', 'GP', 'WC', 'Continental')),
    gold integer NOT NULL DEFAULT 0 CHECK (gold >= 0),
    silver integer NOT NULL DEFAULT 0 CHECK (silver >= 0),
    bronze integer NOT NULL DEFAULT 0 CHECK (bronze >= 0),
    total integer NOT NULL DEFAULT 0 CHECK (total >= 0 AND total = gold + silver + bronze),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_medal_tables_scope_fields CHECK (
        (
            scope = 'country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NULL
        )
        OR (
            scope = 'fencer'
            AND country IS NULL
            AND fencer_id IS NOT NULL
            AND tier IS NULL
        )
        OR (
            scope = 'tier_country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_scope_total
    ON public.fs_medal_tables(scope, total DESC);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_country
    ON public.fs_medal_tables(country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_fencer_id
    ON public.fs_medal_tables(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_tier_country
    ON public.fs_medal_tables(tier, country)
    WHERE tier IS NOT NULL;

ALTER TABLE public.fs_medal_tables ENABLE ROW LEVEL SECURITY;
-- END 20260601_medal_tables.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_medal_tables.sql', now(), 'f7fd559b4cc1312145c60544aa90cf4bdd2e11cdf42325897a12558f98305d9d', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
