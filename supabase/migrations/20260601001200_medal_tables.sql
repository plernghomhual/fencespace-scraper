CREATE TABLE IF NOT EXISTS public.fs_medal_tables (
    id text PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN ('country', 'fencer', 'tier_country')),
    country text,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    tier text CHECK (tier IS NULL OR tier IN ('Olympics', 'Worlds', 'GP', 'WC', 'Continental')),
    gold integer NOT NULL DEFAULT 0 CHECK (gold >= 0),
    silver integer NOT NULL DEFAULT 0 CHECK (silver >= 0),
    bronze integer NOT NULL DEFAULT 0 CHECK (bronze >= 0),
    total integer NOT NULL DEFAULT 0 CHECK (total >= 0 AND total = gold + silver + bronze),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_medal_tables_scope_fields CHECK (
        (
            scope = 'country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NULL
        )
        OR (
            scope = 'fencer'
            AND country IS NULL
            AND fencer_id IS NOT NULL
            AND tier IS NULL
        )
        OR (
            scope = 'tier_country'
            AND country IS NOT NULL
            AND fencer_id IS NULL
            AND tier IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_scope_total
    ON public.fs_medal_tables(scope, total DESC);

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_country
    ON public.fs_medal_tables(country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_fencer_id
    ON public.fs_medal_tables(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_medal_tables_tier_country
    ON public.fs_medal_tables(tier, country)
    WHERE tier IS NOT NULL;

ALTER TABLE public.fs_medal_tables ENABLE ROW LEVEL SECURITY;
