CREATE TABLE IF NOT EXISTS public.fs_travel_cost_estimates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    origin_country text NOT NULL,
    origin_city text NOT NULL,
    destination text NOT NULL,
    date_range text NOT NULL,
    flight_estimate numeric CHECK (flight_estimate IS NULL OR flight_estimate >= 0),
    hotel_estimate numeric CHECK (hotel_estimate IS NULL OR hotel_estimate >= 0),
    currency text NOT NULL DEFAULT 'USD',
    source text NOT NULL,
    confidence numeric NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tournament_id, origin_country, origin_city)
);

CREATE INDEX IF NOT EXISTS fs_travel_cost_estimates_tournament_idx
    ON public.fs_travel_cost_estimates (tournament_id);

CREATE INDEX IF NOT EXISTS fs_travel_cost_estimates_origin_idx
    ON public.fs_travel_cost_estimates (origin_country, origin_city);

CREATE INDEX IF NOT EXISTS fs_travel_cost_estimates_updated_at_idx
    ON public.fs_travel_cost_estimates (updated_at);

COMMENT ON TABLE public.fs_travel_cost_estimates IS
    'Approximate travel cost estimates for planning context only; not booking advice.';

COMMENT ON COLUMN public.fs_travel_cost_estimates.flight_estimate IS
    'Approximate flight cost estimate in the row currency; not a fare quote.';

COMMENT ON COLUMN public.fs_travel_cost_estimates.hotel_estimate IS
    'Approximate lodging cost estimate in the row currency; not a booking quote.';

ALTER TABLE public.fs_travel_cost_estimates ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_travel_cost_estimates FROM anon, authenticated;
GRANT SELECT ON public.fs_travel_cost_estimates TO authenticated;

DROP POLICY IF EXISTS subscriber_fs_travel_cost_estimates_read
ON public.fs_travel_cost_estimates;

CREATE POLICY subscriber_fs_travel_cost_estimates_read
ON public.fs_travel_cost_estimates
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
