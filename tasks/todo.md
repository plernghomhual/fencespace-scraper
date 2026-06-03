# Agent 109 — Competition Bracket Visualizer

## Final Review
- [x] Read project lessons and task state.
- [x] Inspected current bracket sources: `fs_tournament_brackets` is described by task prompts and appears as an untracked migration from other agent work; committed code uses mixed `fs_bouts` fields (`fencer_a`/`fencer_b`/`winner` and `*_id` variants).
- [x] Confirmed no concrete tournament page exists to wire into in this checkout; existing frontend files include pages/components/tests but no actual tournament route file.
- [x] Added red-first component tests for full DE bracket, byes/incomplete bouts, accessibility/focus labels, overflow layout, and empty/error states.
- [x] Added `frontend/lib/brackets.ts` normalizer and `frontend/components/BracketVisualizer.tsx` reusable component.
- [x] Verification: focused bracket Vitest suite passed 6/6; narrow TypeScript check passed for bracket component, normalizer, and test.
- [x] Broader frontend checks were run and failed only in pre-existing/unrelated frontend tests/config: `h2h-page.test.tsx` uses Jest globals under Vitest, `routes.test.tsx` imports missing `@/app/*`, and `country-medal-heatmap.test.tsx` has an ambiguous cell query.
- [ ] Wiki-Brain page/log update was attempted for `[[FenceSpace Tournament Bracket]]` but blocked by the platform approval/usage gate because the Brain vault is outside the writable workspace.

Notes:
- Support files `frontend/package.json`, `frontend/tsconfig.json`, and `frontend/vitest.config.ts` were adjusted only to make the existing frontend scaffold and Vitest/TS 6 checks runnable.
- `npm install` reports 2 moderate dependency audit findings; `npm audit fix --force` was not run because it would be a broad dependency change.
- Do not edit `.github/workflows/`.

---

# Agent 71 — Veterans World Cup circuit

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected graph/session memory and nearby FIE/EVF/result scraper patterns.
- [x] Probed FIE/EVF/FTL public veteran source shapes and blocked sources.
- [x] Added red-first tests in `tests/test_scrape_veterans.py` for EVF age categories, medals, missing points, explicit category isolation, FIE veteran `hasResults=0`, blocked/no-public source stubs, conservative matching, unmatched logging, and all-unmatched write safety.
- [x] Added `scrape_veterans.py` with EVF static result parsing, FIE veteran result-attempt guard, blocked source classification, fencer matching by FIE ID then canonical name+country, no null-fencer result inserts, run logging, and scraper state.
- [x] Verification: red `tests/test_scrape_veterans.py -v` failed first on missing module and later on the added edge cases; final focused `.venv/bin/python -m pytest tests/test_scrape_veterans.py -v` passed 7/7; `.venv/bin/python -m py_compile scrape_veterans.py tests/test_scrape_veterans.py` passed; `git diff --check -- scrape_veterans.py tests/test_scrape_veterans.py tasks/todo.md` passed.
- [x] Broader verification: final `.venv/bin/python -m pytest tests/ -v` failed outside this task with 2 failed, 1916 passed, and 1 warning. Failures were `tests/test_export_bigquery.py::test_resume_continues_from_saved_offset_and_chunk_number` and `tests/test_fencing_stores.py::test_parse_pbt_dealers_extracts_live_dealer_nodes`; all veterans tests passed inside the full run.
- [ ] Wiki-Brain/session log update was attempted for `[[FenceSpace Veteran Fencing Data Sources]]` but blocked because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace and the approval gate rejected the edit due usage limits.

Notes:
- Files changed for this task: `scrape_veterans.py`, `tests/test_scrape_veterans.py`, `tasks/todo.md`.
- Web probe evidence: EVF 2025 Plovdiv results expose static HTML medal rows by weapon and `Category 1`-`Category 4`; EVF circuit/ranking pages describe public rankings/circuit but do not expose row data on those pages; EVF Circuit Poland 2025 schedule is public but FencingTimeLive event result links redirect to login as of 2026-06-02; FIE 2025 Veteran World Championships article links complete official results to Dropbox, while FIE entry PDFs are public but are entry lists rather than result tables.
- Remaining risk: local live requests probe failed on sandbox DNS and the required escalated retry was rejected by the platform usage-limit gate; runtime keeps blocked/no-public sources deterministic and does not invent fallback result rows.

---

# Agent 130 Athlete Trivia — Final Review

- [x] Read project lessons and current task state.
- [x] Inspected career stats, medal table, identity, API, migration, and frontend component/test patterns.
- [x] Wrote red-first backend tests for deterministic fact-backed question generation, distractors, minor/sensitive filtering, Supabase upsert behavior, and migration shape.
- [x] Added `compute_trivia.py` and `supabase/migrations/20260602_trivia_questions.sql`.
- [x] Wrote red-first frontend component tests after the frontend app appeared in the checkout.
- [x] Added `frontend/components/AthleteQuiz.tsx` with empty state, answer reveal, score state, source display, next, and restart flow.
- [x] Verification: focused backend trivia tests passed 5/5; related backend tests passed 11/11; frontend targeted quiz tests passed 2/2; quiz plus nearby timeline tests passed 8/8.
- [ ] Full Python suite has unrelated active-agent failures: 47 failed, 1851 passed, 1 warning. Trivia tests passed inside that run.
- [ ] Full frontend suite has unrelated failures: 3 failed, 10 passed test files; 6 failed, 57 passed tests. Quiz targeted tests passed.
- [ ] CRG change review was skipped because the platform usage-limit gate rejected the tool call.
- [ ] Wiki-Brain page/index/log write was attempted but rejected by the platform usage-limit gate; no workaround was attempted.

Notes:
- Files changed for this task: `compute_trivia.py`, `tests/test_trivia.py`, `supabase/migrations/20260602_trivia_questions.sql`, `frontend/components/AthleteQuiz.tsx`, `frontend/tests/athlete-quiz.test.tsx`, `tasks/todo.md`.
- `frontend/package.json` and `frontend/package-lock.json` are untracked frontend files from concurrent work; `npm install jsdom@27.2.0` and `npm install lucide-react@1.17.0` repaired missing declared dependencies so Vitest could run.
- Do not edit `.github/workflows/`.

---

# Agent 63 FFSU Fencing Results — Final Review

- [x] Read project lessons and current task state.
- [x] Probed public FFSU fencing pages with browser evidence; local requests probe was blocked by sandbox DNS and escalation was rejected by the platform usage-limit gate.
- [x] Added red-first tests for French PDF/HTML/XLSX parsing, accented names, summary rows, repeated multi-page headings, season/university normalization, no-public-data stub behavior, and Supabase mapping/unmatched rows.
- [x] Added `scrape_ffsu.py` with sport-u result discovery, French parser normalization, deterministic missing-data stub, best-effort `fs_fencers` matching, `fs_tournaments`/`fs_results` writes, run logging, state tracking, and rate limiting.
- [x] Verification: red `tests/test_scrape_ffsu.py -v` failed first because `scrape_ffsu` was missing; focused suite now passes 9/9; `py_compile scrape_ffsu.py` passes; schema search found existing `fs_results.points` usage.
- [ ] Wiki-Brain page/index/log update was attempted but blocked because `/Users/plernghomhual/Documents/Brain` is outside the writable project root and the approval system rejected the write; no workaround was attempted.
- [ ] One untracked `__pycache__/scrape_ffsu.cpython-314.pyc` cleanup remains blocked after the final removal command was rejected by the platform usage-limit gate.

Notes:
- Files changed for this task: `scrape_ffsu.py`, `tests/test_scrape_ffsu.py`, `tasks/todo.md`.
- Public source: `https://sport-u.com/sports-ind/ESCRIME/` links CFU fencing result PDFs for 2022-2024 and a 2025 results spreadsheet.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

---

# Agent 153 — Transfer Impact Score

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected nearby analytics compute/test/migration patterns.
- [x] Added red-first tests for transparent component scoring, missing-data confidence penalties, no fabricated age values, sparse-data no-score behavior, idempotent upsert, and migration shape.
- [x] Added `compute_transfer_value.py` with non-monetary `value_score` rows, `score_components`, confidence scoring, identity-aware grouping, run logging, and scraper state updates.
- [x] Added `supabase/migrations/20260602_transfer_value.sql` for internal `fs_transfer_values`.
- [x] Ran focused, syntax, and full-suite verification.
- [x] Updated task memory; Wiki-Brain page/log write was attempted but blocked by the approval usage-limit gate.

Notes:
- Files changed for this task: `compute_transfer_value.py`, `tests/test_transfer_value.py`, `supabase/migrations/20260602_transfer_value.sql`, `tasks/todo.md`.
- Behavior changed: transfer impact scores use public ranking, performance, form, age, and category signals where present; sparse rows keep missing-signal reasons and lower confidence; age/category-only rows get no `value_score`.
- Verification: red `tests/test_transfer_value.py -v` failed first because the module/migration were missing; focused transfer-value suite now passes 6/6; `py_compile compute_transfer_value.py` passes; final full `.venv/bin/python -m pytest tests/ -v` ran 1917 passed, 2 unrelated failures.
- Remaining full-suite failures: `tests/test_fed_srb.py::test_fetch_rankings_page_does_not_confuse_explicit_women_heading_for_men`; `tests/test_fencing_stores.py::test_parse_pbt_dealers_extracts_live_dealer_nodes`.
- Wiki-Brain required write target is outside the workspace and the required approval was rejected by the platform usage-limit gate; no workaround was attempted.
- `tasks/todo.md` is being concurrently rewritten by other agents; preserve unrelated sections.

---

# Agent 138 Google Club Review Scraper — Final Review

- [x] Added red-first tests for no-key behavior, Google API parser output, source-specific upsert idempotence, and ambiguous match rejection.
- [x] Implemented `scrape_google_club_reviews.py` as Google Places/Maps API-only enrichment gated by `MAPS_API_KEY`.
- [x] Loaded and deduped club candidates from `fs_club_reviews`, `fs_club_rankings`, and `fs_fencers`.
- [x] Stored only `source = "google_maps"` rows with `normalized_club_name,city,country,source` conflict handling.
- [x] Verification: focused Google tests passed 4/4; `py_compile` passed; no-key CLI path exited 0; no HTML-scraping patterns were found.
- [x] Wiki-Brain page update succeeded in `[[FenceSpace Club Reviews Scraper]]`.
- [ ] Full suite remains red in unrelated areas: 55 failed, 17 errors.
- [ ] Google endpoint probe, CRG change detection, tracked cache cleanup, and required `Brain/log.md` append were blocked by sandbox/approval usage-limit gates.

---

# Agent 121 — Headshot Dedup Review

## Final Review
- [x] Read project lessons and relevant headshot/media patterns.
- [x] Added tests for hash/perceptual dedupe, corrupt/missing images, no auto-delete/merge, optional mocked embeddings, and migration privacy docs.
- [x] Added `dedupe_headshots.py` with review-candidate-only duplicate detection.
- [x] Added `supabase/migrations/20260602_headshot_dedup.sql` for a private manual review table.
- [x] Ran focused and full verification.
- [x] Updated task memory; Wiki-Brain page/log write was attempted but blocked by the external approval usage-limit gate.

Notes:
- Files changed for this task: `dedupe_headshots.py`, `tests/test_dedupe_headshots.py`, `supabase/migrations/20260602_headshot_dedup.sql`, `tasks/todo.md`.
- Behavior changed: identical URL/local path, normalized content hash, perceptual hash distance, and optional face embeddings produce pending `fs_headshot_duplicate_reviews` rows only.
- No images are deleted and no fencer identities are merged or updated by the dedupe path.
- Verification: focused `tests/test_dedupe_headshots.py -v` passed 6/6; `py_compile dedupe_headshots.py` passed; full `tests/ -v` ran 1886 passed and 20 unrelated failures.
- Remaining risks: remote storage URLs are not fetched for image hashing unless `HEADSHOT_DEDUPE_ALLOW_REMOTE_IMAGES` is enabled; optional face embedding support depends on `face_recognition`; Wiki-Brain external write was blocked by approval usage limits.

---

# Agent 73 — Asian Fencing Confederation

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected nearby championship/result scraper patterns and fencer matching lessons.
- [x] Probed AFC/host source URLs from the sandbox; all DNS lookups failed, and the required escalated network probe was rejected by the platform usage gate.
- [x] Added red AFC parser, country, blocked-source, PDF ranking, and fencer-matching tests.
- [x] Added `scrape_afc.py` with multilingual HTML/PDF table parsing, Asian country code normalization, blocked-source stubs, conservative fencer matching, run logging, and scraper state.
- [x] Ran focused verification, compile check, and deterministic blocked-source probe.

Notes:
- Files changed for this task: `scrape_afc.py`, `tests/test_scrape_afc.py`, `tasks/todo.md`.
- Individual result rows are written only when matched by FIE ID, exact name+country, or identity table row IDs; unmatched individual rows are logged and skipped instead of creating null-fencer orphans.
- Default live AFC sources are currently stubbed as blocked with probe evidence because network escalation was rejected by the platform usage gate.
- Verification: red `tests/test_scrape_afc.py -v` failed first with missing `scrape_afc`; focused AFC suite now passes 6/6; `py_compile scrape_afc.py tests/test_scrape_afc.py` passes; deterministic `probe_sources()` reports 5/5 blocked default sources with evidence.
- Wiki-Brain write/log was attempted but blocked by the platform approval/usage gate because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

---

# Agent 8 — Tournament Brackets Schema

## Final Review
- [x] Read lessons, current task state, CRG context, and relevant `fs_bouts`/`fs_results`/`fs_tournaments` usage.
- [x] Confirmed bracket consumers already expect `fs_tournament_brackets` via `compute_brackets.py` and `api/v1/tournament_brackets.py`.
- [x] Added red parser tests for table shape, compute/API columns, recompute uniqueness, indexes, nullability, and non-destructive SQL.
- [x] Added `supabase/migrations/20260602_tournament_brackets.sql`.
- [x] Ran focused, adjacent bracket, whitespace, and full-suite verification.

Notes:
- Files changed for this task: `supabase/migrations/20260602_tournament_brackets.sql`, `tests/test_tournament_brackets_schema.py`, `tasks/todo.md`.
- The schema uses `UNIQUE (tournament_id, event_key, round_order, bout_order)` for idempotent recompute and `bracket_key` as a stable row identity.
- Nullable fencer IDs, seed values, scores, event ID, and winner support byes, incomplete brackets, missing seeds, and unmatched fencers.
- Full suite has 19 unrelated failures outside this task; focused bracket tests pass.
- Full pytest generated `__pycache__` churn; cleanup was blocked by the approval/usage gate.
- Wiki-Brain update and `/Users/plernghomhual/Documents/Brain/log.md` append were blocked by the same approval/usage gate because those files are outside the writable repo root.

---

# Agent 141 — TikTok Fencing Content Aggregator

## Final Review
- [x] Read project lessons, current task state, CRG/context memory, and relevant social scraper patterns.
- [x] Confirmed no configured `TIKTOK_PROVIDER_API_URL`/`TIKTOK_PROVIDER_API_KEY`; live provider probe is blocked by unavailable API access, so no private/login-gated TikTok access was attempted.
- [x] Added red tests for no-key dry-run behavior, API fixture parsing, hashtag/fencer matching, provider rate-limit/error handling, malformed provider items, and migration DDL.
- [x] Added `scrape_tiktok_fencing.py` with approved-provider-only collection, fixture dry-run default, public metadata normalization, fencer matching, rate limiting, provider errors, state, and run logging.
- [x] Added `supabase/migrations/20260602_tiktok_fencing_videos.sql` for public TikTok video metadata storage.
- [x] Ran focused, adjacent, compile, no-key runtime, and full-suite verification.

Notes:
- Files changed for this task: `scrape_tiktok_fencing.py`, `tests/test_tiktok_fencing.py`, `supabase/migrations/20260602_tiktok_fencing_videos.sql`, `tasks/todo.md`.
- Full suite has 29 failures in other in-progress agent areas; new TikTok tests pass.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

---

# Agent 67 — IWAS World Games and satellite wheelchair events

## Final Review
- [x] Read lessons, prior task state, existing IWAS/Paralympic code, logger/state helpers, and fencer matching patterns.
- [x] Probed public source structures via browser-accessible pages; shell live probe was blocked by sandbox DNS and escalation usage limits.
- [x] Added red tests for historic source mapping, HTML/PDF parsing, missing public data stubs, FIE `hasResults` override, explicit fencer matching, unmatched logging, and rate limiting.
- [x] Added `scrape_iwas_games.py`.
- [x] Ran targeted, adjacent, compile, and full-suite verification.

Notes:
- Public source shapes used: World Para Fencing historic results page, Ophardt `/en/search/results/{id}` pages, Paralympic wheelchair fencing archive pages, and World Abilitysport past competition pages.
- Individual result rows are inserted only when matched by FIE ID or normalized name+country. Unmatched rows are returned/logged and skipped to avoid null-fencer result orphans.
- Missing public download rows create deterministic tournament stubs with evidence metadata instead of invented result data.
- Full suite has 29 unrelated failures outside this task.

---

# Agent 35 — Turkey Federation Scraper

## Plan
- [x] Read project lessons, current task state, and federation ranking scraper patterns.
- [x] Probe Turkey federation ranking pages and record public source evidence.
- [x] Write failing parser/fetch tests with realistic Turkish ranking fixtures.
- [x] Implement `scrape_fed_tur.py` using public ranking PDFs, `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: Brain vault write rejected by approval usage gate.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Requested host `trfencing.gov.tr` did not resolve in the sandboxed local probe; current public federation host found via live web probe is `https://www.eskrim.org.tr`.
- Public rankings page: `https://www.eskrim.org.tr/klasmanlar-20.html`.
- Request method: GET. Response formats: ranking index is HTML; ranking details are public PDF assets under `/resim/extra/Klasmanlar/...`.
- Public coverage on the current index: all 12 requested Senior/Junior Foil/Epee/Sabre Men/Women combos.
- Local escalated probe was rejected by the usage-limit approval gate, so implementation uses browser/web probe evidence and runtime dynamic link discovery.
- Wiki-Brain page/index/log writes were attempted but rejected by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable sandbox.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_fed_tur.py`, `tests/test_fed_tur.py`, `tasks/todo.md`.
- Behavior changed: added Turkey federation scraper with dynamic public PDF link discovery, PDF/table/text parsing for Turkish ranking rows, UTF-8 Turkish header handling, graceful 404/network/blocked/login/JS/missing-combo handling, run logging, state metadata, and 12-combo iteration.
- Verification: red focused run first failed 15/15 on missing `scrape_fed_tur`; focused `.venv/bin/python -m pytest tests/test_fed_tur.py -v` now passes 15/15; `.venv/bin/python -m py_compile scrape_fed_tur.py tests/test_fed_tur.py` passes.
- Remaining risks: local live fetch/parse smoke and Wiki-Brain update could not be completed because sandbox DNS/out-of-workspace writes require escalation and the required approvals were rejected by the usage-limit gate; the scraper discovers the current PDF links at runtime to reduce stale URL risk.

---

# Agent 120 — Data marketplace / API monetization portal

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected existing export API, API key migration, and RLS/public-view patterns.
- [x] Added red-first marketplace tests for Stripe webhook signatures/idempotency, subscription/scope authorization, usage counters, live-key blocking, migration shape, and no-secret logging.
- [x] Added `marketplace_api.py`.
- [x] Added `supabase/migrations/20260602_marketplace.sql`.
- [x] Added `docs/marketplace.md`.
- [x] Ran focused syntax/tests and full-suite verification.

Notes:
- Marketplace keys are stored as hashes, not raw values.
- Stripe Checkout/Portal helpers block live keys unless `FENCESPACE_ALLOW_LIVE_STRIPE=true`.
- Webhooks verify the raw payload HMAC before JSON parsing and use `fs_stripe_webhook_events.id` for idempotency.
- Access is gated by active/trialing subscription status, effective key/plan scopes, and monthly usage limits.
- Full `tests/ -v` failed outside this task with 46 unrelated failures; all marketplace tests passed.

---

# Agent 146 Video Auto-Trimmer

## Final Review
- [x] Read relevant lessons and current repo state.
- [x] Confirmed `video_trimmer.py`, `tests/test_video_trimmer.py`, and `docs/video_trimmer.md` are new in this checkout.
- [x] Added red-first metadata/chapter, confidence, dry-run, missing-ffmpeg, and command-construction tests.
- [x] Implemented metadata-first trim candidate planning and local-only ffmpeg command planning.
- [x] Documented dry-run default, local-video requirement, ffmpeg behavior, limitations, and manual review requirement.
- [x] Ran focused verification and broad pytest checks.
- [x] Update project task memory; Wiki-Brain/session log write blocked by approval gate.

## Notes
- Scope stayed on `video_trimmer.py`, `tests/test_video_trimmer.py`, `docs/video_trimmer.md`, and task/wiki memory.
- The tool does not download YouTube videos. It only trims when `execute=True`, an explicit local video path exists, and ffmpeg is available.
- Full `.venv/bin/python -m pytest tests/ -v` stopped during collection on unrelated missing `compute_junior_conversion`.
- Broad retry with `--ignore=tests/test_junior_conversion.py` failed outside this task: 48 failed, 1795 passed, 17 errors, 8 warnings. `tests/test_video_trimmer.py` passed.
- Running broad tests dirtied tracked Python cache files. Restoring them required `.git` write access; escalation was blocked by the environment usage-limit gate.

---

# Agent 74 African Fencing Confederation Championships

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected Commonwealth/continental/FIE result scraper patterns and fencer identity matching conventions.
- [x] Probed CAE official pages, older mirror, FencingWorldwide/FencingTimeLive, FIE event pages/articles, and public PDF surfaces.
- [x] Added focused tests for French/Arabic/English sparse result parsing, FencingWorldwide link discovery, no-public-data stubs, and explicit fencer matching/skipping.
- [x] Added `scrape_african_conf.py`.
- [x] Verified focused African Confederation tests and syntax compile pass.

Notes:
- Files changed: `scrape_african_conf.py`, `tests/test_scrape_african_conf.py`, `tasks/todo.md`.
- Behavior changed: African Confederation scraper now discovers/probes public sources, parses sparse HTML/text/PDF-like result rows with source evidence, normalizes French/Arabic/English headers and African country names, writes tournaments/results, logs unmatched individual rows, and skips unmatched individual placements instead of inserting null-fencer orphans.
- Local Python live probe was blocked by sandbox DNS; escalated retry was rejected by the platform usage-limit approval gate. Web probe evidence confirmed: CAE links Lagos coverage to FencingWorldwide/FencingTimeLive; FencingWorldwide has public result/event pages; FencingTimeLive is login-gated; the older `afrique-escrime.org` mirror has no durable structured results; FIE pages/articles/PDFs preserve official metadata/medallist evidence.
- Verification: red focused run failed 7/7 on missing module before implementation; focused `.venv/bin/python -m pytest tests/test_scrape_african_conf.py -v` now passes 8/8; `.venv/bin/python -m py_compile scrape_african_conf.py tests/test_scrape_african_conf.py` passes.
- Remaining risks: full live import was not run because Supabase credentials/network access were not available in this shell; CRG change review and Wiki-Brain page/index/log writes were blocked by the platform usage-limit gate; `tasks/todo.md` is being concurrently rewritten by other agents.

---

# Agent 65 USA Y12/Y14 Youth Circuit Results

## Final Review
- [x] Read lessons and current task state.
- [x] Inspected existing FRED/result/youth scraper patterns.
- [x] Probed current USA/FRED public result access; local shell DNS and escalated network retry were blocked, while browser evidence confirmed public FRED UUID result pages and CSV exports.
- [x] Added red-first tests for Y12/Y14 parsing, age normalization, privacy/no-profile fetching, blocked endpoint stubs, explicit fencer matching, and null-fencer insert rejection.
- [x] Implemented `scrape_usa_youth.py` with public FRED HTML/CSV parsing, Y12/Y14 national-circuit filtering, cautious FIE/identity/name-country matching, unmatched logging/skipping, run logging, and state tracking.
- [x] Ran focused verification, compile check, and full-suite check.
- [ ] Update Wiki-Brain/session log. Blocked: out-of-workspace write escalation was rejected by the approval usage gate.

Notes:
- Files changed for this task: `scrape_usa_youth.py`, `tests/test_scrape_usa_youth.py`, `tasks/todo.md`.
- Behavior changed: USA youth imports now parse public FRED Y12/Y14 event results while avoiding linked member/private pages and never inserting unmatched minor rows with `fencer_id = NULL`.
- Verification: red focused run failed 6/6 on missing module; `py_compile scrape_usa_youth.py tests/test_scrape_usa_youth.py` exited 0; focused `pytest tests/test_scrape_usa_youth.py -v` passed 6/6.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed with 1849 passed, 46 failed, 1 warning. Failures were outside this task, including aggregate video/anomaly/camp review/federation/product/frontend/API tests.
- Remaining risk: live shell probe of public FRED/USA Fencing endpoints could not complete due sandbox DNS plus usage-limit rejection, so implementation records blocked endpoint stubs and tests use realistic public FRED fixtures from current page structure.

---

# Agent 156 Fencer Sponsorship Matchmaking

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected sponsorship-adjacent equipment/social/performance schemas and compute/test patterns.
- [x] Added red-first tests in `tests/test_sponsorship_matches.py` for scoring components, minor filtering, sparse data, no-outreach side effects, upsert conflict key, and migration DDL.
- [x] Added `compute_sponsorship_matches.py`.
- [x] Added `supabase/migrations/20260602_sponsorship_matches.sql`.
- [x] Verified focused sponsorship tests pass.

Notes:
- The matcher writes only `fs_sponsorship_matches` with `on_conflict="brand,fencer_id"` and does not touch outreach/email/message/contact/campaign tables.
- Known minors and explicitly ineligible fencers are excluded unless metadata carries an explicit minor-sponsorship policy allow flag.
- Missing social/equipment/weapon/age data lowers confidence and appears in the explanation rather than blocking performance/geography matches.
- Full `tests/ -v` failed outside this task: 48 failed, 1801 passed, 17 errors, 8 warnings. No sponsorship-match tests failed.
- `tasks/todo.md` is being concurrently rewritten by other agents; preserve unrelated sections.

---

# Agent 77 Legacy Score

## Plan
- [x] Read project lessons, current task state, graph context, and adjacent score/medal/identity patterns.
- [x] Write failing tests for `fs_fencer_legacy_scores` schema, tier-field weights, duplicate result handling, team/individual medal normalization, empty data, and Supabase upsert behavior.
- [x] Implement `compute_legacy_score.py` using explicit tournament tier/type fields and `fs_fencer_identities`.
- [x] Add `supabase/migrations/20260602_legacy_score.sql` for explainable identity-scoped storage.
- [x] Run focused pytest verification and compile check.
- [x] Run full pytest suite and record unrelated failures.
- [ ] Update Wiki-Brain/session log. Blocked: write to `/Users/plernghomhual/Documents/Brain` was rejected by approval usage-limit guard; do not retry via workaround.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Scope stayed on `compute_legacy_score.py`, `supabase/migrations/20260602_legacy_score.sql`, `tests/test_legacy_score.py`, and task/wiki memory.
- `fs_tournaments.type` is overloaded in existing code: some rows use tier values (`WCH`, `GP`), while FIE history stores event kind (`individual`, `team`). Legacy-score tier resolution treats only recognized tier aliases as tier weights and uses `team`/`individual` only for event normalization.
- The legacy score never infers tier from tournament names; name-only rows remain `Unclassified` at weight `1.0`.

## Final Review
- Files changed: `compute_legacy_score.py`, `supabase/migrations/20260602_legacy_score.sql`, `tests/test_legacy_score.py`, `tasks/todo.md`.
- Behavior changed: legacy scores are computed per `fs_fencer_identities.id`, duplicate result rows are suppressed per identity/event, team medals/results use a `0.6` multiplier, and score/medal/tier/event breakdowns are stored for explainability.
- Verification: red focused run failed 5/5 before implementation; focused `.venv/bin/python -m pytest tests/test_legacy_score.py -v` passes 5/5; `.venv/bin/python -m py_compile compute_legacy_score.py` passes.
- Full-suite check: `.venv/bin/python -m pytest tests/ -v` reports legacy-score tests passed, but overall suite fails outside this task with 45 failed, 1809 passed, 17 errors, 8 warnings.
- Remaining risks: CRG impact review was blocked by the platform usage-limit gate; this task did not apply the migration to Supabase.

---

# Agent 60 — Malta Federation Scraper

## Final Review
- [x] Read project lessons/todo, graph context, and federation scraper patterns.
- [x] Probed `maltasrim.com` with GET/browser headers for apex/www HTTP/HTTPS and ranking/result/API/wp-json paths; all sandbox probes failed DNS, and escalated confirmation was rejected by the approval usage gate.
- [x] Added `scrape_fed_mlt.py` as a documented 0/12 public-combo stub with all standard Senior/Junior Foil/Epee/Sabre Men/Women combos, robust HTML/delimited parser, future `PUBLIC_RANKING_URLS` support, run logging, and state recording.
- [x] Added `tests/test_fed_mlt.py` covering parser rows, empty/no-data pages, malformed/non-numeric/DNS/DQ/summary rows, UTF-8/native names, 12 combos, 404/network/blocked/login/JS fetch handling, and main-loop 12-combo attempts.
- [x] Verification: red focused tests first failed with missing module; `.venv/bin/python -m pytest tests/test_fed_mlt.py -v` now passes 14/14; `py_compile` passes; live stub run exits 0 with `combos_working=0/12`.
- [x] Wiki-Brain page/index/log writes attempted but blocked by the approval usage-limit gate.

Risks: Malta rankings may exist behind another domain, login, JS-only app, or inaccessible source; add confirmed public URLs to `PUBLIC_RANKING_URLS` when found.

---

# Agent 39 — Chinese Taipei Federation Scraper

## Plan
- [x] Read project lessons, current task state, graph context, and federation scraper patterns.
- [x] Probe `fencing.org.tw` public ranking pages and current workbook exposure.
- [x] Write focused parser/fetch tests with realistic Traditional Chinese fixtures.
- [x] Implement `scrape_fed_tpe.py` using public workbook discovery, `fed_rankings_common`, run logging, and state tracking.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: writing `/Users/plernghomhual/Documents/Brain` requires escalation, and the Codex approval usage gate rejected the scoped write request.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Browser/search probe reached `https://www.fencing.org.tw/` and confirmed public homepage ranking links to `x.webdo.cc` XLSX workbooks.
- Current public homepage evidence exposes `青年組排名(115-1)(公告版).xlsx`, `青少年組排名(115-1)(公告版).xlsx`, and `少年組排名(115-1)(公告版).xlsx`; no current senior full-ranking workbook was visible.
- Local shell live probe was blocked by sandbox DNS; escalation for read-only network probe was rejected by the approval usage gate.
- Wiki-Brain page/index/log writes were also rejected by the approval usage gate, so this task note is the local memory fallback.

## Final Review
- Files changed: `scrape_fed_tpe.py`, `tests/test_fed_tpe.py`, `tasks/todo.md`.
- Behavior changed: added Chinese Taipei federation scraper with dynamic public XLSX discovery, Junior workbook combo extraction, Traditional Chinese parser support, graceful missing/blocked/login/JS/404 handling, run logging, and state metadata.
- Verification: red focused test run first failed on missing module; focused `tests/test_fed_tpe.py -v` now passes 12/12; `py_compile scrape_fed_tpe.py tests/test_fed_tpe.py` passes.
- Remaining risk: current public evidence supports Junior Foil/Epee/Sabre Men/Women only; Senior combos are attempted and logged as no scrapeable public ranking source until a current senior workbook appears.

---

# Agent 44 Portugal Federation Scraper

## Plan
- [x] Read project lessons, current task state, graph context, and existing federation scraper patterns.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Attempt live probe for `fpesgrima.pt` ranking URL structure.
- [x] Write failing Portugal parser/fetch tests with realistic Portuguese/Ophardt fixtures.
- [x] Implement `scrape_fed_por.py` using `fed_rankings_common`, `ScraperRunLogger`, scraper state, and season fallback.
- [x] Run focused verification and fix failures.
- [x] Record Wiki-Brain/session-log blocker and final review.

## Notes
- Keep scope to `scrape_fed_por.py`, `tests/test_fed_por.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Non-escalated live probe against `fpesgrima.pt` and common ranking paths failed with sandbox DNS `NameResolutionError`.
- Required escalated network probe was rejected by the environment usage-limit approval gate, so live Portugal public combo coverage is not verified in this shell.
- Existing federation pattern for Portugal-like public sources is Ophardt GET HTML with dynamic/defensive combo handling and non-fatal missing combos.

## Final Review
- Files changed: `scrape_fed_por.py`, `tests/test_fed_por.py`, `tasks/todo.md`.
- Behavior changed: added Portugal federation scraper that attempts all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos through official FP Esgrima pages and linked public Ophardt ranking indexes; parses Portuguese/Ophardt HTML rows with UTF-8 names, decimal commas, Portuguese headers, nested detail tables, and DNS/DQ/summary skips; logs missing/failed combos without crashing.
- Verification: red focused test run first failed with missing `scrape_fed_por`; focused `./.venv/bin/python -m pytest tests/test_fed_por.py -v` passed 11/11; `./.venv/bin/python -m py_compile scrape_fed_por.py` passed; shared `tests/test_fed_rankings_common.py -v` passed 5/5; no-delay runtime smoke exited 0 and attempted all 12 combos.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed from captured log with 1741 passed, 91 failed, 8 warnings. Failures are unrelated in-progress areas outside the requested Portugal files.
- Remaining risks: live public Portugal ranking coverage could not be verified because DNS was blocked in the sandbox and escalated probing was rejected by the environment usage-limit gate; runtime smoke therefore found 0/12 working combos in this shell.

---

# Agent 130 Athlete Trivia

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing career stats, medal, identity, API, and migration patterns.
- [x] Write failing trivia generator and migration tests.
- [x] Implement deterministic, safe trivia generation and storage.
- [ ] Run focused/full verification and fix failures.
- [x] Update final review; Wiki-Brain/session log write blocked by approval gate.

## Notes
- Scope stayed on `compute_trivia.py`, `tests/test_trivia.py`, `supabase/migrations/20260602_trivia_questions.sql`, and task/wiki memory.
- Frontend app files are absent in this scraper checkout; document `AthleteQuiz` component requirements instead of adding untestable frontend scaffolding.
- Do not edit `.github/workflows/`.

---

# Agent 59 Iceland Federation Scraper

## Plan
- [x] Read project lessons, current task state, graph context, and federation scraper patterns.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe Iceland public ranking sources and record public combo coverage.
- [x] Write failing parser/fetch tests with realistic Icelandic ranking fixtures.
- [x] Implement `scrape_fed_isl.py` with parser, safe stub fetch behavior, run logging, and state.
- [x] Run focused verification and fix failures.
- [x] Update final review.
- [ ] Update Wiki-Brain/session log when the environment allows writes outside the repo.

## Probe Notes
- Shell HTTP probe was blocked by the current approval limit; browser/search probe was used.
- `https://www.fencing.is/` is public `GET text/html` and identifies as Iceland fencing/club Wix content.
- `https://www.fencing.is/frettir` is public `GET text/html`; it lists Iceland fencing news and public PDFs under `/_files/ugd/...pdf`.
- Searches for public Icelandic ranking terms (`Stigalisti`, `Sæti`, `Nafn`, `Félag`, `Stig`) did not find a durable national senior/junior weapon/gender ranking table or downloadable ranking file.
- Public combo coverage found: 0/12 Senior/Junior Foil/Epee/Sabre Men/Women combos.

## Final Review
- Files changed: `scrape_fed_isl.py`, `tests/test_fed_isl.py`, `tasks/todo.md`.
- Behavior changed: Iceland federation rankings now have a self-contained stub scraper that attempts all 12 standard Senior/Junior weapon/gender combos, exits 0 with skipped combos when no public source is known, logs run/state metadata, and includes a real Icelandic table/text parser for `Sæti/Nafn/Félag/Stig` rows.
- Verification performed: red `tests/test_fed_isl.py -v` failed 14/14 before implementation because the module was missing; focused Iceland tests passed 14/14; `py_compile` passed; no-credential smoke run exited 0 with written=0, failed=0, skipped=12, combos_working=0/12.
- Full-suite check: `.venv/bin/python -m pytest tests/ -v --tb=short` stopped during collection with unrelated missing module `compute_junior_conversion` imported by `tests/test_junior_conversion.py`.
- Remaining risks: no durable public Iceland rankings source was found from the browser/search probe; live shell probe could not be completed because escalation was rejected by the approval usage gate.

---

# Agent 15 Country Geo Backfill

## Final Review
- [x] Read lessons and current task state.
- [x] Inspected venue geocoding, scraper state, rate limiter, medal/country analytics, and country-code prompt context.
- [x] Added failing tests for country normalization, static lookup priority, Nominatim fallback, failure cache, no-network dry run, source-table collection, and rate-limited fallback behavior.
- [x] Implemented `scripts/geocode_countries.py`.
- [x] Ran focused verification and compile check.
- [x] Attempted Wiki-Brain update; blocked by platform usage-limit gate.

## Notes
- Files changed for this task: `scripts/geocode_countries.py`, `tests/test_geocode_countries.py`, `tasks/todo.md`.
- Behavior changed: new country geocode backfill reads `fs_fencers`, `fs_tournaments`, and `fs_medal_tables`; resolves embedded ISO/NOC/FIE centroid aliases first; falls back to Nominatim only for unresolved codes; persists Nominatim failures and missing countries in `fs_scraper_state`; supports dry-run/no-network mode; upserts rows by `alpha3`.
- Verification: red `.venv/bin/python -m pytest tests/test_geocode_countries.py -v` failed 7/7 on missing `scripts.geocode_countries`; green focused run passed 7/7; `.venv/bin/python -m py_compile scripts/geocode_countries.py tests/test_geocode_countries.py` passed.
- Remaining risks: default target table is `fs_country_geocodes`; this task did not add a migration because the user-scoped files did not include one and adjacent Agent 18 owns `fs_country_codes`.

---

# Agent 40 Morocco Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing federation scraper/common/season patterns.
- [x] Probe `frmescrime.ma` public ranking URLs and record coverage.
- [x] Add failing Morocco parser/fetch tests from realistic French/Arabic fixtures.
- [x] Implement `scrape_fed_mar.py`.
- [x] Run focused verification and fix failures.
- [x] Record Wiki-Brain/session log blocker.

## Final Review
- Files changed: `scrape_fed_mar.py`, `tests/test_fed_mar.py`, `tasks/todo.md`.
- Behavior changed: Morocco federation rankings now have a self-contained stub scraper that attempts all 12 standard Senior/Junior weapon/gender combos, logs the unavailable public source, exits 0, and includes a French/Arabic HTML table parser ready for any future durable public ranking URL.
- Verification performed: red `tests/test_fed_mar.py -v` failed on missing module; focused Morocco tests passed 12/12; focused Morocco plus shared federation common tests passed 17/17; `py_compile` passed; no-network smoke run exited 0 with 0/12 working combos.
- Remaining risks: direct live probe could not complete because `frmescrime.ma` failed DNS in the sandbox and the required escalated probe was blocked by the Codex approval usage gate; no public Morocco ranking URL was found from available search context.

---

# Agent 153 — Transfer Impact Score

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect nearby analytics compute/test/migration patterns.
- [x] Write failing tests for transparent component scoring, confidence penalties, no fabricated values, idempotent upsert, and migration shape.
- [ ] Implement `compute_transfer_value.py` with non-monetary `value_score` rows, explicit `score_components`, confidence handling, run logging, and state updates.
- [ ] Add `supabase/migrations/20260602_transfer_value.sql` for `fs_transfer_values`.
- [ ] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review. Blocked: writing `/Users/plernghomhual/Documents/Brain` requires escalation, and escalation was rejected by the usage-limit gate.

## Notes
- Keep scope to `compute_transfer_value.py`, `tests/test_transfer_value.py`, `supabase/migrations/20260602_transfer_value.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Avoid monetary wording; output is a transparent non-monetary `value_score` / transfer impact score.
- Sparse source data should lower confidence or produce no-score rows, never fabricated component values.
- Red verification: `.venv/bin/python -m pytest tests/test_transfer_value.py -v` failed 5/5 because module and migration were missing.
- `tasks/todo.md` is being concurrently rewritten by other agents; preserve unrelated sections.

---

# Agent 11 — Compute Fencer Season Stats

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect season utilities, fencer identity logic, result/bout producers, and existing analytics patterns.
- [x] Write failing tests for season normalization, medals/top counts, bout aggregation, orphan skips, duplicate identities, empty input, and Supabase upsert conflict keys.
- [x] Implement `compute_fencer_season_stats.py` with deterministic aggregation, skipped counts, run logging, state update, and `fs_fencer_season_stats` upserts.
- [x] Run focused verification and fix issues.
- [x] Write local final review; Wiki-Brain/session-log write attempted but blocked by approval usage limit.

## Notes
- Keep scope to `compute_fencer_season_stats.py`, `tests/test_compute_fencer_season_stats.py`, `tasks/todo.md`, and required Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Agent 10 owns the `fs_fencer_season_stats` migration in this task file, so this pass only targets the compute script and focused tests unless schema absence becomes a blocker.

## Final review
- Files changed: `compute_fencer_season_stats.py`, `tests/test_compute_fencer_season_stats.py`, `tasks/todo.md`.
- Behavior changed: added per-season fencer stats computation from `fs_results` and `fs_bouts`, grouped by canonical identity row mapping, normalized `YYYY-YYYY` season, weapon, gender, category, and source confidence; computes starts, finishes, medals/top counts, bout record, touches, win percentage, and prior-season finish deltas.
- Verification: red focused run failed 5/5 on missing module; final focused `.venv/bin/python -m pytest tests/test_compute_fencer_season_stats.py -v` passed 5/5; adjacent stats slice `.venv/bin/python -m pytest tests/test_compute_fencer_season_stats.py tests/test_career_stats.py tests/test_specialization.py -v` passed 10/10; `py_compile` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed with 1908 passed, 7 failed, 1 warning. Failures were outside this task in `tests/test_compute_fencer_stats.py`/`compute_fencer_stats.py` and `tests/test_scrape_allstar_uhlmann.py`.
- Remaining risks: CRG post-change review and Wiki-Brain/session-log writes were blocked by the platform usage-limit approval gate; Agent 10 owns the table migration, so this script assumes `fs_fencer_season_stats` has columns matching the row contract and conflict key.

---

# Agent 28 — Tournament Bracket API

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected API conventions in `api.py`, bracket schema prompts, and frontend bracket prompt.
- [x] Wrote red-first tests for complete brackets, byes, missing scores, filters, invalid tournament IDs, route dependency injection, and response-size overflow.
- [x] Implemented scoped `api/v1/tournament_brackets.py` helper/router without editing shared tournament routing.
- [x] Verified focused and API regression tests pass.

## Notes
- `api.py` is a flat module; no `api/__init__.py` was added to avoid shadowing existing `import api` behavior.
- No committed `fs_tournament_brackets` migration was present in this checkout; helper targets the intended Agent 8 schema and mocked fixtures.
- Codebase-memory frontend search was unavailable due usage-limit approval gate; frontend shape was inferred from the Agent 109 prompt and preserved as grouped events/rounds/bouts.
- Do not edit `.github/workflows/` or shared tournament router files.

## Verification
- Red: `.venv/bin/python -m pytest tests/test_api_tournaments_brackets.py -v` failed 5/5 before implementation because `api/v1/tournament_brackets.py` did not exist.
- Green: `.venv/bin/python -m pytest tests/test_api_tournaments_brackets.py -v` passed 5/5 with one Starlette/httpx deprecation warning.
- Regression: `.venv/bin/python -m pytest tests/test_api.py tests/test_api_tournaments_brackets.py -v` passed 17/17 with the same warning.
- Syntax: `.venv/bin/python -m py_compile api/v1/tournament_brackets.py` passed.

---

# Agent 5 — National Rank Backfill

## Final Review
- [x] Read project lessons/todo and inspected `fs_fencers`, `fs_national_fed_rankings`, `fed_rankings_common.py`, `season_utils.py`, and identity matching patterns.
- [x] Added `supabase/migrations/20260602_national_rank.sql` with nullable idempotent `fs_fencers` national rank columns and a safe partial index.
- [x] Added `scripts/backfill_national_rank.py` to select latest normalized federation-ranking seasons, match fencers by identity/FIE ID/name+country, and upsert guarded rank payloads.
- [x] Added `tests/test_backfill_national_rank.py` for migration SQL, season selection, identity/FIE/name matching, stale/current-conflict skips, missing rankings, and upsert payloads.
- [x] Verification: `.venv/bin/python -m pytest tests/test_backfill_national_rank.py -v` passed 6/6; related `tests/test_season_utils.py tests/test_fed_rankings_common.py tests/test_orphan_matching.py -v` passed 27/27; `py_compile` passed.

Risks:
- Existing schema uses `fs_national_fed_rankings`; no live `fs_federation_rankings` table reference exists in this checkout.
- Wiki-Brain/session-log write and generated `__pycache__` cleanup were blocked by the approval usage-limit gate.
- `tasks/todo.md` was being concurrently rewritten by other work during this session; unrelated task-file changes were not reverted.

---

# Agent 1 Fencer Bio Columns

## Final Review
- [x] Read lessons and current task state.
- [x] Inspected `fs_fencers` migrations, including existing `birth_place text`/`bio_text text` overlap.
- [x] Inspected `scrape_fencers.py` and `scrape_athlete_profiles.py`; `birth_date` is already a DOB candidate column.
- [x] Added red-first migration parser tests in `tests/test_bio_columns.py`.
- [x] Added `supabase/migrations/20260602_fencer_bio_columns.sql`.
- [x] Verified focused tests pass.
- [x] Wiki-Brain update attempted; blocked because `/Users/plernghomhual/Documents/Brain` is outside the writable root and the approval usage-limit gate rejected the write.

Notes:
- Migration is schema-only, nullable, additive, and uses `ADD COLUMN IF NOT EXISTS`.
- It does not backfill existing `bio_text` into new `bio`.
- `tasks/todo.md` is being concurrently rewritten by other agents; do not use this diff as Agent 1-only scope.

---

# Agent 80 — Home Advantage Analytics

## Plan
- [x] Read project lessons and relevant analytics/schema patterns.
- [x] Write failing tests for migration shape, classification, transfer-aware country resolution, aggregate math, and Supabase upserts.
- [x] Add `compute_home_advantage.py` with explicit home/away/unknown classification and aggregate rows.
- [x] Add `supabase/migrations/20260602_home_advantage.sql`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: out-of-workspace write approval was rejected by the usage-limit gate.

## Notes
- Keep code changes scoped to `compute_home_advantage.py`, `supabase/migrations/20260602_home_advantage.sql`, `tests/test_home_advantage.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Base `fs_results`, `fs_tournaments`, and `fs_fencers` creation SQL is not in local migrations; use fallback selects for deployed column drift.
- Prefer explicit `fs_fencer_nationality_history` rows when present; fall back to `fs_fencers.metadata.nationality_history`, then result/fencer country. Do not use current fencer country as a transfer shortcut when event-time history is available.
- Red test run: `.venv/bin/python -m pytest tests/test_home_advantage.py -v` failed 6/6 because the module and migration did not exist.
- Final focused run: `.venv/bin/python -m pytest tests/test_home_advantage.py -v` passed 6/6.
- Syntax/diff checks: `.venv/bin/python -m py_compile compute_home_advantage.py` passed; `git diff --check` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed with 1875 passed and 24 unrelated failures outside `tests/test_home_advantage.py`.
- CRG impact-radius and Wiki-Brain write/log steps were blocked by the account usage-limit approval gate.

## Final Review
- Files changed: `compute_home_advantage.py`, `supabase/migrations/20260602_home_advantage.sql`, `tests/test_home_advantage.py`, `tasks/todo.md`.
- Behavior changed: added transfer-aware home advantage detail and aggregate computation with explicit unknown handling for missing countries, neutral venues, and multi-national hosts.
- Verification: red focused run failed 6/6 before implementation; final focused run passed 6/6; syntax and diff checks passed; full suite has unrelated failures listed above.
- Remaining risks: full suite remains red due unrelated agent areas; Wiki-Brain/log update could not be written because approval was rejected.

---

# Agent 109 — Competition Bracket Visualizer

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect current frontend presence, bracket schema prompts, `fs_bouts` producers, and tournament UI availability.
- [ ] Write failing frontend tests for complete DE brackets, byes/incomplete bouts, accessibility, and mobile overflow.
- [ ] Implement `frontend/lib/brackets.ts` tolerant normalization for `fs_tournament_brackets`/`fs_bouts` row quirks.
- [ ] Implement reusable `frontend/components/BracketVisualizer.tsx` with accessible match cards, horizontal scrolling, and empty/error states.
- [ ] Add minimal frontend test support only if required to run the scoped tests.
- [ ] Run focused verification and fix failures.
- [x] Update final review.
- [ ] Update Wiki-Brain/session log. Blocked by approval usage gate for writes outside the repo.

## Notes
- Keep code changes scoped to the requested `frontend/` component, normalizer, and tests, plus minimal test config/dependency files only if required.
- This checkout currently has no `frontend/` directory, no frontend package setup, and no tournament page to wire into.
- No committed `fs_tournament_brackets` migration/schema was found; only task prompts describe the intended table. The UI normalizer must tolerate likely Agent 8/9 rows without depending on that table being present yet.
- Current `fs_bouts` producers/readers use mixed column names: `fencer_a`/`fencer_b`/`winner`, `fencer_a_id`/`fencer_b_id`/`winner_id`, and score/round fields. Component input should normalize both shapes.
- Do not edit `.github/workflows/`.

---

# Agent 3 Fencer Stats Table

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect fencer identity, bout, and analytics migration/test patterns.
- [x] Write failing schema parser tests for `fs_fencer_stats`.
- [x] Create `supabase/migrations/20260602_fencer_stats.sql`.
- [x] Run focused verification and fix issues.
- [x] Attempt Wiki-Brain/session log and final review.

## Notes
- Target files: `supabase/migrations/20260602_fencer_stats.sql`, `tests/test_fencer_stats_schema.py`.
- Keep scope narrow; do not edit `.github/workflows/`.
- `fs_fencers` can contain duplicate rows per person, so stats key by `fs_fencer_identities(id)` where possible.
- Current repo code/tests still reference `fs_bouts.fencer_a`/`fencer_b`; Wiki-Brain audit notes mention later live-schema renames to `fencer_a_id`/`fencer_b_id`. This migration does not depend on either bout column shape.
- Red test run: `.venv/bin/python -m pytest tests/test_fencer_stats_schema.py -v` failed 5/5 because `20260602_fencer_stats.sql` did not exist.
- Green test run: `.venv/bin/python -m pytest tests/test_fencer_stats_schema.py -v` passed 5/5.
- Broader full-suite verification was intentionally not run because the working tree contains substantial unrelated WIP tests/scripts from other agents.
- Wiki-Brain write/log append was attempted but blocked by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable project root.

---

# Agent 26 — Athlete Stats API

## Final Review
- [x] Read lessons, current task state, API patterns, identity schema, and available stats tables.
- [x] Added red-first helper/router tests in `tests/test_api_fencers_stats.py`.
- [x] Added scoped public stats helper/router in `api/v1/fencer_stats.py`.
- [x] Verified focused and adjacent API tests pass.
- [x] Ran full suite and recorded unrelated failures.

## Notes
- `api/v1/fencer_stats.py` exposes `router` and `get_public_fencer_stats()` without editing shared router files.
- The helper validates UUID fencer IDs, `season`, `weapon`, `category`, and `season_limit`; identity members are capped at 25, stats rows at 250, and season rows at 25.
- Output is sanitized: raw rows, metadata, URLs, timestamps, and scraper/service fields are not passed through.
- Duplicate `fs_fencers` rows are grouped through `fs_fencer_identities`; counts are summed only for count-like fields, `win_pct` is recomputed, and unsafe streak aggregation returns nulls.
- `fs_fencer_stats` and `fs_fencer_season_stats` are optional dependency tables; if absent or empty, the helper returns predictable zero/null blocks for existing fencers.
- Red run: `.venv/bin/python -m pytest tests/test_api_fencers_stats.py -v` failed 4/4 before implementation because `api/v1/fencer_stats.py` was missing.
- Focused run: `.venv/bin/python -m pytest tests/test_api_fencers_stats.py -v` passed 4/4.
- Adjacent API run: `.venv/bin/python -m pytest tests/test_api.py tests/test_api_fencers_stats.py -v` passed 16/16.
- Compile run: `.venv/bin/python -m py_compile api/v1/fencer_stats.py tests/test_api_fencers_stats.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v --tb=short` failed 26 unrelated/in-progress tests and passed 1879; failures included missing `scrape_allstar_uhlmann`, missing `compute_trending_fencers`, existing `scrape_competition_details`, `scrape_ffsu`, `scrape_historical_olympedia`, and frontend contract failures.
- Wiki-Brain write/log append was attempted but blocked by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable project root.

---

# Agent 116 — Ranking Alerts Service

## Plan
- [x] Read project lessons/todo and inspect ranking trend, migration, run logger, and test patterns.
- [x] Write failing tests for migration shape, rank-change detection, dry-run delivery, contact validation, unsubscribe handling, duplicate suppression, and rate limiting.
- [x] Implement `supabase/migrations/20260602_ranking_alerts.sql`.
- [x] Implement `ranking_alerts.py` with provider abstraction, dry-run fallback, idempotency keys, sanitized delivery logs, and run logging.
- [x] Run focused verification and fix failures.
- [x] Run broader verification where safe and add final review notes with files changed, behavior, verification, and residual risks.

## Notes
- Keep scope to `ranking_alerts.py`, `supabase/migrations/20260602_ranking_alerts.sql`, `tests/test_ranking_alerts.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Alert source is existing `fs_rankings_trends`; no external site probe was needed.

## Final Review
- Files changed: `ranking_alerts.py`, `supabase/migrations/20260602_ranking_alerts.sql`, `tests/test_ranking_alerts.py`, `tasks/todo.md`.
- Behavior changed: added opt-in ranking alert subscription and delivery-log schema; added rank-change alert computation from `fs_rankings_trends`; added email/SMS provider abstraction with dry-run fallback, contact validation, hashed unsubscribe tokens, delivery idempotency keys, duplicate suppression, run logging, scraper state, sanitized error/contact logging, and per-run rate limits.
- Verification performed: red focused run failed 6/6 on missing module/migration; `.venv/bin/python -m pytest tests/test_ranking_alerts.py -v` passed 6/6; `.venv/bin/python -m py_compile ranking_alerts.py` passed; `.venv/bin/python -m pytest tests/test_ranking_alerts.py tests/test_rankings_trends.py -v` passed 12/12; `git diff --check -- ranking_alerts.py tests/test_ranking_alerts.py supabase/migrations/20260602_ranking_alerts.sql tasks/todo.md` passed; full `.venv/bin/python -m pytest tests/ -v` ran 1875 passed, 30 failed, 1 warning with failures outside Agent 116 scope.
- Remaining risks: full suite has unrelated existing/in-progress failures; CRG `detect_changes_tool` was unavailable due the platform usage-limit approval gate; live provider delivery was not exercised because provider credentials are intentionally optional and tests use dry-run/fake providers.

---

# Agent 104 — Fencer Injury History

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected adjacent news scraper, fencer identity schema, state, logger, rate limiter, and migration/test patterns.
- [x] Probed official/public source structure; local shell network probe was blocked by sandbox DNS and escalated retry was rejected by the usage-limit gate, so tests use realistic official FIE/British-source fixtures based on available public page structure.
- [x] Added red-first tests in `tests/test_scrape_injuries.py`.
- [x] Added `scrape_injuries.py`.
- [x] Added `supabase/migrations/20260602_injuries.sql`.
- [x] Ran focused and broader verification.
- [x] Final review recorded.

## Notes
- Storage is additive in `public.fs_fencer_injury_absences` and uses deterministic `source_key` upsert.
- Rows store identity/fencer row references when available, fencer name/country/FIE ID, event/date fields, status type, source-backed summary/excerpt, source URL, confidence, and metadata.
- Status labels are limited to stated public signals: `injury`, `illness`, `suspension`, `personal_absence`, and `unknown`.
- Parser avoids medical speculation by preserving concise public excerpts and setting `metadata.medical_speculation_avoided`.
- Ambiguous fencer-name matches are skipped and logged instead of guessed.
- Verification: red focused run failed 8/8 on missing module/migration; focused `.venv/bin/python -m pytest tests/test_scrape_injuries.py -v` passed 8/8 after implementation; `.venv/bin/python -m py_compile scrape_injuries.py` passed; full `.venv/bin/python -m pytest tests/ -v` failed with 56 unrelated failures and 1842 passed.
- Wiki-Brain write/log append was attempted but blocked by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable project root.

---

# Agent 14 Country Medal Geo View

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected result, tournament, medal table, geography, materialized-view, and SQL-test patterns.
- [x] Added red-first SQL text tests in `tests/test_country_medal_geo.py`.
- [x] Added `supabase/migrations/20260602_country_medal_geo.sql`.
- [x] Verified focused and related tests pass.
- [x] Attempted Wiki-Brain/session log.

## Notes
- `fs_country_medal_geo` is a materialized view grouped by country code, weapon, category, competition tier, season, and year.
- `fs_country_geo_codes` stores canonical alpha3/FIE/Olympic code mappings with latitude/longitude centroids; stateless codes keep null geo fields.
- The migration adds nullable `fs_results.country` if missing and falls back to `fs_results.nationality`, preserving unknown country tokens through a left join.
- Red test run: `.venv/bin/python -m pytest tests/test_country_medal_geo.py -v` failed because `20260602_country_medal_geo.sql` did not exist.
- Green focused run: `.venv/bin/python -m pytest tests/test_country_medal_geo.py -v` passed 6/6.
- Related run: `.venv/bin/python -m pytest tests/test_country_medal_geo.py tests/test_medal_tables.py tests/test_country_analytics.py tests/test_dashboard_queries.py -v` passed 18/18.
- Full run: `.venv/bin/python -m pytest tests/ -v` completed with this file's tests passing, but failed overall with 45 failures and 17 errors from unrelated in-progress agent areas.
- Wiki-Brain write/log append was attempted but blocked by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable project root.

---

# Agent 84 H2H Graph Computation

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected H2H, bouts, identity, migration, and compute script patterns.
- [x] Added red-first graph and migration tests in `tests/test_h2h_graph.py`.
- [x] Added `compute_h2h_graph.py`.
- [x] Added `supabase/migrations/20260602_h2h_graph.sql`.
- [x] Verified focused tests pass.
- [x] Ran full `tests/` suite and recorded unrelated failures.

## Notes
- `fs_h2h_graph` stores bounded adjacency rows keyed by `fencer_key, weapon`; `fencer_key` is `fs_fencer_identities.id` when available, otherwise the raw fencer row ID.
- Graph construction dedupes physical fencers through `fs_fencer_identities.fs_fencer_row_ids`, skips duplicate bout IDs/source keys, skips missing/self/incomplete bouts, and computes degree/weighted centrality per weapon graph.
- Red test run: `.venv/bin/python -m pytest tests/test_h2h_graph.py -v` failed 5/5 because `compute_h2h_graph.py` and `20260602_h2h_graph.sql` did not exist.
- Green test run: `.venv/bin/python -m pytest tests/test_h2h_graph.py -v` passed 5/5.
- Full test run: `.venv/bin/python -m pytest tests/ -v` failed with unrelated current-suite failures: 1809 passed, 59 failed, 17 errors.

---

# Agent 114 — Tournament Results PDF Generator

## Plan
- [x] Read relevant lessons, current task state, dependency list, and tournament/result/bout schema patterns.
- [x] Write failing tests for deterministic payload assembly, PDF smoke/text extraction, and missing tournament errors.
- [x] Implement scoped `generate_tournament_pdf.py` with UUID validation, Supabase reads, stable ordering, deterministic PDF rendering, and safe output path handling.
- [x] Add CLI usage docs in `docs/pdf_export.md`.
- [x] Run focused and full pytest verification; fix failures where in scope.
- [x] Update task memory and final review; external Wiki-Brain write was attempted but blocked by approval usage-limit gate.

## Notes
- Target files: `generate_tournament_pdf.py`, `tests/test_generate_tournament_pdf.py`, `docs/pdf_export.md`.
- No text-capable PDF generation package is present in `requirements.txt` or the local venv. A small deterministic text-PDF writer avoids adding dependencies.
- `pdfplumber` is present and verifies generated PDF text in tests.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Red test run: `.venv/bin/python -m pytest tests/test_generate_tournament_pdf.py -v` failed 7/7 because `generate_tournament_pdf.py` did not exist.
- Focused verification: `.venv/bin/python -m pytest tests/test_generate_tournament_pdf.py -v` passed 7/7.
- Compile check: `.venv/bin/python -m py_compile generate_tournament_pdf.py tests/test_generate_tournament_pdf.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` passed all PDF tests but failed overall with unrelated current-suite failures: 1908 passed, 7 failed, 1 warning. Failures were in `tests/test_compute_fencer_stats.py` and `tests/test_scrape_allstar_uhlmann.py`.
- Wiki-Brain write/log append was attempted and rejected by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace.
- Final review: PDF generator, tests, and docs were added; remaining verification risk is limited to unrelated full-suite failures outside Agent 114 scope.

---

# Agent 45 — Greece Federation Scraper

## Final Review
- [x] Read lessons/current task state and existing federation scraper patterns.
- [x] Probed `fencing.org.gr`; local shell DNS failed and escalation was rejected, while public web evidence points to Ophardt index `https://fencing.ophardt.online/en/search/rankings/151`.
- [x] Wrote red-first tests for parser rows, empty/no-data pages, malformed/DNS/DQ/summary rows, Greek headers/native names, dynamic ranking links, fetch failures, blocked/login/JS-only pages, and 12-combo main iteration.
- [x] Implemented `scrape_fed_gre.py` with dynamic Ophardt discovery, Greek-aware HTML parsing, run logging, scraper state, and all 12 standard combos.
- [x] Verified focused tests and compile check.

## Notes
- Files changed: `scrape_fed_gre.py`, `tests/test_fed_gre.py`, `tasks/todo.md`.
- Verification: red `tests/test_fed_gre.py -v` failed first with missing module; `.venv/bin/python -m pytest tests/test_fed_gre.py -v` passed 13/13; `.venv/bin/python -m py_compile scrape_fed_gre.py` passed.
- Remaining risk: live local scraper probe could not confirm current public combo coverage because external DNS was blocked and escalation was rejected; scraper discovers season-specific Ophardt IDs dynamically at runtime.
- Wiki-Brain update was attempted after implementation but blocked by the approval usage-limit gate for writes outside the workspace.

# Agent 39 — Chinese Taipei Federation Scraper

## Plan
- [x] Read project lessons, current task state, graph context, and federation scraper patterns.
- [x] Probe `fencing.org.tw` public ranking pages and current workbook exposure.
- [x] Write focused parser/fetch tests with realistic Traditional Chinese fixtures.
- [x] Implement `scrape_fed_tpe.py` using public workbook discovery, `fed_rankings_common`, run logging, and state tracking.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: writing `/Users/plernghomhual/Documents/Brain` was rejected by the environment approval/usage gate.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Keep scope to `scrape_fed_tpe.py`, `tests/test_fed_tpe.py`, and task/wiki memory. Do not edit `.github/workflows/`.
- Browser/search probe reached `https://www.fencing.org.tw/` and confirmed public homepage ranking links to `x.webdo.cc` XLSX workbooks.
- Current public homepage evidence exposes `青年組排名(115-1)(公告版).xlsx`, `青少年組排名(115-1)(公告版).xlsx`, and `少年組排名(115-1)(公告版).xlsx`; no current senior full-ranking workbook was visible.
- Local shell live probe was blocked by sandbox DNS; escalation for read-only network probe was rejected by the approval usage gate.

## Final Review
- Files changed: `scrape_fed_tpe.py`, `tests/test_fed_tpe.py`, `tasks/todo.md`.
- Behavior changed: added Chinese Taipei federation scraper with dynamic public XLSX discovery, Junior workbook combo extraction, Traditional Chinese parser support, graceful missing/blocked/login/JS/404 handling, run logging, and state metadata.
- Verification: red focused test run first failed on missing module; focused `tests/test_fed_tpe.py -v` now passes 12/12; `py_compile scrape_fed_tpe.py tests/test_fed_tpe.py` passes.
- Remaining risk: current public evidence supports Junior Foil/Epee/Sabre Men/Women only; Senior combos are attempted and logged as no scrapeable public ranking source until a current senior workbook appears.

---

# Agent 67 — IWAS World Games and satellite wheelchair events

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing IWAS, Paralympic, run logger, state, and fencer matching patterns.
- [x] Probe IWAS/World Para Fencing, Paralympic, and World Abilitysport public URL structures.
- [ ] Write failing tests for IWAS/wheelchair parsing, no-public-data stubs, and explicit fencer matching.
- [ ] Implement scoped `scrape_iwas_games.py` behavior with logging, rate limiting, source metadata, and no orphan result inserts.
- [ ] Run focused verification and fix failures.
- [x] Update final review; Wiki-Brain/session log write blocked by approval gate.

## Notes
- Keep code changes scoped to `scrape_iwas_games.py`, `tests/test_scrape_iwas_games.py`, task memory, and Wiki-Brain.
- Existing `scrape_iwas.py` remains the ranking scraper; this task targets public games/satellite result evidence and stubs.
- Live shell probe was blocked by sandbox DNS and escalation usage limits; browser-accessible public pages provided current URL structure evidence.

---

# Agent 95 Club Enrichment

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing club/ranking/Wikidata enrichment patterns.
- [x] Add failing tests for migration shape, official page parsing, Wikidata claims, conservative normalization, and ambiguous source stubs.
- [x] Implement `supabase/migrations/20260602_club_enrichment.sql`.
- [x] Implement `enrich_clubs.py` with public-source enrichment, rate limiting, state, logging, and safe stubs.
- [x] Run `pytest tests/test_enrich_clubs.py -v` and fix failures.
- [x] Attempt Wiki-Brain/session log update and write final review.

## Notes
- Keep changes scoped to `enrich_clubs.py`, `supabase/migrations/20260602_club_enrichment.sql`, `tests/test_enrich_clubs.py`, and this tracking section.
- Do not edit `.github/workflows/`.
- Existing lessons apply: fencer matching is best-effort and club normalization must not merge across countries on name alone.

## Final Review
- Files changed: `enrich_clubs.py`, `supabase/migrations/20260602_club_enrichment.sql`, `tests/test_enrich_clubs.py`, `tasks/todo.md`.
- Behavior changed: club enrichment candidates are collected from federation rankings/results, fencers, club rankings, and existing club rows; rows upsert into `fs_club_enrichment` on `(normalized_club_name,country)`.
- Public sources: Wikidata/Wikipedia URLs, optional official club pages, and federation/source URLs from existing row metadata. Private forums/reviews are not used.
- Safety: same normalized club names remain separate by country; ambiguous Wikidata club matches write explicit stubs instead of merging; notable alumni come from Wikidata P54 claims and link to existing fencer IDs when available.
- Verification: red run failed 5/5 before implementation; green run passed 5/5. Adjacent tests passed 18/18. `py_compile enrich_clubs.py` passed.
- Remaining risk: live Wikidata probe was blocked by sandbox DNS and the escalated retry was rejected by the environment usage-limit gate; parser behavior is covered by realistic fixture bindings and existing repo Wikidata patterns.

---

# Agent 155 — Training Facilities Directory

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect training camps, club, geocoding, run logger, state, and migration patterns.
- [x] Probe public facility directory sources and record viable structures.
- [x] Write failing tests for directory parsing, address normalization/dedupe, no-geocoder fallback, PII filtering, pagination, and migration DDL.
- [x] Implement `scrape_training_facilities.py` and `fs_training_facilities` migration.
- [x] Run focused and relevant full verification; fix failures.
- [x] Update final review; Wiki-Brain/session log write was blocked by platform usage-limit gate.

## Notes
- Keep production code scope to `scrape_training_facilities.py`, `supabase/migrations/20260602_training_facilities.sql`, and `tests/test_training_facilities.py`.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Live probes for USA Fencing and British Fencing public directories failed in the sandbox with DNS resolution errors; escalated retry was rejected by the platform usage-limit gate. Parser tests use the existing USA Fencing JSON shape from `scrape_clubs.py` plus realistic public HTML/JSON-LD source stubs.

## Final Review
- Files changed: `scrape_training_facilities.py`, `supabase/migrations/20260602_training_facilities.sql`, `tests/test_training_facilities.py`, `tasks/todo.md`.
- Behavior changed: new training facilities scraper parses public federation API/HTML/JSON-LD facility directories, imports existing `fs_clubs` public rows when available, filters contact info to public business fields, normalizes/dedupes by name+address+country, optionally geocodes only when a provider or geocoder is configured, and upserts into `fs_training_facilities`.
- Verification: red focused run failed 6/6 before implementation; pagination red test failed before pagination patch; `tests/test_training_facilities.py tests/test_camps.py tests/test_venues.py -v` passed 27/27; `py_compile scrape_training_facilities.py` passed; fresh full `tests/ -v` ran 1915 passed, 3 unrelated failures, 1 warning.
- Remaining risk: live public directory fetches and required Wiki-Brain writes were blocked by environment DNS/approval limits, so source fixtures are realistic stubs rather than fresh captured pages; full suite still has unrelated failures in BigQuery export, fencing store dealer parsing, and Allstar/Uhlmann weapon normalization.

---

# Agent 139 YouTube Fencing Video Indexer

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect nearby YouTube/media scraper, migration, run logger, and state patterns.
- [x] Write failing tests for API parsing, classification, ambiguity logging, no-key dry run, dedupe/upsert, and migration DDL.
- [ ] Implement `scrape_youtube_videos.py`.
- [ ] Add `supabase/migrations/20260602_fencing_videos.sql`.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: Brain vault write is outside the workspace and the approval/usage gate rejected the write.

## Notes
- Target files: `scrape_youtube_videos.py`, `supabase/migrations/20260602_fencing_videos.sql`, `tests/test_youtube_videos.py`.
- Keep scope narrow; do not edit `.github/workflows/`.
- `YOUTUBE_API_KEY` must gate all YouTube Data API calls; missing key means dry-run/no external API call.

## Final Review
- Files changed: `scrape_youtube_videos.py`, `tests/test_youtube_videos.py`, `supabase/migrations/20260602_fencing_videos.sql`, `tasks/todo.md`.
- Behavior changed: added a YouTube Data API-gated fencing video indexer that builds fencer/tournament search queries, parses public search-result metadata, classifies likely match videos vs general content, conservatively matches fencers by unambiguous full names, logs ambiguous name matches, skips private/deleted placeholder titles, merges duplicate video context, and upserts by `video_id`.
- Verification performed: red focused tests first failed on missing module/migration; focused YouTube suite passed 9/9; `py_compile scrape_youtube_videos.py` passed; full `.venv/bin/python -m pytest tests/ -v` ran 1911 tests with 1905 passed and 6 unrelated failures in `tests/test_scrape_allstar_uhlmann.py` due `IndentationError` in `scrape_allstar_uhlmann.py:692`.
- Remaining risks: `YOUTUBE_API_KEY` was not set, so no live YouTube API probe was run; dry-run/no-key behavior is covered. CRG impact check, Wiki-Brain/session log write, and pycache cleanup were blocked by the usage-limit approval gate.

---

# Agent 140 Instagram Fencing Content Aggregator

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing social/news scraper patterns and social-agent prompts.
- [x] Add failing tests for no-key dry run, API fixture parsing, mention/fencer matching, and private/login-only skips.
- [x] Implement `scrape_instagram_fencing.py` with API-only provider access, dry-run fixtures, normalized metadata, run logging, and state updates.
- [x] Run focused and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.
- [ ] Update Wiki-Brain/session log. Blocked: Brain vault write rejected by approval usage gate.

## Notes
- Target files: `scrape_instagram_fencing.py`, `tests/test_instagram_fencing.py`.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Use existing `fs_articles` for public post metadata to avoid adding a new table outside the requested scope.
- No Instagram network call should occur unless approved API credentials are configured.

## Final Review
- Files changed: `scrape_instagram_fencing.py`, `tests/test_instagram_fencing.py`, `tasks/todo.md`.
- Behavior changed: added API-only Instagram Graph Business Discovery adapter with no-key fixture dry-run, public metadata normalization, mention/fencer matching, redacted caption snippets, private/login-only skips, `fs_articles` upsert by URL, run logging, and state updates for live runs.
- Verification: red focused test first failed on missing module; focused Instagram tests passed 5/5; related Instagram/news/social tests passed 19/19; `py_compile scrape_instagram_fencing.py tests/test_instagram_fencing.py` passed; no-key script run exited 0 with fixture dry-run and zero writes.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran 1816 passed, 60 failed, 17 errors, 8 warnings. The new Instagram tests passed; failures were in unrelated existing/in-progress areas.
- Remaining risk: no live Instagram Graph probe was possible without configured API credentials; graph impact analysis and Wiki-Brain/session-log writes were blocked by the usage-limit gate.

---

# Agent 56 — Dominican Republic Federation Scraper

## Plan
- [x] Read project lessons, current task state, and existing federation scraper patterns.
- [x] Probe `fedesgrimard.org`, `fedomes.org`, sitemap pages, common ranking paths, and likely API/assets.
- [x] Write failing parser/fetch tests for Dominican ranking behavior and blocked/stub cases.
- [x] Implement `scrape_fed_dom.py` with robust Spanish table parser and documented no-public-data fetch stub.
- [x] Run focused verification and fix failures.
- [x] Update task final review; Wiki-Brain/session log write blocked by approval usage-limit gate.

## Notes
- `https://fedesgrimard.org/` and `http://fedesgrimard.org/` do not resolve.
- FIE/public search points Dominican federation contact to `https://www.fedomes.org/`.
- `https://www.fedomes.org/`, `/ranking`, `/rankings`, `/resultados-y-ranking`, `/documentos`, sitemap pages, and common PDF/XLS asset guesses are public GET targets but expose generic Aruba Supersite HTML with no visible ranking table, forms, file links, or usable ranking API/XHR payload.
- Direct guesses for public ranking PDF/XLS/XLSX assets return 404.
- Current public combo coverage found: 0/12 Senior/Junior Foil/Epee/Sabre Men/Women.
- Keep code changes scoped to `scrape_fed_dom.py`, `tests/test_fed_dom.py`, task memory, and Wiki-Brain.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

## Final Review
- Files changed: `scrape_fed_dom.py`, `tests/test_fed_dom.py`, `tasks/todo.md`.
- Behavior changed: added a Dominican Republic federation rankings scraper with all 12 standard combos, robust Spanish HTML ranking parser, season normalization, run logging, state metadata, and a documented no-public-ranking stub for current `fedomes.org` probe evidence.
- Verification: red focused tests first failed on missing `scrape_fed_dom`; final `.venv/bin/python -m pytest tests/test_fed_dom.py -v` passed 12/12; `.venv/bin/python -m py_compile scrape_fed_dom.py tests/test_fed_dom.py` passed; no-credential `.venv/bin/python scrape_fed_dom.py` exited 0 after attempting all 12 combos and reporting `working_combos=0/12`.
- Remaining risks: no durable public Dominican ranking source was found; parser tests use realistic Spanish fixtures rather than captured live ranking rows because the public site exposes no table/file/API.

---

# Agent 81 — Prediction model for next Olympic/World medalists

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect relevant compute scripts, migrations, and test patterns.
- [x] Write failing tests for migration shape, feature calculation, deterministic ranking, missing data/inactive caveats, Supabase upsert flow, and backtest metrics.
- [x] Implement `compute_predictions.py` with deterministic transparent scoring, optional metric fallbacks, run logging, state updates, and sports-analytics caveats.
- [x] Add `supabase/migrations/20260602_predictions.sql` defining prediction and validation storage without destructive data changes.
- [x] Run focused verification and fix failures.
- [x] Record final review in task memory; Wiki-Brain/session log write was blocked by the host approval usage-limit gate.

## Notes
- Keep code changes scoped to `compute_predictions.py`, `tests/test_predictions.py`, `supabase/migrations/20260602_predictions.sql`, task memory, and Wiki-Brain.
- Use existing rankings/results/tournament/metric tables; optional Elo/legacy tables must be read conservatively and skipped if absent.
- Label outputs as sports analytics, not betting advice or guarantees.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

Final review:
- Files changed by Agent 81: `compute_predictions.py`, `tests/test_predictions.py`, `supabase/migrations/20260602_predictions.sql`, `tasks/todo.md`.
- Behavior changed: adds transparent deterministic Olympic/World prediction rows and backtest validation rows from existing rankings/results/calendar/metric inputs.
- Verification: red prediction tests failed on missing module/migration; focused `.venv/bin/python -m pytest tests/test_predictions.py -v` passed 6/6; `.venv/bin/python -m py_compile compute_predictions.py` passed; full `.venv/bin/python -m pytest tests/ -v` collected 1911 tests with 1902 passed, 9 unrelated failures, and 1 warning. Prediction tests passed in the full run.
- Remaining risks: Wiki-Brain page/index/log update was attempted but rejected by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable sandbox. Full-suite failures are outside Agent 81 scope: `tests/test_fencing_stores.py`, `tests/test_scrape_allstar_uhlmann.py`, `tests/test_scrape_competition_details.py`, and `tests/test_training_facilities.py`.

---

# Agent 85 — Competition Difficulty Trends

## Plan
- [x] Read relevant lessons, current task state, and adjacent strength/ranking trend patterns.
- [x] Write failing tests for moving averages, normalized seasons, sparse data, missing ranking/strength rows, and tier grouping.
- [x] Implement `compute_difficulty_trend.py` using explicit strength/tier/type fields and deterministic skipped counts.
- [x] Run `./.venv/bin/python -m pytest tests/test_difficulty_trend.py -v` and fix failures.
- [x] Final review recorded; Wiki-Brain/session log write blocked by approval usage-limit gate.

## Notes
- Target files are new in this checkout: `compute_difficulty_trend.py` and `tests/test_difficulty_trend.py`.
- Keep scope to target module/test and required task/wiki memory. Do not edit `.github/workflows/`.
- Use strict tier/type fields for trend grouping; do not infer competition tier from event names.

## Final Review
- Files changed: `compute_difficulty_trend.py`, `tests/test_difficulty_trend.py`, `tasks/todo.md`.
- Behavior changed: added deterministic competition difficulty trend aggregation from `fs_tournaments`, `fs_competition_strength`, `fs_rankings_history`, and `fs_results`, with normalized seasons, explicit tier/type grouping, sparse moving windows, sample counts, skipped counts, and confidence levels.
- Verification: red focused tests first failed on missing `compute_difficulty_trend`; final focused test passed 5/5; adjacent strength/ranking/difficulty tests passed 14/14; `py_compile` and `git diff --check` passed.
- Remaining risks: no database output migration/table was added because task scope named only the compute module and tests; generated bytecode cleanup and Wiki-Brain/session log writes were blocked by the approval usage-limit gate.

# Agent 120 — Data marketplace / API monetization portal

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing export API, API key migration, and RLS/public-view patterns.
- [x] Write failing tests for Stripe webhook signatures/idempotency, entitlement access, usage counters, and no-secret logging.
- [x] Implement `marketplace_api.py` with test-mode-safe Stripe helpers, webhook handling, API-key entitlement checks, scoped public-data routes, and usage accounting.
- [x] Add `supabase/migrations/20260602_marketplace.sql` for plans, customers, API keys, subscriptions, usage counters, webhook event idempotency, and private RLS.
- [x] Add `docs/marketplace.md` covering env vars, local Stripe webhook testing, and failure handling.
- [x] Run focused and full verification; fix failures.
- [x] Record final review; Wiki-Brain/session log write was blocked by the external approval gate.

## Notes
- Scope is limited to `marketplace_api.py`, `supabase/migrations/20260602_marketplace.sql`, `tests/test_marketplace_api.py`, `docs/marketplace.md`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Stripe calls must remain test-mode only unless live mode is explicitly enabled.
- Red test run: `.venv/bin/python -m pytest tests/test_marketplace_api.py -v` failed 8/8 on missing module/migration before implementation.
- Focused verification: `py_compile marketplace_api.py` passed; `.venv/bin/python -m pytest tests/test_marketplace_api.py tests/test_api.py tests/test_rls_policy_sql.py -v` passed 26/26 with one existing Starlette/httpx warning.

---

# Agent 154 — Equipment Durability Tracker

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect existing equipment mention/review schema and compute/upsert patterns.
- [x] Write failing tests for dated evidence aggregation, confidence, insufficient data, normalization, migration DDL, and Supabase upsert flow.
- [x] Implement `compute_equipment_durability.py` as a public-evidence aggregation layer over existing equipment/review rows.
- [x] Add `supabase/migrations/20260602_equipment_durability.sql`.
- [x] Run focused and relevant full verification; fix failures.
- [x] Attempt Wiki-Brain/session log update and record final review.

## Notes
- Keep code changes scoped to `compute_equipment_durability.py`, `supabase/migrations/20260602_equipment_durability.sql`, `tests/test_equipment_durability.py`, task memory, and Wiki-Brain.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Durability rows must be labeled as estimates from public dated evidence, not private replacement behavior.
- If fencer-level dated evidence is weak, emit aggregate brand/equipment-type low-confidence summaries only.

## Final Review
- Files changed for this task: `compute_equipment_durability.py`, `supabase/migrations/20260602_equipment_durability.sql`, `tests/test_equipment_durability.py`, `tasks/todo.md`.
- Behavior changed: adds `fs_equipment_durability` schema and a compute script that derives durability estimates only from dated public equipment/review evidence, emits aggregate low/insufficient-confidence rows when fencer evidence is weak, records evidence links, and upserts by deterministic `id`.
- Verification: red focused durability tests failed before implementation; `.venv/bin/python -m pytest tests/test_equipment_durability.py -v` passed 6/6; `.venv/bin/python -m pytest tests/test_equipment.py tests/test_equipment_reviews.py tests/test_equipment_durability.py -v` passed 21/21; `.venv/bin/python -m py_compile compute_equipment_durability.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` passed 1879 tests and failed 26 unrelated tests in existing/in-progress areas.
- Wiki-Brain update: attempted to write `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace Equipment Durability.md` and append `/Users/plernghomhual/Documents/Brain/log.md`; blocked by the escalation usage-limit gate because the vault is outside the writable project root.
- Remaining risk: real production confidence depends on how often upstream equipment rows include explicit dates; sparse data intentionally produces aggregate low/insufficient-confidence summaries instead of private behavior claims.

---

# Agent 75 — PAFC Circuit Events

## Plan
- [x] Read project lessons and current task state.
- [x] Check worktree state and graph/memory context.
- [x] Inspect neighboring result scrapers and shared matching/country patterns.
- [x] Probe PAFC/FIE/host public result sources and record blocked or missing source evidence.
- [x] Write failing tests for bilingual HTML/PDF/FIE-source parsing, country normalization, blocked sources, and conservative fencer matching.
- [x] Implement `scrape_panam_conf.py`.
- [x] Run focused PAFC verification and fix failures.
- [x] Update task final review; Wiki-Brain/session log write blocked by approval usage-limit gate.

## Notes
- Target files do not exist yet: `scrape_panam_conf.py`, `tests/test_scrape_panam_conf.py`.
- Keep scope to PAFC scraper/test plus task/wiki memory. Do not edit `.github/workflows/`.
- Prior wiki context says older PAFC domains (`www.panam-fencing.org`, `panam-fencing.org`, `panam-fencing.com`, `panamericanfencing.org`) were DNS-offline/defunct.
- Current public evidence found via web/source references: 2024/2025 Pan American Senior Championship references point to FIE result pages; the Puerto Rico host federation public page links the 2025 Spanish invitation PDF; that PDF lists the FIE/Ophardt widget URL `https://fencing.ophardt.online/en/widget/event/31914`.
- Local probe script against `https://fie.org/competitions` failed on sandbox DNS (`nodename nor servname provided, or not known`). Escalated retry was blocked by the Codex usage-limit approval gate, so live local probing could not continue from this shell.
- Red test run: `tests/test_scrape_panam_conf.py -v` failed 7/7 before `scrape_panam_conf.py` existed; second red cycle failed on Haiti code and identity fallback.
- Verification: `.venv/bin/python -m pytest tests/test_scrape_panam_conf.py -v` passed 8/8; `.venv/bin/python -m py_compile scrape_panam_conf.py tests/test_scrape_panam_conf.py` passed.
- Cleanup note: removing PAFC-specific generated `__pycache__` files was blocked by the usage-limit approval gate, so no deletion workaround was attempted.

## Final review
- Files changed: `scrape_panam_conf.py`, `tests/test_scrape_panam_conf.py`, `tasks/todo.md`.
- Behavior changed: added PAFC/CPE scraper with bilingual HTML/PDF/FIE inline JSON parsing, PAFC country-code aliases, external live-link discovery, deterministic blocked source stubs, run logging/state, tournament upsert, and conservative result insertion that skips/logs unmatched individual fencers instead of creating null-fencer orphans.
- Verification performed: focused PAFC pytest passed 8/8; py_compile passed.
- Remaining risks: live local source probing and cache cleanup were blocked by the approval usage-limit gate; Ophardt widget pages may be JS-heavy and are skipped when they do not expose static HTML/PDF result rows.

---

# Agent 34 Chile Federation Scraper

## Plan
- [x] Read project lessons, current task state, and existing federation scraper patterns.
- [x] Probe FECHE/Chile ranking URLs and record public combo coverage.
- [x] Write failing parser and fetch tests with realistic Chile PDF/Spanish fixtures.
- [x] Implement `scrape_fed_chi.py` using public FECHE ranking PDFs, `fed_rankings_common`, `ScraperRunLogger`, and scraper state.
- [x] Run focused verification and fix failures.
- [x] Record final review; Wiki-Brain/session log write was blocked by the external approval gate.

## Notes
- Keep scope to `scrape_fed_chi.py`, `tests/test_fed_chi.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Requested probe host was `feche.cl`; public search and page probes identify the current FECHE site as `https://esgrima.cl`.
- `GET https://esgrima.cl/espada/`, `/florete/`, and `/sable/` expose national ranking PDF links for `JUVENIL` and `TODO COMPETIDOR` under women and men sections.
- Public PDF URL pattern is `https://esgrima.cl/wp-content/uploads/2025/04/{ARMA}-{GENERO}-{CATEGORIA}.pdf`.
- Response format is `application/pdf`; browser probe confirmed all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public.
- Local Python live probe was blocked by sandbox DNS, and the escalated rerun was blocked by the usage-limit approval gate.

## Final Review
- Files changed: `scrape_fed_chi.py`, `tests/test_fed_chi.py`, `tasks/todo.md`.
- Behavior changed: Chile federation rankings now dynamically discover public national ranking PDFs from `https://esgrima.cl/{espada,florete,sable}/`, parse Spanish PDF text and fallback HTML tables, attempt all 12 required Senior/Junior weapon/gender combos, write via `fed_rankings_common.write_rankings()`, and record run state/log metadata.
- Verification performed: red focused test run failed on missing `scrape_fed_chi`; `py_compile scrape_fed_chi.py tests/test_fed_chi.py` passed; `.venv/bin/python -m pytest tests/test_fed_chi.py -v` passed 16/16.
- Remaining risks: local live Python probe could not complete because sandbox DNS blocked `esgrima.cl` and the escalated retry was rejected by the usage-limit approval gate; implementation uses browser/web probe evidence for public URL structure and realistic captured PDF text fixtures. Wiki-Brain write/session-log append to `/Users/plernghomhual/Documents/Brain` was also blocked by the approval usage-limit gate because that path is outside the writable repo.

---

# Agent 125 - Weekly Trending Fencers

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect analytics, identity, rankings, results, migration, and test patterns.
- [x] Write failing tests for scoring, missing social data, tie-breaking, migration DDL, and idempotent upserts.
- [x] Implement `compute_trending_fencers.py` with deterministic scoring, identity grouping, weekly windows, run logging, state, and upsert.
- [x] Add `supabase/migrations/20260602_trending_fencers.sql`.
- [x] Run focused and full verification.
- [x] Final review recorded; Wiki-Brain/session log blocked by usage-limit approval gate.

## Notes
- Keep scope to `compute_trending_fencers.py`, `tests/test_trending_fencers.py`, `supabase/migrations/20260602_trending_fencers.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Social data is optional. If no social input table is available, compute performance-only scores with `social_score = 0`.
- Focused red test run failed on missing module/migration; post-implementation focused run passed 5/5.
- Adjacent analytics verification passed 20/20 for trending, rankings trends, form tracker, and social leaderboard.
- Full `tests/ -v` ran 1915 passed, 2 unrelated failed, 1 warning. Failures were `tests/test_export_bigquery.py::test_resume_continues_from_saved_offset_and_chunk_number` and `tests/test_scrape_allstar_uhlmann.py::test_normalizes_german_english_categories_weapons_and_eur_prices`, both outside this task's allowed edit scope.
- Wiki-Brain page/index/log write to `/Users/plernghomhual/Documents/Brain` was attempted and blocked by the platform approval usage-limit gate because the path is outside the writable workspace.

---

# Agent 113 — H2H Comparison Page

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect H2H API/table shape and frontend routing state.
- [ ] Write failing H2H page/component tests for selection, stats, edge states, and API contract.
- [ ] Implement `frontend/pages/head-to-head.tsx` and `frontend/components/H2HComparison.tsx`.
- [ ] Run focused/frontend-available checks and full Python suite.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- This checkout currently has no existing `frontend/` tree or JS package/test runner, so the requested Next.js files are being added from scratch.
- H2H API route is `GET /h2h/{fencer_a}/{fencer_b}` and returns `{ fencer_a, fencer_b, data }`, where `data` contains canonical `fs_head_to_head` rows by weapon.
- Fencer search route is `GET /fencer/search?name=...` and returns paginated `fs_fencers` rows.
- Query params should use only public fencer IDs (`a`, `b`) for deep links.
- Do not edit `.github/workflows/`.

---

# Agent 35 — Turkey Federation Scraper

## Plan
- [x] Read project lessons, current task state, and federation ranking scraper patterns.
- [x] Probe Turkey federation ranking pages and record public source evidence.
- [ ] Write failing parser/fetch tests with realistic Turkish ranking fixtures.
- [ ] Implement `scrape_fed_tur.py` using public ranking PDFs, `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Requested host `trfencing.gov.tr` did not resolve in the sandboxed local probe; current public federation host found via live web probe is `https://www.eskrim.org.tr`.
- Public rankings page: `https://www.eskrim.org.tr/klasmanlar-20.html`.
- Request method: GET. Response formats: ranking index is HTML; ranking details are public PDF assets under `/resim/extra/Klasmanlar/...`.
- Public coverage on the current index: all 12 requested Senior/Junior Foil/Epee/Sabre Men/Women combos.
- Local escalated probe was rejected by the usage-limit approval gate, so implementation uses browser/web probe evidence and runtime dynamic link discovery.
- Do not edit `.github/workflows/`.

---

# Agent 103 — Fencer Handedness Data

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing FIE profile, Wikidata identity, migration, and test patterns.
- [x] Probe representative handedness sources or document probe blockers.
- [ ] Write failing parser, matching, dry-run, and migration tests.
- [ ] Implement `enrich_handedness.py` with explicit-source parsing, identity-first matching, dry run, rate limiting, run logging, and state.
- [ ] Add `supabase/migrations/20260602_handedness.sql`.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `enrich_handedness.py`, `supabase/migrations/20260602_handedness.sql`, `tests/test_enrich_handedness.py`, `tasks/todo.md`, and required Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Relevant lessons: match fencers conservatively; `fs_fencers` can contain duplicate rows per person.
- Probe script targets: FIE athlete profile `https://fie.org/athletes/42855`, Wikidata handedness property `P552`, Wikipedia infobox profile pages, and USA Fencing public federation bio pages.
- Non-escalated live probe failed sandbox DNS for FIE, Wikidata, Wikipedia, and USA Fencing. Required escalated retry was rejected by the approval usage-limit gate.
- Controlled web evidence showed FIE athlete pages expose `Hand L` and `Handedness Left`; Wikidata property `P552` represents handedness with left/right/ambidextrous values; Wikipedia fencer pages expose infobox `Hand` fields; USA Fencing public bios may expose athlete details but no reliable structured handedness field in the probed page.
- Parser must never infer handedness from media, image alt text, or arbitrary narrative mentions.

---

# Agent 7 — FIE Competition Detail Pages

## Plan
- [x] Read lessons and current task state.
- [x] Inspect `scrape_competition_details.py`, older `tests/test_competition_details.py`, FIE result URL discovery, and tournament update patterns.
- [x] Probe current public FIE detail pages and XHR/API assumptions.
- [x] Write failing parser, normalization, missing/malformed, and no-duplicate-update tests in `tests/test_scrape_competition_details.py`.
- [x] Implement scoped parser/update changes in `scrape_competition_details.py`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_competition_details.py`, `tests/test_scrape_competition_details.py`, task memory, and Wiki-Brain.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Local probe script could not resolve `fie.org` from the sandbox. Required escalated retry was blocked by the Codex usage-limit approval gate.
- Read-only web probe confirmed current public detail URLs still use `/competitions/{season}/{competition_url_id}`. Examples: `https://fie.org/competitions/2025/145`, `https://fie.org/competitions/2026/113`, `https://fie.org/competitions/2026/163`.
- Current detail pages expose rendered label/value fields such as weapon, gender, type, start/end day, location, country, `DT President/Event Manager` or `Supervisor`, plus `Live Results`, `Invitation`, and `Entries` links.
- Invitation PDFs are public and carry richer fields: host federation/organiser, venue/address, participation quota, entry fee, and competition formula.
- `supabase/migrations/20260602_tournament_detail_columns.sql` already adds `fs_tournaments.organizer`, `entry_deadline`, `format`, `quota`, `venue_details`, `registration_url`, `live_results_url`, and `detail_source`; scraper updates only existing `fs_tournaments` rows by `id` and still upserts `fs_competition_details` by `tournament_id`.

## Final Review
- Files changed: `scrape_competition_details.py`, `tests/test_scrape_competition_details.py`, `tasks/todo.md`.
- Behavior changed: FIE detail scraping now extracts organizer, defensive entry deadline, format/formula, quota, venue details, registration URL, live results URL, and raw snippets from rendered HTML, inline FIE JSON, and invitation/regulation text.
- Database behavior: existing `fs_competition_details` rows are still upserted by `tournament_id`; existing `fs_tournaments` rows are updated by `id` only when parsed detail fields are present. There is no `fs_tournaments.upsert` path.
- Verification: red focused run failed first with missing helper/parser/update behavior; `tests/test_scrape_competition_details.py tests/test_competition_details.py -v` passed 22/22; `py_compile scrape_competition_details.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed in `/tmp/fencespace-full-tests.XXXXXX.log` with 1908 passed, 7 unrelated failures in `tests/test_compute_fencer_stats.py` and `tests/test_scrape_allstar_uhlmann.py`.
- Remaining risks: local live Python probe could not reach `fie.org` because sandbox DNS failed and escalation was blocked by the approval usage-limit gate; fixtures are realistic and based on read-only web probe evidence, not a captured raw HTML/XHR dump.
- Wiki-Brain/session log update: attempted after verification, but writing `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace Competition Details Scraper.md` was rejected by the host approval usage-limit gate. No bypass attempted.

---

# Agent 1 Fencer Bio Columns

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect existing `fs_fencers` migrations and fencer profile update code.
- [x] Add failing migration SQL structure tests.
- [x] Add idempotent nullable `fs_fencers` bio/birth columns migration.
- [x] Run focused pytest verification and fix issues.
- [x] Update task tracker and record final review; Wiki-Brain/session log write was blocked by approval usage limits.

## Notes
- `20260601033334_wikipedia_bios.sql` already adds `birth_place text` and `bio_text text`, so the new migration remains idempotent and additive only.
- `scrape_athlete_profiles.py` already probes `birth_date` as a DOB column candidate, so adding nullable `birth_date date` is compatible with the current profile update path.
- Keep changes scoped to `supabase/migrations/20260602_fencer_bio_columns.sql`, `tests/test_bio_columns.py`, and task/wiki memory. Do not edit `.github/workflows/`.

## Final Review
- Files changed: `supabase/migrations/20260602_fencer_bio_columns.sql`, `tests/test_bio_columns.py`, `tasks/todo.md`.
- Behavior changed: `fs_fencers` gains nullable `bio`, `birth_date`, `birth_place`, and `bio_source` columns through `ADD COLUMN IF NOT EXISTS`.
- Verification: red focused test failed first because the migration file was missing; focused `pytest tests/test_bio_columns.py -v` then passed 4/4; `git diff --check` passed for touched paths.
- Remaining risks: migration is schema-only and does not backfill existing `bio_text` data into `bio`.

---

# Agent 52 — Latvia Federation Scraper (LVA)

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe Latvia federation URLs and record public ranking coverage.
- [x] Write failing Latvia parser/fetch/stub tests with realistic Latvian/FencingTime fixtures.
- [x] Implement `scrape_fed_lva.py` with all 12 standard combo attempts and graceful no-public-ranking handling.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_lva.py`, `tests/test_fed_lva.py`, `tasks/todo.md`, and required Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Prompt probe host `pauksmes.lv` has no search presence and local DNS probe could not run outside the sandbox approval gate.
- Current official Latvia federation site is `https://paukosana.lv/`.
- Working public source: `GET https://paukosana.lv/sacensibu-rezultati/` returns WordPress HTML listing official competition-result Google Drive folders.
- WordPress API searches for `ranking` and `reitings` returned empty arrays.
- `https://paukosana.tv/results/LCH2021/index.htm` returns FencingTime competition live results, not season federation rankings.
- Public combo coverage: 0/12 durable national ranking pages found; scraper should attempt all 12 combos and log `No scrapeable rankings at {URL}` without crashing.

## Final Review
- Files changed: `scrape_fed_lva.py`, `tests/test_fed_lva.py`, `tasks/todo.md`.
- Behavior changed: Latvia federation scraper now attempts all 12 standard Senior/Junior Foil/Epee/Sabre Men/Women combos, logs probe URLs, skips unavailable public ranking combos cleanly, and includes a localized parser for future Latvian ranking tables with `Vieta`, `Vārds / Uzvārds`, `Klubs`, and `Punkti` headers.
- Verification: red `pytest tests/test_fed_lva.py -v` failed first because `scrape_fed_lva.py` was missing; focused `pytest tests/test_fed_lva.py -v` then passed 12/12; `py_compile scrape_fed_lva.py tests/test_fed_lva.py` passed.
- Remaining risks: no durable public Latvia national ranking table was found. Local Python DNS probe was sandbox-blocked and escalated retry was unavailable due the approval usage gate; web probes confirmed only official competition-result folders and FencingTime competition results.

---

# Agent 101 — Competition Weather Data

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect existing compute/enrichment, migration, and test patterns.
- [x] Probe public weather source availability and record blockage evidence.
- [ ] Write failing tests for migration shape, indoor defaults, API normalization, cache behavior, missing keys, and missing venues.
- [ ] Implement `enrich_weather.py` with cautious indoor/outdoor classification, Open-Meteo normalization, cache/state handling, dry-run behavior, Supabase upsert, and run logging.
- [ ] Add `supabase/migrations/20260602_weather.sql`.
- [ ] Run `pytest tests/test_enrich_weather.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep code scope to `enrich_weather.py`, `supabase/migrations/20260602_weather.sql`, and `tests/test_enrich_weather.py`; do not edit `.github/workflows/`.
- Fencing events default to indoor/unknown weather relevance. Do not imply weather affected results without explicit outdoor evidence.
- Non-escalated Open-Meteo probe failed DNS resolution in the sandbox. Required escalated retry was blocked by the approval usage-limit gate, so tests use realistic dry-run fixtures based on Open-Meteo geocoding/archive response shape.

---

# Agent 124 — Fencer Comparison Tool

## Plan
- [x] Read project lessons and current task state.
- [x] Confirm frontend app status and relevant analytics table shapes.
- [x] Write failing comparison normalization and component tests.
- [x] Implement `frontend/lib/fencerComparison.ts`.
- [x] Implement `frontend/components/FencerComparisonTool.tsx`.
- [x] Run focused/full verification and fix issues.
- [x] Update task final review; Wiki-Brain/session log write blocked by approval usage-limit gate.

## Notes
- Keep scope to `frontend/components/FencerComparisonTool.tsx`, `frontend/lib/fencerComparison.ts`, `frontend/tests/fencer-comparison-tool.test.tsx`, and task/wiki memory.
- A `frontend/` app/test runner appeared during concurrent work; this pass did not add URL/deep-link state or route wiring.
- Do not edit `.github/workflows/`.
- Red check: `node --test frontend/tests/fencer-comparison-tool.test.tsx` failed because raw Node cannot load `.tsx`.
- Focused frontend verification: `cd frontend && npm test -- tests/fencer-comparison-tool.test.tsx` passed 7/7.
- Target-only TypeScript verification passed for `components/FencerComparisonTool.tsx`, `lib/fencerComparison.ts`, and `tests/fencer-comparison-tool.test.tsx`.
- Full Python suite passed: `.venv/bin/python -m pytest tests/ -v` passed 1922/1922 with one Starlette/httpx warning.
- Full frontend suite is red outside Agent 124 scope: `npm test` failed in existing `athlete-quiz`, `h2h-page`, `routes`, `country-medal-heatmap`, and `federation-overview` tests.
- Wiki-Brain/log write was attempted and rejected by the account usage-limit approval gate; no workaround attempted.

## Final Review
- Files changed: `frontend/components/FencerComparisonTool.tsx`, `frontend/lib/fencerComparison.ts`, `frontend/tests/fencer-comparison-tool.test.tsx`, `tasks/todo.md`.
- Behavior changed: added a reusable fencer comparison normalizer and component for typed fencer stats or ID-loaded profiles, with side-by-side career, medals, rankings, Elo/performance, H2H, weapons, and recent-form rows.
- Missing analytics now render placeholders (`No data`, `No bouts`, `No recent results`) instead of throwing.
- API reads use an injectable loader or credential-free public fetch with `credentials: "omit"`; no service credentials are referenced.
- Remaining risks: full frontend suite has unrelated existing failures; no route/deep-link state was added because no comparison route was in the requested scope.
- Wiki-Brain update remains blocked by out-of-workspace write approval limits.

---

# Agent 30 — Public Fencer View

## Plan
- [x] Read lessons and current task state.
- [x] Inspect existing `v_fencer_public`, RLS/public-view conventions, identity grouping, bio, rank, and stats migrations.
- [ ] Write failing SQL tests for required public columns, security-invoker grants, identity grouping, joins, excluded private/internal fields, and non-destructive SQL.
- [x] Add `supabase/migrations/20260602_v_fencer_public.sql`.
- [x] Run focused verification and fix issues.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep code scope to `supabase/migrations/20260602_v_fencer_public.sql`, `tests/test_v_fencer_public.py`, task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Existing `v_fencer_public` in `20260601_rls_policies.sql` is a minimal security-invoker projection over `fs_fencers`.
- Relevant lesson: group by `fs_fencer_identities` so duplicate `fs_fencers` rows do not become duplicate public athletes.
- Live Supabase schema lookup was blocked by the environment usage gate; local migrations/tests/code are the source of truth for this pass.

## Final Review
- Files changed: `supabase/migrations/20260602_v_fencer_public.sql`, `tests/test_v_fencer_public.py`, `tasks/todo.md`.
- Behavior changed: `public.v_fencer_public` now keeps the old replace-compatible column prefix, collapses duplicate `fs_fencers` rows to one public athlete per identity, and appends public bio, birth, media URL, ranking, and stats summaries.
- Verification: red focused test first failed 6/6 on missing migration; focused `tests/test_v_fencer_public.py -v` now passes 7/7; related RLS/stats/trajectory/view suite passes 24/24; `git diff --check` passes.
- Remaining risk: no local `psql`, `postgres`, or `sqlparse` was available, and live Supabase schema introspection was blocked by the usage gate, so SQL syntax/runtime verification is static rather than database-executed.
- Blocker: Wiki-Brain page/index/log write to `/Users/plernghomhual/Documents/Brain` was rejected by the approval usage gate. Do not retry indirectly without explicit user approval after the usage gate resets.

---

# Agent 99 — Fencer Sponsorship Deals

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing equipment scraper, run logger/state helpers, migration/test patterns, and product/equipment schema support.
- [x] Probe official athlete pages, federation bios, Wikidata, sponsor pages, and public announcement source shapes.
- [x] Write failing tests for migration shape, explicit sponsorship extraction, ambiguous mentions, brand normalization, expired deals, and upsert behavior.
- [x] Implement `scrape_sponsorships.py` with explicit-evidence parsing, source fetching, rate limiting, run logging, and state tracking.
- [x] Add `supabase/migrations/20260602_sponsorships.sql`.
- [x] Run focused verification and fix issues.
- [x] Update final review; Wiki-Brain/session log write blocked by approval gate.

## Notes
- Keep scope to `scrape_sponsorships.py`, `supabase/migrations/20260602_sponsorships.sql`, `tests/test_scrape_sponsorships.py`, task/wiki memory.
- Do not edit `.github/workflows/`.
- Local network probe script failed on sandbox DNS; escalated rerun was blocked by the approval usage gate. Web probes still confirmed current source shapes for KM Fencing partners, Red Bull athlete pages, Wikidata P859 sponsor, and FIE athlete profile pages.
- Sponsorship records must require explicit sponsor/partner/ambassador evidence and must not be inferred from equipment use or social-media appearance.

## Final Review
- Files changed: `scrape_sponsorships.py`, `supabase/migrations/20260602_sponsorships.sql`, `tests/test_scrape_sponsorships.py`, `tasks/todo.md`.
- Behavior changed: new sponsorship scraper stores only explicit sponsor/partner/ambassador evidence, normalizes brands/categories, links equipment brands via `linked_equipment_brand` and metadata, records Wikidata P859 sponsor claims, preserves public start/end dates for expired deals, and uses run logging/state plus rate limiting.
- Verification performed: red focused test first failed 8/8 on missing module/migration; focused `tests/test_scrape_sponsorships.py -v` passed 10/10; `py_compile scrape_sponsorships.py` passed; full `.venv/bin/python -m pytest tests/ -v --tb=short` finished 1870 passed, 29 unrelated failures, 1 warning.
- Remaining risks: shell network probe could not run because escalation was blocked by the approval usage gate; source discovery depends on sponsor/federation/announcement URLs present in fencer metadata plus FIE/Wikidata identifiers, not a general web search API; required Wiki-Brain page/log write to `/Users/plernghomhual/Documents/Brain` was also blocked by the approval usage gate.

---

# Agent 27 — Career Milestone Timeline API

## Plan
- [ ] Read project lessons/current state and relevant API, identity, career milestone context.
- [ ] Write failing tests for milestone ordering, filtering, dedupe, empty state, missing fencers, and invalid params.
- [ ] Implement scoped `api/v1/fencer_milestones.py` helper/router without editing shared API router files.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- `fs_career_milestones` migration/engine files are not present in this checkout yet. Per task instructions, implement the endpoint helper against the expected typed table shape and mocked fixtures; keep the backing table/view as an integration dependency.
- Do not edit `.github/workflows/`.
- Do not edit shared `api.py` or any shared router module for this agent.

---

# Agent 119 — BigQuery Export Pipeline

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect graph/search context plus existing Supabase pagination, state, and run logging patterns.
- [x] Write failing BigQuery export tests for schema mapping, dry-run/no credentials, chunking/progress, retry, and resume.
- [x] Implement `export_bigquery.py` with explicit schemas, payload builders, streaming Supabase pagination, dry-run JSONL/schema output, optional BigQuery loading, retries, run logging, and state updates.
- [x] Document Google env vars, dataset/table naming, dry-run behavior, and safe usage.
- [x] Run focused and full verification; fix any issues.
- [x] Record final review; Wiki-Brain/session log write was blocked by the external approval gate.

## Notes
- Keep scope to `export_bigquery.py`, `tests/test_export_bigquery.py`, `docs/bigquery_export.md`, `tasks/todo.md`, and required Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- `google-cloud-bigquery` is not in `requirements.txt`; importer must be lazy and dry-run/local export must work without it.
- Core `fs_*` table DDL is not checked in; schema mappings are explicit exporter contracts based on scraper select/upsert usage and analytics migrations.

## Final Review
- Files changed for this task: `export_bigquery.py`, `tests/test_export_bigquery.py`, `docs/bigquery_export.md`, `tasks/todo.md`.
- Behavior changed: BigQuery export now has explicit schema mappings for core and analytics tables, typed payload builders, local dry-run schema/JSONL output when BigQuery credentials are absent, optional lazy cloud loading, Supabase page/chunk streaming, retry, resume-safe chunk numbering, run logging, and `fs_scraper_state` progress.
- Verification: red focused tests failed first with missing `export_bigquery`; focused `tests/test_export_bigquery.py -v` now passes 6/6; `py_compile export_bigquery.py tests/test_export_bigquery.py` passes; `git diff --check` passes; full `.venv/bin/python -m pytest tests/ -v` passes 1922/1922 with one Starlette/httpx warning.
- Remaining risks: no real BigQuery write was run because Google credentials/SDK installation and cloud writes were intentionally not requested; original core `fs_*` DDL is not checked in, so exporter schemas are stable contracts based on current scraper/API usage and analytics migrations.
- Wiki-Brain page/log update, scoped graph change review, and generated `__pycache__` cleanup were blocked by the platform approval/usage gate; no workaround was attempted.

---

# Agent 41 Tunisia Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe Tunisia federation URLs and record public ranking coverage.
- [x] Write failing Tunisia parser/fetch tests with realistic public data fixtures.
- [x] Implement `scrape_fed_tun.py` with all 12 standard combo attempts.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_tun.py`, `tests/test_fed_tun.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- `fte-tunisie.com`, `http://fte-tunisie.com`, and `www.fte-tunisie.com` did not resolve during probe.
- Current public federation site is `https://escrimetunisie.org/`.
- Working public endpoint: `GET https://escrimetunisie.org/api/fie-athletes?weapon=<foil|epee|sabre>&gender=<M|F>&category=<senior|junior>` returns JSON.
- Public combo coverage from probe: 10/12 standard Senior/Junior weapon/gender combos have rows; Senior Women Foil and Junior Women Epee currently return `200 []`.

## Final Review
- Files changed: `scrape_fed_tun.py`, `tests/test_fed_tun.py`, `tasks/todo.md`.
- Behavior changed: Tunisia scraper now attempts all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos against the public FTE/FIE athlete JSON endpoint, parses JSON plus French/Arabic ranking tables, skips DNS/DQ/summary/malformed rows, writes via `fed_rankings_common.write_rankings()`, and records state/run counts.
- Verification: red focused run failed first with missing `scrape_fed_tun`, then season edge-case test failed on `2024-2025` before the current-season fix; final focused `tests/test_fed_tun.py -v` passed 11/11; `py_compile` passed; live no-write validation parsed 10/12 combos, 2 empty public combos, 0 fetch failures, 40 rows total, and season `2025-2026`.
- Skipped/blocked checks: full `.venv/bin/python -m pytest tests/ -v` exceeded the tool RPC timeout before returning a summary; read-only process inspection for the timed-out run was blocked by the approval usage-limit gate.
- Remaining risks: source is federation-published FIE ranking data rather than a separate national ranking table; no Supabase write was performed because credentials are not required for local verification; generated Python cache cleanup and Wiki-Brain writes were blocked by the approval usage-limit gate.

---

# Agent 104 — Fencer Injury History

## Plan
- [x] Read project lessons and current task state.
- [ ] Inspect adjacent news/scraper, state, logger, fencer identity, and migration patterns.
- [ ] Probe official federation/FIE/public news pages for stable injury/absence announcement structure.
- [ ] Write failing tests for migration shape, official parser extraction, non-injury absence labels, excerpt limits, conservative matching, ambiguous mentions, and blocked-source stubs.
- [ ] Implement `scrape_injuries.py` with cautious public-source extraction, matching, upsert, state, logging, rate limiting, and no-public-data stubs.
- [ ] Add `supabase/migrations/20260602_injuries.sql`.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_injuries.py`, `tests/test_scrape_injuries.py`, `supabase/migrations/20260602_injuries.sql`, `tasks/todo.md`, and required wiki/session memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Store only public source-backed injury/absence statements. Avoid medical speculation.

---

# Agent 88 - Junior Conversion Rates

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing identity, season, results, rankings, and analytics patterns.
- [x] Write failing tests for cohort detection, identity linking, conversion windows, country transfers, and sparse/missing data.
- [x] Implement `compute_junior_conversion.py` with canonical identity linking, conservative skips, conversion-rate rows, run logging, and state updates.
- [x] Add required conversion-rate table migration.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `compute_junior_conversion.py`, `tests/test_junior_conversion.py`, required migration, `tasks/todo.md`, and Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Reuse `fs_fencer_identities` for canonical identity grouping; raw `fs_fencers.id` is only a fallback when no identity table match exists.
- Red verification: focused suite first failed with `ModuleNotFoundError: No module named 'compute_junior_conversion'`; nullable result-dimension regression failed before fallback fix.
- Focused verification: `.venv/bin/python -m pytest tests/test_junior_conversion.py -v` passed 6/6.
- Syntax verification: `.venv/bin/python -m py_compile compute_junior_conversion.py` passed.
- Full-suite verification: `.venv/bin/python -m pytest tests/ -v` failed outside Agent 88 scope with 45 failed, 1808 passed, 17 errors, 8 warnings.
- Full-suite failures include unrelated areas: aggregate videos, fencer season stats, headshot dedupe, club/education/handedness enrichment, Slovak federation scraper, fencing stores, frontend contract, GraphQL API, nationality history, product/competition detail scrapers, FFSU, tournament brackets schema, and YouTube videos.
- Attempted Wiki-Brain page/index/log update for `[[FenceSpace Junior Conversion Rates]]`; write was rejected because the Brain vault is outside the repo writable root and the approval usage gate blocked the patch.

## Final Review
- Files changed: `compute_junior_conversion.py`, `tests/test_junior_conversion.py`, `supabase/migrations/20260602_junior_conversion.sql`, `tasks/todo.md`.
- Behavior changed: added junior-to-senior conversion computation grouped by junior country, weapon, gender/category, cohort season, and conversion window; rows use canonical identities, sample counts, senior appearance/ranking/medal/top placement rates, country-transfer counts, sparse-cohort metadata, run logging, and scraper state.
- Verification: focused junior conversion tests pass 6/6; `py_compile compute_junior_conversion.py` passes; full suite fails in unrelated in-progress areas listed above.
- Remaining risks: live Supabase execution was not run; conversion table migration must be applied before production compute runs; Wiki-Brain update is blocked by approval usage limits.

---

# Agent 38 — Thailand Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect British/shared federation scraper patterns and season utilities.
- [x] Probe `thaifencing.org` ranking source and record public combo coverage.
- [x] Write failing parser/fetch tests with realistic Thai ranking fixtures.
- [ ] Implement `scrape_fed_tha.py` with public PDF discovery/download, parser, run logging, and state tracking.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_tha.py`, `tests/test_fed_tha.py`, `tasks/todo.md`, and required wiki/session memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Web probe found `https://thaifencing.org/` public ranking section titled `Ranking 2024 – 2025 Season`.
- Public source lists 12 Google Drive PDF links for Senior and U20/Junior Foil/Epee/Sabre Men/Women.
- Request method is GET; homepage response is HTML; ranking files are Google Drive PDF views/downloads.
- Local shell network probe failed on sandbox DNS; escalation was blocked by the usage-limit approval gate, so implementation must keep runtime network failures non-fatal.

---

# Agent 135 — PBT Fencing Product Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect product schema prompts, scraper logging/state helpers, and equipment scraper patterns.
- [x] Probe PBT public catalog/detail pages; local network probe blocked by sandbox DNS and escalation usage-limit gate, but browser probe confirmed Magento category/detail structure.
- [ ] Write failing parser/upsert/scrape tests from probed Magento-style PBT fixtures.
- [ ] Implement `scrape_pbt_products.py` with listing/detail parsing, normalization, upserts, state, run logging, rate limiting, and blocked handling.
- [ ] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_pbt_products.py`, `tests/test_scrape_pbt_products.py`, `tasks/todo.md`, and Wiki-Brain memory unless the missing Agent 131 schema becomes a proven blocker.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Public browse probe found Magento-style category URLs under `https://shop.pbtfencing.com/webshop/...` and detail URLs such as `https://shop.pbtfencing.com/fencing-jacket-fie-800-n-primera-for-men25002?lang=euro_foreign`.
- Detail probe evidence includes product name, SKU `25002`, category links, size-chart rows, and euro prices; category pages show product-list rows, pagination, filter labels, and comma-decimal euro prices.

---

# Agent 10 — Fencer Season Stats

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect local season utilities and schema/analytics patterns for results, bouts, and fencer identities.
- [x] Write failing migration parser tests for `fs_fencer_season_stats`.
- [x] Add `supabase/migrations/20260602_fencer_season_stats.sql`.
- [x] Run targeted verification and fix issues.
- [x] Write final review and record Wiki-Brain/session-log blocker.

## Notes
- Keep scope to `supabase/migrations/20260602_fencer_season_stats.sql`, `tests/test_fencer_season_stats_schema.py`, `tasks/todo.md`, and Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Relevant lessons: normalized FIE season end-year integer; aggregate by `fs_fencer_identities` instead of duplicate `fs_fencers` rows.
- Supabase live schema introspection was blocked by the environment usage gate, so local migrations/tests/code are the source of truth for this pass.

## Final Review
- Files changed: `supabase/migrations/20260602_fencer_season_stats.sql`, `tests/test_fencer_season_stats_schema.py`, `tasks/todo.md`.
- Behavior changed: added an identity-scoped `fs_fencer_season_stats` table keyed by `(fencer_identity_id, season, weapon, gender, category)` with integer FIE end-year seasons, placement counts, medal counts, bout/touch aggregates, generated `touches` and `win_pct`, optional canonical `fencer_id`, RLS enablement, and fencer-detail/leaderboard indexes.
- Verification: red focused run failed 6/6 before migration because the SQL file was missing; final `.venv/bin/python -m pytest tests/test_fencer_season_stats_schema.py -v` passed 6/6; `git diff --check` passed.
- Remaining risks: live Supabase schema introspection and required Wiki-Brain/session-log writes were blocked by the approval usage gate; full-suite testing was skipped because the worktree contains many unrelated active/untracked agent files that would make full-suite results low-signal.

---

# Agent 66 — British Youth Fencing Results

## Plan
- [x] Read project lessons, current task state, and nearby scraper/test patterns.
- [x] Probe public British Youth Championships/British Fencing result sources and record blocked/non-public paths.
- [x] Write failing parser/upsert tests for public FTL HTML, PDF text, minor-data restraint, unmatched logging, and missing-data skips.
- [x] Implement `scrape_british_youth.py` with parser normalization, best-effort fencer matching, run logging, rate limiting, and scraper state.
- [x] Run `./.venv/bin/python -m pytest tests/test_scrape_british_youth.py -v` and fix failures.
- [x] Update final review.
- [ ] Wiki-Brain page/index/log update blocked by outside-workspace write approval usage-limit gate.

## Notes
- Keep code scope to `scrape_british_youth.py`, `tests/test_scrape_british_youth.py`, `tasks/todo.md`, and Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Public-source probe: British Fencing 2024 BYC report links to public Fencing Time Live results; 2026 BYC result link redirects to login and is treated as non-public/blocked. British Fencing BYC event pages document U12/U14/U16/U18 groups and 24 events. Engarde archives expose older BYC event lists for 2017-2019.
- Local live probe script failed under sandbox DNS. Required escalated retry was blocked by the approval usage-limit gate, so implementation uses web-probed source evidence plus realistic fixtures.

## Final Review
- Files changed: `scrape_british_youth.py`, `tests/test_scrape_british_youth.py`, `tasks/todo.md`.
- Behavior changed: added British youth result parsing for public Fencing Time Live HTML schedules/results, British Fencing PDF-extracted text, and Engarde-style HTML tables; normalizes weapon/gender/U12-U18 labels, UK regions, clubs, ranks, medals, points, dates, seasons, and source URLs.
- Behavior changed: writes tournaments/results through Supabase with `source_id` upserts, best-effort name+GBR fencer matching, unmatched-row logging, nullable unmatched `fencer_id`, run logging, scraper state, rate limiting, and explicit blocked-source stubs for login-only pages.
- Minor-data restraint: parsers ignore profile URLs, licence fields, and DOB/birth-date cells; result metadata records only competition evidence such as club, region, points, match status, and source.
- Verification: red focused run first failed 6/6 on missing `scrape_british_youth`; added login-nav regression failed before the detector fix; focused `./.venv/bin/python -m pytest tests/test_scrape_british_youth.py -v` now passes 7/7; `./.venv/bin/python -m py_compile scrape_british_youth.py tests/test_scrape_british_youth.py` passes.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` completed with 67 unrelated failures and 1778 passed; no failures were from `tests/test_scrape_british_youth.py`.
- Remaining risks: live local source fetches could not run because sandbox DNS failed and escalated network probing was blocked by the approval usage-limit gate; current implementation relies on web-probed public URL evidence and test fixtures reflecting those structures.

---

# Agent 90 Fencer Similarity Recommendation Engine

---

# Agent 148 — Fantasy League Backend

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect graph/memory context and existing result aggregation/migration/test patterns.
- [x] Write failing fantasy league migration, validation, scoring, and idempotency tests.
- [x] Implement `fantasy_league.py` scoring/validation backend.
- [x] Add `supabase/migrations/20260602_fantasy_league.sql`.
- [x] Run focused and full verification; fix any failures in scope.
- [x] Update final review; Wiki-Brain/session log write was blocked by platform usage-limit gate.

## Notes
- Keep scope to `fantasy_league.py`, `supabase/migrations/20260602_fantasy_league.sql`, `tests/test_fantasy_league.py`, and required task/wiki memory.
- Do not edit `.github/workflows/`.
- No app user/auth table exists in this backend; fantasy ownership must remain optional and service/admin-managed.
- Base `fs_results` DDL is not present in migrations, so scoring should not require a foreign key to a result row ID.

## Final Review
- Files changed: `fantasy_league.py`, `supabase/migrations/20260602_fantasy_league.sql`, `tests/test_fantasy_league.py`, `tasks/todo.md`.
- Behavior changed: added service/admin-managed fantasy league tables and deterministic backend scoring for active starter rosters using verified results, medal bonuses, upset bonuses, duplicate-result dedupe, locked-period checks, and idempotent weekly score upserts.
- Verification: red focused tests first failed with missing module/migration; focused `tests/test_fantasy_league.py -v` passed 5/5; `py_compile fantasy_league.py` passed; scoped whitespace check passed; full `.venv/bin/python -m pytest tests/ -v` ran 1903 passed, 10 failed in unrelated/concurrent areas.
- Remaining risks: production DB migration was not applied here; full suite remains red outside Agent 148 scope; CRG change scan and Wiki-Brain/session-log writes were blocked by the platform usage-limit gate.

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect identity logic, existing compute script patterns, and relevant stats/ranking/result fields.
- [x] Write failing tests for feature construction, scoring, symmetry/deduping, duplicate identity exclusion, sparse data, and migration shape.
- [x] Implement `compute_fencer_similarity.py` with deterministic public-data feature vectors, scoring, confidence/sample fields, run logging, and state update.
- [x] Add `supabase/migrations/20260602_similarity.sql` defining similarity storage and unique unordered pairs.
- [x] Run focused verification and fix issues.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `compute_fencer_similarity.py`, `tests/test_fencer_similarity.py`, `supabase/migrations/20260602_similarity.sql`, and task/wiki memory.
- Use `fs_fencer_identities` to avoid recommending duplicate rows for the same physical fencer.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `compute_fencer_similarity.py`, `supabase/migrations/20260602_similarity.sql`, `tests/test_fencer_similarity.py`, `tasks/todo.md`.
- Behavior changed: new deterministic similarity engine builds canonical identity feature vectors from public fencer, ranking, result, tournament, country, hand, birth/age, weapon, and career-stage data; scores unordered non-self pairs; records factor breakdown, confidence, sample size, model version, and timestamp; upserts on `fencer_id,similar_fencer_id`.
- Verification: red focused tests first failed with missing module/migration; focused `tests/test_fencer_similarity.py -v` passed 6/6; `py_compile compute_fencer_similarity.py` passed; `git diff --check` passed; full `tests/ -v` ran 1677 passed and 134 failed in unrelated existing/in-progress areas while all new similarity tests passed.
- Remaining risks: production DB migration was not applied here; full suite remains red due unrelated tasks; CRG change scan and Wiki-Brain/session-log writes were blocked by the environment usage-limit gate.

---

# Agent 50 — Slovenia Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`, and nearby federation scrapers/tests.
- [x] Probe Slovenia ranking URLs and record public source evidence.
- [ ] Write failing parser/fetch tests with realistic Slovenian ranking fixtures.
- [ ] Implement `scrape_fed_slo.py` using public SZS ranking sources, `fed_rankings_common`, `ScraperRunLogger`, and scraper state.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_slo.py`, `tests/test_fed_slo.py`, `tasks/todo.md`, and Wiki-Brain memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Sandbox probe could not resolve external hosts. Required escalated retry was blocked by the approval usage-limit gate.
- Controlled web probe showed `https://www.sabljaska-zveza.si/rang-lestvice.html` is public and has an “Aktualne rang lestvice” Google Sheets link plus archived 2024/2025 PDFs.
- Active host is `sabljaska-zveza.si`; requested `veza.si` did not appear as the active public federation ranking host.
- Public 2024/2025 PDFs are GET `application/pdf` pages per weapon under `/uploads/1/0/9/1/109197245/rl_24_25_<weapon>.pdf`; the extracted text includes Senior (`Člani`) and Junior (`Mladinci`) Men/Women tables for all required weapons.

---

# Agent 71 — Veterans World Cup circuit

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect graph/session memory and nearby FIE/EVF/result scraper patterns.
- [x] Probe FIE/EVF/FTL public veteran source shapes and blocked sources.
- [x] Write failing veteran parser, source-stub, matching, and category-isolation tests.
- [x] Implement `scrape_veterans.py` with EVF parsing, source stubs, conservative fencer matching, run logging, and state.
- [x] Run focused verification and fix failures.
- [x] Update task final review; Wiki-Brain/session log write attempted and blocked by approval usage-limit gate.

## Notes
- Keep scope to `scrape_veterans.py`, `tests/test_scrape_veterans.py`, task memory, and Wiki-Brain.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Non-escalated live probe failed DNS for FIE, EVF, and EVF Circuit Poland pages. Required escalated retry was blocked by the Codex usage-limit approval gate.
- Web probe evidence: EVF 2025 Plovdiv results expose static HTML medal rows by weapon and `Category 1`-`Category 4`; EVF circuit/ranking pages describe public rankings/circuit but do not expose row data on those pages; EVF Circuit Poland 2025 schedule is public but FencingTimeLive event result links redirect to login as of 2026-06-02; FIE 2025 Veteran World Championships article links complete official results to Dropbox, while FIE entry PDFs are public but are entry lists rather than result tables.
- Match fencers by FIE ID first, then canonical name+country. Skip and log unmatched rows; never insert null-fencer result orphans.

## Final Review
- Files changed: `scrape_veterans.py`, `tests/test_scrape_veterans.py`, `tasks/todo.md`.
- Behavior changed: added a veteran scraper that parses EVF static medal result rows into explicit `Veteran 40-49`/`Veteran 50-59`/`Veteran 60-69`/`Veteran 70+` categories, records blocked/no-public source stubs, overrides FIE veteran `hasResults=0` only for completed veteran events, and writes results only when fencers match by FIE ID or canonical name+country.
- Verification: red-first `tests/test_scrape_veterans.py -v` failed 6/6 on missing module, then 2/7 on the FIE age-bucket and all-unmatched delete edge cases; focused final `.venv/bin/python -m pytest tests/test_scrape_veterans.py -v` passed 7/7; `.venv/bin/python -m py_compile scrape_veterans.py tests/test_scrape_veterans.py` passed.
- Broader verification: `.venv/bin/python -m pytest tests/ -v` failed outside this task with 2 failed, 1916 passed, and 1 warning. Failures were `tests/test_export_bigquery.py::test_resume_continues_from_saved_offset_and_chunk_number` and `tests/test_fencing_stores.py::test_parse_pbt_dealers_extracts_live_dealer_nodes`. All `tests/test_scrape_veterans.py` tests passed inside that run.
- Remaining risks: live shell probes were blocked by DNS sandbox and the escalated retry was blocked by the approval usage-limit gate; implementation remains deterministic for blocked/no-public sources and does not invent fallback result rows.
- Wiki-Brain/session log update was attempted for `[[FenceSpace Veteran Fencing Data Sources]]` but blocked because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace and the approval gate rejected the edit due usage limits.

---

# Agent 100 — Fencer nationality history from Wikidata

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing Wikidata enrichment, transfer tracker, country normalization, and migration/test patterns.
- [x] Write failing tests for migration shape, Wikidata qualifiers, transfer reconciliation, ambiguous claims, and country-code normalization.
- [x] Implement source-backed `fs_fencer_nationality_history` upserts without clobbering `fs_fencers.country`.
- [x] Run focused verification and fix failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Keep code changes scoped to `enrich_nationality_history.py`, `supabase/migrations/20260602_nationality_history.sql`, `tests/test_enrich_nationality_history.py`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Existing `enrich_nationality_history.py` parses Wikidata P27 statement qualifiers but stores history in `fs_fencers.metadata`; this task must emit separate history and discrepancy rows instead.
- Existing transfer evidence table is `fs_fencer_transfers`; use it only for reconciliation metadata/discrepancies.

## Final review
- Files changed: `enrich_nationality_history.py`, `supabase/migrations/20260602_nationality_history.sql`, `tests/test_enrich_nationality_history.py`, `tasks/todo.md`.
- Behavior changed: Wikidata nationality enrichment now parses P27 citizenship, P1532 country-for-sport, and P54 national-team public claims with P580/P582/P585 qualifiers and Wikidata IOC/ISO country codes; upserts deterministic history rows to `fs_fencer_nationality_history`; emits reconciliation discrepancies to `fs_fencer_nationality_discrepancies`; preserves existing `fs_fencers.country` and legacy metadata compatibility.
- Verification: red targeted run failed first as expected; fresh `./.venv/bin/python -m pytest tests/test_enrich_nationality_history.py -v` passed 6/6; `./.venv/bin/python -m pytest tests/test_nationality_history.py -v` passed 6/6; `./.venv/bin/python -m py_compile enrich_nationality_history.py` passed; `git diff --check` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` ran 1904 passed, 7 failed, 1 warning. Failures are unrelated product-scraper issues in `tests/test_scrape_allstar_uhlmann.py` (`scrape_allstar_uhlmann.py` line 692 indentation) and `tests/test_scrape_blue_gauntlet_products.py` weapon casing (`All` vs `all`).
- Remaining risks: no live Wikidata query was run; SPARQL shape is covered by fixture/query tests. Country-code fallback map is intentionally conservative and preserves source-provided Wikidata codes when present. Wiki-Brain page/log write outside the repo was blocked by the approval usage-limit gate, so durable external memory was not updated.

---

# Agent 54 Azerbaijan Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`, and recent federation scraper patterns.
- [x] Probe `azfencing.az` / `fencing.az` ranking pages and record public coverage.
- [x] Write failing Azerbaijan parser/fetch tests with realistic fixtures.
- [x] Implement `scrape_fed_aze.py` with all 12 combo attempts and missing-combo handling.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep code scope to `scrape_fed_aze.py`, `tests/test_fed_aze.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- `azfencing.az` did not resolve in the sandbox probe; browser/search evidence shows the current public federation domain is `https://fencing.az`.
- `https://fencing.az/` redirects to `/az/`; request method is GET; response format is server-rendered HTML.
- Public ranking pages found: `https://fencing.az/az/spaqa-reytinq/` / `https://fencing.az/en/epee-ranking/` and `https://fencing.az/az/sablya-reytinq/` / `https://fencing.az/en/sabre-ranking/`.
- Current public coverage: Epee and Sabre Senior/Junior Men/Women. Foil pages were not found in the public ranking menu and likely 404/missing.
- Direct escalated shell probe was blocked by the Codex approval usage gate; browser probe reached the pages and captured page headings/rows.
- Red focused test run failed 13/13 with missing `scrape_fed_aze`; after implementation, focused `tests/test_fed_aze.py -v` passed 13/13.
- `py_compile scrape_fed_aze.py` passed; `tests/test_fed_aze.py tests/test_fed_rankings_common.py -v` passed 18/18.
- Full `tests/ -v` was attempted through context-mode summarization but timed out at the 120-second tool cap before producing a pass/fail result.
- Wiki-Brain update and session log append were attempted but blocked because `/Users/plernghomhual/Documents/Brain` is outside the writable root and the approval usage-limit gate rejected the escalated write.

## Final Review
- Files changed: `scrape_fed_aze.py`, `tests/test_fed_aze.py`, `tasks/todo.md`.
- Behavior changed: Azerbaijan rankings now attempt all 12 standard Senior/Junior Foil/Epee/Sabre Men/Women combos, parse public Epee/Sabre server-rendered ranking sections, and return/report missing Foil or non-public/blocked pages without crashing.
- Verification performed: red focused test run failed on missing module; focused AZE tests passed 13/13; relevant scoped suite with shared ranking helpers passed 18/18; `py_compile scrape_fed_aze.py` passed.
- Remaining risk: direct escalated live shell probe, live scraper run, and Wiki-Brain writes were blocked by the Codex usage-limit approval gate; browser probe evidence found public HTML coverage for 8/12 combos.

---

# Agent 143 — Fencing Event Photographer Directory

## Final Review
- [x] Read project lessons, current task state, and existing scraper patterns.
- [x] Probed public fencing photographer/event gallery sources; local DNS blocked all target URLs and escalated retry was rejected by the usage-limit gate.
- [x] Added red tests for directory/gallery parsing, public-contact filtering, dedupe, tournament linking, upsert conflict key, and migration DDL.
- [x] Implemented `scrape_photographer_directory.py` with safe public business/contact extraction, dedupe, Supabase upserts, run logging, and state tracking.
- [x] Added `supabase/migrations/20260602_photographers.sql`.
- [x] Ran focused, compile, diff-check, and full-suite verification.
- [x] Final review recorded.

## Notes
- Keep scope to `scrape_photographer_directory.py`, `tests/test_photographer_directory.py`, `supabase/migrations/20260602_photographers.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Known public source coverage is sparse: `DEFAULT_SOURCES` covers FencingPhotos public business pages, one public Flickr/FencingNet gallery attribution, and one FIE press-kit PDF source. Live shell probe could not confirm current HTML because sandbox DNS and escalation were blocked.
- Contact safety: parser only stores mailto/source-declared addresses or text emails from public contact/photo/photographer contexts; unrelated competitor/athlete emails are filtered.
- Tournament links are added only when row metadata has a clear event name and `fs_tournaments` returns an explicit name match.
- Verification: red focused test run failed on missing module/migration; focused `tests/test_photographer_directory.py -v` passed 8/8; `py_compile scrape_photographer_directory.py` passed; scoped `git diff --check` passed; full `tests/ -v` ran 1907 tests with new photographer tests passing but 18 unrelated failures in other in-progress areas.
- Cleanup risk: exact generated pycache deletion for this task was blocked by the usage-limit approval gate, so no cleanup retry was attempted.

---

# Agent 17 — Ranking sparkline data endpoint materialized view

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect ranking history/trend schema, public view conventions, and frontend/API prompt dependencies.
- [x] Write failing SQL parser tests for sparkline view columns, JSON/array ordering, dedupe, grants, and safe DDL.
- [x] Add `supabase/migrations/20260602_ranking_sparklines.sql`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review. Blocked: writing `/Users/plernghomhual/Documents/Brain` requires escalation, and escalation was rejected by the usage-limit gate.

## Notes
- Target files: `supabase/migrations/20260602_ranking_sparklines.sql`, `tests/test_ranking_sparklines.py`.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Initial inspection found no Agent 16 `fs_ranking_history_trajectory` migration, so this migration was built against the existing canonical `fs_rankings_history` FIE trajectory table and exposes `source = 'fie'`.
- Read-only frontend graph and follow-up Supabase schema queries were blocked by the usage-limit approval gate; continue with local schema/tests and the first successful table-list snapshot.
- A concurrent untracked `20260602_ranking_trajectory.sql` appeared later, but `20260602_ranking_sparklines.sql` sorts before it lexicographically. Depending on `fs_ranking_history_trajectory` here would make migration application fail under the repo's filename-order migration runner.

## Final Review
- Files changed: `supabase/migrations/20260602_ranking_sparklines.sql`, `tests/test_ranking_sparklines.py`, `tasks/todo.md`.
- Behavior changed: adds `public.v_ranking_sparklines` as a public-safe materialized projection over canonical `fs_rankings_history`, with deterministic duplicate suppression, ordered `seasons`/`ranks`/`points` arrays, ordered JSON `history`, latest/best/worst rank, delta, sample count, and max source `updated_at`.
- Verification: RED focused tests first failed 5/5 on missing migration; focused `tests/test_ranking_sparklines.py -v` passed 5/5, including a fresh post-tracker-edit run; adjacent `tests/test_ranking_sparklines.py tests/test_rankings_trends.py tests/test_rls_policy_sql.py -v` passed 17/17.
- Full suite: `.venv/bin/python -m pytest tests/ -v` stopped during collection with unrelated `ModuleNotFoundError: No module named 'compute_junior_conversion'` from `tests/test_junior_conversion.py`.
- Remaining risks: SQL was validated by parser-style tests, not applied to a live database in this session; trajectory table integration should be revisited after Agent 16 migration ordering is resolved; Wiki-Brain/session log update was blocked by the escalation usage-limit gate.

---

# Agent 31 Mexico Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe `fme.com.mx` ranking paths and record source availability.
- [ ] Write failing Mexico parser/fetch/stub tests.
- [ ] Implement `scrape_fed_mex.py` with all 12 standard combo attempts and safe stub handling.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_mex.py`, `tests/test_fed_mex.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Non-escalated probe of `https://fme.com.mx`, `http://fme.com.mx`, and `www` variants across common Spanish ranking/API paths failed DNS resolution for every URL.
- Required escalated retry was blocked by the approval usage-limit gate, so live public coverage cannot be confirmed from this shell.
- Search surfaced only older `esgrimamexico.com.mx/documentospdf` PDF result archives, not a durable current `fme.com.mx` national rankings source.

---

# Agent 126 Social Leaderboard

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing social media schema, scraper, compute-script patterns, and identity-map behavior.
- [ ] Write failing tests for platform/handle dedupe, stale indicators, ranking tie-breaks, missing/private account exclusion, missing provider behavior, and migration shape.
- [ ] Implement `compute_social_leaderboard.py`.
- [ ] Add `supabase/migrations/20260602_social_leaderboard.sql`.
- [ ] Run focused and full verification; fix issues found.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `compute_social_leaderboard.py`, `tests/test_social_leaderboard.py`, `supabase/migrations/20260602_social_leaderboard.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Existing source table is `fs_fencer_social_media` with `platform`, `handle`, `url`, `source`, `verified`, and `metadata`; no external follower APIs are currently present.
- Existing compute scripts canonicalize duplicate `fs_fencers` rows through `fs_fencer_identities` and batch upsert with `ScraperRunLogger`.

---

# Agent 145 — Fencing camp review aggregator

## Plan
- [x] Read project lessons and current task state.
- [x] Query graph/session memory for camp directory context.
- [x] Inspect existing training camp scraper, camp migration, review scraper patterns, logger/state usage, and upsert conventions.
- [x] Probe representative public camp pages for review/testimonial structure.
- [x] Write failing tests for review parsing, camp matching ambiguity, PII minimization, dedupe/upsert, API dry-run, and migration shape.
- [x] Implement `scrape_camp_reviews.py` with public page/API parsing, camp matching, review hashing, dedupe, rate limiting, state, and run logging.
- [x] Add `supabase/migrations/20260602_camp_reviews.sql`.
- [x] Run focused verification and fix failures.
- [x] Run relevant broader verification.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Keep code changes scoped to `scrape_camp_reviews.py`, `supabase/migrations/20260602_camp_reviews.sql`, and `tests/test_camp_reviews.py`; do not edit `.github/workflows/`.
- Existing camp directory table is `fs_training_camps` with unique `(name, organizer, start_date, end_date)`. Review scraper must only read that table and write `fs_training_camp_reviews`.
- Live probe command for Hooked on Fencing, Capital Fencing, and NWFC camp pages failed in the sandbox with DNS `NameResolutionError`.
- Required escalated retry was blocked by Codex usage-limit approval gate, so live review source shape is unavailable in this shell.
- Per task fallback, use realistic public page/API fixtures and document source gaps instead of scraping login-only/private content.

## Final review
- Files changed: `scrape_camp_reviews.py`, `tests/test_camp_reviews.py`, `supabase/migrations/20260602_camp_reviews.sql`, `tasks/todo.md`.
- Behavior changed: added separate `fs_training_camp_reviews` storage; new camp review scraper reads `fs_training_camps`, parses public testimonial/review HTML and Google Places details fixtures, matches reviews to camps by name plus organizer/date/location signals, logs ambiguous matches in scraper state, hashes reviewer identifiers, strips reviewer/email/contact metadata, dedupes by `source, source_url, source_hash`, and writes only the review table.
- Verification performed: red focused tests failed first on missing module/migration; focused `tests/test_camp_reviews.py -v` passed 7/7; adjacent `tests/test_camp_reviews.py tests/test_camps.py tests/test_club_reviews.py -v` passed 22/22; `py_compile scrape_camp_reviews.py` passed; full `tests/ -v` ran 1677 passed and 134 failed in unrelated in-progress areas.
- Remaining risks: live public page probe could not complete because sandbox DNS failed and escalation was blocked by the usage-limit gate, so parser fixtures are realistic rather than freshly captured; Google Places review collection requires `MAPS_API_KEY` and dry-runs without HTTP when absent.

---

# Agent 129 — News Aggregator Frontend

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect available graph/memory context and verify requested frontend paths.
- [x] Add failing `NewsFeed` tests for safe rendering, filters, pagination, empty, and error states.
- [x] Implement `frontend/pages/news.tsx` and `frontend/components/NewsFeed.tsx` with scoped safe behavior.
- [x] Run focused frontend verification where available and relevant broader checks.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Requested files are `frontend/pages/news.tsx`, `frontend/components/NewsFeed.tsx`, and `frontend/tests/news-feed.test.tsx`.
- The news backend exists as `scrape_news.py`, `tests/test_news.py`, and `supabase/migrations/20260601_news.sql`.
- No frontend news API endpoint exists in this repo; `frontend/pages/news.tsx` exports the required `GET /api/news -> { articles: NewsArticle[] }` contract and uses typed fixtures until that endpoint is wired.
- Do not edit `.github/workflows/`.

## Final review
- Files changed: `frontend/pages/news.tsx`, `frontend/components/NewsFeed.tsx`, `frontend/tests/news-feed.test.tsx`, `frontend/vitest.config.ts`, `tasks/todo.md`.
- Behavior changed: added a safe React news feed with category, fencer, source, date range, and search filters; missing-summary fallback; invalid/non-HTTP source URL fallback; safe outbound links; loading, error, empty, filtered-empty, and pagination states; and no raw HTML rendering.
- Verification performed: red/blocked first focused frontend run exposed missing/incorrect frontend test setup; final `npm test -- news-feed.test.tsx` passed 7/7; focused TypeScript check for the three news files passed; `rg` found no `dangerouslySetInnerHTML`/`innerHTML` in production news files; backend `tests/test_news.py -v` passed 8/8.
- Broader verification: full frontend `npm test` is red in unrelated existing/in-progress tests (`routes.test.tsx`, `h2h-page.test.tsx`, `country-medal-heatmap.test.tsx`, `federation-overview.test.tsx`); full frontend `tsc --noEmit` is blocked by existing `tsconfig.json` `baseUrl` deprecation under TypeScript 6.
- Remaining risks: UI currently uses typed fixtures until `/api/news` is implemented; no browser-rendered screenshot was captured because the task had no runnable Next dev target confirmed beyond the component tests; Wiki-Brain page/index/log write was rejected by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace.

---

# Agent 115 — Calendar ICS Feed

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect calendar/API/tournament context.
- [x] Write failing tests for ICS output, filter validation, and empty feeds.
- [x] Implement `calendar_feed.py` with safe filter validation, stable UID generation, date/timezone handling, Supabase/client helper, and CLI.
- [x] Document feed URL examples, CLI usage, and client behavior in `docs/calendar_feed.md`.
- [x] Run focused and full verification; fix failures.
- [x] Final review recorded; Wiki-Brain/session log blocked by usage-limit approval gate.

## Notes
- Keep scope to `calendar_feed.py`, `tests/test_calendar_feed.py`, `docs/calendar_feed.md`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- `calendar_feed.py` should stay read-only. It can expose a pure generator plus CLI/API-compatible helper rather than modifying `api.py`.

## Final Review
- Files changed: `calendar_feed.py`, `tests/test_calendar_feed.py`, `docs/calendar_feed.md`, `tasks/todo.md`.
- Behavior changed: added read-only ICS generation from tournament rows with federation/country/weapon/category/date filters, stable UIDs, all-day date handling, timezone validation, 500-event cap, Supabase/API-compatible helper, and JSON-input CLI.
- Verification performed: red `tests/test_calendar_feed.py -v` failed 10/10 on missing module; focused calendar tests now pass 13/13; `py_compile calendar_feed.py tests/test_calendar_feed.py` passes; full `.venv/bin/python -m pytest tests/ -v` passes 1922/1922 with one Starlette/httpx deprecation warning.
- Remaining risks: no API route was added because the scoped files did not include `api.py`; docs describe the URL shape for mounting `generate_ics_feed_from_client()`. CRG impact scan and Wiki-Brain page/log writes were blocked by the usage-limit approval gate.

---

# Agent 117 — Automated Result Tweets Bot

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect state, run logging, result ingestion, and social-media test patterns.
- [x] Write failing tests for formatting, duplicate suppression, dry-run/no-credentials, and mocked live posting.
- [x] Implement `post_result_tweets.py` with dry-run default, explicit live-post gates, validation, state, and run logging.
- [x] Document behavior and X/Twitter credential requirements in `docs/result_tweets.md`.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: writing `/Users/plernghomhual/Documents/Brain` requires approval, and the Codex approval usage gate rejected the scoped write request.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Keep code scope to `post_result_tweets.py`, `tests/test_post_result_tweets.py`, `docs/result_tweets.md`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Default behavior must be no-network dry run. Live posting requires explicit env vars and provider credentials.
- Never print credentials or post from tests; provider path must be mocked.

## Final Review
- Files changed for this task: `post_result_tweets.py`, `tests/test_post_result_tweets.py`, `docs/result_tweets.md`, `tasks/todo.md`.
- Behavior changed: added a dry-run-first result tweet generator that reads completed tournaments and podium rows, formats validated X-length posts with links and hashtags, preserves Unicode names, suppresses duplicates through `fs_scraper_state`, and only live-posts after `--live`, `RESULT_TWEETS_LIVE=1`, and `X_API_BEARER_TOKEN` are present.
- Verification performed: red focused run failed 6/6 on missing `post_result_tweets`; `py_compile post_result_tweets.py` passed; focused `tests/test_post_result_tweets.py -v` passed 6/6; full `.venv/bin/python -m pytest tests/ -v` ran 1818 tests with `1717 passed, 101 failed, 8 warnings`.
- Remaining risk: full-suite failures are in unrelated existing/in-progress areas such as aggregate videos, migration/schema checks, enrichment scrapers, ranking alerts, training facilities, transfer value, travel costs, upsets, and public fencer view. X API access was not live-tested; provider path is mocked and documented.
- Wiki-Brain blocker: attempted to create `[[FenceSpace Result Tweets Bot]]`, update `wiki/index.md`, and append `Brain/log.md`, but the outside-repo write was rejected by the approval/usage-limit gate. No workaround attempted.

---

# Agent 8 — Tournament Brackets Schema

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect relevant `fs_bouts`, `fs_results`, and `fs_tournaments` usage.
- [x] Write failing parser tests for `fs_tournament_brackets` shape, uniqueness, indexes, nullability, and SQL safety.
- [ ] Add `supabase/migrations/20260602_tournament_brackets.sql` with idempotent, non-destructive bracket storage.
- [ ] Run focused verification and fix any failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `supabase/migrations/20260602_tournament_brackets.sql`, `tests/test_tournament_brackets_schema.py`, task/wiki memory.
- Do not edit `.github/workflows/`.
- Existing relevant conventions: `fs_bouts` uses `tournament_id`, nullable fencer links, `score_a`, `score_b`, `winner`/`winner_id`, and round labels; `fs_results` accepts unmatched fencer IDs; `fs_tournaments` carries `id`, source identifiers, `weapon`, `gender`, and `category`.
- Red verification: `.venv/bin/python -m pytest tests/test_tournament_brackets_schema.py -v` failed 6/6 because the migration file was missing.

---

# Agent 83 — Sports Integrity Anomaly Detection

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing analytics compute, migration, and test patterns.
- [x] Write failing tests for anomaly table shape, reviewed flag, scoring, conservative suppression, and evidence payloads.
- [x] Implement `compute_anomalies.py` and `supabase/migrations/20260602_anomalies.sql`.
- [x] Run `pytest tests/test_anomalies.py -v` and fix issues.
- [x] Update task memory and final review; Wiki-Brain write blocked by approval usage limit.

## Notes
- Keep scope to `compute_anomalies.py`, `supabase/migrations/20260602_anomalies.sql`, `tests/test_anomalies.py`, task memory, and Wiki-Brain.
- Generated rows must be sports-integrity statistical review signals only, not accusations or proof of wrongdoing.
- Do not generate `match_fixing` anomaly types; betting mismatch checks must stay dormant unless lawful public betting evidence is present.
- Handle small samples, missing rankings, and duplicate bouts conservatively.

## Final Review
- Files changed: `compute_anomalies.py`, `supabase/migrations/20260602_anomalies.sql`, `tests/test_anomalies.py`, `tasks/todo.md`.
- Behavior changed: added conservative sports-integrity anomaly scoring for scoreline outliers, ranking/result deltas, repeated unusual patterns, and public betting-data mismatch records only when lawful public evidence metadata exists.
- Storage changed: added `public.fs_bout_anomalies` with bout/tournament/fencer references, `anomaly_type`, bounded score, confidence level, evidence JSON, `model_version`, `reviewed`, `created_at`, RLS, and indexes.
- Guardrails: low sample sizes suppress signals; missing rankings suppress ranking-delta signals; duplicate bouts are skipped; existing reviewed anomaly keys are not upserted again.
- Verification: initial red `tests/test_anomalies.py -v` failed on missing module/migration; reviewed-flag regression failed before preservation patch; focused `tests/test_anomalies.py -v` passed 10/10; related analytics subset passed 20/20; `py_compile compute_anomalies.py` passed.
- Remaining risk: full `tests/ -v` was attempted through a summarized harness but hit the MCP call timeout before returning; Wiki-Brain write/log append was blocked by the external-filesystem approval usage-limit gate; worktree contains many unrelated dirty/untracked files from other agents.

---

# Agent 105 — Historical Rule Changes

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect nearby news scraper/migration/test patterns.
- [x] Probe public rule-change source structures.
- [x] Write failing parser and migration tests.
- [x] Implement rule-change scraper and storage migration.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_rule_changes.py`, `tests/test_scrape_rule_changes.py`, `supabase/migrations/20260602_rule_changes.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Store source-cited historical facts separately from any causal result-impact claims.
- Non-escalated live probe failed DNS for FIE, British Fencing, USA Fencing, Fencing.Net, and Fencing Archive sources. The required escalated retry was rejected by the approval/usage-limit gate, so parser fixtures use browser-confirmed public structures and cited manual seeds.
- Focused red run failed on missing module/migration; focused final run passed 9/9.

## Final Review
- Files changed for this task: `scrape_rule_changes.py`, `supabase/migrations/20260602_rule_changes.sql`, `tests/test_scrape_rule_changes.py`, `tasks/todo.md`.
- Behavior changed: added `fs_rule_changes` storage with source/date constraints and no-untested-impact guard; added rule-change parser for FIE rulebook listings, federation summaries, historical archive document listings, cited manual seeds, validation/filtering, Supabase upsert, state, and run logging.
- Verification performed: `.venv/bin/python -m pytest tests/test_scrape_rule_changes.py -v` passed 9/9; `.venv/bin/python -m py_compile scrape_rule_changes.py` passed; `git diff --check -- scrape_rule_changes.py supabase/migrations/20260602_rule_changes.sql tests/test_scrape_rule_changes.py tasks/todo.md` passed.
- Broader verification: `.venv/bin/python -m pytest tests/ -v` failed outside this task with 55 failed, 1792 passed, 17 errors, 8 warnings. `tests/test_scrape_rule_changes.py` passed in that run.
- Remaining risks: live external parser smoke could not run from this shell due network approval limits; USA Fencing source currently returns 403 in browser tooling and is covered as a cited manual seed. No production data was dropped, truncated, or rewritten.

---

# Agent 55 Puerto Rico Federation Scraper

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe Puerto Rico ranking URLs and record public combo coverage.
- [x] Write failing parser/fetch tests with Puerto Rico ranking fixtures.
- [x] Implement `scrape_fed_pur.py` using `fed_rankings_common`, `ScraperRunLogger`, and scraper state.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `scrape_fed_pur.py`, `tests/test_fed_pur.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Probe evidence: `fepur.org` DNS failed in local sandbox; browser confirmed public ranking page at `https://fedesgrimapuertorico.org/ranking/`.
- Probe evidence: ranking page exposes category links by Spanish headings; Adulto XLSX link observed at `/wp-content/uploads/2026/04/Ranking-Nacional-Adulto-2025-2026-Actualizado-abril-252026.xlsx`.
- Probe constraint: escalated workbook probe was blocked by usage-limit approval gate, so tests use realistic XLSX fixtures based on the public ranking page and Spanish headers.

Final review:
- Files changed: `scrape_fed_pur.py`, `tests/test_fed_pur.py`, `tasks/todo.md`.
- Behavior changed: added Puerto Rico federation ranking scraper that discovers category ranking links from the public federation ranking page, downloads XLSX workbooks, extracts matching Senior/Junior Foil/Epee/Sabre Men/Women sheets, parses Spanish ranking rows, writes through `fed_rankings_common.write_rankings()`, and logs failed combos/state.
- Verification: red test run first failed on missing module; `./.venv/bin/python -m pytest tests/test_fed_pur.py -v` now passes 9/9; `./.venv/bin/python -m py_compile scrape_fed_pur.py` passes; `./.venv/bin/python -m pytest tests/test_fed_pur.py tests/test_fed_rankings_common.py -v` passed 14/14 before cleanup; full `tests/ -v` currently fails outside this task with 100 unrelated failures and 1718 passes.
- Wiki-Brain: created `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace Puerto Rico Federation Scraper.md`; updating `wiki/index.md` and appending `log.md` were blocked by the approval/usage gate.
- Remaining risks: live workbook sheet names and Junior coverage could not be verified from this shell because escalated network probing was blocked by the approval/usage gate; scraper attempts all 12 combos and reports missing sheets/links rather than crashing.

---

# Agent 72 — European Fencing Confederation Youth Circuit

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect graph context and nearby youth/result scraper patterns.
- [x] Probe current EFC youth circuit public pages/download structures.
- [x] Write failing parser, restraint, matching, and run-path tests.
- [x] Implement `scrape_efc_youth.py` with public-source parsing, fencer matching, skipped-source stubs, run logging, state, and rate limiting.
- [x] Run focused verification and fix failures.
- [x] Write local final review; Wiki-Brain/session-log write attempted but blocked by approval usage limit.

## Notes
- Keep scope to `scrape_efc_youth.py`, `tests/test_scrape_efc_youth.py`, `tasks/todo.md`, and Wiki-Brain memory.
- Do not edit `.github/workflows/`.
- Match fencers by FIE ID first, then exact name+country; accept unmatched only with explicit unmatched logging.
- Avoid private/minor profile scraping; only public competition result rows should be imported.
- Probe: current `fencing-efc.eu/results` lists event detail pages; detail pages expose public result rows with `Rank`, `Points`, `Name`, `Age`, `Nationality`; older mirror pages at `efc.leonidovich.net`/`efc.bpartners.swiss` show the same shape for cadet circuits and U20 championships. Public linked downloads include invitation PDFs, Engarde/federation-hosted links, and XLSX/PDF result downloads. Local read-only probe script was blocked by sandbox DNS and escalation usage limits, so live evidence came from indexed web fetches.

## Final Review
- Files changed: `scrape_efc_youth.py`, `tests/test_scrape_efc_youth.py`, `tasks/todo.md`.
- Behavior changed: added an EFC youth scraper for public cadet/junior result pages and public PDF/XLSX downloads, with multilingual header parsing, points/date normalization, U14/sub-cadet skip stubs, run logging, state summaries, rate limiting, and FIE-ID-first fencer matching.
- Minor-data restraint: result rows ignore age and profile URLs; unmatched fencers are logged in metadata/run state instead of blocking inserts.
- Verification: red run first failed 5/5 on missing `scrape_efc_youth`; focused `.venv/bin/python -m pytest tests/test_scrape_efc_youth.py -v` now passes 6/6; `.venv/bin/python -m py_compile scrape_efc_youth.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed with 1851 passed, 45 failed, 1 warning. Failures were outside Agent 72 scope; no EFC youth tests failed.
- Remaining risk: local read-only probe script could not resolve EFC hosts in sandbox and escalation was blocked by usage limits, so live structure evidence came from web-indexed public EFC pages rather than local `requests` output.
- Remaining risk: external Wiki-Brain update to `/Users/plernghomhual/Documents/Brain` was attempted and rejected by the approval usage-limit gate; no workaround was attempted.

---

# Agent 65 USA Y12/Y14 Youth Circuit Results

## Plan
- [x] Read lessons and current task state.
- [x] Inspect existing FRED/result/youth scraper patterns.
- [ ] Probe current USA Fencing/FRED public youth result endpoints.
- [ ] Write failing tests for Y12/Y14 parsing, normalization, privacy, blocked dry-run behavior, and explicit matching.
- [ ] Implement `scrape_usa_youth.py` with cautious matching and no AskFRED-private scraping.
- [ ] Run targeted verification and fix failures.
- [ ] Update Wiki-Brain/session log.
- [ ] Final review: files changed, behavior changed, verification, risks.

## Notes
- Keep implementation scope to `scrape_usa_youth.py`, `tests/test_scrape_usa_youth.py`, task memory, and Wiki-Brain.
- Existing `scrape_fred.py` uses public FRED HTML/CSV result exports and existing USA ID/name+country matching helpers, but permits unmatched result rows with `fencer_id=None`; this task requires youth imports to log and skip unmatched rows instead.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

---

# Agent 25 Ranking Trajectory API

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect ranking trajectory prompts, current ranking schemas, season utilities, API conventions, and frontend trajectory context.
- [x] Write failing API/helper tests for ordering, season normalization, filters, missing data, and invalid params.
- [x] Implement scoped `api/v1/fencer_ranking_trajectory.py` helper/router without editing shared API router files.
- [x] Run focused verification and fix any failures.
- [ ] Update Wiki-Brain/session log.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Added `api/v1/fencer_ranking_trajectory.py` with a standalone FastAPI router and pure helper functions.
- Added `tests/test_api_fencers_ranking_trajectory.py` with red-first coverage for season normalization, chronological ordering, filters, missing data, invalid params, route behavior, and missing backing table fallback.
- This repo currently has a top-level `api.py` module, not an `api/` package, so no `api/__init__.py` was added and shared API import behavior was left unchanged.
- `fs_ranking_history_trajectory` / sparkline view migrations are not present in this checkout; the helper targets the intended table shape with mocked rows and returns empty history if that table is absent.
- Verification: red `.venv/bin/python -m pytest tests/test_api_fencers_ranking_trajectory.py -v` failed before implementation because the module was missing; green focused run passed 13/13 with one Starlette/httpx deprecation warning.
- Verification: `.venv/bin/python -m py_compile api/v1/fencer_ranking_trajectory.py tests/test_api_fencers_ranking_trajectory.py` passed; `git diff --check` passed.
- Review note: CRG `detect_changes_tool` was blocked by the external usage-limit gate, so local diff/test verification was used.
- Remaining risk: central router wiring is intentionally left to the merge/integration agent; this module is not automatically mounted by existing `api.py`.

---

# Agent 42 — South Africa Federation Scraper

## Plan
- [x] Read project lessons, current task state, graph context, and existing federation scraper patterns.
- [x] Probe South Africa federation ranking source and identify public ranking coverage.
- [x] Write failing parser/fetch tests with realistic South Africa/Ophardt fixtures.
- [x] Implement `scrape_fed_rsa.py` using dynamic public ranking discovery, `fed_rankings_common`, run logging, and state tracking.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Keep scope to `scrape_fed_rsa.py`, `tests/test_fed_rsa.py`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- `https://safencing.co.za/` and `/rankings/` failed DNS from the sandboxed probe.
- Public search/open probe found active FFSA page `https://safencer.co.za/rankings/`.
- `https://safencer.co.za/rankings/` is public `GET text/html`, lists all 12 Senior/Junior Men/Women Foil/Epee/Sabre ranking links, and links to Ophardt (`fencing.ophardt.online`) detail pages.
- Escalated shell live probe was blocked by the Codex approval usage gate, so implementation uses dynamic discovery from the public federation page instead of hard-coded Ophardt ranking IDs.

## Final Review
- Files changed: `scrape_fed_rsa.py`, `tests/test_fed_rsa.py`, `tasks/todo.md`.
- Behavior changed: added a South Africa federation scraper that discovers all 12 public Senior/Junior Men/Women Foil/Epee/Sabre Ophardt ranking links from `https://safencer.co.za/rankings/`, parses HTML ranking tables with English/Ophardt headers, decimal commas, UTF-8/native-script names, and DNS/DQ/summary/malformed row skipping, writes rows through `fed_rankings_common.write_rankings()`, and records run state/logging.
- Verification performed: red focused RSA tests first failed with missing module; `./.venv/bin/python -m pytest tests/test_fed_rsa.py -v` passed 13/13; `./.venv/bin/python -m pytest tests/test_fed_rsa.py tests/test_fed_rankings_common.py -v` passed 18/18; `./.venv/bin/python -m py_compile scrape_fed_rsa.py tests/test_fed_rsa.py` passed; `git diff --check -- scrape_fed_rsa.py tests/test_fed_rsa.py tasks/todo.md` passed.
- Full suite note: `./.venv/bin/python -m pytest tests/ -v` collected 1679 items but stopped during collection on unrelated missing modules `dedupe_headshots` and `compute_junior_conversion`.
- Remaining risk: shell live fetch could not be escalated because the Codex approval usage gate rejected the network probe; public coverage is based on the web-opened federation ranking page and unit fixtures based on its Ophardt structure.
- Wiki-Brain update skipped: scoped write to `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace South Africa Federation Scraper.md`, `wiki/index.md`, and `log.md` was rejected by the approval usage gate.

---

# Agent 123 Mobile Push Notifications

## Plan
- [x] Read project lessons, current task state, graph context, and live-result/state/migration/test patterns.
- [x] Write failing tests for push migration shape, dry-run provider delivery, duplicate suppression, payload privacy, ownership validation, and retry/backoff.
- [x] Implement `push_notifications.py` with dry-run APNs/FCM provider abstraction, opt-in subscription filtering, live-result change detection, sent fingerprint state, rate limiting, and retry logging.
- [x] Add `supabase/migrations/20260602_push_notifications.sql` for device subscriptions and delivery logs with RLS/ownership constraints.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `push_notifications.py`, `supabase/migrations/20260602_push_notifications.sql`, `tests/test_push_notifications.py`, and task/wiki memory.
- Default provider mode must be dry-run safe when mobile credentials are missing.
- Push payloads must be compact and public-safe: no token, endpoint, metadata, service key, or private row fields.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

## Final review
- Files changed: `push_notifications.py`, `supabase/migrations/20260602_push_notifications.sql`, `tests/test_push_notifications.py`, `tasks/todo.md`.
- Behavior changed: added dry-run-safe mobile push notification service for live-result rows, APNs/FCM provider abstraction with injectable transports, subscription ownership/opt-in validation, compact privacy-safe payloads, per-subscription duplicate suppression via `fs_scraper_state` plus delivery-log fallback, delivery-log upserts, rate limiting hook, and retry/backoff on provider failures.
- Migration changed: added `fs_push_devices`, `fs_push_subscriptions`, and `fs_push_delivery_log` with opt-in/disabled flags, delivery idempotency uniqueness, indexes, RLS ownership policies, and service-role-only delivery writes.
- Verification: red `tests/test_push_notifications.py -v` failed on missing migration/module; focused `tests/test_push_notifications.py -v` passed 7/7; `py_compile push_notifications.py` passed; relevant regression `tests/test_live_results.py tests/test_push_notifications.py -v` passed 9/9; full `.venv/bin/python -m pytest tests/ -v` ran and failed with 44 unrelated failures / 1855 passed / 1 warning from existing dirty-worktree tests, not from `tests/test_push_notifications.py`.
- Remaining risk: real APNs/FCM network transport is intentionally not implemented without provider credentials/transport injection; default and missing-credential modes remain dry-run.
- Wiki-Brain blocker: attempted to update `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace-Scraper.md` and append `/Users/plernghomhual/Documents/Brain/log.md`, but the required escalation was rejected by the approval gate due usage limits. The durable summary is recorded here instead.

---

# Agent 122 Competition PDF OCR Results Pipeline

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect initial graph context and relevant PDF/result scraper patterns.
- [x] Write failing fixture tests for PDF extraction, dry-run/no-write behavior, low-confidence review output, malformed PDFs, duplicate rows, scanned/rotated handling, and opt-in writes.
- [x] Implement `ocr_results.py` with PDF bytes/path extraction, optional OCR fallback, candidate normalization, confidence scoring, duplicate suppression, manual-review output, and safe write path.
- [x] Update `docs/ocr_results.md` with optional OCR dependencies and dry-run workflow.
- [x] Run focused and full verification; fix issues.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `ocr_results.py`, `tests/test_ocr_results.py`, `docs/ocr_results.md`, and task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Default behavior must not write to Supabase.

## Final Review
- Files changed: `ocr_results.py`, `tests/test_ocr_results.py`, `docs/ocr_results.md`, `tasks/todo.md`.
- Behavior changed: added a dry-run-first PDF results pipeline that accepts bytes or paths, extracts text/tables with `pdfplumber`, reconstructs rotated pages, optionally falls back to injected/Tesseract OCR only when enabled, normalizes tournament/event/result candidates, scores confidence, suppresses duplicate rows, emits manual-review items, and writes only high-confidence rows when explicitly requested.
- Verification: red `tests/test_ocr_results.py -v` failed 7/7 on missing `ocr_results`; focused `tests/test_ocr_results.py -v` passed 7/7 after implementation; `py_compile ocr_results.py tests/test_ocr_results.py` passed; related PDF scraper regression `tests/test_ocr_results.py tests/test_scrape_universiade.py tests/test_scrape_commonwealth.py tests/test_scrape_cac_games.py -v` passed 25/25; full `.venv/bin/python -m pytest tests/ -v` passed the OCR tests but failed overall with 46 unrelated failures and 1851 passes in the current dirty worktree.
- Remaining risk: real OCR quality depends on external Tesseract/pytesseract setup and was not exercised with a live OCR engine; tests use injected OCR to avoid installing/running large OCR jobs.

---

# Agent 63 FFSU Fencing Results

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect existing university/games scraper patterns and result upsert conventions.
- [ ] Probe public FFSU fencing pages and document reachable result sources.
- [ ] Write failing parser/upsert/no-public-data tests from realistic French FFSU fixtures.
- [ ] Implement `scrape_ffsu.py` with discovery, parsing, normalization, matching, run logging, state, and rate limiting.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_ffsu.py`, `tests/test_scrape_ffsu.py`, plus task/wiki memory.
- Public source found during initial web probe: `https://sport-u.com/sports-ind/ESCRIME/` links CFU fencing result PDFs for 2022-2024 and a 2025 results spreadsheet.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

---

# Agent 23 AI Insights Pipeline

## Plan
- [x] Read project lessons, current task state, graph context, and relevant compute/migration/test patterns.
- [x] Write failing tests for `fs_ai_insights` schema, evidence-backed summaries, comparisons, skip behavior, no-provider behavior, and upsert caching.
- [x] Implement `compute_ai_insights.py` with deterministic rule-based insight generation from existing analytics outputs.
- [x] Add `supabase/migrations/20260602_ai_insights.sql` for idempotent storage and refresh-friendly uniqueness.
- [x] Run targeted pytest verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Keep scope to `compute_ai_insights.py`, `supabase/migrations/20260602_ai_insights.sql`, `tests/test_ai_insights.py`, and task/wiki memory.
- Default generation must be deterministic and evidence-backed; provider generation remains optional/dry-run only.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `compute_ai_insights.py`, `supabase/migrations/20260602_ai_insights.sql`, `tests/test_ai_insights.py`, `tasks/todo.md`.
- Behavior changed: added deterministic rule-based fencer performance summaries and fencer-pair comparisons from existing stats, performance analysis, rankings trends, head-to-head rows, and dated recent results; each sentence is mirrored in `evidence_json` with source tables and cited values; provider generation is opt-in and dry-run by default.
- Verification: red `tests/test_ai_insights.py -v` failed on missing module/migration; mixed weapon-label edge test failed before normalization; `tests/test_ai_insights.py -v` passed 7/7; related compute suite `tests/test_ai_insights.py tests/test_performance_analysis.py tests/test_rankings_trends.py tests/test_head_to_head.py -v` passed 20/20; `py_compile compute_ai_insights.py` passed.
- Full suite: attempted `.venv/bin/python -m pytest tests/ -v`, but the context-mode tool host timed out before returning a result; bounded related-suite verification completed instead.
- Remaining risks: real Supabase production population was not run because this task is schema/code/test only and should not write production data.

---

# Agent 15 Country Geo Backfill

## Plan
- [x] Read lessons and current task state.
- [x] Inspect country/geocode/state/rate-limit patterns.
- [ ] Write failing geocode country tests.
- [ ] Implement deterministic country geocode/backfill script.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.
- [ ] Final review: files changed, behavior changed, verification, risks.

## Notes
- Scope is `scripts/geocode_countries.py`, `tests/test_geocode_countries.py`, task/wiki memory, and any strictly required test/dependency files.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Prefer static ISO/NOC centroid data; only use Nominatim for missing countries with rate limiting and cached failures.

---

# Agent 106 Next.js Frontend

## Plan
- [x] Read project lessons, current task state, API contract, public-view migrations, and package/frontend state.
- [x] Write failing Python/frontend contract tests and frontend route/search tests before implementation.
- [x] Create scoped Next.js TypeScript frontend with Tailwind, validated server-side data client, and no service-key browser exposure.
- [x] Implement `/`, `/fencers`, `/fencers/[id]`, `/tournaments`, `/tournaments/[id]`, `/rankings`, `/countries/[code]`, and `/head-to-head` with loading, empty, error, search, and pagination states.
- [x] Run Python contract tests, frontend tests, build, and route-render coverage; fix failures.
- [ ] Update Wiki-Brain/session log.
- [x] Add final review.

## Notes
- Scope: `frontend/`, `frontend/package.json`, `frontend/next.config.js`, `frontend_api_contract.py`, `tests/test_frontend_contract.py`, task/wiki memory, and required frontend test/config files.
- Do not edit `api.py` or `.github/workflows/`.
- Server data loading may use `FENCESPACE_API_BASE_URL` plus `FENCESPACE_API_KEY`/`FS_API_KEY`/`API_KEY`; never expose `SUPABASE_SERVICE_KEY` or scraper credentials to client bundles.
- If live API env is unavailable, render typed deterministic fallback fixtures so pages remain browsable locally without inventing backend behavior.
- The default Turbopack build was blocked by sandbox port-binding behavior, so `frontend/package.json` uses `next build --webpack` for the production build command.
- Local dev server smoke could not be completed because sandbox and escalation both blocked binding `127.0.0.1:3000`; route rendering is covered by Vitest and build route collection.

## Final Review
- Files changed for Agent 106: `frontend/`, `frontend/package.json`, `frontend/next.config.js`, `frontend_api_contract.py`, `tests/test_frontend_contract.py`, and targeted frontend config/test files under `frontend/`.
- Behavior changed: added a Next.js TypeScript/Tailwind browse UI with server-side data access, typed mock fixtures when live API env is absent, query-param validation, accessible search/filter/pagination, and empty/error/loading states for required entity routes.
- Pages implemented: `/`, `/fencers`, `/fencers/[id]`, `/tournaments`, `/tournaments/[id]`, `/rankings`, `/countries/[code]`, `/head-to-head`.
- Security: frontend data client reads only server-side `FENCESPACE_API_BASE_URL` and API-key envs; tests scan frontend source to ensure private Supabase/scraper secrets are not referenced.
- Verification: `cd frontend && npm run test` passed 13 files / 69 tests; `cd frontend && npm run build` passed; `.venv/bin/python -m pytest tests/test_frontend_contract.py -v` passed 4/4; full `.venv/bin/python -m pytest tests/ -v` passed 1923 tests with 1 warning.
- Remaining risks: no live API env was available, so runtime data was validated against typed fixtures and mocked route tests; local HTTP smoke was blocked by port-binding permissions; Wiki-Brain page/log write was rejected by the approval/usage gate.

---

# Agent 108 WebSocket Live Results Push

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect graph/wiki context for relevant scraper/API patterns.
- [x] Inspect live watcher, API auth, result, run logger, and state patterns.
- [x] Write failing WebSocket tests before implementation.
- [x] Implement read-only FastAPI WebSocket live-results server.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Keep scope to `ws_server.py`, `tests/test_ws_server.py`, task/wiki memory, and any strictly required test/dependency files.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- `watch_live_results.py` writes live rows and state; `ws_server.py` must only read/query and push to clients.
- Red test evidence: `tests/test_ws_server.py` initially failed with `ModuleNotFoundError: No module named 'ws_server'`.
- Focused WebSocket tests pass 4/4 with one existing FastAPI/Starlette deprecation warning.
- Related verification passes 18/18 for `tests/test_ws_server.py tests/test_api.py tests/test_live_results.py`.
- Full `.venv/bin/python -m pytest tests/ -v` ran 1899 tests: 1865 passed, 34 failed, 1 warning. Failures are outside Agent 108 scope.
- Wiki-Brain update could not be completed because writing `/Users/plernghomhual/Documents/Brain` requires escalation and the approval gate rejected the request due usage limits.

## Final Review
- Files changed for Agent 108: `ws_server.py`, `tests/test_ws_server.py`, `requirements.txt`, `tasks/todo.md`.
- Behavior changed: added read-only FastAPI WebSocket endpoint `/ws/live-results/{tournament_id}` with API-key validation, tournament existence validation, per-client result/bout include filters, polling via `asyncio.to_thread`, bounded send queues, heartbeat events, changed-row detection, and disconnect cleanup.
- Verification: red test first failed on missing `ws_server`; focused WebSocket tests pass; syntax compile passes; related API/live-result tests pass; full suite has unrelated failures listed above.
- Remaining risks: no live Supabase WebSocket smoke was run from this shell; DB polling assumes `fs_results` and `fs_bouts` remain queryable by `tournament_id`; Wiki-Brain/session log write is blocked by approval usage limits.

---

# Agent 102 Equipment Usage Trends

## Plan
- [x] Read project lessons, current task state, CRG context, and related equipment sponsor/review patterns.
- [ ] Write failing migration/parser/normalization/aggregate tests for equipment trend evidence.
- [x] Implement `scrape_equipment_trends.py` and `supabase/migrations/20260602_equipment_trends.sql` with scoped evidence-backed aggregation.
- [x] Run focused verification and fix any failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Keep scope to `scrape_equipment_trends.py`, `tests/test_scrape_equipment_trends.py`, `supabase/migrations/20260602_equipment_trends.sql`, task/wiki memory, and any strictly required test files.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Trend rows must come from explicit public profile/sponsor/product evidence, never visual/image inference.
- Existing related source: `scrape_equipment.py` writes `fs_fencer_equipment` with explicit text evidence and brand aliases; `scrape_equipment_reviews.py` provides product brand/category normalization signals.

## Final Review
- Files changed: `scrape_equipment_trends.py`, `tests/test_scrape_equipment_trends.py`, `supabase/migrations/20260602_equipment_trends.sql`, `tasks/todo.md`.
- Behavior changed: added evidence-backed equipment trend aggregation from stored `fs_fencer_equipment`, product review brand signals, fencer/result/tournament context, and optional rate-limited FIE profile text parsing. Ambiguous low-confidence brand mentions are skipped; no image/speculative inference is used.
- Verification: red focused run first failed 8/8 on missing module/migration; focused `tests/test_scrape_equipment_trends.py -v` passes 9/9; adjacent `tests/test_equipment.py tests/test_scrape_equipment_trends.py -v` passes 17/17; `py_compile scrape_equipment_trends.py` passes; full `tests/ -v` completed with 1875 passed, 24 unrelated failures, 1 warning.
- Remaining risks: full suite has unrelated failures in existing/in-progress areas; CRG change detection was blocked by the usage-limit approval gate after the initial CRG context pass.

---

# Agent 93 Anti-Doping Public Records

## Plan
- [x] Read project lessons, current task state, and relevant scraper/migration patterns.
- [x] Probe ITA/WADA/public sanction sources and document scrapeable official coverage.
- [x] Write failing tests for migration shape, official sanction parsing, cleared/appeal classification, ambiguous matching, and no-public-data behavior.
- [x] Implement `scrape_doping.py` and `supabase/migrations/20260602_doping.sql` with official-source-only records, run logging, state tracking, rate limiting, and ambiguity logging.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Keep scope to `scrape_doping.py`, `tests/test_scrape_doping.py`, `supabase/migrations/20260602_doping.sql`, task/wiki memory, and any strictly required dependency/test files.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Do not infer doping history from rumors, news, or private/non-public data.
- Probe evidence: FIE Clean Sport page exposes public disclosure/table framing but current page has a placeholder; FIE Administrative Department links the public May 2026 sanctions PDF; current FIE sanctions PDF has an ADVR section with Anna Kun (HUN), FIE Doping Disciplinary Tribunal decision date, Art. 2.4 violation, ineligibility dates, disqualification, and fine. ITA FIE partner/news pages provide public delegated-program and potential-ADRV context, not a complete testing-history dataset. WADA Prohibited Association List is support-personnel oriented, not fencing athlete testing history.
- Local network probe failed on sandbox DNS and escalation was rejected by the approval usage gate; browser probes supplied official source structure for fixtures.

## Final Review
- Files changed: `scrape_doping.py`, `tests/test_scrape_doping.py`, `supabase/migrations/20260602_doping.sql`, `tasks/todo.md`.
- Behavior changed: added a conservative anti-doping scraper/table for official public records only. FIE PDF sanctions become `sanction`; ITA notification text becomes `potential_adrv`; appeal and cleared public cases are separately labeled; FIE no-public-data stub emits no row. Matching only attaches `fencer_id` from explicit FIE ID or unique name+country+birth-date evidence; ambiguous name/country candidates are logged and stored as metadata.
- Verification: red focused run first failed 8/8 on missing module/migration; focused `.venv/bin/python -m pytest tests/test_scrape_doping.py -v` now passes 8/8; `.venv/bin/python -m py_compile scrape_doping.py` passes; full `.venv/bin/python -m pytest tests/ -q` completed with 1876 passed, 23 unrelated failures, 1 warning.
- Remaining risks: local live network probe could not run because DNS was sandboxed and escalation was blocked; default source URLs are based on official browser-probed public pages and may need refresh when FIE rotates PDF asset IDs. Wiki-Brain page/index/log write was attempted but rejected by the approval usage gate because `/Users/plernghomhual/Documents/Brain` is outside the writable workspace.

---

# Agent 33 Venezuela Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing federation scraper/common/season patterns.
- [x] Probe `fevenesgrima.com.ve` public ranking URLs and record coverage.
- [x] Add failing Venezuela parser/fetch tests from probed or realistic Spanish fixtures.
- [x] Implement `scrape_fed_ven.py`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files: `scrape_fed_ven.py`, `tests/test_fed_ven.py`.
- Keep scope narrow; do not edit `.github/workflows/`.
- Probe evidence: GET requests to apex/www, HTTP/HTTPS, likely ranking paths, and WordPress `wp-json` search/page/post endpoints all failed DNS resolution in the sandbox. Escalated confirmation was blocked by the approval usage gate.
- Wiki-Brain write attempted for `FenceSpace Venezuela Federation Scraper`, `wiki/index.md`, and `log.md`; write was rejected by the approval usage gate, so local task notes are the fallback memory.

## Final Review
- Files changed: `scrape_fed_ven.py`, `tests/test_fed_ven.py`, `tasks/todo.md`.
- Behavior changed: added Venezuela federation scraper with robust Spanish ranking parser, empty public URL stub mode, all-12 combo attempts, 404/network/login/JS/no-data handling, run logging, and state metadata.
- Verification: red focused test run first failed on missing module; `./.venv/bin/python -m pytest tests/test_fed_ven.py -v` passes 15/15; `./.venv/bin/python -m py_compile scrape_fed_ven.py` passes; no-credential `./.venv/bin/python scrape_fed_ven.py` exits 0 with `written=0`, `failed=12`, `combos_working=0/12`.
- Remaining risks: no durable public Venezuela ranking source could be verified because the federation host did not resolve from the sandbox and outside-sandbox escalation was blocked; Wiki-Brain/log update was also blocked by the approval usage gate.

---

# Agent 78 Peak Performance Age Analysis

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect analytics script/test patterns, fencer identity fields, result/ranking schemas, and competition tier data.
- [x] Add failing tests for age calculation, partial/missing dates, outlier exclusion, grouping, duplicate identities, sparse cohorts, and report output.
- [x] Implement `compute_peak_age.py` with deterministic aggregate-only statistics, skipped counts, sparse-data safeguards, run logging, and optional Supabase adapter.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `compute_peak_age.py`, `tests/test_peak_age.py`, plus task/wiki memory.
- Keep output aggregate-only; no person-level peak-age claims.
- Do not edit `.github/workflows/`.
- Age thresholds must be explicit and exclude implausible result ages.

## Final Review
- Files changed: `compute_peak_age.py`, `tests/test_peak_age.py`, `tasks/todo.md`.
- Behavior changed: added aggregate-only peak-age analysis over result and ranking observations with exact-date validation, age thresholds 10.0-90.0 inclusive, identity dedupe, country/tier/source grouping, sparse-cohort suppression of peak ranges, run logging/state updates, and optional `fs_peak_age_analysis` upsert adapter.
- Verification performed: red focused test run failed before implementation with missing `compute_peak_age`; focused `tests/test_peak_age.py -v` passed 8/8; `py_compile compute_peak_age.py` passed; fresh full `.venv/bin/python -m pytest tests/ -v` passed all 8 peak-age tests but failed overall with 18 unrelated existing failures and 1889 passed tests.
- Remaining risks: no migration was added for the optional `fs_peak_age_analysis` table; `--write-table` requires that table to exist. Full-suite status remains blocked by unrelated failing/missing features outside Agent 78 scope. Wiki-Brain page/log write was attempted but blocked by the Codex escalation usage gate for writes outside the workspace.

---

# Agent 97 Fencer Video Highlight Reels

## Plan
- [x] Read project lessons and current task state.
- [x] Inspect scraper, migration, test, logger, state, and Supabase upsert patterns.
- [x] Write failing focused tests for video table shape, uniqueness, YouTube fixture parsing, false-positive filtering, related entity linking, upsert behavior, missing-key dry run, and rate limiting.
- [x] Implement `aggregate_videos.py`, `supabase/migrations/20260602_videos.sql`, and `tests/test_aggregate_videos.py`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.
- [x] Final review: files changed, behavior changed, verification, risks.

## Notes
- Target files: `aggregate_videos.py`, `supabase/migrations/20260602_videos.sql`, `tests/test_aggregate_videos.py`.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Do not download/process videos; store provider metadata and thumbnails only.
- Provider probe: sandbox DNS could not resolve `www.googleapis.com`; escalated read-only probe was blocked by usage-limit approval gate. Tests use realistic YouTube Data API fixture shape.
- Wiki-Brain page/log write was attempted but rejected by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable sandbox.

## Final Review
- Files changed: `aggregate_videos.py`, `supabase/migrations/20260602_videos.sql`, `tests/test_aggregate_videos.py`, `tasks/todo.md`.
- Behavior changed: added YouTube Data API metadata aggregation with missing-key dry run, conservative fencer/tournament matching, official-channel search targets, false-positive filtering, duration/statistics metadata, thumbnail URL storage, provider/video dedupe, Supabase upsert on `provider,video_id`, rate limiting, state updates, and run logging.
- Verification performed: red focused run first failed 6/6 on missing module/migration; edge-case tournament matcher regression failed before the matcher patch; focused `.venv/bin/python -m pytest tests/test_aggregate_videos.py -v` passed 7/7; `.venv/bin/python -m py_compile aggregate_videos.py tests/test_aggregate_videos.py` passed; `env -u YOUTUBE_API_KEY .venv/bin/python aggregate_videos.py` exited 0 with dry-run evidence; full `.venv/bin/python -m pytest tests/ -q` passed 1922/1922 with one FastAPI/Starlette deprecation warning.
- Remaining risks: no live YouTube response was captured because sandbox DNS blocked the probe and escalation was rejected by the usage-limit gate; Wiki-Brain update/log append was blocked by the same approval gate; production population requires `YOUTUBE_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_KEY`.

---

# Agent 98 — Interview Quotes Database

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect existing news/run logging/state patterns.
- [x] Probe official FIE/federation/news press pages for public quote structure.
- [x] Add failing quote parser and migration tests.
- [x] Implement `scrape_quotes.py` and `fs_quotes` migration.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_quotes.py`, `supabase/migrations/20260602_quotes.sql`, `tests/test_scrape_quotes.py`.
- Keep scope narrow; do not edit `.github/workflows/`.
- Store short quote excerpts and source links only; do not persist full article/transcript text.
- Speaker to fencer matching must be conservative and log ambiguous names.
- Shell network probe failed on sandbox DNS; escalated probe was blocked by the approval usage-limit gate. Official-page search evidence confirmed FIE and USA Fencing article quote patterns, and tests use realistic fixtures based on those structures.

Final review:
- Files changed: `scrape_quotes.py`, `supabase/migrations/20260602_quotes.sql`, `tests/test_scrape_quotes.py`, `tasks/todo.md`.
- Behavior changed: new quote scraper parses official FIE/USA/British-style news pages for short attributed excerpts, conservatively links speakers to `fs_fencers`, dedupes by quote hash, preserves language, records blocked source stubs, and stores run state/logging metadata.
- Verification: red focused test run failed 8/8 before implementation; `./.venv/bin/python -m pytest tests/test_scrape_quotes.py -v` passed 8/8 after implementation; `./.venv/bin/python -m py_compile scrape_quotes.py` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` collected 1757 items but stopped during collection with unrelated missing imports: `dedupe_headshots` and `compute_junior_conversion`.
- Wiki-Brain: attempted to update `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace News Scraper.md` and `/Users/plernghomhual/Documents/Brain/log.md`; write was rejected because out-of-workspace approval is currently blocked by the usage-limit gate.
- Remaining risks: live shell probe could not be completed due environment network approval limits; press-conference transcript pages without public static endpoints are recorded as blocked stubs rather than scraped.

---

# Agent 146 Video Auto-Trimmer

## Plan
- [x] Read relevant lessons and current repo state.
- [x] Confirm target implementation/test/doc files are new in this checkout.
- [ ] Add failing metadata-first planner tests.
- [ ] Implement `video_trimmer.py` without video download or default processing.
- [ ] Document dry-run/manual review limitations.
- [ ] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `video_trimmer.py`, `tests/test_video_trimmer.py`, `docs/video_trimmer.md`.
- Keep scope narrow; do not edit `.github/workflows/`.
- Agent 139 video indexer is listed in the manifest but no implementation file exists in this checkout, so accept known bout timestamp data as caller-provided metadata.

---

# Agent 40 Morocco Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing federation scraper/common/season patterns.
- [x] Probe `frmescrime.ma` public ranking URLs and record coverage.
- [x] Add failing Morocco parser/fetch tests from probed or realistic fixtures.
- [x] Implement `scrape_fed_mar.py`.
- [ ] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files: `scrape_fed_mar.py`, `tests/test_fed_mar.py`.
- Keep scope narrow; do not edit `.github/workflows/`.

---

# Agent 1 Fencer Bio Columns

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect existing `fs_fencers` migrations and fencer profile update code.
- [x] Add failing migration SQL structure tests.
- [ ] Add idempotent nullable `fs_fencers` bio/birth columns migration.
- [ ] Run focused pytest verification and fix issues.
- [ ] Update Wiki-Brain/session log and record final review.

## Notes
- `20260601033334_wikipedia_bios.sql` already adds `birth_place text` and `bio_text text`, so the new migration must remain idempotent and additive only.
- `scrape_athlete_profiles.py` already probes `birth_date` as a DOB column candidate, so adding nullable `birth_date date` is compatible with the current profile update path.
- Keep changes scoped to `supabase/migrations/20260602_fencer_bio_columns.sql`, `tests/test_bio_columns.py`, and task/wiki memory. Do not edit `.github/workflows/`.

# Agent 22 Social Feed Aggregator

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing social-media scraper, migration, and test patterns.
- [x] Add failing tests for migration schema, dedupe/filtering, language handling, dry-run missing keys, and conservative linking.
- [x] Implement `aggregate_social_feed.py`.
- [x] Add `fs_social_feed` migration.
- [x] Run targeted pytest and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked by approval/quota gate after wiki page creation.

## Notes
- Target files are new: `aggregate_social_feed.py`, `supabase/migrations/20260602_social_feed.sql`, `tests/test_aggregate_social_feed.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Existing lesson applies: fencer matching is best-effort and must stay conservative.
- Final verification: `.venv/bin/python -m pytest tests/test_aggregate_social_feed.py -v` passed 7 tests; `.venv/bin/python -m py_compile aggregate_social_feed.py tests/test_aggregate_social_feed.py` exited 0.
- Remaining limitations: live provider probe, full pytest, pycache cleanup, and Wiki-Brain index/log update were blocked by DNS/tool timeout/approval quota constraints.

---

# Agent 157 Travel Cost Estimates

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect tournament/venue, migration, logger/state, and test patterns.
- [x] Add failing tests for cost calculation, missing venue/date skips, dry-run providers, currency conversion, and migration schema.
- [x] Implement `estimate_travel_costs.py` with deterministic default providers, caching, rate limits, and Supabase upsert.
- [x] Add `supabase/migrations/20260602_travel_costs.sql`.
- [x] Run targeted and full pytest verification.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files are new: `estimate_travel_costs.py`, `supabase/migrations/20260602_travel_costs.sql`, `tests/test_travel_costs.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Estimates must be approximate, dry-run safe by default, and not booking advice.

## Final Review
- Files changed: `estimate_travel_costs.py`, `supabase/migrations/20260602_travel_costs.sql`, `tests/test_travel_costs.py`, `tasks/todo.md`.
- Behavior changed: added dry-run/static competition travel cost estimates per tournament and origin, optional custom API provider, caching, rate limiting, currency conversion, skip handling, and Supabase upsert.
- Verification: `tests/test_travel_costs.py -v` passed; `py_compile estimate_travel_costs.py` passed; full `tests/ -v` ran with unrelated failures outside Agent 157 scope.
- Remaining risks: estimates are heuristic unless `TRAVEL_COST_PROVIDER=api` credentials are configured; full suite currently has unrelated failing tests from other modules.

---

# Agent 64 Japanese University Results

## Plan
- [x] Read relevant lessons and repo state.
- [x] Probe public Japanese student fencing source structure where available.
- [x] Add failing tests for parser fixtures, Unicode normalization, blocked sources, matching, logging, and state.
- [x] Implement `scrape_japanese_univ.py`.
- [x] Run `pytest tests/test_scrape_japanese_univ.py -v` and fix failures.
- [x] Attempt Wiki-Brain/session log update.

## Notes
- Keep changes scoped to `scrape_japanese_univ.py` and `tests/test_scrape_japanese_univ.py`.
- Shell network probe was blocked by sandbox DNS and escalation was rejected by the approval system; web probe confirmed Kanto Gakuren pages and public PDF shapes.
- Relevant lesson: fencer matching is best-effort, with unmatched rows logged and not blocked.
- Wiki-Brain write/log append was attempted but rejected by the platform usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable sandbox.

## Final Review
- Files changed: `scrape_japanese_univ.py`, `tests/test_scrape_japanese_univ.py`, `tasks/todo.md`.
- Behavior changed: added Japanese university fencing parser/scraper with CJK-preserving normalization, HTML/PDF-text table parsing, side-by-side weapon seed tables, team league rows, blocked-source stubs, best-effort fencer matching, Supabase tournament/result upserts, run logging, request delay, and scraper state.
- Verification: red test run failed 8/8 on missing module; focused `.venv/bin/python -m pytest tests/test_scrape_japanese_univ.py -v` passed 9/9; `.venv/bin/python -m py_compile scrape_japanese_univ.py tests/test_scrape_japanese_univ.py` passed.
- Remaining risks: shell live probe was blocked by sandbox DNS and escalation was rejected by the platform usage-limit gate, so source confirmation used web probe results. Wiki-Brain/log append and generated `.pyc` cleanup were also rejected by the same approval gate.

---

# Agent 150 Fencer Form Tracker

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing analytics, identity grouping, upsert, migration, and test patterns.
- [x] Add failing tests for scoring trends, fewer than five events, NULL ranks, migration shape, and idempotent upsert.
- [x] Implement `compute_form_tracker.py`.
- [x] Add `fs_fencer_form` migration.
- [x] Run targeted pytest and full test suite.
- [ ] Update Wiki-Brain/session log. Blocked: write to `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace-Scraper.md` was rejected by the approval/usage guard; no alternate write path was attempted.

## Notes
- Target files are new: `compute_form_tracker.py`, `supabase/migrations/20260602_form_tracker.sql`, `tests/test_form_tracker.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Use `fs_fencer_identities` when available; otherwise fall back to raw `fencer_id` grouping.
- Targeted red test failed as expected because `compute_form_tracker.py` and `20260602_form_tracker.sql` were absent.
- Targeted green test passed: `./.venv/bin/python -m pytest tests/test_form_tracker.py -v` -> 4 passed.
- Full suite run: `./.venv/bin/python -m pytest tests/ -v` -> 1841 passed, 57 failed, 1 warning. Failures are in unrelated in-progress modules outside Agent 150 files.
- Generated-cache cleanup blocker: pytest touched `__pycache__`/`tasks/.DS_Store`; sandbox blocked `git restore`, and approval escalation was rejected by the usage-limit approval system.

## Final Review
- Files changed: `compute_form_tracker.py`, `supabase/migrations/20260602_form_tracker.sql`, `tests/test_form_tracker.py`, `tasks/todo.md`.
- Behavior changed: computes identity-aware fencer/weapon recent form from the last five eligible individual competitions, with deterministic recency-weighted scoring and metadata explanation.
- Verification performed: targeted form tracker tests passed; full suite run completed with unrelated failures.
- Remaining risks: full suite is not green because of existing unrelated failures; cache artifact cleanup and Wiki-Brain/log writes were blocked by approval limits.

---

# Agent 111 Country Medal Heatmap

## Plan
- [x] Read relevant lessons and repo state.
- [x] Confirm frontend app files are currently absent and Agent 106 is manifest-only.
- [x] Inspect medal table and country/geocode dependency state.
- [x] Add failing frontend tests for country normalization, tooltip/dialog, missing coordinates, and empty data.
- [x] Implement `frontend/lib/countryMap.ts`.
- [x] Implement `frontend/components/CountryMedalHeatmap.tsx`.
- [x] Run relevant verification and document frontend runner blockers.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files are new. A concurrent frontend scaffold appeared during the session after the initial probe reported no `frontend/` directory.
- Agent 14/15 country medal geo/country code artifacts are not present; component must tolerate view-like rows directly.
- Keep changes scoped; do not edit `.github/workflows/`.

## Final Review
- Files changed for Agent 111: `frontend/components/CountryMedalHeatmap.tsx`, `frontend/lib/countryMap.ts`, `frontend/tests/country-medal-heatmap.test.tsx`, `tasks/todo.md`.
- Behavior changed: country medal rows normalize alpha-2/alpha-3/name/FIE/NOC variants, aggregate duplicate country rows, preserve unknown/disputed codes, and keep missing-coordinate countries in the fallback list/table.
- UI changed: `CountryMedalHeatmap` renders lightweight coordinate markers without adding a map dependency, exposes click/focus/hover medal details, and always renders an accessible medal totals table.
- Verification: Node countryMap smoke passed; `git diff --check` passed; focused Python medal/country tests passed 8/8; full `.venv/bin/python -m pytest tests/ -v` ran 1919 passed and 1 unrelated failure.
- Frontend verification blocker: `npm install --no-package-lock` failed with `ENOTEMPTY` cleanup errors; cleanup approval for generated `frontend/node_modules` was rejected by the approval usage-limit gate. Direct Vitest/TypeScript then failed because partial `node_modules` was missing `jsdom` and TypeScript lib files.
- Remaining unrelated full-suite failure: `tests/test_referee_assignments.py::test_parse_engarde_html_handles_adjacent_role_labels_without_semicolon`.
- Wiki-Brain blocker: required write to `/Users/plernghomhual/Documents/Brain` was rejected by the approval usage-limit gate; no indirect write attempted.

---

# Agent 127 Competition Calendar

## Plan
- [x] Read project lessons, current task state, and repository frontend availability.
- [x] Confirm frontend state: initially absent, then other-agent scaffold appeared with incomplete/corrupt `node_modules`.
- [x] Add failing TS/TSX tests for date normalization, event state/countdown, rendering, filters, empty/error states, and ICS links.
- [x] Implement `frontend/lib/competitionCalendar.ts`.
- [x] Implement `frontend/components/CompetitionCalendar.tsx`.
- [x] Run available verification and document runner limitations.
- [ ] Update Wiki-Brain/session log.

## Notes
- Keep changes scoped to `frontend/components/CompetitionCalendar.tsx`, `frontend/lib/competitionCalendar.ts`, `frontend/tests/competition-calendar.test.tsx`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Test file uses React server rendering plus pure library assertions so component render coverage can run in a Node environment once the frontend toolchain is healthy.
- Vitest status: `npm test -- tests/competition-calendar.test.tsx` reached Vitest after the other-agent frontend scaffold appeared, but failed because existing `node_modules` is incomplete/corrupt (`@testing-library/user-event` missing, then `jsdom` missing/corrupt). `npm install` in `frontend/` failed with `ENOTEMPTY` while cleaning untracked `node_modules/jsdom` and `node_modules/typescript`.
- Scoped TypeScript verification passed: `./node_modules/.bin/tsc --noEmit --jsx react-jsx --moduleResolution bundler --target ES2022 --module esnext --lib dom,dom.iterable,es2022 --skipLibCheck --strict components/CompetitionCalendar.tsx lib/competitionCalendar.ts tests/competition-calendar.test.tsx`.
- Runtime library probe passed: date-only normalization, active/upcoming/past state, countdown labels, filters, and `ics_url` alias handling.
- Static verification passed: `git diff --check -- frontend/components/CompetitionCalendar.tsx frontend/lib/competitionCalendar.ts frontend/tests/competition-calendar.test.tsx tasks/todo.md`.
- Full scraper verification: `.venv/bin/python -m pytest tests/ -v` failed outside this task with 46 failures in unrelated existing/untracked Python work; no failures point at the new frontend files.
- Wiki-Brain/session log update was attempted for `FenceSpace Competition Calendar`, but the outside-workspace write was rejected by the approval/usage gate.

## Final review
- Files changed: `frontend/components/CompetitionCalendar.tsx`, `frontend/lib/competitionCalendar.ts`, `frontend/tests/competition-calendar.test.tsx`, `tasks/todo.md`.
- Behavior changed: added a reusable competition calendar library and React component with local date-only all-day normalization, DST-safe day countdowns, upcoming/active/past state derivation, weapon/category/country filters, empty/error/loading states, responsive dense layout, and ICS URL support through `icsUrl`, `ics_url`, `calendarUrl`, and `calendar_url`.
- Verification performed: frontend Vitest attempted and blocked by incomplete/corrupt frontend dependency state; scoped TypeScript check passed; Node library probe passed; `git diff --check` passed; full Python suite failed on unrelated non-frontend work.
- Remaining risks: TSX tests are written and type-checked, but Vitest cannot execute the component test until the other-agent frontend scaffold has a clean `node_modules` install and JSX transform config.
- Wiki-Brain: required external page/index/log update was blocked by the environment approval/usage gate.

---

# Agent 32 Colombia Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing federation scraper, common writer, season, logger, and state patterns.
- [x] Probe Colombia federation URLs and record public ranking evidence.
- [x] Add failing parser/fetch/main tests for Colombia rankings behavior.
- [x] Implement `scrape_fed_col.py`.
- [x] Run targeted pytest and fix failures.
- [ ] Update Wiki-Brain/session log. Blocked: writing `/Users/plernghomhual/Documents/Brain` requires escalation, and the Codex approval usage gate rejected the scoped write request.

## Notes
- Target files are new: `scrape_fed_col.py`, `tests/test_fed_col.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Existing lessons apply: use normalized season strings and shared federation ranking writer.
- Probe evidence:
  - `https://esgrimacolombia.co/`, `http://esgrimacolombia.co/`, and `https://www.esgrimacolombia.co/` failed DNS from the sandboxed local probe.
  - Public ranking listing found at `GET https://sistemainfo.fedesgrimacolombia.com/rankings`, HTML.
  - Public ranking detail pages found at `GET https://sistemainfo.fedesgrimacolombia.com/rankings/<id>`, HTML.
  - Public combos mapped: 12/12 Senior/Junior individual Foil/Epee/Sabre Men/Women.
  - Working detail IDs from probe/search evidence: Foil M Senior 61, Foil W Senior 60, Epee M Senior 5, Epee W Senior 53, Sabre M Senior 57, Sabre W Senior 56, Foil M Junior 43, Foil W Junior 42, Epee M Junior 4, Epee W Junior 3, Sabre M Junior 41, Sabre W Junior 40.
  - Local read-only probe script could not complete with live network because sandbox DNS failed and the escalated network probe was rejected by the Codex approval usage gate.

## Final Review
- Files changed: `scrape_fed_col.py`, `tests/test_fed_col.py`, `tasks/todo.md`.
- Behavior changed: added Colombia federation scraper with Spanish HTML parser, public combo URL map, blocked/login/JS/404-safe fetch handling, current season normalization, run logging, and shared national rankings writer.
- Verification: red test run failed on missing `scrape_fed_col`; focused Colombia tests passed 12/12; `py_compile` passed; full suite currently has unrelated failures outside Colombia (`59 failed, 1815 passed, 17 errors`).
- Remaining risks: live local scraper validation and Wiki-Brain writes were blocked by network/filesystem approval limits; hardcoded public detail IDs may need refresh if the federation rotates ranking records.

---

# Agent 118 Data Syndication API

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing API, public views, API-key migration, and API test patterns.
- [x] Add failing tests for partner auth/scopes, pagination/filtering, private-field redaction, request logging, and rate limits.
- [x] Implement `api_syndication.py` as a read-only mountable FastAPI router/app.
- [x] Add `fs_syndication_keys` and sanitized request-log migration.
- [x] Document partner onboarding and sample requests.
- [x] Run targeted pytest and full test suite, fixing in-scope failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Keep changes scoped to `api_syndication.py`, `supabase/migrations/20260602_syndication_keys.sql`, `tests/test_api_syndication.py`, `docs/syndication_api.md`, plus this tracker.
- Existing API convention uses `X-API-Key`; syndication should also accept bearer tokens for partner tooling compatibility without logging secrets.
- Existing public views cover fencers and tournaments only; other resources need explicit select projections in code.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `api_syndication.py`, `supabase/migrations/20260602_syndication_keys.sql`, `tests/test_api_syndication.py`, `docs/syndication_api.md`, `tasks/todo.md`.
- Behavior changed: added read-only syndication endpoints under `/syndication/v1` for fencers, tournaments, rankings, results, and medal tables; partner keys are hashed, scoped, disabled-aware, per-key rate limited, last-used tracked, and request logged without secrets.
- Verification performed:
  - RED: `.venv/bin/python -m pytest tests/test_api_syndication.py -v` failed with `ModuleNotFoundError: No module named 'api_syndication'`.
  - RED: `.venv/bin/python -m pytest tests/test_api_syndication.py::test_syndication_migration_defines_partner_keys_and_secret_safe_logs -v` failed with missing `20260602_syndication_keys.sql`.
  - GREEN: `.venv/bin/python -m pytest tests/test_api_syndication.py -v` passed `8 passed, 1 warning`.
  - Full suite: `.venv/bin/python -m pytest tests/ -v` ran `1898` tests and failed with `47 failed, 1851 passed, 1 warning`; failures were outside the new syndication test file and include pre-existing unrelated modules such as anomalies, several scraper implementations, frontend contract, GraphQL, and transfer value.
- Remaining risks: rate limiting is in-memory per process, matching the existing API style but not globally distributed across multi-worker deployments; the full repo test suite is not green due unrelated failures outside this task scope.
- Wiki-Brain: attempted to create `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace Syndication API.md`, update `/Users/plernghomhual/Documents/Brain/wiki/index.md`, and append the session log, but the outside-workspace write was blocked by the tool approval reviewer with a usage-limit error. No bypass attempted.

---

# Agent 159 Technique Analysis

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing compute-job, migration, and test patterns.
- [ ] Write failing focused tests for deterministic insights, evidence metrics, low-data confidence, prohibited claims, migration schema, and Supabase upsert behavior.
- [x] Implement `compute_technique_analysis.py`.
- [x] Add `fs_fencer_technique_analysis` migration.
- [x] Run targeted and full pytest verification; fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files are new: `compute_technique_analysis.py`, `supabase/migrations/20260602_technique_analysis.sql`, `tests/test_technique_analysis.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Existing lesson applies: use `fs_fencer_identities` when present so duplicate fencer rows aggregate conservatively by person.

## Final Review
- Files changed: `compute_technique_analysis.py`, `supabase/migrations/20260602_technique_analysis.sql`, `tests/test_technique_analysis.py`, `tasks/todo.md`.
- Behavior changed: added deterministic, evidence-backed technique-style analysis rows from scored bout/result patterns; low-data rows emit no claims; LLM summaries remain disabled by default.
- Verification performed: red `tests/test_technique_analysis.py` failed before implementation; focused test file passed 6/6; related analytics set passed 15/15; `py_compile` passed for the new compute/test files; full `tests/ -v` currently has unrelated repository failures.
- Remaining risks: comeback rate is only derived when a source row explicitly includes comeback metadata; no point-by-point comeback inference is attempted from final scores. Wiki-Brain/session log update was blocked by approval usage-limit rejection.
- Public API probe evidence: sandbox DNS failed for Bluesky and Mastodon endpoints with `nodename nor servname provided`; escalated retry was rejected by the environment quota gate. Use injected realistic fixtures and missing-key dry-run behavior; do not fabricate production rows.

# Agent 48 Bulgaria Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing federation scraper, common writer, and season utility patterns.
- [x] Probe `bulfencing.com` ranking URLs and record public coverage.
- [x] Add failing Bulgaria parser/fetch tests with realistic Bulgarian ranking fixtures.
- [x] Implement `scrape_fed_bul.py` scoped to all 12 Senior/Junior weapon/gender combos.
- [x] Run `pytest tests/test_fed_bul.py -v` and focused syntax checks; fix failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Scope files: `scrape_fed_bul.py`, `tests/test_fed_bul.py`, `tasks/todo.md`, Wiki-Brain memory.
- Do not edit `.github/workflows/`.
- Existing lessons apply: normalize seasons, tolerate rotating/404 public ranking endpoints, and keep federation fencer matching best-effort.

## Probe Notes
- Working page: `GET https://bulfencing.com/sastezania/ranglista.html` returns `200 text/html` and embeds three public Google Sheets for Sabre, Epee, and Foil.
- Working data format: `GET https://docs.google.com/spreadsheets/d/e/<sheet_id>/pub?gid=<gid>&single=true&output=csv` returns `200 text/csv`.
- Public coverage: all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public.
- Source headers: Bulgarian Cyrillic `ФАМИЛИЯ`, `ИМЕ`, `КЛУБ`, `Точки`; some Google CSV responses need UTF-8 byte decoding instead of `requests.text`.

## Final Review
- Files changed: `scrape_fed_bul.py`, `tests/test_fed_bul.py`, `tasks/todo.md`.
- Behavior changed: added Bulgaria federation scraper using public Google Sheets CSV exports, Bulgarian CSV/HTML ranking parser, UTF-8 Cyrillic response decoding, guarded fetch handling for 404/network/login/JS/missing combos, `ScraperRunLogger`, `scraper_state`, and `fed_rankings_common` write flow.
- Verification: red focused run first failed 12/12 on missing `scrape_fed_bul`; UTF-8 regression failed before decode fix; focused `.venv/bin/python -m pytest tests/test_fed_bul.py -v` passes 13/13; `.venv/bin/python -m py_compile scrape_fed_bul.py tests/test_fed_bul.py` passes; live read-only parse returns 12/12 combos with 0 failures; adjacent `tests/test_fed_bul.py tests/test_fed_rankings_common.py -v` passes 18/18.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed from `/tmp/fed-bul-full-pytest.log` with 1917 passed, 2 unrelated failures, 1 warning. Failures: `tests/test_fed_srb.py::test_fetch_rankings_page_does_not_confuse_explicit_women_heading_for_men`, `tests/test_fencing_stores.py::test_parse_pbt_dealers_extracts_live_dealer_nodes`.
- Remaining risks: production write was not run to avoid accidental Supabase writes; Google published sheet IDs/gids can change if the federation republishes the ranking workbooks; full-suite failures are outside the Bulgaria scope; cleanup of two generated Bulgaria pyc files was blocked by the approval usage-limit gate.

# Agent 16 Ranking History Trajectory

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect ranking history, federation ranking, fencer identity schemas, and season utilities.
- [x] Add failing migration parser tests for columns, nullable points, normalized season support, unique key, indexes, and safe DDL.
- [x] Add `fs_ranking_history_trajectory` migration.
- [ ] Run targeted pytest and fix failures.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files are new: `supabase/migrations/20260602_ranking_trajectory.sql`, `tests/test_ranking_trajectory_schema.py`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Existing season lesson applies: persisted federation seasons should use normalized `YYYY-YYYY` text.

## Final Review
- Files changed: `supabase/migrations/20260602_ranking_trajectory.sql`, `tests/test_ranking_trajectory_schema.py`, `tasks/todo.md`.
- Behavior changed: added an idempotent `fs_ranking_history_trajectory` schema for normalized multi-source ranking trajectory rows keyed by fencer identity, source, season, weapon, gender, category, and trend window.
- Verification: RED run failed first because the migration was missing; post-migration `./.venv/bin/python -m pytest tests/test_ranking_trajectory_schema.py -v` passed 6/6; `git diff --check` passed for scoped files.
- Remaining risks: full `tests/ -v` was not run because the worktree contains many unrelated in-progress files/tests from other agents; this agent stayed scoped to the requested schema parser tests.
- Blocker: Wiki-Brain page/log write to `/Users/plernghomhual/Documents/Brain` was blocked by the escalation approval system due a usage-limit gate, so the required external memory update remains incomplete.

# Agent 47 Serbia Federation Scraper

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`, and nearby federation scraper/test patterns.
- [x] Probe `macesavez.rs` public ranking URLs and record response format plus combo coverage.
- [x] Write failing Serbia parser/fetch tests with realistic Serbian ranking fixtures.
- [x] Implement `scrape_fed_srb.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback compatibility.
- [x] Run focused verification and fix failures.
- [x] Write final review.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files: `scrape_fed_srb.py`, `tests/test_fed_srb.py`, plus this task tracker and Wiki-Brain memory.
- Do not edit `.github/workflows/`.
- `macesavez.rs` failed DNS resolution from the local probe; public search/direct browsing show the active official MSS site is `https://www.mss.org.rs/`.
- Working public URL: `GET https://www.mss.org.rs/rang-liste/`, server-rendered HTML with a public "Rang Liste MSS (26.04.2026)" download.
- Response/data format: HTML page that may expose HTML/PDF/Excel ranking package links; scraper converts Excel/PDF to text and parses Serbian Latin/Cyrillic headers.
- Public combo coverage could not be fully confirmed by local network script because escalation/network probing was blocked by the environment usage limiter. Scraper attempts all 12 combos and filters combo sections when present.

## Final Review
- Files changed: `scrape_fed_srb.py`, `tests/test_fed_srb.py`, `tasks/todo.md`.
- Behavior changed: new Serbia federation scraper attempts all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos, discovers the current MSS ranking download from `mss.org.rs/rang-liste/`, parses HTML/PDF-extracted/workbook-extracted ranking text with Serbian Latin/Cyrillic headers, preserves native-script names, skips DNS/DQ/summary/malformed rows, and exits 0 with stub logging when no scrapeable public rankings are available.
- Verification: red `pytest tests/test_fed_srb.py -v` first failed 12/12 with missing module; focused Serbia tests now pass 13/13; `py_compile scrape_fed_srb.py tests/test_fed_srb.py` passes; targeted federation regression `pytest tests/test_fed_srb.py tests/test_fed_rankings_common.py -v` passes 18/18.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed during collection before scraper tests due unrelated `ModuleNotFoundError: compute_junior_conversion` in `tests/test_junior_conversion.py`.
- Remaining risks: exact current MSS download payload and per-combo coverage were not downloadable from the local shell due blocked network escalation; parser/fetch tests use realistic fixtures based on the probed MSS ranking page and required Serbian headers.
- Blocker: Wiki-Brain/session-log writes to `/Users/plernghomhual/Documents/Brain` were rejected by the tool approval/usage limiter, so external project memory could not be updated in this run.
# Agent 36 Iran Federation Scraper (IRI)

## Plan
- [x] Read relevant lessons and existing federation scraper/shared helper patterns.
- [x] Probe `iranfencing.ir` for public ranking URL structure, response format, and combo coverage.
- [x] Add failing parser/fetch tests in `tests/test_fed_iri.py`.
- [x] Implement `scrape_fed_iri.py` with robust Farsi/RTL parsing and graceful blocked/no-data handling.
- [x] Run `pytest tests/test_fed_iri.py -v` and fix any failures.
- [ ] Update Wiki-Brain/session log and record final review.

## Notes
- Keep code changes scoped to `scrape_fed_iri.py` and `tests/test_fed_iri.py`.
- Use `season_utils.py`; do not edit `.github/workflows/`.
- Probe evidence: public indexed ranking pages use `GET /Athletes/Ranking/rankshow/{Weapon}-{Gender}-{Category}-I` and HTML tables with Farsi/RTL headers. Cadet examples were visible; exact Senior/Junior live fetches were blocked by local network/escalation limits, so implementation attempts all 12 and logs each failed combo.
- Red test run: `.venv/bin/python -m pytest tests/test_fed_iri.py -v` failed 15/15 with `ModuleNotFoundError: scrape_fed_iri`.
- Green test run: `.venv/bin/python -m pytest tests/test_fed_iri.py -v` passed 15/15.
- Compile check: `.venv/bin/python -m compileall scrape_fed_iri.py tests/test_fed_iri.py` passed.

## Final Review
- Files changed: `scrape_fed_iri.py`, `tests/test_fed_iri.py`, `tasks/todo.md`.
- Behavior changed: added Iran federation ranking scraper that parses Farsi HTML ranking tables, attempts all 12 Senior/Junior weapon/gender combos, writes rows through `fed_rankings_common`, and logs missing/blocked combos.
- Verification performed: targeted pytest and compile check.
- Remaining risk: exact Senior/Junior combo coverage was not live-verified from this environment because direct network probing was blocked.

---

# Agent 110 Career Timeline React Component

## Plan
- [x] Read relevant lessons and repo state.
- [x] Confirm requested career timeline target files are absent and the broader `frontend/` app is untracked.
- [x] Add failing typed timeline normalization and component render tests.
- [x] Implement `frontend/lib/careerTimeline.ts`.
- [x] Implement `frontend/components/CareerTimeline.tsx`.
- [x] Run focused frontend verification if tooling exists, plus repo pytest.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `frontend/components/CareerTimeline.tsx`, `frontend/lib/careerTimeline.ts`, `frontend/tests/career-timeline.test.tsx`.
- Keep changes scoped; do not edit `.github/workflows/`.
- Career/milestone backend tables are not present in this repo; use typed realistic fixtures and document required fields in code/test types.
- Red probe: `cd frontend && bun test tests/career-timeline.test.tsx` failed before implementation because `CareerTimeline` was missing.
- Focused frontend verification: `cd frontend && ./node_modules/.bin/vitest run --environment jsdom --pool=threads tests/career-timeline.test.tsx` passed 6/6.
- Targeted typecheck: `cd frontend && ./node_modules/.bin/tsc --ignoreConfig --noEmit --jsx react-jsx --module esnext --target ES2022 --moduleResolution bundler --lib dom,dom.iterable,es2022 --strict --skipLibCheck --esModuleInterop --types vitest/globals,@testing-library/jest-dom components/CareerTimeline.tsx lib/careerTimeline.ts tests/career-timeline.test.tsx` passed.
- Full frontend typecheck remains blocked by unrelated existing errors in `src/lib/api.ts` and `tests/h2h-page.test.tsx`; default Vitest fork pool hit a local jsdom worker-resolution issue, so focused verification used `--pool=threads`.
- Backend verification: `.venv/bin/python -m pytest tests/ -q` passed 1923 tests with one existing Starlette/httpx deprecation warning.
- Wiki-Brain/session log write to `/Users/plernghomhual/Documents/Brain` was attempted and rejected by the approval usage-limit gate, so no Brain page/log entry was written.

## Final Review
- Files changed: `frontend/components/CareerTimeline.tsx`, `frontend/lib/careerTimeline.ts`, `frontend/tests/career-timeline.test.tsx`, `tasks/todo.md`.
- Behavior changed: added typed career timeline normalization from career stats, milestones, medals, transfers, and longevity rows; renders season/year events, medals, ranking peaks, country changes, career spans, and milestones with weapon/category filters.
- Edge cases handled: sparse/empty input, unknown dates, duplicate season stats, non-integer season labels, global milestones under filters, and long careers via stacked list layout instead of absolute positioning.
- Verification performed: red probe failed before implementation; focused Vitest passed 6/6; targeted typecheck passed; backend pytest passed 1923/1923.
- Remaining risks: backend career/milestone table contracts are inferred from typed fixtures because live tables were not present in this repo; broader untracked frontend app has pre-existing type/test runner issues outside this scoped task; required outside-repo Wiki-Brain/session log update was blocked by the approval usage-limit gate.

---

# Agent 144 Second-Hand Equipment Marketplace

## Plan
- [x] Read relevant lessons and current repo state.
- [x] Confirm target files are new and inspect nearby scraper/test/migration patterns.
- [x] Probe public marketplace/search pages and record allowed source structure or blockers.
- [x] Write failing parser, classifier, PII minimization, dedupe/upsert, and migration tests.
- [x] Implement `scrape_secondhand_equipment.py`.
- [x] Add `supabase/migrations/20260602_secondhand_equipment.sql`.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_secondhand_equipment.py`, `supabase/migrations/20260602_secondhand_equipment.sql`, `tests/test_secondhand_equipment.py`.
- Do not edit `.github/workflows/`.
- Target source candidate from initial search: public eBay search/listing pages for used fencing equipment; skip any source that requires login or presents anti-bot blocking.
- Probe attempt: non-escalated read-only Python probe of eBay search/category URLs failed on sandbox DNS; escalation retry was blocked by the approval usage-limit gate. Web search shows public eBay search/category/listing pages for used fencing gear are indexed, so implementation uses conservative eBay HTML fixtures and treats live fetch failures as non-fatal.
- Red test run: `.venv/bin/python -m pytest tests/test_secondhand_equipment.py -v` failed 6/6 because the scraper module and migration were absent.
- Green test run: `.venv/bin/python -m pytest tests/test_secondhand_equipment.py -v` passed 6/6.
- Compile check: `.venv/bin/python -m py_compile scrape_secondhand_equipment.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` collected 1694 items and stopped on pre-existing collection errors for missing `dedupe_headshots` and `compute_junior_conversion`.
- Wiki-Brain update was attempted for `FenceSpace Second-Hand Equipment Scraper`, `index`, and `log.md`, but the Brain vault is outside the writable root and the approval usage-limit gate rejected the write.

## Final Review
- Files changed: `scrape_secondhand_equipment.py`, `supabase/migrations/20260602_secondhand_equipment.sql`, `tests/test_secondhand_equipment.py`, `tasks/todo.md`.
- Behavior changed: added public second-hand equipment scraper for eBay-style marketplace pages, PII-minimized seller metadata, conservative weapon/category classification, URL-hash dedupe fallback, and idempotent Supabase upsert into `fs_secondhand_equipment`.
- Verification performed: red focused tests failed 6/6 before implementation; green focused tests passed 6/6 after implementation and again after tracker updates; `py_compile` passed; full suite collection blocked by unrelated missing modules.
- Remaining risks: live eBay probe could not complete from this environment because DNS was sandboxed and escalation was rejected by the usage-limit gate; parser tests therefore use realistic public eBay HTML fixtures.

---

# Agent 151 Betting Odds Aggregator

## Plan
- [x] Read relevant lessons and repo state.
- [x] Inspect existing scraper, logger, state, migration, and test patterns.
- [x] Write failing betting odds parser/compliance tests.
- [x] Implement `scrape_betting_odds.py` as a compliance-gated informational-data scraper.
- [x] Add `fs_betting_odds` migration.
- [x] Run focused and full test verification; fix failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_betting_odds.py`, `supabase/migrations/20260602_betting_odds.sql`, `tests/test_betting_odds.py`.
- No approved live odds source is known at start; skip login-only, blocked, or legally unclear sources instead of scraping them.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_betting_odds.py`, `supabase/migrations/20260602_betting_odds.sql`, `tests/test_betting_odds.py`, `tasks/todo.md`.
- Behavior changed: added a compliance-gated odds aggregator that only probes sources explicitly marked public-permitted with confirmed terms, parses public JSON odds fixtures into informational rows, flags stale markets, skips missing/withdrawn/blocked/login-only markets, stores source/region caveats in metadata, and avoids betting advice output.
- Verification performed: red focused tests failed 7/7 before implementation; focused `tests/test_betting_odds.py -v` passed 8/8; `py_compile scrape_betting_odds.py` passed; full `tests/ -v` reported 1677 passed and 128 failed, with betting odds tests passing and failures in unrelated pre-existing areas.
- Remaining risks: no live odds source was enabled because source legality/compliance remains unresolved; cache cleanup/restore was blocked by the approval usage-limit gate after test runs touched tracked `__pycache__` artifacts.

---

# Agent 158 Fencing History Timeline

## Plan
- [x] Read relevant lessons and current project state.
- [x] Confirm target scraper, migration, and test files are absent.
- [x] Probe public FIE/federation/history source URLs and record viable structures.
- [x] Add failing migration, parser, citation, dedupe, conflict, and upsert tests.
- [x] Implement `scrape_fencing_history.py` with conservative cited timeline rows.
- [x] Add `supabase/migrations/20260602_fencing_history.sql`.
- [x] Run focused and full verification; fix any failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_fencing_history.py`, `supabase/migrations/20260602_fencing_history.sql`, `tests/test_fencing_history.py`.
- Keep changes scoped and do not edit `.github/workflows/`.
- Probe note: local `curl -I` source probes failed with sandbox DNS errors; escalation was rejected by the approval system due a usage-limit gate. Use browser/search evidence and conservative cited fixtures.

## Final Review
- Files changed: `scrape_fencing_history.py`, `tests/test_fencing_history.py`, `supabase/migrations/20260602_fencing_history.sql`, `tasks/todo.md`.
- Behavior changed: added cited fencing history timeline rows for governance, rule, equipment, and scoring/timing milestones; conservative parsers for FIE, Britannica, USA Fencing, and sabre timing fixtures; citation validation; dedupe with conflicting-date evidence metadata; frontend-ready sorted rows; Supabase upsert by `category,event_year,title`.
- Verification: red focused run failed 9/9 before implementation due missing module/migration; focused `tests/test_fencing_history.py -v` passed 9/9; `tests/test_fencing_history.py -q` passed 9/9; `py_compile scrape_fencing_history.py` passed; no-network row summary produced 13 cited rows with all four categories and epee-date conflict metadata.
- Full suite: latest `.venv/bin/python -m pytest tests/ -v` run completed 1918 tests: 1916 passed, 2 failed, 1 warning. Failures were unrelated: `tests/test_export_bigquery.py::test_resume_continues_from_saved_offset_and_chunk_number` and `tests/test_fencing_stores.py::test_parse_pbt_dealers_extracts_live_dealer_nodes`.
- Remaining risks: shell source probes, CRG impact review, and the required outside-repo Wiki-Brain/log write were blocked by approval usage limits; live remote parsing is best-effort and curated cited seeds provide stable output when public sources are prose/PDF or network is unavailable.

---

# Agent 128 Federation Overview Pages

## Plan
- [x] Read relevant lessons and current project/frontend state.
- [x] Identify country analytics/ranking data shapes and later confirm the untracked frontend app/test runner is present under `frontend/`.
- [x] Add failing federation overview tests for country-code mapping, complete/sparse/empty data, and chart/table fallback.
- [x] Implement `frontend/pages/federations/[code].tsx` and `frontend/components/FederationOverview.tsx`.
- [x] Run focused frontend-source verification and the project pytest suite; fix failures in scope.
- [ ] Update Wiki-Brain/session log and record final review.

## Notes
- Target files: `frontend/pages/federations/[code].tsx`, `frontend/components/FederationOverview.tsx`, `frontend/tests/federation-overview.test.tsx`.
- Keep additions scoped to requested frontend files; the broader untracked frontend app and many unrelated repo changes are not part of this task.
- Do not edit `.github/workflows/`.

## Final review
- Files changed: `frontend/pages/federations/[code].tsx`, `frontend/components/FederationOverview.tsx`, `frontend/tests/federation-overview.test.tsx`, `tasks/todo.md`.
- Behavior changed: added a federation overview route and reusable component with public Supabase REST reads, canonical `fs_country_codes` resolution plus FIE/Olympic alias fallback, top fencers, depth metrics/charts, weapon/category split charts, medal/club/ranking/tournament sections, table fallback, empty/sparse states, and sanitized public fields only.
- Verification: focused `cd frontend && npm test -- --run tests/federation-overview.test.tsx` passed 7/7; focused `.venv/bin/python -m pytest tests/test_country_codes.py tests/test_country_analytics.py -v` passed 13/13; `git diff --check -- ...` passed; secret/metadata scan of new production frontend files returned 0 matches.
- Broader checks: `cd frontend && npm test -- --run` failed in unrelated existing tests (`h2h-page` uses `jest`, `country-medal-heatmap` ambiguous duplicate cell, `routes` mock missing parser exports); `.venv/bin/python -m pytest tests/ -v` failed 63 unrelated existing tests across pending agents; `cd frontend && npx tsc --noEmit --pretty false` is blocked by existing `tsconfig.json` `baseUrl` deprecation.
- Remaining risks: live Supabase table schemas were not probed; route fetches handle missing tables/config by rendering empty-safe data; required outside-repo Wiki-Brain/session log write was blocked by the approval usage-limit gate.

---

# Agent 94 Referee Match Assignments

## Plan
- [x] Read relevant lessons and current project state.
- [x] Confirm target scraper, migration, and test files are absent.
- [x] Probe public FIE/Engarde/live-result evidence and record blockers.
- [x] Write failing migration, parser, blocked-source, dedupe/upsert, and runner tests.
- [x] Implement `scrape_referee_assignments.py`.
- [x] Add `supabase/migrations/20260602_referee_assignments.sql`.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_referee_assignments.py`, `supabase/migrations/20260602_referee_assignments.sql`, `tests/test_referee_assignments.py`.
- Public evidence found: FIE result XML spec includes bout `<Arbitre REF="..." Role="P|V">`; public Engarde pages can expose `Piste` and `Referee:` in tableau HTML; FIE-linked Fencing Time Live tournament pages can be login-gated and must be skipped as blocked.
- Shell network probe failed due sandbox DNS restriction, and escalation was unavailable due tool quota; use public web evidence and fixtures instead of forcing live access.
- Do not edit `.github/workflows/`.
- Red verification: `.venv/bin/python -m pytest tests/test_referee_assignments.py -v` failed 8/8 because the scraper module and migration were absent.
- Green verification: `.venv/bin/python -m pytest tests/test_referee_assignments.py -v` passed 8/8.
- Compile check: `.venv/bin/python -m py_compile scrape_referee_assignments.py` passed.

---

# Agent 9 Bracket Data Pipeline

## Plan
- [x] Read relevant lessons and current project state.
- [x] Inspect `fs_bouts`, `fs_results`, bracket/front-end context, run logger, and state patterns.
- [x] Add failing fixture and mocked-Supabase tests for complete brackets, byes, duplicates, partial data, multiple events, upsert conflicts, and skipped logging.
- [x] Implement `compute_brackets.py` with deterministic event grouping, evidence checks, idempotent rows, run logging, and safe no-credential CLI behavior.
- [x] Run `./.venv/bin/python -m pytest tests/test_compute_brackets.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review. Blocked: Wiki-Brain write to `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace-Scraper.md` was rejected by the tool approval/usage guard, so no alternate write path was attempted.

## Notes
- Target files `compute_brackets.py` and `tests/test_compute_brackets.py` are absent at session start.
- Local migrations do not currently include `20260602_tournament_brackets.sql`; target schema is based on Agent 8's requested table contract.
- `fs_bouts` rows expose only tournament, fencer IDs, scores, round, and winner; ordering, piste, byes, source, and event keys must come from metadata when present or be left null/derived conservatively.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `compute_brackets.py`, `tests/test_compute_brackets.py`, `tasks/todo.md`.
- Behavior changed: Added a conservative bracket compute pipeline that reads bouts/results/tournaments, derives rows only from elimination bouts with explicit order evidence, preserves fencer IDs, scores, winners, byes, seeds, piste, event metadata, and source metadata, groups multiple events through bout/result metadata, upserts idempotently into `fs_tournament_brackets`, records run state/log counts, and returns a safe no-credential summary from `main()`.
- Verification performed: red targeted run failed on missing `compute_brackets`; accounting red test failed before the failed-vs-skipped fix; `./.venv/bin/python -m pytest tests/test_compute_brackets.py -v` passed 9/9; `./.venv/bin/python -m py_compile compute_brackets.py tests/test_compute_brackets.py` passed; `git diff --check` passed; full `./.venv/bin/python -m pytest tests/ -q` ran 1760 passed, 73 failed, 8 warnings.
- Remaining risks: Local `supabase/migrations/20260602_tournament_brackets.sql` is missing and full-suite `tests/test_tournament_brackets_schema.py` fails for that Agent 8-owned schema; current persisted `fs_bouts` schema lacks order/piste/bye/source metadata, so many production tournaments may be skipped until source rows carry that evidence. Wiki-Brain/session log update was blocked by the approval/usage guard when writing outside the repo.

---

# Agent 142 Forum Scraper Fencing.net and Reddit

## Plan
- [x] Read relevant lessons and current project state.
- [x] Confirm target scraper, migration, and test files are absent.
- [ ] Probe public Reddit and fencing.net URL/robots behavior and record evidence.
- [ ] Write failing parser, Reddit no-key/API, PII minimization, fencer ambiguity, upsert, and migration tests.
- [ ] Implement `scrape_fencing_forums.py` with public-source safeguards, hashed authors, conservative fencer matching, run logging, and state tracking.
- [ ] Add `supabase/migrations/20260602_forum_discussions.sql`.
- [ ] Run focused and full verification; fix any failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_fencing_forums.py`, `supabase/migrations/20260602_forum_discussions.sql`, `tests/test_fencing_forums.py`.
- Use Reddit API only when credentials exist; otherwise use public JSON/RSS only if allowed and non-private.
- Fencing.net must be public-access only; blocked pages should be skipped with probe evidence.
- Hash or omit usernames and avoid storing unnecessary personal data.
- Do not edit `.github/workflows/`.

---

# Agent 57 Jamaica Federation Scraper

## Plan
- [x] Read relevant lessons and current project state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`, and nearby federation scraper/test patterns.
- [x] Probe Jamaica federation URLs and record public ranking-source evidence.
- [x] Write failing parser/fetch/stub tests for `scrape_fed_jam.py`.
- [x] Implement scoped Jamaica federation scraper/stub with 12 combo attempts, parser, run logging, and state logging.
- [x] Run focused verification and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_fed_jam.py`, `tests/test_fed_jam.py`, `tasks/todo.md`.
- Probe evidence: `jamaicafencing.com` could not be retrieved through available web fetch; shell DNS probe was blocked by sandbox and approval was unavailable. CFF lists the official federation site as `https://jamaicanfencing.org/`.
- `https://jamaicanfencing.org/` is public server-rendered HTML, but exposes only a contact/landing page; indexed searches found no ranking/results subpages.
- Implement as a documented stub that attempts all 12 standard Senior/Junior Men/Women Foil/Epee/Sabre combos and exits 0 when no scrapeable public rankings are found.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_fed_jam.py`, `tests/test_fed_jam.py`, `tasks/todo.md`.
- Behavior changed: new Jamaica federation scraper attempts all 12 standard combos, logs no-public-ranking failures cleanly, persists run metadata via `fs_scraper_state` when credentials are configured, and includes a robust HTML/text parser for future Rank/Name/Club/Points tables.
- Verification: red run failed first with missing `scrape_fed_jam`; `pytest tests/test_fed_jam.py -v` passed 14/14; `py_compile` passed; `pytest tests/test_fed_jam.py tests/test_fed_rankings_common.py -v` passed 19/19.
- Full suite note: `.venv/bin/python -m pytest tests/ -v` currently fails during collection before Jamaica tests due unrelated missing modules: `dedupe_headshots` and `compute_junior_conversion`.
- Remaining risks: direct shell network probing for `jamaicafencing.com` was unavailable in this sandbox, so probe evidence relies on available web/search results and CFF-listed official site context. No public Jamaica ranking source was found; data format is `stub` and working combos are 0/12.
- Wiki-Brain note: attempted to add `[[FenceSpace Jamaica Federation Scraper]]` and append the session log, but out-of-repo write approval was rejected by the Codex usage-limit gate. Do not bypass; retry after approvals are available.

---

# Agent 29 Tournament Detail API

## Plan
- [x] Read relevant lessons and current project state.
- [x] Inspect existing API, tournament, competition-detail, and test patterns.
- [ ] Add tests for complete details, partial/missing details, URL/date normalization, and invalid IDs.
- [ ] Implement `api/v1/tournament_details.py` as a scoped importable helper/router module.
- [ ] Run `./.venv/bin/python -m pytest tests/test_api_tournaments_details.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `api/v1/tournament_details.py`, `tests/test_api_tournaments_details.py`.
- The repo currently has top-level `api.py`, not an `api` package; avoid adding package `__init__.py` that would shadow `import api`.
- Do not edit `.github/workflows/` or shared router files.

---

# Agent 76 Elo Rating System

## Plan
- [x] Read relevant lessons and current project state.
- [x] Inspect `fs_bouts`, identity mapping, and analytics table patterns.
- [x] Write failing migration and algorithm tests for Elo table shape, deterministic math, chronological ordering, duplicate skips, safe skips, dry-run behavior, and empty input.
- [x] Implement `compute_elo.py` with identity-aware deterministic recompute, configurable K factors, dry-run support, run logging, and state updates.
- [x] Add `supabase/migrations/20260602_elo.sql`.
- [x] Run `./.venv/bin/python -m pytest tests/test_elo.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `compute_elo.py`, `supabase/migrations/20260602_elo.sql`, `tests/test_elo.py`, plus required task/wiki memory.
- `fs_fencer_identities` groups duplicate `fs_fencers` rows; Elo should collapse bout participants through that identity map where available.
- `fs_bouts` column usage is inconsistent across scrapers (`fencer_a`/`fencer_b` and some legacy `fencer_a_id`/`fencer_b_id` writers), so tests should cover row normalization.
- Team events must be skipped at tournament/event level; individual NCAA-style bouts that include team names in metadata remain valid if both fencers and scores are present.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `compute_elo.py`, `supabase/migrations/20260602_elo.sql`, `tests/test_elo.py`, `tasks/todo.md`.
- Behavior changed: added deterministic identity-aware Elo recompute from completed individual bouts, with chronological replay, configurable K factors, duplicate/incomplete/team/missing-data skips, dry-run mode, state logging, and idempotent upsert into `fs_fencer_elo`.
- Verification: red focused run failed first because `compute_elo.py` and `20260602_elo.sql` were missing; post-implementation `./.venv/bin/python -m pytest tests/test_elo.py -v` passed 7/7; `./.venv/bin/python -m py_compile compute_elo.py tests/test_elo.py` passed.
- Broad check: `./.venv/bin/python -m pytest tests/ -v` was attempted but hit the tool RPC timeout after 120 seconds, so no full-suite result was available.
- Remaining risks: live Supabase recompute was not run because this task must not rewrite production data; real `fs_bouts` schemas may vary, so the loader uses select fallbacks and normalizes both `fencer_a`/`fencer_b` and `fencer_a_id`/`fencer_b_id`.

---

# Agent 61 National Championships Scraper

## Plan
- [x] Read relevant lessons, current task state, result-scraper patterns, run logger, and scraper state helpers.
- [x] Confirm `scrape_national_champs.py` and `tests/test_scrape_national_champs.py` are absent at session start.
- [x] Probe representative top-20 national championship public sources and record parsable/blocked evidence.
- [x] Write failing tests for HTML/PDF/XLS parsers, fencer matching by FIE ID and name+country, unmatched logging, and blocked-source stubs.
- [x] Implement `scrape_national_champs.py` with top-20 country configs, conservative parsers, result/tournament adapter, run logging, and state tracking.
- [x] Run `./.venv/bin/python -m pytest tests/test_scrape_national_champs.py -v` and fix failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_national_champs.py`, `tests/test_scrape_national_champs.py`, `tasks/todo.md`.
- Follow lesson: match fencers by FIE ID first, then name+country; log unmatched rows instead of dropping rows or silently creating null-fencer results.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_national_champs.py`, `tests/test_scrape_national_champs.py`, `tasks/todo.md`.
- Behavior changed: added top-20 national championship source config with parser/stub status, HTML/PDF/XLS parser support, tournament/result writing adapter, FIE ID then name+country fencer matching, explicit unmatched-row logging, run logging, and scraper state.
- Verification: red focused run failed 7/7 on missing module; focused `./.venv/bin/python -m pytest tests/test_scrape_national_champs.py -v` passed 7/7 after implementation; `./.venv/bin/python -m py_compile scrape_national_champs.py tests/test_scrape_national_champs.py` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` failed outside this task scope with 59 failures and 17 errors; national championship tests passed in that run.
- Probe risk: local shell DNS probe failed and escalation was blocked by environment usage-limit gate; public web probes and config evidence were used for source shapes. Several top-20 countries remain intentional stubs until a stable public full-standings source is confirmed.
- Wiki-Brain note: attempted to add `[[FenceSpace National Championships Scraper]]` and append the session log, but out-of-repo write approval was rejected by the Codex usage-limit gate. Do not bypass; retry after approvals are available.

---

# Agent 13 Career Milestone Detection Engine

## Plan
- [x] Read relevant lessons and current project state.
- [x] Inspect schemas/patterns for results, rankings, stats, identities, run logging, state, and upserts.
- [x] Add failing fixture and mocked-Supabase tests for evidence-backed milestones, identity dedupe, ambiguous skips, and idempotent upsert keys.
- [x] Implement `compute_career_milestones.py` with deterministic row generation, canonical identity grouping, safe empty-data behavior, run logging, and state updates.
- [x] Run `./.venv/bin/python -m pytest tests/test_compute_career_milestones.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files `compute_career_milestones.py` and `tests/test_compute_career_milestones.py` are absent at session start.
- Local migration `supabase/migrations/20260602_career_milestones.sql` is present as untracked work from another agent; this task reads its contract but does not edit it.
- Supabase SQL introspection was blocked by platform usage limit; do not keep retrying live schema queries this session.
- Wiki-Brain update was attempted but blocked by the escalation reviewer due platform usage limit; do not attempt an indirect outside-workspace write workaround this session.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `compute_career_milestones.py`, `tests/test_compute_career_milestones.py`, `tasks/todo.md`.
- Behavior changed: Added deterministic career milestone generation for supported result/ranking/stat/longevity evidence, canonical identity dedupe, idempotent upsert batching, run logging, and state updates.
- Verification: `./.venv/bin/python -m pytest tests/test_compute_career_milestones.py -v` passed 7 tests; `./.venv/bin/python -m pytest tests/test_compute_career_milestones.py tests/test_career_milestones_schema.py -v` passed 12 tests; full `./.venv/bin/python -m pytest tests/ -v` completed with 1,889 passed and 18 unrelated failures outside Agent 13.
- Remaining risks: Full-suite failures are pre-existing/unrelated in other agents' files; live Supabase SQL introspection and required Wiki-Brain outside-workspace write were unavailable due platform usage limit.

---

# Agent 68 Historical Olympedia Results

## Plan
- [x] Read relevant lessons and current project state.
- [x] Confirm target scraper and test files are absent.
- [x] Attempt live Olympedia probe and record sandbox blocker.
- [x] Write failing fixture tests for individual, team, historical country, tie/missing-rank, Unicode names, fencer matching, and resume state.
- [x] Implement `scrape_historical_olympedia.py` with stable Olympedia URL discovery, parsing, conservative matching, state, and run logging.
- [x] Run `./.venv/bin/python -m pytest tests/test_scrape_historical_olympedia.py -v` and fix failures.
- [x] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_historical_olympedia.py`, `tests/test_scrape_historical_olympedia.py`, `tasks/todo.md`.
- Live shell probe to `https://www.olympedia.org/sports/FEN` failed with sandbox DNS; escalation was rejected by the environment. Use existing repo probe evidence for stable public Olympedia URL shapes: `/sports/FEN`, `/editions/{id}/sports/FEN`, and `/results/{id}`.
- Keep crawl pre-2000 only and do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_historical_olympedia.py`, `tests/test_scrape_historical_olympedia.py`, `tasks/todo.md`.
- Behavior changed: added a pre-2000 Olympedia fencing crawler using `/sports/FEN` to discover edition sport pages and `/results/{id}` result tables; parses event classification, individual/team rows, historical country codes, ties with blank repeated ranks, Unicode names, and source URLs.
- Identity safety: individual results are inserted only after explicit FIE ID, Olympedia athlete ID, or unique canonical name+country match; unmatched or ambiguous individual rows are written to `historical_olympedia_unmatched.log`; team rows are allowed with `metadata.team=true` and no fencer ID.
- State/logging: uses `get_state`/`set_state` `done_source_ids` to skip completed event result pages on resume and `ScraperRunLogger("scrape_historical_olympedia").start().complete(written, failed, skipped)`.
- Verification: initial targeted test run failed on missing module; after implementation, `./.venv/bin/python -m pytest tests/test_scrape_historical_olympedia.py -v` passed 7/7; `./.venv/bin/python -m py_compile scrape_historical_olympedia.py` passed; `git diff --check` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` collected 1757 items but stopped during collection with unrelated missing modules `dedupe_headshots` and `compute_junior_conversion`.
- Remaining risks: live Olympedia shell probe could not be completed in this environment due DNS sandboxing and rejected escalation; implementation is based on existing repo probe notes and deterministic fixtures. CRG post-change detection and Wiki-Brain/log writes were rejected by the environment usage limit.


---

# Agent 2 Wikipedia Bio Scraper Expansion

## Plan
- [x] Read project lessons/todo and inspect existing Wikipedia bio scraper, fencer upsert patterns, Wikidata helpers, and prior wiki notes.
- [x] Probe Wikipedia/Wikidata API shape or record blocker evidence.
- [x] Write failing tests in `tests/test_wikipedia_bios.py` for summary parsing, Wikidata birth claims, trusted matching, ambiguous skips, and dry-run processing.
- [x] Implement robust `bio`, `birth_date`, `birth_place`, and `bio_source` enrichment without loose-name guessing or lower-quality overwrites.
- [x] Run focused verification for `tests/test_wikipedia_bios.py` and relevant existing scraper tests.
- [x] Add final review notes with files changed, behavior, verification, and residual risks.

## Probe Notes
- Sandbox probe to `https://www.wikidata.org/wiki/Special:EntityData/Q1657692.json` failed with DNS resolution error.
- Escalated retry was unavailable because the approval tool reported a usage-limit rejection.
- Implementation uses realistic fixtures matching the existing EntityData and Wikipedia REST PageSummary structures already covered in `tests/test_scrape_wikipedia_bios.py`.

## Final Review
- Files changed: `scrape_wikipedia_bios.py`, `tests/test_wikipedia_bios.py`, `tasks/todo.md`.
- Behavior changed: Wikipedia bio enrichment now selects new `bio`, `birth_date`, `birth_place`, and `bio_source` fields; parses PageSummary summaries; parses Wikidata P569/P19 birth claims with full-date-only ISO normalization; fetches birth-place labels; matches by Wikidata ID first, then explicit Wikipedia URL/title fields only; skips loose name-only matches; logs skipped fencers; and preserves richer existing bio text unless the same source has a clearly longer replacement.
- Compatibility: legacy `bio_text`, `wikipedia_url`, infobox `birth_place`, `nickname`, `height`, and `weight` updates still work when those columns are selected.
- Verification: red run first failed 6/8 in `tests/test_wikipedia_bios.py`; after implementation `.venv/bin/python -m pytest tests/test_wikipedia_bios.py -v` passed 9/9, `.venv/bin/python -m pytest tests/test_scrape_wikipedia_bios.py -v` passed 9/9, combined `.venv/bin/python -m pytest tests/test_bio_columns.py tests/test_wikipedia_bios.py tests/test_scrape_wikipedia_bios.py -v` passed 22/22, `py_compile` passed, and `git diff --check -- scrape_wikipedia_bios.py tests/test_wikipedia_bios.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran 1885 tests with 1809 passed, 59 failed, and 17 errors in unrelated in-progress areas including aggregate videos, federation CRO/SVK, GraphQL, frontend contract, fencing stores, tournament brackets migration, nationality history, and product/video scrapers.
- Remaining risks: live Wikipedia/Wikidata probe could not complete in this sandbox; fixtures are realistic and based on existing project response shapes. Wikidata birth-place labels may be city-level only unless Wikipedia infobox/summary provides richer place text.

---

# Agent 147 OBS Live Scoring Overlay

## Plan
- [x] Read lessons and current task state without overwriting other agent sections.
- [x] Inspect live-result watcher, API/test patterns, and existing overlay/WebSocket state.
- [x] Write failing endpoint and static overlay smoke tests.
- [x] Implement `obs_overlay_server.py` read-only live-score endpoint.
- [x] Implement minimal `frontend/obs-overlay/` browser-source assets with no credentials.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review. Blocked: platform approval/usage gate rejected writes to `/Users/plernghomhual/Documents/Brain`.

## Notes
- Scope: `obs_overlay_server.py`, `frontend/obs-overlay/`, `tests/test_obs_overlay_server.py`, `tasks/todo.md`, and Wiki-Brain memory.
- Live source is existing `watch_live_results.py` output: `fs_tournaments`, `fs_results`, and `fs_bouts`.
- `ws_server.py` / `tests/test_ws_server.py` were absent during initial inspection; untracked versions appeared later from other work. The OBS endpoint remains standalone and read-only.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed for this task: `obs_overlay_server.py`, `frontend/obs-overlay/index.html`, `frontend/obs-overlay/styles.css`, `frontend/obs-overlay/overlay.js`, `tests/test_obs_overlay_server.py`, `tasks/todo.md`.
- Behavior changed: added `/overlay/live-score` FastAPI endpoint with active/no-active/error payloads, validated `tournament_id`/`event_id`/`token` selection, per-client rate limiting, short cache headers, and static `/obs-overlay/` serving.
- Behavior changed: added a credential-free OBS browser-source overlay that forwards only selection params, polls the endpoint, and visibly renders live, no-active, and disconnected states.
- Verification performed: red `tests/test_obs_overlay_server.py -v` failed on missing module/assets before implementation; focused `tests/test_obs_overlay_server.py tests/test_live_results.py -v` passed 10/10 with one existing Starlette/httpx warning; `py_compile obs_overlay_server.py` passed; static mount smoke via FastAPI TestClient returned 200 for `/obs-overlay/`, `styles.css`, and `overlay.js`.
- Full suite: `.venv/bin/python -m pytest tests/ -v` collected 1909 tests, with 1900 passed and 9 failed in unrelated pre-existing/untracked agent areas (`tests/test_fencing_stores.py`, `tests/test_scrape_allstar_uhlmann.py`, `tests/test_scrape_competition_details.py`, `tests/test_training_facilities.py`).
- Remaining risks: live localhost rendered Browser QA was blocked because the in-app browser backend was unavailable and sandbox binding/fetch to `127.0.0.1:8765` was not permitted; endpoint behavior is verified through TestClient rather than a real OBS browser source. Wiki-Brain page/log update was also blocked by the platform approval/usage gate for writes outside the workspace.

---

# Agent 43 — Ireland Federation Scraper

## Plan
- [x] Read relevant lessons, current task state, graph context, and existing federation scraper patterns.
- [x] Probe `irishfencing.net`, current Fencing Ireland pages, Ophardt, and public Google Sheets endpoints or record blocker evidence.
- [x] Write failing Ireland parser/fetch tests from probed Google Sheets-style fixtures.
- [x] Implement `scrape_fed_irl.py` with public senior Google Sheets support, robust parser, failed/skipped combo tracking, run logging, and state updates.
- [x] Run `./.venv/bin/python -m pytest tests/test_fed_irl.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Probe Notes
- Browser/web probe found current federation pages under `https://www.fencingireland.net/`; the site menu links Senior Rankings to public Google Sheet `1iZdJ_GfFRx61_qwvYa5Ck9dTKN3lM852zfDSf2Cvw-g`.
- Public Google Sheets view exposes Senior Rankings 2025-2026 with headers `Rank | Fencer | Club | Points` and sample senior rows including accented Irish names.
- The `https://www.fencingireland.net/cadet-and-junior/` page did not expose public Junior ranking links in the rendered HTML probe.
- Local shell probe was blocked by sandbox DNS for `irishfencing.net`, `fencingireland.net`, `fencing.ophardt.online`, and `docs.google.com`; escalated retry was unavailable because the approval tool reported a usage-limit rejection.
- Implement all 12 standard combo attempts; expect senior Google Sheets combos to be available and junior combos to fail closed until a durable public junior source is found.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed: `scrape_fed_irl.py`, `tests/test_fed_irl.py`, `tasks/todo.md`.
- Behavior changed: added Ireland federation scraper using the public Fencing Ireland Google Sheets XLSX export, robust table/text parsing, 12-combo attempts, failed/skipped combo metadata, run logging, scraper state, and shared `fed_rankings_common.write_rankings()`.
- Verification: red run failed with missing `scrape_fed_irl`; `./.venv/bin/python -m pytest tests/test_fed_irl.py -v` passed 14/14; `./.venv/bin/python -m py_compile scrape_fed_irl.py tests/test_fed_irl.py` passed; `./.venv/bin/python -m pytest tests/test_fed_irl.py tests/test_fed_rankings_common.py -v` passed 19/19; full `./.venv/bin/python -m pytest tests/ -v` failed with 27 unrelated failures and 1872 passes.
- Remaining risks: local live network probe was blocked by sandbox DNS and escalation quota, so public Google Sheets export behavior is covered by browser evidence plus realistic XLSX fixtures; Junior public ranking source was not visible and is currently skipped when no matching worksheet is present; actual senior worksheet titles may need reprobe if Fencing Ireland renames tabs unexpectedly.

---

# Agent 131 Absolute Fencing Product Catalog Scraper

## Plan
- [x] Read relevant lessons, current task state, repo memory, and nearby product/equipment scraper patterns.
- [x] Probe Absolute Fencing URL structure or record blocker evidence.
- [x] Write failing migration, parser, normalization, upsert, and no-network dry-run tests.
- [x] Implement scoped `scrape_absolutefencing.py` parser, crawler, normalization, idempotent upsert, run logging, and scraper state handling.
- [x] Add `fs_products` migration with source/source_id conflict key and product fields.
- [x] Run focused tests and full `tests/` suite; fix verification failures.
- [x] Final review: files changed, behavior changed, verification performed, remaining risks.

## Probe Notes
- Probe script attempted `https://absolute-fencing.com/robots.txt`, `https://www.absolute-fencing.com/robots.txt`, `https://www.absolutefencinggear.com/robots.txt`, and `https://www.absolutefencinggear.com/uniforms/lame/foil`.
- Sandbox DNS failed for all hosts. Required escalated retry was rejected by the environment usage limit.
- Implementation will use the repo's existing Absolute Fencing Magento selectors and realistic listing/detail fixtures, with explicit dry-run/no-network tests.

## Final Review
- Files changed for this task: `scrape_absolutefencing.py`, `supabase/migrations/20260602_products.sql`, `tests/test_scrape_absolutefencing.py`, `tasks/todo.md`.
- Behavior changed: added Absolute Fencing product catalog parsing for Magento listing/detail pages, price/stock/category/weapon normalization, SKU-or-slug source IDs, source/source_id dedupe, detail 404 fallback, dry-run mode, robots-aware request policy, rate limiting, `ScraperRunLogger`, and `scraper_state` incremental tracking.
- Verification: red focused tests failed before implementation; `./.venv/bin/python -m pytest tests/test_scrape_absolutefencing.py tests/test_scrape_leonpaul.py::test_products_migration_defines_shared_schema_for_catalog_scrapers -v` passed 9/9; summarized full `./.venv/bin/python -m pytest tests/ -q --tb=short` failed with 10 unrelated failures, 1905 passes, and no Absolute Fencing failures.
- Remaining risks: live site probe was blocked by sandbox DNS and escalation usage limit, so parser coverage uses realistic Magento fixtures plus existing repo Absolute Fencing selectors; default category URLs may need reprobe if Absolute Fencing changes paths.

---

# Agent 134 Fencing.net Product Scraper + Reviews

## Plan
- [x] Read relevant lessons, current task state, and adjacent equipment review scraper/test patterns.
- [x] Confirm target files are absent and review existing `fs_equipment_reviews` schema.
- [x] Probe Fencing.net availability or record blocker evidence.
- [x] Write failing product/review parser, private page, and dedupe/hash tests.
- [x] Implement `scrape_fencingnet_products.py` with public-only parsing, product/review upserts, state, and run logging.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scrape_fencingnet_products.py`, `tests/test_scrape_fencingnet_products.py`, `tasks/todo.md`.
- `fs_equipment_reviews` exists with one row per URL and `metadata jsonb`; no local `fs_products` migration/table definition was found in this checkout.
- Public web search found current Fencing.net review pages including `/reviews/adidas-pro-combi-fencing-glove/`, `/reviews/nike-air-zoom-fencing-shoes/`, older review posts such as `/482/bf-blue-fie-epee-blade-review/`, and `/forums/` stating forums are retired and only converted public articles remain.
- Local probe script failed with sandbox DNS resolution for `fencing.net`; escalated retry was rejected by the approval usage-limit gate. Use realistic fixtures based on public WordPress review/forum page structure and search snippets.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fencingnet_products.py`, `tests/test_scrape_fencingnet_products.py`, `tasks/todo.md`.
- Behavior changed: added Fencing.net product/review scraper that parses public WordPress and forum-style review pages, rejects private/login-only pages, infers brand/category/rating/count/date/snippets, dedupes review snippets by stable source URL hash, upserts product rows to `fs_products` by `source,source_id`, upserts review snippet rows to `fs_equipment_reviews` by `url`, and records run state/logs.
- Verification: red focused run failed 4/4 because `scrape_fencingnet_products.py` was missing; edge red run failed on public forum pages with login widgets; focused green run passed 5/5; `py_compile scrape_fencingnet_products.py tests/test_scrape_fencingnet_products.py` passed; full `./.venv/bin/python -m pytest tests/ -v` completed with 1903 passed, 10 failed, 1 warning.
- Full-suite failures were outside Agent 134 target files: `tests/test_compute_fencer_stats.py`, `tests/test_scrape_allstar_uhlmann.py`, `tests/test_scrape_blue_gauntlet_products.py`, `tests/test_scrape_bucs.py`, and `tests/test_scrape_veterans.py`.
- Remaining risks: live Fencing.net HTML probe could not be completed from this shell because DNS was sandboxed and escalation was rejected; fixtures are realistic and based on public search evidence plus common WordPress review/forum markup. Local checkout now contains Agent 131 `fs_products` migration work, but the table was not in the tracked baseline when this task started.

---

# Agent 152 Youth Talent Identification

## Plan
- [x] Read project lessons/todo and inspect adjacent analytics, ranking, run logger, state, migration, and test patterns.
- [x] Write failing tests for youth scoring patterns, sparse/unknown category handling, no sensitive output, explanation content, compute/upsert flow, and migration DDL.
- [x] Implement `compute_youth_talent.py` using public competition/ranking rows only, with conservative labels and low-confidence flags.
- [x] Add `supabase/migrations/20260602_youth_talent.sql` with privacy-conscious columns and interpretation comments.
- [x] Run focused and full verification; record unrelated full-suite failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `compute_youth_talent.py`, `tests/test_youth_talent.py`, `supabase/migrations/20260602_youth_talent.sql`, and `tasks/todo.md`.
- Uses category/age-band evidence from public result/ranking rows. It does not read or persist exact birthdates.
- Labels are non-deterministic: `early-career outlier`, `monitor with more public results`, or `insufficient public evidence`.
- Sparse data and uncertain age/category evidence are recorded through `low_confidence_flags`.
- Red test run: `.venv/bin/python -m pytest tests/test_youth_talent.py -v` failed 6/6 because module and migration were missing.
- Focused green run: `.venv/bin/python -m pytest tests/test_youth_talent.py -v` passed 6/6.
- Syntax check: `.venv/bin/python -m py_compile compute_youth_talent.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed with 1815 passed, 59 failed, 17 errors in unrelated existing/generated tests outside the target files.
- Test-generated `__pycache__` cleanup was blocked because restoring tracked cache files requires `.git/index.lock`; escalation was rejected by the environment usage-limit gate.
- Do not edit `.github/workflows/`.

---

# Agent 18 Country Codes Single Source

## Plan
- [x] Read relevant lessons, current task state, graph/wiki context, and existing country-code mappings.
- [x] Write failing tests for helper lookup behavior, SQL table shape, seed aliases, historical codes, and duplicate-code protection.
- [x] Implement `scripts/country_codes.py` with deterministic lookup helpers and shared seed data.
- [x] Add `supabase/migrations/20260602_country_codes.sql` with `fs_country_codes` schema and idempotent seed upserts.
- [x] Run `./.venv/bin/python -m pytest tests/test_country_codes.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Notes
- Target files: `scripts/country_codes.py`, `supabase/migrations/20260602_country_codes.sql`, `tests/test_country_codes.py`.
- Existing country-code sources include federation `COUNTRY` constants, `scrape_commonwealth.py` aliases, `scrape_south_american_games.py` aliases, `scrape_engarde.py` IOC mapping, `compute_transfers.py` display-name aliases, and historical CAC codes.
- Production `information_schema` country-column query was blocked by the Codex approval/usage gate, so active database-country coverage is derived from repo scrapers/maps instead of live distinct database values.
- Do not edit `.github/workflows/`.

## Final Review
- Files changed for Agent 18: `scripts/country_codes.py`, `supabase/migrations/20260602_country_codes.sql`, `tests/test_country_codes.py`, `tasks/todo.md`.
- Behavior changed: added a migration-backed `fs_country_codes` single source with 127 active/common/historical fencing country rows, SQL upsert seeding, aliases, computed flag emoji, and Python helpers for alpha2/alpha3/Olympic/FIE/name lookups.
- Verification: red run failed with missing helper/migration; `./.venv/bin/python -m pytest tests/test_country_codes.py -v` passed 9/9; `./.venv/bin/python -m py_compile scripts/country_codes.py` passed; `git diff --check -- scripts/country_codes.py supabase/migrations/20260602_country_codes.sql tests/test_country_codes.py tasks/todo.md` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` completed from the temp log with 1851 passed, 46 failed, and 1 warning; failures were unrelated existing/in-progress test areas and did not include `tests/test_country_codes.py`.
- Remaining risks: production distinct-country SQL query, CRG impact check, and Wiki-Brain/session-log write were blocked by the approval/usage gate; live database coverage was inferred from repo scrapers/maps rather than queried directly.

---

# Agent 92 Fencer Family Relationships

## Plan
- [x] Read relevant lessons, current task state, CRG summary, and existing Wikidata/identity enrichment patterns.
- [ ] Write failing migration and Wikidata family fixture tests.
- [ ] Implement `enrich_family.py` with public Wikidata family claim parsing, exact Wikidata-ID matching, identity expansion, and idempotent upserts.
- [ ] Add `supabase/migrations/20260602_family.sql` for `fs_fencer_family_relationships`.
- [ ] Run `./.venv/bin/python -m pytest tests/test_enrich_family.py -v` and fix failures.
- [ ] Final review: files changed, behavior changed, verification, and residual risks.

## Notes
- Target files are new in this checkout: `enrich_family.py`, `tests/test_enrich_family.py`, and `supabase/migrations/20260602_family.sql`.
- Family enrichment must link related fencers only by exact public Wikidata IDs. Name-only related-person data is kept as unlinked metadata and ambiguous matches are skipped.
# Agent 79 — Upset Tracker

## Plan
- [x] Read relevant lessons, current task state, graph/wiki context, and adjacent compute/bracket patterns.
- [x] Write failing upset algorithm and migration shape tests first.
- [x] Implement deterministic upset row generation from bracket seeds, pre-event rank evidence, results, and tournaments.
- [x] Add `fs_upsets` migration without dropping or rewriting production data.
- [x] Run `./.venv/bin/python -m pytest tests/test_upsets.py -v` and fix failures.
- [ ] Update Wiki-Brain/session log.
- [x] Final review.

## Notes
- Keep code/schema/test scope to `compute_upsets.py`, `supabase/migrations/20260602_upsets.sql`, `tests/test_upsets.py`, and required task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Existing bracket compute uses `fs_tournament_brackets` with `seed_a`/`seed_b` and the conflict key `tournament_id,event_key,round_order,bout_order`.
- `fs_results.rank`/`placement` are final outcomes and must not be used as seed/rank evidence.

## Final Review
- Files changed: `compute_upsets.py`, `supabase/migrations/20260602_upsets.sql`, `tests/test_upsets.py`, `tasks/todo.md`.
- Behavior changed: added deterministic upset computation into `fs_upsets` using source bracket seeds first, pre-event ranking table evidence when seed evidence is absent, and final result placement only for medal outcome detection.
- Verification: red `tests/test_upsets.py -v` failed first on missing module/migration; focused `./.venv/bin/python -m pytest tests/test_upsets.py -v` passed 7/7; `./.venv/bin/python -m py_compile compute_upsets.py` passed; full `./.venv/bin/python -m pytest tests/ -v` had 26 unrelated failures and 1873 passes.
- Remaining risks: live Supabase execution was not run because credentials are not set in this shell; CRG post-change review and out-of-repo Wiki-Brain/session-log writes were blocked by the account usage gate.

---

# Agent 82 — Fantasy fencing scoring engine

## Plan
- [x] Read project lessons, current task state, and relevant compute/schema patterns.
- [x] Write failing fantasy scoring and migration tests first.
- [x] Implement deterministic, versioned fantasy scoring from results, bouts, tournaments, fencers, and optional identity rows.
- [x] Add fantasy points storage migration without dropping or rewriting production data.
- [x] Run focused fantasy verification and fix failures.
- [x] Update project memory / Wiki-Brain and final review.

## Notes
- Keep scope to `compute_fantasy_points.py`, `supabase/migrations/20260602_fantasy.sql`, `tests/test_fantasy.py`, and required task/wiki memory.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.
- Existing `fs_bouts` callers use both `fencer_a`/`fencer_b` and `fencer_a_id`/`fencer_b_id`; fantasy compute must support both.
- Use identity rows when available to group duplicate `fs_fencers` rows by canonical fencer.

## Final Review
- Files changed: `compute_fantasy_points.py`, `supabase/migrations/20260602_fantasy.sql`, `tests/test_fantasy.py`, `tasks/todo.md`.
- Behavior changed: Added versioned fantasy scoring with documented weights for participation, placements, medals, upsets, DNS/DQ penalties, team-event multiplier, and tier multipliers; writes `fs_fantasy_points` by fencer/tournament/season/rules_version.
- Verification performed: red focused tests first failed on missing module/migration; `.venv/bin/python -m pytest tests/test_fantasy.py -v` passed 8/8; `.venv/bin/python -m py_compile compute_fantasy_points.py` passed; `git diff --check -- compute_fantasy_points.py supabase/migrations/20260602_fantasy.sql tests/test_fantasy.py tasks/todo.md` passed with no output.
- Remaining risks: upset points depend on current `fs_fencers.world_rank`; if historical pre-event ranks are later added, the scorer should switch to that better evidence. Wiki-Brain update and `/Users/plernghomhual/Documents/Brain/log.md` append were attempted but blocked by the escalation usage-limit approval gate because the Brain vault is outside the writable sandbox.

---

# Agent 37 — Kazakhstan Federation Scraper

## Plan
- [x] Read relevant lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, `season_utils.py`, and nearby federation scraper/test patterns.
- [x] Probe `fencing.kz`, official `kazfencing.kz`/`kazfencing.com`, ranking/search paths, WP API paths, posts, attachments, and uploads directories.
- [x] Write failing Kazakhstan parser/fetch/main tests with realistic Kazakh/Russian fixtures.
- [x] Implement `scrape_fed_kaz.py` as a documented stub-compatible parser/fetcher using `fed_rankings_common`, `ScraperRunLogger`, and `scraper_state`.
- [x] Run focused verification and fix failures.
- [x] Final review: files changed, behavior changed, verification performed, remaining risks.

## Probe Notes
- Requested probe host `https://fencing.kz/` returns `200 text/html` for a Karaganda meat shop (`Мясной Павильон Караганда`), not the fencing federation. Ranking/result/API paths such as `/ranking`, `/rankings`, `/rating`, `/рейтинги`, `/results`, `/api`, and `/api/rankings` return `404`.
- Kazakhstan NOC lists `www.kazfencing.com` and SportQory lists `kazfencing.kz`; `https://kazfencing.com/` redirects to `https://kazfencing.kz/`.
- `https://kazfencing.kz/` is public HTML for the National Fencing Federation of Kazakhstan. `/?page_id=488` (`Наши результаты`) and search pages such as `/?s=рейтинг` are public HTML, but sampled result posts expose prose/images only, with no ranking tables and no PDF/XLS/CSV ranking links.
- Direct ranking slugs on `kazfencing.kz` (`/ranking`, `/rankings`, `/rating`, `/rejting`, `/рейтинги`, `/results`) return `404`; `/wp-json` and `wp-json/wp/v2/*` return `404`; uploads directory listings return `403`.
- Public Senior/Junior Foil/Epee/Sabre Men/Women ranking combos found: `0/12`. Current implementation should attempt all 12 standard combos, record no-public-ranking failures, and exit 0.

## Final Review
- Files changed: `scrape_fed_kaz.py`, `tests/test_fed_kaz.py`, `tasks/todo.md`.
- Behavior changed: added Kazakhstan federation scraper as a documented 0/12 public-combo stub with a future-ready Kazakh/Russian HTML/delimited ranking parser, fetch handling for missing/404/network/blocked/login/JS-only pages, `ScraperRunLogger`, `scraper_state`, shared row building, and 12-combo iteration.
- Verification performed: red focused run failed 17/17 on missing `scrape_fed_kaz`; focused `.venv/bin/python -m pytest tests/test_fed_kaz.py -v` passed 17/17; `.venv/bin/python -m py_compile scrape_fed_kaz.py tests/test_fed_kaz.py` passed; `.venv/bin/python scrape_fed_kaz.py` exited 0 with `combos_working=0/12`; full `.venv/bin/python -m pytest tests/ -v` passed all Kazakhstan tests but failed overall with unrelated existing/in-progress failures (`57 failed, 1842 passed, 1 warning`).
- Remaining risks: no durable public Kazakhstan national ranking table/file/API was found; if `kazfencing.kz` later publishes one, add confirmed URLs to `PUBLIC_RANKING_URLS`. Full-suite cleanup of generated artifacts was not performed because the required destructive cleanup approval was rejected by the platform usage gate.

# Agent 58 — Cyprus Federation Scraper

## Plan
- [x] Read relevant lessons, current task state, British scraper, shared ranking helpers, and season utilities.
- [x] Probe Cyprus federation URLs and record evidence.
- [x] Write failing Cyprus parser/fetch tests first.
- [x] Implement `scrape_fed_cyp.py` with public PDF discovery/extraction, parser, fetch, run logging, and 12-combo iteration.
- [x] Run `./.venv/bin/python -m pytest tests/test_fed_cyp.py -v` and fix failures.
- [x] Final review: files changed, behavior changed, verification, remaining risks.

## Probe Notes
- Requested probe host: `https://cyprusfencing.com` and `https://www.cyprusfencing.com`; local sandbox DNS failed. Required escalated retry was rejected by the environment usage-limit gate.
- Public web probe found current federation host `https://fencing.org.cy/`, rankings page `https://fencing.org.cy/rankings/`, and linked PDF `https://fencing.org.cy/wp-content/uploads/Rankings-290126.pdf`.
- Working method/format from public web probe: `GET` rankings page; linked ranking asset is PDF. Parser fixtures will use realistic pdfplumber text plus bilingual Greek/English HTML table fallbacks.
- Public combo coverage observed from the rankings page appears partial and PDF-based; scraper must attempt all 12 standard Senior/Junior Foil/Epee/Sabre Men/Women combos and report missing combos.

## Final Review
- Files changed: `scrape_fed_cyp.py`, `tests/test_fed_cyp.py`, `tasks/todo.md`.
- Behavior changed: added Cyprus federation scraper with 12 standard Senior/Junior weapon/gender combos, browser-like headers, `fencing.org.cy/rankings/` PDF discovery, pdfplumber extraction, combo-section filtering, Greek/English HTML/PDF parser support, decimal comma parsing, skip-row handling, and run logging via `ScraperRunLogger("scrape_fed_cyp")`.
- Verification: red `./.venv/bin/python -m pytest tests/test_fed_cyp.py -v` failed 14/14 before implementation on missing module; after implementation the same command passed 14/14. `./.venv/bin/python -m py_compile scrape_fed_cyp.py tests/test_fed_cyp.py` passed.
- Remaining risks: local shell probe to Cyprus hosts was blocked by DNS sandboxing and escalation was rejected by the usage-limit gate; public web discovery confirmed the active site and PDF link, but live PDF text extraction was not re-run from this shell. CRG post-change detection and Wiki-Brain/log writes were also rejected by the same usage-limit gate.

---

# Agent 137 — Fencing Store Directory

## Plan
- [x] Read relevant lessons, current task state, CRG summary, and adjacent scraper/migration/test patterns.
- [x] Confirm target files are absent and identify product/vendor source dependency from Agents 131-136.
- [x] Probe public store/dealer URLs and record source structures.
- [x] Write failing migration, dealer parser, normalization/dedupe, no-geocoder, and upsert tests.
- [x] Implement `scrape_fencing_stores.py` with source parsers, optional geocoding, rate limiting, logging, and state tracking.
- [x] Add `supabase/migrations/20260602_fencing_stores.sql`.
- [x] Run focused and full verification; fix failures.
- [ ] Update Wiki-Brain/session log and final review.

## Probe Notes
- Target files are absent at session start: `scrape_fencing_stores.py`, `supabase/migrations/20260602_fencing_stores.sql`, `tests/test_fencing_stores.py`.
- Public probe sources returned 200: PBT dealer list, Uhlmann distributors, Absolute Fencing contact page, Blue Gauntlet contact page, Leon Paul contact page, and Allstar contact/showroom page.
- PBT page is grouped by country panels with dealer text blocks. Uhlmann page exposes distributor rows as list items. Retailer pages expose single physical location/contact blocks.
- Geocoding must be optional and disabled unless a key/service is configured; rows should store addresses without coordinates by default.
- Do not edit `.github/workflows/`; Agent 160 owns CI integration.

## Final Review
- Files changed: `scrape_fencing_stores.py`, `supabase/migrations/20260602_fencing_stores.sql`, `tests/test_fencing_stores.py`, `tasks/todo.md`.
- Behavior changed: added `fs_fencing_stores` schema with normalized `dedupe_key`; added scraper for PBT dealers, Uhlmann distributors, and single-store contact pages for Absolute Fencing, Blue Gauntlet, Leon Paul, and Allstar; geocoding is disabled unless `FENCING_STORES_GEOCODER_URL` is configured; rows retain address-only locations by default.
- Red tests: focused `tests/test_fencing_stores.py -v` first failed 6/6 due missing module/migration; live-shape PBT fixture failed before parser patch.
- Verification: focused `tests/test_fencing_stores.py -v` passed 7/7; `py_compile scrape_fencing_stores.py` passed; live no-write fake-Supabase dry run parsed 106 rows from 6 public sources with 0 failed, 0 skipped, 0 coordinate rows, and 6 logged missing-location rows; full `tests/ -v` passed 1922/1922 with one Starlette/httpx deprecation warning.
- Remaining risk: source pages may change markup; PBT exposes some dealers with incomplete location details, which are logged and stored only when enough dedupe/address data exists.
- Wiki-Brain blocker: writing `/Users/plernghomhual/Documents/Brain/wiki/FenceSpace Fencing Store Directory.md` and updating the Brain session log was rejected by the environment usage-limit approval gate, and policy disallowed retrying through another write path.

---

# Agent 3 Fencer Stats Table

## Final Review
- [x] Read project lessons and current task state.
- [x] Inspected fencer identity, bout, and analytics migration/test patterns.
- [x] Added red-first schema parser tests in `tests/test_fencer_stats_schema.py`.
- [x] Added `supabase/migrations/20260602_fencer_stats.sql`.
- [x] Verified focused tests pass.
- [x] Attempt Wiki-Brain/session log.

## Notes
- `fs_fencer_stats` keys by `fs_fencer_identities(id), weapon, category` to avoid duplicate `fs_fencers` rows per physical fencer.
- Migration is additive and non-destructive: no drops, truncates, deletes, or data rewrites.
- Red test run: `.venv/bin/python -m pytest tests/test_fencer_stats_schema.py -v` failed 5/5 because `20260602_fencer_stats.sql` did not exist.
- Green test run: `.venv/bin/python -m pytest tests/test_fencer_stats_schema.py -v` passed 5/5.
- Broader full-suite verification was intentionally not run because the working tree contains substantial unrelated WIP tests/scripts from other agents.

---

# Agent 136 — Blue Gauntlet Products

## Final Review
- [x] Read project lessons/current task state and inspected product schema dependency, existing product/equipment scraper patterns, rate limiter, run logger, and scraper state.
- [x] Probed Blue Gauntlet via browser/web and attempted local `.venv/bin/python` probe; local DNS was sandbox-blocked and escalated retry was rejected by the usage-limit gate.
- [x] Added red-first fixture tests for listing/detail parsing, sale price normalization, waiting-list/out-of-stock normalization, idempotent `fs_products` upsert, rate limiting, run logging, and state tracking.
- [x] Implemented `scrape_blue_gauntlet_products.py`.
- [x] Verified focused and full test suites.
- [ ] Wiki-Brain/session log update blocked by outside-repo write approval usage-limit gate.

## Notes
- Files changed: `scrape_blue_gauntlet_products.py`, `tests/test_scrape_blue_gauntlet_products.py`, `tasks/todo.md`.
- Behavior changed: Blue Gauntlet product rows now target shared `fs_products` with `source='blue_gauntlet'`, stable `source_id` from SKU/Part Number when present or URL product ID fallback, sale-aware USD price parsing, title-case weapon normalization matching Agent 131, detail description preserved in metadata, image/product URLs, stock status, rate-limited fetches, run logging, and `fs_scraper_state` last-run summary.
- Verification: red run failed 9/9 with missing module; focused Blue Gauntlet tests passed 10/10 after implementation and waiting-list fix; adjacent suite `tests/test_scrape_blue_gauntlet_products.py tests/test_rate_limiter.py tests/test_equipment_reviews.py -v` passed 27/27; full `.venv/bin/python -m pytest tests/ -v` passed 1922/1922 with 1 warning.
- Remaining risk: live local probe could not run because sandbox DNS blocked `blue-gauntlet.com` and escalation was unavailable; parser fixtures are based on browser/web-probed Shift4Shop page structure. Wiki-Brain outside-repo write was also blocked by the approval usage-limit gate.
- Wiki-Brain write/log append was attempted but blocked by the approval usage-limit gate because `/Users/plernghomhual/Documents/Brain` is outside the writable project root.

---

# Agent 149 Tournament Re-Simulator

## Final Review
- [x] Read relevant lessons and repo state.
- [x] Inspected Agent 8/9/76/149 prompts and existing result/analytics patterns.
- [x] Added red-first tests for seeded determinism, probability normalization, small direct-elimination bracket behavior, missing Elo fallback, and CLI JSON output.
- [x] Implemented `simulate_tournament.py` with pure Monte Carlo helpers plus read-only CLI JSON output.
- [x] Documented assumptions, data inputs, confidence levels, CLI usage, and limitations in `docs/tournament_simulation.md`.
- [x] Ran focused and broad verification.
- [ ] Update Wiki-Brain/session log.

## Notes
- Target files: `simulate_tournament.py`, `tests/test_simulate_tournament.py`, `docs/tournament_simulation.md`.
- Source result tables are not mutated. Historical bracket `winner_id` fields are ignored during simulation so actual outcomes are not replayed.
- `fs_fencer_elo` and `fs_tournament_brackets` may be absent in this checkout; CLI handles missing tables through warnings and lower-confidence fallback behavior.
- Verification:
  - Red run: `.venv/bin/python -m pytest tests/test_simulate_tournament.py -v` failed 5/5 with `ModuleNotFoundError: No module named 'simulate_tournament'`.
  - Green run: `.venv/bin/python -m pytest tests/test_simulate_tournament.py -v` passed 5/5.
  - Compile: `.venv/bin/python -m py_compile simulate_tournament.py` passed.
  - Full suite: `.venv/bin/python -m pytest tests/ -v` finished with 46 failed, 1851 passed, 1 warning; failures were outside `simulate_tournament.py` and `tests/test_simulate_tournament.py`.
- Remaining risk: Supabase-backed CLI quality depends on Agent 76 Elo and Agent 8/9 bracket table availability; missing data is documented and flagged in output.

---

# Agent 132 Leon Paul Product Catalog Scraper

## Final Review
- [x] Read relevant lessons, current task state, CRG/memory context, existing product/review scraper patterns, logger/state helpers, and shared product migration expectations.
- [x] Attempted live Leon Paul probe script; sandbox DNS failed and required escalation was rejected by the environment usage-limit gate.
- [x] Added red-first fixture tests for Magento listing cards, detail variants, price/currency normalization, missing-region-price fallback, state updates, and idempotent `fs_products` upsert payloads.
- [x] Implemented `scrape_leonpaul.py` using the shared `fs_products` table, source `leon_paul`, rate-limited fetches, detail-page enrichment, scraper state, and run logging.
- [x] Added/reused `supabase/migrations/20260602_products.sql` as the shared product schema because no tracked `fs_products` migration was present in this checkout.
- [x] Ran focused, compile, shared-migration, and full-suite verification.

## Notes
- Files changed for Agent 132: `scrape_leonpaul.py`, `tests/test_scrape_leonpaul.py`, `supabase/migrations/20260602_products.sql`, `tasks/todo.md`.
- Behavior changed: Leon Paul catalog rows parse name, source ID/SKU, category, inferred weapon, price, currency, image, URL, stock, and variant metadata, then upsert to `fs_products` on `source,source_id`.
- Missing detail/region prices do not crash the scrape; listing prices are retained when available and metadata records `detail_missing_price_reason`.
- Verification: red focused run failed 7/7 on missing module/migration; focused Leon Paul tests pass 7/7; Leon Paul plus Absolute shared migration checks pass 8/8; `py_compile scrape_leonpaul.py` passes; full `.venv/bin/python -m pytest tests/ -v` finishes with 13 unrelated failures and 1896 passes.
- Remaining risks: live Leon Paul page validation could not complete due sandbox DNS plus rejected escalation; fixtures are realistic Magento/Leon Paul shapes based on prior project probe memory and adjacent scraper fixtures.

---

# Agent 46 Croatia Federation Scraper (CRO)

## Final Review
- [x] Read relevant lessons and existing federation scraper/shared helper patterns.
- [x] Probed `hms.hr/rang-liste` and latest public HMS ranking media.
- [x] Added red-first parser/fetch tests in `tests/test_fed_cro.py`.
- [x] Implemented `scrape_fed_cro.py` with Croatian HTML/text/PDF extraction support and graceful missing-data handling.
- [x] Ran focused verification.
- [ ] Update Wiki-Brain/session log.

## Probe Notes
- Public index: `https://hms.hr/rang-liste`, GET, server-rendered HTML.
- Latest 2025/2026 ranking link on 2026-06-02: `https://v3-hms-master-uxhuxdpqnq-ew.a.run.app/media/221/463779/MediumSize/20260513-rang-hms-pdf.png/YAv9vjk7pjfsVeD.Eevz-BOCaQFupHlkDrgMlE119Y358~~221`.
- Media URL returns `application/pdf` with `%PDF-1.7` content despite `.png` path.
- Sampled PDF text exposes Croatian sections and columns: `Rg. Prezime`, `Ime`, `Klub`, `Bod. Zbroj`; implementation attempts all 12 required Senior/Junior Foil/Epee/Sabre Men/Women combos and logs missing sections.

## Notes
- Files changed: `scrape_fed_cro.py`, `tests/test_fed_cro.py`, `tasks/todo.md`.
- Behavior changed: Croatia HMS scraper discovers the latest public ranking PDF, extracts text once per run, parses Croatian ranking rows, writes via `fed_rankings_common.write_rankings()`, records state, and logs failed/skipped combos through `ScraperRunLogger`.
- Verification: red run failed with `ModuleNotFoundError: No module named 'scrape_fed_cro'`; final `.venv/bin/python -m pytest tests/test_fed_cro.py -v` passed 14/14; `.venv/bin/python -m py_compile scrape_fed_cro.py tests/test_fed_cro.py` passed; `git diff --check -- scrape_fed_cro.py tests/test_fed_cro.py tasks/todo.md` passed.
- Remaining risks: live full-PDF extraction is slow and full live combo extraction was not run because local read-only probe escalation was unavailable; parser tests use realistic fixtures based on probed public HMS PDF text and URL structure.
# Agent 25 Ranking Trajectory API — Final Review

- [x] Added `api/v1/fencer_ranking_trajectory.py` with standalone `router`, `validate_trajectory_params()`, and `build_ranking_trajectory_payload()`.
- [x] Added `tests/test_api_fencers_ranking_trajectory.py` covering season normalization/order, filters, empty history, invalid params, route fake-client behavior, and missing table fallback.
- [x] Verification: red focused run failed before implementation because the module was missing; green focused run passed 13/13.
- [x] Verification: `py_compile` passed; `git diff --check` passed; API/season regression run passed 36/36.
- [x] Full-suite signal: full `tests/ -v` completed with 1855 passed, 44 unrelated failures, 1 warning in other active agent areas.
- [ ] Wiki-Brain/session log write blocked: required write to `/Users/plernghomhual/Documents/Brain` was rejected by the approval usage-limit gate.
- [ ] Integration risk: central router wiring is intentionally left to the merge/integration agent; existing `api.py` is unchanged.

---

# Agent 67 IWAS Games — Final Review

- [x] Added `scrape_iwas_games.py` for IWAS/World Para Fencing games and satellite result imports/stubs.
- [x] Added `tests/test_scrape_iwas_games.py` with red-first coverage for source discovery, HTML/PDF parsing, missing data stubs, public-evidence override, matching, unmatched logging, and rate limiting.
- [x] Individual result rows now require explicit fencer matches by FIE ID or normalized name+country before insert; unmatched rows are logged/skipped.
- [x] Missing public result rows create deterministic `fs_tournaments` stubs with evidence metadata instead of invented results.
- [x] Verification: targeted IWAS games tests pass 9/9; adjacent `tests/test_scrape_iwas.py` passed 15/15; compile check passed; full suite had 29 unrelated failures outside this task.
- [ ] Live shell probe was blocked by sandbox DNS and rejected escalation usage limits; source URL evidence came from browser-accessible public pages.

---

# Agent 107 - GraphQL API wrapping existing REST + Supabase

## Final Review
- [x] Read relevant lessons, task state, prior API context, and existing REST API/auth/pagination patterns.
- [x] Checked installed GraphQL dependencies; no Strawberry/graphql-core/Ariadne/Graphene package is present in the Python 3.14 venv.
- [x] Added red-first GraphQL API tests for startup, schema snapshot, auth failure, mutation rejection, pagination, invalid filters, private-field rejection, and one happy path per core type.
- [x] Implemented a dependency-free read-only FastAPI GraphQL adapter under `graphql/` using existing Supabase sources and explicit field whitelists.
- [x] Added `docs/graphql.md` local startup notes, safety model, source table mapping, and example queries.
- [x] Added `docker-compose.yml` with a local `graphql-api` service.
- [x] Verification: `./.venv/bin/python -m py_compile graphql/app.py tests/test_graphql_api.py` passed; `./.venv/bin/python -m pytest tests/test_graphql_api.py -v` passed 18/18.
- [x] Full-suite signal: `./.venv/bin/python -m pytest tests/ -v` passed 1923/1923.
- [ ] Wiki-Brain/session log write blocked: required write to `/Users/plernghomhual/Documents/Brain` was rejected by the approval usage-limit gate.

## Notes
- Files changed for Agent 107: `graphql/__init__.py`, `graphql/app.py`, `tests/test_graphql_api.py`, `docs/graphql.md`, `docker-compose.yml`, `tasks/todo.md`.
- Behavior changed: standalone `graphql.app:app` exposes read-only fencers, fencer profiles, tournaments, results, rankings, H2H, country depth, news, and products through `POST /graphql`, `GET /graphql`, and `GET /graphql/schema`.
- Auth and rate limiting follow `api.py`: `X-API-Key`, env key support, `fs_api_keys` fallback, and shared rate-limit state.
- Resolvers select only requested public columns; private columns such as `metadata` are rejected.
- Remaining risks: Docker is unavailable in this environment, so `docker compose config` could not run; `news` depends on `fs_social_feed`, which may be absent until the social feed table/view is deployed; Wiki-Brain update must be retried after approval capacity is available.

---

# Agent 94 Referee Match Assignments

## Final Review
- [x] Read relevant lessons and current project state.
- [x] Confirmed target scraper, migration, and test files were absent.
- [x] Probed public evidence: FIE XML docs expose bout `<Arbitre REF="..." Role="P|V">`; Engarde HTML can expose `Piste ... Referee: ...`; FIE-linked Fencing Time Live pages can be login-gated and are skipped as blocked.
- [x] Added red-first tests for migration shape, FIE XML, Engarde HTML, adjacent role labels, API JSON, PDF text, blocked sources, source-key dedupe, runner state, and no `fs_referees` upsert from name-only rows.
- [x] Implemented `scrape_referee_assignments.py` with run logging, scraper state, rate limiting, public-content parsing, blocked-source tracking, and `fs_referee_assignments` upserts on `source_key`.
- [x] Added `supabase/migrations/20260602_referee_assignments.sql`.
- [x] Verification: `.venv/bin/python -m pytest tests/test_referee_assignments.py -v` passed 9/9; `.venv/bin/python -m py_compile scrape_referee_assignments.py` passed.

## Notes
- Files changed for Agent 94: `scrape_referee_assignments.py`, `supabase/migrations/20260602_referee_assignments.sql`, `tests/test_referee_assignments.py`, `tasks/todo.md`.
- Behavior changed: referee assignments are captured from public bout evidence without creating or linking name-only referee identities; ID-bearing rows store `referee_fie_id` / `referee_fie_license_id` when available.
- Compatibility: `bout_id` is `text` to avoid forcing a foreign key against uncertain existing `fs_bouts.id` type.
- Blocked/skipped checks: shell live probes and Wiki-Brain writes were blocked by sandbox/approval quota; full project suite attempt timed out in the tool host after 120s.

---

# Agent 133 — Allstar/Uhlmann Product Catalog Scraper

## Final Review
- [x] Read relevant lessons, task state, shared `fs_products` schema, and neighboring product scraper/test patterns.
- [x] Ran the required local public-catalog probe script; sandbox DNS failed for `allstar.de` and `uhlmann-fechtsport.com`, and the escalated retry was rejected by the environment usage gate.
- [x] Added red-first Shopware fixture tests for Allstar, Uhlmann, German category/weapon normalization, EUR prices, no-public-price rows, `fs_products` upsert, state tracking, and brand separation.
- [x] Implemented `scrape_allstar_uhlmann.py` with Allstar/Uhlmann listing configs, parser/detail enrichment, `source,source_id` upsert, rate limiting, run logging, and scraper state.
- [x] Verification: red focused tests failed 6/6 on missing module; focused tests passed 6/6; `py_compile` passed; `git diff --check` passed; full `.venv/bin/python -m pytest tests/ -v` passed 1922/1922 with 1 existing FastAPI warning.
- [x] Wiki-Brain update attempted for `[[FenceSpace Allstar Uhlmann Product Scraper]]` plus session log, but writing `/Users/plernghomhual/Documents/Brain` was rejected by the approval usage gate.

## Notes
- Files changed for Agent 133: `scrape_allstar_uhlmann.py`, `tests/test_scrape_allstar_uhlmann.py`, `tasks/todo.md`.
- Behavior changed: public Allstar rows write `source=allstar`, `brand=Allstar`; public Uhlmann rows write `source=uhlmann`, `brand=Uhlmann`; both use shared `fs_products`.
- Blocked/skipped checks: graph change review and Wiki-Brain write were rejected by the environment usage gate; live shell probe could not complete beyond sandbox DNS failure and rejected escalation, so parser fixtures are based on public web evidence plus realistic Shopware 6 structure.
