CREATE TABLE IF NOT EXISTS public.fs_secondhand_equipment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    listing_id text NOT NULL,
    title text NOT NULL,
    category text,
    weapon text,
    price numeric,
    currency text,
    location text,
    listing_url text NOT NULL,
    posted_at timestamptz,
    status text DEFAULT 'active',
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (source, listing_id),
    CONSTRAINT fs_secondhand_equipment_weapon_check CHECK (
        weapon IS NULL OR weapon IN ('epee', 'foil', 'sabre')
    ),
    CONSTRAINT fs_secondhand_equipment_category_check CHECK (
        category IS NULL OR category IN (
            'weapon',
            'protective_gear',
            'uniform',
            'scoring_equipment',
            'bag_storage',
            'other'
        )
    ),
    CONSTRAINT fs_secondhand_equipment_status_check CHECK (
        status IS NULL OR status IN ('active', 'sold', 'expired', 'unknown')
    )
);

ALTER TABLE public.fs_secondhand_equipment ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_secondhand_equipment_source_status
    ON public.fs_secondhand_equipment (source, status);

CREATE INDEX IF NOT EXISTS idx_fs_secondhand_equipment_category_weapon
    ON public.fs_secondhand_equipment (category, weapon);

CREATE INDEX IF NOT EXISTS idx_fs_secondhand_equipment_scraped_at
    ON public.fs_secondhand_equipment (scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_fs_secondhand_equipment_listing_url
    ON public.fs_secondhand_equipment (listing_url);
