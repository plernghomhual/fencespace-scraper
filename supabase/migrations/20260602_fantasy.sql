CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fantasy_points (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    season integer NOT NULL,
    components jsonb NOT NULL DEFAULT '{}'::jsonb,
    total_points numeric NOT NULL DEFAULT 0,
    rules_version text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fencer_id, tournament_id, season, rules_version)
);

CREATE INDEX IF NOT EXISTS fs_fantasy_points_fencer_idx
ON public.fs_fantasy_points (fencer_id, season DESC);

CREATE INDEX IF NOT EXISTS fs_fantasy_points_tournament_idx
ON public.fs_fantasy_points (tournament_id);

CREATE INDEX IF NOT EXISTS fs_fantasy_points_rules_version_idx
ON public.fs_fantasy_points (rules_version, season DESC);

COMMENT ON TABLE public.fs_fantasy_points IS
'Fantasy scoring weights rules_version=2026.06.v1: participation=2; placement 1=32,2=24,3=21,4=16,5-8=8,9-16=6,17-32=3,33-64=1; medals gold=20,silver=14,bronze=10; upset=8 when winner world_rank is 10+ places worse than loser; penalties dns=-5,dq=-10; team_event_multiplier=0.5; tier multipliers Olympics=2,Worlds=1.75,GP=1.35,WC=1.25,Continental=1.2,National=1,Domestic=1,Unknown=1.';
