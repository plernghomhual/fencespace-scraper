# FenceSpace GraphQL API

Read-only GraphQL access lives in `graphql.app:app`. It wraps the same Supabase-backed project data exposed by `api.py`, uses the same `X-API-Key` auth model, and rejects mutations/subscriptions.

## Local Startup

Run directly from the project root:

```bash
FENCESPACE_API_KEY=dev-secret \
SUPABASE_URL=https://your-project.supabase.co \
SUPABASE_SERVICE_KEY=your-service-key \
.venv/bin/python -m uvicorn graphql.app:app --reload --host 0.0.0.0 --port 8001
```

Or with Docker Compose:

```bash
docker compose up graphql-api
```

The endpoint is available at:

- `POST /graphql` for JSON bodies: `{"query": "...", "variables": {...}}`
- `GET /graphql?query=...` for read-only query requests
- `GET /graphql/schema` for the schema SDL

All data queries require `X-API-Key`. Valid keys come from `FENCESPACE_API_KEY`, `FS_API_KEY`, `API_KEY`, or active rows in `fs_api_keys`.

## Safety Model

- Read-only: `mutation` and `subscription` operations return an error.
- Pagination: list resolvers accept `limit` and `offset`; `limit` is bounded to `1..500`.
- Field whitelisting: resolvers select only requested public columns and never use `select("*")` for exposed data.
- No nested relationship expansion: fencer profile subresources are fetched in fixed batches; list rows expose IDs instead of per-row nested lookups to avoid N+1 behavior.
- Private columns such as `metadata` are not part of the GraphQL schema.

## Source Tables And Views

| GraphQL field | Supabase source |
| --- | --- |
| `fencers` / `fencer.profile` | `fs_fencers` |
| `fencer.careerStats` | `fs_fencer_career_stats` |
| `fencer.social` | `fs_fencer_social_media` |
| `fencer.equipment` | `fs_fencer_equipment` |
| `tournaments` | `fs_tournaments` |
| `results` | `fs_results` |
| `rankings` | `fs_rankings_history` |
| `h2h` | `fs_head_to_head` |
| `countries` | `fs_country_depth` |
| `news` | `fs_social_feed` |
| `products` | `fs_equipment_reviews` |

`fs_social_feed` is expected from the social feed module. If that table/view is not present in a deployment, `news` returns a Supabase query error while the rest of the schema remains available.

## Example Queries

Search fencers:

```graphql
{
  fencers(name: "lee", country: "KOR", weapon: "Epee", limit: 25, offset: 0) {
    pagination { limit offset count }
    data { id fieId name country weapon worldRank fiePoints }
  }
}
```

Fetch a fencer profile:

```graphql
{
  fencer(id: "fencer-uuid") {
    profile { id name country weapon }
    careerStats { totalCompetitions goldMedals silverMedals bronzeMedals }
    social { platform url handle }
    equipment { brand equipmentType sourceUrl confidence }
  }
}
```

List tournaments and results:

```graphql
{
  tournaments(season: 2026, type: "GP", country: "KOR") {
    data { id fieId name startDate endDate }
    pagination { count }
  }
  results(tournamentId: "tournament-uuid", limit: 50) {
    data { rank name nationality fencerId points }
  }
}
```

Rankings, H2H, countries, news, and products:

```graphql
{
  rankings(season: 2026, weapon: "Epee", gender: "Men", category: "Senior") {
    data { rank name country points }
  }
  h2h(fencerA: "fencer-a-uuid", fencerB: "fencer-b-uuid") {
    fencerA
    fencerB
    data { weapon aWins bWins boutsTotal lastMeetingDate }
  }
  countries(code: "KOR") {
    data { country weapon category fencersInTop16 totalRanked avgWorldRank }
  }
  news(platform: "instagram") {
    data { platform author url textExcerpt postedAt }
  }
  products(brand: "Allstar", category: "blade") {
    data { productName brand rating reviewCount price currency url }
  }
}
```

Example curl:

```bash
curl -sS http://localhost:8001/graphql \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-secret' \
  --data '{"query":"{ fencers(limit: 1) { data { id name } pagination { count } } }"}'
```
