CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_injury_absences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key text NOT NULL,
    identity_id uuid REFERENCES public.fs_fencer_identities(id),
    fencer_row_id uuid REFERENCES public.fs_fencers(id),
    fie_id text,
    fencer_name text NOT NULL,
    country text,
    event_name text,
    event_date date,
    status_type text NOT NULL CHECK (
        status_type IN ('injury', 'illness', 'suspension', 'personal_absence', 'unknown')
    ),
    summary text NOT NULL,
    source_excerpt text NOT NULL,
    source_url text NOT NULL,
    source_name text,
    source_site text NOT NULL,
    source_published_at timestamptz,
    confidence numeric NOT NULL DEFAULT 0.50 CHECK (confidence >= 0 AND confidence <= 1),
    metadata jsonb NOT NULL DEFAULT '{}',
    scraped_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_key)
);

CREATE INDEX IF NOT EXISTS fs_fencer_injury_absences_identity_idx
    ON public.fs_fencer_injury_absences(identity_id)
    WHERE identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_injury_absences_fencer_row_idx
    ON public.fs_fencer_injury_absences(fencer_row_id)
    WHERE fencer_row_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_injury_absences_status_idx
    ON public.fs_fencer_injury_absences(status_type);

CREATE INDEX IF NOT EXISTS fs_fencer_injury_absences_source_url_idx
    ON public.fs_fencer_injury_absences(source_url);

CREATE INDEX IF NOT EXISTS fs_fencer_injury_absences_event_date_idx
    ON public.fs_fencer_injury_absences(event_date)
    WHERE event_date IS NOT NULL;
