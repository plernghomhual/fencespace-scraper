CREATE TABLE IF NOT EXISTS public.fs_betting_odds (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    market_type text NOT NULL,
    participant text NOT NULL,
    odds_decimal numeric(12,4) NOT NULL,
    implied_probability numeric(12,8) NOT NULL,
    region text NOT NULL,
    source_url text NOT NULL,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fs_betting_odds_decimal_check
        CHECK (odds_decimal > 1),
    CONSTRAINT fs_betting_odds_probability_check
        CHECK (implied_probability > 0 AND implied_probability <= 1),
    CONSTRAINT fs_betting_odds_market_type_check
        CHECK (length(trim(market_type)) > 0),
    CONSTRAINT fs_betting_odds_participant_check
        CHECK (length(trim(participant)) > 0),
    CONSTRAINT fs_betting_odds_region_check
        CHECK (length(trim(region)) > 0),
    CONSTRAINT fs_betting_odds_unique_market
        UNIQUE (source, tournament_id, market_type, participant, region)
);

CREATE INDEX IF NOT EXISTS fs_betting_odds_tournament_idx
    ON public.fs_betting_odds (tournament_id, market_type);

CREATE INDEX IF NOT EXISTS fs_betting_odds_source_scraped_idx
    ON public.fs_betting_odds (source, region, scraped_at DESC);

CREATE INDEX IF NOT EXISTS fs_betting_odds_metadata_gin_idx
    ON public.fs_betting_odds USING gin (metadata);

COMMENT ON TABLE public.fs_betting_odds IS
    'Informational public odds snapshots only; not betting advice, picks, predictions, or wagering guidance.';

COMMENT ON COLUMN public.fs_betting_odds.metadata IS
    'Compliance caveats including source disclaimer, region disclaimer, access policy, market status, stale flag, and no_betting_advice marker.';
