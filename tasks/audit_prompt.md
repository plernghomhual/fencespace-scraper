# Claude Prompt: Complete Audit of the 80-Agent Implementation

Complete a comprehensive pre-production audit of the entire 80-agent implementation in this repository.

This is an audit-first task. Do not implement fixes, modify files, run migrations, deploy, push, delete files, install packages, or touch production services unless I explicitly approve a follow-up fix phase.

Project root: `/Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper`

Python: `.venv/bin/python`

Default full test command: `.venv/bin/python -m pytest tests/ -v`

Primary source-of-truth files to read first:
- `tasks/agent_prompts.md`
- `tasks/todo.md`
- `tasks/lessons.md`
- `requirements.txt`
- `.github/workflows/`
- `supabase/migrations/`
Also, the results from each of the GitHub actions to further best diagnose:
- `scraperresults.txt`
- `liveresultsscraperresults.txt`
- `weeklyanalyticsresults.txt`

Your job is to verify whether the original 80-agent project was actually implemented correctly, completely, safely, and consistently. Treat this like a release gate where missing one serious issue is unacceptable.

Do not do a shallow pass. Do not only inspect obvious files. Do not assume an agent completed its work because a file exists. For every major claim, cite concrete evidence: file paths, function names, schema names, tests, commands, or observed behavior.

## Required Audit Outcome

Return a complete audit report that answers:

1. Which of the original 80 agent deliverables are fully implemented?
2. Which are partially implemented?
3. Which are missing?
4. Which implementations are present but broken, fragile, unsafe, untested, or inconsistent with project patterns?
5. Which tests pass or fail?
6. Which failures are pre-existing versus introduced by the 80-agent work?
7. Which issues must be fixed before starting the next 160-agent wave?

Do not fix issues in this audit. Produce the report and wait for approval.

## Required Process

### Phase 1 - Repo Orientation

Build a concise codebase map before judging implementation quality.

Inspect:
- project type and stack
- important directories
- scraper entry points
- compute/analytics entry points
- enrichment modules
- API/CLI/dashboard entry points
- Supabase migration structure
- GitHub Actions workflows
- test structure
- run logging and scraper state patterns
- external services and environment variables
- deployment assumptions

Use the strongest available navigation workflow:
- Read `tasks/lessons.md` and apply lessons.
- Read `tasks/todo.md` for current implementation notes and known failures.
- Read `tasks/agent_prompts.md` as the original implementation contract.
- Use wiki/graph/codebase-memory/CRG/semantic search if available.
- Prefer targeted search before broad raw file reads.
- Use subagents only if they materially improve coverage. Use 3-5 maximum unless I approve more.

### Phase 2 - Implementation Coverage Audit

Create a coverage matrix. Every row must have:

```text
Item:
Expected files/tables/workflows:
Implementation status: complete / partial / missing / not verified
Evidence:
Tests found:
Verification result:
Risks or bugs:
Recommended action:
Confidence:
```

You must cover every item below. Do not merge rows in a way that hides missing work.

Before filling the matrix, create an expected-file inventory directly from `tasks/agent_prompts.md`:

1. Extract every `## Agent N` section.
2. Extract every path listed in each section's `**Files:**` line.
3. Verify each expected source file, test file, migration file, workflow file, docs file, dashboard file, and script exists or is explicitly marked missing.
4. For every expected test file, verify whether it is present, whether it is meaningful, and whether it passes.
5. For every expected migration placeholder such as `supabase/migrations/YYYYMMDD_*.sql`, verify an actual dated migration exists with the expected table/view/policy.
6. For every expected workflow file, verify YAML validity, schedule, job order, env vars, and script coverage.

Include this expected-file inventory in the report. If a file is listed in `tasks/agent_prompts.md` but missing from the repo, that is a finding even if the broader feature appears partially implemented elsewhere.

Use an approach like this, adapted as needed:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import re
text = Path("tasks/agent_prompts.md").read_text()
for agent in re.finditer(r"^## Agent (\\d+)\\b[^\\n]*", text, re.M):
    n = int(agent.group(1))
    start = agent.start()
    next_agent = re.search(r"^## Agent \\d+\\b", text[start + 1:], re.M)
    end = start + 1 + next_agent.start() if next_agent else len(text)
    section = text[start:end]
    files = []
    for line in section.splitlines():
        if line.startswith("**Files:**"):
            files.extend(re.findall(r"`([^`]+)`", line))
    print(n, files)
PY
```

## Mandatory Coverage Checklist

### A. Known Bug Fixes (7)

1. Italy scraper returns 0 data
   - Verify `scrape_fed_italy.py` no longer relies on broken HTML Olympic-table matching.
   - Verify Federscherma `.xls` / `.xlsx` handling exists.
   - Verify `xlrd` / `openpyxl` dependencies where needed.
   - Verify rows write via `fed_rankings_common.py`.
   - Verify tests cover `.xls` or `.xlsx`, empty sheets, headers, and Italian numeric/name formats.

2. `fs_fencers` duplicate rows per person
   - Verify schema/script support for canonical fencer identity grouping.
   - Verify duplicate grouping handles same `fie_id` across weapons/categories and name+country fallback.
   - Verify downstream matching/analytics use identity groups where appropriate.

3. `fs_results` NULL `fencer_id` orphans
   - Verify orphan matching script or shared matching layer exists.
   - Verify matching order: FIE ID first, then exact name+country, then normalized/fuzzy fallbacks.
   - Verify ambiguous matches are logged, not silently applied.
   - Verify result scrapers do not casually accept NULL without logging.

4. Engarde endpoints return 404
   - Verify `scrape_engarde.py` no longer depends only on stale `/prog/getTournoisForDisplay.php`.
   - Verify current endpoint probing, pool parsing, DE parsing, result parsing, and graceful 404 behavior.
   - Verify `fs_bouts` integration.

5. `result_weight` fragile string matching
   - Verify `compute_national_rankings.py` uses tournament `type` first.
   - Verify string matching remains only as fallback for legacy rows.
   - Verify tests cover type-based weighting.

6. Season format inconsistent
   - Verify `season_utils.py` exists.
   - Verify `season_to_string()`, `season_from_string()`, `current_fie_season()`, and `normalize_season()` behavior.
   - Verify scrapers and analytics use normalized season formats consistently.

7. No weapon combo dedup in upsert
   - Verify `scraper.py` deduplicates fencers across weapon/category combos before upsert.
   - Verify dedup is race-safe and preserves the best available fencer data.
   - Verify tests cover multi-weapon duplicate scenarios.

### B. Federation National Rankings (25)

For every federation scraper below, verify:
- file exists
- tests exist
- current public URL was probed or documented as blocked
- parser handles source format: HTML, XLS/XLSX, CSV, PDF, API, or stub with evidence
- language-specific rank/name/club/points headers are handled
- non-Latin scripts are preserved
- all 12 Senior/Junior x Foil/Epee/Sabre x Men/Women combos are attempted or missing combos are logged
- rows use `fed_rankings_common.build_ranking_row()` and `write_rankings()`
- `ScraperRunLogger` is used
- network errors, 404s, login-only pages, JS pages, and IP blocks fail gracefully
- tests use real captured fixtures where possible or realistic fixtures based on probed structure

Audit each one separately:

1. Hungary / MVSZ - `scrape_fed_hun.py`, Hungarian headers, `hunfencing.hu` / `magyarvivaszszovetseg.hu`
2. South Korea / KFA - `scrape_fed_kor.py`, Korean Hangul, `koreafencing.org`
3. China / CFA - `scrape_fed_chn.py`, Chinese CJK, `fencing.org.cn` or documented block
4. Japan / JFA - `scrape_fed_jpn.py`, Japanese HTML/PDF, `fencing-jpn.jp`
5. Russia / RUS - `scrape_fed_rus.py`, Cyrillic, `rusfencing.ru` or documented geoblock
6. Poland / PZS - `scrape_fed_pol.py`, Polish, `pzszerm.pl`
7. Ukraine / NFFU - `scrape_fed_ukr.py`, Ukrainian Cyrillic, `fencing.ua` / `nffu.gov.ua`
8. Romania / FR - `scrape_fed_rou.py`, Romanian, `federatia-de-scrima.ro`
9. Spain / RFEE - `scrape_fed_esp.py`, Spanish, `rfeespada.es`
10. Egypt / EGF - `scrape_fed_egy.py`, Arabic/English, `egfencing.com`
11. Netherlands / NFF - `scrape_fed_ned.py`, Dutch, `knfb.nl`
12. Belgium / FBB - `scrape_fed_bel.py`, Dutch/French/German, `fencing-belgium.be`
13. Switzerland / Swiss Fencing - `scrape_fed_sui.py`, German/French/Italian, `swiss-fencing.ch`
14. Austria / OFV - `scrape_fed_aut.py`, German, `fencing.at`
15. Sweden / SFF - `scrape_fed_swe.py`, Swedish, `swefencing.se`
16. Denmark / DFF - `scrape_fed_den.py`, Danish, `fencing.dk`
17. Norway / NFF - `scrape_fed_nor.py`, Norwegian, `fencing.no`
18. Finland / SLY - `scrape_fed_fin.py`, Finnish, `fencing.fi`
19. Australia / AFF - `scrape_fed_aus.py`, English, `ausfencing.org`
20. New Zealand / NZFA - `scrape_fed_nzl.py`, English, `fencing.org.nz`
21. Brazil / CBE - `scrape_fed_bra.py`, Portuguese, `cbesgrima.org.br`
22. Argentina / FAA - `scrape_fed_arg.py`, Spanish, `esgrima.org.ar`
23. Hong Kong / HKFA - `scrape_fed_hkg.py`, English/Chinese, `fencing.org.hk`
24. Singapore / FFS - `scrape_fed_sgp.py`, English, `fencing.org.sg` or current public replacement
25. Israel / IFA - `scrape_fed_isr.py`, Hebrew/English, `fencing.org.il`

### C. New Competition Sources (14+ source areas)

For every competition scraper, verify:
- file exists
- tests exist
- source was probed
- discovery works
- tournaments are upserted with stable `source_id`
- results are parsed with ranks/name/country/medals where applicable
- fencer matching is best-effort and logs unmatched rows
- `ScraperRunLogger` and `scraper_state` are used where appropriate
- failures are non-fatal and documented

Audit each separately:

1. USA Fencing FRED - `scrape_fred.py`
2. Youth Olympic Games 2010, 2014, 2018, 2026 - `scrape_youth_olympics.py`
3. World Fencing Games 2023+ Bali - same or dedicated implementation; verify source and coverage
4. Universiade / World University Games 1957+ - `scrape_universiade.py`
5. Pan American Games 1951+ - `scrape_continental_games.py`
6. Asian Games 1974+ - `scrape_continental_games.py`
7. European Games 2015+ - `scrape_continental_games.py`
8. African Games 1965+ - `scrape_continental_games.py`
9. NCAA Regular Season results, top-50 programs - `scrape_ncaa_regular.py`
10. Cadet/Junior World Championships missing seasons - `scrape_youth_majors.py`
11. EYOF - `scrape_youth_majors.py`
12. Paralympic Wheelchair Fencing 1980+ - `scrape_paralympics.py`
13. FIE News + Injury/Absence tracker - `scrape_news.py`
14. Commonwealth Fencing Championships - `scrape_commonwealth.py`
15. CISM World Military Games - `scrape_cism.py`
16. Mediterranean Games 1951+ - `scrape_mediterranean_games.py`
17. Maccabiah Games - `scrape_maccabiah.py`
18. World Masters Games - `scrape_masters_games.py`
19. South American Games / ODESUR 1978+ - `scrape_south_american_games.py`
20. Central American & Caribbean Games 1938+ - `scrape_cac_games.py`
21. Island Games / Oceania Zonal Championships - `scrape_island_games.py`

If a prompt combined multiple sources in one agent, still audit every source individually.

### D. Aggregation and Analytics (12)

For every analytics engine, verify schema, compute logic, tests, idempotency, NULL handling, identity grouping, and incremental behavior where relevant.

1. Head-to-Head records - `compute_head_to_head.py`, `fs_head_to_head`
2. Fencer Career Stats - `compute_career_stats.py`, `fs_fencer_career_stats`
3. Rankings Trends + Points Projection - `compute_rankings_trends.py`, `fs_rankings_trends`
4. Country Depth + Club Rankings - `compute_country_analytics.py`, `fs_country_depth`, `fs_club_rankings`
5. Fencer Transfer Tracker - `compute_transfers.py`, `fs_fencer_transfers`
6. Name Variant Database - `compute_name_variants.py`, `fs_fencer_name_variants`
7. Venue Geocoding - `enrich_locations.py`, `fs_venues`
8. Strength of Field Metric - `compute_strength_of_field.py`, `fs_competition_strength`
9. Performance vs Ranking Prediction / clutch score - `compute_performance_analysis.py`, `fs_fencer_performance_analysis`
10. Medal Table Aggregation - `compute_medal_tables.py`, medal aggregation tables
11. Fencer Longevity Analysis - `compute_longevity.py`, `fs_fencer_longevity`
12. Weapon Specialization Analysis - `compute_specialization.py`

### E. Enrichment (11)

For every enrichment module, verify schema, source probing, parsing, rate limiting, storage behavior, privacy/security implications, tests, and graceful degradation.

1. Wikipedia Bio Text - `scrape_wikipedia_bios.py`
2. Social Media Presence - `scrape_social_media.py`
3. Headshot Download + Media Pipeline - `scripts/download_headshots.py`
4. Equipment & Brand Data - `scrape_equipment.py`
5. Physical Stats - `scrape_physical_stats.py`
6. Nationality History - `enrich_nationality_history.py`
7. Competition Format & Prize Money - `scrape_competition_details.py`
8. Club Ratings & Reviews - `scrape_club_reviews.py`
9. Equipment Reviews Database - `scrape_equipment_reviews.py`
10. Training Camps Directory - `scrape_training_camps.py`
11. US College Fencing Scholarships - `scrape_college_scholarships.py`

### F. Infrastructure (9)

Audit each infrastructure item separately:

1. Live Results Watcher - `watch_live_results.py`, 15-minute workflow
2. Referee & Coach Data - `scrape_referees.py`, `scrape_coaches.py`, referee/coach migrations
3. FIE Competition URL ID Discovery - `discover_competition_urls.py`
4. Data Quality Automation - `scripts/data_quality_check.py`, materialized views
5. Export API + CLI - `api.py`, `cli_export.py`, `docs/api.yaml`
6. Supabase RLS + Multi-Tenant - RLS migration and public/subscriber access behavior
7. Rate Limiter Service - `scripts/rate_limiter.py`
8. Schema Migration Tooling - `scripts/migrate.py`
9. Health Dashboard - `dashboard/app.py`, `dashboard/queries.sql`

### G. Cross-Cutting (3)

Audit these across the entire implementation:

1. CI Workflow Merge
   - Verify 6-hour scraper cron includes all relevant scrapers in safe order.
   - Verify 15-minute live watcher workflow exists.
   - Verify weekly analytics workflow exists.
   - Verify `discover_competition_urls.py` runs before result scrapers.
   - Verify workflows are valid YAML and use expected env vars.

2. `season_utils.py`
   - Verify all scrapers/analytics use shared season normalization or compatible fallback.
   - Verify no new inconsistent season formats were introduced.

3. Cross-Source Data Reconciliation
   - Verify `scripts/reconcile_data.py` exists.
   - Verify FIE vs federation vs Olympedia comparison logic.
   - Verify discrepancies are reported without overwriting source data.

## Phase 3 - Automated and Search-Based Audit

Run safe, relevant commands. Capture command, result, important output, and pass/fail/skipped status.

Required checks unless impossible:

```bash
git status --short
git diff --stat
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m py_compile $(git ls-files '*.py')
```

Also run targeted discovery/search checks:

```bash
git ls-files
find . -maxdepth 3 -type f -name '*.py' | sort
find supabase/migrations -type f | sort
find tests -type f -name 'test_*.py' | sort
grep -R "TODO\\|FIXME\\|HACK\\|pass$\\|NotImplemented\\|print(" -n -- *.py scripts tests 2>/dev/null
grep -R "SUPABASE_SERVICE_KEY\\|API_KEY\\|SECRET\\|TOKEN\\|PASSWORD" -n . --exclude-dir=.git --exclude-dir=.venv
grep -R "requests.get\\|requests.post\\|fetch(" -n -- *.py scripts 2>/dev/null
grep -R "on_conflict\\|upsert\\|insert\\|update\\|delete" -n -- *.py scripts 2>/dev/null
```

Use better local equivalents if the repo has scripts for lint, typecheck, build, or smoke tests.

Do not run destructive commands.

Ask before:
- installing packages
- applying migrations
- pushing/deploying
- deleting files
- touching production data
- running live scrapers that write to Supabase

If a check is too expensive or unsafe, skip it and explain why.

## Phase 4 - Manual Deep Review

Do not rely only on tests. Deeply inspect high-risk flows:

- all new scraper entry points
- federation scraper parser patterns and source-specific fallbacks
- result upsert and fencer matching paths
- identity resolution
- `fs_results` orphan handling
- `fs_bouts` and head-to-head aggregation
- season normalization
- run logger usage
- scraper state usage
- migration SQL validity and ordering
- migration SQL cross-referenced against compute/enrichment scripts (verify every table and column a compute engine writes to actually exists in its matching migration)
- Supabase RLS / public view safety
- API auth and pagination
- CLI export behavior
- dashboard query assumptions
- GitHub Actions order and env handling
- rate limiting and external-service retry behavior
- use of service keys/secrets
- tests that are superficial or only check imports

For every scraper that uses an external source, check whether the implementation is robust if:
- the site returns 404
- the site is login-only
- the site is JS-rendered
- the response is empty
- the file is malformed
- the language has non-Latin text
- names have accents/apostrophes/particles
- points use decimal commas
- multiple fencers share the same name
- Supabase credentials are missing

## Phase 5 - Audit Categories

Review every area below.

### Correctness
- logic bugs
- broken edge cases
- bad assumptions
- race conditions
- async/state bugs
- NULL handling
- error handling gaps
- invalid data flows
- broken imports/exports
- stale or dead code
- inconsistent behavior

### Security
- secrets or token leaks
- unsafe auth/session handling
- missing authorization checks
- injection risks
- insecure redirects
- unsafe file/network access
- weak input validation
- exposed internal data
- dangerous dependencies/config
- insecure defaults
- production-data risks

### Architecture
- confusing module boundaries
- duplicated logic
- bad abstractions
- circular dependencies
- tight coupling
- state/data-flow problems
- missing separation of concerns
- brittle scale-breaking patterns

### Performance
- unnecessary repeated work
- expensive queries/loops
- avoidable recomputation
- inefficient data loading
- memory leaks
- blocking operations
- large dependency issues
- N+1 patterns
- weak caching strategy

### Reliability
- missing retries/fallbacks
- weak error boundaries
- fragile deployment assumptions
- bad environment handling
- missing health checks
- bad logging/observability
- unhandled failure modes
- flaky tests/scripts

### Tests
- missing critical tests
- low-value tests
- tests that do not assert enough
- untested auth/security/data paths
- untested edge cases
- fragile test setup
- missing integration/e2e coverage

### Developer Experience
- unclear scripts
- bad README/setup docs
- confusing config
- inconsistent formatting/linting
- hard-to-run local environment
- missing examples
- dependency/version issues

### UX/Product Behavior
If any dashboard/API/user-facing behavior exists, audit:
- broken flows
- confusing states
- missing loading/error/empty states
- accessibility issues
- mobile/responsive issues
- data mismatch between UI and backend
- user-facing edge cases

## Phase 6 - Required Report Format

Return a compact but complete report with these sections.

### A. Executive Verdict
- Overall health: excellent / good / risky / broken
- One blunt paragraph.

### B. Codebase Map
- Architecture summary.
- Important directories/files.
- Critical flows.

### C. 80-Agent Coverage Matrix
- Include every original agent/deliverable or grouped prompt item.
- Status: complete / partial / missing / not verified.
- Evidence.
- Tests.
- Risks.

### D. Checks Run
For each command/check:
- command
- result
- important output
- passed/failed/skipped
- why skipped if skipped

### E. Critical Findings
For each issue:
- severity: critical / high / medium / low
- category
- file(s)
- exact evidence
- why it matters
- likely impact
- recommended fix
- confidence level

### F. Security Findings
Same format as critical findings, with extra attention to secrets/auth/data exposure.

### G. Test Gaps
List missing or weak tests by risk level.

### H. Architecture and Maintainability Risks
List structural problems and future failure risks.

### I. Performance Risks
List confirmed and likely bottlenecks.

### J. Quick Wins
Small safe fixes with high impact.

### K. Larger Refactors
Bigger changes that need planning.

### L. Suspicious but Probably Okay
Include why each item is probably acceptable.

### M. Unknowns / Not Fully Verified
Be honest about what could not be proven.

### N. Prioritized Fix Plan
Group into:
1. fix immediately
2. fix soon
3. improve later
4. monitor only

### O. Suggested Implementation Order
Give a safe order that avoids breaking the codebase.

### P. Final Confidence Rating
Rate audit confidence 1-10 and explain what would raise it.

## Rules

- Do not say "no issues found" unless you genuinely checked enough to support that.
- Separate confirmed bugs from suspicions.
- Do not invent issues.
- Do not fix anything yet unless I explicitly approve.
- If context gets large, summarize progress and continue systematically instead of skipping sections.
- If subagents are useful, use bounded parallel review by logical area. Use 3-5 subagents by default and ask before more than 5.
- Subagents must return compact English summaries using:

```text
Scope:
Files:
Findings:
Risks:
Tests:
Confidence:
```

- Every major claim must point to file paths, commands, or observed evidence.
- Update Wiki-Brain / project memory if this is a meaningful audit session and the setup supports it.
- After the audit report, wait for my approval before implementing.
