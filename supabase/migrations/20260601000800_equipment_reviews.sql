CREATE TABLE IF NOT EXISTS public.fs_equipment_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name text NOT NULL,
    brand text NOT NULL,
    category text,
    rating numeric(3,1),
    review_count integer,
    price numeric,
    currency text DEFAULT 'USD',
    source text,
    url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    CONSTRAINT fs_equipment_reviews_url_unique UNIQUE (url),
    CONSTRAINT fs_equipment_reviews_rating_check
        CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT fs_equipment_reviews_review_count_check
        CHECK (review_count IS NULL OR review_count >= 0),
    CONSTRAINT fs_equipment_reviews_price_check
        CHECK (price IS NULL OR price >= 0)
);

ALTER TABLE public.fs_equipment_reviews ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_reviews TO service_role;

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_source_idx
    ON public.fs_equipment_reviews (source, scraped_at DESC);

CREATE INDEX IF NOT EXISTS fs_equipment_reviews_brand_category_idx
    ON public.fs_equipment_reviews (brand, category);
