# FenceSpace Marketplace API

The marketplace API wraps paid data access around public-safe FenceSpace views.
It is intentionally separate from `api.py` so subscription, webhook, and usage
logic can be deployed and tested without changing the existing export API.

## Access Model

API keys are stored only as SHA-256 hashes in `fs_marketplace_api_keys`.
Optional `FENCESPACE_MARKETPLACE_KEY_PEPPER` is included in the hash input, so
set it before issuing customer keys and keep it stable afterward.

Access is granted only when all checks pass:

- the raw `X-API-Key` hashes to an active, unrevoked key;
- the key has not expired;
- the linked plan is active;
- the linked subscription is `active` or `trialing`;
- the requested scope is present in both the key and plan scope set when both
  are configured;
- the monthly request limit has not been reached.

Current scoped public-data routes:

- `GET /data/fencers/search` requires `data:fencers:read` and queries
  `v_fencer_public`.
- `GET /data/tournaments` requires `data:tournaments:read` and queries
  `v_tournament_public`.

Do not point marketplace routes at base tables containing private metadata or
scraper-only fields.

## Stripe Safety

Stripe Checkout and Customer Portal helpers accept only test-mode keys by
default. Live keys and live webhook events are rejected unless:

```bash
export FENCESPACE_ALLOW_LIVE_STRIPE=true
```

Only set that variable after explicit production approval. Tests and local
development should use `sk_test_...` keys and `whsec_...` webhook secrets.

The implementation uses Stripe Checkout Sessions for subscriptions and Customer
Portal Sessions for customer self-service. It does not require the Stripe Python
SDK; it posts form-encoded requests through `requests` and pins the request
header to Stripe API version `2026-02-25.clover`.

Reference docs:

- Checkout Sessions: https://docs.stripe.com/api/checkout/sessions
- Customer Portal Sessions: https://docs.stripe.com/api/customer_portal/sessions
- Webhook signatures: https://docs.stripe.com/webhooks/signature

## Environment

Required for Supabase access:

```bash
export SUPABASE_URL="https://..."
export SUPABASE_SERVICE_KEY="..."
```

Required for Stripe Checkout, Portal, and webhooks:

```bash
export STRIPE_SECRET_KEY="sk_test_..."
export STRIPE_WEBHOOK_SECRET="whsec_..."
export STRIPE_PRICE_ID_STARTER="price_..."
export STRIPE_PRICE_ID_GROWTH="price_..."
export STRIPE_PRICE_ID_ENTERPRISE="price_..."
```

Optional:

```bash
export FENCESPACE_MARKETPLACE_KEY_PEPPER="stable-random-secret"
export STRIPE_WEBHOOK_TOLERANCE_SECONDS=300
export FENCESPACE_ALLOW_LIVE_STRIPE=false
```

## Local Webhook Testing

Run the marketplace service locally:

```bash
uvicorn marketplace_api:app --reload --port 8001
```

Forward Stripe test events:

```bash
stripe listen --forward-to localhost:8001/stripe/webhook
```

Copy the printed `whsec_...` value into `STRIPE_WEBHOOK_SECRET`, then trigger
test events:

```bash
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_failed
```

The webhook handler verifies the raw request body against the
`Stripe-Signature` header before parsing JSON. Duplicate events return a
duplicate status and do not re-apply subscription changes.

## Failure Handling

- `400 Invalid Stripe webhook`: signature, timestamp, JSON, missing event ID,
  or live-mode event rejected.
- `401`: missing, invalid, revoked, or expired marketplace API key.
- `402`: subscription missing or not `active`/`trialing`.
- `403`: inactive plan or missing scope entitlement.
- `429`: monthly request limit reached.
- `500`: Stripe webhook processing failed after signature verification.
- `502`: Supabase or Stripe API request failed.

Logs intentionally avoid raw webhook payloads, Stripe secrets, API keys, and
signature header contents. Webhook payloads are stored only in the private
`fs_stripe_webhook_events` table for idempotency and audit.
