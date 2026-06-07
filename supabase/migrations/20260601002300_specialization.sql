CREATE TABLE IF NOT EXISTS public.fs_fencer_specialization (
    fencer_id               text            NOT NULL PRIMARY KEY,
    classification          text            NOT NULL,
    primary_weapon          text,
    weapons                 jsonb           NOT NULL DEFAULT '[]',
    total_results           integer         NOT NULL DEFAULT 0,
    total_competitions      integer         NOT NULL DEFAULT 0,
    ranked_results          integer         NOT NULL DEFAULT 0,
    avg_rank                double precision,
    best_rank               integer,
    worst_rank              integer,
    medal_count             integer         NOT NULL DEFAULT 0,
    medals_per_competition  double precision,
    per_weapon              jsonb           NOT NULL DEFAULT '{}',
    season_primary_weapons  jsonb           NOT NULL DEFAULT '{}',
    changed_primary_weapon  boolean         NOT NULL DEFAULT false,
    weapon_switches         jsonb           NOT NULL DEFAULT '[]',
    categories              jsonb           NOT NULL DEFAULT '[]',
    computed_at             timestamptz     NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_fencer_specialization ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fencer_specialization FROM anon, authenticated;
GRANT SELECT ON public.fs_fencer_specialization TO authenticated;

DROP POLICY IF EXISTS subscriber_fencer_specialization_read ON public.fs_fencer_specialization;
CREATE POLICY subscriber_fencer_specialization_read ON public.fs_fencer_specialization
FOR SELECT TO authenticated
USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'subscriber');
