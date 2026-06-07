CREATE TABLE IF NOT EXISTS public.fs_competition_weather (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid NOT NULL REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    venue_name text,
    location text,
    event_date date,
    is_indoor boolean,
    environment text NOT NULL DEFAULT 'indoor_assumed'
        CHECK (environment IN ('indoor', 'indoor_assumed', 'outdoor', 'unknown')),
    weather_relevance text NOT NULL DEFAULT 'low'
        CHECK (weather_relevance IN ('low', 'possible_context_only', 'unknown')),
    latitude double precision CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude double precision CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    temperature_celsius numeric,
    humidity_percent numeric CHECK (humidity_percent IS NULL OR humidity_percent BETWEEN 0 AND 100),
    source text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    scraped_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_competition_weather_unique_tournament UNIQUE (tournament_id)
);

CREATE INDEX IF NOT EXISTS fs_competition_weather_tournament_id_idx
    ON public.fs_competition_weather (tournament_id);

CREATE INDEX IF NOT EXISTS fs_competition_weather_event_date_idx
    ON public.fs_competition_weather (event_date);

CREATE INDEX IF NOT EXISTS fs_competition_weather_environment_idx
    ON public.fs_competition_weather (environment);
