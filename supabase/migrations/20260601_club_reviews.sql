CREATE TABLE IF NOT EXISTS public.fs_club_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_name text NOT NULL,
    normalized_club_name text NOT NULL,
    city text NOT NULL,
    country text NOT NULL,
    source text NOT NULL,
    rating numeric,
    review_count integer,
    review_summary text,
    source_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_club_reviews_rating_check
        CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT fs_club_reviews_review_count_check
        CHECK (review_count IS NULL OR review_count >= 0),
    CONSTRAINT fs_club_reviews_unique_source
        UNIQUE (normalized_club_name, city, country, source)
);

CREATE INDEX IF NOT EXISTS fs_club_reviews_lookup_idx
    ON public.fs_club_reviews (normalized_club_name, city, country);

CREATE INDEX IF NOT EXISTS fs_club_reviews_source_idx
    ON public.fs_club_reviews (source, scraped_at DESC);
