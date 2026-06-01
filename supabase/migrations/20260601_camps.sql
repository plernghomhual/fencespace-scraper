CREATE TABLE IF NOT EXISTS public.fs_training_camps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organizer text,
    city text,
    country text,
    start_date date,
    end_date date,
    coaches text[],
    cost numeric,
    currency text DEFAULT 'USD',
    weapons_covered text[],
    max_participants integer,
    source_url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    UNIQUE (name, organizer, start_date, end_date),
    CONSTRAINT fs_training_camps_date_order CHECK (
        start_date IS NULL OR end_date IS NULL OR end_date >= start_date
    )
);

ALTER TABLE public.fs_training_camps ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_dates
    ON public.fs_training_camps (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_location
    ON public.fs_training_camps (country, city);

CREATE INDEX IF NOT EXISTS idx_fs_training_camps_weapons
    ON public.fs_training_camps USING gin (weapons_covered);
