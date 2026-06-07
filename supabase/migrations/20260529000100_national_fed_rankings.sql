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
