CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_elo (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    identity_id uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    weapon text NOT NULL,
    category text NOT NULL DEFAULT 'Open',
    rating numeric(8,2) NOT NULL DEFAULT 1500.00,
    games integer NOT NULL DEFAULT 0,
    peak_rating numeric(8,2) NOT NULL DEFAULT 1500.00,
    last_bout_at date,
    version integer NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_elo_games_nonnegative CHECK (games >= 0),
    CONSTRAINT fs_fencer_elo_rating_positive CHECK (rating > 0 AND peak_rating > 0),
    CONSTRAINT fs_fencer_elo_unique UNIQUE (fencer_id, weapon, category, version)
);

CREATE INDEX IF NOT EXISTS fs_fencer_elo_identity_idx
    ON public.fs_fencer_elo (identity_id)
    WHERE identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_elo_weapon_category_idx
    ON public.fs_fencer_elo (weapon, category);

CREATE INDEX IF NOT EXISTS fs_fencer_elo_rating_idx
    ON public.fs_fencer_elo (weapon, category, rating DESC);

CREATE INDEX IF NOT EXISTS fs_fencer_elo_updated_idx
    ON public.fs_fencer_elo (updated_at DESC);

ALTER TABLE public.fs_fencer_elo ENABLE ROW LEVEL SECURITY;
