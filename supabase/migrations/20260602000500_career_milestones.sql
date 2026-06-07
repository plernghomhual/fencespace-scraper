CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_career_milestones (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id     uuid REFERENCES public.fs_fencer_identities(id) ON DELETE SET NULL,
    fencer_id       uuid REFERENCES public.fs_fencers(id) ON DELETE SET NULL,
    fie_id          text,
    fencer_name     text,
    milestone_type  text NOT NULL,
    milestone_date  date NOT NULL,
    tournament_id   uuid REFERENCES public.fs_tournaments(id) ON DELETE SET NULL,
    weapon          text,
    season          text,
    title           text NOT NULL,
    description     text,
    rank            integer CHECK (rank IS NULL OR rank > 0),
    medal           text CHECK (medal IS NULL OR medal IN ('gold', 'silver', 'bronze')),
    source          text NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    person_key      text GENERATED ALWAYS AS (
        COALESCE(
            identity_id::text,
            fencer_id::text,
            NULLIF(BTRIM(fie_id), ''),
            LOWER(NULLIF(BTRIM(fencer_name), ''))
        )
    ) STORED,
    tournament_key  text GENERATED ALWAYS AS (
        COALESCE(tournament_id::text, '__no_tournament__')
    ) STORED,
    CONSTRAINT fs_career_milestones_person_required
        CHECK (person_key IS NOT NULL),
    CONSTRAINT fs_career_milestones_type_not_blank
        CHECK (BTRIM(milestone_type) <> ''),
    CONSTRAINT fs_career_milestones_title_not_blank
        CHECK (BTRIM(title) <> ''),
    CONSTRAINT fs_career_milestones_source_not_blank
        CHECK (BTRIM(source) <> ''),
    CONSTRAINT fs_career_milestones_unique_person_type_event_date
        UNIQUE (person_key, milestone_type, tournament_key, milestone_date)
);

CREATE INDEX IF NOT EXISTS idx_fs_career_milestones_identity_timeline
    ON public.fs_career_milestones (identity_id, milestone_date DESC, created_at DESC)
    WHERE identity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_career_milestones_fencer_timeline
    ON public.fs_career_milestones (fencer_id, milestone_date DESC, created_at DESC)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_career_milestones_type_date
    ON public.fs_career_milestones (milestone_type, milestone_date DESC);

ALTER TABLE public.fs_career_milestones ENABLE ROW LEVEL SECURITY;
