CREATE TABLE IF NOT EXISTS public.fs_competition_details (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid UNIQUE REFERENCES public.fs_tournaments(id),
    format_type text,
    pool_size integer,
    de_rounds integer,
    entry_fee numeric,
    prize_pool numeric,
    currency text,
    participant_count integer,
    countries_represented integer,
    metadata jsonb DEFAULT '{}'::jsonb,
    scraped_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fs_competition_details_tournament_id_idx
    ON public.fs_competition_details (tournament_id);
