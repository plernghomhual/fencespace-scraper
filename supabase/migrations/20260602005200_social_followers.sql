CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_social_followers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_key text NOT NULL,
    fencer_identity_id uuid REFERENCES fs_fencer_identities(id) ON DELETE SET NULL,
    fencer_id uuid REFERENCES fs_fencers(id) ON DELETE SET NULL,
    platform text NOT NULL CHECK (
        platform IN ('mastodon', 'instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')
    ),
    handle text NOT NULL,
    url text NOT NULL,
    follower_count integer,
    following_count integer,
    source text NOT NULL,
    collected_at timestamptz NOT NULL DEFAULT now(),
    date_bucket date NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_key),
    CHECK (fencer_identity_id is not null or fencer_id is not null),
    CHECK (follower_count is null or follower_count >= 0),
    CHECK (following_count is null or following_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS fs_social_followers_snapshot_bucket_uidx
    ON fs_social_followers (
        COALESCE(fencer_identity_id, fencer_id),
        platform,
        lower(handle),
        date_bucket
    );

CREATE INDEX IF NOT EXISTS fs_social_followers_identity_idx
    ON fs_social_followers (fencer_identity_id)
    WHERE fencer_identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_social_followers_fencer_idx
    ON fs_social_followers (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_social_followers_platform_date_idx
    ON fs_social_followers (platform, date_bucket DESC);

ALTER TABLE fs_social_followers ENABLE ROW LEVEL SECURITY;
