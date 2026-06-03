CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_fencer_family_relationships (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id                  uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    fencer_identity_id         uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    fencer_wikidata_id         text NOT NULL,
    fencer_name                text,
    relationship_type          text NOT NULL,
    related_name               text NOT NULL,
    related_wikidata_id        text,
    related_fencer_id          uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    related_fencer_identity_id uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    relationship_key           text NOT NULL,
    source                     text NOT NULL DEFAULT 'wikidata',
    confidence                 numeric(4, 3) NOT NULL DEFAULT 1.000,
    metadata                   jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at                 timestamptz NOT NULL DEFAULT now(),
    updated_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_family_relationships_type_check
        CHECK (relationship_type IN ('sibling', 'parent', 'spouse', 'child', 'relative')),
    CONSTRAINT fs_fencer_family_relationships_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT fs_fencer_family_relationships_unique
        UNIQUE (fencer_id, relationship_type, source, relationship_key)
);

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_fencer_idx
    ON public.fs_fencer_family_relationships (fencer_id);

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_identity_idx
    ON public.fs_fencer_family_relationships (fencer_identity_id)
    WHERE fencer_identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_related_fencer_idx
    ON public.fs_fencer_family_relationships (related_fencer_id)
    WHERE related_fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_related_identity_idx
    ON public.fs_fencer_family_relationships (related_fencer_identity_id)
    WHERE related_fencer_identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_related_wikidata_idx
    ON public.fs_fencer_family_relationships (related_wikidata_id)
    WHERE related_wikidata_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_family_relationships_type_idx
    ON public.fs_fencer_family_relationships (relationship_type);
