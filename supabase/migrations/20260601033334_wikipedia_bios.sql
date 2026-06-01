ALTER TABLE public.fs_fencers
    ADD COLUMN IF NOT EXISTS bio_text text,
    ADD COLUMN IF NOT EXISTS wikipedia_url text,
    ADD COLUMN IF NOT EXISTS birth_place text,
    ADD COLUMN IF NOT EXISTS nickname text,
    ADD COLUMN IF NOT EXISTS height text,
    ADD COLUMN IF NOT EXISTS weight text;
