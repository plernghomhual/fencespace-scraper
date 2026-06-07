ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS height integer,
    ADD COLUMN IF NOT EXISTS weight integer,
    ADD COLUMN IF NOT EXISTS reach integer;

COMMENT ON COLUMN public.fs_fencers.height IS 'Fencer height in centimeters, when available.';
COMMENT ON COLUMN public.fs_fencers.weight IS 'Fencer weight in kilograms, when available.';
COMMENT ON COLUMN public.fs_fencers.reach IS 'Fencer reach in centimeters, when available.';
