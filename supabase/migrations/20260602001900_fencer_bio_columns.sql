ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS bio text,
    ADD COLUMN IF NOT EXISTS birth_date date,
    ADD COLUMN IF NOT EXISTS birth_place text,
    ADD COLUMN IF NOT EXISTS bio_source text;

COMMENT ON COLUMN public.fs_fencers.bio IS 'Biographical summary text, when available.';
COMMENT ON COLUMN public.fs_fencers.birth_date IS 'Fencer birth date, when available.';
COMMENT ON COLUMN public.fs_fencers.birth_place IS 'Fencer birth place, when available.';
COMMENT ON COLUMN public.fs_fencers.bio_source IS 'Source for biographical fields, when available.';
