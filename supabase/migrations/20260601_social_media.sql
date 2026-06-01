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
