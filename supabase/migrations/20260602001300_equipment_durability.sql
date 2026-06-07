CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_equipment_durability (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand text NOT NULL,
    equipment_type text NOT NULL,
    fencer_id uuid REFERENCES public.fs_fencers(id),
    observed_first_date date,
    observed_last_date date,
    replacement_interval_estimate integer,
    evidence_count integer NOT NULL DEFAULT 0,
    confidence text NOT NULL DEFAULT 'insufficient',
    metadata jsonb DEFAULT '{}',
    computed_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT fs_equipment_durability_confidence_check
        CHECK (confidence IN ('high', 'medium', 'low', 'insufficient')),
    CONSTRAINT fs_equipment_durability_evidence_count_check
        CHECK (evidence_count >= 0),
    CONSTRAINT fs_equipment_durability_interval_check
        CHECK (replacement_interval_estimate IS NULL OR replacement_interval_estimate >= 0),
    CONSTRAINT fs_equipment_durability_date_order_check
        CHECK (
            observed_first_date IS NULL
            OR observed_last_date IS NULL
            OR observed_first_date <= observed_last_date
        )
);

ALTER TABLE public.fs_equipment_durability ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.fs_equipment_durability TO service_role;

CREATE INDEX IF NOT EXISTS fs_equipment_durability_brand_type_fencer_idx
    ON public.fs_equipment_durability (brand, equipment_type, fencer_id);

CREATE INDEX IF NOT EXISTS fs_equipment_durability_confidence_idx
    ON public.fs_equipment_durability (confidence);

CREATE INDEX IF NOT EXISTS fs_equipment_durability_computed_at_idx
    ON public.fs_equipment_durability (computed_at DESC);
