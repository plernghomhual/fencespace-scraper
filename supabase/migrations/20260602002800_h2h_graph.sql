CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_h2h_graph (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_key text NOT NULL,
    identity_id uuid REFERENCES public.fs_fencer_identities(id),
    fencer_id uuid REFERENCES public.fs_fencers(id),
    canonical_name text,
    country text,
    weapon text NOT NULL,
    opponents jsonb NOT NULL DEFAULT '[]'::jsonb,
    degree integer NOT NULL DEFAULT 0,
    weighted_degree integer NOT NULL DEFAULT 0,
    total_bouts integer NOT NULL DEFAULT 0,
    wins integer NOT NULL DEFAULT 0,
    losses integer NOT NULL DEFAULT 0,
    strength numeric NOT NULL DEFAULT 0,
    degree_centrality numeric NOT NULL DEFAULT 0,
    weighted_degree_centrality numeric NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fencer_key, weapon),
    CONSTRAINT fs_h2h_graph_opponents_array
        CHECK (jsonb_typeof(opponents) = 'array'),
    CONSTRAINT fs_h2h_graph_nonnegative_metrics
        CHECK (
            degree >= 0
            AND weighted_degree >= 0
            AND total_bouts >= 0
            AND wins >= 0
            AND losses >= 0
            AND strength >= 0
            AND degree_centrality >= 0
            AND weighted_degree_centrality >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_fs_h2h_graph_fencer_key
    ON public.fs_h2h_graph(fencer_key);

CREATE INDEX IF NOT EXISTS idx_fs_h2h_graph_identity_id
    ON public.fs_h2h_graph(identity_id)
    WHERE identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_h2h_graph_fencer_id
    ON public.fs_h2h_graph(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_h2h_graph_weapon_strength
    ON public.fs_h2h_graph(weapon, strength DESC, total_bouts DESC);

COMMENT ON TABLE public.fs_h2h_graph IS
    'Bounded per-fencer head-to-head adjacency graph for API/frontend consumers.';

COMMENT ON COLUMN public.fs_h2h_graph.fencer_key IS
    'Stable graph node key: fs_fencer_identities.id when available, otherwise raw fs_fencers.id.';

COMMENT ON COLUMN public.fs_h2h_graph.opponents IS
    'Bounded adjacency list with opponent identity, weapon, bouts, wins, losses, strength, and win rate.';
