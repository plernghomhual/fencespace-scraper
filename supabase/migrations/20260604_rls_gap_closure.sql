-- Close RLS gaps identified during the 2026-06-04 pre-production audit.
-- These tables are read and written through service-role backend jobs/APIs.

ALTER TABLE IF EXISTS public.fs_betting_odds ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_betting_odds FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_coach_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_coach_history FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_country_geo_codes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_country_geo_codes FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_fencer_family_relationships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_fencer_family_relationships FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_fantasy_points ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_fantasy_points FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_h2h_graph ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_h2h_graph FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_fencer_injury_absences ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_fencer_injury_absences FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_junior_conversion_rates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_junior_conversion_rates FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_ranking_history_trajectory ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_ranking_history_trajectory FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_social_feed ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_social_feed FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_upsets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_upsets FROM anon, authenticated;

ALTER TABLE IF EXISTS public.fs_competition_weather ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fs_competition_weather FROM anon, authenticated;
