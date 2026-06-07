CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencing_videos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform text NOT NULL DEFAULT 'youtube'
        CHECK (platform IN ('youtube')),
    video_id text NOT NULL,
    title text NOT NULL,
    channel text,
    published_at timestamptz,
    url text NOT NULL,
    related_fencer_ids uuid[] DEFAULT '{}',
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    tags text[] DEFAULT '{}',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (video_id)
);

ALTER TABLE public.fs_fencing_videos ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_fencing_videos TO service_role;

CREATE INDEX IF NOT EXISTS fs_fencing_videos_platform_video_idx
    ON public.fs_fencing_videos (platform, video_id);

CREATE INDEX IF NOT EXISTS fs_fencing_videos_published_at_idx
    ON public.fs_fencing_videos (published_at DESC);

CREATE INDEX IF NOT EXISTS fs_fencing_videos_tournament_id_idx
    ON public.fs_fencing_videos (tournament_id)
    WHERE tournament_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencing_videos_related_fencer_ids_idx
    ON public.fs_fencing_videos USING gin (related_fencer_ids);

CREATE INDEX IF NOT EXISTS fs_fencing_videos_tags_idx
    ON public.fs_fencing_videos USING gin (tags);
