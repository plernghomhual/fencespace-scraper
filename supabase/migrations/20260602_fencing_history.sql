CREATE TABLE IF NOT EXISTS public.fs_fencing_history_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date date,
    event_year integer NOT NULL,
    category text NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    affected_weapons text[] NOT NULL DEFAULT '{}',
    source_url text NOT NULL,
    confidence numeric NOT NULL DEFAULT 0.75,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (category, event_year, title),
    CONSTRAINT fs_fencing_history_year_check CHECK (
        event_year BETWEEN 1200 AND 2100
    ),
    CONSTRAINT fs_fencing_history_category_check CHECK (
        category IN ('governance', 'rule_change', 'equipment', 'scoring_timing')
    ),
    CONSTRAINT fs_fencing_history_title_check CHECK (
        length(btrim(title)) > 0
    ),
    CONSTRAINT fs_fencing_history_description_check CHECK (
        length(btrim(description)) > 0
    ),
    CONSTRAINT fs_fencing_history_source_url_check CHECK (
        source_url ~* '^https?://'
    ),
    CONSTRAINT fs_fencing_history_confidence_check CHECK (
        confidence >= 0 AND confidence <= 1
    )
);

ALTER TABLE public.fs_fencing_history_events ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencing_history_events_year_idx
    ON public.fs_fencing_history_events (event_year, event_date);

CREATE INDEX IF NOT EXISTS fs_fencing_history_events_category_idx
    ON public.fs_fencing_history_events (category);

CREATE INDEX IF NOT EXISTS fs_fencing_history_events_weapons_idx
    ON public.fs_fencing_history_events USING gin (affected_weapons);

CREATE INDEX IF NOT EXISTS fs_fencing_history_events_scraped_at_idx
    ON public.fs_fencing_history_events (scraped_at);
