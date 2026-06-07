CREATE TABLE IF NOT EXISTS public.fs_coach_history (
    id text PRIMARY KEY,
    coach_id uuid REFERENCES public.fs_coaches(id),
    coach_name text NOT NULL,
    country text,
    team text,
    club text,
    role text NOT NULL,
    start_date date,
    end_date date,
    source_url text NOT NULL,
    source_type text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    scraped_at timestamptz DEFAULT now(),
    CONSTRAINT fs_coach_history_source_url_not_blank CHECK (btrim(source_url) <> ''),
    CONSTRAINT fs_coach_history_role_not_blank CHECK (btrim(role) <> ''),
    CONSTRAINT fs_coach_history_date_order CHECK (
        start_date IS NULL OR end_date IS NULL OR start_date <= end_date
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS fs_coach_history_source_unique_idx
    ON public.fs_coach_history (
        coach_name,
        role,
        source_url,
        COALESCE(start_date, DATE '0001-01-01'),
        COALESCE(end_date, DATE '9999-12-31')
    );

CREATE INDEX IF NOT EXISTS fs_coach_history_coach_id_idx
    ON public.fs_coach_history (coach_id);

CREATE INDEX IF NOT EXISTS fs_coach_history_country_idx
    ON public.fs_coach_history (country);

CREATE INDEX IF NOT EXISTS fs_coach_history_team_idx
    ON public.fs_coach_history (team);

CREATE INDEX IF NOT EXISTS fs_coach_history_source_url_idx
    ON public.fs_coach_history (source_url);
