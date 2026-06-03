ALTER TABLE public.fs_tournaments
    ADD COLUMN IF NOT EXISTS organizer text,
    ADD COLUMN IF NOT EXISTS entry_deadline date,
    ADD COLUMN IF NOT EXISTS format text,
    ADD COLUMN IF NOT EXISTS quota integer,
    ADD COLUMN IF NOT EXISTS venue_details text,
    ADD COLUMN IF NOT EXISTS registration_url text,
    ADD COLUMN IF NOT EXISTS live_results_url text,
    ADD COLUMN IF NOT EXISTS detail_source text;

CREATE INDEX IF NOT EXISTS idx_fs_tournaments_entry_deadline
    ON public.fs_tournaments (entry_deadline);

CREATE INDEX IF NOT EXISTS idx_fs_tournaments_organizer
    ON public.fs_tournaments (organizer);
