ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS national_rank integer;

ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS national_rank_points numeric;

ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS national_rank_source text;

ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS national_rank_season text;

CREATE INDEX IF NOT EXISTS fs_fencers_national_rank_idx
    ON public.fs_fencers (national_rank_source, national_rank_season, national_rank)
    WHERE national_rank IS NOT NULL;
