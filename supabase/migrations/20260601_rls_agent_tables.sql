-- RLS for all agent-created tables not covered by 20260601_rls_policies.sql.
-- Pattern mirrors the base RLS migration: subscriber JWT required for SELECT.

-- ── Enable RLS ──────────────────────────────────────────────────────────────

ALTER TABLE public.fs_fencer_career_stats          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_rankings_trends              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_venues                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_medal_tables                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_competition_strength         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_transfers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_longevity             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_performance_analysis  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_name_variants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_social_media          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_competition_details          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_country_depth                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_club_rankings                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fencer_equipment             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_training_camps               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_college_scholarships         ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_articles                            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_referees                            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_coaches                             ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_fencer_coach_relationship           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_club_reviews                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_equipment_reviews            ENABLE ROW LEVEL SECURITY;
-- Internal dedup table — enable RLS, no read policy (service_role only)
ALTER TABLE fs_fencer_identities                   ENABLE ROW LEVEL SECURITY;

-- ── Revoke defaults ─────────────────────────────────────────────────────────

REVOKE ALL ON public.fs_fencer_career_stats         FROM anon, authenticated;
REVOKE ALL ON public.fs_rankings_trends             FROM anon, authenticated;
REVOKE ALL ON public.fs_venues                      FROM anon, authenticated;
REVOKE ALL ON public.fs_medal_tables                FROM anon, authenticated;
REVOKE ALL ON public.fs_competition_strength        FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_transfers            FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_longevity            FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_performance_analysis FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_name_variants        FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_social_media         FROM anon, authenticated;
REVOKE ALL ON public.fs_competition_details         FROM anon, authenticated;
REVOKE ALL ON public.fs_country_depth               FROM anon, authenticated;
REVOKE ALL ON public.fs_club_rankings               FROM anon, authenticated;
REVOKE ALL ON public.fs_fencer_equipment            FROM anon, authenticated;
REVOKE ALL ON public.fs_training_camps              FROM anon, authenticated;
REVOKE ALL ON public.fs_college_scholarships        FROM anon, authenticated;
REVOKE ALL ON fs_articles                           FROM anon, authenticated;
REVOKE ALL ON fs_referees                           FROM anon, authenticated;
REVOKE ALL ON fs_coaches                            FROM anon, authenticated;
REVOKE ALL ON fs_fencer_coach_relationship          FROM anon, authenticated;
REVOKE ALL ON public.fs_club_reviews                FROM anon, authenticated;
REVOKE ALL ON public.fs_equipment_reviews           FROM anon, authenticated;
REVOKE ALL ON fs_fencer_identities                  FROM anon, authenticated;

-- ── Grant SELECT to authenticated (RLS policies enforce subscriber check) ───

GRANT SELECT ON public.fs_fencer_career_stats         TO authenticated;
GRANT SELECT ON public.fs_rankings_trends             TO authenticated;
GRANT SELECT ON public.fs_venues                      TO authenticated;
GRANT SELECT ON public.fs_medal_tables                TO authenticated;
GRANT SELECT ON public.fs_competition_strength        TO authenticated;
GRANT SELECT ON public.fs_fencer_transfers            TO authenticated;
GRANT SELECT ON public.fs_fencer_longevity            TO authenticated;
GRANT SELECT ON public.fs_fencer_performance_analysis TO authenticated;
GRANT SELECT ON public.fs_fencer_name_variants        TO authenticated;
GRANT SELECT ON public.fs_fencer_social_media         TO authenticated;
GRANT SELECT ON public.fs_competition_details         TO authenticated;
GRANT SELECT ON public.fs_country_depth               TO authenticated;
GRANT SELECT ON public.fs_club_rankings               TO authenticated;
GRANT SELECT ON public.fs_fencer_equipment            TO authenticated;
GRANT SELECT ON public.fs_training_camps              TO authenticated;
GRANT SELECT ON public.fs_college_scholarships        TO authenticated;
GRANT SELECT ON fs_articles                           TO authenticated;
GRANT SELECT ON fs_referees                           TO authenticated;
GRANT SELECT ON fs_coaches                            TO authenticated;
GRANT SELECT ON fs_fencer_coach_relationship          TO authenticated;
GRANT SELECT ON public.fs_club_reviews                TO authenticated;
GRANT SELECT ON public.fs_equipment_reviews           TO authenticated;

-- ── Subscriber-only SELECT policies ─────────────────────────────────────────

DO $$
DECLARE
    tbl text;
    tbls text[] := ARRAY[
        'fs_fencer_career_stats',
        'fs_rankings_trends',
        'fs_venues',
        'fs_medal_tables',
        'fs_competition_strength',
        'fs_fencer_transfers',
        'fs_fencer_longevity',
        'fs_fencer_performance_analysis',
        'fs_fencer_name_variants',
        'fs_fencer_social_media',
        'fs_competition_details',
        'fs_country_depth',
        'fs_club_rankings',
        'fs_fencer_equipment',
        'fs_training_camps',
        'fs_college_scholarships',
        'fs_articles',
        'fs_referees',
        'fs_coaches',
        'fs_fencer_coach_relationship',
        'fs_club_reviews',
        'fs_equipment_reviews'
    ];
BEGIN
    FOREACH tbl IN ARRAY tbls LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS subscriber_%1$s_read ON %1$s;
             CREATE POLICY subscriber_%1$s_read ON %1$s
             FOR SELECT TO authenticated
             USING (((SELECT auth.jwt()) -> ''app_metadata'' ->> ''role'') = ''subscriber'');',
            tbl
        );
    END LOOP;
END $$;
