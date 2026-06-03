CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Fantasy league backend data model.
--
-- Game rules:
-- - Admins create leagues, teams, scoring periods, rosters, and draft picks.
-- - Only active starter roster slots score by default.
-- - Weekly scores are derived from verified fs_results rows: participation,
--   medal bonus, and upset bonus based on pre-event seed/rank improvement.
-- - Scores are idempotent by period/team/fencer/result_key.
--
-- Manual setup:
-- 1. Apply this migration.
-- 2. Insert a row in fs_fantasy_leagues with roster_size/starter_slots/rules.
-- 3. Insert fs_fantasy_teams and optional owner/manager user identifiers if
--    a frontend/auth integration already exists.
-- 4. Insert draft picks and active roster rows.
-- 5. Lock a scoring period, then run fantasy_league.py with service-role
--    credentials. No anon/authenticated writes are granted here.

CREATE TABLE IF NOT EXISTS public.fs_fantasy_leagues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    season text,
    roster_size integer NOT NULL DEFAULT 8 CHECK (roster_size > 0),
    starter_slots integer NOT NULL DEFAULT 5 CHECK (starter_slots > 0),
    max_teams integer CHECK (max_teams IS NULL OR max_teams > 0),
    status text NOT NULL DEFAULT 'drafting'
        CHECK (status IN ('drafting', 'active', 'completed', 'archived')),
    owner_user_id uuid,
    owner_external_id text,
    rules jsonb NOT NULL DEFAULT '{
        "participation_points": 1,
        "medal_points": {"gold": 12, "silver": 8, "bronze": 5},
        "upset_bonus": {
            "tiers": [
                {"improvement": 16, "points": 10},
                {"improvement": 8, "points": 6},
                {"improvement": 4, "points": 3}
            ]
        },
        "scoring_slot_types": ["starter"]
    }'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fantasy_leagues_starters_fit_roster
        CHECK (starter_slots <= roster_size)
);

CREATE TABLE IF NOT EXISTS public.fs_fantasy_teams (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES public.fs_fantasy_leagues(id) ON DELETE CASCADE,
    name text NOT NULL,
    manager_name text,
    manager_user_id uuid,
    manager_external_id text,
    draft_position integer CHECK (draft_position IS NULL OR draft_position > 0),
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (league_id, name),
    UNIQUE (league_id, draft_position)
);

CREATE TABLE IF NOT EXISTS public.fs_fantasy_rosters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES public.fs_fantasy_leagues(id) ON DELETE CASCADE,
    team_id uuid NOT NULL REFERENCES public.fs_fantasy_teams(id) ON DELETE CASCADE,
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    slot_type text NOT NULL DEFAULT 'starter'
        CHECK (slot_type IN ('starter', 'bench', 'reserve')),
    acquired_by text NOT NULL DEFAULT 'draft'
        CHECK (acquired_by IN ('draft', 'manual', 'waiver')),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_fantasy_rosters_release_order
        CHECK (released_at IS NULL OR released_at >= acquired_at)
);

CREATE TABLE IF NOT EXISTS public.fs_fantasy_draft_picks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES public.fs_fantasy_leagues(id) ON DELETE CASCADE,
    team_id uuid NOT NULL REFERENCES public.fs_fantasy_teams(id) ON DELETE CASCADE,
    round_number integer NOT NULL CHECK (round_number > 0),
    pick_number integer NOT NULL CHECK (pick_number > 0),
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE RESTRICT,
    skipped boolean NOT NULL DEFAULT false,
    auto_picked boolean NOT NULL DEFAULT false,
    picked_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (league_id, pick_number),
    UNIQUE (league_id, round_number, pick_number),
    CONSTRAINT fs_fantasy_draft_picks_selected_or_skipped
        CHECK ((skipped = true AND fencer_id IS NULL) OR (skipped = false AND fencer_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.fs_fantasy_scoring_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES public.fs_fantasy_leagues(id) ON DELETE CASCADE,
    period_key text NOT NULL,
    week_number integer CHECK (week_number IS NULL OR week_number > 0),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'locked', 'scored', 'closed')),
    locked_at timestamptz,
    scored_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (league_id, period_key),
    CONSTRAINT fs_fantasy_scoring_periods_date_order
        CHECK (ends_at >= starts_at),
    CONSTRAINT fs_fantasy_scoring_periods_locked_status
        CHECK (
            (status = 'open' AND locked_at IS NULL)
            OR (status <> 'open' AND locked_at IS NOT NULL)
        )
);

CREATE TABLE IF NOT EXISTS public.fs_fantasy_weekly_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES public.fs_fantasy_leagues(id) ON DELETE CASCADE,
    period_id uuid NOT NULL REFERENCES public.fs_fantasy_scoring_periods(id) ON DELETE CASCADE,
    team_id uuid NOT NULL REFERENCES public.fs_fantasy_teams(id) ON DELETE CASCADE,
    fencer_id uuid NOT NULL REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    tournament_id uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    result_key text NOT NULL,
    points integer NOT NULL DEFAULT 0,
    components jsonb NOT NULL DEFAULT '{}',
    source_result jsonb NOT NULL DEFAULT '{}',
    scored_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (period_id, team_id, fencer_id, result_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fs_fantasy_rosters_active_fencer
    ON public.fs_fantasy_rosters (league_id, fencer_id)
    WHERE released_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_fs_fantasy_rosters_team_active
    ON public.fs_fantasy_rosters (team_id, slot_type)
    WHERE released_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fs_fantasy_draft_unique_fencer
    ON public.fs_fantasy_draft_picks (league_id, fencer_id)
    WHERE fencer_id IS NOT NULL AND skipped = false;

CREATE INDEX IF NOT EXISTS idx_fs_fantasy_scoring_periods_dates
    ON public.fs_fantasy_scoring_periods (league_id, starts_at, ends_at);

CREATE INDEX IF NOT EXISTS idx_fs_fantasy_weekly_scores_team_period
    ON public.fs_fantasy_weekly_scores (period_id, team_id, points DESC);

CREATE INDEX IF NOT EXISTS idx_fs_fantasy_weekly_scores_fencer
    ON public.fs_fantasy_weekly_scores (fencer_id, scored_at DESC);

ALTER TABLE public.fs_fantasy_leagues ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fantasy_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fantasy_rosters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fantasy_draft_picks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fantasy_scoring_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_fantasy_weekly_scores ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_fantasy_leagues FROM anon, authenticated;
REVOKE ALL ON public.fs_fantasy_teams FROM anon, authenticated;
REVOKE ALL ON public.fs_fantasy_rosters FROM anon, authenticated;
REVOKE ALL ON public.fs_fantasy_draft_picks FROM anon, authenticated;
REVOKE ALL ON public.fs_fantasy_scoring_periods FROM anon, authenticated;
REVOKE ALL ON public.fs_fantasy_weekly_scores FROM anon, authenticated;
