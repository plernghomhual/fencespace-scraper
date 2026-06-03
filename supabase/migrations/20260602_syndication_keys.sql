-- Partner syndication API credentials and sanitized request logs.
-- API keys are stored as SHA-256 hashes; plaintext partner secrets must only
-- be shown at provisioning time and never inserted into this schema.

CREATE TABLE IF NOT EXISTS public.fs_syndication_keys (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_name          text        NOT NULL,
    key_hash              text        NOT NULL UNIQUE,
    scopes                text[]      NOT NULL DEFAULT ARRAY[]::text[],
    rate_limit_per_minute integer     NOT NULL DEFAULT 100 CHECK (rate_limit_per_minute > 0),
    disabled              boolean     NOT NULL DEFAULT false,
    last_used_at          timestamptz,
    created_at            timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at            timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fs_syndication_keys_scopes_known CHECK (
        scopes <@ ARRAY[
            '*',
            'fencers:read',
            'tournaments:read',
            'rankings:read',
            'results:read',
            'medals:read'
        ]::text[]
    )
);

CREATE INDEX IF NOT EXISTS idx_fs_syndication_keys_disabled
    ON public.fs_syndication_keys(disabled);

CREATE TABLE IF NOT EXISTS public.fs_syndication_request_logs (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key_id       uuid REFERENCES public.fs_syndication_keys(id) ON DELETE SET NULL,
    partner_name text,
    scope        text,
    method       text        NOT NULL,
    path         text        NOT NULL,
    status_code  integer     NOT NULL CHECK (status_code >= 100 AND status_code <= 599),
    query_params jsonb       NOT NULL DEFAULT '{}'::jsonb,
    ip_hash      text,
    user_agent   text,
    created_at   timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_fs_syndication_request_logs_key_created
    ON public.fs_syndication_request_logs(key_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fs_syndication_request_logs_status_created
    ON public.fs_syndication_request_logs(status_code, created_at DESC);

ALTER TABLE public.fs_syndication_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_syndication_request_logs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_syndication_keys FROM anon, authenticated;
REVOKE ALL ON public.fs_syndication_request_logs FROM anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON public.fs_syndication_keys TO service_role;
GRANT SELECT, INSERT ON public.fs_syndication_request_logs TO service_role;

CREATE OR REPLACE FUNCTION public.touch_fs_syndication_keys_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fs_syndication_keys_updated_at
ON public.fs_syndication_keys;

CREATE TRIGGER trg_fs_syndication_keys_updated_at
BEFORE UPDATE ON public.fs_syndication_keys
FOR EACH ROW
EXECUTE FUNCTION public.touch_fs_syndication_keys_updated_at();

REVOKE ALL ON FUNCTION public.touch_fs_syndication_keys_updated_at() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.touch_fs_syndication_keys_updated_at() FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.touch_fs_syndication_keys_updated_at() TO service_role;

