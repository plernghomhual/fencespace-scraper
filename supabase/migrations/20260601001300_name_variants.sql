CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fs_fencer_name_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL,
    name text NOT NULL,
    script text NOT NULL CHECK (script IN ('Latin', 'Hangul', 'Cyrillic', 'CJK', 'Arabic', 'Other')),
    source text NOT NULL,
    country text,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fencer_name_variants_unique
    ON fs_fencer_name_variants(fencer_id, name, script);

CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_fencer
    ON fs_fencer_name_variants(fencer_id);

CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_name
    ON fs_fencer_name_variants(name);
