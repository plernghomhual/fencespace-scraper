-- Dedup index for FRED/AskFRED result rows where fie_fencer_id is NULL.
-- These scrapers use (tournament_id, name) as the natural key since fencers
-- are matched by USA Fencing ID or name but fie_fencer_id is not populated.
-- This prevents duplicate rows from multi-run incremental scraping.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fs_results_tournament_name_nofieid
    ON public.fs_results (tournament_id, lower(name))
    WHERE fie_fencer_id IS NULL
      AND metadata ? 'fred_fencer_key';
