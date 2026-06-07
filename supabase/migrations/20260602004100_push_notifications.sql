-- Mobile push notification subscriptions and delivery logs.
-- Service-role jobs write delivery logs; authenticated users may manage only
-- their own devices/subscriptions through RLS ownership checks.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_push_devices (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform       text        NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    app_install_id text        NOT NULL,
    opt_in         boolean     NOT NULL DEFAULT false,
    disabled       boolean     NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, app_install_id)
);

CREATE TABLE IF NOT EXISTS public.fs_push_subscriptions (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    device_id         uuid        NOT NULL REFERENCES public.fs_push_devices(id) ON DELETE CASCADE,
    notification_type text        NOT NULL DEFAULT 'live_result',
    provider          text        NOT NULL CHECK (provider IN ('dry-run', 'apns', 'fcm')),
    provider_token    text        NOT NULL,
    tournament_id     uuid        REFERENCES public.fs_tournaments(id) ON DELETE CASCADE,
    opt_in            boolean     NOT NULL DEFAULT false,
    disabled          boolean     NOT NULL DEFAULT false,
    last_sent_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, device_id, notification_type, tournament_id)
);

CREATE TABLE IF NOT EXISTS public.fs_push_delivery_log (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id   uuid        NOT NULL REFERENCES public.fs_push_subscriptions(id) ON DELETE CASCADE,
    user_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_fingerprint text        NOT NULL,
    event_type        text        NOT NULL DEFAULT 'live_result',
    provider          text        NOT NULL CHECK (provider IN ('dry-run', 'apns', 'fcm')),
    status            text        NOT NULL CHECK (status IN ('dry_run', 'dry_run_missing_credentials', 'sent', 'failed')),
    attempt_count     integer     NOT NULL DEFAULT 1 CHECK (attempt_count >= 1),
    dry_run           boolean     NOT NULL DEFAULT true,
    payload           jsonb       NOT NULL DEFAULT '{}'::jsonb,
    provider_message_id text,
    error             text,
    next_attempt_at   timestamptz,
    delivered_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subscription_id, event_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_live_enabled
ON public.fs_push_subscriptions (notification_type, tournament_id)
WHERE opt_in AND NOT disabled;

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_device
ON public.fs_push_subscriptions (device_id);

CREATE INDEX IF NOT EXISTS idx_push_delivery_log_user_created
ON public.fs_push_delivery_log (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_push_delivery_log_retry
ON public.fs_push_delivery_log (status, next_attempt_at)
WHERE status = 'failed';

ALTER TABLE public.fs_push_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_push_delivery_log ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_push_devices FROM anon, authenticated;
REVOKE ALL ON public.fs_push_subscriptions FROM anon, authenticated;
REVOKE ALL ON public.fs_push_delivery_log FROM anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON public.fs_push_devices TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.fs_push_subscriptions TO authenticated;
GRANT SELECT ON public.fs_push_delivery_log TO authenticated;

DROP POLICY IF EXISTS push_devices_owner_select ON public.fs_push_devices;
CREATE POLICY push_devices_owner_select ON public.fs_push_devices
FOR SELECT TO authenticated
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS push_devices_owner_insert ON public.fs_push_devices;
CREATE POLICY push_devices_owner_insert ON public.fs_push_devices
FOR INSERT TO authenticated
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS push_devices_owner_update ON public.fs_push_devices;
CREATE POLICY push_devices_owner_update ON public.fs_push_devices
FOR UPDATE TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS push_subscriptions_owner_select ON public.fs_push_subscriptions;
CREATE POLICY push_subscriptions_owner_select ON public.fs_push_subscriptions
FOR SELECT TO authenticated
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS push_subscriptions_owner_insert ON public.fs_push_subscriptions;
CREATE POLICY push_subscriptions_owner_insert ON public.fs_push_subscriptions
FOR INSERT TO authenticated
WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
        SELECT 1
        FROM public.fs_push_devices device
        WHERE device.id = device_id
          AND device.user_id = auth.uid()
          AND device.disabled = false
    )
);

DROP POLICY IF EXISTS push_subscriptions_owner_update ON public.fs_push_subscriptions;
CREATE POLICY push_subscriptions_owner_update ON public.fs_push_subscriptions
FOR UPDATE TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
        SELECT 1
        FROM public.fs_push_devices device
        WHERE device.id = device_id
          AND device.user_id = auth.uid()
          AND device.disabled = false
    )
);

DROP POLICY IF EXISTS push_delivery_owner_select ON public.fs_push_delivery_log;
CREATE POLICY push_delivery_owner_select ON public.fs_push_delivery_log
FOR SELECT TO authenticated
USING (auth.uid() = user_id);

-- No anon/authenticated insert policy for delivery logs; service_role writes only.

COMMENT ON TABLE public.fs_push_devices IS
    'Opt-in mobile push devices owned by authenticated users.';
COMMENT ON TABLE public.fs_push_subscriptions IS
    'Live-result push subscriptions; provider tokens are service-read for delivery.';
COMMENT ON TABLE public.fs_push_delivery_log IS
    'Idempotent push delivery audit log keyed by subscription and event fingerprint.';
