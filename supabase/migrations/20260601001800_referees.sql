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
