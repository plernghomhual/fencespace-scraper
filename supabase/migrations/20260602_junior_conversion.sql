CREATE TABLE IF NOT EXISTS public.fs_junior_conversion_rates (
    country                   text NOT NULL,
    weapon                    text NOT NULL,
    gender                    text NOT NULL,
    category                  text NOT NULL,
    cohort_season             integer NOT NULL,
    window_years              integer NOT NULL,
    sample_count              integer NOT NULL,
    junior_result_count       integer NOT NULL DEFAULT 0,
    junior_ranking_count      integer NOT NULL DEFAULT 0,
    senior_appearance_count   integer NOT NULL DEFAULT 0,
    senior_appearance_rate    numeric,
    senior_ranking_count      integer NOT NULL DEFAULT 0,
    senior_ranking_rate       numeric,
    senior_medal_count        integer NOT NULL DEFAULT 0,
    senior_medal_rate         numeric,
    senior_top8_count         integer NOT NULL DEFAULT 0,
    senior_top8_rate          numeric,
    senior_top16_count        integer NOT NULL DEFAULT 0,
    senior_top16_rate         numeric,
    country_transfer_count    integer NOT NULL DEFAULT 0,
    country_transfer_rate     numeric,
    computed_at               timestamptz NOT NULL DEFAULT now(),
    metadata                  jsonb NOT NULL DEFAULT '{}',
    CONSTRAINT fs_junior_conversion_rates_pkey
        PRIMARY KEY (country, weapon, gender, category, cohort_season, window_years),
    CONSTRAINT fs_junior_conversion_rates_counts_check
        CHECK (
            sample_count >= 0
            AND junior_result_count >= 0
            AND junior_ranking_count >= 0
            AND senior_appearance_count >= 0
            AND senior_ranking_count >= 0
            AND senior_medal_count >= 0
            AND senior_top8_count >= 0
            AND senior_top16_count >= 0
            AND country_transfer_count >= 0
            AND window_years > 0
        )
);

CREATE INDEX IF NOT EXISTS fs_junior_conversion_rates_country_idx
    ON public.fs_junior_conversion_rates (country, weapon, cohort_season);

CREATE INDEX IF NOT EXISTS fs_junior_conversion_rates_window_idx
    ON public.fs_junior_conversion_rates (window_years, senior_appearance_rate);
