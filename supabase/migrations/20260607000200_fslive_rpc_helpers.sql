-- FenceSpace Live: RPC helpers for jsonb array operations on bout cards.
-- Called by the live-sync Edge Function to avoid read-modify-write races.
-- Migration: 20260607_fslive_rpc_helpers.sql

-- Append a card entry to a bout's cards jsonb column.
-- p_table must be 'fs_live_pool_bouts' or 'fs_live_de_bouts'.
-- p_card shape: {fencer_id, card, reason, ts}
CREATE OR REPLACE FUNCTION public.fslive_append_card(
  p_table   text,
  p_bout_id uuid,
  p_card    jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  IF p_table NOT IN ('fs_live_pool_bouts', 'fs_live_de_bouts') THEN
    RAISE EXCEPTION 'invalid table: %', p_table;
  END IF;

  IF p_table = 'fs_live_pool_bouts' THEN
    UPDATE public.fs_live_pool_bouts
    SET cards = cards || jsonb_build_array(p_card)
    WHERE id = p_bout_id;
  ELSE
    UPDATE public.fs_live_de_bouts
    SET cards = cards || jsonb_build_array(p_card)
    WHERE id = p_bout_id;
  END IF;
END;
$$;

-- Remove the first card matching fencer_id + card type.
-- Filters the jsonb array in-place without a separate read.
CREATE OR REPLACE FUNCTION public.fslive_remove_card(
  p_table     text,
  p_bout_id   uuid,
  p_fencer_id text,
  p_card      text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  removed boolean := false;
BEGIN
  IF p_table NOT IN ('fs_live_pool_bouts', 'fs_live_de_bouts') THEN
    RAISE EXCEPTION 'invalid table: %', p_table;
  END IF;

  IF p_table = 'fs_live_pool_bouts' THEN
    UPDATE public.fs_live_pool_bouts
    SET cards = (
      SELECT jsonb_agg(elem)
      FROM (
        SELECT elem, row_number() OVER () AS rn
        FROM jsonb_array_elements(cards) AS elem
      ) sub
      -- Remove only the first matching entry (one revocation = one card removed)
      WHERE NOT (
        elem->>'fencer_id' = p_fencer_id
        AND elem->>'card' = p_card
        AND NOT removed
        AND (removed := true) IS NOT NULL
      )
    )
    WHERE id = p_bout_id;
  ELSE
    UPDATE public.fs_live_de_bouts
    SET cards = (
      SELECT jsonb_agg(elem)
      FROM (
        SELECT elem, row_number() OVER () AS rn
        FROM jsonb_array_elements(cards) AS elem
      ) sub
      WHERE NOT (
        elem->>'fencer_id' = p_fencer_id
        AND elem->>'card' = p_card
        AND NOT removed
        AND (removed := true) IS NOT NULL
      )
    )
    WHERE id = p_bout_id;
  END IF;
END;
$$;

-- Grant execution to the service role only (Edge Function uses service role key)
REVOKE ALL ON FUNCTION public.fslive_append_card FROM PUBLIC;
REVOKE ALL ON FUNCTION public.fslive_remove_card FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fslive_append_card TO service_role;
GRANT EXECUTE ON FUNCTION public.fslive_remove_card TO service_role;
