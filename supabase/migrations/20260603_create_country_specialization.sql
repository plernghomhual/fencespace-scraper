CREATE TABLE IF NOT EXISTS public.fs_country_specialization (
    id                          text                NOT NULL PRIMARY KEY,
    country_code                text                NOT NULL,
    weapon                      text                NOT NULL,
    category                    text                NOT NULL,
    tier                        text                NOT NULL,
    season                      integer,
    raw_score                   double precision    NOT NULL DEFAULT 0,
    sample_count                integer             NOT NULL DEFAULT 0,
    source_counts               jsonb               NOT NULL DEFAULT '{}',
    country_share_in_segment    double precision    NOT NULL DEFAULT 0,
    country_baseline_share      double precision    NOT NULL DEFAULT 0,
    specialization_index        double precision    NOT NULL DEFAULT 0,
    z_score                     double precision    NOT NULL DEFAULT 0,
    segment_rank                integer,
    confidence                  double precision    NOT NULL DEFAULT 0,
    confidence_label            text,
    is_sparse                   boolean             NOT NULL DEFAULT false,
    gold                        integer             NOT NULL DEFAULT 0,
    silver                      integer             NOT NULL DEFAULT 0,
    bronze                      integer             NOT NULL DEFAULT 0,
    medal_count                 integer             NOT NULL DEFAULT 0,
    computed_at                 timestamptz         NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_country_specialization ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_country_specialization FROM anon, authenticated;
GRANT SELECT ON public.fs_country_specialization TO authenticated;

DROP POLICY IF EXISTS subscriber_country_specialization_read ON public.fs_country_specialization;
CREATE POLICY subscriber_country_specialization_read ON public.fs_country_specialization
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
