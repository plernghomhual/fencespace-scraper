CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_social_feed (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform text NOT NULL CHECK (platform IN ('bluesky', 'mastodon', 'x', 'reddit', 'other')),
    post_id text NOT NULL,
    author text,
    url text NOT NULL,
    text_excerpt text CHECK (text_excerpt IS NULL OR char_length(text_excerpt) <= 500),
    hashtags text[] DEFAULT '{}',
    language text,
    related_fencer_ids uuid[] DEFAULT '{}',
    tournament_id uuid REFERENCES fs_tournaments(id),
    posted_at timestamptz NOT NULL,
    source text NOT NULL,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (platform, post_id)
);

CREATE INDEX IF NOT EXISTS fs_social_feed_posted_at_idx
    ON fs_social_feed (posted_at DESC);

CREATE INDEX IF NOT EXISTS fs_social_feed_hashtags_idx
    ON fs_social_feed USING gin (hashtags);

CREATE INDEX IF NOT EXISTS fs_social_feed_related_fencer_ids_idx
    ON fs_social_feed USING gin (related_fencer_ids);

CREATE INDEX IF NOT EXISTS fs_social_feed_tournament_idx
    ON fs_social_feed (tournament_id)
    WHERE tournament_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_social_feed_source_idx
    ON fs_social_feed (source);
