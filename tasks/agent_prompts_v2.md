# Agent Prompts v2 -- 160 Agents (Rough Draft)

This is an expanded rough draft from the one-line descriptions in the original v2 file.
Each prompt follows the v1 template pattern. Refinement pass is needed.

---

## FRONTEND DATA GAPS (30 agents)

---

## Agent 1 -- Add bio/birth_date/birth_place columns to fs_fencers

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

1. Read current `fs_fencers` schema from existing migration files and `scraper.py`.
2. Write SQL migration:
```sql
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS bio text;
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS birth_date date;
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS birth_place text;
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS birth_country text;
```
3. Migration must be idempotent (IF NOT EXISTS).
4. Write tests verifying SQL structure and column types.
5. Do NOT modify any scraper or compute code.

**Success criteria:** Migration file with 4 idempotent ALTER TABLE statements. Tests verify SQL structure.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_bio_columns.sql, tests/test_bio_columns.py
Migration: idempotent
Tests: pytest tests/test_bio_columns.py -v
```

---

## Agent 2 -- Expand Wikipedia bio scraper to fill bio/birth_date/birth_place

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

Depends on: Agent 1 (bio columns must exist)

1. Read current `scrape_wikipedia_bios.py`. Read `scraper.py` for fs_fencers upsert pattern.
2. Extend the Wikipedia scraper to:
   - Query fencers that have NULL bio, birth_date, or birth_place
   - For each fencer, fetch Wikipedia infobox (from stored wikidata_id or by searching)
   - Parse infobox for: born/birth_date, birth_place, occupation, height, weight, nationality
   - Write a short bio from the article's lead paragraph (first 1-2 sentences)
   - UPDATE fs_fencers SET bio = ..., birth_date = ..., birth_place = ... WHERE id = ...
3. Rate limit: 2s between requests to Wikipedia API.
4. Write tests:
   - Mock Wikipedia API response with known infobox HTML
   - Test infobox parser extracts birth_date, birth_place, bio lead
   - Test missing Wikipedia page to skip gracefully
   - Test date format normalization (various formats to ISO date)

**Success criteria:** Wikipedia scraper fills bio, birth_date, birth_place for fencers with Wikipedia pages.

**Output format:**
```
Files: scrape_wikipedia_bios.py (modified), tests/test_wikipedia_bios.py (modified)
Bio fill rate: X%
Tests: pytest tests/test_wikipedia_bios.py -v
```

---

## Agent 3 -- Create fs_fencer_stats table (bout stats)

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

1. Read `fs_bouts` schema from existing migration files.
2. Write SQL migration:
```sql
CREATE TABLE IF NOT EXISTS fs_fencer_stats (
    fencer_id uuid PRIMARY KEY REFERENCES fs_fencers(id),
    total_bouts integer DEFAULT 0,
    wins integer DEFAULT 0,
    losses integer DEFAULT 0,
    win_pct numeric(5,2),
    current_win_streak integer DEFAULT 0,
    current_loss_streak integer DEFAULT 0,
    longest_win_streak integer DEFAULT 0,
    longest_loss_streak integer DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);
```
3. Write tests asserting SQL structure, PRIMARY KEY, REFERENCES, column types.

**Success criteria:** Migration creates fs_fencer_stats. Tests pass.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_stats.sql, tests/test_fencer_stats_schema.py
Tests: pytest tests/test_fencer_stats_schema.py -v
```

---

## Agent 4 -- Compute fencer bout stats from fs_bouts

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

Depends on: Agent 3 (fs_fencer_stats table)

1. Read `fs_bouts` schema. Understand that bouts have fencer_a_id, score_a, fencer_b_id, score_b.
2. Write `compute_fencer_stats.py`:
   - Query all bouts from fs_bouts where both fencer IDs are non-null
   - For each fencer: count total_bouts, wins (higher score), losses
   - Compute win_pct = wins / total_bouts * 100 (NULL if total_bouts = 0)
   - Compute current streaks: sort by date DESC, count consecutive same-outcome
   - Compute longest streak by scanning all bouts in date order
   - Upsert to fs_fencer_stats
3. Write tests with mock bout data and known outcomes.

**Success criteria:** Stats computed from bout data, streaks computed correctly.

**Output format:**
```
Files: compute_fencer_stats.py, tests/test_compute_fencer_stats.py
Fencers with stats: X
Tests: pytest tests/test_compute_fencer_stats.py -v
```

---

## Agent 5 -- Add national_rank column to fs_fencers and backfill

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

1. Write SQL migration:
```sql
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS national_rank integer;
ALTER TABLE fs_fencers ADD COLUMN IF NOT EXISTS national_rank_source text;
```
2. Write `scripts/backfill_national_rank.py`:
   - Query fs_national_fed_rankings for each fencer
   - Find latest season's rank per fencer
   - UPDATE fs_fencers SET national_rank = ... WHERE id = ...
3. Write tests: mock rankings, test latest-season selection, test missing rankings.

**Success criteria:** Migration adds columns, backfill populates them.

**Output format:**
```
Files: supabase/migrations/20260602_national_rank.sql, scripts/backfill_national_rank.py, tests/test_backfill_national_rank.py
Fencers with national_rank: X/Total
Tests: pytest tests/test_backfill_national_rank.py -v
```

---

## Agent 6 -- Add organizer/entry_deadline/format/quota columns to fs_tournaments

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

1. Read current `fs_tournaments` schema.
2. Write SQL migration adding columns idempotently:
   - organizer text, organizer_url text, entry_deadline timestamptz
   - format text, quota text, prize_money text, venue_name text, venue_address text
3. Write tests verifying SQL structure.

**Success criteria:** Migration adds 8 columns. Tests pass.

**Output format:**
```
Files: supabase/migrations/20260602_tournament_detail_columns.sql, tests/test_tournament_detail_columns.py
Tests: pytest tests/test_tournament_detail_columns.py -v
```

---

## Agent 7 -- Scrape FIE competition detail pages for organizer/format/quota/deadline

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

Depends on: Agent 6 (detail columns on fs_tournaments)

1. Probe FIE competition detail pages: https://fie.org/competitions/{year}/{fie_id}
2. Write scraper that:
   - Queries tournaments WHERE organizer IS NULL
   - Fetches FIE detail page using source_id to construct URL
   - Parses: organizer name, entry deadline, format, quota, venue, prize money
   - UPDATE fs_tournaments SET ... WHERE id = ...
3. Write tests with mocked FIE HTML.

**Success criteria:** Competition detail fields populated for FIE events.

**Output format:**
```
Files: scrape_competition_details.py, tests/test_scrape_competition_details.py
Tournaments enriched: X/Total
Tests: pytest tests/test_scrape_competition_details.py -v
```

---

## Agent 8 -- Create fs_tournament_brackets table

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

Depends on: Agent 7 (bout data in fs_bouts)

Write SQL migration creating fs_tournament_brackets with: tournament_id, weapon, category, gender, round_name, round_order, bout_order, fencer_a_id, fencer_b_id, fencer_a_name, fencer_b_name, fencer_a_seed, fencer_b_seed, score_a, score_b, winner_id, bout_id, source, metadata, created_at.

Include indexes on tournament_id and bout_id.

Write tests asserting SQL structure.

**Success criteria:** Migration creates fs_tournament_brackets with indexes.

**Output format:**
```
Files: supabase/migrations/20260602_tournament_brackets.sql, tests/test_tournament_brackets_schema.py
Tests: pytest tests/test_tournament_brackets_schema.py -v
```

---

## Agent 9 -- Build bracket data pipeline from fs_bouts into fs_tournament_brackets

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

Depends on: Agent 8 (fs_tournament_brackets table)

Write compute_brackets.py that:
- Queries fs_bouts grouped by tournament_id, weapon, category, gender
- Detects round from metadata or bout number pattern (Pools=0, T128=1, T64=2, T32=3, T16=4, QF=5, SF=6, F=7)
- Upserts to fs_tournament_brackets

Write tests with mock bout data.

**Success criteria:** Bracket data populated from bout data.

**Output format:**
```
Files: compute_brackets.py, tests/test_compute_brackets.py
Brackets built: X
Tests: pytest tests/test_compute_brackets.py -v
```

---

## Agent 10 -- Create fs_fencer_season_stats table

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

Write SQL migration:
```sql
CREATE TABLE IF NOT EXISTS fs_fencer_season_stats (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL REFERENCES fs_fencers(id),
    season text NOT NULL,
    weapon text NOT NULL,
    category text NOT NULL,
    bouts integer DEFAULT 0, wins integer DEFAULT 0, losses integer DEFAULT 0,
    win_pct numeric(5,2), avg_rank numeric(5,1), best_rank integer,
    gold integer DEFAULT 0, silver integer DEFAULT 0, bronze integer DEFAULT 0,
    total_medals integer DEFAULT 0, tournaments_entered integer DEFAULT 0,
    fie_points integer DEFAULT 0, world_rank_high integer, world_rank_low integer,
    updated_at timestamptz DEFAULT now(),
    UNIQUE(fencer_id, season, weapon, category)
);
```
Write tests asserting uniqueness constraint.

**Success criteria:** Migration creates fs_fencer_season_stats.

**Output format:**
```
Files: supabase/migrations/20260602_fencer_season_stats.sql, tests/test_fencer_season_stats_schema.py
Tests: pytest tests/test_fencer_season_stats_schema.py -v
```

---

## Agent 11 -- Compute per-season fencer stats from results + bouts

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

Depends on: Agent 10 (fs_fencer_season_stats table)

Write compute_fencer_season_stats.py:
- Query fs_results joined with fs_tournaments for season/weapon/category
- Group by fencer_id, season, weapon, category
- Compute: tournaments_entered, avg_rank, best_rank, medal counts
- Query fs_bouts for same groups: bouts, wins, losses, win_pct
- Upsert to fs_fencer_season_stats

Write tests with mock results across multiple seasons and weapons.

**Success criteria:** Season stats computed for all fencer/season/weapon combos.

**Output format:**
```
Files: compute_fencer_season_stats.py, tests/test_compute_fencer_season_stats.py
Season stats rows: X
Tests: pytest tests/test_compute_fencer_season_stats.py -v
```

---

## Agent 12 -- Create fs_career_milestones table

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

Write SQL migration creating fs_career_milestones with: fencer_id, milestone_type (CHECK constraint with types: first_podium, first_gold, first_senior_competition, first_worlds, first_olympics, category_transition, rank_breakthrough, 100_wins, 200_wins, 500_bouts, first_grand_prix, first_world_cup, world_rank_top10/50/100, defended_title, three_peat, most_medals_season, coach_change), description, date, season, tournament_id, tournament_name, rank, weapon, metadata, created_at. UNIQUE(fencer_id, milestone_type, date).

Write tests asserting SQL structure and CHECK constraint.

**Success criteria:** Migration creates fs_career_milestones.

**Output format:**
```
Files: supabase/migrations/20260602_career_milestones.sql, tests/test_career_milestones_schema.py
Tests: pytest tests/test_career_milestones_schema.py -v
```

---

## Agent 13 -- Career milestone detection engine

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

Depends on: Agent 12 (fs_career_milestones table)

Write compute_career_milestones.py:
- For each fencer, query ALL results ordered by date
- Detect: first_podium, first_gold, first_senior_competition, first_worlds, first_olympics, category_transition, first_grand_prix, first_world_cup, world_rank_top10/50/100
- For each detected milestone not already in fs_career_milestones, INSERT
- Idempotent: running twice inserts same milestones only once

Write tests with mock career progression data.

**Success criteria:** Career milestones detected for all fencers with sufficient data.

**Output format:**
```
Files: compute_career_milestones.py, tests/test_compute_career_milestones.py
Milestones detected: X
Tests: pytest tests/test_compute_career_milestones.py -v
```

---

## Agent 14 -- Create fs_country_medal_geo materialized view

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

Write SQL migration creating materialized view fs_country_medal_geo with: country, gold, silver, bronze, total, lat, lon. Join fs_results medals to fs_fencers for country. Include unique index on country and refresh function.

---

## Agent 15 -- Geocode all countries for medal heatmap

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

Write script that queries distinct countries from fs_fencers, geocodes via Nominatim (1 req/s), stores to fs_locations table (country, lat, lon, geojson). Write tests with mocked Nominatim responses.

---

## Agent 16 -- Create fs_ranking_history_trajectory table

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

Write SQL migration creating fs_ranking_trajectory: fencer_id, weapon, category, season, rank, rank_date, prev_rank, rank_change, fie_points, tournaments_attended, running_total_points, source, snapshot_id. UNIQUE(fencer_id, weapon, category, season, rank_date).

---

## Agent 17 -- Ranking sparkline data endpoint materialized view

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

Depends on: Agent 16

Write SQL migration creating v_ranking_sparklines materialized view with: fencer_id, weapon, category, rank_history (jsonb_agg), worst_rank, best_rank, rank_range. Unique index on (fencer_id, weapon, category).

---

## Agent 18 -- Unify country code data: single source of truth

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

Create fs_country_codes table (alpha3 PK, alpha2, name, region, continent, flag_emoji, olympic_code, fie_code). Populate all 206 NOCs. Write Python module with lookup functions. Search and document all hardcoded mappings in codebase.

---

## Agent 19 -- Add losses/defeats column to fs_results and backfill

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

SQL: ALTER TABLE fs_results ADD COLUMN wins/losses/total_bouts. Backfill script queries fs_bouts for each result+fencer, counts wins/losses, UPDATEs.

---

## Agent 20 -- Featured athletes algorithm

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

SQL: fs_featured_athletes (fencer_id, reason, score, category CHECK top_ranked/trending/recent_medalist/rising_star/comeback/milestone, season, weapon, active, expires_at). Compute script ranks fencers per category. Tests for each category.

---

## Agent 21 -- Fencer social follower count tracker

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

SQL: fs_social_followers (fencer_id, platform CHECK instagram/twitter/youtube/tiktok/facebook/weibo, handle, url, followers, following, posts_count, snapshot_date). Scraper attempts public profile scrapes. Stub for auth-required platforms.

---

## Agent 22 -- Social media feed real-time aggregator for #fencing

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

SQL: fs_social_feed_items (platform, platform_item_id, author_handle, content, media_urls, posted_at, url UNIQUE, fencer_ids, hashtags). Aggregator searches fencing hashtags across platforms. Document auth requirements for each platform.

---

## Agent 23 -- AI insights pipeline: fencer comparison / performance summary

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

SQL: fs_ai_insights (entity_type CHECK fencer/tournament/comparison/trend, entity_id_a, entity_id_b, insight_type, insight_text, confidence, data_sources). Template-based text generation from structured data. NOT an LLM API call.

---

## Agent 24 -- Wire H2H data into athlete page API

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

**Files:** `api/v1/fencers.py`, `tests/test_api_fencers_h2h.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 25

Add GET /v1/fencers/{id}/head-to-head endpoint querying fs_head_to_head. Return opponents with wins/losses/win%/last_meeting.

---

## Agent 25 -- Wire ranking history into athlete page trajectory chart

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

**Files:** `api/v1/fencers.py`, `tests/test_api_fencers_ranking_trajectory.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 16

Add GET /v1/fencers/{id}/ranking-trajectory endpoint. Returns chronological rank data from fs_ranking_trajectory with optional weapon/category filter.

---

## Agent 26 -- Wire win/loss stats into athlete page

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

**Files:** `api/v1/fencers.py`, `tests/test_api_fencers_stats.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 4

Add GET /v1/fencers/{id}/stats endpoint querying fs_fencer_stats. Return total_bouts, wins, losses, win_pct, streaks.

---

## Agent 27 -- Wire career milestones into athlete page timeline

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

**Files:** `api/v1/fencers.py`, `tests/test_api_fencers_milestones.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 13

Add GET /v1/fencers/{id}/milestones endpoint. Returns chronological milestones from fs_career_milestones.

---

## Agent 28 -- Wire bracket data into tournament page interactive bracket

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

**Files:** `api/v1/tournaments.py`, `tests/test_api_tournaments_brackets.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 9

Add GET /v1/tournaments/{id}/brackets endpoint. Returns structured bracket data grouped by weapon/category/gender/round.

---

## Agent 29 -- Wire organizer/format/deadline into tournament info table

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

**Files:** `api/v1/tournaments.py`, `tests/test_api_tournaments_details.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Depends on: Agent 7

Enhance GET /v1/tournaments/{id} to include organizer, organizer_url, entry_deadline, format, quota, prize_money, venue_name, venue_address.

---

## Agent 30 -- Create v_fencer_public view exposing all needed athlete fields

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

Create OR REPLACE VIEW v_fencer_public joining fs_fencers with fs_fencer_stats subqueries. Include bio, birth fields, national_rank, stats. Exclude sensitive columns (metadata, raw_text).

---

## TIER-3 FEDERATIONS (30 agents)

---

## Agent 31 -- Mexico Federation Scraper (MEX)

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

**Files:** `scrape_fed_mex.py`, `tests/test_fed_mex.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fme.com.mx` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `mex`, SOURCE: `mex_fencing`, COUNTRY: `Mexico`
- Probe URL: `fme.com.mx`
- Language: Spanish. Column headers: Pos, Nombre, Club, Puntos
- Handle: n, accented vowels, Spanish decimal commas, club abbreviations.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Mexico rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_mex.py, tests/test_fed_mex.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_mex.py -v
```

---

## Agent 32 -- Colombia Federation Scraper (COL)

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

**Files:** `scrape_fed_col.py`, `tests/test_fed_col.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `esgrimacolombia.co` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `col`, SOURCE: `col_fencing`, COUNTRY: `Colombia`
- Probe URL: `esgrimacolombia.co`
- Language: Spanish. Column headers: Posicion, Deportista, Club, Puntaje

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Colombia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_col.py, tests/test_fed_col.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_col.py -v
```

---

## Agent 33 -- Venezuela Federation Scraper (VEN)

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

**Files:** `scrape_fed_ven.py`, `tests/test_fed_ven.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fevenesgrima.com.ve` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `ven`, SOURCE: `ven_fencing`, COUNTRY: `Venezuela`
- Probe URL: `fevenesgrima.com.ve`
- Language: Spanish. Column headers: Pos, Esgrimista, Estado/Club, Puntos
- Economic/political instability may affect site availability.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Venezuela rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_ven.py, tests/test_fed_ven.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_ven.py -v
```

---

## Agent 34 -- Chile Federation Scraper (CHI)

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

**Files:** `scrape_fed_chi.py`, `tests/test_fed_chi.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `feche.cl` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `chi`, SOURCE: `chi_fencing`, COUNTRY: `Chile`
- Probe URL: `feche.cl`
- Language: Spanish. Column headers: Ranking, Nombre, Club, Puntos

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Chile rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_chi.py, tests/test_fed_chi.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_chi.py -v
```

---

## Agent 35 -- Turkey Federation Scraper (TUR)

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

**Files:** `scrape_fed_tur.py`, `tests/test_fed_tur.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `trfencing.gov.tr` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `tur`, SOURCE: `tur_fencing`, COUNTRY: `Turkey`
- Probe URL: `trfencing.gov.tr`
- Language: Turkish. Column headers: Sira, Isim, Kulup, Puan
- Turkish chars: I, i, g, u, s, o, c with diacritics.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Turkey rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_tur.py, tests/test_fed_tur.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_tur.py -v
```

---

## Agent 36 -- Iran Federation Scraper (IRI)

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

**Files:** `scrape_fed_iri.py`, `tests/test_fed_iri.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `iranfencing.ir` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `iri`, SOURCE: `iri_fencing`, COUNTRY: `Iran`
- Probe URL: `iranfencing.ir`
- Language: Persian (Farsi). Column headers: rth, nAm, bAshgAh, AmtIAz
- RTL script. Arabic/Persian numerals. May require Iranian IP.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Iran rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_iri.py, tests/test_fed_iri.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_iri.py -v
```

---

## Agent 37 -- Kazakhstan Federation Scraper (KAZ)

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

**Files:** `scrape_fed_kaz.py`, `tests/test_fed_kaz.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fencing.kz` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `kaz`, SOURCE: `kaz_fencing`, COUNTRY: `Kazakhstan`
- Probe URL: `fencing.kz`
- Language: Kazakh (Cyrillic) + Russian. Column headers: Oryn, Aty-zoni, Klub, Upay
- May be bilingual (Kazakh + Russian headers).

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Kazakhstan rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_kaz.py, tests/test_fed_kaz.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_kaz.py -v
```

---

## Agent 38 -- Thailand Federation Scraper (THA)

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

**Files:** `scrape_fed_tha.py`, `tests/test_fed_tha.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `thaifencing.org` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `tha`, SOURCE: `tha_fencing`, COUNTRY: `Thailand`
- Probe URL: `thaifencing.org`
- Language: Thai. Column headers: xndab, chux, smosr, khaaen
- Thai script range U+0E00-U+0E7F. No spaces between words.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Thailand rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_tha.py, tests/test_fed_tha.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_tha.py -v
```

---

## Agent 39 -- Chinese Taipei Federation Scraper (TPE)

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

**Files:** `scrape_fed_tpe.py`, `tests/test_fed_tpe.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fencing.org.tw` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `tpe`, SOURCE: `tpe_fencing`, COUNTRY: `Chinese Taipei`
- Probe URL: `fencing.org.tw`
- Language: Traditional Chinese. Column headers: pi ming, xing ming, dan wei, ji fen

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Chinese Taipei rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_tpe.py, tests/test_fed_tpe.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_tpe.py -v
```

---

## Agent 40 -- Morocco Federation Scraper (MAR)

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

**Files:** `scrape_fed_mar.py`, `tests/test_fed_mar.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `frmescrime.ma` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `mar`, SOURCE: `mar_fencing`, COUNTRY: `Morocco`
- Probe URL: `frmescrime.ma`
- Language: French + Arabic. Column headers: Rang, Nom, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Morocco rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_mar.py, tests/test_fed_mar.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_mar.py -v
```

---

## Agent 41 -- Tunisia Federation Scraper (TUN)

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

**Files:** `scrape_fed_tun.py`, `tests/test_fed_tun.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fte-tunisie.com` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `tun`, SOURCE: `tun_fencing`, COUNTRY: `Tunisia`
- Probe URL: `fte-tunisie.com`
- Language: French + Arabic. Column headers: Rang, Nom, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Tunisia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_tun.py, tests/test_fed_tun.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_tun.py -v
```

---

## Agent 42 -- South Africa Federation Scraper (RSA)

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

**Files:** `scrape_fed_rsa.py`, `tests/test_fed_rsa.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `safencing.co.za` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `rsa`, SOURCE: `rsa_fencing`, COUNTRY: `South Africa`
- Probe URL: `safencing.co.za`
- Language: English. Column headers: Rank, Name, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** South Africa rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_rsa.py, tests/test_fed_rsa.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_rsa.py -v
```

---

## Agent 43 -- Ireland Federation Scraper (IRL)

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

**Files:** `scrape_fed_irl.py`, `tests/test_fed_irl.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `irishfencing.net` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `irl`, SOURCE: `irl_fencing`, COUNTRY: `Ireland`
- Probe URL: `irishfencing.net`
- Language: English. Column headers: Rank, Name, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Ireland rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_irl.py, tests/test_fed_irl.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_irl.py -v
```

---

## Agent 44 -- Portugal Federation Scraper (POR)

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

**Files:** `scrape_fed_por.py`, `tests/test_fed_por.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fpesgrima.pt` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `por`, SOURCE: `por_fencing`, COUNTRY: `Portugal`
- Probe URL: `fpesgrima.pt`
- Language: Portuguese. Column headers: Pos, Nome, Clube, Pontos
- Portuguese chars: c, a, o, e, a.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Portugal rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_por.py, tests/test_fed_por.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_por.py -v
```

---

## Agent 45 -- Greece Federation Scraper (GRE)

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

**Files:** `scrape_fed_gre.py`, `tests/test_fed_gre.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fencing.org.gr` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `gre`, SOURCE: `gre_fencing`, COUNTRY: `Greece`
- Probe URL: `fencing.org.gr`
- Language: Greek. Column headers: Thesi, Onoma, Syllogos, Vathmoi
- Greek alphabet range U+0370-U+03FF.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Greece rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_gre.py, tests/test_fed_gre.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_gre.py -v
```

---

## Agent 46 -- Croatia Federation Scraper (CRO)

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

**Files:** `scrape_fed_cro.py`, `tests/test_fed_cro.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `hms.hr` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `cro`, SOURCE: `cro_fencing`, COUNTRY: `Croatia`
- Probe URL: `hms.hr`
- Language: Croatian. Column headers: Mjesto, Ime, Klub, Bodovi
- Croatian diacritics: c, c, d, s, z.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Croatia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_cro.py, tests/test_fed_cro.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_cro.py -v
```

---

## Agent 47 -- Serbia Federation Scraper (SRB)

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

**Files:** `scrape_fed_srb.py`, `tests/test_fed_srb.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `macesavez.rs` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `srb`, SOURCE: `srb_fencing`, COUNTRY: `Serbia`
- Probe URL: `macesavez.rs`
- Language: Serbian (Cyrillic + Latin). Column headers: Позициja, Име, Клуб, Поени
- Both scripts may appear on same page.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Serbia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_srb.py, tests/test_fed_srb.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_srb.py -v
```

---

## Agent 48 -- Bulgaria Federation Scraper (BUL)

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

**Files:** `scrape_fed_bul.py`, `tests/test_fed_bul.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `bulfencing.com` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `bul`, SOURCE: `bul_fencing`, COUNTRY: `Bulgaria`
- Probe URL: `bulfencing.com`
- Language: Bulgarian (Cyrillic). Column headers: Myasto, Ime, Klub, Tochki

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Bulgaria rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_bul.py, tests/test_fed_bul.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_bul.py -v
```

---

## Agent 49 -- Slovakia Federation Scraper (SVK)

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

**Files:** `scrape_fed_svk.py`, `tests/test_fed_svk.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `slovakfencing.sk` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `svk`, SOURCE: `svk_fencing`, COUNTRY: `Slovakia`
- Probe URL: `slovakfencing.sk`
- Language: Slovak. Column headers: Poradie, Meno, Klub, Body
- Slovak diacritics: a, a, c, d, e, i, l, l, n, o, o, r, s, t, u, y, z.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Slovakia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_svk.py, tests/test_fed_svk.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_svk.py -v
```

---

## Agent 50 -- Slovenia Federation Scraper (SLO)

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

**Files:** `scrape_fed_slo.py`, `tests/test_fed_slo.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `veza.si` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `slo`, SOURCE: `slo_fencing`, COUNTRY: `Slovenia`
- Probe URL: `veza.si`
- Language: Slovenian. Column headers: Mesto, Ime, Klub, Tocke
- Slovenian diacritics: c, s, z.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Slovenia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_slo.py, tests/test_fed_slo.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_slo.py -v
```

---

## Agent 51 -- Lithuania Federation Scraper (LTU)

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

**Files:** `scrape_fed_ltu.py`, `tests/test_fed_ltu.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `ltf.lt` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `ltu`, SOURCE: `ltu_fencing`, COUNTRY: `Lithuania`
- Probe URL: `ltf.lt`
- Language: Lithuanian. Column headers: Vieta, Vardas, Klubas, Taskai
- Lithuanian diacritics: a, c, e, e, i, s, u, u, z.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Lithuania rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_ltu.py, tests/test_fed_ltu.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_ltu.py -v
```

---

## Agent 52 -- Latvia Federation Scraper (LVA)

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

**Files:** `scrape_fed_lva.py`, `tests/test_fed_lva.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `pauksmes.lv` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `lva`, SOURCE: `lva_fencing`, COUNTRY: `Latvia`
- Probe URL: `pauksmes.lv`
- Language: Latvian. Column headers: Vieta, Vards, Klubs, Punkti
- Latvian diacritics: a, c, e, g, i, k, l, n, o, r, s, u, z.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Latvia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_lva.py, tests/test_fed_lva.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_lva.py -v
```

---

## Agent 53 -- Estonia Federation Scraper (EST)

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

**Files:** `scrape_fed_est.py`, `tests/test_fed_est.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `efl.ee` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `est`, SOURCE: `est_fencing`, COUNTRY: `Estonia`
- Probe URL: `efl.ee`
- Language: Estonian. Column headers: Koht, Nimi, Klubi, Punktid
- Estonian diacritics: a, o, u, o.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Estonia rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_est.py, tests/test_fed_est.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_est.py -v
```

---

## Agent 54 -- Azerbaijan Federation Scraper (AZE)

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

**Files:** `scrape_fed_aze.py`, `tests/test_fed_aze.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `azfencing.az` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `aze`, SOURCE: `aze_fencing`, COUNTRY: `Azerbaijan`
- Probe URL: `azfencing.az`
- Language: Azerbaijani (Latin). Column headers: Yer, Ad, Klub, Xal
- Azerbaijani chars: a, g, i, o, s, u.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Azerbaijan rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_aze.py, tests/test_fed_aze.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_aze.py -v
```

---

## Agent 55 -- Puerto Rico Federation Scraper (PUR)

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

**Files:** `scrape_fed_pur.py`, `tests/test_fed_pur.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fepur.org` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `pur`, SOURCE: `pur_fencing`, COUNTRY: `Puerto Rico`
- Probe URL: `fepur.org`
- Language: Spanish. Column headers: Posicion, Nombre, Club, Puntos

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Puerto Rico rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_pur.py, tests/test_fed_pur.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_pur.py -v
```

---

## Agent 56 -- Dominican Republic Federation Scraper (DOM)

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

**Files:** `scrape_fed_dom.py`, `tests/test_fed_dom.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `fedesgrimard.org` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `dom`, SOURCE: `dom_fencing`, COUNTRY: `Dominican Republic`
- Probe URL: `fedesgrimard.org`
- Language: Spanish. Column headers: Pos, Nombre, Club, Puntos

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Dominican Republic rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_dom.py, tests/test_fed_dom.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_dom.py -v
```

---

## Agent 57 -- Jamaica Federation Scraper (JAM)

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

**Files:** `scrape_fed_jam.py`, `tests/test_fed_jam.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `jamaicafencing.com` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `jam`, SOURCE: `jam_fencing`, COUNTRY: `Jamaica`
- Probe URL: `jamaicafencing.com`
- Language: English. Column headers: Rank, Name, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Jamaica rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_jam.py, tests/test_fed_jam.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_jam.py -v
```

---

## Agent 58 -- Cyprus Federation Scraper (CYP)

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

**Files:** `scrape_fed_cyp.py`, `tests/test_fed_cyp.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `cyprusfencing.com` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `cyp`, SOURCE: `cyp_fencing`, COUNTRY: `Cyprus`
- Probe URL: `cyprusfencing.com`
- Language: Greek + English. Column headers: Thesi/Position, Onoma/Name, Syllogos/Club, Vathmoi/Points
- Bilingual headers.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Cyprus rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_cyp.py, tests/test_fed_cyp.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_cyp.py -v
```

---

## Agent 59 -- Iceland Federation Scraper (ISL)

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

**Files:** `scrape_fed_isl.py`, `tests/test_fed_isl.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `skylmingar.is` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `isl`, SOURCE: `isl_fencing`, COUNTRY: `Iceland`
- Probe URL: `skylmingar.is`
- Language: Icelandic. Column headers: Sati, Nafn, Felag, Stig
- Icelandic chars: thorn, eth, ae, o.

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Iceland rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_isl.py, tests/test_fed_isl.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_isl.py -v
```

---

## Agent 60 -- Malta Federation Scraper (MLT)

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

**Files:** `scrape_fed_mlt.py`, `tests/test_fed_mlt.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 160 owns CI integration.

**Task:**
Build federation rankings scraper following the established pattern from v1 agents 6-25.

1. Read `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`.
2. Probe `maltasrim.com` -- find rankings URL pattern, record format.
3. Implement with: `parse_rankings_table()`, `fetch_rankings_page()`, `main()` using ScraperRunLogger.
4. Handle language-specific headers, UTF-8 scripts, decimal separators, DNS/DQ rows.
5. Write tests with realistic fixtures from probed source.

**Country-specific params:**
- CC: `mlt`, SOURCE: `mlt_fencing`, COUNTRY: `Malta`
- Probe URL: `maltasrim.com`
- Language: English. Column headers: Rank, Name, Club, Points

**Blocked handling:**
- 404/no public data: create stub scraper that logs probed URLs and exits 0.
- Login-only/JS-rendered: check XHR/API endpoints first; stub only after evidence.
- IP/geoblock: retry with delays/backoff, document and stub if still blocked.
- Partial combo coverage: implement available combos and report missing ones.

**Success criteria:** Malta rankings attempt all 12 combos, parse public data correctly, tests pass.

**Output format:**
```
Files: scrape_fed_mlt.py, tests/test_fed_mlt.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_mlt.py -v
```

---

## MORE TOURNAMENTS (15 agents)

---

## Agent 61 -- National championships scraper for top-20 countries

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

**Depends on:** Aggregates all 20 countries national championship data

Probe federation sites of top-20 fencing countries for national championship results. Parse ranking/medal tables. Use federation_request() for rate-limited access. Upsert tournaments (source_id: national_champs:{country}:{year}) and results.

---

## Agent 62 -- BUCS UK university fencing results

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

Probe bucs.org.uk for fencing results (individual and team). Parse tournament and result data. Handle British university naming conventions.

---

## Agent 63 -- French university fencing league (FFSU)

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

Probe ffsu.org for fencing results. Language: French. Handle French university naming.

---

## Agent 64 -- Japanese university fencing league results

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

Probe Japanese university fencing sites. Language: Japanese. Handle CJK text and Japanese university abbreviations.

---

## Agent 65 -- USA Y12/Y14 youth national circuit results

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

Probe USA Fencing youth results. Parse Y12/Y14 age category results. Handle USA Fencing specific event naming.

---

## Agent 66 -- British Youth Fencing results (BYC)

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

Probe britishfencing.com for British Youth Championships. Handle age categories (U10, U12, U14, U16, U18).

---

## Agent 67 -- IWAS World Games and satellite wheelchair events

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

Extend existing IWAS scraper to cover IWAS World Games and satellite events. Handle disability classification system.

---

## Agent 68 -- Historical pre-2000 results from olympedia deep crawl

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

Deep crawl olympedia for all pre-2000 Olympic fencing results. Handle legacy event naming and merged event codes.

---

## Agent 69 -- FIE World Cup individual pool bout-by-bout data

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

Scrape FIE pool bout results for World Cup events. Parse all pools, not just DE. Store bout-level pool data.

---

## Agent 70 -- FIE Satellite and FIE Challenge series results

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

Scrape FIE Satellite and Challenge series tournaments. Lower-tier events with fewer participants.

---

## Agent 71 -- Veterans World Cup circuit

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

Scrape Veteran World Championships and VWC events. Handle veteran age categories (V40, V50, V60, V70).

---

## Agent 72 -- European Fencing Confederation (EFC) youth circuit

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

Probe eurofencing.org for EFC youth circuit results. Handle Cadet/Junior European events.

---

## Agent 73 -- Asian Fencing Confederation (AFC) championships and circuit

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

Probe Asian Fencing Confederation site for championship results. Handle diverse country naming conventions.

---

## Agent 74 -- African Fencing Confederation championship results

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

Probe African Fencing Confederation for championship results. Handle limited online presence.

---

## Agent 75 -- Pan American Fencing Confederation (PAFC) circuit events

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

Probe Pan American Fencing Confederation for circuit events. Spanish/English bilingual.

---

## DEEPER ANALYTICS (15 agents)

---

## Agent 76 -- Elo rating system for fencers

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

SQL: fs_elo_ratings (fencer_id, weapon, category, elo_rating, matches_played, peak_elo, last_match_date, updated_at). Compute Elo from fs_bouts: K-factor=32 for all bouts, 2000 starting rating. Update after each bout. Handle cross-era comparability.

---

## Agent 77 -- Legacy score: weighted medal index

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

SQL: fs_legacy_scores (fencer_id, legacy_score, olympic_gold, worlds_gold, gp_gold, wc_gold, continental_gold, updated_at). Weight: Olympic gold=x10, Worlds=x5, GP=x3, WC=x2, Continental=x1. Compute per fencer.

---

## Agent 78 -- Peak performance age analysis by weapon x gender

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

Analyze which ages correlate with best results per weapon x gender. Query fs_results + fs_fencers birth_date. Report peak age ranges, average peak age per category. Write aggregate stats, not per-fencer table.

---

## Agent 79 -- Upset tracker: lowest seed to medal per tournament

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

SQL: fs_upsets (tournament_id, fencer_id, seed, final_rank, upset_score, description). For each tournament, find medalists with lowest initial seeds. Compute upset_score = seed - final_rank. Report biggest rank gap upsets.

---

## Agent 80 -- Home advantage analysis: fencer performance at home vs abroad

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

SQL: fs_home_advantage (fencer_id, home_competitions, home_medals, abroad_competitions, abroad_medals, home_win_pct, abroad_win_pct, advantage_delta). For each fencer, compare results when tournament country matches fencer country vs when abroad.

---

## Agent 81 -- Prediction model for next Olympic/World medalists

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

SQL: fs_predictions (fencer_id, weapon, category, predicted_medal_probability, factors jsonb, season). Weighted model based on: current rank (40%), recent form/last 5 results (30%), age curve (15%), historical performance at event tier (15%).

---

## Agent 82 -- Fantasy fencing scoring engine

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

SQL: fs_fantasy_points (fencer_id, tournament_id, points, breakdown jsonb). Points: 1st=100, 2nd=80, 3rd=60, QF=40, T16=20, T32=10, participation=5. Bonus for upsets, top-8 wins, clean sheets. Per-tournament scoring.

---

## Agent 83 -- Match-fixing / betting anomaly detection

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

SQL: fs_anomalies (bout_id, score_pattern, anomaly_score, flags text[], description). Detect: unusual score patterns (15-0 in high-level match), fencer performance variance across tournaments, suspicious rank difference x outcome combos.

---

## Agent 84 -- Fencer head-to-head network graph computation

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

SQL: fs_h2h_network (fencer_a_id, fencer_b_id, a_wins, b_wins, total_meetings, last_meeting, a_win_pct, edge_weight). Build complete weighted graph from all bouts. Edge_weight = (a_wins + 1) / (total_meetings + 2) -- smoothed win probability.

---

## Agent 85 -- Competition difficulty trending over time

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

For each tournament, compute strength-of-field metric (avg world rank of participants). Trend by season, weapon, category. Report: easiest/hardest competitions per season, difficulty inflation/deflation over time.

---

## Agent 86 -- Fencer clutch metric: performance delta elimination vs pool

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

SQL: fs_clutch_metrics (fencer_id, pool_win_pct, de_win_pct, clutch_delta, high_pressure_win_pct, medal_conversion_rate). For fencers with bout data, compare pool win% vs DE win%. High pressure = quarter-final+ matches.

---

## Agent 87 -- Country specialization index

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

Per country, compute medal concentration by weapon. Specialization index = Gini coefficient across weapons. Report which countries dominate which weapons, which are generalists.

---

## Agent 88 -- Junior-to-Senior conversion rate by country and weapon

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

For fencers with Junior results, track whether they appear in Senior results. Compute conversion rate (%) by country, weapon, gender. Report average years from Junior medaling to Senior medaling.

---

## Agent 89 -- Medal efficiency: medals per capita, per fencer, per competition

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

Compute: medals per capita (by country population data), medals per fencer (by fencer count per country), medals per competition entered. Normalize and rank countries by efficiency.

---

## Agent 90 -- Fencer similarity recommendation engine

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

SQL: fs_fencer_similarity (fencer_id, similar_fencer_id, similarity_score, factors jsonb). Compute pairwise fencer similarity based on: same weapon+category, similar rank trajectory, similar competition patterns, similar medal profiles. Recommend top-10 similar fencers.

---

## MORE ENRICHMENT (15 agents)

---

## Agent 91 -- Fencer education and occupation from Wikipedia + Wikidata

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

Query Wikidata SPARQL for fencing athletes. Extract: alma_mater, occupation, employer. Store in fs_fencers JSON metadata. Rate limit: 1s between SPARQL queries.

---

## Agent 92 -- Fencer family relationships from Wikidata

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

SQL: fs_fencer_relationships (fencer_id, related_fencer_id, relationship_type, verified). Query Wikidata for family relationships between fencers. Store sibling, parent-child, spouse connections.

---

## Agent 93 -- Anti-doping test history per fencer (from ITA/WADA)

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

SQL: fs_doping_records (fencer_id, test_date, substance, sanction, ban_start, ban_end, source_url). Probe ITA/WADA databases. Handle data availability and privacy concerns.

---

## Agent 94 -- Referee match assignments per tournament

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

SQL: fs_referee_assignments (referee_id, tournament_id, bout_id, role). Extend existing referee data with bout-level assignment details from FIE sources.

---

## Agent 95 -- Club founding dates, history text, notable alumni

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

SQL: fs_club_details (club_id, founded_date, history_text, notable_alumni, website, social_links). Probe club websites and Wikipedia for detail data.

---

## Agent 96 -- Coach career history

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

SQL: fs_coach_history (coach_id, fencer_id, start_date, end_date, role). Build coach-fencer relationship data from FIE and federation sources.

---

## Agent 97 -- Fencer video highlight reels auto-curated from YouTube

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

SQL: fs_videos (fencer_id, url, title, channel, duration, published_at, view_count, thumbnail_url). Search YouTube for fencer name + fencing. Store relevant matches. Handle YouTube API rate limits.

---

## Agent 98 -- Interview quotes database from press conferences and media

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

SQL: fs_quotes (fencer_id, quote_text, source_url, source_name, date, context). Scrape fencing news sites for athlete quotes. Classify by topic (competition, training, retirement, etc.).

---

## Agent 99 -- Fencer sponsorship deals and endorsement history

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

SQL: fs_sponsorships (fencer_id, sponsor_name, sponsor_type, start_date, end_date, estimated_value). Scrape news articles and social media for sponsorship announcements.

---

## Agent 100 -- Fencer nationality history from Wikidata

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

SQL: fs_nationality_history (fencer_id, country, start_date, end_date, reason). Query Wikidata for country of citizenship with dates. Flag fencers who changed national representation.

---

## Agent 101 -- Competition weather data (indoor vs outdoor, temperature, humidity)

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

SQL: fs_competition_weather (tournament_id, venue_type, temperature_c, humidity, conditions, source). Query historical weather for tournament location + date. Note: most fencing is indoor.

---

## Agent 102 -- Equipment usage trends (brands winning by weapon)

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

SQL: fs_equipment_trends (fencer_id, tournament_id, equipment_brand, equipment_type, medal_won). Scrape social media/event photos for visible branding. Aggregate by weapon and medal status.

---

## Agent 103 -- Fencer handedness data (left-handed vs right-handed stats)

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

SQL: fs_handedness (fencer_id, hand, confidence, source). Query Wikidata, Wikipedia, FIE profiles for handedness. Compute lefty advantage stats per weapon.

---

## Agent 104 -- Fencer injury history from news scraping

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

SQL: fs_injury_history (fencer_id, injury_type, date, recovery_date, severity, source_url). Scrape fencing news sites for injury reports, surgery announcements, recovery timelines.

---

## Agent 105 -- Historical rule changes database and their impact on results

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

SQL: fs_rule_changes (change_date, rule_body, description, affected_weapons, impact_analysis). Document major FIE rule changes (2004 electro, 2008 new grip rules, 2016 new timing, 2021 mask rules). Correlate with result pattern changes.

---


## PRODUCT / FRONTEND LAYER (25 agents)

---

## Agent 106 -- Next.js frontend with search + browse for all entities

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

[Standard boilerplate omitted for space -- use same template as v1]

**Files:** `frontend/`, `package.json`, `next.config.js`

**Task:**
1. Set up Next.js project with TypeScript, Tailwind CSS, and shadcn/ui components.
2. Create pages:
   - `/` -- landing page with search bar and featured athletes
   - `/fencers` -- fencer browse + search (name, country, weapon, category filters)
   - `/fencers/[id]` -- athlete profile page
   - `/tournaments` -- tournament browse + search
   - `/tournaments/[id]` -- tournament detail page
   - `/rankings` -- FIE and national rankings viewer
   - `/countries/[code]` -- country overview page with medal counts and top fencers
   - `/head-to-head` -- H2H comparison tool
3. Use Supabase client SDK for data fetch.
4. Implement server-side rendering where appropriate.
5. Write tests using Playwright or Vitest.

**Success criteria:** Frontend runs, searches work, athlete/tournament pages render from live data.

**Output format:**
```
Files: frontend/ (new Next.js app)
Pages: [list]
Tests: npm run test
```

---

## Agent 107 -- GraphQL API wrapping existing REST + Supabase
[Single-line: Wrap Supabase + REST API in GraphQL using Hasura or Apollo Server with federation support]

**Files:** `graphql/`, `docker-compose.yml` for Hasura

---

## Agent 108 -- WebSocket server for live results push
[Single-line: FastAPI WebSocket endpoint that pushes new fs_bouts/fs_results to connected clients]

**Files:** `ws_server.py`, `tests/test_ws_server.py`

---

## Agent 109 -- Competition bracket visualizer React component
[Single-line: React component that renders fs_tournament_brackets as an interactive bracket tree]

**Files:** `frontend/components/bracket-visualizer.tsx`, `tests/test_bracket_visualizer.tsx`

---

## Agent 110 -- Fencer career timeline visualizer React component
[Single-line: React component rendering fs_career_milestones as an interactive timeline]

**Files:** `frontend/components/career-timeline.tsx`, `tests/test_career_timeline.tsx`

---

## Agent 111 -- Country medal heatmap interactive map component
[Single-line: React component using MapLibre/Leaflet to render fs_country_medal_geo data]

**Files:** `frontend/components/medal-heatmap.tsx`, `tests/test_medal_heatmap.tsx`

---

## Agent 112 -- Ranking history sparkline chart component
[Single-line: React component using Nivo/Recharts to render v_ranking_sparklines data]

**Files:** `frontend/components/ranking-sparkline.tsx`, `tests/test_ranking_sparkline.tsx`

---

## Agent 113 -- Head-to-head comparison page with side-by-side stats
[Single-line: Page at /compare?fencer_a=X&fencer_b=Y showing side-by-side stats, H2H history]

**Files:** `frontend/pages/compare.tsx`, `tests/test_compare.tsx`

---

## Agent 114 -- Tournament results PDF generator
[Single-line: FastAPI endpoint that generates PDF of tournament results from fs_results data]

**Files:** `api/v1/pdf.py`, `tests/test_pdf.py`

---

## Agent 115 -- Calendar sync (ICS feed per federation/weapon/category)
[Single-line: Generate .ics calendar feeds for tournaments filtered by federation/weapon/category]

**Files:** `api/v1/calendar.py`, `tests/test_calendar.py`

---

## Agent 116 -- Ranking alerts service (email/SMS when fencer rank changes)
[Single-line: Monitor fs_ranking_trajectory, detect rank changes, send alerts via SendGrid/Twilio]

**Files:** `scripts/ranking_alerts.py`, `tests/test_ranking_alerts.py`

---

## Agent 117 -- Automated result tweets bot (Twitter/X integration)
[Single-line: Bot that posts new competition results to Twitter/X from fs_results]

**Files:** `scripts/tweet_bot.py`, `tests/test_tweet_bot.py`

---

## Agent 118 -- Data syndication API for media partners
[Single-line: FastAPI endpoints for media partners to bulk download curated data sets]

**Files:** `api/v1/syndication.py`, `tests/test_syndication.py`

---

## Agent 119 -- BigQuery export pipeline for data science users
[Single-line: Export fs_* tables to BigQuery for data science analysis]

**Files:** `scripts/bigquery_export.py`, `tests/test_bigquery_export.py`

---

## Agent 120 -- Data marketplace / API monetization portal with Stripe
[Single-line: Stripe subscription portal for API access tiers (free/supporter/pro)]

**Files:** `api/v1/subscriptions.py`, `frontend/pages/pricing.tsx`

---

## Agent 121 -- Fencer photo dedup via facial recognition
[Single-line: Image hashing + perceptual hash comparison to deduplicate fencer headshots]

**Files:** `scripts/dedup_photos.py`, `tests/test_dedup_photos.py`

---

## Agent 122 -- Competition PDF results to structured data OCR pipeline
[Single-line: OCR pipeline for competition PDF results using Tesseract/pytesseract]

**Files:** `scripts/ocr_results.py`, `tests/test_ocr_results.py`

---

## Agent 123 -- Mobile push notification service for live results
[Single-line: Firebase Cloud Messaging integration for push notifications on live results]

**Files:** `scripts/push_notifications.py`, `tests/test_push_notifications.py`

---

## Agent 124 -- Fencer comparison tool (side-by-side career stats)
[Single-line: Enhanced comparison page with radar charts and stat overlays]

**Files:** `frontend/pages/compare-enhanced.tsx`, `tests/test_compare_enhanced.tsx`

---

## Agent 125 -- "Who's hot" trending fencers weekly leaderboard
[Single-line: Weekly computation of trending fencers based on recent performance and rank change]

**Files:** `compute_trending.py`, `tests/test_trending.py`

---

## Agent 126 -- Fencer social leaderboard (most followed, most mentioned)
[Single-line: Leaderboard from fs_social_followers data: most followers, most mentioned in news]

**Files:** `frontend/pages/social-leaderboard.tsx`, `tests/test_social_leaderboard.tsx`

---

## Agent 127 -- Competition countdown and calendar view
[Single-line: Calendar view of upcoming competitions with countdown timers]

**Files:** `frontend/pages/calendar.tsx`, `tests/test_calendar.tsx`

---

## Agent 128 -- Federation overview pages with depth charts
[Single-line: Country/federation overview pages showing depth chart (all fencers per weapon/gender)]

**Files:** `frontend/pages/federations/[code].tsx`, `tests/test_federation_page.tsx`

---

## Agent 129 -- News aggregator frontend with filtering by fencer
[Single-line: News feed page from fs_articles + fs_quotes with fencer filtering]

**Files:** `frontend/pages/news.tsx`, `tests/test_news_feed.tsx`

---

## Agent 130 -- Athlete quiz / trivia feature from career data
[Single-line: Generate trivia questions from fencer career milestones for engagement]

**Files:** `compute_trivia.py`, `tests/test_trivia.py`

---

## MARKETPLACE / SOCIAL / MEDIA (15 agents)

---

## Agent 131 -- Absolute Fencing product catalog scraper

[Standard boilerplate]

**Files:** `scrape_absolutefencing.py`, `tests/test_scrape_absolutefencing.py`

**Task:**
1. Probe absolutefencing.com product catalog structure.
2. Scrape: product name, SKU, category (weapon), price, description, image URL, stock status.
3. Store in fs_products table:
```sql
CREATE TABLE IF NOT EXISTS fs_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    source_id text UNIQUE NOT NULL,
    name text NOT NULL,
    brand text,
    category text,
    weapon text,
    price numeric(10,2),
    currency text DEFAULT 'USD',
    description text,
    image_url text,
    product_url text,
    stock_status text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
4. Write tests with fixture product pages.

**Success criteria:** Product catalog scraped from Absolute Fencing.

**Output format:**
```
Files: scrape_absolutefencing.py, tests/test_scrape_absolutefencing.py
Products scraped: X
Tests: pytest tests/test_scrape_absolutefencing.py -v
```

## Agent 132 -- Leon Paul product catalog scraper
[Same pattern as Agent 131 but for leonpaul.com]

**Files:** `scrape_leonpaul.py`, `tests/test_scrape_leonpaul.py`

---

## Agent 133 -- Allstar/Uhlmann product catalog scraper
[Same pattern -- allstar-uhlmann.com]

**Files:** `scrape_allstar.py`, `tests/test_scrape_allstar.py`

---

## Agent 134 -- Fencing.net product scraper + reviews
[Scrape fencing.net store + reviews]

**Files:** `scrape_fencingnet.py`, `tests/test_scrape_fencingnet.py`

---

## Agent 135 -- PBT Fencing product scraper
[Scrape pbtfencing.com]

**Files:** `scrape_pbt.py`, `tests/test_scrape_pbt.py`

---

## Agent 136 -- Blue Gauntlet product scraper
[Scrape blue-gauntlet.com]

**Files:** `scrape_bluegauntlet.py`, `tests/test_scrape_bluegauntlet.py`

---

## Agent 137 -- Fencing store directory (physical stores worldwide)
[Build directory of physical fencing stores worldwide from Google Maps + web search]

**Files:** `scrape_store_directory.py`, `tests/test_store_directory.py`

---

## Agent 138 -- Fencing club review scraper from Google Maps
[Scrape Google Maps reviews for fencing clubs]

**Files:** `scrape_club_reviews_maps.py`, `tests/test_club_reviews_maps.py`

---

## Agent 139 -- YouTube fencing video indexer
[Index YouTube fencing videos by channel/playlist/fencer]

**Files:** `index_youtube.py`, `tests/test_index_youtube.py`

---

## Agent 140 -- Instagram fencing content aggregator
[Aggregate Instagram fencing content (requires API auth -- build schema + stubs)]

**Files:** `aggregate_instagram.py`, `tests/test_aggregate_instagram.py`

---

## Agent 141 -- TikTok fencing content aggregator
[Aggregate TikTok fencing content (requires API auth -- build schema + stubs)]

**Files:** `aggregate_tiktok.py`, `tests/test_aggregate_tiktok.py`

---

## Agent 142 -- Forum scraper (fencing.net, reddit r/fencing) for discussions
[Scrape fencing forums and Reddit for discussion topics]

**Files:** `scrape_forums.py`, `tests/test_scrape_forums.py`

---

## Agent 143 -- Fencing event photographer directory
[Build directory of fencing photographers by event coverage]

**Files:** `scrape_photographers.py`, `tests/test_scrape_photographers.py`

---

## Agent 144 -- Fencing equipment second-hand marketplace scraper
[Scrape fencing classifieds for used equipment listings]

**Files:** `scrape_used_gear.py`, `tests/test_scrape_used_gear.py`

---

## Agent 145 -- Fencing camp review aggregator
[Aggregate fencing camp listings and reviews]

**Files:** `scrape_camps.py`, `tests/test_scrape_camps.py`

---

## ADVANCED / EXPERIMENTAL (15 agents)

---

## Agent 146 -- Match video auto-trimmer (find fencer from YouTube video)
[Analyze YouTube video metadata to identify featured fencers and auto-trim to relevant segments]

**Files:** `video_trimmer.py`, `tests/test_video_trimmer.py`

---

## Agent 147 -- Live scoring overlay for streamers (OBS plugin data)
[Generate real-time scoring data feed for OBS overlays]

**Files:** `scoring_overlay.py`, `tests/test_scoring_overlay.py`

---

## Agent 148 -- Fencing fantasy league with draft and weekly scoring
[Fantasy fencing league engine: draft, lineup management, weekly scoring from competition results]

**Files:** `fantasy_league/`, `tests/test_fantasy_league.py`

---

## Agent 149 -- Historical tournament re-simulator (Monte Carlo based on Elo)
[Monte Carlo simulation of historical tournaments using Elo ratings to compare eras]

**Files:** `simulate_tournaments.py`, `tests/test_simulate_tournaments.py`

---

## Agent 150 -- Fencer form tracker (last 5 competitions trend)
[Track each fencer's form over last 5 competitions: rank trend, win rate trend, points trend]

**Files:** `compute_form_tracker.py`, `tests/test_form_tracker.py`

---

## Agent 151 -- Betting odds aggregator for upcoming competitions
[Aggregate betting odds for upcoming fencing events from various bookmakers]

**Files:** `scrape_odds.py`, `tests/test_scrape_odds.py`

---

## Agent 152 -- Youth talent identification (early-career outlier detection)
[Identify youth fencers with outlier performance patterns suggesting future success]

**Files:** `compute_talent_id.py`, `tests/test_talent_id.py`

---

## Agent 153 -- Fencer transfer market value estimator
[Estimate fencer transfer value based on performance, age, contract status]

**Files:** `compute_transfer_value.py`, `tests/test_transfer_value.py`

---

## Agent 154 -- Equipment durability tracker (how often top fencers replace gear)
[Track equipment replacement patterns from social media and news]

**Files:** `scrape_gear_durability.py`, `tests/test_gear_durability.py`

---

## Agent 155 -- Fencing gym / training facility directory worldwide
[Build global directory of fencing training facilities]

**Files:** `scrape_training_facilities.py`, `tests/test_training_facilities.py`

---

## Agent 156 -- Fencer sponsorship matchmaking (brand to athlete)
[Match fencers to potential sponsors based on profile, reach, performance]

**Files:** `compute_sponsorship_match.py`, `tests/test_sponsorship_match.py`

---

## Agent 157 -- Competition travel cost estimator (flights + hotels for each event)
[Estimate travel costs for attending each competition based on location]

**Files:** `compute_travel_costs.py`, `tests/test_travel_costs.py`

---

## Agent 158 -- Fencing history timeline (major rule changes, equipment evolution)
[Interactive timeline of fencing history: rules, equipment, great rivalries]

**Files:** `compute_history_timeline.py`, `tests/test_history_timeline.py`

---

## Agent 159 -- AI coach: technique analysis from bout data patterns
[Analyze bout patterns to identify technical strengths and weaknesses]

**Files:** `compute_technique_analysis.py`, `tests/test_technique_analysis.py`

---

## Agent 160 -- CI merge for all 160 agents into workflow files

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

**IMPORTANT:** This agent is the ONLY one that touches `.github/workflows/`. Do not modify any other files.

**Files:** `.github/workflows/scraper.yml`, `.github/workflows/live_results.yml`, `.github/workflows/weekly_analytics.yml`, `tests/test_workflow_integrity.py`

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
4. Product/frontend layer (agents 106-130) does NOT go in CI -- document separately.
5. Every scraper step: continue-on-error: true with SUPABASE_URL + SUPABASE_SERVICE_KEY env.
6. Validate each YAML.
7. Write workflow integrity tests that:
   - Parse all workflow files with PyYAML
   - Assert every new script appears in exactly one intended workflow
   - Assert discover_competition_urls appears before results scrapers
   - Assert each scraper step has continue-on-error: true
   - Assert Supabase env vars present on scraper steps

**Success criteria:** Three workflow files, valid YAML, all scripts integrated, workflow integrity tests pass.

**Output format:**
```
Files: .github/workflows/scraper.yml, .github/workflows/live_results.yml, .github/workflows/weekly_analytics.yml, tests/test_workflow_integrity.py
YAML validation: pass/fail
Missing scripts: []
Tests: pytest tests/test_workflow_integrity.py -v
```
