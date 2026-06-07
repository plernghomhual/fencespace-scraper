CREATE TABLE IF NOT EXISTS public.fs_referee_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key text NOT NULL UNIQUE,
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    event_id text,
    event_name text,
    bout_id text,
    bout_source_id text,
    referee_id uuid REFERENCES public.fs_referees(id) ON DELETE SET NULL,
    referee_fie_id text,
    referee_fie_license_id text,
    referee_name text,
    country text,
    role text,
    piste text,
    round text,
    source_url text NOT NULL,
    assignment_status text NOT NULL DEFAULT 'assigned',
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CHECK (assignment_status IN ('assigned', 'missing', 'blocked'))
);

CREATE INDEX IF NOT EXISTS idx_fs_referee_assignments_tournament_event
    ON public.fs_referee_assignments (tournament_id, event_id);

CREATE INDEX IF NOT EXISTS idx_fs_referee_assignments_bout
    ON public.fs_referee_assignments (bout_id, bout_source_id);

CREATE INDEX IF NOT EXISTS idx_fs_referee_assignments_referee_license
    ON public.fs_referee_assignments (referee_fie_license_id);

CREATE INDEX IF NOT EXISTS idx_fs_referee_assignments_referee_name
    ON public.fs_referee_assignments (referee_name);

CREATE INDEX IF NOT EXISTS idx_fs_referee_assignments_source_url
    ON public.fs_referee_assignments (source_url);

ALTER TABLE public.fs_referee_assignments ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_referee_assignments TO service_role;
