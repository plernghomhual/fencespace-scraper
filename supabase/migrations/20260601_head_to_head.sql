CREATE TABLE IF NOT EXISTS public.fs_head_to_head (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_a_id uuid REFERENCES public.fs_fencers(id),
    fencer_b_id uuid REFERENCES public.fs_fencers(id),
    weapon text NOT NULL,
    a_wins integer DEFAULT 0,
    b_wins integer DEFAULT 0,
    a_touches integer DEFAULT 0,
    b_touches integer DEFAULT 0,
    bouts_total integer DEFAULT 0,
    last_meeting_date date,
    last_winner_id uuid REFERENCES public.fs_fencers(id),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (fencer_a_id, fencer_b_id, weapon)
);
