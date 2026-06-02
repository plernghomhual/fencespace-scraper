# Agent Prompts v2 -- 160 Agents (Final Dispatch Pack)

This file is ready to dispatch. Every agent prompt embeds the shared production preamble and follows the v1 prompt shape: files, constraints, task steps, tests, success criteria, blocked handling, and output format.

## Dispatch Rules

When sending an individual prompt to an agent, include the complete agent-specific section from this file.

Rules for all agents:
- Probe current public URLs before coding any scraper or enrichment module that uses an external source.
- Write or update tests for parser, compute, schema, API, or frontend logic before implementation whenever practical.
- Do not edit `.github/workflows/` except Agent 160.
- Prefer stubs that exit 0 with clear probe evidence over brittle fake scrapers when a source is blocked, login-only, paid/API-key-only, geoblocked, JS-only with no public API, or has no durable public data.
- Keep changes scoped to the listed files unless a migration, requirement, docs file, or test file is explicitly required by the implementation.
- For database writes, use existing Supabase/run-logger/state patterns and avoid destructive migrations.
- For fencer/result matching, prefer FIE ID, then canonical identity, then conservative name+country matching; log unmatched rows instead of silently creating null-fencer orphans.
- For seasons, use existing `season_utils.py` if present and never mix integer FIE seasons with `YYYY-YYYY` strings without normalization.
- For social/media/minor/privacy-sensitive agents, use public/API-backed sources only and do not bypass logins or infer private facts.

Every agent must finish with the output format defined in its own prompt.

## Dependency Coordination

Run a baseline first: `.venv/bin/python -m pytest tests/ -v` from the project root.

Suggested batches:

| Batch | Agents | Dependency notes |
|-------|--------|------------------|
| 0 | Baseline only | Record current test state before dispatch. |
| 1 | 1-23, 30 | Core schema/data/view work. Respect per-agent dependencies inside each prompt. |
| 2 | 24-29 | API data wiring after the relevant schemas/compute outputs exist. |
| 3 | 31-60 | Tier-3 federation scrapers; parallel-safe. Use existing `season_utils.py` if present. |
| 4 | 61-75 | More tournament/result sources; parallel-safe except shared helper discoveries. |
| 5 | 76-90 | Deeper analytics; best after results/bouts/rankings exist. |
| 6 | 91-105 | Enrichment; best after fencer identity/bio/public-source fields exist. |
| 7 | 106-130 | Product/frontend/API surfaces; best after public views and data APIs exist. |
| 8 | 131-145 | Marketplace/social modules; respect product/social schema dependencies in prompts. |
| 9 | 146-159 | Advanced/experimental modules; run after their listed data dependencies. |
| 10 | 160 | CI merge; must run last and is the only workflow-editing agent. |

If running many agents in parallel, avoid assigning two agents that declare the same file. This file has been deduped for declared targets, but integration agents may still need to wire outputs together later.

---
## FRONTEND DATA GAPS (30 agents)

---

## Agent 1 — Add bio/birth_date/birth_place columns to fs_fencers

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_fencer_bio_columns.sql`, `tests/test_bio_columns.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing `fs_fencers` migrations and current fencer upsert code before writing SQL.
2. Create an idempotent migration adding `bio text`, `birth_date date`, `birth_place text`, and `bio_source text` to `fs_fencers`.
3. Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` and avoid destructive rewrites, default values, or backfills in this schema-only agent.
4. Add comments or metadata only if the project migration style already uses them.
5. Write tests that parse the migration and assert column names, SQL types, idempotency, and no unrelated table changes.

**Tests:**
- Migration SQL structure test for all four columns and `IF NOT EXISTS`.
- Negative test asserting no `DROP`, `TRUNCATE`, or broad data rewrite appears.
- Run `pytest tests/test_bio_columns.py -v`.

**Success criteria:** Migration is idempotent, scoped to `fs_fencers`, and tests verify the exact bio/birth columns.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_bio_columns.sql, tests/test_bio_columns.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 2 — Expand Wikipedia bio scraper to fill bio/birth_date/birth_place

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_wikipedia_bios.py`, `tests/test_wikipedia_bios.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read the existing bio scraper, `scraper.py` fencer upsert patterns, and any Wikidata/Wikipedia helpers already present.
2. Use Wikipedia REST/PageSummary and Wikidata fields to populate `bio`, `birth_date`, `birth_place`, and `bio_source` only for confidently matched fencers.
3. Match by `wikidata_id` first, then existing Wikipedia title/url fields; do not guess biographies by loose name alone.
4. Normalize dates to ISO `YYYY-MM-DD` where possible and preserve unknown/partial data as null rather than fabricated values.
5. Rate limit Wikipedia/Wikidata calls, log skipped/unmatched fencers, and use `ScraperRunLogger` plus scraper state.
6. Write via Supabase update/upsert without overwriting richer existing bio fields unless the new source is clearly fresher.

**Tests:**
- Parser tests for Wikipedia summary, Wikidata birth date/place claims, and missing-field responses.
- Matching tests for wikidata-id-first behavior and ambiguous-name skip behavior.
- No-network dry-run test using mocked HTTP and mocked Supabase.
- Run `pytest tests/test_wikipedia_bios.py -v`.

**Success criteria:** Bio/birth fields are filled from reliable public sources, ambiguous matches are skipped, and tests cover parsing plus update behavior.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: scrape_wikipedia_bios.py, tests/test_wikipedia_bios.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 3 — Create fs_fencer_stats table (bout stats)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_fencer_stats.sql`, `tests/test_fencer_stats_schema.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing `fs_bouts`, `fs_fencers`, identity, and analytics migration patterns.
2. Create `fs_fencer_stats` with one row per canonical fencer identity/weapon/category where possible, not per duplicate weapon/category fencer row unless existing schema requires it.
3. Include bouts, wins, losses, touches_scored, touches_received, win_pct, current_streak, longest_win_streak, last_bout_at, and updated_at.
4. Add primary/unique keys and indexes that support fencer detail pages and analytics refreshes.
5. Use foreign keys only where existing migrations safely support them; otherwise document the choice in SQL comments.
6. Write SQL tests for table shape, keys/indexes, and non-destructive migration behavior.

**Tests:**
- Migration parser tests for required columns, numeric types, timestamps, primary/unique key, and indexes.
- Safety test rejecting destructive SQL.
- Run `pytest tests/test_fencer_stats_schema.py -v`.

**Success criteria:** `fs_fencer_stats` schema is ready for bout aggregation with stable keys and tests.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_stats.sql, tests/test_fencer_stats_schema.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 4 — Compute fencer bout stats from fs_bouts

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_fencer_stats.py`, `tests/test_compute_fencer_stats.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_bouts`, fencer identity resolution utilities, and existing compute scripts before implementation.
2. Aggregate completed bouts where both fencers and scores are known; skip null/incomplete scores with clear counters.
3. Compute per-fencer/weapon/category bouts, wins, losses, touches, win_pct, current streak, longest win streak, and last bout date.
4. Collapse duplicate fencer rows through `fs_fencer_identities` when available so the same person is not split across weapon/category duplicates incorrectly.
5. Upsert into `fs_fencer_stats` idempotently and use `ScraperRunLogger` for written/skipped/failed counts.
6. Keep the script safe for empty databases and no-credential local test runs.

**Tests:**
- Mock bout aggregation tests for wins/losses, touches, streaks, incomplete-bout skips, and empty input.
- Identity-group test proving duplicate fencer rows aggregate to the canonical person when identity data exists.
- Mock Supabase upsert test for idempotent conflict keys.
- Run `pytest tests/test_compute_fencer_stats.py -v`.

**Success criteria:** Stats are computed deterministically from bouts, duplicate identities are handled, and tests verify core math.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_fencer_stats.py, tests/test_compute_fencer_stats.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 5 — Add national_rank column to fs_fencers and backfill

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_national_rank.sql`, `scripts/backfill_national_rank.py`, `tests/test_backfill_national_rank.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_fencers`, `fs_federation_rankings`, `fed_rankings_common.py`, and identity matching lessons.
2. Create an idempotent migration adding `national_rank`, `national_rank_points`, `national_rank_source`, and `national_rank_season` to `fs_fencers`.
3. Implement a backfill that selects the latest normalized season per source/country/weapon/gender/category and updates matching fencers by identity/FIE ID/name+country.
4. Use `season_utils` for season parsing and never compare mixed int/string seasons directly.
5. Do not overwrite a better/current rank with stale or lower-confidence data; record skipped/unmatched counts.
6. Write mock tests for season selection, fencer matching, missing rankings, and upsert/update payloads.

**Tests:**
- Migration SQL tests for four idempotent columns and safe indexes if needed.
- Backfill unit tests with multiple seasons, duplicate identities, and unmatched ranking rows.
- Run `pytest tests/test_backfill_national_rank.py -v`.

**Success criteria:** National rank columns exist and backfill picks current trustworthy federation ranking rows without unsafe overwrites.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_national_rank.sql, scripts/backfill_national_rank.py, tests/test_backfill_national_rank.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 6 — Add organizer/entry_deadline/format/quota columns to fs_tournaments

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_tournament_detail_columns.sql`, `tests/test_tournament_detail_columns.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read current `fs_tournaments` schema and tournament detail usage in result scrapers.
2. Create an idempotent migration adding organizer, entry_deadline, format, quota, venue_details, registration_url, live_results_url, and detail_source columns.
3. Choose SQL types that match existing project conventions, using `date`/`timestamptz` only where the source data can support it reliably.
4. Add lightweight indexes only for fields likely to be queried, such as `entry_deadline` or `organizer`, if consistent with project style.
5. Do not backfill or alter existing tournament rows in this schema-only prompt.
6. Write migration tests for exact columns, types, idempotency, and absence of destructive SQL.

**Tests:**
- Migration parser tests for eight columns and safe SQL.
- Run `pytest tests/test_tournament_detail_columns.py -v`.

**Success criteria:** Tournament detail columns are added safely and verified by schema tests.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_tournament_detail_columns.sql, tests/test_tournament_detail_columns.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 7 — Scrape FIE competition detail pages for organizer/format/quota/deadline

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_competition_details.py`, `tests/test_scrape_competition_details.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe current FIE competition detail URLs and API/XHR responses before coding; do not assume the URL shape is still valid.
2. Read `scrape_results.py`, `discover_competition_urls.py`, and tournament upsert patterns.
3. Parse organizer, format, quota, entry deadline, venue details, registration URL, and live results URL from public FIE detail pages or APIs.
4. Normalize dates and quotas defensively; preserve raw source snippets/metadata when fields are uncertain.
5. Update only existing tournament rows identified by FIE id/source; do not create duplicate tournaments from detail pages alone.
6. Use rate limiting, run logging, scraper state, and graceful 404/network handling.

**Tests:**
- Parser tests using realistic FIE HTML/API fixtures for populated, missing, and malformed detail fields.
- Normalization tests for dates, quotas, and relative URLs.
- Mock Supabase update tests proving no duplicate tournament insert path.
- Run `pytest tests/test_scrape_competition_details.py -v`.

**Success criteria:** FIE detail fields are populated from current public pages/APIs with robust missing-data behavior.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: scrape_competition_details.py, tests/test_scrape_competition_details.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 8 — Create fs_tournament_brackets table

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_tournament_brackets.sql`, `tests/test_tournament_brackets_schema.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_bouts`, `fs_results`, and tournament schema before designing bracket storage.
2. Create `fs_tournament_brackets` with tournament_id, event_id or event key, weapon, gender, category, round_name, bout_order, fencer_a_id, fencer_b_id, scores, winner_id, seed fields, source, metadata, and updated_at.
3. Include a stable unique key that prevents duplicate bracket rows on recompute.
4. Index tournament/event/round fields needed by tournament detail pages.
5. Avoid assuming every competition has direct-elimination data; schema must support missing seeds and byes.
6. Write migration tests for table shape, indexes, unique constraints, nullable fields, and safe SQL.

**Tests:**
- Migration parser tests for required columns and conflict key/indexes.
- Safety test for no destructive SQL.
- Run `pytest tests/test_tournament_brackets_schema.py -v`.

**Success criteria:** Bracket schema supports elimination trees, byes, missing seeds, and idempotent recomputation.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_tournament_brackets.sql, tests/test_tournament_brackets_schema.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 9 — Build bracket data pipeline from fs_bouts into fs_tournament_brackets

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_brackets.py`, `tests/test_compute_brackets.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_bouts`, `fs_results`, existing bracket schema, and result source metadata.
2. Build bracket rows from elimination bouts, preserving round order, piste/order where available, fencer IDs, scores, winner, byes, and source metadata.
3. Do not fabricate bracket trees when source data lacks round/ordering evidence; log skipped tournaments instead.
4. Handle partial data, missing scores, duplicate bouts, and tournaments with multiple weapons/genders/categories.
5. Upsert idempotently into `fs_tournament_brackets` and track written/skipped/failed counts.
6. Add a CLI/main entry with safe no-credential behavior for tests.

**Tests:**
- Fixture tests for a complete 8-person bracket, byes, duplicate bouts, missing winner/score, and multiple events.
- Mock Supabase tests for upsert conflict keys and skipped-tournament logging.
- Run `pytest tests/test_compute_brackets.py -v`.

**Success criteria:** Bracket rows are derived only from adequate bout evidence and recompute safely.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_brackets.py, tests/test_compute_brackets.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 10 — Create fs_fencer_season_stats table

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_fencer_season_stats.sql`, `tests/test_fencer_season_stats_schema.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read season utilities, `fs_results`, `fs_bouts`, and fencer identity schema.
2. Create `fs_fencer_season_stats` keyed by fencer identity/fencer_id, season, weapon, gender/category as needed.
3. Include starts, best_finish, medals, top8/top16/top32 counts, bouts, wins, losses, touches, win_pct, rank_delta, and updated_at.
4. Use a normalized season representation compatible with `season_utils` and existing FIE season lessons.
5. Add indexes for fencer detail pages and season leaderboards.
6. Write SQL tests for schema shape, season column type, unique key, and safe migration behavior.

**Tests:**
- Migration parser tests for required columns, keys, indexes, and idempotency.
- Run `pytest tests/test_fencer_season_stats_schema.py -v`.

**Success criteria:** Season stats table is ready for normalized per-season aggregation.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_season_stats.sql, tests/test_fencer_season_stats_schema.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 11 — Compute per-season fencer stats from results + bouts

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_fencer_season_stats.py`, `tests/test_compute_fencer_season_stats.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `season_utils.py`, fencer identity logic, `fs_results`, `fs_bouts`, and existing analytics scripts.
2. Aggregate results and bouts by canonical fencer, normalized season, weapon, gender/category, and source confidence.
3. Compute starts, best finish, medals, top placement counts, bout record, touches, win_pct, and rank/placement deltas where data exists.
4. Skip or null fields that cannot be proven from available data; do not mix int seasons with `YYYY-YYYY` strings.
5. Upsert into `fs_fencer_season_stats` with deterministic conflict keys and run logging.
6. Handle empty data, missing fencer IDs, orphan results, and duplicate identity rows gracefully.

**Tests:**
- Unit tests for season normalization, medals/top counts, bout aggregation, orphan skips, and duplicate identity handling.
- Mock Supabase upsert tests for conflict keys and empty input.
- Run `pytest tests/test_compute_fencer_season_stats.py -v`.

**Success criteria:** Per-season fencer stats are computed consistently without season-format or identity duplication bugs.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_fencer_season_stats.py, tests/test_compute_fencer_season_stats.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 12 — Create fs_career_milestones table

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_career_milestones.sql`, `tests/test_career_milestones_schema.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read fencer, results, stats, and identity schemas before designing milestone storage.
2. Create `fs_career_milestones` with fencer identity/fencer_id, milestone_type, milestone_date, tournament_id, weapon, season, title, description, rank/medal fields, source, metadata, and created_at.
3. Use a unique key preventing duplicate milestones for the same person/type/tournament/date.
4. Support milestones with no tournament_id when based on rankings or biography data.
5. Add indexes for fencer timeline and milestone-type filtering.
6. Write SQL tests for table shape, keys, indexes, nullable fields, and safe migration behavior.

**Tests:**
- Migration parser tests for required columns and unique/index constraints.
- Safety test rejecting destructive SQL.
- Run `pytest tests/test_career_milestones_schema.py -v`.

**Success criteria:** Career milestones table supports timeline rendering and idempotent detection.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_career_milestones.sql, tests/test_career_milestones_schema.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 13 — Career milestone detection engine

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_career_milestones.py`, `tests/test_compute_career_milestones.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_results`, `fs_rankings_history`, `fs_fencer_stats`, identity logic, and `fs_career_milestones` schema.
2. Detect first international result, first medal, first gold, first top-8/top-16, personal-best ranking, country change, weapon/category transition, and retirement/reactivation signals where evidence exists.
3. Use canonical fencer identities so duplicate `fs_fencers` rows do not create duplicate milestones.
4. Generate deterministic milestone titles/descriptions and metadata with source evidence.
5. Upsert idempotently and skip ambiguous or unsupported milestone types rather than guessing.
6. Use run logging and safe empty-data behavior.

**Tests:**
- Fixture tests for first medal/gold/top placement, personal-best ranking, duplicate identity dedupe, and ambiguous data skips.
- Mock Supabase upsert tests for idempotent keys.
- Run `pytest tests/test_compute_career_milestones.py -v`.

**Success criteria:** Milestones are evidence-backed, deduped by identity, and suitable for athlete timeline APIs.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_career_milestones.py, tests/test_compute_career_milestones.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 14 — Create fs_country_medal_geo materialized view

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_country_medal_geo.sql`, `tests/test_country_medal_geo.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read medal/result tables, country-code conventions, and public API/view patterns.
2. Create a materialized view or SQL view `fs_country_medal_geo` aggregating medals by country, weapon, gender/category, competition tier, and season/year where supported.
3. Join to country code/geography data using a stable alpha3/FIE/Olympic mapping instead of raw display names.
4. Include medal counts, total medals, top8/top16 counts if source tables support them, latitude/longitude or centroid fields, and refreshed_at.
5. Handle unknown/stateless country codes with null geo fields instead of dropping medals.
6. Write SQL tests for aggregation, grouping columns, indexes/refresh support, and safe migration behavior.

**Tests:**
- Migration/view SQL tests for expected columns, joins, grouping, and no destructive SQL.
- Fixture-level SQL text tests for unknown country handling and medal count expressions.
- Run `pytest tests/test_country_medal_geo.py -v`.

**Success criteria:** Country medal geo view is queryable for a heatmap and preserves medals even when geography is incomplete.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_country_medal_geo.sql, tests/test_country_medal_geo.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 15 — Geocode all countries for medal heatmap

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scripts/geocode_countries.py`, `tests/test_geocode_countries.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing country code utilities, venue geocoding, scraper state, and rate-limiter patterns.
2. Create a deterministic country geocoding/backfill script for all country codes used by fencers, tournaments, and medal views.
3. Prefer static ISO/NOC centroid data when available; use Nominatim only for missing countries with rate limiting and cached failures.
4. Normalize alpha2, alpha3, Olympic, FIE, display name, continent/region, latitude, longitude, and source metadata.
5. Never hammer geocoding APIs; persist state and skipped/missing values.
6. Write tests with mocked geocoder responses and static fixtures.

**Tests:**
- Unit tests for code normalization, static lookup priority, Nominatim fallback, failure cache, and no-network dry run.
- Run `pytest tests/test_geocode_countries.py -v`.

**Success criteria:** Country geo data can be populated safely with deterministic lookups and rate-limited fallbacks.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: scripts/geocode_countries.py, tests/test_geocode_countries.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 16 — Create fs_ranking_history_trajectory table

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_ranking_trajectory.sql`, `tests/test_ranking_trajectory_schema.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read ranking history/federation ranking schemas and season utilities.
2. Create `fs_ranking_history_trajectory` for fencer identity/fencer_id, source, season, weapon, gender/category, rank, points, rank_delta, points_delta, trend_window, and updated_at.
3. Use normalized seasons and stable ordering that supports sparklines and projection engines.
4. Add a unique key preventing duplicate source/season rows per fencer and indexes for fencer detail queries.
5. Allow null points when rankings publish rank-only data.
6. Write schema tests for columns, keys, indexes, and safe migration behavior.

**Tests:**
- Migration parser tests for required columns, nullable points, season field, unique key, and indexes.
- Run `pytest tests/test_ranking_trajectory_schema.py -v`.

**Success criteria:** Ranking trajectory table can store normalized multi-source rank history for frontend sparklines.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_ranking_trajectory.sql, tests/test_ranking_trajectory_schema.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 17 — Ranking sparkline data endpoint materialized view

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_ranking_sparklines.sql`, `tests/test_ranking_sparklines.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read ranking trajectory schema, public API/view conventions, and frontend data needs.
2. Create a public-safe view/materialized view for compact ranking sparklines by fencer, weapon, gender/category, and source.
3. Aggregate ordered season/rank/points arrays or JSON payloads suitable for chart rendering without exposing private scraper metadata.
4. Include latest rank, best rank, worst rank, delta, sample_count, and updated_at.
5. Protect against duplicate ranking rows by using the canonical trajectory table and deterministic ordering.
6. Write SQL tests for JSON/array shape, public-safe selected columns, and no destructive SQL.

**Tests:**
- Migration/view SQL tests for expected columns, aggregation/order expressions, and privacy-safe field selection.
- Run `pytest tests/test_ranking_sparklines.py -v`.

**Success criteria:** Ranking sparkline view exposes compact, public-safe rank history for athlete pages.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_ranking_sparklines.sql, tests/test_ranking_sparklines.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 18 — Unify country code data: single source of truth

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scripts/country_codes.py`, `supabase/migrations/20260602_country_codes.sql`, `tests/test_country_codes.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read all existing country-code mappings in scrapers, rankings, results, and tests.
2. Create `fs_country_codes` with alpha3 primary key, alpha2, name, region, continent, flag_emoji, olympic_code, fie_code, aliases, latitude, longitude, and updated_at.
3. Populate all relevant NOC/IOC/FIE countries and aliases used by fencing sources; include at least all active countries seen in the database plus common historical codes.
4. Implement `scripts/country_codes.py` lookup helpers for alpha2/alpha3/Olympic/FIE/name aliases with deterministic fallback behavior.
5. Avoid one-off country maps scattered through new code; document how other agents should import the helper.
6. Write tests for alias lookup, historical/edge codes, schema SQL, and no duplicate codes.

**Tests:**
- Migration tests for table shape, primary key, aliases, and seed inserts/upserts.
- Python helper tests for alpha2/alpha3/Olympic/FIE/name lookup and unknown-code behavior.
- Run `pytest tests/test_country_codes.py -v`.

**Success criteria:** Country code data becomes a tested single source of truth for scrapers, analytics, and frontend views.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scripts/country_codes.py, supabase/migrations/20260602_country_codes.sql, tests/test_country_codes.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 19 — Add losses/defeats column to fs_results and backfill

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_result_losses.sql`, `scripts/backfill_result_losses.py`, `tests/test_backfill_result_losses.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_results`, `fs_bouts`, bracket data, and result scraper conventions.
2. Add idempotent result fields for losses/defeats or elimination-loss metadata using names consistent with existing schema.
3. Backfill losses from bout outcomes and placement/elimination data where source evidence is reliable.
4. Skip rows without enough bout/round evidence rather than deriving false losses from final rank alone.
5. Handle team events, byes, withdrawals, DNS/DQ, and missing scores explicitly in metadata/counters.
6. Write mock tests for migration structure and backfill edge cases.

**Tests:**
- Migration SQL tests for idempotent columns and safe SQL.
- Backfill tests for normal elimination, byes, DNS/DQ, missing scores, and team-event skips.
- Run `pytest tests/test_backfill_result_losses.py -v`.

**Success criteria:** Result loss fields are added and backfilled only where bout evidence supports them.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_result_losses.sql, scripts/backfill_result_losses.py, tests/test_backfill_result_losses.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 20 — Featured athletes algorithm

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_featured_athletes.py`, `supabase/migrations/20260602_featured_athletes.sql`, `tests/test_featured_athletes.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read fencer stats, rankings, results, bios, and frontend public-view needs.
2. Create a table/view for featured athlete candidates with fencer_id/identity, score, reasons, rank context, recency, country, weapon, and updated_at.
3. Implement a deterministic scoring algorithm balancing recent medals, ranking, activity, data completeness, and country/weapon diversity.
4. Prevent one country/weapon from monopolizing the list unless explicitly requested.
5. Exclude fencers with missing names, inactive/retired flags when reliable, or unsafe/private data.
6. Write tests for scoring, tie-breakers, diversity caps, empty data, and schema.

**Tests:**
- Schema tests for featured athlete table/view.
- Algorithm tests for score weights, tie ordering, diversity, and missing-data skips.
- Run `pytest tests/test_featured_athletes.py -v`.

**Success criteria:** Featured athletes are selected deterministically with explainable reasons and public-safe fields.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_featured_athletes.py, supabase/migrations/20260602_featured_athletes.sql, tests/test_featured_athletes.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 21 — Fencer social follower count tracker

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_social_followers.py`, `supabase/migrations/20260602_social_followers.sql`, `tests/test_scrape_social_followers.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing social/Wikidata enrichment and privacy rules before scraping.
2. Create `fs_social_followers` for fencer identity, platform, handle/url, follower_count, following_count if public, source, collected_at, and metadata.
3. Use official APIs or public Wikidata/federation profile links where available; do not scrape private/login-only pages or bypass platform restrictions.
4. Normalize handles and URLs; dedupe by fencer/platform/handle/date bucket.
5. Treat follower counts as volatile snapshots and never overwrite historical snapshots unless using the same timestamp/key.
6. Use run logging, rate limiting, and clear blocked-source stubs.

**Tests:**
- Parser/API fixture tests for public profile snapshots and missing/hidden counts.
- Migration tests for snapshot table and uniqueness.
- Policy tests ensuring login-only/private pages are skipped.
- Run `pytest tests/test_scrape_social_followers.py -v`.

**Success criteria:** Follower snapshots are collected only from allowed public/API sources and stored historically.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: scrape_social_followers.py, supabase/migrations/20260602_social_followers.sql, tests/test_scrape_social_followers.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 22 — Social media feed real-time aggregator for #fencing

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `aggregate_social_feed.py`, `supabase/migrations/20260602_social_feed.sql`, `tests/test_aggregate_social_feed.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Define the feed as public posts from approved APIs/search providers, not private timeline scraping.
2. Create `fs_social_feed` with platform, post_id, author, url, text_excerpt, hashtags, language, related_fencer_ids, tournament_id, posted_at, source, and metadata.
3. Implement query/provider adapters for `#fencing` and fencing-specific terms with rate limits and provider-key detection.
4. Filter spam, duplicates, non-fencing false positives, and unsafe/private content; store excerpts only if allowed by provider terms.
5. Link posts to fencers/tournaments conservatively using exact handles, known URLs, and event names.
6. Write dry-run behavior for missing API keys.

**Tests:**
- Migration tests for feed table and uniqueness.
- Provider fixture tests for dedupe, hashtag filtering, language handling, and missing-key dry run.
- Linking tests that avoid loose name false positives.
- Run `pytest tests/test_aggregate_social_feed.py -v`.

**Success criteria:** Social feed aggregation is public/API-backed, deduped, and safe when providers are unavailable.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: aggregate_social_feed.py, supabase/migrations/20260602_social_feed.sql, tests/test_aggregate_social_feed.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 23 — AI insights pipeline: fencer comparison / performance summary

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_ai_insights.py`, `supabase/migrations/20260602_ai_insights.sql`, `tests/test_ai_insights.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing analytics outputs and avoid external LLM calls unless the project already has an approved provider path.
2. Create `fs_ai_insights` with entity_type, entity_id, insight_type, summary, evidence_json, confidence, model/provider or rule_version, generated_at, and metadata.
3. Implement deterministic template/rule-based fencer comparison and performance summaries from stats, rankings, H2H, and recent results.
4. Ground every sentence in evidence_json; avoid unsupported predictions, medical claims, or private data.
5. Make provider-based generation optional/dry-run and keep tests independent of network/API keys.
6. Write cache/upsert behavior so insights can refresh without duplicate rows.

**Tests:**
- Schema tests for insight storage and evidence fields.
- Unit tests for template summaries, comparison logic, unsupported-data skips, and no-provider behavior.
- Run `pytest tests/test_ai_insights.py -v`.

**Success criteria:** Insights are evidence-backed, deterministic by default, and safe to expose in product surfaces.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_ai_insights.py, supabase/migrations/20260602_ai_insights.sql, tests/test_ai_insights.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 24 — Wire H2H data into athlete page API

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/fencer_h2h.py`, `tests/test_api_fencers_h2h.py`

**Parallel-safety:** Do not edit shared `api/v1/fencers.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing API style, auth/public-view patterns, and `fs_head_to_head` or H2H analytics schema.
2. Implement a fencer H2H data helper/route returning opponent summaries, records, last meeting, weapon filters, and pagination.
3. Resolve fencer identity groups so duplicate `fs_fencers` rows do not split H2H results.
4. Validate fencer IDs, weapon/category query params, pagination limits, and missing fencer behavior.
5. Return stable JSON with empty arrays for no data and never expose private scraper metadata.
6. Write tests for filtering, identity grouping, empty data, and invalid params.

**Tests:**
- API/helper tests with mocked data for normal H2H, duplicate identities, filters, pagination, and 404/empty states.
- Run `pytest tests/test_api_fencers_h2h.py -v`.

**Success criteria:** Athlete page can fetch public H2H summaries through a scoped module without shared-router conflicts.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/fencer_h2h.py, tests/test_api_fencers_h2h.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 25 — Wire ranking history into athlete page trajectory chart

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/fencer_ranking_trajectory.py`, `tests/test_api_fencers_ranking_trajectory.py`

**Parallel-safety:** Do not edit shared `api/v1/fencers.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read ranking trajectory/sparkline schemas and existing API response conventions.
2. Implement a ranking trajectory helper/route returning ordered rank/points history by source, season, weapon, and category.
3. Normalize seasons through `season_utils` and sort chronologically even when sources use mixed season formats.
4. Validate fencer ID, source, weapon, category, and limit params; default to compact public data.
5. Return empty history rather than errors for fencers without rankings.
6. Write tests for ordering, season normalization, filters, missing data, and invalid params.

**Tests:**
- API/helper tests with mocked trajectory rows for multi-season ordering and filters.
- Run `pytest tests/test_api_fencers_ranking_trajectory.py -v`.

**Success criteria:** Athlete pages can fetch consistent ranking history data without season-format bugs.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/fencer_ranking_trajectory.py, tests/test_api_fencers_ranking_trajectory.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 26 — Wire win/loss stats into athlete page

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/fencer_stats.py`, `tests/test_api_fencers_stats.py`

**Parallel-safety:** Do not edit shared `api/v1/fencers.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_fencer_stats`, season stats, and existing API patterns.
2. Implement a public stats helper/route returning bout record, win_pct, touches, medals/top placements if available, and per-weapon breakdowns.
3. Resolve identity groups and combine duplicate rows only where fields are mathematically safe to aggregate.
4. Validate IDs and query params, cap expensive requests, and provide predictable null/zero behavior.
5. Avoid exposing internal state, raw scraper metadata, or service-role-only fields.
6. Write tests for aggregation, identity grouping, empty stats, and validation.

**Tests:**
- API/helper tests with mocked fencer stats and duplicate identity rows.
- Run `pytest tests/test_api_fencers_stats.py -v`.

**Success criteria:** Athlete page gets clean public win/loss/stat blocks from a scoped module.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/fencer_stats.py, tests/test_api_fencers_stats.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 27 — Wire career milestones into athlete page timeline

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/fencer_milestones.py`, `tests/test_api_fencers_milestones.py`

**Parallel-safety:** Do not edit shared `api/v1/fencers.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_career_milestones`, fencer identity handling, and API response conventions.
2. Implement a milestone timeline helper/route returning ordered milestones with type, date, title, description, tournament, weapon, and evidence/source fields safe for public use.
3. Resolve canonical fencer identity and dedupe same milestone across duplicate fencer rows.
4. Validate fencer ID, milestone type filter, and pagination/limit params.
5. Return empty arrays for no milestones and keep date sorting deterministic when dates tie.
6. Write tests for ordering, filtering, dedupe, empty state, and invalid params.

**Tests:**
- API/helper tests using mocked milestone rows, duplicates, type filters, and missing fencers.
- Run `pytest tests/test_api_fencers_milestones.py -v`.

**Success criteria:** Athlete timeline data is ordered, deduped, public-safe, and scoped away from shared routers.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/fencer_milestones.py, tests/test_api_fencers_milestones.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 28 — Wire bracket data into tournament page interactive bracket

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/tournament_brackets.py`, `tests/test_api_tournaments_brackets.py`

**Parallel-safety:** Do not edit shared `api/v1/tournaments.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read bracket schema, tournament API conventions, and frontend bracket requirements.
2. Implement a bracket helper/route returning tournament event brackets grouped by weapon/gender/category and round.
3. Preserve bout order, byes, scores, winner, seed fields, and enough IDs for fencer links.
4. Validate tournament ID, event filters, and response size; return empty brackets for missing data.
5. Do not fabricate bracket trees when stored bracket rows are incomplete.
6. Write tests for complete bracket, byes, missing scores, filters, and invalid tournament IDs.

**Tests:**
- API/helper tests with mocked bracket rows for multiple events and edge cases.
- Run `pytest tests/test_api_tournaments_brackets.py -v`.

**Success criteria:** Tournament page can fetch interactive bracket data without editing the shared tournament router.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/tournament_brackets.py, tests/test_api_tournaments_brackets.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 29 — Wire organizer/format/deadline into tournament info table

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `api/v1/tournament_details.py`, `tests/test_api_tournaments_details.py`

**Parallel-safety:** Do not edit shared `api/v1/tournaments.py` in this agent. Expose an importable route/helper from this module; central router wiring is left for the merge/integration agent unless automatic route discovery exists.

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read tournament detail columns, existing tournament API patterns, and frontend info-table needs.
2. Implement a detail helper/route returning organizer, format, entry deadline, quota, venue details, registration/live URLs, and source freshness.
3. Validate tournament IDs and keep date/url fields normalized and public-safe.
4. Return nulls for unknown detail fields instead of fabricated defaults.
5. Avoid leaking internal scraper metadata beyond safe source/freshness fields.
6. Write tests for complete details, partial/missing details, URL/date normalization, and invalid IDs.

**Tests:**
- API/helper tests with mocked tournament detail rows and partial data.
- Run `pytest tests/test_api_tournaments_details.py -v`.

**Success criteria:** Tournament info tables can use a scoped public detail endpoint/helper.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: api/v1/tournament_details.py, tests/test_api_tournaments_details.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 30 — Create v_fencer_public view exposing all needed athlete fields

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `supabase/migrations/20260602_v_fencer_public.sql`, `tests/test_v_fencer_public.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_fencers`, identity, bio, stats, ranking, and RLS/public-view conventions.
2. Create or replace `v_fencer_public` using `security_invoker` where supported and only public-safe columns.
3. Expose fencer identity/display fields, country, weapon/category summary, bio/birth fields, rank/stat summaries, and public media URLs if available.
4. Exclude service-only metadata, raw API credentials, scraper state, private social handles, and ambiguous identity internals.
5. Use canonical identity grouping carefully so duplicate fencer rows do not appear as duplicate public athletes.
6. Write SQL tests for selected columns, security-invoker/public safety, joins, and no destructive SQL.

**Tests:**
- Migration/view SQL tests for expected public columns and excluded private/internal fields.
- Run `pytest tests/test_v_fencer_public.py -v`.

**Success criteria:** `v_fencer_public` exposes all athlete-page fields without leaking private/internal data.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: supabase/migrations/20260602_v_fencer_public.sql, tests/test_v_fencer_public.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## TIER-3 FEDERATION SCRAPERS (30 agents)

---

## Agent 31 — Mexico Federation Scraper (MEX)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_mex.py`, `tests/test_fed_mex.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_mex.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `mex`, SOURCE: `mex_fencing`, COUNTRY: `Mexico`
- Probe URL: `fme.com.mx`
- Language: Spanish. Column headers: Posición / Puesto, Nombre, Club, Puntos
- Handle: n, accented vowels, Spanish decimal commas, club abbreviations.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_mex.py -v`.

**Success criteria:** Mexico rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_mex.py, tests/test_fed_mex.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_mex.py -v
```

---

## Agent 32 — Colombia Federation Scraper (COL)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_col.py`, `tests/test_fed_col.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_col.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `col`, SOURCE: `col_fencing`, COUNTRY: `Colombia`
- Probe URL: `esgrimacolombia.co`
- Language: Spanish. Column headers: Posición / Puesto, Deportista / Nombre, Club, Puntaje / Puntos


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_col.py -v`.

**Success criteria:** Colombia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_col.py, tests/test_fed_col.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_col.py -v
```

---

## Agent 33 — Venezuela Federation Scraper (VEN)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_ven.py`, `tests/test_fed_ven.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_ven.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `ven`, SOURCE: `ven_fencing`, COUNTRY: `Venezuela`
- Probe URL: `fevenesgrima.com.ve`
- Language: Spanish. Column headers: Posición / Puesto, Esgrimista / Nombre, Estado / Club, Puntos
- Economic/political instability may affect site availability.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_ven.py -v`.

**Success criteria:** Venezuela rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_ven.py, tests/test_fed_ven.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_ven.py -v
```

---

## Agent 34 — Chile Federation Scraper (CHI)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_chi.py`, `tests/test_fed_chi.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_chi.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `chi`, SOURCE: `chi_fencing`, COUNTRY: `Chile`
- Probe URL: `feche.cl`
- Language: Spanish. Column headers: Ranking / Puesto, Nombre, Club, Puntos


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_chi.py -v`.

**Success criteria:** Chile rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_chi.py, tests/test_fed_chi.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_chi.py -v
```

---

## Agent 35 — Turkey Federation Scraper (TUR)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_tur.py`, `tests/test_fed_tur.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_tur.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `tur`, SOURCE: `tur_fencing`, COUNTRY: `Turkey`
- Probe URL: `trfencing.gov.tr`
- Language: Turkish. Column headers: Sıra, İsim / Ad Soyad, Kulüp, Puan
- Turkish chars: I, i, g, u, s, o, c with diacritics.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_tur.py -v`.

**Success criteria:** Turkey rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_tur.py, tests/test_fed_tur.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_tur.py -v
```

---

## Agent 36 — Iran Federation Scraper (IRI)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_iri.py`, `tests/test_fed_iri.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_iri.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `iri`, SOURCE: `iri_fencing`, COUNTRY: `Iran`
- Probe URL: `iranfencing.ir`
- Language: Persian (Farsi). Column headers: رتبه, نام, باشگاه, امتیاز
- RTL script. Arabic/Persian numerals. May require Iranian IP.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_iri.py -v`.

**Success criteria:** Iran rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_iri.py, tests/test_fed_iri.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_iri.py -v
```

---

## Agent 37 — Kazakhstan Federation Scraper (KAZ)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_kaz.py`, `tests/test_fed_kaz.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_kaz.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `kaz`, SOURCE: `kaz_fencing`, COUNTRY: `Kazakhstan`
- Probe URL: `fencing.kz`
- Language: Kazakh (Cyrillic) + Russian. Column headers: Орын / Место, Аты-жөні / ФИО, Клуб, Ұпай / Очки
- May be bilingual (Kazakh + Russian headers).


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_kaz.py -v`.

**Success criteria:** Kazakhstan rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_kaz.py, tests/test_fed_kaz.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_kaz.py -v
```

---

## Agent 38 — Thailand Federation Scraper (THA)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_tha.py`, `tests/test_fed_tha.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_tha.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `tha`, SOURCE: `tha_fencing`, COUNTRY: `Thailand`
- Probe URL: `thaifencing.org`
- Language: Thai. Column headers: อันดับ, ชื่อ, สโมสร, คะแนน
- Thai script range U+0E00-U+0E7F. No spaces between words.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_tha.py -v`.

**Success criteria:** Thailand rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_tha.py, tests/test_fed_tha.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_tha.py -v
```

---

## Agent 39 — Chinese Taipei Federation Scraper (TPE)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_tpe.py`, `tests/test_fed_tpe.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_tpe.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `tpe`, SOURCE: `tpe_fencing`, COUNTRY: `Chinese Taipei`
- Probe URL: `fencing.org.tw`
- Language: Traditional Chinese. Column headers: 名次 / 排名, 姓名, 單位 / 俱樂部, 積分


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_tpe.py -v`.

**Success criteria:** Chinese Taipei rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_tpe.py, tests/test_fed_tpe.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_tpe.py -v
```

---

## Agent 40 — Morocco Federation Scraper (MAR)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_mar.py`, `tests/test_fed_mar.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_mar.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `mar`, SOURCE: `mar_fencing`, COUNTRY: `Morocco`
- Probe URL: `frmescrime.ma`
- Language: French + Arabic. Column headers: Rang / Classement / المركز, Nom / الاسم, Club / النادي, Points / النقاط


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_mar.py -v`.

**Success criteria:** Morocco rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_mar.py, tests/test_fed_mar.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_mar.py -v
```

---

## Agent 41 — Tunisia Federation Scraper (TUN)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_tun.py`, `tests/test_fed_tun.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_tun.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `tun`, SOURCE: `tun_fencing`, COUNTRY: `Tunisia`
- Probe URL: `fte-tunisie.com`
- Language: French + Arabic. Column headers: Rang / Classement / المركز, Nom / الاسم, Club / النادي, Points / النقاط


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_tun.py -v`.

**Success criteria:** Tunisia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_tun.py, tests/test_fed_tun.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_tun.py -v
```

---

## Agent 42 — South Africa Federation Scraper (RSA)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_rsa.py`, `tests/test_fed_rsa.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_rsa.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `rsa`, SOURCE: `rsa_fencing`, COUNTRY: `South Africa`
- Probe URL: `safencing.co.za`
- Language: English. Column headers: Rank, Name, Club, Points


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_rsa.py -v`.

**Success criteria:** South Africa rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_rsa.py, tests/test_fed_rsa.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_rsa.py -v
```

---

## Agent 43 — Ireland Federation Scraper (IRL)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_irl.py`, `tests/test_fed_irl.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_irl.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `irl`, SOURCE: `irl_fencing`, COUNTRY: `Ireland`
- Probe URL: `irishfencing.net`
- Language: English. Column headers: Rank, Name, Club, Points


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_irl.py -v`.

**Success criteria:** Ireland rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_irl.py, tests/test_fed_irl.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_irl.py -v
```

---

## Agent 44 — Portugal Federation Scraper (POR)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_por.py`, `tests/test_fed_por.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_por.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `por`, SOURCE: `por_fencing`, COUNTRY: `Portugal`
- Probe URL: `fpesgrima.pt`
- Language: Portuguese. Column headers: Posição, Nome, Clube, Pontos
- Portuguese chars: c, a, o, e, a.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_por.py -v`.

**Success criteria:** Portugal rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_por.py, tests/test_fed_por.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_por.py -v
```

---

## Agent 45 — Greece Federation Scraper (GRE)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_gre.py`, `tests/test_fed_gre.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_gre.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `gre`, SOURCE: `gre_fencing`, COUNTRY: `Greece`
- Probe URL: `fencing.org.gr`
- Language: Greek. Column headers: Θέση, Ονοματεπώνυμο / Όνομα, Σύλλογος, Βαθμοί
- Greek alphabet range U+0370-U+03FF.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_gre.py -v`.

**Success criteria:** Greece rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_gre.py, tests/test_fed_gre.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_gre.py -v
```

---

## Agent 46 — Croatia Federation Scraper (CRO)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_cro.py`, `tests/test_fed_cro.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_cro.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `cro`, SOURCE: `cro_fencing`, COUNTRY: `Croatia`
- Probe URL: `hms.hr`
- Language: Croatian. Column headers: Mjesto / Poredak, Ime i prezime, Klub, Bodovi
- Croatian diacritics: c, c, d, s, z.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_cro.py -v`.

**Success criteria:** Croatia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_cro.py, tests/test_fed_cro.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_cro.py -v
```

---

## Agent 47 — Serbia Federation Scraper (SRB)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_srb.py`, `tests/test_fed_srb.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_srb.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `srb`, SOURCE: `srb_fencing`, COUNTRY: `Serbia`
- Probe URL: `macesavez.rs`
- Language: Serbian (Cyrillic + Latin). Column headers: Пласман / Pozicija, Име и презиме / Ime i prezime, Клуб / Klub, Бодови / Bodovi
- Both scripts may appear on same page.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_srb.py -v`.

**Success criteria:** Serbia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_srb.py, tests/test_fed_srb.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_srb.py -v
```

---

## Agent 48 — Bulgaria Federation Scraper (BUL)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_bul.py`, `tests/test_fed_bul.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_bul.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `bul`, SOURCE: `bul_fencing`, COUNTRY: `Bulgaria`
- Probe URL: `bulfencing.com`
- Language: Bulgarian (Cyrillic). Column headers: Място, Име, Клуб, Точки


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_bul.py -v`.

**Success criteria:** Bulgaria rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_bul.py, tests/test_fed_bul.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_bul.py -v
```

---

## Agent 49 — Slovakia Federation Scraper (SVK)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_svk.py`, `tests/test_fed_svk.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_svk.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `svk`, SOURCE: `svk_fencing`, COUNTRY: `Slovakia`
- Probe URL: `slovakfencing.sk`
- Language: Slovak. Column headers: Poradie, Meno, Klub, Body
- Slovak diacritics: a, a, c, d, e, i, l, l, n, o, o, r, s, t, u, y, z.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_svk.py -v`.

**Success criteria:** Slovakia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_svk.py, tests/test_fed_svk.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_svk.py -v
```

---

## Agent 50 — Slovenia Federation Scraper (SLO)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_slo.py`, `tests/test_fed_slo.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_slo.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `slo`, SOURCE: `slo_fencing`, COUNTRY: `Slovenia`
- Probe URL: `veza.si`
- Language: Slovenian. Column headers: Mesto / Uvrstitev, Ime, Klub, Točke
- Slovenian diacritics: c, s, z.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_slo.py -v`.

**Success criteria:** Slovenia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_slo.py, tests/test_fed_slo.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_slo.py -v
```

---

## Agent 51 — Lithuania Federation Scraper (LTU)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_ltu.py`, `tests/test_fed_ltu.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_ltu.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `ltu`, SOURCE: `ltu_fencing`, COUNTRY: `Lithuania`
- Probe URL: `ltf.lt`
- Language: Lithuanian. Column headers: Vieta, Vardas / Pavardė, Klubas, Taškai
- Lithuanian diacritics: a, c, e, e, i, s, u, u, z.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_ltu.py -v`.

**Success criteria:** Lithuania rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_ltu.py, tests/test_fed_ltu.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_ltu.py -v
```

---

## Agent 52 — Latvia Federation Scraper (LVA)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_lva.py`, `tests/test_fed_lva.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_lva.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `lva`, SOURCE: `lva_fencing`, COUNTRY: `Latvia`
- Probe URL: `pauksmes.lv`
- Language: Latvian. Column headers: Vieta, Vārds / Uzvārds, Klubs, Punkti
- Latvian diacritics: a, c, e, g, i, k, l, n, o, r, s, u, z.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_lva.py -v`.

**Success criteria:** Latvia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_lva.py, tests/test_fed_lva.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_lva.py -v
```

---

## Agent 53 — Estonia Federation Scraper (EST)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_est.py`, `tests/test_fed_est.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_est.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `est`, SOURCE: `est_fencing`, COUNTRY: `Estonia`
- Probe URL: `efl.ee`
- Language: Estonian. Column headers: Koht, Nimi, Klubi, Punktid
- Estonian diacritics: a, o, u, o.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_est.py -v`.

**Success criteria:** Estonia rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_est.py, tests/test_fed_est.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_est.py -v
```

---

## Agent 54 — Azerbaijan Federation Scraper (AZE)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_aze.py`, `tests/test_fed_aze.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_aze.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `aze`, SOURCE: `aze_fencing`, COUNTRY: `Azerbaijan`
- Probe URL: `azfencing.az`
- Language: Azerbaijani (Latin). Column headers: Yer, Ad, Klub, Xal
- Azerbaijani chars: a, g, i, o, s, u.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_aze.py -v`.

**Success criteria:** Azerbaijan rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_aze.py, tests/test_fed_aze.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_aze.py -v
```

---

## Agent 55 — Puerto Rico Federation Scraper (PUR)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_pur.py`, `tests/test_fed_pur.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_pur.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `pur`, SOURCE: `pur_fencing`, COUNTRY: `Puerto Rico`
- Probe URL: `fepur.org`
- Language: Spanish. Column headers: Posición / Puesto, Nombre, Club, Puntos


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_pur.py -v`.

**Success criteria:** Puerto Rico rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_pur.py, tests/test_fed_pur.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_pur.py -v
```

---

## Agent 56 — Dominican Republic Federation Scraper (DOM)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_dom.py`, `tests/test_fed_dom.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_dom.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `dom`, SOURCE: `dom_fencing`, COUNTRY: `Dominican Republic`
- Probe URL: `fedesgrimard.org`
- Language: Spanish. Column headers: Pos, Nombre, Club, Puntos


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_dom.py -v`.

**Success criteria:** Dominican Republic rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_dom.py, tests/test_fed_dom.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_dom.py -v
```

---

## Agent 57 — Jamaica Federation Scraper (JAM)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_jam.py`, `tests/test_fed_jam.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_jam.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `jam`, SOURCE: `jam_fencing`, COUNTRY: `Jamaica`
- Probe URL: `jamaicafencing.com`
- Language: English. Column headers: Rank, Name, Club, Points


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_jam.py -v`.

**Success criteria:** Jamaica rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_jam.py, tests/test_fed_jam.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_jam.py -v
```

---

## Agent 58 — Cyprus Federation Scraper (CYP)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_cyp.py`, `tests/test_fed_cyp.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_cyp.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `cyp`, SOURCE: `cyp_fencing`, COUNTRY: `Cyprus`
- Probe URL: `cyprusfencing.com`
- Language: Greek + English. Column headers: Θέση / Position, Ονοματεπώνυμο / Name, Σύλλογος / Club, Βαθμοί / Points
- Bilingual headers.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_cyp.py -v`.

**Success criteria:** Cyprus rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_cyp.py, tests/test_fed_cyp.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_cyp.py -v
```

---

## Agent 59 — Iceland Federation Scraper (ISL)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_isl.py`, `tests/test_fed_isl.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_isl.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `isl`, SOURCE: `isl_fencing`, COUNTRY: `Iceland`
- Probe URL: `skylmingar.is`
- Language: Icelandic. Column headers: Sæti, Nafn, Félag, Stig
- Icelandic chars: thorn, eth, ae, o.


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_isl.py -v`.

**Success criteria:** Iceland rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_isl.py, tests/test_fed_isl.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_isl.py -v
```

---

## Agent 60 — Malta Federation Scraper (MLT)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fed_mlt.py`, `tests/test_fed_mlt.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Use existing `season_utils.py` if present. If it is missing, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later. Do not depend on any numbered v2 agent for season utilities.

**Task:**
Build this national federation rankings scraper as a self-contained prompt. Do not rely on any shared contract outside this agent section.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py` if it exists.
2. Probe the country-specific URLs below before coding. Record the working URL, request method, response format, and which weapon/gender/category combos are public.
3. Implement the scraper with this structure:
   - Constants: `SOURCE`, `COUNTRY`, `BASE_URL`, `REQUEST_DELAY = 1.5`, browser-like `HEADERS`.
   - `RANKING_COMBOS`: Senior and Junior for Foil/Epee/Sabre, Men/Women.
   - `parse_rankings_table(html_or_text: str) -> list[dict]`: return rows with `rank`, `name`, `club`, `points`; handle language-specific headers, UTF-8/non-Latin scripts, decimal commas, and skip summary/DNS/DQ rows.
   - `fetch_rankings_page(weapon, gender, category) -> str | None`: return content for one combo; return `None` on 404/network error without crashing.
   - `current_season() -> str`: return `"YYYY-YYYY"` using `season_utils` when available.
   - `main()`: use `ScraperRunLogger`, iterate all combos, build rows with `fed_rankings_common.build_ranking_row()`, write via `write_rankings()`, sleep between requests, and log failed combos.
4. Write `tests/test_fed_mlt.py` with realistic fixtures from the probed source:
   - Parser returns at least one valid row with rank/name/points.
   - Empty HTML returns `[]`.
   - No-table/no-data page returns `[]`.
   - Non-standard rows such as DNS/DQ/summary rows are skipped.
   - Language-specific headers and native-script names are preserved.
5. Blocked handling:
   - 404/no public data: create a stub scraper that logs probed URLs and exits 0.
   - Login-only: check public subpages/API endpoints first; stub only after evidence.
   - JS-rendered: inspect XHR/API endpoints first; stub if no accessible API.
   - Partial combo coverage: implement available combos and report missing combos.
   - IP/geoblock: retry with delays/backoff, then document and stub if still blocked.

**Country-specific params:**
- CC: `mlt`, SOURCE: `mlt_fencing`, COUNTRY: `Malta`
- Probe URL: `maltasrim.com`
- Language: English. Column headers: Rank, Name, Club, Points


**Tests:**
- Parser fixture tests using real or realistic source HTML/PDF/XLS rows for rank/name/club/points extraction.
- Empty-page, no-table, malformed-row, non-numeric-rank, DNS/DQ, and summary-row skip tests.
- Fetch/stub tests for 404, blocked, login-only, JS-only, and missing-combo behavior.
- Run `pytest tests/test_fed_mlt.py -v`.

**Success criteria:** Malta rankings attempt all 12 combos, parse public data correctly, tests pass.

**When blocked:**
- Site returns 404 or no durable public ranking source exists: create a stub that logs `No scrapeable rankings at {URL}` and exits 0.
- Site requires login, blocks access, or is JS-only with no public API/XHR: document probe evidence and keep parser tests with captured/realistic fixtures.
- Only some weapon/gender/category combos are public: implement those, attempt all 12 standard combos, and list failed combos with reasons.

**Output format:**
```
Files: scrape_fed_mlt.py, tests/test_fed_mlt.py
Combos working: X/12
Data format: html/pdf/excel/stub
Risks: [remaining risks or skipped checks]
Tests: pytest tests/test_fed_mlt.py -v
```

---

## MORE TOURNAMENT SOURCES (15 agents)

---

## Agent 61 — National championships scraper for top-20 countries

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_national_champs.py`, `tests/test_scrape_national_champs.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Tier-1/Tier-2/Tier-3 federation scraper source discovery and existing result/fencer matching utilities.

**Task:**
1. Define a country config list for the top-20 fencing nations with federation URLs, language, expected result page types, and fallback notes.
2. Probe current public national championship result pages before coding each parser; prefer official federation pages and public PDFs/XLS/HTML.
3. Parse tournament, event, rank, fencer name, country/club, points/medal, weapon, gender, category, season, and source URL.
4. Use cross-source fencer matching by FIE ID when available, then name+country, and log unmatched rows instead of dropping them.
5. Write rows through existing result/tournament helpers or a clearly scoped adapter; never accept silent null-fencer orphans without logging.
6. Create stubs with probe evidence for countries that are blocked, login-only, or lack public data.

**Tests:**
- Parser tests with realistic HTML/PDF/XLS fixtures for at least three representative countries/languages.
- Matching tests for FIE ID, name+country, and unmatched logging.
- Blocked-source stub tests.
- Run `pytest tests/test_scrape_national_champs.py -v`.

**Success criteria:** Top-20 national championship sources are probed, parsable sources import safely, blocked sources exit 0 with evidence.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: scrape_national_champs.py, tests/test_scrape_national_champs.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 62 — BUCS UK university fencing results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_bucs.py`, `tests/test_scrape_bucs.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe BUCS/UK university fencing public results pages and any downloadable PDFs/CSV/fixtures before coding.
2. Parse university competition season, event, weapon, gender/category, team/individual result, fencer/university names, placement, and source URL.
3. Normalize UK university names and distinguish team results from individual fencer results.
4. Store or emit rows using existing tournament/result conventions; log unmatched fencers and university-only rows clearly.
5. Handle login-only or removed BUCS pages with a stub and documented probe evidence.
6. Use run logging, rate limiting, and scraper state.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- Parser fixture tests for BUCS individual and team result formats.
- Normalization tests for university names and season strings.
- Blocked/no-public-data stub test.
- Run `pytest tests/test_scrape_bucs.py -v`.

**Success criteria:** BUCS public results are parsed where available and team/individual data is not conflated.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_bucs.py, tests/test_scrape_bucs.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 63 — French university fencing league (FFSU)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_ffsu.py`, `tests/test_scrape_ffsu.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FFSU and French university sport result pages for fencing competitions and downloadable result files.
2. Parse French headers for rank, name, university/association, event, weapon, gender/category, points/medals, season, and source URL.
3. Normalize French names, accents, university labels, and season strings.
4. Map rows into existing result/tournament structures with best-effort fencer matching and logged unmatched rows.
5. Create a documented stub if current FFSU pages are blocked, removed, or non-public.
6. Use run logging, rate limiting, and parser tests from captured/realistic fixtures.

**Tests:**
- French HTML/PDF fixture parser tests including accented names and summary rows.
- Season/university normalization tests.
- No-public-data stub test.
- Run `pytest tests/test_scrape_ffsu.py -v`.

**Success criteria:** French university fencing results parse safely or stub with clear public-source evidence.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_ffsu.py, tests/test_scrape_ffsu.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 64 — Japanese university fencing league results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_japanese_univ.py`, `tests/test_scrape_japanese_univ.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe Japanese university fencing federation/league result pages and public PDFs before writing the parser.
2. Parse Japanese result headers for rank, athlete/team name, university, weapon, gender/category, points/medal, season/date, and source URL.
3. Handle UTF-8 Japanese names and university labels without lossy ASCII normalization.
4. Map results to tournaments/results with best-effort fencer matching and logged unmatched rows.
5. Support PDF/table fixtures and graceful stubs for blocked/no-public pages.
6. Use run logging, request delays, and scraper state.

**Tests:**
- Japanese fixture parser tests for CJK names, rank rows, summary rows, and missing points.
- Normalization tests preserving Unicode names.
- Blocked-source stub test.
- Run `pytest tests/test_scrape_japanese_univ.py -v`.

**Success criteria:** Japanese university results are parsed without Unicode loss or brittle fake data.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_japanese_univ.py, tests/test_scrape_japanese_univ.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 65 — USA Y12/Y14 youth national circuit results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_usa_youth.py`, `tests/test_scrape_usa_youth.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe current USA Fencing/FRED youth event APIs or public pages for Y12/Y14 national circuit results.
2. Parse event, weapon, gender, age group, rank, fencer name, club/division, points/medal, date, and source URL.
3. Use the new FRED platform rather than deprecated AskFRED if public data exists.
4. Match fencers cautiously; youth/minor data must avoid unnecessary personal enrichment beyond public results.
5. Handle missing FIE IDs and club/division-only identifiers with logged unmatched rows.
6. Stub blocked/no-public endpoints with probe evidence instead of scraping private data.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- Parser tests for public USA youth result fixtures and age-group normalization.
- Privacy test ensuring no extra minor profile scraping occurs.
- FRED/blocked endpoint dry-run tests.
- Run `pytest tests/test_scrape_usa_youth.py -v`.

**Success criteria:** USA Y12/Y14 public results import safely with minor-data restraint and no AskFRED dependency unless justified.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_usa_youth.py, tests/test_scrape_usa_youth.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 66 — British Youth Fencing results (BYC)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_british_youth.py`, `tests/test_scrape_british_youth.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe British Youth Championships and British Fencing public youth result pages/downloads.
2. Parse event, weapon, gender, age group, rank, fencer name, club/region, points/medal, season/date, and source URL.
3. Normalize UK regions/clubs and youth category labels while preserving names.
4. Use best-effort fencer matching and avoid extra minor profile scraping beyond public competition results.
5. Create documented stubs for blocked or non-public pages.
6. Use run logging, rate limiting, and scraper state.

**Tests:**
- Parser tests for British youth HTML/PDF fixtures with age groups and region/club fields.
- Minor-data restraint test and unmatched-row logging test.
- Run `pytest tests/test_scrape_british_youth.py -v`.

**Success criteria:** British youth results parse from public sources without over-collecting minor data.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_british_youth.py, tests/test_scrape_british_youth.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 67 — IWAS World Games and satellite wheelchair events

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_iwas_games.py`, `tests/test_scrape_iwas_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe IWAS, Wheelchair Fencing, Paralympic, and public satellite event result pages for current URL structures.
2. Parse wheelchair fencing event, classification when available, weapon, gender, rank, fencer, country, medal/points, date, and source URL.
3. Handle cases where FIE `hasResults` flags are wrong for veteran/wheelchair-style events by relying on actual public result evidence.
4. Map tournaments/results with source-specific metadata and log unmatched fencers.
5. Support HTML/PDF fixtures and graceful stubs for missing public data.
6. Use run logging, rate limiting, and no-crash behavior for incomplete classifications.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- IWAS/wheelchair fixture parser tests for classifications, medals, missing scores, and country normalization.
- No-public-data stub test.
- Run `pytest tests/test_scrape_iwas_games.py -v`.

**Success criteria:** IWAS and wheelchair satellite results import or stub with documented evidence and classification-safe parsing.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_iwas_games.py, tests/test_scrape_iwas_games.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 68 — Historical pre-2000 results from olympedia deep crawl

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_historical_olympedia.py`, `tests/test_scrape_historical_olympedia.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe Olympedia fencing result pages and respect public access/rate limits.
2. Crawl pre-2000 Olympic/continental/historical fencing pages only through stable public URLs discovered during probe.
3. Parse tournament, year, event, rank/medal, fencer name, country, team/individual flag, and source URL.
4. Normalize historical country codes and name variants without overwriting modern identities blindly.
5. Use incremental state so the crawler can resume and avoid repeated full crawls.
6. Log uncertain historical matches for reconciliation rather than forcing fencer IDs.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- Olympedia fixture tests for individual, team, historical country, tie/missing-rank, and Unicode names.
- Crawler state/resume tests with mocked pages.
- Run `pytest tests/test_scrape_historical_olympedia.py -v`.

**Success criteria:** Historical Olympedia crawl is resumable, rate-limited, and conservative about identity matching.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_historical_olympedia.py, tests/test_scrape_historical_olympedia.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 69 — FIE World Cup individual pool bout-by-bout data

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_fie_pools.py`, `tests/test_scrape_fie_pools.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe current FIE result APIs/pages for pool bout data and confirm endpoint shapes before coding.
2. Parse pool rounds, poule number, bout order, fencer IDs/names/countries, scores, victory indicators, priority/withdrawal markers, and source URL.
3. Write rows compatible with `fs_bouts` and existing result/tournament identifiers without duplicating elimination bouts.
4. Handle missing/rotating FIE endpoints, empty pools, team events, and incomplete scores gracefully.
5. Use fencer matching by FIE ID first and log unmatched names.
6. Use run logging, rate limiting, and scraper state.

**Tests:**
- FIE pool API/HTML fixture parser tests for normal pools, withdrawals, incomplete scores, and team-event skips.
- Dedup/upsert tests for `fs_bouts` compatibility.
- Run `pytest tests/test_scrape_fie_pools.py -v`.

**Success criteria:** FIE pool bout data imports into `fs_bouts` without duplicating or fabricating bouts.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_fie_pools.py, tests/test_scrape_fie_pools.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 70 — FIE Satellite and FIE Challenge series results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_fie_satellite.py`, `tests/test_scrape_fie_satellite.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FIE calendar/result APIs for Satellite and Challenge-series event identifiers and result availability.
2. Parse tournaments, event metadata, rankings/results, weapon, gender/category, date, location, source URL, and FIE IDs where present.
3. Use existing FIE competition URL discovery helpers where possible instead of duplicating endpoint logic.
4. Handle FIE veteran/satellite `hasResults` inconsistencies by checking actual result pages.
5. Match fencers by FIE ID first and log unmatched rows.
6. Use run logging, state, and rate limiting.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- FIE satellite/challenge fixture parser tests for event discovery, result rows, and missing hasResults flags.
- Mock endpoint tests for 404/empty data handling.
- Run `pytest tests/test_scrape_fie_satellite.py -v`.

**Success criteria:** Satellite/Challenge events are discovered and imported through current FIE endpoints with robust fallback behavior.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_fie_satellite.py, tests/test_scrape_fie_satellite.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 71 — Veterans World Cup circuit

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_veterans.py`, `tests/test_scrape_veterans.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FIE/EVF/veteran circuit public result pages and APIs before coding.
2. Parse veteran age categories, weapon, gender, rank, fencer, country/club, points/medal, date, tournament, and source URL.
3. Handle veteran-specific category labels and known FIE `hasResults` flag issues.
4. Avoid mixing veteran results into senior/junior category analytics without explicit category labels.
5. Match fencers conservatively and log unmatched rows.
6. Stub blocked/no-public sources with probe evidence.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- Veteran fixture parser tests for age categories, medals, missing scores, and category isolation.
- Endpoint/stub tests for no-public data.
- Run `pytest tests/test_scrape_veterans.py -v`.

**Success criteria:** Veteran circuit results parse with correct age-category handling and safe category separation.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_veterans.py, tests/test_scrape_veterans.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 72 — European Fencing Confederation (EFC) youth circuit

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_efc_youth.py`, `tests/test_scrape_efc_youth.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe European Fencing Confederation youth circuit pages/APIs and public result downloads.
2. Parse cadet/junior event metadata, weapon, gender, rank, fencer, country/club, points, date, and source URL.
3. Handle multilingual European pages, PDFs, and federation-hosted result links.
4. Use fencer matching by FIE ID if present, otherwise name+country with unmatched logging.
5. Avoid private/minor profile scraping beyond public competition results.
6. Use run logging, rate limiting, and blocked-source stubs.

**Tests:**
- EFC youth fixture parser tests for cadet/junior categories, multilingual headers, and points.
- Minor-data restraint and unmatched logging tests.
- Run `pytest tests/test_scrape_efc_youth.py -v`.

**Success criteria:** EFC youth results parse from public pages with category and minor-data safeguards.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_efc_youth.py, tests/test_scrape_efc_youth.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 73 — Asian Fencing Confederation (AFC) championships and circuit

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_afc.py`, `tests/test_scrape_afc.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe Asian Fencing Confederation and host federation public championship/circuit result pages.
2. Parse event metadata, weapon, gender/category, rank, fencer/team, country, medal/points, date, and source URL.
3. Handle English plus CJK/Korean/Japanese/Arabic host-country mirrors where current AFC pages link outward.
4. Normalize country names/codes through shared country-code utilities when available.
5. Match fencers conservatively and log unmatched rows.
6. Stub blocked/geoblocked pages with probe evidence.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- AFC fixture parser tests for English and one non-Latin host-page shape.
- Country normalization and blocked-source tests.
- Run `pytest tests/test_scrape_afc.py -v`.

**Success criteria:** AFC championship/circuit results import from public pages or stub with evidence when blocked.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_afc.py, tests/test_scrape_afc.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 74 — African Fencing Confederation championship results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_african_conf.py`, `tests/test_scrape_african_conf.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe African Fencing Confederation, federation mirrors, and public PDFs/social-site result pages before coding.
2. Parse event metadata, weapon, gender/category, rank, fencer/team, country, medal/points, date, and source URL.
3. Handle limited online presence by supporting sparse PDFs/HTML and preserving source evidence.
4. Normalize French/Arabic/English headers and country names.
5. Match fencers conservatively and log unmatched rows.
6. Create a stub if no durable public data source exists.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- African championship fixture parser tests for French/Arabic/English rows and sparse tables.
- No-public-data stub test.
- Run `pytest tests/test_scrape_african_conf.py -v`.

**Success criteria:** African confederation data is imported where public and otherwise documented without brittle fake scraping.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_african_conf.py, tests/test_scrape_african_conf.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 75 — Pan American Fencing Confederation (PAFC) circuit events

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_panam_conf.py`, `tests/test_scrape_panam_conf.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe Pan American Fencing Confederation and host federation public circuit/championship result pages.
2. Parse Spanish/English event metadata, weapon, gender/category, rank, fencer/team, country, medal/points, date, and source URL.
3. Normalize PAFC country names and Olympic/FIE codes using shared country-code utilities when available.
4. Support PDFs, HTML tables, and external live-result links discovered by probe.
5. Match fencers conservatively and log unmatched rows.
6. Stub blocked/missing pages with probe evidence.

7. Use explicit fencer matching: FIE ID where available, then canonical identity/name+country; log unmatched rows and never silently create null-fencer result orphans.

**Tests:**
- Spanish/English PAFC fixture parser tests for rank/name/country/points fields.
- Country-code normalization and blocked-source tests.
- Run `pytest tests/test_scrape_panam_conf.py -v`.

**Success criteria:** PAFC circuit/championship results parse from public sources with bilingual support.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: scrape_panam_conf.py, tests/test_scrape_panam_conf.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## DEEPER ANALYTICS (15 agents)

---

## Agent 76 — Elo rating system for fencers

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_elo.py`, `supabase/migrations/20260602_elo.sql`, `tests/test_elo.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_bouts`, identity logic, and existing analytics table patterns.
2. Create `fs_fencer_elo` or equivalent schema with fencer identity, weapon, category, rating, games, peak_rating, last_bout_at, version, and updated_at.
3. Implement deterministic Elo updates from chronologically ordered completed bouts only.
4. Use configurable K factors by competition tier/category and sensible defaults documented in code.
5. Skip null scores, missing fencers, duplicate bouts, and team events unless explicitly supported.
6. Upsert ratings idempotently and provide dry-run recompute behavior.

**Tests:**
- Migration tests for Elo table shape and indexes.
- Algorithm tests for expected rating updates, chronological ordering, duplicate skips, and empty input.
- Run `pytest tests/test_elo.py -v`.

**Success criteria:** Elo ratings recompute deterministically from bout data with tested math and safe skips.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_elo.py, supabase/migrations/20260602_elo.sql, tests/test_elo.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 77 — Legacy score: weighted medal index

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_legacy_score.py`, `supabase/migrations/20260602_legacy_score.sql`, `tests/test_legacy_score.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read medal/result tables, competition tiers, and fencer identity schema.
2. Create storage for legacy_score by fencer identity with score components, medal counts, tier weights, active span, and updated_at.
3. Implement a weighted medal/result index using explicit competition `type`/tier fields, not fragile tournament-name string matching.
4. Normalize team vs individual medals and avoid double-counting duplicate result rows.
5. Record component breakdowns for explainability.
6. Write tests for weights, duplicate prevention, team/individual handling, and schema.

**Tests:**
- Migration tests for legacy-score table shape.
- Algorithm tests for medal weights, tier fields, duplicate rows, and empty data.
- Run `pytest tests/test_legacy_score.py -v`.

**Success criteria:** Legacy scores are explainable, tier-field based, and robust against duplicate result rows.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_legacy_score.py, supabase/migrations/20260602_legacy_score.sql, tests/test_legacy_score.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 78 — Peak performance age analysis by weapon x gender

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_peak_age.py`, `tests/test_peak_age.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read fencer birth-date fields, results, rankings, and competition tier data.
2. Compute aggregate peak-age ranges by weapon, gender/category, country optional, and competition tier.
3. Use only fencers with reliable birth dates and result dates; exclude implausible ages and document thresholds.
4. Report aggregate distributions/statistics, not sensitive per-person inferences beyond public sports results.
5. Handle missing birth dates, partial dates, duplicate identities, and sparse cohorts.
6. Write output as a script report or table adapter consistent with existing analytics patterns.

**Tests:**
- Unit tests for age calculation, partial/missing dates, outlier exclusion, grouping, and sparse-data behavior.
- Run `pytest tests/test_peak_age.py -v`.

**Success criteria:** Peak-age analysis produces reliable aggregate stats and avoids misleading sparse/person-level claims.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_peak_age.py, tests/test_peak_age.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 79 — Upset tracker: lowest seed to medal per tournament

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_upsets.py`, `supabase/migrations/20260602_upsets.sql`, `tests/test_upsets.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read bracket, result, ranking/seed, and tournament schemas.
2. Create an upset table with tournament/event, fencer, opponent, seed/rank context, round, expected outcome, actual outcome, upset_score, and evidence metadata.
3. Use source seed/rank fields when available; do not infer seeds from final ranks after the event.
4. Detect lowest seed to medal, high-rank defeated by low-rank, and round-level upset records.
5. Skip events without pre-event seed/rank evidence and log them.
6. Write deterministic compute/upsert logic.

**Tests:**
- Migration tests for upset table shape.
- Algorithm tests for seed-based upsets, no-seed skips, duplicate bouts, and team-event handling.
- Run `pytest tests/test_upsets.py -v`.

**Success criteria:** Upsets are evidence-backed and never derived from post-event rank alone.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_upsets.py, supabase/migrations/20260602_upsets.sql, tests/test_upsets.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 80 — Home advantage analysis: fencer performance at home vs abroad

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_home_advantage.py`, `supabase/migrations/20260602_home_advantage.sql`, `tests/test_home_advantage.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read tournament location/country fields, fencer country history if available, and result tables.
2. Create home-advantage analytics storage with country, fencer/event grouping, home/away flag, expected baseline, actual placement/medal, delta, and updated_at.
3. Define home status using tournament country versus fencer country at event time where available.
4. Compute aggregate effects by country, weapon, gender/category, and competition tier.
5. Handle neutral/unknown venues, multi-national hosts, country transfers, and missing countries as explicit unknowns.
6. Write tests for classification and aggregation math.

**Tests:**
- Migration tests for table shape.
- Unit tests for home/away/unknown classification, transfer cases, aggregate deltas, and missing data.
- Run `pytest tests/test_home_advantage.py -v`.

**Success criteria:** Home advantage metrics are computed with explicit unknown handling and no country-transfer shortcuts.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_home_advantage.py, supabase/migrations/20260602_home_advantage.sql, tests/test_home_advantage.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 81 — Prediction model for next Olympic/World medalists

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_predictions.py`, `supabase/migrations/20260602_predictions.sql`, `tests/test_predictions.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read rankings, recent results, Elo/legacy/strength metrics, and competition calendars.
2. Create predictions storage with target event, fencer identity, probability/score, factors, model_version, generated_at, and caveats.
3. Implement a transparent deterministic baseline model; avoid black-box claims unless model inputs and validation are documented.
4. Use historical backtesting splits where possible and store expected-vs-actual validation metrics.
5. Avoid betting advice and label outputs as sports analytics, not guarantees.
6. Handle missing data and inactive fencers conservatively.

**Tests:**
- Migration tests for prediction table shape.
- Model tests for feature calculation, deterministic ranking, missing data, and backtest metric computation.
- Run `pytest tests/test_predictions.py -v`.

**Success criteria:** Predictions are transparent, validated by tests/backtests, and framed as non-guaranteed analytics.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_predictions.py, supabase/migrations/20260602_predictions.sql, tests/test_predictions.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 82 — Fantasy fencing scoring engine

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_fantasy_points.py`, `supabase/migrations/20260602_fantasy.sql`, `tests/test_fantasy.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Define fantasy scoring rules for placements, medals, upsets, participation, and penalties with documented weights.
2. Create fantasy points storage by fencer/event/season with components, total_points, rules_version, and updated_at.
3. Compute points from results/bouts using competition type/tier fields and avoid duplicate result double-counting.
4. Support recalculation when rules_version changes.
5. Handle team events, DNS/DQ, byes, and missing scores explicitly.
6. Write tests for every scoring component and versioning behavior.

**Tests:**
- Migration tests for fantasy table shape.
- Scoring tests for medals, placements, upsets, DNS/DQ, duplicate rows, and rules_version changes.
- Run `pytest tests/test_fantasy.py -v`.

**Success criteria:** Fantasy scoring is deterministic, versioned, and fully covered by component tests.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_fantasy_points.py, supabase/migrations/20260602_fantasy.sql, tests/test_fantasy.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 83 — Match-fixing / betting anomaly detection

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_anomalies.py`, `supabase/migrations/20260602_anomalies.sql`, `tests/test_anomalies.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Frame this as sports-integrity anomaly detection, not accusations or proof of wrongdoing.
2. Create anomaly storage with bout/tournament/fencer references, anomaly_type, score, evidence, model_version, reviewed flag, and created_at.
3. Detect statistical outliers such as scoreline anomalies, ranking-vs-result deltas, repeated unusual patterns, and betting-data mismatches only if lawful/public data exists.
4. Require clear evidence fields and confidence levels; do not name match-fixing in generated records without human review.
5. Handle small sample sizes, missing rankings, and duplicate bouts conservatively.
6. Write tests for outlier scoring and false-positive guardrails.

**Tests:**
- Migration tests for anomaly table shape and reviewed flag.
- Algorithm tests for normal cases, outliers, low-sample suppression, and evidence payloads.
- Run `pytest tests/test_anomalies.py -v`.

**Success criteria:** Anomaly detection flags review-worthy statistical outliers without making unsupported accusations.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_anomalies.py, supabase/migrations/20260602_anomalies.sql, tests/test_anomalies.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 84 — Fencer head-to-head network graph computation

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_h2h_graph.py`, `supabase/migrations/20260602_h2h_graph.sql`, `tests/test_h2h_graph.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read `fs_head_to_head`, `fs_bouts`, identity logic, and graph/frontend needs.
2. Create graph storage for nodes/edges or compact adjacency data with fencer identity, opponent, weapon, bouts, wins, losses, strength, and updated_at.
3. Compute network centrality/degree metrics from completed bouts while respecting identity dedupe.
4. Limit graph size or provide filters so frontend/API consumers do not load the entire graph accidentally.
5. Handle disconnected fencers, duplicate bouts, and missing fencer IDs.
6. Write deterministic tests for graph construction and metrics.

**Tests:**
- Migration tests for graph table shape.
- Algorithm tests for adjacency, centrality/degree, duplicate skips, and empty/disconnected graphs.
- Run `pytest tests/test_h2h_graph.py -v`.

**Success criteria:** H2H graph metrics are deduped, bounded, and suitable for API/frontend consumption.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_h2h_graph.py, supabase/migrations/20260602_h2h_graph.sql, tests/test_h2h_graph.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 85 — Competition difficulty trending over time

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_difficulty_trend.py`, `tests/test_difficulty_trend.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read strength-of-field metrics, tournament tiers, rankings, and historical result tables.
2. Compute competition difficulty trends over time by event/tier/weapon/gender/category using stable strength metrics.
3. Use normalized seasons and avoid mixing event-name string matches with type/tier fields.
4. Handle sparse seasons, missing ranking data, and changing competition formats.
5. Output aggregate rows/report data with confidence/sample counts.
6. Write tests for trend windows, missing data, and season ordering.

**Tests:**
- Unit tests for moving averages, season normalization, sparse data, and tier grouping.
- Run `pytest tests/test_difficulty_trend.py -v`.

**Success criteria:** Difficulty trends are computed from explicit strength/tier fields with clear sample counts.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_difficulty_trend.py, tests/test_difficulty_trend.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 86 — Fencer clutch metric: performance delta elimination vs pool

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_clutch.py`, `supabase/migrations/20260602_clutch.sql`, `tests/test_clutch.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read pool results, elimination bouts, rankings/seeds, and performance-vs-ranking metrics.
2. Create clutch metric storage with fencer identity, event, pool_performance, elimination_performance, expected_result, actual_result, delta, confidence, and updated_at.
3. Compare elimination performance against pool/ranking expectation using transparent formulas.
4. Require enough pool and DE evidence before scoring; otherwise skip with reason.
5. Handle byes, withdrawals, team events, and missing scores explicitly.
6. Write tests for formula, skip conditions, and edge cases.

**Tests:**
- Migration tests for clutch table shape.
- Algorithm tests for expected-vs-actual delta, insufficient-data skips, byes, and missing scores.
- Run `pytest tests/test_clutch.py -v`.

**Success criteria:** Clutch metrics are explainable and only computed when pool/DE evidence is adequate.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_clutch.py, supabase/migrations/20260602_clutch.sql, tests/test_clutch.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 87 — Country specialization index

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_country_specialization.py`, `tests/test_country_specialization.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read country medal/depth, rankings, and result aggregates.
2. Compute country specialization by weapon, gender/category, tier, and season using shares, z-scores, or normalized indexes.
3. Use country-code single source of truth and avoid raw display-name grouping.
4. Include sample counts and confidence so small countries/events are not overinterpreted.
5. Output report/table rows consistent with existing analytics patterns.
6. Write tests for normalization, sparse data, and multi-weapon comparisons.

**Tests:**
- Unit tests for index math, country-code normalization, sparse samples, and tie handling.
- Run `pytest tests/test_country_specialization.py -v`.

**Success criteria:** Country specialization metrics are normalized, sample-aware, and grouped by stable country codes.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_country_specialization.py, tests/test_country_specialization.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 88 — Junior-to-Senior conversion rate by country and weapon

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_junior_conversion.py`, `tests/test_junior_conversion.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read junior/senior results, rankings, fencer identity, and season utilities.
2. Identify junior cohorts and track senior appearances, rankings, medals, and top placements across defined windows.
3. Compute conversion rates by country, weapon, gender/category, and cohort season with sample counts.
4. Use canonical identities so junior and senior rows for the same person are connected.
5. Handle name changes, country transfers, missing birth/category data, and sparse cohorts conservatively.
6. Write tests for cohort detection and conversion math.

**Tests:**
- Unit tests for cohort selection, identity linking, conversion windows, country transfer handling, and sparse data.
- Run `pytest tests/test_junior_conversion.py -v`.

**Success criteria:** Junior-to-senior conversion rates are identity-aware and sample-counted by country/weapon.

**When blocked:**
- If required source data is missing, keep the implementation deterministic with explicit skipped counts and tests for the missing-data path.
- Do not invent fallback data to make tests pass.

**Output format:**
```
Files: compute_junior_conversion.py, tests/test_junior_conversion.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 89 — Medal efficiency: medals per capita, per fencer, per competition

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_medal_efficiency.py`, `tests/test_medal_efficiency.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read medal tables, country depth metrics, country-code data, and optional population/fencer-count sources.
2. Compute medals per capita, medals per active fencer, medals per competition, and tier-weighted efficiency by country/season.
3. Use stable country codes and explicit competition tier/type fields.
4. Handle missing population/fencer counts with null efficiency fields and clear sample counts.
5. Avoid over-ranking countries with tiny samples without confidence/sample metadata.
6. Write tests for all denominators and missing-data behavior.

**Tests:**
- Unit tests for medal counts, denominator normalization, missing denominator nulls, tier weights, and small-sample handling.
- Run `pytest tests/test_medal_efficiency.py -v`.

**Success criteria:** Medal efficiency metrics are denominator-aware, tier-aware, and transparent about missing data.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: compute_medal_efficiency.py, tests/test_medal_efficiency.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 90 — Fencer similarity recommendation engine

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `compute_fencer_similarity.py`, `supabase/migrations/20260602_similarity.sql`, `tests/test_fencer_similarity.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read fencer stats, rankings, results, weapons, country, age/birth fields, and identity logic.
2. Create similarity storage with fencer_id, similar_fencer_id, score, factor breakdown, model_version, and updated_at.
3. Build normalized feature vectors from public sports data only: weapon, hand if available, ranking history, results, style proxies, country, and career stage.
4. Compute similarity deterministically and exclude self/duplicate identity matches.
5. Handle missing features and sparse data with confidence/sample fields.
6. Write tests for feature construction, scoring, symmetry/deduping, and missing data.

**Tests:**
- Migration tests for similarity table shape and unique pairs.
- Algorithm tests for vector normalization, score ordering, self-exclusion, duplicate identity exclusion, and sparse data.
- Run `pytest tests/test_fencer_similarity.py -v`.

**Success criteria:** Similarity recommendations are deterministic, public-data-based, and identity-deduped.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: compute_fencer_similarity.py, supabase/migrations/20260602_similarity.sql, tests/test_fencer_similarity.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## MORE ENRICHMENT (15 agents)

---

## Agent 91 — Fencer education and occupation from Wikipedia + Wikidata

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_education.py`, `tests/test_enrich_education.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing Wikidata/Wikipedia enrichment helpers and fencer identity/wikidata fields.
2. Use Wikidata SPARQL/API to fetch education and occupation claims for fencers with `wikidata_id`.
3. Store or emit normalized public fields with claim IDs/source URLs and confidence; do not infer education/occupation from biographies by loose text alone.
4. Handle missing claims, multiple values, deprecated ranks, and language labels.
5. Rate limit requests and use run logging/state.
6. Write dry-run behavior for missing credentials/network.

**Tests:**
- SPARQL/API fixture tests for education, occupation, multiple claims, deprecated/no-value claims, and label fallback.
- No-network dry-run and upsert/update payload tests.
- Run `pytest tests/test_enrich_education.py -v`.

**Success criteria:** Education/occupation enrichment uses sourced Wikidata claims and skips unsupported inference.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: enrich_education.py, tests/test_enrich_education.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 92 — Fencer family relationships from Wikidata

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_family.py`, `supabase/migrations/20260602_family.sql`, `tests/test_enrich_family.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read fencer identity and Wikidata enrichment patterns.
2. Create `fs_fencer_family_relationships` with fencer identity, related person, relationship type, related wikidata_id/fencer_id if matched, source, confidence, and metadata.
3. Fetch public Wikidata family claims such as sibling, parent, spouse, child, and relative where relevant.
4. Match related people to existing fencers by wikidata_id first and avoid loose name-only linking.
5. Exclude private/minor-sensitive details not present in public Wikidata claims.
6. Write migration and enrichment tests.

**Tests:**
- Migration tests for relationship table shape and unique keys.
- Wikidata fixture tests for claim parsing, related-fencer matching, and ambiguous skip behavior.
- Run `pytest tests/test_enrich_family.py -v`.

**Success criteria:** Family relationships are sourced, public, and linked only with high-confidence identifiers.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: enrich_family.py, supabase/migrations/20260602_family.sql, tests/test_enrich_family.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 93 — Anti-doping test history per fencer (from ITA/WADA)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_doping.py`, `supabase/migrations/20260602_doping.sql`, `tests/test_scrape_doping.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe ITA/WADA/public sanction pages and determine whether fencing-specific anti-doping data is public and scrapeable.
2. Create a sanctions/testing-history table only for public, source-backed records with athlete, date, sanction/test type if public, authority, source URL, and metadata.
3. Do not infer doping history from news rumors or private data; distinguish tests, sanctions, appeals, and cleared cases.
4. Implement parser/stub behavior with careful terminology and legal-risk comments.
5. Match fencers by explicit identifiers or strong name+country+date evidence; log ambiguous rows.
6. Use rate limiting and run logging.

**Tests:**
- Migration tests for public-record table shape.
- Parser tests for official sanction fixtures, cleared/appeal cases, ambiguous names, and no-public-data stub.
- Run `pytest tests/test_scrape_doping.py -v`.

**Success criteria:** Anti-doping records are official/public, carefully labeled, and never inferred from weak evidence.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_doping.py, supabase/migrations/20260602_doping.sql, tests/test_scrape_doping.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 94 — Referee match assignments per tournament

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_referee_assignments.py`, `supabase/migrations/20260602_referee_assignments.sql`, `tests/test_referee_assignments.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FIE/Engarde/live-result pages for public referee assignment data.
2. Create `fs_referee_assignments` with tournament/event/bout, referee name/id if available, country, role, piste, round, source URL, and metadata.
3. Parse assignments from bout sheets, PDFs, or API responses only when publicly available.
4. Avoid creating duplicate referee identities from name-only rows; store raw name/source when IDs are absent.
5. Handle missing assignments, multiple referees, and role labels.
6. Use run logging, rate limiting, and blocked-source stubs.

**Tests:**
- Migration tests for assignment table shape and indexes.
- Parser tests for HTML/PDF/API fixtures with multiple referees and missing IDs.
- Run `pytest tests/test_referee_assignments.py -v`.

**Success criteria:** Referee assignments are captured from public bout evidence without over-linking name-only rows.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_referee_assignments.py, supabase/migrations/20260602_referee_assignments.sql, tests/test_referee_assignments.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 95 — Club founding dates, history text, notable alumni

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_clubs.py`, `supabase/migrations/20260602_club_enrichment.sql`, `tests/test_enrich_clubs.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read club fields from federation rankings/results and any existing club normalization.
2. Create club enrichment storage with club name, normalized name, country, website, founding_date, history_summary, notable_alumni, source URLs, and metadata.
3. Use official club/federation/Wikipedia/Wikidata public sources; do not scrape private forums or reviews in this agent.
4. Normalize clubs conservatively and avoid merging clubs across countries on name alone.
5. Link notable alumni only through existing fencer IDs or sourced public claims.
6. Use rate limiting, run logging, and stubs for blocked/no-source clubs.

**Tests:**
- Migration tests for club enrichment table shape.
- Parser/enrichment tests for official pages, Wikidata claims, conservative normalization, and ambiguous-club skip behavior.
- Run `pytest tests/test_enrich_clubs.py -v`.

**Success criteria:** Club enrichment is public-source-backed and avoids unsafe club merges.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: enrich_clubs.py, supabase/migrations/20260602_club_enrichment.sql, tests/test_enrich_clubs.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 96 — Coach career history

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_coach_history.py`, `supabase/migrations/20260602_coach_history.sql`, `tests/test_enrich_coach_history.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing referee/coach data and federation/team staff enrichment patterns.
2. Create coach history storage with coach name/id if known, country/team/club, role, start/end dates if public, source URL, and metadata.
3. Fetch from public federation staff pages, Wikidata/Wikipedia, and official team announcements.
4. Normalize role labels and date ranges; do not infer employment history from unsourced mentions.
5. Link coaches to fencers/teams only with clear evidence.
6. Use run logging, rate limits, and blocked-source stubs.

**Tests:**
- Migration tests for coach history table shape.
- Parser tests for federation staff pages, date ranges, role normalization, and ambiguous linking skips.
- Run `pytest tests/test_enrich_coach_history.py -v`.

**Success criteria:** Coach career history is official/public-source-backed and safely linked.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: enrich_coach_history.py, supabase/migrations/20260602_coach_history.sql, tests/test_enrich_coach_history.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 97 — Fencer video highlight reels auto-curated from YouTube

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `aggregate_videos.py`, `supabase/migrations/20260602_videos.sql`, `tests/test_aggregate_videos.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Use YouTube Data API or public provider APIs when keys are available; do not download videos by default.
2. Create `fs_videos` with provider, video_id, title, channel, url, thumbnail, published_at, duration, related fencer/tournament IDs, tags, source, and metadata.
3. Search by known fencer names, tournaments, and official channels with conservative matching and false-positive filtering.
4. Store metadata and thumbnails only within provider terms; keep missing-key dry-run behavior.
5. Deduplicate by provider/video_id and update metadata idempotently.
6. Use run logging and rate limiting.

**Tests:**
- Migration tests for video table shape and uniqueness.
- API fixture tests for search results, false-positive filtering, related-entity linking, and missing-key dry run.
- Run `pytest tests/test_aggregate_videos.py -v`.

**Success criteria:** Video index is API-backed, deduped, and does not download/process media unexpectedly.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: aggregate_videos.py, supabase/migrations/20260602_videos.sql, tests/test_aggregate_videos.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 98 — Interview quotes database from press conferences and media

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_quotes.py`, `supabase/migrations/20260602_quotes.sql`, `tests/test_scrape_quotes.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe official FIE/federation/news press pages for public quotes and press conferences.
2. Create `fs_quotes` with quote text excerpt, speaker, fencer_id if confidently matched, event/tournament, source title/url, published_at, language, and metadata.
3. Respect copyright by storing short excerpts and source links, not full articles/transcripts.
4. Match speakers by explicit page context or known IDs; log ambiguous names.
5. Handle multilingual quotes and translated/duplicate articles.
6. Use rate limiting, run logging, and stubs for blocked sites.

**Tests:**
- Migration tests for quote table shape.
- Parser tests for quote extraction, excerpt limits, speaker matching, multilingual text, and duplicate detection.
- Run `pytest tests/test_scrape_quotes.py -v`.

**Success criteria:** Quotes are short, sourced, copyright-conscious, and conservatively linked.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_quotes.py, supabase/migrations/20260602_quotes.sql, tests/test_scrape_quotes.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 99 — Fencer sponsorship deals and endorsement history

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_sponsorships.py`, `supabase/migrations/20260602_sponsorships.sql`, `tests/test_scrape_sponsorships.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe official athlete pages, federation bios, Wikidata, sponsor pages, and public announcements for sponsorship evidence.
2. Create `fs_sponsorships` with fencer identity, sponsor/brand, category, start/end if public, evidence text excerpt, source URL, confidence, and metadata.
3. Do not infer sponsorships solely from equipment usage or social-media appearance; require explicit public evidence.
4. Normalize brand names and link to equipment/product tables where supported.
5. Handle expired/ambiguous deals and avoid private financial terms unless publicly stated.
6. Use rate limiting, run logging, and parser tests.

**Tests:**
- Migration tests for sponsorship table shape.
- Parser tests for official announcements, ambiguous mentions, brand normalization, and expired deals.
- Run `pytest tests/test_scrape_sponsorships.py -v`.

**Success criteria:** Sponsorship records are explicit, sourced, and not inferred from weak signals.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_sponsorships.py, supabase/migrations/20260602_sponsorships.sql, tests/test_scrape_sponsorships.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 100 — Fencer nationality history from Wikidata

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_nationality_history.py`, `supabase/migrations/20260602_nationality_history.sql`, `tests/test_enrich_nationality_history.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read existing nationality/transfer tracker outputs and Wikidata enrichment patterns.
2. Create nationality history storage with fencer identity, country code, start/end dates or point-in-time qualifiers, source, confidence, and metadata.
3. Fetch Wikidata citizenship/national team/country claims and reconcile with ranking/result country changes.
4. Use country-code utilities and preserve historical country codes where source-backed.
5. Do not overwrite current country blindly; emit history rows and discrepancies for reconciliation.
6. Write tests for qualifiers, transfers, ambiguous claims, and country-code normalization.

7. Use only public Wikidata/federation/result evidence for nationality history; do not infer private citizenship or overwrite current country fields from unsourced claims.

**Tests:**
- Migration tests for nationality history table shape.
- Wikidata fixture tests for citizenship claims, qualifiers, multiple countries, and transfer reconciliation.
- Run `pytest tests/test_enrich_nationality_history.py -v`.

**Success criteria:** Nationality history is source-backed, historical, and reconciled without clobbering current country fields.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: enrich_nationality_history.py, supabase/migrations/20260602_nationality_history.sql, tests/test_enrich_nationality_history.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 101 — Competition weather data (indoor vs outdoor, temperature, humidity)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_weather.py`, `supabase/migrations/20260602_weather.sql`, `tests/test_enrich_weather.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read venue/location data and determine whether weather is relevant for fencing events, which are usually indoor.
2. Create weather/context storage with tournament_id, venue/location, date, indoor/outdoor flag if known, temperature/humidity fields if available, source, and metadata.
3. Use public weather APIs only with approved keys or dry-run fixtures; do not call paid services without approval.
4. Mark indoor events clearly and avoid implying weather affected results without evidence.
5. Cache lookups and handle missing geocodes/date ranges gracefully.
6. Write tests for indoor defaults, API fixture parsing, cache behavior, and missing data.

**Tests:**
- Migration tests for weather table shape.
- Unit tests for indoor/outdoor classification, API normalization, cache/missing-key behavior, and missing venues.
- Run `pytest tests/test_enrich_weather.py -v`.

**Success criteria:** Weather enrichment is cautious, cached, and does not overclaim relevance for indoor fencing.

**When blocked:**
- If the public source is blocked, login-only, paid/API-key-only, or unavailable, implement a stub that exits 0 and prints clear probe evidence.
- Do not fabricate production rows; keep parser tests using captured or realistic fixtures that match the probed source shape.

**Output format:**
```
Files: enrich_weather.py, supabase/migrations/20260602_weather.sql, tests/test_enrich_weather.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 102 — Equipment usage trends (brands winning by weapon)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_equipment_trends.py`, `supabase/migrations/20260602_equipment_trends.sql`, `tests/test_scrape_equipment_trends.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Read equipment/brand/product enrichment tables and public FIE profile patterns.
2. Create equipment trend storage by brand, equipment category, weapon, event/tier, fencer/result, source, confidence, and updated_at.
3. Extract brand/equipment usage only from explicit public profile/sponsor/product evidence, not image guessing.
4. Aggregate trends such as brand wins by weapon while preserving evidence rows.
5. Normalize brand names against product/sponsorship data.
6. Use run logging, rate limiting, and no-public-data stubs.

**Tests:**
- Migration tests for trend/evidence table shape.
- Parser tests for explicit equipment/sponsor text, brand normalization, ambiguous mentions, and aggregate calculations.
- Run `pytest tests/test_scrape_equipment_trends.py -v`.

**Success criteria:** Equipment trends are evidence-backed and aggregated without visual/speculative inference.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_equipment_trends.py, supabase/migrations/20260602_equipment_trends.sql, tests/test_scrape_equipment_trends.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 103 — Fencer handedness data (left-handed vs right-handed stats)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `enrich_handedness.py`, `supabase/migrations/20260602_handedness.sql`, `tests/test_enrich_handedness.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FIE profiles, federation bios, Wikidata, and public athlete pages for handedness fields.
2. Create handedness storage with fencer identity, handedness, source URL, confidence, collected_at, and metadata.
3. Do not infer handedness from photos/video unless a future human-reviewed pipeline explicitly supports it.
4. Normalize left/right/ambidextrous/unknown values and support multilingual labels.
5. Link by wikidata/FIE IDs first and log ambiguous name-only matches.
6. Use rate limiting, run logging, and dry-run behavior.

**Tests:**
- Migration tests for handedness table shape and enum/check constraints if used.
- Parser tests for profile/Wikidata fixtures, multilingual labels, unknown values, and ambiguous skip behavior.
- Run `pytest tests/test_enrich_handedness.py -v`.

**Success criteria:** Handedness enrichment is sourced from explicit public profile data and never inferred from media.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: enrich_handedness.py, supabase/migrations/20260602_handedness.sql, tests/test_enrich_handedness.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 104 — Fencer injury history from news scraping

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_injuries.py`, `supabase/migrations/20260602_injuries.sql`, `tests/test_scrape_injuries.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe official federation/FIE/news public pages for injury/absence announcements.
2. Create injury/absence storage with fencer identity, event/date, status type, short source-backed summary, source URL, confidence, and metadata.
3. Avoid medical speculation; store only public announced injuries/absences and concise excerpts.
4. Distinguish injury, illness, suspension, personal absence, and unknown reasons when stated.
5. Match fencers conservatively and log ambiguous mentions.
6. Use rate limiting, copyright-conscious excerpts, and no-public-data stubs.

**Tests:**
- Migration tests for injury/absence table shape.
- Parser tests for official announcements, non-injury absence labels, excerpt limits, ambiguous matches, and blocked-source stub.
- Run `pytest tests/test_scrape_injuries.py -v`.

**Success criteria:** Injury/absence data is public, cautious, sourced, and not medically speculative.

**When blocked:**
- If the backing table/view does not exist yet, implement a typed helper against mocked fixtures and document the dependency.
- Do not broaden shared API/router files beyond the listed scoped module.

**Output format:**
```
Files: scrape_injuries.py, supabase/migrations/20260602_injuries.sql, tests/test_scrape_injuries.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 105 — Historical rule changes database and their impact on results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger -- use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state -- persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ -- CI integration is handled by Agent 160.

**Files:** `scrape_rule_changes.py`, `supabase/migrations/20260602_rule_changes.sql`, `tests/test_scrape_rule_changes.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
1. Probe FIE rule books, congress decisions, federation summaries, and historical sources for public fencing rule changes.
2. Create rule-change storage with effective date/season, weapon/category affected, rule area, summary, source URL, source type, and metadata.
3. Parse rule-change timelines and link to affected competitions/seasons where evidence exists.
4. Do not claim causal impact on results unless paired with a tested aggregate analysis and clear caveats.
5. Support manual seed fixtures for older rule changes when web pages are unavailable but sources are cited.
6. Write parser and migration tests.

**Tests:**
- Migration tests for rule-change table shape.
- Parser tests for rulebook/changelog fixtures, effective dates, weapon filters, citation requirements, and missing-date behavior.
- Run `pytest tests/test_scrape_rule_changes.py -v`.

**Success criteria:** Rule-change database is source-cited, date-aware, and separates historical facts from impact claims.

**When blocked:**
- If an existing schema conflict is discovered, document the conflict and write the narrowest compatible migration/test instead of forcing a rewrite.
- Never drop, truncate, or rewrite production data in this agent.

**Output format:**
```
Files: scrape_rule_changes.py, supabase/migrations/20260602_rule_changes.sql, tests/test_scrape_rule_changes.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## PRODUCT / FRONTEND / API (25 agents)

---

## Agent 106 — Next.js frontend with search + browse for all entities

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/`, `frontend/package.json`, `frontend/next.config.js`, `frontend_api_contract.py`, `tests/test_frontend_contract.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 24-30 API/public-view outputs and existing Supabase/API data contracts; do not duplicate backend logic in the frontend.

**Task:**
1. Read any existing frontend conventions, `api.py`, `docs/api.yaml`, public Supabase views, and current repository package files before scaffolding. Do not edit `api.py`; put frontend-specific backend contract shims in `frontend_api_contract.py` if needed.
2. Create a Next.js TypeScript app under `frontend/` with Tailwind CSS and shadcn/ui only if no compatible frontend already exists; otherwise extend the existing app in place.
3. Implement pages for `/`, `/fencers`, `/fencers/[id]`, `/tournaments`, `/tournaments/[id]`, `/rankings`, `/countries/[code]`, and `/head-to-head` with loading, empty, and error states.
4. Use safe server-side data loading for public data; never expose `SUPABASE_SERVICE_KEY` or scraper credentials to the browser.
5. Add a small API/data-client layer that matches `docs/api.yaml` or public Supabase views and keeps query params validated.
6. Add responsive, accessible UI states for search filters, pagination, cards/tables, and detail pages without marketing-only landing content.

**Tests:**
- Vitest or Playwright coverage for search filters, route rendering, empty/error states, and no service-key exposure.
- `npm run build` or the repo-equivalent frontend build command passes.
- Contract test verifies required public fields exist in API/view responses or mocked fixtures.

**Success criteria:**
- Frontend runs locally, renders live/mocked fencer and tournament data, and exposes no private env vars.
- All listed pages exist with search/browse behavior and accessible loading/error/empty states.
- Tests and build pass or skipped checks are explicitly justified.

**When blocked:**
- If frontend dependencies are not installed, request approval before installing; otherwise write code and tests only.
- If no backend/public view can satisfy a page, document the missing field and use a typed mock fixture in tests without inventing production data.

**Output format:**
```
Files: frontend/, frontend/package.json, frontend/next.config.js, frontend_api_contract.py, tests/test_frontend_contract.py
Pages: [list]
Build: pass/fail
Tests: [commands and results]
Risks: [remaining risks]
```

---

## Agent 107 — GraphQL API wrapping existing REST + Supabase

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `graphql/`, `tests/test_graphql_api.py`, `docs/graphql.md`, `docker-compose.yml`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing `api.py`, public Supabase views, and Agents 24-30 API/public data modules where available.

**Task:**
1. Choose a minimal GraphQL implementation that fits the repo: Apollo/Strawberry/FastAPI GraphQL or Hasura only if Docker is already acceptable.
2. Define schema types for fencers, tournaments, rankings, results, H2H, countries, news, and products using existing tables/views rather than new storage.
3. Implement resolvers with pagination, field whitelisting, input validation, and API-key/auth handling consistent with `api.py`.
4. Prevent N+1 query behavior by batching lookups or selecting joined data where possible.
5. Document local startup and example queries in `docs/graphql.md`.
6. Keep GraphQL read-only unless a separate explicit mutation requirement exists.

**Tests:**
- Schema snapshot test for core types.
- Resolver tests for auth failure, pagination, invalid filters, and one happy path per core type.
- Import/startup test for the GraphQL app or Hasura config validation.

**Success criteria:**
- GraphQL endpoint exposes read-only project data with safe auth and pagination.
- Resolvers do not expose service keys or private columns.
- Tests pass and docs include example queries.

**When blocked:**
- If Hasura requires external install/network, ask before installing and provide a non-install fallback design.
- If a table/view is missing, document it and skip that resolver with a clear test expectation.

**Output format:**
```
Files: graphql/, tests/test_graphql_api.py, docs/graphql.md, docker-compose.yml
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 108 — WebSocket server for live results push

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `ws_server.py`, `tests/test_ws_server.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing live-result watcher/result tables and Agent 107 only if GraphQL/WebSocket integration is needed.

**Task:**
1. Read `watch_live_results.py`, `api.py`, `scrape_results.py`, and run logger/state patterns.
2. Implement a FastAPI WebSocket endpoint that streams new/changed `fs_results` and `fs_bouts` records by tournament ID.
3. Use heartbeat/ping, connection cleanup, backpressure-safe send loops, and per-client subscription filters.
4. Poll or consume scraper-state changes without blocking the event loop; do not write to production data from the socket server.
5. Validate tournament IDs and API keys before subscribing.
6. Add startup docs or comments for running the server locally.

**Tests:**
- WebSocket connect/auth test.
- Subscription filter test for tournament-specific events.
- Disconnect/cleanup test.
- No-event heartbeat test.

**Success criteria:**
- Clients receive only authorized live updates.
- Server handles disconnects and no-result polling without crashes.
- Tests pass.

**When blocked:**
- If live result state source is unavailable, implement a mocked polling abstraction and document the required DB query.

**Output format:**
```
Files: ws_server.py, tests/test_ws_server.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 109 — Competition bracket visualizer React component

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/BracketVisualizer.tsx`, `frontend/lib/brackets.ts`, `frontend/tests/bracket-visualizer.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 8, 9, 28, and frontend Agent 106 if present.

**Task:**
1. Read existing tournament/bracket data shape from `fs_tournament_brackets`, `fs_bouts`, and any tournament page code.
2. Build a reusable bracket visualizer component for DE rounds with seed, fencer, score, winner, bye, and incomplete-bout states.
3. Normalize bracket input in `frontend/lib/brackets.ts` so UI does not depend on raw DB quirks.
4. Add keyboard-accessible match cards, responsive horizontal scrolling, and empty/error states.
5. Integrate only where an existing tournament page exists; otherwise export the component and tests without forcing app-wide wiring.

**Tests:**
- Render test for full DE bracket.
- Render test for byes/incomplete bouts.
- Accessibility smoke test for labels/keyboard focus.
- Layout test or snapshot for mobile overflow behavior.

**Success criteria:**
- Component renders bracket data without overlap or crashing on missing scores.
- No raw service credentials or DB writes are introduced.
- Tests pass.

**When blocked:**
- If frontend app does not exist yet, create component/tests under `frontend/` without wiring routes.

**Output format:**
```
Files: frontend/components/BracketVisualizer.tsx, frontend/lib/brackets.ts, frontend/tests/bracket-visualizer.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 110 — Fencer career timeline visualizer React component

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/CareerTimeline.tsx`, `frontend/lib/careerTimeline.ts`, `frontend/tests/career-timeline.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 10-13, 27, and frontend Agent 106 if present.

**Task:**
1. Derive a typed timeline data model from career stats, milestones, medals, transfers, and longevity tables.
2. Build a timeline component that displays seasons/years, medals, ranking peaks, country changes, and notable milestones.
3. Handle sparse data, unknown dates, duplicate seasons, and long careers without visual overlap.
4. Add filters for weapon/category when data includes multiple weapons.
5. Keep formatting locale-safe and avoid assuming integer-only season strings.

**Tests:**
- Unit tests for timeline normalization.
- Component render tests for empty/sparse/full career data.
- Accessibility test for chronological labels.

**Success criteria:**
- Career timeline renders from typed data and handles missing fields safely.
- Tests pass with realistic career fixtures.

**When blocked:**
- If career/milestone tables are absent, use typed fixtures and document required backend fields.

**Output format:**
```
Files: frontend/components/CareerTimeline.tsx, frontend/lib/careerTimeline.ts, frontend/tests/career-timeline.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 111 — Country medal heatmap interactive map component

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/CountryMedalHeatmap.tsx`, `frontend/lib/countryMap.ts`, `frontend/tests/country-medal-heatmap.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 14, 15, and frontend Agent 106 if present.

**Task:**
1. Read country medal/geocode view shape and any existing country pages.
2. Build an interactive map or fallback choropleth/list that shows medal totals by country with gold/silver/bronze breakdown.
3. Use accessible tooltip/dialog behavior and a non-map table fallback for screen readers.
4. Handle missing coordinates and disputed/unknown country codes without crashing.
5. Keep map dependency lightweight and lazy-loaded if it affects bundle size.

**Tests:**
- Data normalization tests for ISO/country-code edge cases.
- Component tests for tooltip, no-coordinate fallback, and empty data.
- Bundle/import smoke test if a map library is added.

**Success criteria:**
- Heatmap renders medal data and gracefully handles missing geodata.
- Accessible fallback exists.
- Tests pass.

**When blocked:**
- If map library installation is needed, ask before installing; otherwise implement list/placeholder fallback with tests.

**Output format:**
```
Files: frontend/components/CountryMedalHeatmap.tsx, frontend/lib/countryMap.ts, frontend/tests/country-medal-heatmap.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 112 — Ranking history sparkline chart component

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/RankingSparkline.tsx`, `frontend/lib/rankingSparkline.ts`, `frontend/tests/ranking-sparkline.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 16, 17, 25, and frontend Agent 106 if present.

**Task:**
1. Normalize ranking history into ordered series by season/date, weapon, category, and points.
2. Build a compact sparkline component where lower rank numbers display as improvement, not decline.
3. Handle missing seasons, tied ranks, NULL points, and single-point series.
4. Add tooltips/ARIA labels with season, rank, and points.
5. Expose color/size props without coupling to a specific page.

**Tests:**
- Normalization tests for rank direction and missing seasons.
- Component render tests for empty/single/full series.
- Accessibility label tests.

**Success criteria:**
- Sparkline accurately represents ranking trend direction and remains readable in compact layouts.
- Tests pass.

**When blocked:**
- If chart dependencies are unavailable, implement SVG-only sparkline without adding packages.

**Output format:**
```
Files: frontend/components/RankingSparkline.tsx, frontend/lib/rankingSparkline.ts, frontend/tests/ranking-sparkline.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 113 — Head-to-head comparison page with side-by-side stats

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/pages/head-to-head.tsx`, `frontend/components/H2HComparison.tsx`, `frontend/tests/h2h-page.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 24, 84, 106, and H2H API/view availability.

**Task:**
1. Inspect H2H API/table shape and existing frontend routing conventions.
2. Build fencer search/select controls for two athletes with debounce and clear states.
3. Display side-by-side stats: wins, losses, touches, last meeting, weapon split, and recent bouts.
4. Handle same-fencer selection, no H2H record, missing fencer, and network errors.
5. Ensure query params can deep-link selected fencers without exposing private data.

**Tests:**
- Page tests for selecting fencers and rendering H2H stats.
- Edge tests for same fencer/no record/error states.
- Contract test for API response shape.

**Success criteria:**
- H2H page works with public data and handles all empty/error states.
- Tests pass.

**When blocked:**
- If frontend routing differs from Next.js pages, adapt path but keep component/page tests.

**Output format:**
```
Files: frontend/pages/head-to-head.tsx, frontend/components/H2HComparison.tsx, frontend/tests/h2h-page.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 114 — Tournament results PDF generator

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `generate_tournament_pdf.py`, `tests/test_generate_tournament_pdf.py`, `docs/pdf_export.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Tournament/result schemas plus Agents 28 and 29 for bracket/detail data when available.

**Task:**
1. Choose a lightweight PDF generation library already present or request approval before adding one.
2. Generate tournament result PDFs with tournament metadata, event table, medalists, full standings, and optional bout summary.
3. Validate tournament IDs and fail cleanly when data is missing.
4. Keep PDFs deterministic for tests by injecting date/time and using stable ordering.
5. Add CLI usage docs and do not write outside requested output paths.

**Tests:**
- Unit tests for data-to-PDF payload assembly.
- Golden/smoke test verifying generated PDF bytes/header and key text where feasible.
- Missing tournament/error test.

**Success criteria:**
- PDF generator creates readable tournament results and handles missing data safely.
- Tests pass.

**When blocked:**
- If PDF text extraction in tests is unavailable, verify generated bytes plus structured payload tests.

**Output format:**
```
Files: generate_tournament_pdf.py, tests/test_generate_tournament_pdf.py, docs/pdf_export.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 115 — Calendar sync ICS feed per federation/weapon/category

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `calendar_feed.py`, `tests/test_calendar_feed.py`, `docs/calendar_feed.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** `fs_tournaments`, tournament detail data from Agent 29 if available, and existing public API conventions.

**Task:**
1. Implement read-only ICS feed generation for tournaments filtered by federation/country/weapon/category/date range.
2. Use stable UID values and proper timezone/date handling.
3. Validate filter params and cap result counts to avoid huge responses.
4. Expose CLI or API-compatible function without modifying workflows.
5. Document example feed URLs and client behavior.

**Tests:**
- ICS generation test with stable UID/date fields.
- Filter validation tests.
- Empty feed test.

**Success criteria:**
- Valid ICS feeds are generated from tournament data with safe filters.
- Tests pass.

**When blocked:**
- If no web API exists, implement pure generator and CLI tests only.

**Output format:**
```
Files: calendar_feed.py, tests/test_calendar_feed.py, docs/calendar_feed.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 116 — Ranking alerts service email/SMS when fencer rank changes

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `ranking_alerts.py`, `supabase/migrations/20260602_ranking_alerts.sql`, `tests/test_ranking_alerts.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 16, 17, 25 and any notification/email provider config.

**Task:**
1. Create tables for alert subscriptions and alert delivery log with opt-in fields and unsubscribe token/hash.
2. Compute rank changes from ranking history/trends without sending duplicate alerts.
3. Implement provider abstraction for email/SMS; default to dry-run logging when credentials are missing.
4. Validate subscriber contact data and never log raw secrets.
5. Add rate limits and idempotency keys for delivery.

**Tests:**
- Migration shape tests.
- Rank-change detection tests.
- Dry-run provider tests.
- Unsubscribe/duplicate suppression tests.

**Success criteria:**
- Alerts are opt-in, idempotent, dry-run safe, and covered by tests.
- No live messages are sent during tests.

**When blocked:**
- If provider credentials are absent, keep dry-run mode and document required env vars.

**Output format:**
```
Files: ranking_alerts.py, supabase/migrations/20260602_ranking_alerts.sql, tests/test_ranking_alerts.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 117 — Automated result tweets bot Twitter/X integration

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `post_result_tweets.py`, `tests/test_post_result_tweets.py`, `docs/result_tweets.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Result tables and optional social API credentials.

**Task:**
1. Build a dry-run-first bot that formats tournament result summaries for posting.
2. Use scraper_state or delivery-log state to avoid duplicate posts.
3. Require explicit env vars for live posting; default to no-network dry run.
4. Validate message length, links, hashtags, and Unicode names.
5. Never print tokens or post from tests.

**Tests:**
- Message formatting tests.
- Duplicate suppression tests.
- Dry-run/no-credentials tests.
- Provider mock test for live-post path.

**Success criteria:**
- Bot can generate result posts safely and will not post unless explicitly configured.
- Tests pass.

**When blocked:**
- If Twitter/X API access is unavailable, keep provider mocked and document required credentials.

**Output format:**
```
Files: post_result_tweets.py, tests/test_post_result_tweets.py, docs/result_tweets.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 118 — Data syndication API for media partners

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `api_syndication.py`, `supabase/migrations/20260602_syndication_keys.sql`, `tests/test_api_syndication.py`, `docs/syndication_api.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing API/public views, Agent 30 public fencer view, and API key/auth conventions.

**Task:**
1. Design read-only partner endpoints for fencers, tournaments, rankings, results, and medal tables.
2. Create API-key table with scopes, rate limits, partner name, disabled flag, and last-used timestamp.
3. Implement auth, pagination, filtering, and response schemas without exposing private columns.
4. Add request logging that avoids storing secrets.
5. Document partner onboarding and sample requests.

**Tests:**
- Auth/scope failure tests.
- Pagination/filter tests.
- Private-field redaction tests.
- Rate-limit behavior test.

**Success criteria:**
- Syndication API is read-only, scoped, paginated, and documented.
- Tests pass.

**When blocked:**
- If API framework conflicts with existing `api.py`, expose routers/functions without starting a second incompatible app.

**Output format:**
```
Files: api_syndication.py, supabase/migrations/20260602_syndication_keys.sql, tests/test_api_syndication.py, docs/syndication_api.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 119 — BigQuery export pipeline for data science users

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `export_bigquery.py`, `tests/test_export_bigquery.py`, `docs/bigquery_export.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Public views/API outputs and analytics tables; BigQuery credentials are optional and must be dry-run safe.

**Task:**
1. Implement export payload builders for fencers, tournaments, results, bouts, rankings, and analytics tables.
2. Use dry-run/local JSON schema export when Google credentials are absent.
3. Add schema mapping with explicit column types and nullable handling.
4. Chunk large exports and track progress/state without loading entire tables into memory.
5. Document required Google env vars and dataset/table naming.

**Tests:**
- Schema mapping tests.
- Chunked export tests.
- Dry-run/no-credentials tests.
- Failure retry test.

**Success criteria:**
- Pipeline can dry-run exports and is safe without cloud credentials.
- Tests pass.

**When blocked:**
- Ask before installing Google SDK or running cloud writes.

**Output format:**
```
Files: export_bigquery.py, tests/test_export_bigquery.py, docs/bigquery_export.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 120 — Data marketplace / API monetization portal with Stripe

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `marketplace_api.py`, `supabase/migrations/20260602_marketplace.sql`, `tests/test_marketplace_api.py`, `docs/marketplace.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 118 syndication API, public API/view access, and Stripe test credentials if available.

**Task:**
1. Design subscription plans, API-key entitlements, usage counters, and billing status tables.
2. Use Stripe Checkout or Customer Portal only in test-mode unless explicitly approved.
3. Implement webhook signature verification and idempotent event handling.
4. Gate API access by subscription status and scopes without exposing private data.
5. Document env vars, local webhook testing, and failure handling.

**Tests:**
- Webhook signature/idempotency tests.
- Entitlement/access tests.
- Usage counter tests.
- No-secret-logging tests.

**Success criteria:**
- Marketplace access control is secure, test-mode safe, and covered by tests.
- No live Stripe calls are made without explicit approval.

**When blocked:**
- If Stripe SDK/docs are unavailable, write schema and mocked service layer with clear docs.

**Output format:**
```
Files: marketplace_api.py, supabase/migrations/20260602_marketplace.sql, tests/test_marketplace_api.py, docs/marketplace.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 121 — Fencer photo dedup via facial recognition

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `dedupe_headshots.py`, `supabase/migrations/20260602_headshot_dedup.sql`, `tests/test_dedupe_headshots.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing headshot/media storage pipeline if present; privacy-sensitive media handling is mandatory.

**Task:**
1. Implement image hash and metadata-based dedup first; add face embedding only behind an optional dependency/config flag.
2. Create a review table for candidate duplicates rather than auto-merging identities or deleting images.
3. Handle corrupt/non-image files, missing images, and identical URLs.
4. Keep all outputs auditable with confidence score and source image IDs.
5. Document privacy limitations and manual-review workflow.

**Tests:**
- Perceptual/hash dedup tests.
- Corrupt image tests.
- No-auto-delete/no-auto-merge tests.
- Optional embedding provider mocked test.

**Success criteria:**
- Duplicates are flagged for review, not destructively merged.
- Tests pass and privacy risks are documented.

**When blocked:**
- If face-recognition dependency is unavailable, implement hash-only candidate detection and document optional extension.

**Output format:**
```
Files: dedupe_headshots.py, supabase/migrations/20260602_headshot_dedup.sql, tests/test_dedupe_headshots.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 122 — Competition PDF results to structured data OCR pipeline

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `ocr_results.py`, `tests/test_ocr_results.py`, `docs/ocr_results.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing PDF-based scrapers and result upsert patterns.

**Task:**
1. Build a pipeline that accepts PDF bytes/path, extracts text/tables with available libraries, and falls back to OCR only if configured.
2. Normalize extracted rows into tournament/event/result candidates without writing directly by default.
3. Add confidence scores and manual-review output for low-confidence rows.
4. Handle multi-page PDFs, rotated pages, scanned pages, malformed files, and duplicate rows.
5. Document optional OCR dependencies and safe dry-run workflow.

**Tests:**
- Fixture PDF extraction tests.
- Low-confidence/manual-review tests.
- Malformed PDF test.
- No-write dry-run test.

**Success criteria:**
- Pipeline produces structured candidates with confidence and does not silently write bad rows.
- Tests pass.

**When blocked:**
- Ask before installing OCR engines or running large OCR jobs.

**Output format:**
```
Files: ocr_results.py, tests/test_ocr_results.py, docs/ocr_results.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 123 — Mobile push notification service for live results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `push_notifications.py`, `supabase/migrations/20260602_push_notifications.sql`, `tests/test_push_notifications.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 108 and existing live result state.

**Task:**
1. Create device/subscription and delivery-log tables with opt-in and disabled flags.
2. Implement provider abstraction for APNs/FCM with dry-run default.
3. Detect live result changes and format compact push payloads without duplicate sends.
4. Validate subscription ownership and avoid leaking private data in payloads.
5. Add rate limiting and retry/backoff for provider failures.

**Tests:**
- Migration tests.
- Dry-run provider tests.
- Duplicate suppression tests.
- Payload privacy tests.

**Success criteria:**
- Push service is opt-in, idempotent, and dry-run safe.
- Tests pass.

**When blocked:**
- If mobile provider credentials are missing, keep dry-run mode and document required setup.

**Output format:**
```
Files: push_notifications.py, supabase/migrations/20260602_push_notifications.sql, tests/test_push_notifications.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 124 — Fencer comparison tool side-by-side career stats

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/FencerComparisonTool.tsx`, `frontend/lib/fencerComparison.ts`, `frontend/tests/fencer-comparison-tool.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 23, 24, 76-90 analytics, and frontend Agent 106 if present.

**Task:**
1. Build a reusable comparison component that accepts two fencer IDs or typed fencer stat objects.
2. Compare career stats, medals, rankings, Elo, H2H, weapons, and recent form when data exists.
3. Handle missing analytics gracefully with placeholder rows, not crashes.
4. Add URL/deep-link state only if frontend routing exists.
5. Keep API reads public and do not expose service credentials.

**Tests:**
- Comparison normalization tests.
- Component tests for full/missing/empty stats.
- Same-fencer and missing-fencer tests.

**Success criteria:**
- Comparison tool renders meaningful side-by-side stats and handles missing data.
- Tests pass.

**When blocked:**
- If frontend app is absent, implement component/library/tests only.

**Output format:**
```
Files: frontend/components/FencerComparisonTool.tsx, frontend/lib/fencerComparison.ts, frontend/tests/fencer-comparison-tool.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 125 — Who's hot trending fencers weekly leaderboard

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_trending_fencers.py`, `supabase/migrations/20260602_trending_fencers.sql`, `tests/test_trending_fencers.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Results, rankings, Elo/form analytics, and scraper_state.

**Task:**
1. Design weekly leaderboard table with fencer_id, week_start, score, rank_delta, recent_results_score, social_score, reasons, updated_at.
2. Compute trends from recent competition performance, rank movement, medals/upsets, and optional social mentions without over-weighting missing social data.
3. Make scoring deterministic and explainable through reason fields.
4. Use identity grouping and skip fencers with insufficient data rather than inventing scores.
5. Add idempotent weekly upsert behavior.

**Tests:**
- Scoring tests for rank jumps, medals, missing social data, and tie-breaking.
- Migration tests.
- Idempotent upsert payload test.

**Success criteria:**
- Weekly leaderboard is deterministic, explainable, and tested.
- No private/social credentials are required for core scoring.

**When blocked:**
- If social data is absent, compute performance-only leaderboard and document missing input.

**Output format:**
```
Files: compute_trending_fencers.py, supabase/migrations/20260602_trending_fencers.sql, tests/test_trending_fencers.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 126 — Fencer social leaderboard most followed and most mentioned

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_social_leaderboard.py`, `supabase/migrations/20260602_social_leaderboard.sql`, `tests/test_social_leaderboard.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 21, 22, and 139-142 if available.

**Task:**
1. Aggregate social handles, follower counts, mention counts, source platform, and collection date into a leaderboard table.
2. Normalize platform names and avoid double-counting the same handle/source.
3. Keep missing/private accounts out of rankings unless publicly verified.
4. Add stale-data indicators so old follower counts are not presented as current.
5. Use dry-run/mocked providers by default for tests.

**Tests:**
- Dedup/normalization tests.
- Stale-data tests.
- Ranking tie-break tests.
- Missing provider tests.

**Success criteria:**
- Leaderboard uses public data, dedupes handles, and labels stale counts.
- Tests pass.

**When blocked:**
- If social APIs are blocked, compute from existing stored social media rows only.

**Output format:**
```
Files: compute_social_leaderboard.py, supabase/migrations/20260602_social_leaderboard.sql, tests/test_social_leaderboard.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 127 — Competition countdown and calendar view

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/components/CompetitionCalendar.tsx`, `frontend/lib/competitionCalendar.ts`, `frontend/tests/competition-calendar.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 115 and frontend Agent 106 if present.

**Task:**
1. Build a calendar/countdown component from tournament dates, country, weapon, category, and status.
2. Handle timezone/date-only events correctly and avoid negative countdown bugs for active/past events.
3. Add filters by weapon/category/country and empty/error states.
4. Expose ICS links from Agent 115 when available.
5. Keep component responsive for mobile and dense desktop scanning.

**Tests:**
- Date/timezone normalization tests.
- Component render tests for upcoming/active/past events.
- Filter tests.

**Success criteria:**
- Calendar view accurately represents upcoming/active/past competitions.
- Tests pass.

**When blocked:**
- If frontend app is absent, implement component/library/tests only.

**Output format:**
```
Files: frontend/components/CompetitionCalendar.tsx, frontend/lib/competitionCalendar.ts, frontend/tests/competition-calendar.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 128 — Federation overview pages with depth charts

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/pages/federations/[code].tsx`, `frontend/components/FederationOverview.tsx`, `frontend/tests/federation-overview.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Federation ranking scrapers, country analytics, and frontend Agent 106.

**Task:**
1. Build federation overview page showing top fencers, depth metrics, medals, clubs, rankings, and recent tournaments.
2. Use country/federation code mapping from the shared country-code source of truth.
3. Add charts for top-16/32/64 depth and weapon/gender splits with table fallback.
4. Handle federations with sparse/no national ranking data.
5. Never expose internal scraper metadata or service keys.

**Tests:**
- Country-code mapping tests.
- Component tests for complete/sparse/empty federation data.
- Chart/table fallback tests.

**Success criteria:**
- Federation pages render analytics and handle sparse data safely.
- Tests pass.

**When blocked:**
- If frontend routing differs, implement reusable page/component under current conventions.

**Output format:**
```
Files: frontend/pages/federations/[code].tsx, frontend/components/FederationOverview.tsx, frontend/tests/federation-overview.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 129 — News aggregator frontend with filtering by fencer

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `frontend/pages/news.tsx`, `frontend/components/NewsFeed.tsx`, `frontend/tests/news-feed.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 98, 104, 117, 142 where available, plus frontend Agent 106.

**Task:**
1. Build news feed page with filters for category, fencer, source, date range, and search text.
2. Display article title, source, date, summary, related fencers, and category badges.
3. Handle missing summaries, broken source URLs, and empty filters.
4. Use safe outbound links and avoid rendering untrusted HTML directly.
5. Add loading/error/empty states and pagination.

**Tests:**
- XSS-safe rendering test for article summary/title.
- Filter/pagination tests.
- Empty/error state tests.

**Success criteria:**
- News feed is safe, filterable, and tested.
- No raw HTML is injected into the page.

**When blocked:**
- If news API is absent, use typed fixtures and document required endpoint.

**Output format:**
```
Files: frontend/pages/news.tsx, frontend/components/NewsFeed.tsx, frontend/tests/news-feed.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 130 — Athlete quiz / trivia feature from career data

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_trivia.py`, `frontend/components/AthleteQuiz.tsx`, `tests/test_trivia.py`, `frontend/tests/athlete-quiz.test.tsx`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Career stats, milestones, medals, and frontend Agent 106 if present.

**Task:**
1. Generate trivia question candidates from verified career stats, medals, milestones, countries, and weapons.
2. Create deterministic question templates with answer/options and source metadata for fact checking.
3. Filter out sensitive/private biographical data and avoid questions about minors unless data is public and non-sensitive.
4. Build optional quiz component with answer reveal, score state, and empty state.
5. Store/generated questions only if a migration/table already exists or add a migration when needed.

**Tests:**
- Question generation tests for deterministic answers and distractors.
- Sensitive-data filter tests.
- Component tests for answer flow if frontend is implemented.

**Success criteria:**
- Trivia questions are fact-backed, deterministic, and safe.
- Tests pass.

**When blocked:**
- If frontend app is absent, implement generator/tests and document component requirements.

**Output format:**
```
Files: compute_trivia.py, frontend/components/AthleteQuiz.tsx, tests/test_trivia.py, frontend/tests/athlete-quiz.test.tsx
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## MARKETPLACE / SOCIAL (15 agents)

---

## Agent 131 — Absolute Fencing product catalog scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_absolutefencing.py`, `supabase/migrations/20260602_products.sql`, `tests/test_scrape_absolutefencing.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** No prior product agent. This agent creates or verifies the shared `fs_products` schema for Agents 132-136.

**Task:**
1. Probe `absolute-fencing.com` catalog/search/category pages and identify product listing/detail structure.
2. Create or reuse `fs_products` table with source, source_id, name, brand, category, weapon, price, currency, image_url, product_url, stock_status, metadata, scraped_at.
3. Scrape product list and detail pages with rate limiting, robots-aware delays, and graceful 404 handling.
4. Normalize weapon/category/price/stock fields and dedupe by `source, source_id`.
5. Use `ScraperRunLogger` and `scraper_state` for incremental runs.

**Tests:**
- Migration/table-shape tests.
- Listing/detail fixture parser tests.
- Price/stock normalization tests.
- No-credentials/no-network dry-run tests.

**Success criteria:**
- Absolute Fencing products parse and upsert idempotently.
- Tests pass.

**When blocked:**
- If the site blocks requests, create a stub with probe evidence and parser tests from captured/realistic fixtures.

**Output format:**
```
Files: scrape_absolutefencing.py, supabase/migrations/20260602_products.sql, tests/test_scrape_absolutefencing.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 132 — Leon Paul product catalog scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_leonpaul.py`, `tests/test_scrape_leonpaul.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 131 `fs_products` table or migration equivalent.

**Task:**
1. Probe `leonpaul.com` category/list/detail pages and identify variants such as size/color options.
2. Reuse `fs_products` schema and write source `leon_paul` rows.
3. Parse name, product ID/SKU, category, weapon, price, currency, image, product URL, stock/availability, and variant metadata.
4. Handle multi-currency/region redirects without crashing.
5. Use rate limiting, scraper state, and run logging.

**Tests:**
- Fixture tests for listing/detail/variant parsing.
- Currency/price normalization tests.
- Idempotent upsert payload test.

**Success criteria:**
- Leon Paul products parse into shared product schema.
- Tests pass.

**When blocked:**
- If region redirect blocks prices, store product metadata and log missing price reason.

**Output format:**
```
Files: scrape_leonpaul.py, tests/test_scrape_leonpaul.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 133 — Allstar/Uhlmann product catalog scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_allstar_uhlmann.py`, `tests/test_scrape_allstar_uhlmann.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 131 product schema.

**Task:**
1. Probe Allstar and Uhlmann public catalog pages for product listings and detail URLs.
2. Scrape product names, SKU/source ID, brand, category, weapon, price if public, images, and product URL.
3. Keep brand separation clear even if both brands share one storefront/platform.
4. Normalize German/English category labels and EUR currency values.
5. Use rate limiting, run logging, and state tracking.

**Tests:**
- Allstar fixture parser test.
- Uhlmann fixture parser test.
- German category/currency normalization tests.
- Blocked/no-price test.

**Success criteria:**
- Allstar and Uhlmann product data imports into shared schema safely.
- Tests pass.

**When blocked:**
- If prices require login, store public catalog fields and document missing price.

**Output format:**
```
Files: scrape_allstar_uhlmann.py, tests/test_scrape_allstar_uhlmann.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 134 — Fencing.net product scraper + reviews

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fencingnet_products.py`, `tests/test_scrape_fencingnet_products.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 131 product schema and any existing reviews schema if present.

**Task:**
1. Probe Fencing.net product/review pages and identify whether content is current and public.
2. Scrape product names, brand/category, review rating/count/text snippets, review date, and source URL.
3. Store product rows in `fs_products` and review rows in `fs_equipment_reviews` or metadata when review table exists.
4. Handle forum-style pages and avoid scraping private/user-only content.
5. Dedupe reviews by stable source URL/hash.

**Tests:**
- Product/review fixture tests.
- Private/login-only page test.
- Review dedupe/hash test.

**Success criteria:**
- Public Fencing.net product/review data parses without private content leakage.
- Tests pass.

**When blocked:**
- If Fencing.net has no current public product catalog, produce a documented stub plus parser tests for available public pages.

**Output format:**
```
Files: scrape_fencingnet_products.py, tests/test_scrape_fencingnet_products.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 135 — PBT Fencing product scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_pbt_products.py`, `tests/test_scrape_pbt_products.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 131 product schema.

**Task:**
1. Probe `pbtfencing.com` catalog pages and product detail pages.
2. Parse product name, SKU, category, weapon, price/currency, images, URL, stock status, and size metadata.
3. Normalize multilingual labels and prices.
4. Upsert rows with source `pbt` and stable source IDs.
5. Use rate limiting, run logging, state, and graceful blocked handling.

**Tests:**
- Listing/detail parser tests.
- Variant/size metadata test.
- Price normalization test.

**Success criteria:**
- PBT product catalog imports into shared product schema.
- Tests pass.

**When blocked:**
- If site blocks automated access, write stub with probe evidence and fixture parser tests.

**Output format:**
```
Files: scrape_pbt_products.py, tests/test_scrape_pbt_products.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 136 — Blue Gauntlet product scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_blue_gauntlet_products.py`, `tests/test_scrape_blue_gauntlet_products.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 131 product schema.

**Task:**
1. Probe `blue-gauntlet.com` catalog/list/detail pages.
2. Parse product name, SKU, category, weapon, price/currency, description, image URL, stock status, and product URL.
3. Handle sale prices and out-of-stock labels consistently.
4. Upsert by source `blue_gauntlet` and stable SKU/source ID.
5. Use rate limiting, run logging, and state tracking.

**Tests:**
- Listing/detail fixture tests.
- Sale/out-of-stock normalization tests.
- Idempotent upsert test.

**Success criteria:**
- Blue Gauntlet products import safely into shared product schema.
- Tests pass.

**When blocked:**
- If access is blocked, document probes and keep tests around realistic fixtures.

**Output format:**
```
Files: scrape_blue_gauntlet_products.py, tests/test_scrape_blue_gauntlet_products.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 137 — Fencing store directory physical stores worldwide

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fencing_stores.py`, `supabase/migrations/20260602_fencing_stores.sql`, `tests/test_fencing_stores.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Product/vendor sources from Agents 131-136.

**Task:**
1. Create `fs_fencing_stores` table with name, brand/source, website, city, country, address, lat/lon, contact fields, source_url, metadata, scraped_at.
2. Collect public store/dealer locations from manufacturer dealer pages and retailer store pages.
3. Geocode only when a geocoder key/service is configured; default to storing address without coordinates.
4. Dedupe by normalized name+address+country.
5. Use rate limiting and log missing/ambiguous location data.

**Tests:**
- Migration tests.
- Dealer-list parser tests.
- Address normalization/dedupe tests.
- No-geocoder fallback test.

**Success criteria:**
- Store directory imports public store/dealer locations without requiring geocoding.
- Tests pass.

**When blocked:**
- If dealer lists are JS-rendered, probe XHR endpoints before stubbing.

**Output format:**
```
Files: scrape_fencing_stores.py, supabase/migrations/20260602_fencing_stores.sql, tests/test_fencing_stores.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 138 — Fencing club review scraper from Google Maps

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_google_club_reviews.py`, `tests/test_google_club_reviews.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 95 club enrichment if available and approved Google Maps API access.

**Task:**
1. Use Google Places/Maps API only if `MAPS_API_KEY` is set; do not scrape Google Maps HTML.
2. Load club names/locations from `fs_club_reviews`, `fs_club_rankings`, or `fs_fencers` club fields.
3. Fetch rating, review count, place ID, URL, and selected public metadata with rate limits.
4. Store source-specific rows without overwriting other review sources.
5. Log no-key/no-match cases clearly and exit 0.

**Tests:**
- No-key behavior test.
- Google API response parser test.
- Dedupe/upsert test.
- Ambiguous place match test.

**Success criteria:**
- Google club review enrichment is API-only, safe without a key, and tested.
- No HTML scraping of Google Maps is introduced.

**When blocked:**
- If no API key exists, implement dry-run/no-key path and document required env var.

**Output format:**
```
Files: scrape_google_club_reviews.py, tests/test_google_club_reviews.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 139 — YouTube fencing video indexer

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_youtube_videos.py`, `supabase/migrations/20260602_fencing_videos.sql`, `tests/test_youtube_videos.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** YouTube Data API access if available and existing media/storage conventions.

**Task:**
1. Create `fs_fencing_videos` table with platform, video_id, title, channel, published_at, url, related_fencer_ids, tournament_id, tags, metadata, scraped_at.
2. Use YouTube Data API only when `YOUTUBE_API_KEY` is set; default to dry-run/mocked parser tests.
3. Search by tournament/fencer names and classify likely match videos vs general content.
4. Dedupe by video ID and avoid storing private/unlisted assumptions.
5. Extract related fencers by safe name matching and log ambiguity.

**Tests:**
- API response parser tests.
- Classification tests.
- Fencer matching ambiguity tests.
- No-key dry-run test.

**Success criteria:**
- Video indexer stores public video metadata and handles missing API key safely.
- Tests pass.

**When blocked:**
- If API quota/key is unavailable, keep dry-run and document.

**Output format:**
```
Files: scrape_youtube_videos.py, supabase/migrations/20260602_fencing_videos.sql, tests/test_youtube_videos.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 140 — Instagram fencing content aggregator

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_instagram_fencing.py`, `tests/test_instagram_fencing.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 21, 22, 126 and public Instagram API/provider availability.

**Task:**
1. Use approved API/provider access only; do not scrape private or login-gated Instagram pages.
2. Collect public post/account metadata for known public fencer/federation handles when credentials are configured.
3. Normalize platform, handle, post URL, timestamp, caption snippet, mention tags, and related fencer IDs.
4. Default to no-key dry-run mode with mocked fixtures.
5. Respect rate limits and do not store sensitive personal data.

**Tests:**
- No-key behavior test.
- API fixture parser test.
- Mention/fencer match test.
- Private/login-only skip test.

**Success criteria:**
- Aggregator is API-only/dry-run safe and stores only public metadata.
- Tests pass.

**When blocked:**
- If no approved API exists, implement a stub with clear limitation and fixture tests.

**Output format:**
```
Files: scrape_instagram_fencing.py, tests/test_instagram_fencing.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 141 — TikTok fencing content aggregator

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_tiktok_fencing.py`, `tests/test_tiktok_fencing.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 21, 22, 126 and public TikTok API/provider availability.

**Task:**
1. Use approved API/provider access only; do not bypass login or scrape private content.
2. Collect public video metadata for known fencer/federation hashtags/handles when credentials are configured.
3. Normalize platform, video ID, URL, creator, caption snippet, posted date, metrics if public, and related fencers.
4. Default to no-key dry-run mode with mocked fixtures.
5. Add rate limiting and provider error handling.

**Tests:**
- No-key behavior test.
- API fixture parser test.
- Hashtag/fencer match test.
- Provider error test.

**Success criteria:**
- Aggregator stores public TikTok metadata safely and is tested.
- No private/login-gated scraping.

**When blocked:**
- If API access is unavailable, ship dry-run stub plus parser tests.

**Output format:**
```
Files: scrape_tiktok_fencing.py, tests/test_tiktok_fencing.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 142 — Forum scraper fencing.net and reddit r/fencing discussions

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fencing_forums.py`, `supabase/migrations/20260602_forum_discussions.sql`, `tests/test_fencing_forums.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** News/social tables and public forum access.

**Task:**
1. Create `fs_forum_discussions` with source, thread_id, title, url, author_hash, posted_at, tags, related_fencer_ids, summary, metadata, scraped_at.
2. Use Reddit API when credentials exist; otherwise parse public RSS/JSON only if allowed. Do not scrape private/user-only content.
3. Probe Fencing.net public forum/thread structure and respect robots/rate limits.
4. Hash or omit usernames unless they are official/public accounts; avoid storing unnecessary personal data.
5. Match fencer names conservatively and log ambiguous matches.

**Tests:**
- Forum thread fixture parser tests.
- Reddit API/no-key tests.
- PII minimization tests.
- Fencer-match ambiguity tests.

**Success criteria:**
- Forum aggregator stores public discussion metadata with privacy safeguards.
- Tests pass.

**When blocked:**
- If a forum blocks access, stub that source with documented probe evidence.

**Output format:**
```
Files: scrape_fencing_forums.py, supabase/migrations/20260602_forum_discussions.sql, tests/test_fencing_forums.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 143 — Fencing event photographer directory

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_photographer_directory.py`, `supabase/migrations/20260602_photographers.sql`, `tests/test_photographer_directory.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Tournament/media sources.

**Task:**
1. Create `fs_event_photographers` table with name/business, website, email/public contact, regions, event_urls, source_url, metadata, scraped_at.
2. Probe federation event pages, tournament galleries, and public photographer directories for fencing-event photographers.
3. Only store public business/contact information; do not infer private personal data.
4. Dedupe by normalized business/name+website/contact.
5. Link photographers to tournaments when source pages clearly identify an event.

**Tests:**
- Directory/gallery parser tests.
- Public-contact filtering tests.
- Dedupe tests.
- Tournament linking test.

**Success criteria:**
- Directory stores public photographer business info and event links safely.
- Tests pass.

**When blocked:**
- If sources are sparse, implement parser + known public source list and document coverage limits.

**Output format:**
```
Files: scrape_photographer_directory.py, supabase/migrations/20260602_photographers.sql, tests/test_photographer_directory.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 144 — Fencing equipment second-hand marketplace scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_secondhand_equipment.py`, `supabase/migrations/20260602_secondhand_equipment.sql`, `tests/test_secondhand_equipment.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Equipment/product categories and public marketplace sources.

**Task:**
1. Create `fs_secondhand_equipment` with source, listing_id, title, category, weapon, price, currency, location, listing_url, posted_at, status, metadata, scraped_at.
2. Probe only public marketplace/search pages that allow access; do not bypass login or anti-bot protections.
3. Parse listing metadata without storing seller personal data beyond public display name hash/source ID if needed.
4. Dedupe by source/listing_id or URL hash.
5. Classify weapon/equipment category from title/description conservatively.

**Tests:**
- Listing parser tests.
- Category classification tests.
- PII minimization tests.
- Dedupe/upsert tests.

**Success criteria:**
- Second-hand listings import public metadata safely and idempotently.
- Tests pass.

**When blocked:**
- If sources are login-only, create a documented stub and no private scraping.

**Output format:**
```
Files: scrape_secondhand_equipment.py, supabase/migrations/20260602_secondhand_equipment.sql, tests/test_secondhand_equipment.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 145 — Fencing camp review aggregator

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_camp_reviews.py`, `supabase/migrations/20260602_camp_reviews.sql`, `tests/test_camp_reviews.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Existing training camp directory/table if present; otherwise create only review-specific storage in this agent.

**Task:**
1. Create `fs_training_camp_reviews` with camp_id/name, source, rating, review_count, review_text_snippet, reviewer_hash, source_url, metadata, scraped_at.
2. Collect public reviews from camp pages, club pages, and approved review APIs; avoid login-only/private content.
3. Match reviews to camps by name+organizer+date/location with ambiguity logging.
4. Dedupe by source URL/hash and avoid overwriting camp directory data.
5. Use rate limiting and no-key dry-run behavior for review APIs.

**Tests:**
- Review parser tests.
- Camp matching ambiguity tests.
- PII minimization tests.
- Dedupe tests.

**Success criteria:**
- Camp reviews aggregate into separate review table and preserve camp directory rows.
- Tests pass.

**When blocked:**
- If review sources are unavailable, implement stub with parser tests and documented source gaps.

**Output format:**
```
Files: scrape_camp_reviews.py, supabase/migrations/20260602_camp_reviews.sql, tests/test_camp_reviews.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## ADVANCED / EXPERIMENTAL (14 agents)

---

## Agent 146 — Match video auto-trimmer find fencer from YouTube video

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `video_trimmer.py`, `tests/test_video_trimmer.py`, `docs/video_trimmer.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 139 video index and optional local video tooling.

**Task:**
1. Implement a metadata-first auto-trim planner that identifies likely fencer/tournament segments from title, description, chapters, and known bout timestamps.
2. Do not download or process large videos by default; require explicit local file/path input for actual trimming.
3. Generate trim candidates with start/end times, confidence, related fencer IDs, and reason fields.
4. Use ffmpeg only if available and only on local files; otherwise output planned commands without executing.
5. Document limitations and manual review requirement.

**Tests:**
- Metadata/chapter parsing tests.
- Candidate confidence tests.
- No-video/no-ffmpeg dry-run tests.
- Local trim command construction test.

**Success criteria:**
- Tool produces auditable trim candidates and does not download/process videos unexpectedly.
- Tests pass.

**When blocked:**
- If ffmpeg is unavailable, keep dry-run planner and document requirement.

**Output format:**
```
Files: video_trimmer.py, tests/test_video_trimmer.py, docs/video_trimmer.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 147 — Live scoring overlay for streamers OBS plugin data

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `obs_overlay_server.py`, `frontend/obs-overlay/`, `tests/test_obs_overlay_server.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 108 and existing live result watcher/data. Do not depend on v1 Agent 35 numbering.

**Task:**
1. Build a lightweight read-only overlay data endpoint for active tournament scores and bout status.
2. Create minimal OBS browser-source overlay HTML/CSS/JS under `frontend/obs-overlay/` with no private credentials.
3. Support tournament/event selection through query params or config token with validation.
4. Handle disconnected/no-active-event states visibly and safely.
5. Add rate limiting/cache headers to avoid hammering Supabase.

**Tests:**
- Endpoint tests for active/no-active/error states.
- Overlay HTML smoke test.
- Query-param validation tests.

**Success criteria:**
- OBS overlay can display live scores from public/live data safely.
- Tests pass.

**When blocked:**
- If live data source is unavailable, implement mocked overlay and document required endpoint.

**Output format:**
```
Files: obs_overlay_server.py, frontend/obs-overlay/, tests/test_obs_overlay_server.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 148 — Fencing fantasy league with draft and weekly scoring

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `fantasy_league.py`, `supabase/migrations/20260602_fantasy_league.sql`, `tests/test_fantasy_league.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Results, rankings, and user/auth system if present.

**Task:**
1. Design tables for fantasy leagues, teams, rosters, draft picks, scoring periods, and weekly scores.
2. Implement scoring rules based on verified competition results, medals, upset bonuses, and participation.
3. Keep user/auth integration optional; do not invent auth if none exists.
4. Validate roster constraints, duplicate picks, locked periods, and scoring idempotency.
5. Document game rules and admin/manual setup steps.

**Tests:**
- Migration tests.
- Draft/roster validation tests.
- Weekly scoring tests.
- Idempotency tests.

**Success criteria:**
- Fantasy league data model and scoring engine are deterministic and tested.
- No production user writes without existing auth integration.

**When blocked:**
- If user/auth layer is absent, implement backend scoring/model only and document frontend/auth prerequisites.

**Output format:**
```
Files: fantasy_league.py, supabase/migrations/20260602_fantasy_league.sql, tests/test_fantasy_league.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 149 — Historical tournament re-simulator Monte Carlo based on Elo

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `simulate_tournament.py`, `tests/test_simulate_tournament.py`, `docs/tournament_simulation.md`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 76 Elo ratings and tournament/result data.

**Task:**
1. Implement deterministic seeded Monte Carlo simulation from entrants, Elo ratings, format, and bracket/pool data where available.
2. Support simulation modes for DE bracket, simple standings, and partial-data fallback.
3. Return probability distributions for winner/medal/top8 without rewriting historical results.
4. Expose CLI args for tournament ID, seed, iterations, and output JSON.
5. Document assumptions and limitations clearly.

**Tests:**
- Seed determinism tests.
- Probability normalization tests.
- Known small bracket simulation tests.
- Missing Elo fallback tests.

**Success criteria:**
- Simulator produces reproducible probability outputs and never mutates source results.
- Tests pass.

**When blocked:**
- If tournament format data is missing, support documented fallback and flag lower confidence.

**Output format:**
```
Files: simulate_tournament.py, tests/test_simulate_tournament.py, docs/tournament_simulation.md
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 150 — Fencer form tracker last 5 competitions trend

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_form_tracker.py`, `supabase/migrations/20260602_form_tracker.sql`, `tests/test_form_tracker.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Results/rankings/Elo analytics.

**Task:**
1. Create `fs_fencer_form` with fencer_id, weapon, last_competitions, form_score, trend_direction, recent_medals, recent_avg_rank, updated_at.
2. Compute form from the last 5 eligible competitions per fencer/weapon with deterministic weighting.
3. Handle fewer than 5 competitions, missing ranks, and mixed categories.
4. Use identity grouping and avoid double-counting team/duplicate results.
5. Upsert idempotently and explain score components in metadata.

**Tests:**
- Scoring tests for improving/declining/stable form.
- Fewer-than-5 and NULL-rank tests.
- Idempotent upsert test.

**Success criteria:**
- Form tracker computes explainable recent-form metrics safely.
- Tests pass.

**When blocked:**
- If identity table is absent, use fencer_id and document grouping limitation.

**Output format:**
```
Files: compute_form_tracker.py, supabase/migrations/20260602_form_tracker.sql, tests/test_form_tracker.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 151 — Betting odds aggregator for upcoming competitions

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_betting_odds.py`, `supabase/migrations/20260602_betting_odds.sql`, `tests/test_betting_odds.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Upcoming tournaments and legal/compliance review.

**Task:**
1. Create `fs_betting_odds` for source, tournament_id, market_type, participant, odds_decimal, implied_probability, region, source_url, scraped_at, metadata.
2. Probe only public odds sources that legally permit access; do not bypass geo/login restrictions.
3. Store odds as informational data only; do not generate betting advice or recommendations.
4. Add region/source disclaimers in metadata and docs.
5. Handle missing/withdrawn markets and stale odds explicitly.

**Tests:**
- Odds parser tests.
- Decimal/implied probability conversion tests.
- No-advice output tests.
- Blocked/login-only source test.

**Success criteria:**
- Aggregator stores public odds data safely with compliance caveats.
- Tests pass.

**When blocked:**
- If sources are restricted or legally unclear, produce a documented stub and do not scrape.

**Output format:**
```
Files: scrape_betting_odds.py, supabase/migrations/20260602_betting_odds.sql, tests/test_betting_odds.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 152 — Youth talent identification early-career outlier detection

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_youth_talent.py`, `supabase/migrations/20260602_youth_talent.sql`, `tests/test_youth_talent.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Youth/junior results, rankings, and privacy safeguards for minors.

**Task:**
1. Create an analytics table with fencer_id, age_band or category, feature summary, outlier_score, explanation, updated_at; avoid exposing sensitive birthdate details unnecessarily.
2. Compute outlier scores from public competition/ranking results, not private attributes.
3. Use conservative labels such as “early-career outlier” rather than deterministic future predictions.
4. Handle sparse data and age/category uncertainty with low-confidence flags.
5. Document privacy and interpretation limits.

**Tests:**
- Scoring tests for known feature patterns.
- Sparse/unknown-age tests.
- No-sensitive-output tests.
- Explanation field tests.

**Success criteria:**
- Youth analytics are privacy-conscious, explainable, and non-deterministic.
- Tests pass.

**When blocked:**
- If birth dates/ages are missing, compute category-based features only and document limits.

**Output format:**
```
Files: compute_youth_talent.py, supabase/migrations/20260602_youth_talent.sql, tests/test_youth_talent.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 153 — Fencer transfer market value estimator

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_transfer_value.py`, `supabase/migrations/20260602_transfer_value.sql`, `tests/test_transfer_value.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 26, 76, 77, 90, 100, and 150 where available.

**Task:**
1. Create an internal analytics table with fencer_id, season, value_score, score_components, confidence, updated_at.
2. Compute score from public performance/ranking/age/category/form signals with transparent components.
3. Name outputs as “value_score” or “transfer impact score,” not monetary personal worth unless explicitly justified.
4. Handle missing data with confidence penalties and no fabricated values.
5. Document ethical/product limitations.

**Tests:**
- Component scoring tests.
- Missing data confidence tests.
- No-fabricated-values tests.
- Idempotent upsert test.

**Success criteria:**
- Estimator produces transparent non-monetary scores with confidence and limitations.
- Tests pass.

**When blocked:**
- If data is too sparse, output low-confidence/no-score rows instead of inventing values.

**Output format:**
```
Files: compute_transfer_value.py, supabase/migrations/20260602_transfer_value.sql, tests/test_transfer_value.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 154 — Equipment durability tracker how often top fencers replace gear

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_equipment_durability.py`, `supabase/migrations/20260602_equipment_durability.sql`, `tests/test_equipment_durability.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 99, 102, and 131-136 equipment/product data.

**Task:**
1. Create table for brand/equipment_type/fencer_id, observed_first_date, observed_last_date, replacement_interval_estimate, evidence_count, confidence, metadata.
2. Derive durability only from public equipment mentions, sponsor changes, product review data, and explicitly dated observations.
3. Do not claim actual private replacement behavior without evidence; label estimates clearly.
4. Aggregate by brand/equipment type when fencer-level evidence is weak.
5. Add confidence scoring and evidence links.

**Tests:**
- Evidence aggregation tests.
- Confidence/insufficient-data tests.
- Brand/equipment normalization tests.

**Success criteria:**
- Durability tracker outputs evidence-backed estimates with confidence labels.
- Tests pass.

**When blocked:**
- If dated equipment evidence is sparse, produce aggregate low-confidence summaries only.

**Output format:**
```
Files: compute_equipment_durability.py, supabase/migrations/20260602_equipment_durability.sql, tests/test_equipment_durability.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 155 — Fencing gym / training facility directory worldwide

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_training_facilities.py`, `supabase/migrations/20260602_training_facilities.sql`, `tests/test_training_facilities.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Club/store/camp directories and public federation pages.

**Task:**
1. Create `fs_training_facilities` with name, type, address, city, country, website, contact_public, weapons, programs, lat/lon, source_url, metadata, scraped_at.
2. Probe federation club directories, public facility pages, and existing club data for training locations.
3. Normalize names/addresses and dedupe by name+address+country.
4. Geocode only with configured provider; no-key mode stores address only.
5. Store only public contact/business info.

**Tests:**
- Directory parser tests.
- Address normalization/dedupe tests.
- No-geocoder fallback test.
- PII filtering test.

**Success criteria:**
- Facility directory imports public training locations safely.
- Tests pass.

**When blocked:**
- If sources are unavailable, create documented source stubs and parser tests for available pages.

**Output format:**
```
Files: scrape_training_facilities.py, supabase/migrations/20260602_training_facilities.sql, tests/test_training_facilities.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 156 — Fencer sponsorship matchmaking brand to athlete

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_sponsorship_matches.py`, `supabase/migrations/20260602_sponsorship_matches.sql`, `tests/test_sponsorship_matches.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agents 99, 126, 153, and equipment/brand/social data.

**Task:**
1. Create recommendation table with brand, fencer_id, match_score, score_components, confidence, explanation, updated_at.
2. Compute matches from public performance, geography, weapon, existing equipment/brand affinity, and public social reach.
3. Exclude minors or mark them ineligible unless explicit policy allows otherwise.
4. Do not contact athletes/brands or send outreach automatically.
5. Provide transparent explanations and confidence penalties for sparse data.

**Tests:**
- Scoring component tests.
- Minor/ineligible filtering tests.
- No-outreach side-effect tests.
- Sparse data tests.

**Success criteria:**
- Matchmaking produces explainable candidate rows without outreach side effects.
- Tests pass.

**When blocked:**
- If social/equipment data is missing, compute lower-confidence performance/geography-only matches.

**Output format:**
```
Files: compute_sponsorship_matches.py, supabase/migrations/20260602_sponsorship_matches.sql, tests/test_sponsorship_matches.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 157 — Competition travel cost estimator flights + hotels for each event

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `estimate_travel_costs.py`, `supabase/migrations/20260602_travel_costs.sql`, `tests/test_travel_costs.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Tournament venue/geocoding data and optional travel APIs.

**Task:**
1. Create `fs_travel_cost_estimates` with tournament_id, origin_country/city, destination, date_range, flight_estimate, hotel_estimate, currency, source, confidence, metadata, updated_at.
2. Use static/dry-run estimates unless approved API credentials are configured; do not scrape booking sites that prohibit it.
3. Estimate costs from public APIs or configurable mock providers with caching and rate limits.
4. Handle missing venue dates/coordinates and currency conversion carefully.
5. Document that estimates are approximate and not booking advice.

**Tests:**
- Cost calculation tests.
- Missing venue/date tests.
- Provider dry-run tests.
- Currency conversion tests.

**Success criteria:**
- Travel estimates are approximate, cached/dry-run safe, and tested.
- No live booking scrape occurs by default.

**When blocked:**
- If travel APIs are unavailable, implement deterministic mock/static provider and document required env vars.

**Output format:**
```
Files: estimate_travel_costs.py, supabase/migrations/20260602_travel_costs.sql, tests/test_travel_costs.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 158 — Fencing history timeline major rule changes and equipment evolution

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `scrape_fencing_history.py`, `supabase/migrations/20260602_fencing_history.sql`, `tests/test_fencing_history.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Agent 105 rule changes and public history sources.

**Task:**
1. Create `fs_fencing_history_events` with event_date/year, category, title, description, affected_weapons, source_url, confidence, metadata.
2. Collect rule changes, equipment changes, scoring/timing changes, and major governance milestones from public FIE/federation/history sources.
3. Parse source pages conservatively and require a citation/source URL for every timeline item.
4. Dedupe by category+date/title and preserve conflicting dates as separate evidence metadata.
5. Prepare data for frontend timeline consumption.

**Tests:**
- Migration tests.
- Parser tests for public source fixtures.
- Citation-required tests.
- Dedupe/conflicting-date tests.

**Success criteria:**
- Timeline data is cited, deduped, and safe for display.
- Tests pass.

**When blocked:**
- If sources are prose-only, store curated/cited entries with tests and document manual curation.

**Output format:**
```
Files: scrape_fencing_history.py, supabase/migrations/20260602_fencing_history.sql, tests/test_fencing_history.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## Agent 159 — AI coach technique analysis from bout data patterns

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.
Do not touch .github/workflows/ — CI integration is handled by Agent 160.

**Files:** `compute_technique_analysis.py`, `supabase/migrations/20260602_technique_analysis.sql`, `tests/test_technique_analysis.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Depends on:** Bout data, H2H, form/Elo analytics; no video/medical inference required.

**Task:**
1. Create table with fencer_id, weapon, pattern_summary, strengths, weaknesses, evidence_metrics, confidence, updated_at.
2. Derive technique-style insights from public bout/result patterns only: touch differential, pool/DE performance, comeback rate, close-bout rate, left/right if known.
3. Avoid making medical, psychological, or definitive coaching claims; label outputs as data-pattern insights.
4. Use deterministic rules/templates first; optional LLM summaries must be disabled by default and never require secrets in tests.
5. Add evidence metrics for every generated claim.

**Tests:**
- Rule-based insight tests.
- Evidence-required tests.
- Low-data confidence tests.
- No-medical/psychological claim test.

**Success criteria:**
- Technique analysis is evidence-backed, deterministic by default, and conservative.
- Tests pass.

**When blocked:**
- If bout data is sparse, emit low-confidence/no-analysis rows rather than hallucinated insights.

**Output format:**
```
Files: compute_technique_analysis.py, supabase/migrations/20260602_technique_analysis.sql, tests/test_technique_analysis.py
Implemented: yes/no
Tests: [commands and results]
Risks: [remaining risks or skipped checks]
```

---

## CI MERGE (1 agent)

---

## Agent 160 — CI merge for all 160 agents into workflow files

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
7. Fix any issues found by verification.
8. Update project memory / Wiki-Brain if this was a meaningful session.
9. Final response must include: what changed, files changed, verification run and result, remaining risks or skipped checks.

Optimize for correctness, completeness, safety, and zero regressions.
Treat this like production work. Fully understand the relevant code path, implement the fix completely, verify with the strongest safe checks, handle edge cases, update tests/docs/memory if needed, and do not stop until the task is genuinely done or a real blocker is proven.

Project root: /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
Python: .venv/bin/python
Dependencies: in requirements.txt
Tests: .venv/bin/python -m pytest tests/ -v
Run logger: from run_logger import ScraperRunLogger — use .start().complete(written, failed, skipped) or .error(str(exc))
State: from scraper_state import get_state, set_state — persists to fs_scraper_state
Supabase upsert: supabase.table("t").upsert(row, on_conflict="col").execute()
Tests-first: Write failing tests with real captured fixture data when available; otherwise use realistic fixtures based on the probed source structure before implementing.
Probe-first: For any new external site, run a probe script to confirm URL structure before writing parser code.

**IMPORTANT:** This agent is the ONLY one that touches `.github/workflows/`. Keep non-workflow edits limited to `tests/test_workflow_integrity.py`.

**Files:** `.github/workflows/scraper.yml`, `.github/workflows/live_results.yml`, `.github/workflows/weekly_analytics.yml`, `tests/test_workflow_integrity.py`

**Constraints:** Agent 160 is the only agent allowed to edit `.github/workflows/`. Keep non-workflow edits limited to `tests/test_workflow_integrity.py`; do not modify scraper, analytics, API, frontend, or migration implementation files.

**Depends on:** All other agents. This is the final integration agent.

**Task:**
1. Read current workflow files fully.
2. Integrate ALL new agent scripts into the correct workflows (scraper 6hr, live 15min, weekly analytics).
3. Group in this order:
   - Frontend data gap scripts
   - Tier-3 federation scrapers (agents 31-60)
   - More tournament scrapers (agents 61-75)
   - Deeper analytics (agents 76-90)
   - More enrichment (agents 91-105)
   - Marketplace / social scrapers (agents 131-145)
   - Advanced / experimental (agents 146-159)
4. Product/frontend layer (agents 106-130) does NOT go in CI — document separately.
5. Every scraper step: continue-on-error: true with SUPABASE_URL + SUPABASE_SERVICE_KEY env.
6. Validate each YAML.
7. Write workflow integrity tests that:
   - Parse all workflow files with PyYAML
   - Assert every new script appears in exactly one intended workflow
   - Assert discover_competition_urls appears before results scrapers
   - Assert each scraper step has continue-on-error: true
   - Assert Supabase env vars present on scraper steps

**Tests:**
- Workflow integrity tests parse all edited YAML files with PyYAML.
- Tests assert every generated scraper/analytics script is assigned to exactly one intended workflow or explicitly documented as frontend/product-only.
- Tests assert `discover_competition_urls` runs before dependent result scrapers.
- Tests assert scraper steps include `continue-on-error: true` and required Supabase env vars.
- Run `pytest tests/test_workflow_integrity.py -v`.

**Success criteria:** Three workflow files, valid YAML, all scripts integrated, workflow integrity tests pass.

**When blocked:**
- If a generated script is missing, document it under `Missing scripts` instead of inventing a workflow step.
- If workflow syntax or repository CI conventions conflict, preserve existing working CI and add the narrowest integrity test that captures the conflict.
- Do not run or deploy GitHub Actions from this agent; only edit YAML/tests and validate locally.

**Output format:**
```
Files: .github/workflows/scraper.yml, .github/workflows/live_results.yml, .github/workflows/weekly_analytics.yml, tests/test_workflow_integrity.py
YAML validation: pass/fail
Missing scripts: []
Tests: pytest tests/test_workflow_integrity.py -v
Risks: [remaining risks or skipped checks]
```
