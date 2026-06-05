-- Marketplace subscriptions, API-key entitlements, Stripe webhook idempotency,
-- and usage counters. Private tables are service-role only by default.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fs_marketplace_plans (
    plan_id                 text PRIMARY KEY,
    name                    text NOT NULL,
    description             text,
    stripe_price_id          text,
    monthly_request_limit   integer CHECK (
        monthly_request_limit IS NULL OR monthly_request_limit >= 0
    ),
    scopes                  text[] NOT NULL DEFAULT '{}',
    active                  boolean NOT NULL DEFAULT true,
    requires_subscription   boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_marketplace_customers (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_customer_id  text UNIQUE,
    email               text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_marketplace_api_keys (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash            text NOT NULL UNIQUE,
    label               text,
    customer_id          uuid REFERENCES public.fs_marketplace_customers(id) ON DELETE SET NULL,
    plan_id             text REFERENCES public.fs_marketplace_plans(plan_id),
    subscription_id     uuid,
    scopes              text[] NOT NULL DEFAULT '{}',
    active              boolean NOT NULL DEFAULT true,
    revoked_at          timestamptz,
    expires_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_marketplace_subscriptions (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id              uuid REFERENCES public.fs_marketplace_customers(id) ON DELETE SET NULL,
    api_key_id               uuid REFERENCES public.fs_marketplace_api_keys(id) ON DELETE SET NULL,
    plan_id                  text REFERENCES public.fs_marketplace_plans(plan_id),
    stripe_subscription_id   text UNIQUE,
    stripe_customer_id       text,
    status                  text NOT NULL DEFAULT 'incomplete' CHECK (
        status IN (
            'incomplete',
            'incomplete_expired',
            'trialing',
            'active',
            'past_due',
            'canceled',
            'unpaid',
            'paused'
        )
    ),
    current_period_start     timestamptz,
    current_period_end       timestamptz,
    cancel_at_period_end     boolean NOT NULL DEFAULT false,
    last_invoice_status      text,
    metadata                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fs_marketplace_usage_counters (
    api_key_id          uuid NOT NULL REFERENCES public.fs_marketplace_api_keys(id) ON DELETE CASCADE,
    scope               text NOT NULL,
    period_start        date NOT NULL,
    period_end          date NOT NULL,
    request_count       integer NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    last_request_at     timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (api_key_id, scope, period_start)
);

CREATE TABLE IF NOT EXISTS public.fs_stripe_webhook_events (
    id              text PRIMARY KEY,
    type            text,
    livemode        boolean NOT NULL DEFAULT false,
    processed       boolean NOT NULL DEFAULT false,
    received_at     timestamptz NOT NULL DEFAULT now(),
    processed_at    timestamptz,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    error           text
);

ALTER TABLE public.fs_marketplace_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_marketplace_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_marketplace_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_marketplace_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_marketplace_usage_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fs_stripe_webhook_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.fs_marketplace_plans FROM anon, authenticated;
REVOKE ALL ON public.fs_marketplace_customers FROM anon, authenticated;
REVOKE ALL ON public.fs_marketplace_api_keys FROM anon, authenticated;
REVOKE ALL ON public.fs_marketplace_subscriptions FROM anon, authenticated;
REVOKE ALL ON public.fs_marketplace_usage_counters FROM anon, authenticated;
REVOKE ALL ON public.fs_stripe_webhook_events FROM anon, authenticated;

CREATE INDEX IF NOT EXISTS idx_fs_marketplace_api_keys_customer
    ON public.fs_marketplace_api_keys(customer_id);
CREATE INDEX IF NOT EXISTS idx_fs_marketplace_subscriptions_customer
    ON public.fs_marketplace_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_fs_marketplace_subscriptions_api_key
    ON public.fs_marketplace_subscriptions(api_key_id);
CREATE INDEX IF NOT EXISTS idx_fs_marketplace_usage_period
    ON public.fs_marketplace_usage_counters(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_fs_stripe_webhook_events_processed
    ON public.fs_stripe_webhook_events(processed, received_at);

INSERT INTO public.fs_marketplace_plans (
    plan_id,
    name,
    description,
    monthly_request_limit,
    scopes
) VALUES
    (
        'starter',
        'Starter',
        'Public fencer and tournament marketplace access.',
        10000,
        ARRAY['data:fencers:read', 'data:tournaments:read']
    ),
    (
        'growth',
        'Growth',
        'Higher-volume access with rankings and analytics scopes.',
        100000,
        ARRAY[
            'data:fencers:read',
            'data:tournaments:read',
            'data:rankings:read',
            'data:analytics:read',
            'data:syndication:read'
        ]
    ),
    (
        'enterprise',
        'Enterprise',
        'Custom-volume data syndication and analytics access.',
        NULL,
        ARRAY[
            'data:fencers:read',
            'data:tournaments:read',
            'data:rankings:read',
            'data:analytics:read',
            'data:syndication:read'
        ]
    )
ON CONFLICT (plan_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    monthly_request_limit = EXCLUDED.monthly_request_limit,
    scopes = EXCLUDED.scopes,
    updated_at = now();

CREATE OR REPLACE FUNCTION public.fs_marketplace_increment_usage(
    p_api_key_id uuid,
    p_scope text,
    p_period_start date,
    p_period_end date,
    p_limit integer
) RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    next_count integer;
BEGIN
    INSERT INTO public.fs_marketplace_usage_counters (
        api_key_id,
        scope,
        period_start,
        period_end,
        request_count,
        last_request_at,
        updated_at
    )
    VALUES (
        p_api_key_id,
        p_scope,
        p_period_start,
        p_period_end,
        1,
        now(),
        now()
    )
    ON CONFLICT (api_key_id, scope, period_start)
    DO UPDATE SET
        request_count = public.fs_marketplace_usage_counters.request_count + 1,
        period_end = EXCLUDED.period_end,
        last_request_at = now(),
        updated_at = now()
    RETURNING request_count INTO next_count;

    IF p_limit IS NOT NULL AND next_count > p_limit THEN
        RAISE EXCEPTION 'usage limit exceeded' USING ERRCODE = 'P0001';
    END IF;

    RETURN next_count;
END;
$$;

REVOKE ALL ON FUNCTION public.fs_marketplace_increment_usage(uuid, text, date, date, integer)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fs_marketplace_increment_usage(uuid, text, date, date, integer)
TO service_role;
