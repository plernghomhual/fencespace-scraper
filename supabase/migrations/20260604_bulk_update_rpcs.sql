-- Bulk update RPCs for maintenance jobs that need different values per row.
-- These avoid per-row Supabase update loops without using unsafe partial upserts.

CREATE OR REPLACE FUNCTION public.fs_bulk_update_fencer_matches(
    p_table_name text,
    p_updates jsonb
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    updated_count integer := 0;
BEGIN
    IF p_table_name NOT IN ('fs_results', 'fs_national_fed_rankings') THEN
        RAISE EXCEPTION 'unsupported table for fencer match bulk update';
    END IF;

    IF p_updates IS NULL OR jsonb_typeof(p_updates) <> 'array' THEN
        RETURN 0;
    END IF;

    IF p_table_name = 'fs_results' THEN
        WITH payload AS (
            SELECT id, fencer_id
            FROM jsonb_to_recordset(p_updates) AS x(id text, fencer_id text)
            WHERE id IS NOT NULL AND fencer_id IS NOT NULL
        ),
        updated AS (
            UPDATE public.fs_results AS target
            SET fencer_id = payload.fencer_id::uuid
            FROM payload
            WHERE target.id::text = payload.id
            RETURNING target.id
        )
        SELECT count(*) INTO updated_count FROM updated;
    ELSE
        WITH payload AS (
            SELECT id, fencer_id
            FROM jsonb_to_recordset(p_updates) AS x(id text, fencer_id text)
            WHERE id IS NOT NULL AND fencer_id IS NOT NULL
        ),
        updated AS (
            UPDATE public.fs_national_fed_rankings AS target
            SET fencer_id = payload.fencer_id::uuid
            FROM payload
            WHERE target.id::text = payload.id
            RETURNING target.id
        )
        SELECT count(*) INTO updated_count FROM updated;
    END IF;

    RETURN updated_count;
END;
$$;

REVOKE ALL ON FUNCTION public.fs_bulk_update_fencer_matches(text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fs_bulk_update_fencer_matches(text, jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.fs_bulk_update_result_losses(
    p_updates jsonb
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    updated_count integer := 0;
BEGIN
    IF p_updates IS NULL OR jsonb_typeof(p_updates) <> 'array' THEN
        RETURN 0;
    END IF;

    WITH payload AS (
        SELECT
            id,
            tournament_id,
            fencer_id,
            name,
            defeats,
            elimination_loss_metadata
        FROM jsonb_to_recordset(p_updates) AS x(
            id text,
            tournament_id text,
            fencer_id text,
            name text,
            defeats integer,
            elimination_loss_metadata jsonb
        )
    ),
    updated AS (
        UPDATE public.fs_results AS target
        SET
            defeats = payload.defeats,
            elimination_loss_metadata = COALESCE(payload.elimination_loss_metadata, '{}'::jsonb)
        FROM payload
        WHERE
            (
                payload.id IS NOT NULL
                AND target.id::text = payload.id
            )
            OR (
                payload.id IS NULL
                AND payload.tournament_id IS NOT NULL
                AND payload.fencer_id IS NOT NULL
                AND target.tournament_id::text = payload.tournament_id
                AND target.fencer_id::text = payload.fencer_id
            )
            OR (
                payload.id IS NULL
                AND payload.fencer_id IS NULL
                AND payload.tournament_id IS NOT NULL
                AND payload.name IS NOT NULL
                AND target.tournament_id::text = payload.tournament_id
                AND target.name = payload.name
            )
        RETURNING target.id
    )
    SELECT count(*) INTO updated_count FROM updated;

    RETURN updated_count;
END;
$$;

REVOKE ALL ON FUNCTION public.fs_bulk_update_result_losses(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fs_bulk_update_result_losses(jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.fs_bulk_update_tournament_metadata(
    p_updates jsonb
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    updated_count integer := 0;
BEGIN
    IF p_updates IS NULL OR jsonb_typeof(p_updates) <> 'array' THEN
        RETURN 0;
    END IF;

    WITH payload AS (
        SELECT id, metadata
        FROM jsonb_to_recordset(p_updates) AS x(id text, metadata jsonb)
        WHERE id IS NOT NULL
    ),
    updated AS (
        UPDATE public.fs_tournaments AS target
        SET metadata = COALESCE(payload.metadata, '{}'::jsonb)
        FROM payload
        WHERE target.id::text = payload.id
        RETURNING target.id
    )
    SELECT count(*) INTO updated_count FROM updated;

    RETURN updated_count;
END;
$$;

REVOKE ALL ON FUNCTION public.fs_bulk_update_tournament_metadata(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fs_bulk_update_tournament_metadata(jsonb) TO service_role;
