CREATE TABLE IF NOT EXISTS public.fs_ranking_alert_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id text NOT NULL,
    weapon text,
    category text,
    email text,
    phone_e164 text,
    email_opt_in boolean NOT NULL DEFAULT false,
    sms_opt_in boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    email_opted_in_at timestamptz,
    sms_opted_in_at timestamptz,
    unsubscribed_at timestamptz,
    unsubscribe_token_hash text NOT NULL,
    unsubscribe_token_hint text,
    min_rank_change integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}',
    CONSTRAINT fs_ranking_alert_subscriptions_channel_check
        CHECK (email_opt_in OR sms_opt_in),
    CONSTRAINT fs_ranking_alert_subscriptions_contact_check
        CHECK (
            (email_opt_in = false OR email IS NOT NULL)
            AND (sms_opt_in = false OR phone_e164 IS NOT NULL)
        ),
    CONSTRAINT fs_ranking_alert_subscriptions_phone_check
        CHECK (phone_e164 IS NULL OR phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
    CONSTRAINT fs_ranking_alert_subscriptions_min_change_check
        CHECK (min_rank_change >= 1)
);

ALTER TABLE public.fs_ranking_alert_subscriptions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_ranking_alert_subscriptions FROM anon;
REVOKE ALL ON public.fs_ranking_alert_subscriptions FROM authenticated;

CREATE INDEX IF NOT EXISTS idx_fs_ranking_alert_subscriptions_fencer
    ON public.fs_ranking_alert_subscriptions (fencer_id, active)
    WHERE unsubscribed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_fs_ranking_alert_subscriptions_token_hash
    ON public.fs_ranking_alert_subscriptions (unsubscribe_token_hash);

CREATE TABLE IF NOT EXISTS public.fs_ranking_alert_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id uuid NOT NULL
        REFERENCES public.fs_ranking_alert_subscriptions(id) ON DELETE CASCADE,
    idempotency_key text NOT NULL,
    fencer_id text NOT NULL,
    weapon text NOT NULL,
    category text NOT NULL,
    season integer NOT NULL,
    rank integer NOT NULL,
    previous_rank integer,
    rank_change integer NOT NULL,
    channel text NOT NULL,
    provider text NOT NULL,
    status text NOT NULL,
    contact_hash text NOT NULL,
    provider_message_id text,
    error text,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    CONSTRAINT fs_ranking_alert_deliveries_idempotency_key_key
        UNIQUE (idempotency_key),
    CONSTRAINT fs_ranking_alert_deliveries_channel_check
        CHECK (channel IN ('email', 'sms')),
    CONSTRAINT fs_ranking_alert_deliveries_status_check
        CHECK (status IN ('dry_run', 'sent', 'failed', 'rate_limited', 'skipped'))
);

ALTER TABLE public.fs_ranking_alert_deliveries ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_ranking_alert_deliveries FROM anon;
REVOKE ALL ON public.fs_ranking_alert_deliveries FROM authenticated;

CREATE INDEX IF NOT EXISTS idx_fs_ranking_alert_deliveries_subscription_created
    ON public.fs_ranking_alert_deliveries (subscription_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fs_ranking_alert_deliveries_fencer_change
    ON public.fs_ranking_alert_deliveries (fencer_id, weapon, category, season);
