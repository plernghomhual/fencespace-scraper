# FenceSpace Syndication API

Read-only API for approved media and data partners. The API exposes public
fencer, tournament, ranking, result, and medal-table data through scoped partner
keys.

Base path:

```text
/syndication/v1
```

## Partner Onboarding

1. Generate a high-entropy partner secret.

   ```bash
   openssl rand -hex 32
   ```

2. Store only its SHA-256 hash in `fs_syndication_keys`.

   ```bash
   python - <<'PY'
   import hashlib

   secret = "paste-partner-secret-here"
   print(hashlib.sha256(secret.encode("utf-8")).hexdigest())
   PY
   ```

3. Insert the partner row with the minimum required scopes.

   ```sql
   INSERT INTO public.fs_syndication_keys (
       partner_name,
       key_hash,
       scopes,
       rate_limit_per_minute
   )
   VALUES (
       'Example Media',
       '<sha256-hex-hash>',
       ARRAY['fencers:read', 'tournaments:read', 'rankings:read']::text[],
       120
   );
   ```

4. Send the plaintext secret to the partner once through an approved secure
   channel. Do not store plaintext keys in Supabase, logs, tickets, docs, or
   chat.

5. Disable access by setting `disabled = true`. Rotate access by issuing a new
   secret, updating `key_hash`, and communicating the new plaintext secret once.

## Authentication

Preferred header:

```bash
curl 'https://api.example.com/syndication/v1/fencers?country=KOR' \
  -H 'X-API-Key: <partner-secret>'
```

Bearer tokens are also accepted for partner tooling that cannot set custom
headers:

```bash
curl 'https://api.example.com/syndication/v1/fencers?country=KOR' \
  -H 'Authorization: Bearer <partner-secret>'
```

Do not send secrets in query parameters. If a request includes sensitive query
keys such as `api_key` or `token`, request logging stores `[redacted]`.

## Scopes

| Scope | Endpoints |
| --- | --- |
| `fencers:read` | `GET /fencers` |
| `tournaments:read` | `GET /tournaments` |
| `rankings:read` | `GET /rankings` |
| `results:read` | `GET /results` |
| `medals:read` | `GET /medal-tables` |
| `*` | All syndication endpoints |

Missing, invalid, disabled, or out-of-scope keys are rejected before data is
returned.

## Pagination

Every list endpoint accepts:

| Parameter | Default | Limit |
| --- | ---: | ---: |
| `limit` | `50` | `1..500` |
| `offset` | `0` | `>= 0` |

Responses use this shape:

```json
{
  "data": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "count": 0
  }
}
```

`count` is the number of rows in the returned page, not a full-table total.

## Endpoints

### Fencers

```http
GET /syndication/v1/fencers
```

Filters: `name`, `country`, `weapon`, `category`, `limit`, `offset`.

Public fields: `id`, `name`, `country`, `weapon`, `category`, `world_rank`,
`fie_points`, `image_url`.

Sample:

```bash
curl 'https://api.example.com/syndication/v1/fencers?country=KOR&weapon=Epee&limit=25' \
  -H 'X-API-Key: <partner-secret>'
```

### Tournaments

```http
GET /syndication/v1/tournaments
```

Filters: `season`, `type`, `country`, `weapon`, `category`, `limit`, `offset`.

Public fields: `id`, `name`, `season`, `start_date`, `end_date`, `country`,
`weapon`, `category`, `type`.

### Rankings

```http
GET /syndication/v1/rankings
```

Filters: `season`, `weapon`, `gender`, `category`, `country`, `limit`, `offset`.

Public fields: `id`, `season`, `weapon`, `gender`, `category`, `rank`,
`fencer_id`, `name`, `country`, `points`.

### Results

```http
GET /syndication/v1/results
```

Filters: `tournament_id`, `fencer_id`, `country`, `nationality`, `name`,
`limit`, `offset`.

Public fields: `id`, `tournament_id`, `fencer_id`, `rank`, `name`,
`nationality`, `country`.

Sample:

```bash
curl 'https://api.example.com/syndication/v1/results?tournament_id=<uuid>&limit=100' \
  -H 'X-API-Key: <partner-secret>'
```

### Medal Tables

```http
GET /syndication/v1/medal-tables
```

Filters: `scope`, `country`, `fencer_id`, `tier`, `limit`, `offset`.

Public fields: `id`, `scope`, `country`, `fencer_id`, `tier`, `gold`, `silver`,
`bronze`, `total`, `updated_at`.

## Rate Limits

Each key has its own `rate_limit_per_minute`. When a key exceeds its limit, the
API returns:

```http
429 Too Many Requests
Retry-After: <seconds>
```

```json
{"detail": "Rate limit exceeded"}
```

## Request Logging

The API writes sanitized request logs to `fs_syndication_request_logs`.

Stored fields include partner key ID, partner name, scope, method, path, status,
redacted query parameters, hashed remote address, user agent, and timestamp.

Logs do not store API-key headers, bearer tokens, raw IP addresses, or plaintext
partner secrets.

## Mounting

`api_syndication.py` exposes both:

- `router` for mounting under another FastAPI app.
- `app` for running the syndication API independently in local or dedicated
  deployments.

