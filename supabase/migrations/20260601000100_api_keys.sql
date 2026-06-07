-- API key table for primary API authentication.
-- Read by service_role only (RLS enabled, no authenticated policy).
--
-- Primary API key rotation cutover:
-- backfill key_hash for every existing plaintext key, rotate production
-- consumers to replacement keys, then remove plaintext storage and the
-- application fallback that compares incoming keys to public.fs_api_keys.key.
--
-- Plaintext compatibility window:
-- during rotation, application verification accepts either
-- sha256(incoming_key) = key_hash or incoming_key = key.

CREATE TABLE IF NOT EXISTS public.fs_api_keys (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text        UNIQUE,
    key_hash    text        UNIQUE,
    name        text,
    active      boolean     NOT NULL DEFAULT true,
    revoked     boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.fs_api_keys ADD COLUMN IF NOT EXISTS key_hash text;
ALTER TABLE public.fs_api_keys ALTER COLUMN key DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS fs_api_keys_key_hash_key
    ON public.fs_api_keys (key_hash)
    WHERE key_hash IS NOT NULL;

ALTER TABLE public.fs_api_keys ENABLE ROW LEVEL SECURITY;

-- No SELECT policy for authenticated/anon — service_role bypasses RLS.
REVOKE ALL ON public.fs_api_keys FROM anon, authenticated;
