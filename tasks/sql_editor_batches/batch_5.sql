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

-- BEGIN 20260601_referees.sql
CREATE TABLE IF NOT EXISTS fs_referees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    fie_license_id text UNIQUE,
    category text,
    certification_level text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fs_coaches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    federation text,
    national_team_role text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fs_fencer_coach_relationship (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    coach_id uuid REFERENCES fs_coaches(id),
    start_date date,
    end_date date,
    current boolean DEFAULT true,
    metadata jsonb DEFAULT '{}',
    UNIQUE (fencer_id, coach_id)
);

CREATE INDEX IF NOT EXISTS fs_referees_country_idx
    ON fs_referees (country);

CREATE INDEX IF NOT EXISTS fs_referees_weapons_idx
    ON fs_referees USING gin (weapons);

CREATE INDEX IF NOT EXISTS fs_coaches_country_idx
    ON fs_coaches (country);

CREATE INDEX IF NOT EXISTS fs_coaches_federation_idx
    ON fs_coaches (federation);

CREATE INDEX IF NOT EXISTS fs_coaches_weapons_idx
    ON fs_coaches USING gin (weapons);

CREATE INDEX IF NOT EXISTS fs_fencer_coach_relationship_fencer_idx
    ON fs_fencer_coach_relationship (fencer_id);

CREATE INDEX IF NOT EXISTS fs_fencer_coach_relationship_coach_idx
    ON fs_fencer_coach_relationship (coach_id);
-- END 20260601_referees.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_referees.sql', now(), '5776b7939b3e45b81b501828c0bf951c2c481da990e503a0eba8338674c680f5', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_scholarships.sql
CREATE TABLE IF NOT EXISTS public.fs_college_scholarships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    college_name text NOT NULL,
    division text,
    conference text,
    weapons text[],
    gender_teams text[],
    roster_size integer,
    scholarship_slots integer,
    head_coach text,
    coach_email text,
    website text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (college_name)
);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_division_idx
    ON public.fs_college_scholarships (division);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_scraped_at_idx
    ON public.fs_college_scholarships (scraped_at);
-- END 20260601_scholarships.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_scholarships.sql', now(), '2b8388e27006c6e49b292229d40c18c301607a5f3b83e0a59fdd9370ef9068a2', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_social_media.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_fencer_social_media (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    platform text NOT NULL CHECK (platform IN ('instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')),
    handle text,
    url text NOT NULL,
    source text DEFAULT 'wikidata',
    verified boolean DEFAULT false,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    UNIQUE (fencer_id, platform)
);

CREATE INDEX IF NOT EXISTS fs_fencer_social_media_fencer_idx
    ON fs_fencer_social_media (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_social_media_platform_idx
    ON fs_fencer_social_media (platform);
-- END 20260601_social_media.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_social_media.sql', now(), 'af32ab25a70ad246d33a2c746724e0fefb3fbfc5d9852fd65b4769a6a6fc79c3', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_specialization.sql
CREATE TABLE IF NOT EXISTS public.fs_fencer_specialization (
    fencer_id               text            NOT NULL PRIMARY KEY,
    classification          text            NOT NULL,
    primary_weapon          text,
    weapons                 jsonb           NOT NULL DEFAULT '[]',
    total_results           integer         NOT NULL DEFAULT 0,
    total_competitions      integer         NOT NULL DEFAULT 0,
    ranked_results          integer         NOT NULL DEFAULT 0,
    avg_rank                double precision,
    best_rank               integer,
    worst_rank              integer,
    medal_count             integer         NOT NULL DEFAULT 0,
    medals_per_competition  double precision,
    per_weapon              jsonb           NOT NULL DEFAULT '{}',
    season_primary_weapons  jsonb           NOT NULL DEFAULT '{}',
    changed_primary_weapon  boolean         NOT NULL DEFAULT false,
    weapon_switches         jsonb           NOT NULL DEFAULT '[]',
    categories              jsonb           NOT NULL DEFAULT '[]',
    computed_at             timestamptz     NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_fencer_specialization ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fencer_specialization FROM anon, authenticated;
GRANT SELECT ON public.fs_fencer_specialization TO authenticated;

DROP POLICY IF EXISTS subscriber_fencer_specialization_read ON public.fs_fencer_specialization;
CREATE POLICY subscriber_fencer_specialization_read ON public.fs_fencer_specialization
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
-- END 20260601_specialization.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_specialization.sql', now(), 'dd23fea49ee564c4d90a67b982cfd40bedb5ce1033b5e61f6a15d7880f056b76', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;

-- BEGIN 20260601_strength_of_field.sql
CREATE TABLE IF NOT EXISTS public.fs_competition_strength (
    tournament_id uuid PRIMARY KEY REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    avg_world_rank numeric,
    top8_count integer NOT NULL DEFAULT 0 CHECK (top8_count >= 0),
    top16_count integer NOT NULL DEFAULT 0 CHECK (top16_count >= 0),
    total_fie_ranked integer NOT NULL DEFAULT 0 CHECK (total_fie_ranked >= 0),
    strength_score numeric,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (top8_count <= top16_count),
    CHECK (top16_count <= total_fie_ranked)
);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_score
ON public.fs_competition_strength (strength_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_fs_competition_strength_avg_rank
ON public.fs_competition_strength (avg_world_rank ASC NULLS LAST);
-- END 20260601_strength_of_field.sql

INSERT INTO public.fs_schema_migrations (filename, applied_at, hash, success)
VALUES ('20260601_strength_of_field.sql', now(), '6b739aaa3649e6cb9c3406450b0c8d19e10771916fb62ce9eb77d51a61713704', true)
ON CONFLICT (filename) DO UPDATE
SET applied_at = EXCLUDED.applied_at, hash = EXCLUDED.hash, success = EXCLUDED.success;
