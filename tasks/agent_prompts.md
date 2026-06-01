# Agent Prompts: Operation Insane Fencing Database

## Agent 1 — Fix Italy Scraper (BIFF .xls)

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_italy.py`, `tests/test_fed_italy.py`, `requirements.txt`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
The current `scrape_fed_italy.py` has an HTML parser that never matches Olympic weapon tables — it gets 0 data. Italy's Federscherma publishes rankings as BIFF .xls files.

1. Read existing `scrape_fed_italy.py`, `fed_rankings_common.py`, `scrape_fed_british.py`.
2. Probe `https://www.federscherma.it/classifiche/` (or current URL) — find .xls download links for each weapon/gender/category combo. Print URLs found.
3. Add `xlrd` + `openpyxl` to `requirements.txt`.
4. Rewrite the scraper:
   - Replace HTML parser with .xls download + parser
   - `parse_rankings_xls(file_bytes)` → try openpyxl first, fall back to xlrd
   - Column mapping: Pos=rank, Atleta=name, Società=club, Punti=points
   - Handle Italian chars (è, é, ò, ù, à)
   - Handle "." vs "," decimal separators in points
5. Write `tests/test_fed_italy.py`:
   - Test with an openpyxl-generated .xlsx in memory (BytesIO)
   - Test column mapping
   - Test empty sheet, header-only sheet
   - Test BIFF .xls format with a tiny checked-in binary fixture or an `xlwt`-generated workbook if you add `xlwt` as a test dependency

**Success criteria:**
- `xlrd` + `openpyxl` in requirements.txt
- `parse_rankings_xls()` parses .xls and .xlsx correctly
- All 12 combos attempted (may not all have .xls files)
- Tests pass
- The old broken HTML parser is gone — no HTML-parsing code remains

**When blocked:**
- No .xls files found at the probed URL → try alternative federscherma.it subpages. If none exist, document and stub.
- Can't install xlrd (Python 3.12+ compat issue) → use openpyxl only and document

**Output format:**
```
Files: scrape_fed_italy.py (rewritten), tests/test_fed_italy.py (new), requirements.txt (modified)
Combos working: X/12 — list which ones
Old HTML parser removed: yes/no
Tests: pytest tests/test_fed_italy.py -v — result
```

---

## Agent 2 — Canonical Fencer Identity Resolution

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/merge_fencer_identities.py`, `supabase/migrations/YYYYMMDD_fencer_identities.sql`, `tests/test_fencer_identity.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
`fs_fencers` has duplicate rows for the same person across weapons/categories. Build an identity resolution system.

1. Read `scraper.py` and any result scraper to understand `fs_fencers` schema.
2. Design `fs_fencer_identities` table: `id` (uuid PK), `canonical_name` (text), `country` (text), `fie_ids` (uuid[]), `fs_fencer_row_ids` (uuid[]), `metadata` (jsonb), `created_at`, `updated_at`.
3. Write SQL migration.
4. Write `scripts/merge_fencer_identities.py`:
   - Query all `fs_fencers` rows
   - Group by `fie_id` (exact match — same person across weapons)
   - For rows without `fie_id`, group by normalized name+country
   - Normalization: `unicodedata.normalize('NFKC', name).lower().strip()`, remove punctuation
   - Store each identity group as one row in `fs_fencer_identities`
   - Report: total fencers, identities found, ambiguous cases left
5. Write `tests/test_fencer_identity.py`:
   - Mock fs_fencers data with known duplicate scenarios
   - Test fie_id grouping, name+country grouping, ambiguous cases
   - Test normalization handles accented chars

**Success criteria:**
- Migration SQL creates the table
- Merge script runs and produces identity groups
- Tests cover: fie_id match, name+country match, ambiguous no-match, unicode normalization
- Safe to run multiple times (idempotent)

**When blocked:**
- Can't determine schema (no migration file) → read from code that uses the tables

**Depends on:** Agent 1 (for complete fencer set from Italy)

**Output format:**
```
Files: scripts/merge_fencer_identities.py, supabase/migrations/YYYYMMDD_fencer_identities.sql, tests/test_fencer_identity.py
Migration SQL: included
Test results: pytest tests/test_fencer_identity.py -v
Identity groups created: (reported by script)
```

---

## Agent 3 — Orphan Result Matching Engine

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/match_orphan_results.py`, `tests/test_orphan_matching.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 (needs identity resolution to match against)

**Task:**
Many `fs_results` rows have `fencer_id = NULL`. Match them to fencers.

1. Read `fs_results` schema from `scrape_results.py`, `scrape_olympics.py`.
2. Write `scripts/match_orphan_results.py`:
   - Query `fs_results WHERE fencer_id IS NULL AND name IS NOT NULL`
   - Matching tiers:
     - Tier 1: `fie_fencer_id` matches `fs_fencers.fie_id` (direct link)
     - Tier 2: exact name + exact country match against `fs_fencers`
     - Tier 3: normalized name (NFKC, lower) + exact country
     - Tier 4: fuzzy name (Levenshtein ratio >= 0.85) + exact country
     - Tier 5: for NCAA results, match by `metadata->>'school'`
     - Tier 6: for olympedia results, match by `metadata->>'olympedia_athlete_id'`
   - For each match, batch UPDATE `fs_results SET fencer_id = X WHERE id = Y`
   - Log unmatched orphans to `unmatched_orphans.log` with name, country, source
3. Also match `fs_national_fed_rankings` orphans (rows with NULL fencer_id).
4. Write tests:
   - Mock orphans with known matchable names
   - Test each matching tier independently
   - Test that ambiguous matches (same name, different country) are NOT auto-matched
   - Test that fie_id match takes priority over name match

**Success criteria:**
- Reduces NULL fencer_id by 80%+ on realistic test data
- Ambiguous matches logged, not silently applied
- Unmatched orphans written to log file
- Tests pass

**When blocked:**
- No fs_fencer_identities yet from Agent 2 → match against raw fs_fencers instead (less powerful but still works)

**Output format:**
```
Files: scripts/match_orphan_results.py, tests/test_orphan_matching.py
Match rate on test data: X%
Unmatched logged: yes
Tests: pytest tests/test_orphan_matching.py -v
```

---

## Agent 4 — Engarde Rewrite + Non-FIE Expansion

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_engarde.py`, `tests/test_scrape_engarde.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
The current Engarde scraper hits 404 on many endpoints. Engarde is a tournament platform used internationally for non-FIE events.

1. Read the current `scrape_engarde.py` completely. Read `scrape_bouts.py` for `fs_bouts` schema.
2. Probe Engarde endpoints:
   - Try main Engarde services: `engarde-service.com`
   - Try country-specific: look for UK, Irish, Australian, French Engarde instances
   - Test both tournament listing and results endpoints
   - Test the pool/DE bout detail endpoints
   - Document exact URL, request method, params/body, response format
3. Write `tests/test_scrape_engarde.py` with fixture HTML from probe:
   - `test_parse_tournament_listing`: parse event list, verify name+date+ID
   - `test_parse_results_table`: parse individual results
   - `test_parse_pool_bouts`: parse pool bout scores
   - `test_parse_de_bouts`: parse DE bracket bouts
   - `test_empty_tournament`: no results page → empty list
   - `test_404_handled`: mock 404 response → None, not crash
4. Rewrite `scrape_engarde.py`:
   - Tournament discovery: query multiple Engarde service instances
   - Upsert tournaments to `fs_tournaments` (source_id: `engarde:{service}:{event_id}`)
   - Parse individual competition results
   - Parse pool bouts (round, fencer_a, score_a, fencer_b, score_b)
   - Parse DE bouts (round, fencer_a, score_a, fencer_b, score_b)
   - Upsert results to `fs_results` (delete+reinsert per tournament)
   - Upsert bouts to `fs_bouts` (UUIDv5 based on tournament_id + source_key)
   - Fencer matching: best-effort name+country against `fs_fencers`
   - Incremental state: `done_ids` in scraper_state
   - Rate limit: 1.5s between requests

**Success criteria:**
- Scraper discovers tournaments from at least 2 Engarde service instances
- Individual results parsed correctly
- Pool and DE bouts parsed correctly
- `fs_bouts` populated with bout-level data
- Tests pass with real-world HTML fixtures

**When blocked:**
- All Engarde endpoints return 404 → document the dead endpoints and create a stub that logs "Engarde API currently unavailable"
- Only some services work → implement what works

**Output format:**
```
Files: scrape_engarde.py (rewritten), tests/test_scrape_engarde.py (new)
Engarde services working: [list]
Bout data: yes/no — pool+DE or just results?
Tests: pytest tests/test_scrape_engarde.py -v
```

---

## Agent 5 — Compute Pipeline Cleanup

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_national_rankings.py`, `tests/test_compute_rankings.py`, `season_utils.py`, `tests/test_season_utils.py`, `scraper.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
Three known issues: weight function uses string-matching on names, season formats inconsistent, no weapon combo dedup.

1. Read `compute_national_rankings.py`, `scraper.py`, `fed_rankings_common.py`.
2. Create `season_utils.py`:
```python
def season_to_string(season_int: int) -> str:  # 2026 → "2025-2026"
def season_from_string(season_str: str) -> int:  # "2025-2026" → 2026; "2026" → 2026
def current_fie_season() -> int:  # if month >= 7 return year, else return year-1
def normalize_season(raw) -> str:  # accepts int or string, returns "YYYY-YYYY"
```
3. Write `tests/test_season_utils.py` covering all conversion functions and edge cases.
4. Fix `result_weight` in `compute_national_rankings.py`:
   - Check `fs_tournaments.type` field first: {"WCH": 5.0, "GP": 4.0, "WC": 3.0, "CC": 2.5, ...}
   - Fall back to string-matching for tournaments without type
   - Update tests to verify type-based weighting
5. Add weapon combo dedup to `scraper.py`:
   - Before iterating weapon combos, collect all distinct fencers across combos
   - Deduplicate by `fie_id` (keep the most complete name row)
   - Pass deduplicated list to upsert
6. Update `compute_national_rankings.py` and federation scrapers to use `season_utils` where possible.
7. Run full test suite: `.venv/bin/python -m pytest tests/ -v`

**Success criteria:**
- `season_utils.py` with tests covering all conversion functions
- `result_weight` uses `type` field first, string fallback second
- `scraper.py` deduplicates fencers across weapon combos before upsert
- All existing tests still pass

**When blocked:**
- Can't find the weapon combo loop in `scraper.py` → grep for `for weapon in` or `for w in` in scraper.py

**Output format:**
```
Files: season_utils.py (new), tests/test_season_utils.py (new), compute_national_rankings.py (modified), scraper.py (modified)
season_utils: 4 functions, all tested
result_weight: now uses type field
Dedup: added to scraper.py
Tests: pytest tests/ -v — all pass
```

---

## Agent 6 — Hungary Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_hun.py`, `tests/test_fed_hun.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `hun`, SOURCE: `hun_fencing`, COUNTRY: `HUN`
- Probe URL: `hunfencing.hu` / `magyarvivaszszovetseg.hu`
- Try: `/ranglistak`, `/rankings`
- Language: Hungarian. Column headers: Helyezés, Név, Egyesület, Pont
- Hungarian chars: á, é, í, ó, ö, ő, ú, ü, ű
- Probe first: run a script to check which URL pattern works

**Success criteria:** Hungary rankings attempt all 12 standard combos, public combos write rows through `fed_rankings_common.write_rankings()`, unavailable combos skip cleanly, and parser tests pass.

**Output format:**
```
Files: scrape_fed_hun.py, tests/test_fed_hun.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_hun.py -v
```

---

## Agent 7 — South Korea Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_kor.py`, `tests/test_fed_kor.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `kor`, SOURCE: `kor_fencing`, COUNTRY: `KOR`
- Probe URL: `koreafencing.org`
- Language: Korean (Hangul). Column headers: 순위, 이름, 소속, 점수
- Hangul range: \uAC00-\uD7AF
- Name handling: keep Hangul as-is. If romanization is also available in the page, capture both.
- Many Korean fencers also have English names on FIE — don't romanize, just store the Hangul
- Probe first: check if site requires Korean IP or has anti-scraping measures

**Success criteria:** South Korea rankings preserve Hangul names, capture romanized alternate names only when published, attempt all public combos, and pass parser tests with Korean fixtures.

**Output format:**
```
Files: scrape_fed_kor.py, tests/test_fed_kor.py
Combos working: X/12
Blocked/IP gated: yes/no
Tests: pytest tests/test_fed_kor.py -v
```

---

## Agent 8 — China Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_chn.py`, `tests/test_fed_chn.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `chn`, SOURCE: `chn_fencing`, COUNTRY: `CHN`
- Probe URL: `fencing.org.cn` (may be blocked from outside China — try `cnfencing.org.cn` or `sport.gov.cn`)
- Language: Chinese (CJK). Column headers: 排名, 姓名, 单位, 积分
- CJK range: \u4E00-\u9FFF
- May require Chinese IP or have CAPTCHA. If blocked after all probes, create stub: "China rankings require in-country access"
- Name handling: store Chinese characters as-is. Family name first (Chinese convention)

**Success criteria:** China rankings parse CJK rows from a public source or produce a clear stub after documented probes; tests cover Chinese headers and CJK names.

**Output format:**
```
Files: scrape_fed_chn.py, tests/test_fed_chn.py
Combos working: X/12
Stub reason: none/in-country access/captcha/no public rankings
Tests: pytest tests/test_fed_chn.py -v
```

---

## Agent 9 — Japan Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_jpn.py`, `tests/test_fed_jpn.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `jpn`, SOURCE: `jpn_fencing`, COUNTRY: `JPN`
- Probe URL: `fencing-jpn.jp` or `jfa-fencing.jp`
- Language: Japanese. Column headers: 順位, 選手名, 所属, 得点
- Japanese scripts: Kanji (CJK), Hiragana, Katakana
- May use PDF for rankings instead of HTML tables. If PDF:
  - Add `pdfplumber` or `tabula-py` to requirements.txt if needed
  - Test PDF parsing approach
- Name handling: Family + Given (Japanese order). Store as-is.

**Success criteria:** Japan rankings parse from current public HTML/PDF source, preserve Japanese scripts, attempt all available combos, and pass parser tests.

**Output format:**
```
Files: scrape_fed_jpn.py, tests/test_fed_jpn.py
Combos working: X/12
Data format: html/pdf/stub
Tests: pytest tests/test_fed_jpn.py -v
```

---

## Agent 10 — Russia Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_rus.py`, `tests/test_fed_rus.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `rus`, SOURCE: `rus_fencing`, COUNTRY: `RUS`
- Probe URL: `rusfencing.ru`
- Try: `/rating`, `/rankings`, `/sport/ranking`
- Language: Russian (Cyrillic). Column headers: Место, ФИО, Клуб, Очки
- Cyrillic range: \u0400-\u04FF
- May be geoblocked or slow from outside Russia. If unreachable: create stub.
- May use PDF or Excel files (like Italy). If so, use xlrd/openpyxl.
- Name handling: Cyrillic text. Store as-is. If Latin transliteration also present, capture both.

**Success criteria:** Russia rankings parse Cyrillic rows from an accessible public source or produce a documented geoblock/unreachable stub; tests cover Cyrillic headers and optional Latin alternates.

**Output format:**
```
Files: scrape_fed_rus.py, tests/test_fed_rus.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_rus.py -v
```

---

## Agent 11 — Poland Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_pol.py`, `tests/test_fed_pol.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `pol`, SOURCE: `pol_fencing`, COUNTRY: `POL`
- Probe URL: `pzszerm.pl`
- Try: `/ranking`, `/klasyfikacje`, `/rankingi`
- Language: Polish. Column headers: Miejsce, Zawodnik, Klub, Punkty
- Polish chars: ą, ć, ę, ł, ń, ó, ś, ź, ż

**Success criteria:** Poland rankings parse Polish headers and characters, write all public combos, skip unavailable combos safely, and pass parser tests.

**Output format:**
```
Files: scrape_fed_pol.py, tests/test_fed_pol.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_pol.py -v
```

---

## Agent 12 — Ukraine Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_ukr.py`, `tests/test_fed_ukr.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `ukr`, SOURCE: `ukr_fencing`, COUNTRY: `UKR`
- Probe URL: `fencing.ua` or `nffu.gov.ua`
- Try: `/reyting`, `/rankings`, `/zmahannya/reyting`
- Language: Ukrainian (Cyrillic). Column headers: Місце, Ім'я, Клуб, Очки
- Ukrainian Cyrillic: і, ї, є, ґ (different from Russian)
- May be slow or intermittently accessible — add retry logic (3 retries with backoff)

**Success criteria:** Ukraine rankings parse Ukrainian Cyrillic rows with retry/backoff, write public combos, and pass parser tests.

**Output format:**
```
Files: scrape_fed_ukr.py, tests/test_fed_ukr.py
Combos working: X/12
Retries/backoff: implemented yes/no
Tests: pytest tests/test_fed_ukr.py -v
```

---

## Agent 13 — Romania Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_rou.py`, `tests/test_fed_rou.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `rou`, SOURCE: `rou_fencing`, COUNTRY: `ROU`
- Probe URL: `federatia-de-scrima.ro`
- Try: `/clasamente`, `/rankinguri`, `/rezultate/clasament`
- Language: Romanian. Column headers: Loc, Nume, Club, Puncte
- Romanian chars: ă, â, î, ș, ț

**Success criteria:** Romania rankings parse Romanian headers/characters, write public combos through the common writer, and pass parser tests.

**Output format:**
```
Files: scrape_fed_rou.py, tests/test_fed_rou.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_rou.py -v
```

---

## Agent 14 — Spain Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_esp.py`, `tests/test_fed_esp.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `esp`, SOURCE: `esp_fencing`, COUNTRY: `ESP`
- Probe URL: `rfeespada.es`
- Try: `/ranking`, `/clasificaciones`, `/rankings`
- Language: Spanish. Column headers: Puesto, Nombre, Club, Puntos
- Spanish chars: á, é, í, ó, ú, ü, ñ

**Success criteria:** Spain rankings parse Spanish headers/characters, normalize points, write public combos, and pass parser tests.

**Output format:**
```
Files: scrape_fed_esp.py, tests/test_fed_esp.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_esp.py -v
```

---

## Agent 15 — Egypt Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_egy.py`, `tests/test_fed_egy.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `egy`, SOURCE: `egy_fencing`, COUNTRY: `EGY`
- Probe URL: `egfencing.com`
- Bilingual (English + Arabic). Column headers in either language:
  - English: Rank, Name, Club, Points
  - Arabic: المركز, الاسم, النادي, النقاط
- Arabic range: \u0600-\u06FF (right-to-left text)
- May use PDF. If so, add `pdfplumber` to requirements.txt.
- Name handling: Arabic script. Store as-is.

**Success criteria:** Egypt rankings parse English and/or Arabic rows, preserve RTL names, write available public combos, and pass tests with Arabic fixtures.

**Output format:**
```
Files: scrape_fed_egy.py, tests/test_fed_egy.py
Combos working: X/12
Language parsed: english/arabic/both/stub
Tests: pytest tests/test_fed_egy.py -v
```

---

## Agent 16 — USA Fencing FRED Results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fred.py`, `tests/test_scrape_fred.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
Build scraper for USA Fencing's new FRED platform (replaces AskFRED).

1. Read `askfred_scraper.py`, `scrape_results.py`, `scrape_olympics.py`.
2. Probe `https://fred.usafencing.org` or `fred.fencing.org`:
   - Check if results are public or login-required
   - Look for API endpoints (check browser network tab)
   - Document: base URL, auth needed, response format
3. If REST/GraphQL API found:
   - Write tests with fixture API responses
   - Implement: discover tournaments → fetch results → upsert
   - Upsert tournaments with `source_id: "fred:{event_id}"`
   - Upsert results with fencer matching (USA fencers → fs_fencers)
   - Fencer matching: name+country (USA), plus USA Fencing ID if available
4. If no public API (HTML only):
   - Use BeautifulSoup to parse tournament listing and results tables
   - Follow the same upsert pattern
5. If fully auth-walled:
   - Check if session cookie approach works
   - If not, create stub documenting what auth is needed

**Success criteria:**
- Scraper produces USA tournament results
- Tests pass with fixture API responses or HTML
- Fencer matching works for USA fencers

**When blocked:** FRED fully auth-walled with no public access → stub documenting the required API key or credentials

**Output format:**
```
Files: scrape_fred.py, tests/test_scrape_fred.py
API type: [REST/GraphQL/HTML/stub]
Auth required: yes/no — details
Tests: pytest tests/test_scrape_fred.py -v
```

---

## Agent 17 — Youth Olympics + World Fencing Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_youth_olympics.py`, `tests/test_scrape_youth_olympics.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia.org for Youth Olympic Games fencing events (2010, 2014, 2018, 2026). Editions may be under the main FEN sport code or filtered by edition name containing "Youth".
2. Probe FIE site or google for World Fencing Games 2023 Bali results.
3. Both follow the same pattern as `scrape_olympics.py`:
   - Discover events
   - Parse results tables (rank, name, country, medal)
   - Classify weapon, gender from event name
   - Upsert tournaments (`source_id: yog:{edition_id}:{event_code}` or `wfg:{year}:{event}`)
   - Upsert results with best-effort fencer matching
4. YOG has individual events only (no team events in early editions).
5. WFG may have a different format — adapt to what exists.

**Success criteria:** Both YOG and WFG results in DB. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 18 — Universiade / World University Fencing

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_universiade.py`, `tests/test_scrape_universiade.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia and `fisu.net` for Universiade fencing events (1957+). Olympedia has some editions.
2. Follow olympics scraper pattern: discover events → parse results → upsert.
3. Source ID: `universiade:{edition_id}:{event_code}`.
4. Season = edition year (not FIE season). The Universiade happens in July of the competition year.
5. Handle: team events, missing editions (not all Universiades had fencing).

**Success criteria:** Universiade fencing results in DB. Tests pass.

**When blocked:** If FISU pages are JS-rendered or incomplete, probe olympedia first, then official archive endpoints, then create a stub documenting missing editions.

**Output format:**
```
Files: scrape_universiade.py, tests/test_scrape_universiade.py
Editions found/imported: X/Y
Data source: olympedia/fisu/both/stub
Tests: pytest tests/test_scrape_universiade.py -v
```

---

## Agent 19 — Continental Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_continental_games.py`, `tests/test_scrape_continental_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
Single scraper covering 4 multi-sport Games:
1. Pan American Games (1951+): olympedia has these
2. Asian Games (1974+): olympedia has these
3. European Games (2015, 2019, 2023): olympedia or EOC site
4. African Games (1965+): olympedia or ANOCA site

Probe each on olympedia. Not all editions may be on olympedia — fall back to official Games websites.

Implement:
- Discover events per Games type and edition
- Parse results per event
- Classify weapon+gender from event name
- Upsert tournaments (`source_id: {type}:{edition_id}:{event_code}`)
- Upsert results

Write tests per Games type with fixture HTML.

**Success criteria:** All four Games types with available data are in DB. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 20 — NCAA Regular Season Results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_ncaa_regular.py`, `tests/test_scrape_ncaa_regular.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** Existing `scrape_ncaa.py`, `scrape_results.py`, `scrape_bouts.py`

**Task:**
1. Probe sources for NCAA regular season dual meet results:
   - `ncaa.escrimeresults.com` (may have more than just championships)
   - Individual school team pages (top programs: Harvard, Princeton, Notre Dame, Columbia, Penn State, Ohio State, St. John's, etc.)
   - Conference sites (Ivy League, ACC, Big Ten)
2. For each meet found:
   - Parse bout-by-bout: fencer name, opponent, score, weapon, decision (win/loss)
   - Create tournament record: "NCAA Regular Season: School A vs School B" with date
   - Upsert tournament to `fs_tournaments` (`source_id: ncaa_regular:{year}:{meet_id}`)
   - Upsert results per fencer to `fs_results`
   - Upsert bouts to `fs_bouts`
3. Focus on most recent 5 seasons. Skip 2020.
4. Fencer matching: name+country (USA) against `fs_fencers`

**Success criteria:** Regular season bout data for top-50 NCAA programs. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 21 — Youth/Junior Major Results

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_youth_majors.py`, `tests/test_scrape_youth_majors.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_fie_history.py`, `scrape_results.py`, `scrape_olympics.py`

**Task:**
1. Check which Cadet/Junior World Championship seasons are missing from `fs_tournaments`. The FIE history scraper covers many but may have gaps.
2. Probe FIE API for missing seasons (same API as `scrape_fie_history.py`).
3. Probe olympedia for EYOF (European Youth Olympic Festival) fencing events.
4. Implement:
   - Scrape missing Cadet/Junior World Championship seasons from FIE API
   - Scrape EYOF from olympedia
   - Upsert tournaments + results per existing patterns
   - Track done via `scraper_state`

**Success criteria:** No gaps in Cadet/Junior World Championship coverage. EYOF results added. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 22 — Head-to-Head Stats Engine

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_head_to_head.py`, `supabase/migrations/YYYYMMDD_head_to_head.sql`, `tests/test_head_to_head.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 4, 16–21 (for bout data)

**Read:** `scrape_bouts.py` for `fs_bouts` schema.

**Task:**
1. Design table:
```sql
CREATE TABLE fs_head_to_head (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_a_id uuid REFERENCES fs_fencers(id),
    fencer_b_id uuid REFERENCES fs_fencers(id),
    weapon text NOT NULL,
    a_wins integer DEFAULT 0,
    b_wins integer DEFAULT 0,
    a_touches integer DEFAULT 0,
    b_touches integer DEFAULT 0,
    bouts_total integer DEFAULT 0,
    last_meeting_date date,
    last_winner_id uuid REFERENCES fs_fencers(id),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (fencer_a_id, fencer_b_id, weapon)
);
```
2. Write SQL migration.
3. Write `compute_head_to_head.py`:
   - Query `fs_bouts` where both fencer IDs are non-null
   - Group canonical pair (lower UUID first) + weapon
   - Determine winner: if score_a > score_b → a_wins += 1
   - Aggregate: wins, touches, last meeting
   - Upsert to fs_head_to_head
   - Handle NULL scores (skip incomplete bouts)
4. Write tests: mock bout data, verify aggregation.

**Success criteria:** H2H table created and populated. `SELECT * FROM fs_head_to_head WHERE fencer_a_id = X` returns results. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 23 — Fencer Career Stats Aggregation

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_career_stats.py`, `supabase/migrations/YYYYMMDD_career_stats.sql`, `tests/test_career_stats.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 2, 16–21 (needs identity resolution + results data)

**Task:**
1. Design table:
```sql
CREATE TABLE fs_fencer_career_stats (
    fencer_id uuid PRIMARY KEY REFERENCES fs_fencers(id),
    total_competitions integer DEFAULT 0,
    gold_medals integer DEFAULT 0,
    silver_medals integer DEFAULT 0,
    bronze_medals integer DEFAULT 0,
    top8_count integer DEFAULT 0,
    best_rank integer,
    avg_rank numeric(5,2),
    worst_rank integer,
    weapons_used jsonb,
    categories_competed jsonb,
    first_season text,
    last_season text,
    total_touches_scored integer DEFAULT 0,
    total_touches_received integer DEFAULT 0,
    touch_differential integer DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Write `compute_career_stats.py`:
   - Aggregate `fs_results` by fencer_id: competition count, medals, ranks
   - Also aggregate touch data from `fs_bouts`
   - Use identity resolution (Agent 2) to group stats if available
   - Upsert per fencer
4. Write tests: mock results data, verify medal counts and averages.

**Success criteria:** Career stats for every fencer with results. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 24 — Rankings Trends + Points Projection

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_rankings_trends.py`, `supabase/migrations/YYYYMMDD_rankings_trends.sql`, `tests/test_rankings_trends.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 2 and existing `scrape_rankings_history.py` data; Agent 23 optional for downstream career stats integration

**Read:** `scrape_rankings_history.py`, `scrape_fie_career.py`

**Task:**
1. Design `fs_rankings_trends` table: fencer_id, weapon, category, season, rank, previous_rank, rank_change, points, previous_points, points_change, trend_direction ('up'/'down'/'stable'/'new'), projected_next_rank, projected_next_points.
2. Write SQL migration.
3. Write `compute_rankings_trends.py`:
   - Query `fs_rankings_history` ordered by fencer/weapon/category/season
   - For consecutive season pairs: compute delta rank, delta points
   - Trend direction: rank improved → 'up', declined → 'down', no change → 'stable', first appearance → 'new'
   - Points projection: 3-season weighted moving average (most recent season weighted 50%, previous 30%, oldest 20%)
   - Upsert to fs_rankings_trends
4. Write tests: mock rankings history with known changes.

**Success criteria:** Trends table populated with direction indicators. Projections computed. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 25 — Country Depth + Club Rankings

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_country_analytics.py`, `supabase/migrations/YYYYMMDD_country_club_rankings.sql`, `tests/test_country_analytics.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping

**Task:**
1. Design tables:
   - `fs_country_depth`: country, weapon, category, fencers_in_top16, fencers_in_top32, fencers_in_top64, total_ranked, avg_world_rank, updated_at — PK on (country, weapon, category)
   - `fs_club_rankings`: id, club, country, weapon, total_fencers, avg_rank, total_points, updated_at
2. Write SQL migration.
3. Write `compute_country_analytics.py`:
   - Country depth: query `fs_fencers` for world_rank buckets per country/weapon/category
   - Club rankings: query `fs_fencers` for club + world_rank, aggregate per club name
   - Club name normalization: lowercase, strip whitespace, handle variants
4. Write tests.

**Success criteria:** Country depth and club rankings populated. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 26 — Fencer Transfer Tracker

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_transfers.py`, `supabase/migrations/YYYYMMDD_transfers.sql`, `tests/test_transfers.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping; Agent 64 optional for Wikidata nationality cross-checks

**Task:**
1. Design `fs_fencer_transfers` table: id, fencer_id, from_country, to_country, season, competition_id, source, confirmed (boolean), metadata.
2. Write SQL migration.
3. Write `compute_transfers.py`:
   - Query `fs_rankings_history` for same fencer_id, different country in consecutive seasons → transfer
   - Query `fs_results` for same fencer_id, different country within same season (flag as uncertain)
   - Insert transfers
   - If Agent 64 (nationality history from Wikidata) is done, cross-reference
4. Write tests: mock rankings history with known transfers.

**Success criteria:** Transfer database populated. Tests pass.

**Output format:**
```
Files: compute_transfers.py, supabase/migrations/YYYYMMDD_transfers.sql, tests/test_transfers.py
Confirmed transfers found: X
Uncertain transfers found: Y
Tests: pytest tests/test_transfers.py -v
```

---

## Agent 27 — Wikipedia Bio Text Enrichment

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_wikipedia_bios.py`, `supabase/migrations/YYYYMMDD_wikipedia_bios.sql`, `tests/test_scrape_wikipedia_bios.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping

**Read:** `scrape_wikidata.py`

**Task:**
1. Write SQL migration adding nullable columns to `fs_fencers`: `bio_text` (text), `wikipedia_url` (text), `birth_place` (text), `nickname` (text), `height` (text), `weight` (text) only if they do not already exist.
2. Write `scrape_wikipedia_bios.py`:
   - Query `fs_fencers WHERE metadata->>'wikidata_id' IS NOT NULL AND bio_text IS NULL`
   - For each, get Wikipedia page title from Wikidata ID:
     `GET https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&titles=Q{wikidata_id}&format=json`
   - Get page summary:
     `GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}`
   - Extract: `extract` (first paragraph), `page_url`, `content_urls.desktop.page`
   - Also extract birth place from Wikipedia infobox if available (can be found in `pageprops` or from parsing the extract)
   - Choose language based on fencer nationality:
     - FRA → fr.wikipedia.org, ITA → it.wikipedia.org, GER → de.wikipedia.org, etc.
     - Fall back to English always
   - Update `fs_fencers` row
   - Rate limit: 1 req/sec
   - Incremental via scraper_state: track last_fencer_id processed
3. Write tests: mock Wikipedia API responses, verify extraction.

**Success criteria:** 2000+ fencers with bio text. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 28 — Fencer Social Media Presence

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_social_media.py`, `supabase/migrations/YYYYMMDD_social_media.sql`, `tests/test_social_media.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping

**Read:** `scrape_wikidata.py` for SPARQL pattern.

**Task:**
1. Design table:
```sql
CREATE TABLE fs_fencer_social_media (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    platform text NOT NULL CHECK (platform IN ('instagram', 'twitter', 'youtube', 'tiktok', 'facebook', 'threads', 'other')),
    handle text,
    url text NOT NULL,
    source text DEFAULT 'wikidata',
    verified boolean DEFAULT false,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    UNIQUE (fencer_id, platform)
);
```
2. Write SQL migration.
3. Write `scrape_social_media.py`:
   - Pass 1: SPARQL Wikidata for social properties (P2003, P2002, P2397, P7085, P2013)
   - Match Wikidata fencers to `fs_fencers` by `fie_id` via `metadata.wikidata_id`
   - Pass 2: scrape federation profiles for social links
   - Upsert to social media table
   - Incremental via scraper_state
4. Write tests: mock SPARQL responses, federation profile HTML.

**Success criteria:** Social media links for fencers across all platforms. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 29 — Fencer Media Pipeline

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/download_headshots.py`, `tests/test_download_headshots.py`, `requirements.txt`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping

**Task:**
1. Add `Pillow` to requirements.txt.
2. Write `scripts/download_headshots.py`:
   - Query `fs_fencers WHERE headshot_url IS NOT NULL AND (local_image_path IS NULL OR local_image_path = '')`
   - For each: download image, verify content-type is image, resize to 400×400 (center crop), upload to Supabase Storage bucket `fencer-headshots`
   - Update `fs_fencers.local_image_path` with the Storage public URL
   - If Supabase Storage not configured, save to local `headshots/` directory
   - Rate limit: 1 req/sec for external downloads
3. YouTube match video discovery:
   - If `YOUTUBE_API_KEY` env var is set:
     - Search "fencing {fencer_name}" for top-100 ranked fencers
     - Store video IDs in `metadata->>'youtube_videos'`
   - If not set: document the limitation in a comment
4. Handle: failed downloads (403, 404), non-image URLs, rate limits, Commons file deletions

**Success criteria:** Fencer headshots downloaded and stored locally/on Storage. Tests pass (mock downloads).

**Output format:**
```
Files: scripts/download_headshots.py, tests/test_download_headshots.py, requirements.txt
Storage mode: supabase/local
Images processed on mock run: X
Tests: pytest tests/test_download_headshots.py -v
```

---

## Agent 30 — Equipment & Brand Data

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_equipment.py`, `supabase/migrations/YYYYMMDD_equipment.sql`, `tests/test_equipment.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping and Agent 27 optional for bio text scanning

**Task:**
1. Design table:
```sql
CREATE TABLE fs_fencer_equipment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    brand text NOT NULL,
    equipment_type text,
    sponsor_name text,
    source text,
    source_url text,
    confidence text DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
```
2. Known fencing brands: Allstar, Uhlmann, Leon Paul, Prieur, Absolute Fencing, Negrini, FWF, Carmimari, Blaise Frères, Triplette, Versari, Favero, LP, SG, OK, Dynamo, PBT, Blue Gauntlet, AF, Victory, Wuxi.
3. Write `scrape_equipment.py`:
   - Source 1: FIE athlete profiles — reuse/extend `scrape_athlete_profiles.py` to check for brand mentions in profile text
   - Source 2: Wikipedia — check bio_text (from Agent 27) for brand names near fencer name
   - Source 3: Federation profiles — scrape for "sponsored by" sections
   - Text pattern: brand name mentioned near fencer name in content → extract and store
   - For each match: store fencer_id, brand, equipment_type (if identifiable: "weapon", "mask", "jacket", or NULL for general sponsorship)
4. Write tests: fixture texts with known equipment mentions.

**Success criteria:** Equipment/sponsor data for fencers. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 31 — Paralympic Games Fencing

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_paralympics.py`, `tests/test_scrape_paralympics.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia for Paralympic fencing (sport code may differ from FEN — try `WHEELCHAIR_FENCING` or similar). Also check `paralympic.org/fencing`.
2. Follow olympics scraper pattern:
   - Discover events by Paralympic edition (1980 Roma → 2024 Paris)
   - Parse results tables (rank, name, country, medal, classification A/B/C)
   - Classify: weapon, gender, disability class from event name (e.g., "Men's Foil Individual A")
   - Upsert tournaments (`source_id: paralympics:{edition_id}:{event_code}`)
   - Upsert results with fencer matching against `fs_fencers`
3. Handle: classification system (A=minimal impairment, B=moderate, C=severe) in event naming

**Success criteria:** Paralympic fencing history in DB. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 32 — Fencing News + Injury/Absence Tracker

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_news.py`, `supabase/migrations/YYYYMMDD_news.sql`, `tests/test_news.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
1. Design table:
```sql
CREATE TABLE fs_articles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text UNIQUE NOT NULL,
    source text NOT NULL,
    source_site text NOT NULL,
    published_at timestamptz,
    category text NOT NULL CHECK (category IN ('competition_report', 'injury', 'transfer', 'rule_change', 'general')),
    summary text,
    related_fencer_ids uuid[],
    content_hash text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Write `scrape_news.py`:
   - Sources:
     - FIE news: `https://fie.org/articles` — RSS or HTML listing
     - British Fencing news: `britishfencing.com/news`
     - (More sources can be added later)
   - For each source:
     - Fetch article list
     - For each article: fetch full text, extract title+date+body
     - Classify by keyword presence:
       - "injury" / "sidelined" / "surgery" / "recovery" → injury
       - "transfer" / "switches" / "new country" / "naturalized" → transfer
       - "rule change" / "new format" / "FIE Congress" → rule_change
       - Has tournament name + result word → competition_report
       - Default → general
     - Extract fencer names: check if any known fencer name appears in the article text
     - Upsert by URL (ignore duplicates)
4. Write tests: fixture articles, test classification accuracy.

**Success criteria:** News article database with categorized entries. Injury/transfer tracking. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 33 — Fencer Name Variant Database

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_name_variants.py`, `supabase/migrations/YYYYMMDD_name_variants.sql`, `tests/test_name_variants.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 (identity resolution)

**Task:**
1. Design table:
```sql
CREATE TABLE fs_fencer_name_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid NOT NULL,
    name text NOT NULL,
    script text NOT NULL CHECK (script IN ('Latin', 'Hangul', 'Cyrillic', 'CJK', 'Arabic', 'Other')),
    source text NOT NULL,
    country text,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_fencer_name_variants_fencer ON fs_fencer_name_variants(fencer_id);
CREATE INDEX idx_fencer_name_variants_name ON fs_fencer_name_variants(name);
```
2. Write SQL migration.
3. Write `compute_name_variants.py`:
   - Collect names from: `fs_fencers.name`, `fs_results.name`, `fs_national_fed_rankings.name`
   - Per fencer identity (use Agent 2's `fs_fencer_identities`)
   - Detect script via Unicode ranges:
     - Hangul: \uAC00-\uD7AF
     - CJK: \u4E00-\u9FFF
     - Cyrillic: \u0400-\u04FF
     - Arabic: \u0600-\u06FF
     - If none match: Latin. If no Latin chars either: Other.
   - Store each unique (fencer_id, name, script)
4. Write tests: mock names in multiple scripts, verify detection per script.

**Success criteria:** Name variant database populated. Multi-script grouping works. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 34 — Venue / Location Geocoding

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `enrich_locations.py`, `supabase/migrations/YYYYMMDD_venues.sql`, `tests/test_venues.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (tournament data populated)

**Task:**
1. Design `fs_venues` table: id, name, city, country, latitude, longitude, country_code, competitions_count, metadata, created_at. UNIQUE on (name, city, country).
2. Write SQL migration.
3. Write `enrich_locations.py`:
   - Query distinct `city` + `country` from `fs_tournaments` where both non-null
   - For each: geocode via OpenStreetMap Nominatim API (free, 1 req/sec, needs User-Agent)
     - `GET https://nominatim.openstreetmap.org/search?q={city}+{country}&format=json&limit=1`
   - Extract lat/lon from response
   - Determine country_code from response address
   - Attempt to extract venue name from tournament name:
     - If tournament name contains " - " → venue might be after the dash
     - If tournament name matches known venue → extract
     - Otherwise → venue name = city (generic)
   - Store in fs_venues
   - Link competitions to venue via `metadata->>'venue_id'` on tournament
   - Incremental: skip cities already processed
4. Write tests: mock Nominatim API responses, verify extraction.
5. Handle: rate limits (sleep 1s between requests), ungeocodable locations, multiple competitions at same venue

**Success criteria:** Geocoded venue database. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 35 — Live Results Watcher

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `watch_live_results.py`, `tests/test_live_results.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_results.py`, `scrape_bouts.py`

**Task:**
1. Write `watch_live_results.py`:
   - Query active tournaments: `fs_tournaments WHERE start_date <= today AND end_date >= (today - 2) AND competition_url_id IS NOT NULL`
   - For each active tournament:
     - Get `last_checked` timestamp from `scraper_state('live_watcher', f'last_checked_{tournament_id}')`
     - Fetch competition results page (same endpoint as `scrape_results.py`)
     - Parse results
     - Compare with previously stored results (store result hashes in scraper_state)
     - Upsert new results and bouts only (don't delete+reinsert — only add new ones)
     - Update `last_checked` timestamp
   - Designed for 15-min execution frequency:
     - Exit quickly if no active tournaments
     - Only process tournaments within their active window + 1 day buffer
     - Log: tournaments checked, new results found, tourn IDs
2. Write tests: mock FIE API with scenario where new results appear between checks.

**Success criteria:** Watcher detects and upserts new results for active tournaments. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 36 — Referee & Coach Data

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_referees.py`, `scrape_coaches.py`, `tests/test_referees.py`, `supabase/migrations/YYYYMMDD_referees.sql`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Task:**
1. Design tables:
```sql
CREATE TABLE fs_referees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    fie_license_id text UNIQUE,
    category text,
    certification_level text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
CREATE TABLE fs_coaches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country text,
    federation text,
    national_team_role text,
    weapons text[],
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
CREATE TABLE fs_fencer_coach_relationship (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fencer_id uuid REFERENCES fs_fencers(id),
    coach_id uuid REFERENCES fs_coaches(id),
    start_date date,
    end_date date,
    current boolean DEFAULT true,
    metadata jsonb DEFAULT '{}',
    UNIQUE (fencer_id, coach_id)
);
```
2. Write SQL migration.
3. Write `scrape_referees.py`:
   - Probe FIE website for referee list (try `fie.org/referees` or `fie.org/commissions`)
   - Parse table or list: name, country, category, license ID
   - Handle: may be a PDF (parse with pdfplumber) or HTML table
4. Write `scrape_coaches.py`:
   - For top-20 federations: find "national team" or "coaching staff" page
   - Parse coaching staff per weapon
   - If fencer-coach relationships stated, store in relationship table
5. Write tests: fixture referee list HTML, coach profile pages.

**Success criteria:** Referee database + national team coaches. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 37 — FIE Competition URL ID Discovery

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `discover_competition_urls.py`, `tests/test_discover_urls.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_results.py` for the URL discovery logic embedded within it.

**Task:**
1. Extract the URL discovery logic from `scrape_results.py` into standalone `discover_competition_urls.py`.
2. The script should:
   - Query `fs_tournaments WHERE competition_url_id IS NULL AND fie_id IS NOT NULL AND has_results = true`
   - For each, call FIE competition detail page to find the URL ID
   - The URL ID is typically in the competition page URL (e.g., `/competitions/123` → URL ID is `123`)
   - Update `fs_tournaments SET competition_url_id = X WHERE id = Y`
   - Rate limit: 1 req/sec
   - Incremental: only process tournaments without URL ID
3. Write tests: mock FIE API responses with URL ID data.
4. **This must run BEFORE Agent 16–21 (results scrapers) in CI ordering.**

**Success criteria:** Populates competition_url_id for tournaments missing it. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 38 — Data Quality Automation

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/data_quality_check.py`, `supabase/migrations/YYYYMMDD_coverage_views.sql`, `tests/test_data_quality_check.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Scraper run logging tables must exist; run after the main scraper agents have produced data

**Task:**
1. Write SQL migration creating materialized views:
   - `v_fencer_source_coverage`: source name, fencer count — UNION of counts from each source table
   - `v_scraper_health`: module, status, started_at, completed_at, written, failed, skipped from `fs_scraper_runs` (last 7 days)
   - `v_orphan_results`: tournament type, orphan count — `fs_results` with NULL fencer_id grouped by tournament type
   - `v_stale_sources`: module, last_run — modules whose last success was > 48h ago
2. Write `scripts/data_quality_check.py`:
   - Refresh all materialized views
   - Check each view for anomalies:
     - Zero fencers from any source that should have data
     - All scrapers stale (critical: pipeline down)
     - Orphan count increased > 20% since last check (store last count in scraper_state)
   - Print report: view name, row count, any warnings
   - Exit code: 0 = healthy, 1 = warnings, 2 = critical failure
3. Write tests with mocked Supabase/query layer:
   - Healthy views → exit code 0
   - Stale all-scraper condition → exit code 2
   - Orphan count increase > 20% → exit code 1
   - Materialized view refresh failure → exit code 2 with clear message

**Success criteria:** Views created. Check script reports status with deterministic exit codes. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 39 — Export API + CLI

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `api.py` (FastAPI), `cli_export.py`, `docs/api.yaml`, `tests/test_api.py`, `tests/test_cli_export.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Analytics and enrichment tables should exist before exposing API fields that depend on them

**Task:**
1. Write OpenAPI 3.0 spec (`docs/api.yaml`) with endpoints:
   - `GET /fencer/{id}` — profile + career stats + social + equipment
   - `GET /fencer/search?name=&country=&weapon=` — search with pagination
   - `GET /tournaments?season=&type=&country=&limit=&offset=` — list
   - `GET /tournaments/{id}/results` — results for a tournament
   - `GET /rankings?season=&weapon=&gender=&category=` — rankings
   - `GET /h2h/{fencer_a}/{fencer_b}` — head-to-head stats
   - `GET /countries/{code}/depth` — country depth analysis
   - Security: API Key header (X-API-Key)
   - Pagination: ?limit=50&offset=0
   - Response format: JSON
2. Write `api.py` (FastAPI):
   - Routes for all endpoints
   - Supabase client for DB queries
   - API key auth middleware (check against `fs_api_keys` table or env var)
   - Rate limiting: 100 req/min per key
   - CORS enabled
   - Read-only (no POST/PUT/DELETE)
   - Built-in pagination
3. Write `cli_export.py`:
```bash
python cli_export.py fencers --format json --output fencers.json
python cli_export.py tournaments --season 2026 --format csv
python cli_export.py rankings --weapon Epee --gender Men
python cli_export.py h2h --fencer <id> --min-bouts 5
```
   - Supports JSON and CSV output
   - Paginates large results automatically
   - Progress indicator for large exports
4. Write tests:
   - FastAPI TestClient covers auth failure, pagination, and one happy path for each endpoint
   - CLI tests mock Supabase pagination and verify JSON/CSV output

**Success criteria:** FastAPI server starts. All endpoints return data. CLI exports to JSON and CSV. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 40 — Netherlands Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_ned.py`, `tests/test_fed_ned.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `ned`, SOURCE: `ned_fencing`, COUNTRY: `NED`
- Probe URL: `knfb.nl`
- Try: `/ranglijsten`, `/wedstrijdsport/ranglijsten`, `/rankings`, `/ranking`
- Language: Dutch. Column headers: Plaats, Naam, Vereniging, Punten
- Club field may be called `Vereniging` or `Club`; normalize both to `club`
- Preserve Dutch particles in names (`van`, `de`, `van der`); do not title-case names
- If rankings are PDF or Excel downloads, add the smallest parser dependency and fixture test for that format

**Success criteria:** All public Netherlands ranking combos are attempted, unavailable combos skip cleanly, tests pass.

**Output format:**
```
Files: scrape_fed_ned.py, tests/test_fed_ned.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_ned.py -v
```

---

## Agent 41 — Belgium Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_bel.py`, `tests/test_fed_bel.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `bel`, SOURCE: `bel_fencing`, COUNTRY: `BEL`
- Probe URL: `fencing-belgium.be`
- Try public pages for FBB/BFF/Ligue francophone/Vlaamse schermbond rankings
- Languages: Dutch, French, German. Headers may be Rang, Classement, Plaats, Name, Naam, Nom, Club, Punten, Points
- Federation may split rankings by language community; merge rows into one BEL source while preserving `metadata.language` and `metadata.sub_federation`
- Handle Belgian names with apostrophes and particles; do not strip accents
- If only regional ranking pages exist, implement both regions and deduplicate by normalized name+club+weapon+category

**Success criteria:** Belgium rankings are written from every public regional or national source found, tests cover trilingual headers.

**Output format:**
```
Files: scrape_fed_bel.py, tests/test_fed_bel.py
Combos working: X/12
Regional sources: [list]
Stub: yes/no
Tests: pytest tests/test_fed_bel.py -v
```

---

## Agent 42 — Switzerland Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_sui.py`, `tests/test_fed_sui.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `sui`, SOURCE: `sui_fencing`, COUNTRY: `SUI`
- Probe URL: `swiss-fencing.ch`
- Try: `/classements`, `/rankings`, `/ranglisten`, `/ranking`
- Languages: German, French, Italian. Headers may be Rang, Platz, Classement, Pos, Name, Nom, Nome, Verein, Club, Societa, Punkte, Points, Punti
- Swiss pages may include downloadable PDFs/Excel files; prefer structured downloads over brittle rendered tables
- Preserve accented Latin names and club names; do not transliterate
- Store source language and file URL in `metadata`

**Success criteria:** Switzerland rankings parse in at least one official language path or produce a clear stub if no public data exists.

**Output format:**
```
Files: scrape_fed_sui.py, tests/test_fed_sui.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_sui.py -v
```

---

## Agent 43 — Austria Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_aut.py`, `tests/test_fed_aut.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `aut`, SOURCE: `aut_fencing`, COUNTRY: `AUT`
- Probe URL: `fencing.at`
- Try: `/rangliste`, `/ranglisten`, `/leistungssport/ranglisten`, `/ranking`
- Language: German. Column headers: Platz, Rang, Name, Verein, Punkte
- Handle German characters: ä, ö, ü, ß
- Austria may publish separate age-group lists; implement Senior, Junior, Cadet if public
- If points use comma decimals, convert to numeric floats

**Success criteria:** Austria rankings write clean rows via `fed_rankings_common.write_rankings()`, tests cover German headers and comma decimals.

**Output format:**
```
Files: scrape_fed_aut.py, tests/test_fed_aut.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_aut.py -v
```

---

## Agent 44 — Sweden Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_swe.py`, `tests/test_fed_swe.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `swe`, SOURCE: `swe_fencing`, COUNTRY: `SWE`
- Probe URL: `swefencing.se`
- Try: `/rankning`, `/ranking`, `/resultat/ranking`, `/tavling/ranking`
- Language: Swedish. Column headers: Placering, Rank, Namn, Förening, Klubb, Poäng
- Handle Swedish characters: å, ä, ö
- Swedish rankings may be season PDFs; if PDF, use `pdfplumber` only if tables are extractable
- Store edition/date of the ranking page in `metadata.ranking_date` when visible

**Success criteria:** Sweden rankings attempt all available weapon/gender/category combos and tests cover Swedish header variants.

**Output format:**
```
Files: scrape_fed_swe.py, tests/test_fed_swe.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_swe.py -v
```

---

## Agent 45 — Denmark Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_den.py`, `tests/test_fed_den.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `den`, SOURCE: `den_fencing`, COUNTRY: `DEN`
- Probe URL: `fencing.dk`
- Try: `/ranglister`, `/ranking`, `/resultater/rangliste`
- Language: Danish. Column headers: Plads, Placering, Navn, Klub, Point, Points
- Handle Danish characters: æ, ø, å
- If ranking files are linked from news posts, implement link discovery from the ranking/news index before fetching files
- Missing categories should be skipped with a logged reason, not treated as script failure

**Success criteria:** Denmark rankings parse from the current public source or a stub documents why no public rankings are available.

**Output format:**
```
Files: scrape_fed_den.py, tests/test_fed_den.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_den.py -v
```

---

## Agent 46 — Norway Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_nor.py`, `tests/test_fed_nor.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `nor`, SOURCE: `nor_fencing`, COUNTRY: `NOR`
- Probe URL: `fencing.no`
- Try: `/ranking`, `/rangering`, `/resultater`, `/terminliste/ranking`
- Language: Norwegian. Column headers: Plass, Rangering, Navn, Klubb, Poeng
- Handle Norwegian characters: æ, ø, å
- Norway may publish limited ranking depth; store whatever public rows exist and report combo coverage
- If source uses embedded Google Sheets, fetch the CSV/export endpoint rather than scraping rendered HTML

**Success criteria:** Norway rankings parse for all public lists found; tests include Norwegian headers and embedded-sheet fixture if applicable.

**Output format:**
```
Files: scrape_fed_nor.py, tests/test_fed_nor.py
Combos working: X/12
Data format: html/sheet/pdf/stub
Tests: pytest tests/test_fed_nor.py -v
```

---

## Agent 47 — Finland Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_fin.py`, `tests/test_fed_fin.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `fin`, SOURCE: `fin_fencing`, COUNTRY: `FIN`
- Probe URL: `fencing.fi`
- Try: `/ranking`, `/rankingit`, `/kilpailu/ranking`, `/tulokset`
- Language: Finnish. Column headers: Sija, Nimi, Seura, Pisteet
- Handle Finnish characters: ä, ö, å
- Some Finnish pages may combine gender/category in one table; split rows only when the page identifies category/gender reliably
- Store uncertain inferred fields in metadata and skip rows that cannot map to a known weapon/gender/category

**Success criteria:** Finland rankings parse with explicit weapon/gender/category mapping and tests cover combined-table parsing.

**Output format:**
```
Files: scrape_fed_fin.py, tests/test_fed_fin.py
Combos working: X/12
Inferred combos: [list]
Tests: pytest tests/test_fed_fin.py -v
```

---

## Agent 48 — Australia Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_aus.py`, `tests/test_fed_aus.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `aus`, SOURCE: `aus_fencing`, COUNTRY: `AUS`
- Probe URL: `ausfencing.org`
- Try: `/rankings`, `/results`, `/national-rankings`, `/events/results`
- Language: English. Column headers: Rank, Name, State, Club, Points
- State may be present instead of club; store state in `metadata.state` and club when available
- Australia may publish CSV/XLS ranking files; prefer direct downloads over page scraping
- Preserve season source value and normalize with `season_utils.normalize_season`

**Success criteria:** Australia rankings parse from public national rankings with state/club handling, tests pass.

**Output format:**
```
Files: scrape_fed_aus.py, tests/test_fed_aus.py
Combos working: X/12
Data format: html/csv/excel/stub
Tests: pytest tests/test_fed_aus.py -v
```

---

## Agent 49 — New Zealand Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_nzl.py`, `tests/test_fed_nzl.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `nzl`, SOURCE: `nzl_fencing`, COUNTRY: `NZL`
- Probe URL: `fencing.org.nz`
- Try: `/rankings`, `/results`, `/competitions/rankings`
- Language: English. Column headers: Rank, Name, Club, Region, Points
- Region may replace club; store region in `metadata.region`
- Ranking lists may be shallow or annual; implement incremental refresh without assuming all 12 combos exist
- If only PDF lists exist, add a table fixture test for the extraction path

**Success criteria:** New Zealand rankings write rows for all available public categories and skip missing categories clearly.

**Output format:**
```
Files: scrape_fed_nzl.py, tests/test_fed_nzl.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_nzl.py -v
```

---

## Agent 50 — Brazil Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_bra.py`, `tests/test_fed_bra.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `bra`, SOURCE: `bra_fencing`, COUNTRY: `BRA`
- Probe URL: `cbesgrima.org.br`
- Try: `/ranking`, `/rankings`, `/resultados`, `/competicoes/ranking`
- Language: Portuguese. Column headers: Posição, Pos., Nome, Clube, Pontos
- Handle Portuguese characters: á, â, ã, à, ç, é, ê, í, ó, ô, õ, ú
- Brazilian pages may use comma decimals and thousands separators; normalize points carefully
- If ranking pages require a season/year parameter, discover available years and default to current season

**Success criteria:** Brazil rankings parse with Portuguese headers and numeric normalization, tests pass.

**Output format:**
```
Files: scrape_fed_bra.py, tests/test_fed_bra.py
Combos working: X/12
Data format: html/pdf/excel/stub
Tests: pytest tests/test_fed_bra.py -v
```

---

## Agent 51 — Argentina Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_arg.py`, `tests/test_fed_arg.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `arg`, SOURCE: `arg_fencing`, COUNTRY: `ARG`
- Probe URL: `esgrima.org.ar`
- Try: `/ranking`, `/rankings`, `/clasificaciones`, `/resultados`
- Language: Spanish. Column headers: Puesto, Posición, Nombre, Club, Puntos
- Handle Spanish characters and particles; preserve full names as published
- Argentina may publish season PDFs/Excel sheets; prefer direct file parsing if linked
- Some ranking tables may use category names like Mayores, Juveniles, Cadetes; map to Senior, Junior, Cadet

**Success criteria:** Argentina rankings parse with Spanish category mapping, tests pass.

**Output format:**
```
Files: scrape_fed_arg.py, tests/test_fed_arg.py
Combos working: X/12
Category mappings: [list]
Tests: pytest tests/test_fed_arg.py -v
```

---

## Agent 52 — Hong Kong Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_hkg.py`, `tests/test_fed_hkg.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `hkg`, SOURCE: `hkg_fencing`, COUNTRY: `HKG`
- Probe URL: `fencing.org.hk`
- Try: `/ranking`, `/rankings`, `/competition/ranking`, `/en/ranking`, `/tc/ranking`
- Languages: English and Chinese. Headers may be Rank, Name, Club, Points, 排名, 姓名, 會, 會籍, 積分
- Preserve both English and Chinese names when present: store published display name in `name`, alternate script in `metadata.alt_name`
- Handle Traditional Chinese characters; do not simplify or romanize
- If the site offers bilingual pages, prefer English for stable field labels and Chinese for alternate names

**Success criteria:** Hong Kong rankings parse bilingual rows and tests cover English+Traditional Chinese headers.

**Output format:**
```
Files: scrape_fed_hkg.py, tests/test_fed_hkg.py
Combos working: X/12
Bilingual names: yes/no
Tests: pytest tests/test_fed_hkg.py -v
```

---

## Agent 53 — Singapore Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_sgp.py`, `tests/test_fed_sgp.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `sgp`, SOURCE: `sgp_fencing`, COUNTRY: `SGP`
- Probe URL: `fencing.org.sg`
- Try: `/rankings`, `/ranking`, `/high-performance/rankings`, `/competition-results`
- Language: English. Column headers: Rank, Name, Club, School, Points
- Singapore rankings may include school instead of club; store school in `metadata.school`
- If rankings are posted as PDFs, implement PDF extraction only for clearly tabular rankings
- Use conservative fencer matching; many junior/school names may collide

**Success criteria:** Singapore rankings parse current public lists, tests cover school/club column variants.

**Output format:**
```
Files: scrape_fed_sgp.py, tests/test_fed_sgp.py
Combos working: X/12
Stub: yes/no
Tests: pytest tests/test_fed_sgp.py -v
```

---

## Agent 54 — Israel Federation Scraper

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_fed_isr.py`, `tests/test_fed_isr.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 5 preferred for `season_utils.py`; if Agent 5 is not merged yet, implement a local `current_season()` fallback and keep the scraper compatible with `season_utils.normalize_season()` later.

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
4. Write `tests/test_fed_{cc}.py` with realistic fixtures from the probed source:
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

- CC: `isr`, SOURCE: `isr_fencing`, COUNTRY: `ISR`
- Probe URL: `fencing.org.il`
- Try Hebrew and English paths: `/ranking`, `/rankings`, `/he/ranking`, `/תחרויות`, `/דירוג`
- Languages: Hebrew and English. Headers may be מיקום, דירוג, שם, מועדון, נקודות, Rank, Name, Club, Points
- Hebrew text is right-to-left; preserve names as-is and do not reverse strings
- If both Hebrew and English names are present, store English in `metadata.latin_name` or Hebrew in `metadata.hebrew_name` depending on the display column
- Tests must include Hebrew fixture rows and ensure parser handles RTL text without lossy normalization

**Success criteria:** Israel rankings parse Hebrew/English public lists or produce a clear stub if no public rankings exist.

**Output format:**
```
Files: scrape_fed_isr.py, tests/test_fed_isr.py
Combos working: X/12
Language parsed: hebrew/english/both/stub
Tests: pytest tests/test_fed_isr.py -v
```

---

## Agent 55 — Commonwealth Fencing Championships

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_commonwealth.py`, `tests/test_scrape_commonwealth.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`, `scrape_continental_games.py` if Agent 19 exists

**Task:**
1. Probe `commonwealthfencing.org` and olympedia for Commonwealth Fencing Championships results.
2. Follow olympics scraper pattern:
   - Discover events by edition and distinguish Commonwealth Games from standalone Commonwealth Championships
   - Parse results tables (rank, name, country, medal)
   - Classify weapon+gender from event name
   - Upsert tournaments (`source_id: commonwealth:{edition_id}:{event_code}`)
   - Upsert results with best-effort fencer matching by FIE ID first, then name+country
3. If not on olympedia, check the official Commonwealth Fencing website directly.
4. Write tests with fixture pages covering edition discovery, event classification, medal parsing, and no-data pages.

**When blocked:** If no structured public results exist, create a stub that logs the probed URLs and exits 0 without touching DB rows.

**Success criteria:** Commonwealth fencing results are inserted where public data exists; tests pass.

**Output format:**
```
Files: scrape_commonwealth.py, tests/test_scrape_commonwealth.py
Sources working: [list]
Editions found: X
Tests: pytest tests/test_scrape_commonwealth.py -v
```

---

## Agent 56 — CISM World Military Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_cism.py`, `tests/test_cism.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe `milsport.one` or olympedia for CISM World Military Games fencing results.
2. Follow olympics scraper pattern: discover editions, discover fencing events, parse result rows, classify weapon/gender/team/individual, upsert tournaments and results.
3. Handle French and English event names (`fleuret`, `epee`, `sabre`, `hommes`, `dames`) and store original event title in metadata.
4. Use source ID: `cism:{edition_id}:{event_code}`.
5. Write tests for bilingual event classification, result-row parsing, and empty/missing edition pages.

**When blocked:** If CISM pages are PDF-only, parse only tables that can be extracted reliably; otherwise create a stub with documented URLs.

**Success criteria:** Military Games fencing results are imported for structured public editions; tests pass.

**Output format:**
```
Files: scrape_cism.py, tests/test_cism.py
Editions found: X
Data format: html/pdf/stub
Tests: pytest tests/test_cism.py -v
```

---

## Agent 57 — Mediterranean Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_mediterranean_games.py`, `tests/test_mediterranean_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia for Mediterranean Games fencing (1951 Alexandria onwards).
2. Probe official Mediterranean Games result pages if olympedia coverage is incomplete.
3. Follow olympics scraper pattern: discover editions/events, parse ranks/names/countries/medals, classify weapon+gender, upsert tournaments and results.
4. Use source ID: `mediterranean:{edition_id}:{event_code}`.
5. Write tests for edition discovery, event title classification, medal parsing, and missing result tables.

**When blocked:** If early editions only have unstructured prose, skip those editions with a warning and continue structured editions.

**Success criteria:** Mediterranean Games fencing results are imported for structured public editions; tests pass.

**Output format:**
```
Files: scrape_mediterranean_games.py, tests/test_mediterranean_games.py
Editions found/imported: X/Y
Skipped editions: [list with reason]
Tests: pytest tests/test_mediterranean_games.py -v
```

---

## Agent 58 — Maccabiah Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_maccabiah.py`, `tests/test_scrape_maccabiah.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia and `maccabiah.com` for Maccabiah Games fencing results.
2. Follow olympics scraper pattern: discover editions, classify fencing events, parse results, upsert tournaments/results.
3. Use source ID: `maccabiah:{edition_id}:{event_code}`.
4. Handle Hebrew/English event titles if official pages are bilingual; preserve original title in metadata.
5. Write tests for olympedia-like tables, official-site table rows, and no-results pages.

**When blocked:** If results are only in PDFs or images, parse extractable PDF tables; otherwise create a stub that documents source limitations.

**Success criteria:** Maccabiah fencing results import where public structured data exists; tests pass.

**Output format:**
```
Files: scrape_maccabiah.py, tests/test_scrape_maccabiah.py
Sources working: [list]
Data format: html/pdf/stub
Tests: pytest tests/test_scrape_maccabiah.py -v
```

---

## Agent 59 — World Masters Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_masters_games.py`, `tests/test_scrape_masters_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe `imga.ch` and olympedia for World Masters Games veteran fencing results.
2. Follow olympics scraper pattern but preserve veteran category/age band from event names (`V40`, `V50`, `Veteran`, `Masters`, age-group labels).
3. Parse result rows with rank, name, country, medal, weapon, gender, and age category.
4. Use source ID: `masters:{edition_id}:{event_code}`.
5. Write tests for veteran age-category extraction and result parsing.

**When blocked:** If IMGA exposes only PDFs, parse extractable tables and skip image-only pages with a warning.

**Success criteria:** Masters Games veteran fencing results are imported with age category metadata; tests pass.

**Output format:**
```
Files: scrape_masters_games.py, tests/test_scrape_masters_games.py
Age categories parsed: yes/no
Data format: html/pdf/stub
Tests: pytest tests/test_scrape_masters_games.py -v
```

---

## Agent 60 — South American Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_south_american_games.py`, `tests/test_scrape_south_american_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`, potentially `scrape_continental_games.py` (Agent 19)

**Task:**
1. Probe olympedia and `odesur.org` for ODESUR South American Games fencing (1978+).
2. Follow olympics/continental-games scraper pattern: edition discovery, event discovery, result-row parsing, weapon/gender classification, tournament/result upsert.
3. Use source ID: `south_american_games:{edition_id}:{event_code}`.
4. Handle Spanish and Portuguese event labels (`espada`, `florete`, `sable`, `masculino`, `femenino`).
5. Write tests for multilingual event classification and result rows.

**When blocked:** If ODESUR pages are JS-rendered, search for embedded JSON/XHR endpoints before falling back to a documented stub.

**Success criteria:** South American Games fencing results import for public structured editions; tests pass.

**Output format:**
```
Files: scrape_south_american_games.py, tests/test_scrape_south_american_games.py
Editions found/imported: X/Y
Language labels handled: spanish/portuguese/both
Tests: pytest tests/test_scrape_south_american_games.py -v
```

---

## Agent 61 — Central American & Caribbean Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_cac_games.py`, `tests/test_scrape_cac_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe olympedia for CAC Games fencing (1938+).
2. Probe official Central American & Caribbean Games result archives for missing olympedia editions.
3. Follow olympics scraper pattern: discover events, parse results, classify weapon/gender/team, upsert tournaments/results.
4. Use source ID: `cac_games:{edition_id}:{event_code}`.
5. Write tests for Spanish event labels, medal parsing, and missing early-edition data.

**When blocked:** Skip unstructured early editions with a logged reason and continue later structured editions.

**Success criteria:** CAC Games fencing results are imported for structured public editions; tests pass.

**Output format:**
```
Files: scrape_cac_games.py, tests/test_scrape_cac_games.py
Editions found/imported: X/Y
Skipped editions: [list with reason]
Tests: pytest tests/test_scrape_cac_games.py -v
```

---

## Agent 62 — Island Games / Oceania Games

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_island_games.py`, `tests/test_scrape_island_games.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Read:** `scrape_olympics.py`

**Task:**
1. Probe `islandgames.net`, olympedia, and Oceania Fencing Confederation for Island Games fencing results and Oceania Zonal Championships.
2. Follow olympics scraper pattern for Island Games editions and a simpler year/event pattern for Oceania Zonal Championships.
3. Parse result rows with rank, name, country/island, medal, weapon, gender, and age/category if present.
4. Use source IDs: `island_games:{edition_id}:{event_code}`, `oceania:{year}:{event_code}`.
5. Write tests for Island Games HTML tables, Oceania result pages, and no-data pages.

**When blocked:** If sources publish only PDFs, parse reliable PDF tables; if no public fencing results exist, create a stub with documented probes.

**Success criteria:** Island Games and Oceania fencing results import where structured public data exists; tests pass.

**Output format:**
```
Files: scrape_island_games.py, tests/test_scrape_island_games.py
Island Games editions: X
Oceania events: Y
Tests: pytest tests/test_scrape_island_games.py -v
```

---

## Agent 63 — Fencer Physical Stats

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_physical_stats.py`, `supabase/migrations/YYYYMMDD_physical_stats.sql`, `tests/test_scrape_physical_stats.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 (identity resolution — to know which fencers to look up)

**Task:**
1. Write SQL migration adding nullable `height`, `weight`, and `reach` columns to `fs_fencers` if they do not already exist.
2. Query fencers missing height/reach/weight fields in `fs_fencers`.
3. Source 1: FIE athlete profiles — read `scrape_athlete_profiles.py` and reuse/extend its logic. The FIE profile page often lists height and weight.
4. Source 2: Wikipedia infobox via REST API — same approach as Agent 27:
   - Parse infobox for `height`, `weight`, `reach` fields
5. For each fencer, if a source has the data, `UPDATE fs_fencers SET height = X, weight = Y, reach = Z WHERE id = ...`.
6. Update metadata: `metadata->>'height_source'`, `metadata->>'weight_source'`, `metadata->>'reach_source'`.

**Success criteria:** Height/weight data populated for fencers where available. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 64 — Fencer Nationality History

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `enrich_nationality_history.py`, `tests/test_nationality_history.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 (identity resolution)

**Read:** `scrape_wikidata.py` for SPARQL pattern.

**Task:**
1. Query Wikidata for fencers who have changed country of citizenship (multiple P27 statements for the same fencer at different times).
   - SPARQL: `?athlete wdt:P27 ?country . ?athlete p:P27 ?statement . ?statement pq:P580 ?start_time .`
2. For fencers with multiple nationalities, determine the sequence:
   - Use qualifier P580 (start time) and P582 (end time) on the citizenship statement
   - If no time qualifiers, store as unordered nationality list
3. Cross-reference with Agent 26 (Transfer Tracker) data for consistency.
4. Update `fs_fencers.metadata->>'nationality_history'` as a JSON array.
5. Write tests: mock SPARQL responses with multi-citizenship data.

**Success criteria:** Nationality history populated for fencers with multiple citizenships. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 65 — Competition Format & Prize Money

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_competition_details.py`, `supabase/migrations/YYYYMMDD_competition_details.sql`, `tests/test_competition_details.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (tournament data populated)

**Task:**
1. Design table:
```sql
CREATE TABLE fs_competition_details (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id uuid UNIQUE REFERENCES fs_tournaments(id),
    format_type text,
    pool_size integer,
    de_rounds integer,
    entry_fee numeric,
    prize_pool numeric,
    currency text,
    participant_count integer,
    countries_represented integer,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Write `scrape_competition_details.py`:
   - Query tournaments with `fie_id` but no competition_details entry
   - For each, scrape FIE competition detail page:
     - Extract: participant count, format, pool information
     - If prize money is published, extract monetary values
   - Some data may be in FIE regulation documents (PDF) — extract if available
   - Upsert to fs_competition_details
4. Write tests: fixture competition detail pages.

**Success criteria:** Competition format and prize money populated. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 66 — Fencing Club Ratings & Reviews

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_club_reviews.py`, `supabase/migrations/YYYYMMDD_club_reviews.sql`, `tests/test_club_reviews.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping; Agent 25 optional for `fs_club_rankings`

**Task:**
1. Write SQL migration for `fs_club_reviews`: id, club_name, normalized_club_name, city, country, source, rating, review_count, review_summary, source_url, metadata, scraped_at. Unique key: `(normalized_club_name, city, country, source)`.
2. Query distinct clubs from `fs_fencers` (club field) and `fs_club_rankings` (if Agent 25 done).
3. For each club with name + city:
   - Try Google Maps API (if key available in MAPS_API_KEY env): search "fencing club {name} {city}" → extract rating, review count
   - If no API key: skip Google Maps and log "MAPS_API_KEY not set"; do not scrape Google Maps HTML
   - Try fencing forum review threads (fencing.net, reddit r/fencing) for club mentions
4. Aggregate results by normalized club name; store source-specific ratings separately rather than overwriting.
5. Write tests for normalization, API response parsing, no-key behavior, and idempotent upsert payloads.

**Success criteria:** Club review table is created, parser tests pass, and no-key runs exit cleanly with a clear message.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 67 — Equipment Reviews Database

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_equipment_reviews.py`, `supabase/migrations/YYYYMMDD_equipment_reviews.sql`, `tests/test_equipment_reviews.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping; Agent 30 optional for brand vocabulary reuse

**Task:**
1. Design table:
```sql
CREATE TABLE fs_equipment_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name text NOT NULL,
    brand text NOT NULL,
    category text,
    rating numeric(3,1),
    review_count integer,
    price numeric,
    currency text DEFAULT 'USD',
    source text,
    url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Known fencing retailers with product listings:
   - Absolute Fencing (absolute-fencing.com)
   - Leon Paul (leonpaul.com)
   - Allstar (allstar.de)
   - Fencing.net
   - PBT (pbtfencing.com)
   - Blue Gauntlet (blue-gauntlet.com)
4. Scrape product listings: name, brand, price, category, rating.
5. Write tests: fixture product listing pages.

**Success criteria:** Equipment review database populated from at least 3 retailers. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 68 — Training Camps Directory

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_training_camps.py`, `supabase/migrations/YYYYMMDD_camps.sql`, `tests/test_camps.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agent 2 preferred for canonical fencer identity grouping; run after federation/source discovery if camp pages are found there

**Task:**
1. Design table:
```sql
CREATE TABLE fs_training_camps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organizer text,
    city text,
    country text,
    start_date date,
    end_date date,
    coaches text[],
    cost numeric,
    currency text DEFAULT 'USD',
    weapons_covered text[],
    max_participants integer,
    source_url text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Sources: federation sites ("camps" or "training" sections), camp aggregators, top-fencing club pages.
4. Deduplicate by name+organizer+date range.
5. Write tests.

**Success criteria:** Training camp directory populated. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 69 — US College Fencing Scholarships

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scrape_college_scholarships.py`, `supabase/migrations/YYYYMMDD_scholarships.sql`, `tests/test_scholarships.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** No hard code dependency; run after NCAA source conventions from Agent 20 are known

**Task:**
1. Design table:
```sql
CREATE TABLE fs_college_scholarships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    college_name text NOT NULL,
    division text,
    conference text,
    weapons text[],
    gender_teams text[],
    roster_size integer,
    scholarship_slots integer,
    head_coach text,
    coach_email text,
    website text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
```
2. Write SQL migration.
3. Scrape NCAA college fencing program pages (top-50 programs):
   - Find roster pages, coaching staff pages
   - Extract roster size, coach name, coach email
   - Scholarship slot information may be in program overview pages
4. Also scrape scholarship directory sites (e.g., ncsasports.org, scholarships.com).
5. Write tests.

**Success criteria:** College scholarship database populated for top-50 NCAA fencing programs. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 70 — Strength of Field Metric

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_strength_of_field.py`, `supabase/migrations/YYYYMMDD_strength_of_field.sql`, `tests/test_strength_of_field.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (tournament + results data)

**Task:**
1. Design `fs_competition_strength` table: tournament_id, avg_world_rank, top8_count, top16_count, total_fie_ranked, strength_score, updated_at.
2. Write SQL migration.
3. Write `compute_strength_of_field.py`:
   - For each tournament in `fs_tournaments` with results:
     - Query `fs_results` for all results, join `fs_fencers` for `world_rank`
     - Compute: avg world rank of participants (exclude NULL ranks)
     - Count: how many top-8, top-16 fencers participated
     - Strength score: `SUM(101 - fencer.world_rank) / COUNT(*)` — higher = stronger field
   - Upsert to fs_competition_strength
4. Write tests: mock results with known participant ranks.

**Success criteria:** Strength of field computed per competition. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 71 — Performance vs Ranking Prediction

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_performance_analysis.py`, `supabase/migrations/YYYYMMDD_performance_analysis.sql`, `tests/test_performance_analysis.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (results data)

**Task:**
1. For each fencer per competition result in `fs_results`:
   - Get their `world_rank` from `fs_fencers` at the time of the competition (approximate: use current world_rank)
   - Expected placement ≈ world_rank
   - Actual placement = result.rank
   - Delta = expected - actual (positive = overperformed, negative = underperformed)
2. Compute per-fencer:
   - Average delta across all competitions ("clutch score")
   - Standard deviation (consistency metric)
   - Overperformance rate: % of competitions where rank > expected
3. Write SQL migration creating `fs_fencer_performance_analysis`: fencer_id, weapon, competitions_count, avg_delta, stddev_delta, overperformance_rate, clutch_score, updated_at. Use `(fencer_id, weapon)` as the unique key.
4. Store per-fencer metrics in `fs_fencer_performance_analysis`; optionally mirror `clutch_score` into `fs_fencer_career_stats` only if that table already has the column.
5. Write tests: mock results with known deltas, NULL ranks, and mixed weapons.

**Success criteria:** Performance metrics computed per fencer. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 72 — Medal Table Aggregation

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_medal_tables.py`, `supabase/migrations/YYYYMMDD_medal_tables.sql`, `tests/test_medal_tables.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (results data)

**Task:**
1. Design `fs_medal_tables` with these aggregations:
   - By country: country, gold, silver, bronze, total, updated_at
   - By fencer: fencer_id, gold, silver, bronze, total, updated_at
   - By competition tier: tier (Olympics/Worlds/GP/WC/Continental), country, gold, silver, bronze
2. Write SQL migration.
3. Write `compute_medal_tables.py`:
   - Query `fs_results` WHERE medal IS NOT NULL
   - Join with `fs_tournaments` for competition tier info
   - Aggregate by country, fencer, tier
   - Upsert to medal tables
4. Write tests: mock results with known medal distributions.

**Success criteria:** Medal tables populated for countries, fencers, and tiers. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 73 — Fencer Longevity Analysis

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_longevity.py`, `supabase/migrations/YYYYMMDD_longevity.sql`, `tests/test_longevity.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (results data)

**Task:**
1. For each fencer, query date range from results:
   - `fs_results` joined with `fs_tournaments` on tournament_id for start_date
   - First season = MIN(tournament.season)
   - Last season = MAX(tournament.season)
   - Career length = last_season - first_season (in years)
   - Competitions per season = COUNT(*) / career_length
2. Active vs retired detection:
   - If last_competition was > 2 years ago → likely retired
   - If last_competition was within 2 years → active
   - If no results at all → unknown
3. Write SQL migration creating `fs_fencer_longevity`: fencer_id, first_competition_date, last_competition_date, first_season, last_season, career_years, competitions_per_season, status, updated_at.
4. Store longevity metrics in `fs_fencer_longevity`; do not overload unrelated metadata.
5. Write tests: mock results with known date ranges, active/retired/unknown cases, and single-season fencers.

**Success criteria:** Longevity metrics computed per fencer. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 74 — Weapon Specialization Analysis

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `compute_specialization.py`, `tests/test_specialization.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 16–21 (results data)

**Task:**
1. For each fencer, query distinct weapons from `fs_results`:
   - Single-weapon vs multi-weapon classification
   - For multi-weapon: which weapon is their primary (most results)?
2. Compare success rates:
   - Single-weapon specialists: avg rank, medals per competition
   - Multi-weapon fencers: avg rank per weapon, medals per competition
   - Do specialists outperform generalists? (compute aggregate stats)
3. Category transition:
   - For fencers with Junior + Senior results: what % of Junior fencers reach Senior?
   - At what age do they transition? (from first Junior result to first Senior result)
4. Weapon switching:
   - Fencers who changed primary weapon between seasons
   - How common is it? Does it affect performance?
5. Write tests: mock results with known weapon patterns.

**Success criteria:** Weapon specialization analysis computed. Stats reported. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 75 — Supabase RLS + Multi-Tenant Access

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `supabase/migrations/YYYYMMDD_rls_policies.sql`, `tests/test_rls_policy_sql.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Run after schema-changing agents are merged so RLS policies cover final tables/views

**Task:**
1. Read existing Supabase migration files before editing so policy/table names match the current schema.
2. Write SQL migration with Supabase-compatible RLS:
```sql
-- Enable RLS on public read tables.
ALTER TABLE fs_fencers ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_tournaments ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_national_fed_rankings ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_head_to_head ENABLE ROW LEVEL SECURITY;
ALTER TABLE fs_rankings_history ENABLE ROW LEVEL SECURITY;

-- Public-safe views expose only fields intended for anonymous readers.
CREATE OR REPLACE VIEW v_fencer_public AS
SELECT id, name, country, weapon, category, world_rank, fie_points, image_url
FROM fs_fencers;

CREATE OR REPLACE VIEW v_tournament_public AS
SELECT id, name, season, start_date, end_date, country, weapon, category, type
FROM fs_tournaments;

-- Revoke direct anonymous reads from base tables; grant view reads.
REVOKE ALL ON fs_fencers FROM anon;
REVOKE ALL ON fs_tournaments FROM anon;
GRANT SELECT ON v_fencer_public TO anon;
GRANT SELECT ON v_tournament_public TO anon;

-- Authenticated subscribers read base tables only when JWT/app metadata says subscriber.
CREATE POLICY subscriber_fencers_read ON fs_fencers
FOR SELECT TO authenticated
USING ((auth.jwt() -> 'app_metadata' ->> 'role') = 'subscriber');
```
3. Do not create arbitrary Postgres roles such as `public_user`; Supabase uses `anon`, `authenticated`, and service-role bypass.
4. Add a SQL comment block explaining the expected JWT metadata shape for subscribers.
5. Write `tests/test_rls_policy_sql.py`:
   - Assert migration contains no invalid `CREATE SECURITY POLICY`
   - Assert direct anon grants are revoked from sensitive base tables
   - Assert public views exclude sensitive columns (`bio_text`, `metadata`, `date_of_birth`, `height`, `club`)
   - Assert subscriber policy checks JWT app metadata

**Success criteria:** Migration is valid Postgres/Supabase SQL, public views expose limited fields, subscriber policy exists, and SQL tests pass.

**Output format:**
```
Files: supabase/migrations/YYYYMMDD_rls_policies.sql, tests/test_rls_policy_sql.py
Public views: [list]
Sensitive base tables protected: [list]
Tests: pytest tests/test_rls_policy_sql.py -v
```

---

## Agent 76 — Scraper Rate Limiting Service

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/rate_limiter.py`, `tests/test_rate_limiter.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** No hard dependency; safe to run earlier, but integrate into scrapers after tests pass

**Task:**
1. Write `RateLimiter` class:
```python
import time
from collections import defaultdict

class RateLimiter:
    """Per-domain rate limiter with jitter and backoff."""
    
    def __init__(self, default_rps: float = 1.0, jitter: float = 0.1, backoff: float = 2.0):
        self.default_rps = default_rps
        self.jitter = jitter
        self.backoff = backoff
        self._last_request = defaultdict(float)
        self._failures = defaultdict(int)
    
    def wait(self, domain: str, rps: float | None = None):
        """Sleep if needed to maintain rps for domain."""
        if rps is None:
            rps = self.default_rps
        elapsed = time.time() - self._last_request[domain]
        min_interval = 1.0 / rps
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        # Add jitter
        time.sleep(random.uniform(0, self.jitter))
        self._last_request[domain] = time.time()
    
    def record_failure(self, domain: str):
        """Record a failure for this domain (increases backoff)."""
        self._failures[domain] += 1
        if self._failures[domain] > 3:
            time.sleep(self.backoff * self._failures[domain])
    
    def record_success(self, domain: str):
        """Reset failure count on success."""
        self._failures[domain] = 0
    
    def __call__(self, domain: str, rps: float | None = None):
        """Context manager usage: with RateLimiter() as rl: rl.wait(...)"""
        self.wait(domain, rps)
        return self
```
2. Write tests: verify timing accuracy (±10%), domain isolation (waiting on one domain doesn't affect another), jitter range, backoff after failures.

**Success criteria:** RateLimiter class with timing tests passing.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 77 — Schema Migration Tooling

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/migrate.py`, `supabase/migrations/README.md`, `tests/test_migrate_cli.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** No hard dependency; use after current migration naming conventions are confirmed

**Task:**
1. Write `scripts/migrate.py` CLI:
   - `python scripts/migrate.py list` — list all migration files in `supabase/migrations/`, show which are applied
   - `python scripts/migrate.py apply` — apply all unapplied migrations in filename order (YYYYMMDD_*.sql)
   - `python scripts/migrate.py generate --name description` — create new `supabase/migrations/YYYYMMDD_description.sql` from template
   - `python scripts/migrate.py dry-run` — show what would be applied without doing it
   - `python scripts/migrate.py status` — show last migration applied and pending count
2. Track migrations in `fs_schema_migrations` table:
```sql
CREATE TABLE IF NOT EXISTS fs_schema_migrations (
    id serial PRIMARY KEY,
    filename text UNIQUE NOT NULL,
    applied_at timestamptz DEFAULT now(),
    hash text,
    success boolean DEFAULT true
);
```
3. Write README with usage examples.
4. Write tests:
   - `list` shows applied and pending migrations from mocked DB rows
   - `generate --name add_table` creates a correctly named file in a temp migrations directory
   - `dry-run` prints pending SQL filenames without applying them
   - Migration hash changes are detected and reported as an error

**Success criteria:** CLI tool lists, applies, generates, and dry-runs migrations. README and tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 78 — Scraper Health Monitoring Dashboard

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `dashboard/app.py`, `dashboard/queries.sql`, `tests/test_dashboard_queries.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 35 and 38 preferred so live runs and quality views exist

**Task:**
1. Write `dashboard/queries.sql` with reference SQL queries:
   - Scraper run status (last 24h per module)
   - Data counts (fencers, tournaments, results per source)
   - Stale sources (last success > 48h ago)
   - Error rate per module
2. Write `dashboard/app.py` (Streamlit):
   - Page 1: Status Dashboard — table of each scraper module, last run time, status, written/failed/skipped counts. Color-coded: green (success), yellow (completed_with_errors), red (error/grey (no run in 48h))
   - Page 2: Data Counts — bar chart of fencers per source, tournaments per season, results per competition type. List of orphan counts.
   - Page 3: Coverage Map — world map with fencer count per country (using plotly or pydeck). Color intensity by density.
   - Page 4: Error Log — recent errors from `fs_scraper_runs` with error messages, searchable/filterable by module
   - Requires `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` env vars to connect
3. Add `streamlit` and `plotly` to requirements.txt (or note as optional extras if the project avoids dashboard deps in scraper runtime).
4. Write tests:
   - `dashboard/queries.sql` contains the four required query blocks
   - Query strings include stale-source and orphan-result checks
   - Dashboard module can import with Streamlit mocked

**Success criteria:** Streamlit dashboard runs, all 4 pages are functional, query tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 79 — Cross-Source Data Reconciliation

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.

**Files:** `scripts/reconcile_data.py`, `tests/test_reconcile.py`

**Constraints:** Keep changes scoped to the listed files and any explicitly required migration/test/requirements files. Do not edit `.github/workflows/`; Agent 80 owns CI integration.

**Depends on:** Agents 2, 16–21, 27–34, and federation scrapers preferred so multiple sources exist to compare

**Task:**
1. Write `scripts/reconcile_data.py`:
```python
def reconcile(source_a: str, source_b: str) -> dict:
    """Compare fencer data between two sources.
    
    Args:
        source_a: Name of first source (e.g., 'FIE', 'british_fencing', 'olympedia')
        source_b: Name of second source
        
    Returns:
        dict with keys: matched, mismatched, in_a_only, in_b_only, samples
    """
    # 1. Get fencers from source A (query appropriate table)
    # 2. Get fencers from source B
    # 3. Match by fie_id if available
    # 4. For matched pairs, compare: name, country, weapon, rank
    # 5. Flag: name spelling differences, country differences, rank differences
    # 6. Report unmatched from each side
    
def main():
    """CLI: python scripts/reconcile.py --source-a FIE --source-b british_fencing"""
    # Parse args, call reconcile(), print report
```
2. Options:
   - `--source-a` and `--source-b`: sources to compare
   - `--output report.json`: save detailed report to file
3. Write tests: mock two datasets with known matches and mismatches.

**Success criteria:** Reconciliation script produces match/mismatch report. Tests pass.

**Output format:**
```
Scope:
Files:
Findings:
Changes:
Risks:
Tests:
Confidence:
```

---

## Agent 80 — CI Workflow Merge

Complete this task fully and correctly to the best of your ability.
Do not do a shallow pass.
Do not stop at the first working solution.
Do not skip edge cases, verification, or cleanup.
Do not make broad unrelated changes.
Do not ask for clarification unless you are genuinely blocked.
Use the existing project instructions, memory/wiki/graph tools, and codebase navigation workflow.

Process:
1. Understand the goal and current state.
2. Inspect the relevant files/context before editing.
3. Identify risks, edge cases, and likely failure points.
4. Make the smallest robust changes that solve the real problem.
5. Add or update tests if appropriate.
6. Run relevant verification.
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
Do not touch .github/workflows/ — CI integration is handled by Agent 80.
You are the only agent allowed to touch .github/workflows/. Do not modify scraper, analytics, enrichment, or schema files except tests needed to validate workflow integrity.

**Files:** `.github/workflows/scraper.yml`, `.github/workflows/live_results.yml`, `.github/workflows/weekly_analytics.yml`, `tests/test_workflow_integrity.py`

**Depends on:** All other agents. This is the final integration agent.

**IMPORTANT:** This agent is the ONLY one that touches `.github/workflows/`. Do not modify any other files.

**Task:**
1. Read the current `.github/workflows/scraper.yml` fully.
2. Merge all new scraper steps into the 6-hour cron workflow, preserving existing steps. Add in this order:
   - **Pre-results:** Agent 37 (`discover_competition_urls.py`) — run BEFORE results scrapers
   - **Core scrapers:** existing steps (scraper.py, scrape_fie_events.py, scrape_rankings_history.py, scrape_results.py, askfred_scraper.py, scrape_engarde.py, scrape_bouts.py, scrape_clubs.py)
   - **Federation scrapers (Batch B):** scrape_fed_hun.py → scrape_fed_kor.py → scrape_fed_chn.py → scrape_fed_jpn.py → scrape_fed_rus.py → scrape_fed_pol.py → scrape_fed_ukr.py → scrape_fed_rou.py → scrape_fed_esp.py → scrape_fed_egy.py
   - **Federation scrapers (Tier 2):** scrape_fed_ned.py → scrape_fed_bel.py → scrape_fed_sui.py → scrape_fed_aut.py → scrape_fed_swe.py → scrape_fed_den.py → scrape_fed_nor.py → scrape_fed_fin.py → scrape_fed_aus.py → scrape_fed_nzl.py → scrape_fed_bra.py → scrape_fed_arg.py → scrape_fed_hkg.py → scrape_fed_sgp.py → scrape_fed_isr.py
   - **Competition sources:** scrape_fred.py → scrape_youth_olympics.py → scrape_universiade.py → scrape_continental_games.py → scrape_ncaa_regular.py → scrape_youth_majors.py → scrape_paralympics.py → scrape_news.py
   - **More competition (Tier 3):** scrape_commonwealth.py → scrape_cism.py → scrape_mediterranean_games.py → scrape_maccabiah.py → scrape_masters_games.py → scrape_south_american_games.py → scrape_cac_games.py → scrape_island_games.py
   - **Enrichment:** scrape_wikipedia_bios.py → scrape_social_media.py → scripts/download_headshots.py → scrape_equipment.py → scrape_physical_stats.py → enrich_nationality_history.py → scrape_competition_details.py → scrape_club_reviews.py → scrape_equipment_reviews.py → scrape_training_camps.py → scrape_college_scholarships.py
   - **Compute:** compute_head_to_head.py → compute_career_stats.py → compute_rankings_trends.py → compute_country_analytics.py → compute_transfers.py → compute_name_variants.py → enrich_locations.py → compute_strength_of_field.py → compute_performance_analysis.py → compute_medal_tables.py → compute_longevity.py → compute_specialization.py
   - **Final:** data_quality_check.py
   - **Existing compute:** compute_national_rankings.py, scrape_athlete_profiles.py, scrape_fie_history.py, scrape_wikidata.py, scrape_olympics.py, scrape_ncaa.py, scrape_iwas.py, scrape_fie_career.py (keep existing ordering)
   - Every step: `continue-on-error: true` with env SUPABASE_URL + SUPABASE_SERVICE_KEY
3. Create `.github/workflows/live_results.yml`:
   - Cron: `*/15 * * * *`
   - Steps: `watch_live_results.py` only
4. Create `.github/workflows/weekly_analytics.yml`:
   - Cron: `0 3 * * 0` (Sunday 3am)
   - Steps: all compute scripts
5. Validate each YAML: `python -c "import yaml; yaml.safe_load(open('file'))"`.
6. Write `tests/test_workflow_integrity.py`:
   - Parses all three workflow files with PyYAML
   - Asserts `discover_competition_urls.py` appears before `scrape_results.py`
   - Asserts every new scraper/compute script from this prompt pack appears in exactly one intended workflow
   - Asserts each scraper step has `continue-on-error: true`
   - Asserts required Supabase env vars are present on scraper steps

**Success criteria:** Three workflow files, valid YAML, all generated scripts integrated in the right workflow, workflow integrity tests pass. This is the final piece.

**Output format:**
```
Files: .github/workflows/scraper.yml, .github/workflows/live_results.yml, .github/workflows/weekly_analytics.yml, tests/test_workflow_integrity.py
YAML validation: pass/fail
Workflow integrity tests: pytest tests/test_workflow_integrity.py -v
Missing scripts: []
```
