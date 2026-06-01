CREATE TABLE IF NOT EXISTS public.fs_fencer_transfers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id      uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    from_country   text NOT NULL,
    to_country     text NOT NULL,
    season         text NOT NULL,
    competition_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    source         text NOT NULL,
    confirmed      boolean NOT NULL DEFAULT false,
    metadata       jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fs_fencer_transfers_country_changed
        CHECK (from_country <> to_country)
);

ALTER TABLE public.fs_fencer_transfers ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_fencer_season_idx
    ON public.fs_fencer_transfers (fencer_id, season);

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_confirmed_idx
    ON public.fs_fencer_transfers (confirmed);

CREATE INDEX IF NOT EXISTS fs_fencer_transfers_competition_idx
    ON public.fs_fencer_transfers (competition_id)
    WHERE competition_id IS NOT NULL;
