-- Add result loss fields for evidence-backed backfills.
-- Data backfill is performed separately by scripts/backfill_result_losses.py.

ALTER TABLE public.fs_results
    ADD COLUMN IF NOT EXISTS defeats integer,
    ADD COLUMN IF NOT EXISTS elimination_loss_metadata jsonb DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fs_results_defeats_nonnegative'
          AND conrelid = 'public.fs_results'::regclass
    ) THEN
        ALTER TABLE public.fs_results
            ADD CONSTRAINT fs_results_defeats_nonnegative
            CHECK (defeats IS NULL OR defeats >= 0)
            NOT VALID;
    END IF;
END $$;
