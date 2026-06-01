-- API key table for fs_api.py authentication.
-- Read by service_role only (RLS enabled, no authenticated policy).

CREATE TABLE IF NOT EXISTS public.fs_api_keys (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text        NOT NULL UNIQUE,
    name        text,
    active      boolean     NOT NULL DEFAULT true,
    revoked     boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_api_keys ENABLE ROW LEVEL SECURITY;

-- No SELECT policy for authenticated/anon — service_role bypasses RLS.
REVOKE ALL ON public.fs_api_keys FROM anon, authenticated;
