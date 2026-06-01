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
