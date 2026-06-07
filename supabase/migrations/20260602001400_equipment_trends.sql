CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_equipment_trend_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand text NOT NULL,
    equipment_category text NOT NULL,
    weapon text NOT NULL,
    event_tier text,
    fencer_id uuid REFERENCES public.fs_fencers(id),
    result_id uuid,
    tournament_id uuid REFERENCES public.fs_tournaments(id),
    result_rank integer,
    result_name text,
    source text NOT NULL,
    source_url text,
    evidence_type text,
    confidence text NOT NULL DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    metadata jsonb DEFAULT '{}',
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_equipment_trends (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand text NOT NULL,
    equipment_category text NOT NULL,
    weapon text NOT NULL,
    event_tier text,
    evidence_count integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    result_count integer NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    win_count integer NOT NULL DEFAULT 0 CHECK (win_count >= 0),
    podium_count integer NOT NULL DEFAULT 0 CHECK (podium_count >= 0),
    top8_count integer NOT NULL DEFAULT 0 CHECK (top8_count >= 0),
    confidence text NOT NULL DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    confidence_score numeric(4,3) NOT NULL DEFAULT 0,
    sources jsonb DEFAULT '[]',
    metadata jsonb DEFAULT '{}',
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT fs_equipment_trends_unique_group
        UNIQUE (brand, equipment_category, weapon, event_tier)
);

ALTER TABLE public.fs_equipment_trend_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_equipment_trends ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_trend_evidence TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_trends TO service_role;

CREATE INDEX IF NOT EXISTS fs_equipment_trend_evidence_brand_weapon_tier_idx
    ON public.fs_equipment_trend_evidence (brand, weapon, event_tier);

CREATE INDEX IF NOT EXISTS fs_equipment_trend_evidence_fencer_result_idx
    ON public.fs_equipment_trend_evidence (fencer_id, result_id);

CREATE INDEX IF NOT EXISTS fs_equipment_trend_evidence_source_idx
    ON public.fs_equipment_trend_evidence (source, updated_at DESC);

CREATE INDEX IF NOT EXISTS fs_equipment_trends_brand_category_weapon_tier_idx
    ON public.fs_equipment_trends (brand, equipment_category, weapon, event_tier);

CREATE INDEX IF NOT EXISTS fs_equipment_trends_weapon_wins_idx
    ON public.fs_equipment_trends (weapon, win_count DESC);
