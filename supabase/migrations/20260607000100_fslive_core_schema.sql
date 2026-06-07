-- FenceSpace Live: Core Schema
-- Migration: 20260607_fslive_core_schema.sql
--
-- Tables: tournaments, events, strips, registrations, pools, pool bouts,
--         pool results, DE brackets, DE bouts, strip assignments, cloud
--         event log, spectator follows, push subscriptions, device registry.
-- Includes: composite indexes, partial indexes, generated columns, RLS, Realtime.

-- ============================================================
-- HELPER: updated_at trigger function
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

-- ============================================================
-- TOURNAMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_tournaments (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text        NOT NULL,
  venue           text,
  city            text,
  state_code      text,
  date            date        NOT NULL,
  organizer_id    uuid        REFERENCES auth.users ON DELETE SET NULL,
  status          text        NOT NULL DEFAULT 'setup'
                              CHECK (status IN ('setup','pools','de','complete','cancelled')),
  config          jsonb       NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fslive_tournaments_organizer
  ON public.fs_live_tournaments(organizer_id);
CREATE INDEX IF NOT EXISTS idx_fslive_tournaments_date
  ON public.fs_live_tournaments(date DESC);
-- Partial: only index active/upcoming tournaments for routing queries
CREATE INDEX IF NOT EXISTS idx_fslive_tournaments_active
  ON public.fs_live_tournaments(status, date)
  WHERE status NOT IN ('complete', 'cancelled');

CREATE TRIGGER trg_fslive_tournaments_updated_at
  BEFORE UPDATE ON public.fs_live_tournaments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- EVENTS (weapon + age/gender category within a tournament)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_events (
  id                  uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  tournament_id       uuid    NOT NULL REFERENCES public.fs_live_tournaments ON DELETE CASCADE,
  weapon              text    NOT NULL CHECK (weapon IN ('foil','epee','sabre')),
  category            text    NOT NULL DEFAULT 'open',
  gender              text    NOT NULL DEFAULT 'mixed' CHECK (gender IN ('male','female','mixed')),
  status              text    NOT NULL DEFAULT 'setup'
                              CHECK (status IN ('setup','pools','de','complete')),
  strip_count         integer NOT NULL DEFAULT 4 CHECK (strip_count >= 1),
  pool_target_size    integer NOT NULL DEFAULT 6 CHECK (pool_target_size BETWEEN 4 AND 8),
  -- fraction of field promoted to DE; 0.80 = top 80%
  de_cutoff_pct       numeric(4,2) NOT NULL DEFAULT 0.80
                              CHECK (de_cutoff_pct BETWEEN 0.50 AND 1.00),
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fslive_events_tournament
  ON public.fs_live_events(tournament_id);
CREATE INDEX IF NOT EXISTS idx_fslive_events_status
  ON public.fs_live_events(tournament_id, status);

-- ============================================================
-- STRIPS (physical pistes at venue)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_strips (
  id               uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  tournament_id    uuid    NOT NULL REFERENCES public.fs_live_tournaments ON DELETE CASCADE,
  number           integer NOT NULL CHECK (number >= 1),
  label            text,               -- e.g. "Piste A", "Strip 7"
  cyrano_device_id text,               -- MAC address of scoring box
  cyrano_ip        inet,               -- last resolved IP (Cyrano UDP)
  status           text    NOT NULL DEFAULT 'idle'
                           CHECK (status IN ('idle','active','offline','error')),
  UNIQUE (tournament_id, number)
);

CREATE INDEX IF NOT EXISTS idx_fslive_strips_tournament
  ON public.fs_live_strips(tournament_id);
CREATE INDEX IF NOT EXISTS idx_fslive_strips_cyrano
  ON public.fs_live_strips(cyrano_device_id)
  WHERE cyrano_device_id IS NOT NULL;

-- ============================================================
-- REGISTRATIONS (hybrid identity model)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_registrations (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id        uuid        NOT NULL REFERENCES public.fs_live_events ON DELETE CASCADE,
  -- Identity: FK to Matrix record OR loose display name (TD manual entry)
  fencer_id       uuid        REFERENCES public.fs_fencers ON DELETE SET NULL,
  display_name    text,
  club_code       text,       -- club abbreviation used for pool separation
  usfa_id         text,       -- USFA member number if known at check-in
  -- Spectator claim loop: QR code payload links fencer to user account post-event
  claim_token     uuid        NOT NULL DEFAULT gen_random_uuid(),
  claimed_user_id uuid        REFERENCES auth.users ON DELETE SET NULL,
  seed_rank       integer,
  scratch_at      timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT reg_must_have_identity CHECK (fencer_id IS NOT NULL OR display_name IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_fslive_reg_event
  ON public.fs_live_registrations(event_id);
CREATE INDEX IF NOT EXISTS idx_fslive_reg_fencer
  ON public.fs_live_registrations(fencer_id)
  WHERE fencer_id IS NOT NULL;
-- Fast lookup for active (non-scratched) fencers in pool generation
CREATE INDEX IF NOT EXISTS idx_fslive_reg_active
  ON public.fs_live_registrations(event_id, seed_rank)
  WHERE scratch_at IS NULL;
-- QR scan → claim lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_fslive_reg_claim
  ON public.fs_live_registrations(claim_token);
-- Club-separation seeding queries
CREATE INDEX IF NOT EXISTS idx_fslive_reg_club
  ON public.fs_live_registrations(event_id, club_code)
  WHERE club_code IS NOT NULL;

-- ============================================================
-- POOLS
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_pools (
  id           uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id     uuid    NOT NULL REFERENCES public.fs_live_events ON DELETE CASCADE,
  pool_number  integer NOT NULL CHECK (pool_number >= 1),
  status       text    NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','active','complete')),
  UNIQUE (event_id, pool_number)
);

CREATE INDEX IF NOT EXISTS idx_fslive_pools_event
  ON public.fs_live_pools(event_id);
CREATE INDEX IF NOT EXISTS idx_fslive_pools_pending
  ON public.fs_live_pools(event_id)
  WHERE status != 'complete';

CREATE TABLE IF NOT EXISTS public.fs_live_pool_assignments (
  pool_id         uuid    NOT NULL REFERENCES public.fs_live_pools ON DELETE CASCADE,
  registration_id uuid    NOT NULL REFERENCES public.fs_live_registrations ON DELETE CASCADE,
  -- 1-indexed position in canonical bout table order (FIE bout order table)
  position        integer NOT NULL CHECK (position >= 1),
  PRIMARY KEY (pool_id, registration_id)
);

CREATE INDEX IF NOT EXISTS idx_fslive_pool_assign_reg
  ON public.fs_live_pool_assignments(registration_id);

-- ============================================================
-- POOL BOUTS
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_pool_bouts (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  pool_id       uuid        NOT NULL REFERENCES public.fs_live_pools ON DELETE CASCADE,
  fencer_a_id   uuid        NOT NULL REFERENCES public.fs_live_registrations,
  fencer_b_id   uuid        NOT NULL REFERENCES public.fs_live_registrations,
  strip_id      uuid        REFERENCES public.fs_live_strips,
  referee_id    uuid        REFERENCES auth.users,
  status        text        NOT NULL DEFAULT 'scheduled'
                            CHECK (status IN ('scheduled','active','complete','walkover')),
  winner_id     uuid        REFERENCES public.fs_live_registrations,
  score_a       integer     CHECK (score_a >= 0),
  score_b       integer     CHECK (score_b >= 0),
  -- [{fencer_id, card: 'yellow'|'red'|'black', reason, ts}]
  cards         jsonb       NOT NULL DEFAULT '[]',
  bout_order    integer     NOT NULL CHECK (bout_order >= 1),
  started_at    timestamptz,
  ended_at      timestamptz,
  CONSTRAINT pool_bout_different_fencers CHECK (fencer_a_id != fencer_b_id)
);

-- Primary query: "what bouts are left in this pool?"
CREATE INDEX IF NOT EXISTS idx_fslive_pool_bouts_pool_status
  ON public.fs_live_pool_bouts(pool_id, status, bout_order);
-- "what is on this strip right now?"
CREATE INDEX IF NOT EXISTS idx_fslive_pool_bouts_active_strip
  ON public.fs_live_pool_bouts(strip_id)
  WHERE status = 'active';
-- Fencer bout history within event
CREATE INDEX IF NOT EXISTS idx_fslive_pool_bouts_fencer_a
  ON public.fs_live_pool_bouts(fencer_a_id, status);
CREATE INDEX IF NOT EXISTS idx_fslive_pool_bouts_fencer_b
  ON public.fs_live_pool_bouts(fencer_b_id, status);

-- ============================================================
-- POOL RESULTS (materialized after pool completes)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_pool_results (
  pool_id           uuid    NOT NULL REFERENCES public.fs_live_pools ON DELETE CASCADE,
  registration_id   uuid    NOT NULL REFERENCES public.fs_live_registrations ON DELETE CASCADE,
  victories         integer NOT NULL DEFAULT 0,
  bouts             integer NOT NULL DEFAULT 0,
  touches_scored    integer NOT NULL DEFAULT 0,
  touches_received  integer NOT NULL DEFAULT 0,
  -- Generated columns: FIE standard metrics
  vm_ratio          numeric(8,6) GENERATED ALWAYS AS (
                      CASE WHEN bouts = 0 THEN 0
                           ELSE victories::numeric / bouts
                      END
                    ) STORED,
  indicator         integer GENERATED ALWAYS AS (touches_scored - touches_received) STORED,
  pool_rank         integer,   -- rank within pool (1 = best)
  de_seed           integer,   -- global DE seeding position across all pools
  promoted          boolean    NOT NULL DEFAULT false,
  PRIMARY KEY (pool_id, registration_id)
);

-- Seeding sort: V/M desc, indicator desc, touches_scored desc
CREATE INDEX IF NOT EXISTS idx_fslive_pool_results_seeding
  ON public.fs_live_pool_results(de_seed)
  WHERE de_seed IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fslive_pool_results_promoted
  ON public.fs_live_pool_results(pool_id)
  WHERE promoted = true;

-- ============================================================
-- DE BRACKETS
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_de_brackets (
  id            uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id      uuid    NOT NULL REFERENCES public.fs_live_events ON DELETE CASCADE,
  tableau_size  integer NOT NULL CHECK (tableau_size IN (4,8,16,32,64,128,256)),
  repechage     boolean NOT NULL DEFAULT false,
  bronze_final  boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fslive_de_brackets_event
  ON public.fs_live_de_brackets(event_id);

CREATE TABLE IF NOT EXISTS public.fs_live_de_bouts (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  bracket_id      uuid        NOT NULL REFERENCES public.fs_live_de_brackets ON DELETE CASCADE,
  -- distance_from_final: 0=final, 1=semi, 2=quarter, 3=R16, etc.
  round           integer     NOT NULL CHECK (round >= 0),
  -- position within round (1-indexed from top of bracket)
  tableau_pos     integer     NOT NULL CHECK (tableau_pos >= 1),
  fencer_a_id     uuid        REFERENCES public.fs_live_registrations,
  fencer_b_id     uuid        REFERENCES public.fs_live_registrations,
  strip_id        uuid        REFERENCES public.fs_live_strips,
  referee_id      uuid        REFERENCES auth.users,
  status          text        NOT NULL DEFAULT 'scheduled'
                              CHECK (status IN ('scheduled','active','complete','walkover','bye')),
  winner_id       uuid        REFERENCES public.fs_live_registrations,
  score_a         integer     CHECK (score_a >= 0),
  score_b         integer     CHECK (score_b >= 0),
  cards           jsonb       NOT NULL DEFAULT '[]',
  period          smallint    NOT NULL DEFAULT 1 CHECK (period BETWEEN 1 AND 3),
  time_remaining_ms integer,
  started_at      timestamptz,
  ended_at        timestamptz,
  UNIQUE (bracket_id, round, tableau_pos)
);

CREATE INDEX IF NOT EXISTS idx_fslive_de_bouts_bracket_round
  ON public.fs_live_de_bouts(bracket_id, round, tableau_pos);
CREATE INDEX IF NOT EXISTS idx_fslive_de_bouts_active_strip
  ON public.fs_live_de_bouts(strip_id)
  WHERE status = 'active';
-- "next bouts ready to start" — both fencers known, not yet started
CREATE INDEX IF NOT EXISTS idx_fslive_de_bouts_ready
  ON public.fs_live_de_bouts(bracket_id, round)
  WHERE status = 'scheduled'
    AND fencer_a_id IS NOT NULL
    AND fencer_b_id IS NOT NULL;

-- ============================================================
-- STRIP ASSIGNMENTS (referee ↔ strip, per event phase)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_strip_assignments (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  strip_id      uuid        NOT NULL REFERENCES public.fs_live_strips ON DELETE CASCADE,
  referee_id    uuid        NOT NULL REFERENCES auth.users,
  event_id      uuid        NOT NULL REFERENCES public.fs_live_events ON DELETE CASCADE,
  assigned_at   timestamptz NOT NULL DEFAULT now(),
  released_at   timestamptz
);

-- Enforce single active referee per strip per event (partial unique on NULLable column)
CREATE UNIQUE INDEX IF NOT EXISTS idx_fslive_strip_assign_active
  ON public.fs_live_strip_assignments(strip_id, event_id)
  WHERE released_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_fslive_strip_assign_referee_active
  ON public.fs_live_strip_assignments(referee_id)
  WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_fslive_strip_assign_event_active
  ON public.fs_live_strip_assignments(event_id)
  WHERE released_at IS NULL;

-- ============================================================
-- DEVICE REGISTRY (authorizes devices to write event log)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_devices (
  id             uuid        PRIMARY KEY,  -- crypto.randomUUID() on first launch, stored locally
  user_id        uuid        NOT NULL REFERENCES auth.users ON DELETE CASCADE,
  tournament_id  uuid        REFERENCES public.fs_live_tournaments ON DELETE CASCADE,
  role           text        NOT NULL CHECK (role IN ('td','referee','scorer')),
  label          text,                     -- "TD Laptop", "Strip 3 iPad"
  registered_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz
);

CREATE INDEX IF NOT EXISTS idx_fslive_devices_user
  ON public.fs_live_devices(user_id);
CREATE INDEX IF NOT EXISTS idx_fslive_devices_tournament
  ON public.fs_live_devices(tournament_id)
  WHERE tournament_id IS NOT NULL;

-- ============================================================
-- CLOUD EVENT LOG (append-only; mirrors local IndexedDB queue)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_event_log (
  -- same UUID generated on device — enables global dedup
  id              uuid        NOT NULL,
  tournament_id   uuid        NOT NULL REFERENCES public.fs_live_tournaments ON DELETE CASCADE,
  device_id       uuid        NOT NULL REFERENCES public.fs_live_devices ON DELETE CASCADE,
  -- monotonically increasing per device; never reset; enables gap detection
  sequence        bigint      NOT NULL,
  type            text        NOT NULL,
  payload         jsonb       NOT NULL DEFAULT '{}',
  strip_id        uuid,
  actor_id        uuid,
  -- device local clock — intentionally preserved (not coerced to server time)
  created_at      timestamptz NOT NULL,
  received_at     timestamptz NOT NULL DEFAULT now(),
  -- composite PK: idempotent upsert by (device, sequence)
  PRIMARY KEY (device_id, sequence),
  UNIQUE (id)
);

CREATE INDEX IF NOT EXISTS idx_fslive_event_log_tournament
  ON public.fs_live_event_log(tournament_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_fslive_event_log_type
  ON public.fs_live_event_log(tournament_id, type, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_fslive_event_log_strip
  ON public.fs_live_event_log(strip_id, received_at DESC)
  WHERE strip_id IS NOT NULL;

-- ============================================================
-- SPECTATOR FLYWHEEL: follows & push subscriptions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.fs_live_spectator_follows (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  spectator_id        uuid        NOT NULL REFERENCES auth.users ON DELETE CASCADE,
  -- Follow a specific event registration (precise) OR a Matrix fencer (cross-event)
  registration_id     uuid        REFERENCES public.fs_live_registrations ON DELETE CASCADE,
  fencer_id           uuid        REFERENCES public.fs_fencers ON DELETE CASCADE,
  notify_strip_call   boolean     NOT NULL DEFAULT true,
  notify_bout_result  boolean     NOT NULL DEFAULT true,
  notify_event_result boolean     NOT NULL DEFAULT true,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT follow_must_target CHECK (registration_id IS NOT NULL OR fencer_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_fslive_follows_spectator
  ON public.fs_live_spectator_follows(spectator_id);
-- Fan-out: "who follows this registration?" — called on every FENCER_STRIP_CALLED event
CREATE INDEX IF NOT EXISTS idx_fslive_follows_registration
  ON public.fs_live_spectator_follows(registration_id)
  WHERE registration_id IS NOT NULL AND notify_strip_call = true;
CREATE INDEX IF NOT EXISTS idx_fslive_follows_fencer
  ON public.fs_live_spectator_follows(fencer_id)
  WHERE fencer_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.fs_live_push_subscriptions (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        NOT NULL REFERENCES auth.users ON DELETE CASCADE,
  -- Web Push API fields
  endpoint     text        NOT NULL,
  p256dh       text        NOT NULL,
  auth_key     text        NOT NULL,
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  -- one subscription per browser/device per user
  UNIQUE (user_id, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_fslive_push_user
  ON public.fs_live_push_subscriptions(user_id);

-- ============================================================
-- REALTIME: subscribe spectators to live score changes
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE public.fs_live_pool_bouts;
ALTER PUBLICATION supabase_realtime ADD TABLE public.fs_live_de_bouts;
ALTER PUBLICATION supabase_realtime ADD TABLE public.fs_live_strips;
ALTER PUBLICATION supabase_realtime ADD TABLE public.fs_live_pool_results;
-- Registrations: triggers spectator UI when fencer is strip-called
ALTER PUBLICATION supabase_realtime ADD TABLE public.fs_live_registrations;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE public.fs_live_tournaments      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_strips           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_registrations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_pools            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_pool_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_pool_bouts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_pool_results     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_de_brackets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_de_bouts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_strip_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_devices          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_event_log        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_spectator_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_live_push_subscriptions ENABLE ROW LEVEL SECURITY;

-- -------- Helper functions (SECURITY DEFINER = single privilege check) --------

CREATE OR REPLACE FUNCTION public.fslive_is_td(t_id uuid)
RETURNS boolean LANGUAGE sql SECURITY DEFINER STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.fs_live_tournaments
    WHERE id = t_id AND organizer_id = auth.uid()
  );
$$;

-- Referee has an active (non-released) assignment on this strip
CREATE OR REPLACE FUNCTION public.fslive_is_strip_referee(s_id uuid)
RETURNS boolean LANGUAGE sql SECURITY DEFINER STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.fs_live_strip_assignments
    WHERE strip_id = s_id
      AND referee_id = auth.uid()
      AND released_at IS NULL
  );
$$;

-- -------- Tournaments --------
CREATE POLICY "fslive_td_full_tournament" ON public.fs_live_tournaments
  FOR ALL USING (organizer_id = auth.uid());
CREATE POLICY "fslive_public_read_tournament" ON public.fs_live_tournaments
  FOR SELECT USING (status != 'setup');

-- -------- Events --------
CREATE POLICY "fslive_td_full_events" ON public.fs_live_events
  FOR ALL USING (public.fslive_is_td(tournament_id));
CREATE POLICY "fslive_public_read_events" ON public.fs_live_events
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_tournaments
      WHERE id = tournament_id AND status != 'setup'
    )
  );

-- -------- Strips --------
CREATE POLICY "fslive_td_full_strips" ON public.fs_live_strips
  FOR ALL USING (public.fslive_is_td(tournament_id));
CREATE POLICY "fslive_public_read_strips" ON public.fs_live_strips
  FOR SELECT USING (true);

-- -------- Registrations --------
CREATE POLICY "fslive_td_full_registrations" ON public.fs_live_registrations
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_events e
      WHERE e.id = event_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_public_read_registrations" ON public.fs_live_registrations
  FOR SELECT USING (true);
-- Fencer can claim their own registration (UPDATE claimed_user_id only — enforced app-side)
CREATE POLICY "fslive_fencer_claim" ON public.fs_live_registrations
  FOR UPDATE USING (claimed_user_id IS NULL OR claimed_user_id = auth.uid());

-- -------- Pools & assignments --------
CREATE POLICY "fslive_td_full_pools" ON public.fs_live_pools
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_events e
      WHERE e.id = event_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_public_read_pools" ON public.fs_live_pools
  FOR SELECT USING (true);

CREATE POLICY "fslive_td_full_pool_assignments" ON public.fs_live_pool_assignments
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_pools p
      JOIN public.fs_live_events e ON e.id = p.event_id
      WHERE p.id = pool_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_public_read_pool_assignments" ON public.fs_live_pool_assignments
  FOR SELECT USING (true);

-- -------- Pool bouts --------
CREATE POLICY "fslive_td_full_pool_bouts" ON public.fs_live_pool_bouts
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_pools p
      JOIN public.fs_live_events e ON e.id = p.event_id
      WHERE p.id = pool_id AND public.fslive_is_td(e.tournament_id)
    )
  );
-- Referee can update score/status on their assigned strip only
CREATE POLICY "fslive_referee_update_pool_bout" ON public.fs_live_pool_bouts
  FOR UPDATE USING (
    strip_id IS NOT NULL AND public.fslive_is_strip_referee(strip_id)
  );
CREATE POLICY "fslive_public_read_pool_bouts" ON public.fs_live_pool_bouts
  FOR SELECT USING (true);

-- -------- Pool results --------
CREATE POLICY "fslive_td_full_pool_results" ON public.fs_live_pool_results
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_pools p
      JOIN public.fs_live_events e ON e.id = p.event_id
      WHERE p.id = pool_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_public_read_pool_results" ON public.fs_live_pool_results
  FOR SELECT USING (true);

-- -------- DE brackets & bouts --------
CREATE POLICY "fslive_td_full_de_brackets" ON public.fs_live_de_brackets
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_events e
      WHERE e.id = event_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_public_read_de_brackets" ON public.fs_live_de_brackets
  FOR SELECT USING (true);

CREATE POLICY "fslive_td_full_de_bouts" ON public.fs_live_de_bouts
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_de_brackets b
      JOIN public.fs_live_events e ON e.id = b.event_id
      WHERE b.id = bracket_id AND public.fslive_is_td(e.tournament_id)
    )
  );
CREATE POLICY "fslive_referee_update_de_bout" ON public.fs_live_de_bouts
  FOR UPDATE USING (
    strip_id IS NOT NULL AND public.fslive_is_strip_referee(strip_id)
  );
CREATE POLICY "fslive_public_read_de_bouts" ON public.fs_live_de_bouts
  FOR SELECT USING (true);

-- -------- Strip assignments --------
CREATE POLICY "fslive_td_full_strip_assignments" ON public.fs_live_strip_assignments
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.fs_live_strips s
      WHERE s.id = strip_id AND public.fslive_is_td(s.tournament_id)
    )
  );
CREATE POLICY "fslive_referee_read_own_assignments" ON public.fs_live_strip_assignments
  FOR SELECT USING (referee_id = auth.uid());

-- -------- Devices --------
CREATE POLICY "fslive_user_own_devices" ON public.fs_live_devices
  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "fslive_td_read_tournament_devices" ON public.fs_live_devices
  FOR SELECT USING (
    tournament_id IS NOT NULL AND public.fslive_is_td(tournament_id)
  );

-- -------- Event log --------
-- Devices insert only their own events; validated by device registry
CREATE POLICY "fslive_device_insert_own_events" ON public.fs_live_event_log
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.fs_live_devices
      WHERE id = device_id AND user_id = auth.uid()
    )
  );
CREATE POLICY "fslive_td_read_event_log" ON public.fs_live_event_log
  FOR SELECT USING (public.fslive_is_td(tournament_id));

-- -------- Spectator follows --------
CREATE POLICY "fslive_own_follows" ON public.fs_live_spectator_follows
  FOR ALL USING (spectator_id = auth.uid());

-- -------- Push subscriptions --------
CREATE POLICY "fslive_own_push_subscriptions" ON public.fs_live_push_subscriptions
  FOR ALL USING (user_id = auth.uid());
