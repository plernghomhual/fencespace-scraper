CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    source_id text NOT NULL,
    name text NOT NULL,
    brand text NOT NULL,
    category text,
    weapon text,
    price numeric,
    currency text DEFAULT 'USD',
    image_url text,
    product_url text NOT NULL,
    stock_status text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT fs_products_source_id_unique UNIQUE (source, source_id),
    CONSTRAINT fs_products_price_check CHECK (price IS NULL OR price >= 0),
    CONSTRAINT fs_products_currency_check CHECK (
        currency IS NULL OR currency ~ '^[A-Z]{3}$'
    )
);

ALTER TABLE public.fs_products ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_products TO service_role;

CREATE INDEX IF NOT EXISTS fs_products_source_scraped_at_idx
    ON public.fs_products (source, scraped_at DESC);

CREATE INDEX IF NOT EXISTS fs_products_category_weapon_idx
    ON public.fs_products (category, weapon);

CREATE INDEX IF NOT EXISTS fs_products_brand_idx
    ON public.fs_products (brand);

CREATE INDEX IF NOT EXISTS fs_products_product_url_idx
    ON public.fs_products (product_url);
