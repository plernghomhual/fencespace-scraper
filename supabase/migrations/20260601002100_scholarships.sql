CREATE TABLE IF NOT EXISTS public.fs_college_scholarships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    college_name text NOT NULL,
    division text,
    conference text,
    weapons text[],
    gender_teams text[],
    roster_size integer,
    scholarship_slots integer,
    head_coach text,
    coach_email text,
    website text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (college_name)
);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_division_idx
    ON public.fs_college_scholarships (division);

CREATE INDEX IF NOT EXISTS fs_college_scholarships_scraped_at_idx
    ON public.fs_college_scholarships (scraped_at);
