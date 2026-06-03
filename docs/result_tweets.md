# Result Tweets Bot

`post_result_tweets.py` formats recent tournament result summaries for X/Twitter. It is dry-run first: it reads result data, validates candidate messages, and prints them without posting unless live posting is explicitly enabled.

## Data Source

The bot reads completed tournaments from `fs_tournaments` where `has_results = true`, then reads podium rows from `fs_results`.

Required to read Supabase:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

Optional settings:

- `RESULT_TWEETS_LIMIT`: number of recent tournaments to inspect, default `10`
- `FENCESPACE_BASE_URL`: fallback result link base, default `https://fencespace.app`

## Dry Run

Default command:

```bash
.venv/bin/python post_result_tweets.py
```

Dry run does not create posts and does not mark result keys as delivered. It still records `result_tweets:last_run` in `fs_scraper_state` when Supabase state is available.

## Live Posting

Live posting requires both:

- CLI flag: `--live`
- Environment flag: `RESULT_TWEETS_LIVE=1`

The X provider also requires:

- `X_API_BEARER_TOKEN`: X API v2 user-context bearer token with tweet write permission

Command:

```bash
RESULT_TWEETS_LIVE=1 .venv/bin/python post_result_tweets.py --live
```

The script never prints token values. If Twitter/X API access is unavailable, keep the provider mocked in tests and configure credentials only in the runtime environment.

## Duplicate Suppression

Delivered result keys are persisted in `fs_scraper_state`:

- source: `result_tweets`
- key: `posted_result_keys`
- key: `delivery_log`

The delivery key is `fs_tournaments.source_id` when present, otherwise `fs_tournaments.id`. A live post is marked delivered only after the provider returns successfully. Dry runs do not mark delivery.

## Message Validation

Each message is validated before live posting:

- X length must be 280 characters or fewer, with HTTP links counted as 23 characters.
- Links must use `http://` or `https://`.
- At least one valid hashtag is required.
- Hashtags must use letters, numbers, and underscores only.
- Unicode names are preserved.

Invalid messages are skipped and reported in the run summary.
