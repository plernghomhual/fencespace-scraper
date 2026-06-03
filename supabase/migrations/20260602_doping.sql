CREATE TABLE IF NOT EXISTS public.fs_anti_doping_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    athlete_name text NOT NULL,
    athlete_country text,
    record_date date,
    record_type text NOT NULL CHECK (
        record_type IN (
            'sanction',
            'potential_adrv',
            'appeal',
            'cleared_case',
            'test',
            'support_personnel'
        )
    ),
    case_status text,
    test_type text,
    sanction text,
    authority text NOT NULL,
    source_url text NOT NULL,
    source_kind text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_url, athlete_name, record_type, record_date)
);

ALTER TABLE public.fs_anti_doping_records ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_fs_anti_doping_records_fencer
    ON public.fs_anti_doping_records (fencer_id);

CREATE INDEX IF NOT EXISTS idx_fs_anti_doping_records_athlete
    ON public.fs_anti_doping_records (athlete_name, athlete_country);

CREATE INDEX IF NOT EXISTS idx_fs_anti_doping_records_type_date
    ON public.fs_anti_doping_records (record_type, record_date);

CREATE INDEX IF NOT EXISTS idx_fs_anti_doping_records_metadata
    ON public.fs_anti_doping_records USING gin (metadata);
