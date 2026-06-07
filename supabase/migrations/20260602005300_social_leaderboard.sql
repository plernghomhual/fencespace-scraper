CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_social_leaderboard (
    platform              text        NOT NULL,
    normalized_handle     text        NOT NULL,
    handle                text        NOT NULL,
    fencer_id             uuid        REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    url                   text,
    source_platform       text        NOT NULL,
    source                text,
    sources               jsonb       NOT NULL DEFAULT '[]',
    follower_count        integer,
    mention_count         integer     NOT NULL DEFAULT 0,
    follower_rank         integer,
    mention_rank          integer,
    collected_at          timestamptz,
    days_since_collected  integer,
    is_stale              boolean     NOT NULL DEFAULT true,
    stale_reason          text,
    computed_at           timestamptz NOT NULL DEFAULT now(),
    metadata              jsonb       NOT NULL DEFAULT '{}',
    PRIMARY KEY (platform, normalized_handle),
    CONSTRAINT fs_fencer_social_leaderboard_platform_check
        CHECK (platform IN ('instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')),
    CONSTRAINT fs_fencer_social_leaderboard_source_platform_check
        CHECK (source_platform IN ('instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')),
    CONSTRAINT fs_fencer_social_leaderboard_follower_count_check
        CHECK (follower_count IS NULL OR follower_count >= 0),
    CONSTRAINT fs_fencer_social_leaderboard_mention_count_check
        CHECK (mention_count >= 0),
    CONSTRAINT fs_fencer_social_leaderboard_follower_rank_check
        CHECK (follower_rank IS NULL OR follower_rank > 0),
    CONSTRAINT fs_fencer_social_leaderboard_mention_rank_check
        CHECK (mention_rank IS NULL OR mention_rank > 0),
    CONSTRAINT fs_fencer_social_leaderboard_days_check
        CHECK (days_since_collected IS NULL OR days_since_collected >= 0)
);

CREATE INDEX IF NOT EXISTS fs_fencer_social_leaderboard_followers_idx
    ON public.fs_fencer_social_leaderboard (platform, follower_rank)
    WHERE follower_rank IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_social_leaderboard_mentions_idx
    ON public.fs_fencer_social_leaderboard (platform, mention_rank)
    WHERE mention_rank IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_social_leaderboard_fencer_idx
    ON public.fs_fencer_social_leaderboard (fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_social_leaderboard_stale_idx
    ON public.fs_fencer_social_leaderboard (is_stale, collected_at);

ALTER TABLE public.fs_fencer_social_leaderboard ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fencer_social_leaderboard FROM anon, authenticated;
GRANT SELECT ON public.fs_fencer_social_leaderboard TO authenticated;

DROP POLICY IF EXISTS authenticated_social_leaderboard_read ON public.fs_fencer_social_leaderboard;
CREATE POLICY authenticated_social_leaderboard_read
ON public.fs_fencer_social_leaderboard
FOR SELECT TO authenticated
USING (true);
