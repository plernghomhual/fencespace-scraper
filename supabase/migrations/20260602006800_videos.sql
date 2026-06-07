CREATE TABLE IF NOT EXISTS public.fs_videos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    video_id text NOT NULL,
    title text NOT NULL,
    channel text,
    url text NOT NULL,
    thumbnail text,
    published_at timestamptz,
    duration text,
    related_fencer_ids uuid[] NOT NULL DEFAULT '{}',
    related_tournament_ids uuid[] NOT NULL DEFAULT '{}',
    tags text[] NOT NULL DEFAULT '{}',
    source text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, video_id)
);

ALTER TABLE public.fs_videos ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_videos_provider_published_at_idx
    ON public.fs_videos (provider, published_at DESC);

CREATE INDEX IF NOT EXISTS fs_videos_related_fencer_ids_idx
    ON public.fs_videos USING gin (related_fencer_ids);

CREATE INDEX IF NOT EXISTS fs_videos_related_tournament_ids_idx
    ON public.fs_videos USING gin (related_tournament_ids);

CREATE INDEX IF NOT EXISTS fs_videos_tags_idx
    ON public.fs_videos USING gin (tags);
