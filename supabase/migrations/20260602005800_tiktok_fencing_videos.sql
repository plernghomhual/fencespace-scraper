CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_tiktok_fencing_videos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform text NOT NULL DEFAULT 'tiktok' CHECK (platform = 'tiktok'),
    video_id text NOT NULL,
    url text NOT NULL,
    creator text,
    creator_handle text,
    caption_snippet text,
    posted_at timestamptz,
    metrics jsonb DEFAULT '{}',
    related_fencers jsonb DEFAULT '[]',
    targets jsonb DEFAULT '[]',
    source text DEFAULT 'tiktok_provider',
    provider text,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (platform, video_id)
);

CREATE INDEX IF NOT EXISTS fs_tiktok_fencing_videos_posted_idx
    ON fs_tiktok_fencing_videos (posted_at DESC)
    WHERE posted_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_tiktok_fencing_videos_creator_idx
    ON fs_tiktok_fencing_videos (creator_handle)
    WHERE creator_handle IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_tiktok_fencing_videos_related_fencers_idx
    ON fs_tiktok_fencing_videos USING gin (related_fencers);

ALTER TABLE public.fs_tiktok_fencing_videos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_tiktok_fencing_videos FROM anon, authenticated;
