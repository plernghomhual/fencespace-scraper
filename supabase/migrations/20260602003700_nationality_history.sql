CREATE TABLE IF NOT EXISTS public.fs_fencer_nationality_history (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    history_key           text NOT NULL,
    fencer_id             uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    fencer_identity_id    uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    wikidata_id           text,
    wikidata_country_id   text,
    wikidata_statement_id text,
    claim_property        text,
    country               text NOT NULL,
    country_code          text,
    start_date            text,
    end_date              text,
    point_in_time         text,
    source                text NOT NULL,
    confidence            numeric NOT NULL,
    sequence_index        integer,
    metadata              jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_at           timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_nationality_history_history_key_unique
        UNIQUE (history_key),
    CONSTRAINT fs_fencer_nationality_history_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1)
);

ALTER TABLE public.fs_fencer_nationality_history ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_history_fencer_idx
    ON public.fs_fencer_nationality_history (fencer_id, sequence_index);

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_history_identity_idx
    ON public.fs_fencer_nationality_history (fencer_identity_id)
    WHERE fencer_identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_history_country_code_idx
    ON public.fs_fencer_nationality_history (country_code)
    WHERE country_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_history_wikidata_idx
    ON public.fs_fencer_nationality_history (wikidata_id)
    WHERE wikidata_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.fs_fencer_nationality_discrepancies (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    discrepancy_key       text NOT NULL,
    fencer_id             uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    fencer_identity_id    uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    wikidata_id           text,
    discrepancy_type      text NOT NULL,
    source                text NOT NULL,
    severity              text NOT NULL DEFAULT 'needs_review',
    country_code          text,
    observed_country_code text,
    description           text NOT NULL,
    confidence            numeric NOT NULL,
    metadata              jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_at           timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fencer_nationality_discrepancies_key_unique
        UNIQUE (discrepancy_key),
    CONSTRAINT fs_fencer_nationality_discrepancies_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1)
);

ALTER TABLE public.fs_fencer_nationality_discrepancies ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_discrepancies_fencer_idx
    ON public.fs_fencer_nationality_discrepancies (fencer_id, discrepancy_type);

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_discrepancies_identity_idx
    ON public.fs_fencer_nationality_discrepancies (fencer_identity_id)
    WHERE fencer_identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_fencer_nationality_discrepancies_source_idx
    ON public.fs_fencer_nationality_discrepancies (source, severity);
