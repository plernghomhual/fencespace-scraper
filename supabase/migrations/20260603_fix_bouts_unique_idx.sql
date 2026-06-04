-- Fix: fs_bouts was missing UNIQUE constraint on id, causing 42P10 on all upserts with on_conflict="id"
CREATE UNIQUE INDEX IF NOT EXISTS fs_bouts_id_key ON public.fs_bouts (id);
