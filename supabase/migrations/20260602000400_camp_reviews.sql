CREATE TABLE IF NOT EXISTS public.fs_training_camp_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    camp_id uuid,
    camp_name text NOT NULL,
    camp_organizer text,
    camp_start_date date,
    camp_end_date date,
    camp_city text,
    camp_country text,
    source text NOT NULL,
    rating numeric,
    review_count integer,
    review_text_snippet text,
    reviewer_hash text,
    source_url text NOT NULL,
    source_hash text NOT NULL,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (source, source_url, source_hash),
    CONSTRAINT fs_training_camp_reviews_rating_range CHECK (
        rating IS NULL OR (rating >= 0 AND rating <= 5)
    ),
    CONSTRAINT fs_training_camp_reviews_count_nonnegative CHECK (
        review_count IS NULL OR review_count >= 0
    )
);

ALTER TABLE public.fs_training_camp_reviews ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_training_camp_reviews_camp_id
    ON public.fs_training_camp_reviews (camp_id);

CREATE INDEX IF NOT EXISTS idx_fs_training_camp_reviews_camp_name
    ON public.fs_training_camp_reviews (camp_name);

CREATE INDEX IF NOT EXISTS idx_fs_training_camp_reviews_source
    ON public.fs_training_camp_reviews (source);

CREATE INDEX IF NOT EXISTS idx_fs_training_camp_reviews_scraped_at
    ON public.fs_training_camp_reviews (scraped_at DESC);
