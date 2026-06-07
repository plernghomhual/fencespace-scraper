CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- fs_fencers.fie_id stores FIE's external athlete identifier as text/numeric
-- data, while fs_fencers.id is the Supabase UUID row identifier.
CREATE TABLE IF NOT EXISTS fs_fencer_identities (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name     text,
    country            text,
    fie_ids            text[] NOT NULL DEFAULT '{}',
    fs_fencer_row_ids  uuid[] NOT NULL DEFAULT '{}',
    metadata           jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_identities_has_rows
        CHECK (cardinality(fs_fencer_row_ids) > 0)
);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_country_idx
    ON fs_fencer_identities (country)
    WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_identities_fie_ids_idx
    ON fs_fencer_identities USING gin (fie_ids);

CREATE INDEX IF NOT EXISTS fs_fencer_identities_row_ids_idx
    ON fs_fencer_identities USING gin (fs_fencer_row_ids);
