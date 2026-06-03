CREATE TABLE IF NOT EXISTS public.fs_forum_discussions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    thread_id text NOT NULL,
    title text NOT NULL,
    url text NOT NULL,
    author_hash text,
    posted_at timestamptz,
    tags text[] DEFAULT '{}',
    related_fencer_ids bigint[] DEFAULT '{}',
    summary text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (source, thread_id),
    CONSTRAINT fs_forum_discussions_author_hash_format CHECK (
        author_hash IS NULL OR author_hash ~ '^sha256:[a-f0-9]{64}$'
    )
);

ALTER TABLE public.fs_forum_discussions ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_forum_discussions_source_posted
    ON public.fs_forum_discussions (source, posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_fs_forum_discussions_tags
    ON public.fs_forum_discussions USING gin (tags);

CREATE INDEX IF NOT EXISTS idx_fs_forum_discussions_related_fencers
    ON public.fs_forum_discussions USING gin (related_fencer_ids);

CREATE INDEX IF NOT EXISTS idx_fs_forum_discussions_metadata
    ON public.fs_forum_discussions USING gin (metadata);
