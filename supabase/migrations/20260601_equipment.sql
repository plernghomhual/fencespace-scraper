CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_equipment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES public.fs_fencers(id),
    brand text NOT NULL,
    equipment_type text,
    sponsor_name text,
    source text,
    source_url text,
    confidence text DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_fencer_id_idx
    ON public.fs_fencer_equipment (fencer_id);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_brand_idx
    ON public.fs_fencer_equipment (brand);

CREATE INDEX IF NOT EXISTS fs_fencer_equipment_source_idx
    ON public.fs_fencer_equipment (source);
