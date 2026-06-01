# Operation: Insane Fencing Database

## Active Work: Agent 69 — US College Fencing Scholarships

- [x] Read project lessons and current task state.
- [x] Inspect NCAA scraper, run logger, scraper state, test, and migration patterns.
- [x] Probe representative NCAA roster/staff pages and scholarship directory pages.
- [x] Write failing tests for directory parsing, roster/coaching extraction, row construction, Supabase upsert behavior, and migration DDL.
- [x] Implement `scrape_college_scholarships.py` with top-50 NCAA program discovery, official page probing, scholarship metadata, run logging, and state tracking.
- [x] Add `supabase/migrations/20260601_scholarships.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep scope to `scrape_college_scholarships.py`, `tests/test_scholarships.py`, `supabase/migrations/20260601_scholarships.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_college_scholarships.py`, `tests/test_scholarships.py`, `supabase/migrations/20260601_scholarships.sql`, `tasks/todo.md`.
- Behavior changed: new college scholarships scraper loads the current ScholarshipStats NCAA fencing program directory, filters top/all NCAA programs up to 50, derives scholarship slot limits, probes official athletics roster/coach/staff URLs, extracts roster size, weapons, head coach, and coach email where public, stores source details in metadata, upserts by `college_name`, and records run state/logging.
- Verification: red targeted test run first failed on missing module/migration; focused `tests/test_scholarships.py -v` now passes 9/9; `py_compile scrape_college_scholarships.py` passes; live directory count found 45 NCAA programs; live fake-Supabase dry run for first 3 programs wrote 3 rows with no database writes.
- Full suite: `.venv/bin/python -m pytest tests/ -v` collected 652 tests: 646 passed, 6 failed in pre-existing `tests/test_scrape_iwas.py` parser expectations.
- Remaining risks: full production population could not run because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are not set in this shell; official athletics sites can redirect or alter markup, so missing roster/coach fields are tracked in row metadata rather than blocking directory rows.

---

## Active Work: Agent 53 — Singapore Federation Scraper

- [x] Read project lessons, current task state, and existing federation scraper patterns.
- [x] Probe `fencing.org.sg` / `fencingsingapore.org.sg` ranking URLs and record public ranking coverage.
- [x] Write failing parser and fetch tests with realistic Singapore ranking fixtures.
- [x] Implement `scrape_fed_sgp.py` using public XLSX downloads, `fed_rankings_common`, `ScraperRunLogger`, and scraper state.
- [x] Run focused and relevant broader verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Probe notes:
- `https://fencing.org.sg/*` does not resolve.
- `https://www.fencingsingapore.org.sg/ranking-files/` is public and lists current 25-26 season ranking files.
- Current files are public XLSX downloads reached by GET from WordPress Download Manager `data-downloadurl` links.
- Latest probed files: Epee `25-26-Ranking-Epee_260524.xlsx`, Foil `25-26-Ranking-Foil_260517.xlsx`, Sabre `25-26-Ranking-Sabre_260504.xlsx`.
- Public sheets cover all 12 required Senior/Junior Men/Women Foil/Epee/Sabre combos. Cadet sheets also exist but are out of this task scope.
- `https://my.fencingsingapore.org.sg/showranks` is public HTML but 2025/2026 form queries returned empty current tables; older years returned HTML rows.

Final review:
- Files changed: `scrape_fed_sgp.py`, `tests/test_fed_sgp.py`, `tasks/todo.md`.
- Behavior changed: new Singapore federation scraper downloads current public XLSX ranking files, extracts the requested sheet for all 12 required combos, parses school/club and final ranking points, writes `sgp_fencing` rows, and records run state.
- Verification: red test run failed with missing `scrape_fed_sgp`; focused tests then passed 10/10; `py_compile` passed; `tests/test_fed_sgp.py tests/test_fed_rankings_common.py -v` passed 15/15; live no-credential scraper run parsed 12/12 combos with 0 failed and 0 skipped; full `tests/ -v` currently has 6 unrelated failures in `tests/test_scrape_iwas.py`.
- Remaining risks: local live run wrote 0 rows because Supabase credentials were not configured; WordPress download slugs include old dates even though page titles and downloaded filenames are current, so source changes may require updating `DOWNLOAD_PAGES`.

---

## Active Work: Agent 51 — Argentina Federation Scraper

- [x] Read project lessons, current task state, and existing federation scraper patterns.
- [x] Probe `esgrima.org.ar`, `esgrima-fae.com.ar`, and public FAE ranking PDF assets.
- [x] Write failing parser tests with realistic Argentina PDF/Spanish fixtures.
- [x] Implement `scrape_fed_arg.py` using direct FAE ranking PDFs, `fed_rankings_common`, `ScraperRunLogger`, and `season_utils.normalize_season()`.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `esgrima.org.ar` did not resolve from local probes. Current public FAE domain is `https://www.esgrima-fae.com.ar`.
- HTML routes such as `/ranking`, `/rankings`, `/clasificaciones`, and `/resultados` return a reCAPTCHA security page.
- Direct ranking PDFs under `/assets/pdf/ranking/{mayores,juveniles,cadetes}/` return `200 application/pdf`.
- All 12 requested Senior/Junior Foil/Epee/Sabre Men/Women PDF combos are public.
- Do not edit `.github/workflows/`; Agent 80 owns CI integration.

Final review:
- Files changed: `scrape_fed_arg.py`, `tests/test_fed_arg.py`, `tasks/todo.md`.
- Behavior changed: new Argentina federation scraper downloads direct public FAE ranking PDFs for all 12 required Senior/Junior weapon/gender combos, extracts text with `pdfplumber`, parses Spanish ranking rows with comma decimals and malformed source dates, and writes `arg_fencing` rows via `fed_rankings_common.write_rankings()`.
- Verification: red test run failed with missing `scrape_fed_arg`; focused tests then passed 8/8; `py_compile` passed; live no-write validation parsed 12/12 combos and 326 total rows; full `tests/ -v` currently has 6 unrelated failures in `tests/test_scrape_iwas.py`.
- Remaining risks: live run writes 0 rows without Supabase credentials; direct PDF URL pattern is stable in the current probe but could change if FAE renames ranking assets.

---

## Active Work: Agent 50 — Brazil Federation Scraper

- [x] Read relevant project lessons and current task state.
- [x] Inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and `season_utils.py`.
- [x] Probe CBE/Ophardt ranking URLs and record public combo coverage.
- [x] Write failing parser tests with realistic Portuguese/Ophardt fixtures.
- [x] Implement `scrape_fed_bra.py` using dynamic Ophardt link discovery, `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `https://cbesgrima.org.br/ranking/` is public HTML but contains no ranking table; it links to `https://fencing.ophardt.online/pt/search/rankings/163`.
- Ophardt `GET /pt/search/rankings/163?season=2026` returns HTML with public matrix links. Current season option `2026` was selected during probe.
- Senior IDs are public for all six gender/weapon combos: female Epee/Foil/Sabre `22355/22357/22359`, male Epee/Foil/Sabre `22356/22358/22360`.
- Junior maps to Ophardt `U20`; all six gender/weapon combos are public: female Epee/Foil/Sabre `22343/22345/22347`, male Epee/Foil/Sabre `22344/22346/22348`.
- Ranking detail pages redirect from `/pt/search/rankings/show/{id}` to `/pt/show-ranking/html/{id}` and return server-rendered HTML. Main ranking table class is `rankingbody fixedheader`; headers include `Rank`, `Pontos`, `Pontos transferidos`, `Nome`, `País`, `Clubes`, `Nasc`.
- Do not edit `.github/workflows/`.
- Changed files: `scrape_fed_bra.py`, `tests/test_fed_bra.py`, `tasks/todo.md`.
- Behavior changed: Brazil rankings now dynamically discover current Ophardt Senior/U20 links and parse server-rendered ranking tables with Portuguese headers, UTF-8 names, comma decimals, and summary/DNS/DQ row skipping.
- Verification: red tests failed first with missing `scrape_fed_bra`; `pytest tests/test_fed_bra.py -v` passed 6/6; `py_compile` passed; live no-write validation parsed 12/12 combos; no-database `scrape_fed_bra.py` run parsed 575 total rows with 0 failed combos.
- Full suite note: `pytest tests/ -v` currently fails outside Agent 50 scope (`23 failed, 604 passed`) in Singapore federation, Engarde, IWAS, and NCAA in-progress tests.
- Remaining risk: Ophardt matrix IDs are season-specific, so scraper discovers links from the current season index instead of hard-coding IDs.

---

## Active Work: Agent 47 — Finland Federation Scraper

- [x] Read relevant project lessons and existing federation scraper patterns.
- [x] Probe `fencing.fi`, `fencing-pentathlon.fi`, and Ophardt ranking endpoints.
- [x] Write failing parser tests with realistic Finnish/Ophardt ranking fixtures.
- [x] Implement `scrape_fed_fin.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused and relevant verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fencing.fi` ranking paths timed out from the live probe; current public federation ranking page is `https://www.fencing-pentathlon.fi/miekkailu/kilpailutoiminta/miekkailun_ranking/`.
- The current public page links to Ophardt `GET text/html` pages under `https://fencing.ophardt.online/en/search/rankings/11`.
- Public `Kansallinen ranking: 2025` pages are available for 10/12 Senior/U20 combos. Missing from current public listing: Junior Foil Men, Junior Foil Women.
- Old archived `show-ranking/html/*` links on federation archive pages return 404; use current `search/rankings/show/*` pages.
- No `.github/workflows/` edits for this agent.
- Changed files: `scrape_fed_fin.py`, `tests/test_fed_fin.py`.
- Verification: focused Finland tests passed (`8 passed`), py_compile passed, live read-only fetch parsed 10/12 combos with 0 failures.
- Full suite note: `pytest tests/ -v` currently fails outside Agent 47 scope (`23 failed, 604 passed`), including Singapore federation, Engarde, IWAS, and NCAA in-progress tests.

---

## Active Work: Agent 57 — Mediterranean Games

- [x] Read project lessons, current task state, and Olympics scraper pattern.
- [x] Probe Olympedia and official Mediterranean Games fencing sources.
- [x] Write failing tests for edition discovery, title classification, medal parsing, and missing result tables.
- [x] Implement `scrape_mediterranean_games.py` for structured public editions with skipped-edition warnings.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Olympedia manual list coverage is medalist-only/incomplete for full imports.
- Structured sources confirmed: Tarragona 2018 Bornan HTML final-rank pages and Oran 2022 Microplus PDF standings.
- Earlier public sources appear archival/prose-only from initial probes; skip with warning unless a structured source is confirmed.
- Do not edit `.github/workflows/`.

---

## Active Work: Agent 55 — Commonwealth Fencing Championships

- [x] Read relevant project lessons and current task state.
- [x] Inspect Olympics scraper/test pattern and source availability.
- [x] Probe Olympedia, Commonwealth Fencing, CFC2018, and CFC2022 public result structures.
- [x] Write failing parser/upsert tests with captured Commonwealth fixtures.
- [x] Implement `scrape_commonwealth.py` with official-source discovery, parsing, upserts, state, and run logging.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Olympedia exposes Olympic fencing only; no Commonwealth fencing result structure was found there.
- Official public data found: CFF 1998/2006 result PDFs and CFC2018 Australian Fencing final result tables.
- CFF 2010 and CFC2022 public pages expose event metadata/links but not static full ranking tables in the probed HTML.
- Do not edit `.github/workflows/`; Agent 80 owns CI integration.

Final review:
- Files changed: `scrape_commonwealth.py`, `tests/test_scrape_commonwealth.py`, `tasks/todo.md`.
- Behavior changed: adds Commonwealth scraper for official 1998/2006 PDFs and CFC2018 Australian Fencing final result tables, with edition discovery, event classification, tournament upserts, result writes, and FIE ID/name+country fencer matching.
- Verification: targeted tests passed; real-source smoke parsed 30 events; full `tests/ -q` still has unrelated IWAS parser test failures.
- Remaining risk: 2010/2022 public pages did not expose static full result rows during probe, so they are logged/probed but not inserted.

---

## Active Work: Agent 68 — Training Camps Directory

- [x] Read relevant project lessons and current task state.
- [x] Probe public camp sources and record viable URL structures.
- [x] Write failing tests for HTML/PDF camp parsing, deduplication, migration shape, and Supabase upsert behavior.
- [x] Add `supabase/migrations/20260601_camps.sql` defining `fs_training_camps`.
- [x] Implement `scrape_training_camps.py` with source fetch/parse, name+organizer+date-range dedupe, run logging, and state tracking.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `https://www.eurofencing.info/activities/camps` and known `getFile` links redirected to `fencing-efc.eu` 404 during the probe, so federation/PDF sources must be best-effort and non-fatal.
- Club pages from Apex, Capital, Mission, NWFC, and Hooked on Fencing returned 200 with camp headings and date text.
- Do not edit `.github/workflows/`; Agent 80 owns CI integration.

Final review:
- Files changed: `scrape_training_camps.py`, `tests/test_camps.py`, `supabase/migrations/20260601_camps.sql`, `tasks/todo.md`.
- Behavior changed: added `fs_training_camps` migration with date/location/weapon indexes and RLS enabled; added a scraper that fetches federation/club/aggregator camp sources, parses HTML and PDF text, extracts dates/cost/coaches/weapons/location, dedupes by `name,organizer,start_date,end_date`, upserts to Supabase, and records run state.
- Verification: red test run failed first with missing module/migration; `./.venv/bin/python -m pytest tests/test_camps.py -v` passed 8/8; `./.venv/bin/python -m py_compile scrape_training_camps.py` passed; live-source fake-client dry run parsed 26 candidates, wrote 25 deduped rows, failed only the two known broken Eurofencing URLs, and skipped one page.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` ran 637 passed, 13 failed, 1 warning. Failures were unrelated existing/in-progress areas: `tests/test_scholarships.py` and `tests/test_scrape_iwas.py`.
- Remaining risks: Supabase credentials were not present in this shell, so the live run used a fake client and did not populate the real database; Eurofencing camp links currently 404 and are kept best-effort.

---

## Active Work: Agent 61 — Central American & Caribbean Games

- [x] Read relevant lessons and current task state.
- [x] Inspect Olympics scraper pattern and existing result-scraper tests.
- [x] Probe Olympedia and official CAC Games result archive structure.
- [x] Write failing CAC parser tests from probed source fixtures.
- [x] Implement `scrape_cac_games.py` with discovery, parsers, upserts, state, logging, and skip reasons.
- [x] Run targeted and relevant verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Olympedia exposes CAC Games only in athlete/list mention text; no structured CAC fencing result pages were found in the probed results/organization/sport pages.
- 2018 official Barranquilla PDFs expose structured individual final standings and team medalist lists.
- 2014 official Veracruz PDFs are bracket-style, 2023 official S3 PDFs currently return AccessDenied, and 2010 has no usable public official fencing archive in the initial probe.
- Do not edit `.github/workflows/`; Agent 80 owns CI integration.

### Final Review: Agent 61 — Central American & Caribbean Games

- Files changed: `scrape_cac_games.py`, `tests/test_scrape_cac_games.py`, `tasks/todo.md`.
- Behavior changed: added CAC Games scraper for structured public official fencing results. Current importable coverage is 2018 Barranquilla: 12/12 official archive PDF events parse successfully. Earlier editions are skipped with explicit reasons; 2014 bracket-only PDFs and 2023 AccessDenied PDFs are not imported.
- Verification: red tests first failed on missing `scrape_cac_games`; targeted `pytest tests/test_scrape_cac_games.py -v` passed 6/6; `py_compile` passed; live no-write 2018 archive parse passed 12/12 events.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed outside this task scope with 8 unrelated failures in `tests/test_camps.py` and `tests/test_scrape_iwas.py` (`631 passed`).
- Remaining risk: only public structured 2018 official PDFs are imported; 2023 can be enabled if the official S3 PDFs become public or another official archive appears. No Supabase write smoke was run because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are not set in this shell.

---

## Active Work: Agent 30 — Equipment & Brand Data

- [x] Read project lessons and current task state.
- [x] Inspect existing profile/enrichment scraper patterns and migration/test conventions.
- [x] Probe FIE/Wikipedia source structure before parser implementation.
- [x] Write failing fixture tests for brand extraction, equipment type detection, sponsor section parsing, dedupe, fencer loading, and upsert payloads.
- [x] Implement `scrape_equipment.py` with extraction helpers, Supabase loading/upserts, run logging, and state summary.
- [x] Add `supabase/migrations/20260601_equipment.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `scrape_wikipedia_bios.py` is not present in this checkout yet; equipment scraping should consume `fs_fencers.bio_text` opportunistically when the column exists.
- Agent 2 identity grouping is preferred, but equipment rows should remain keyed to raw `fs_fencers.id` because the requested table references `fs_fencers(id)`.
- Do not edit `.github/workflows/`; Agent 80 owns CI integration.

Final review:
- Files changed: `scrape_equipment.py`, `tests/test_equipment.py`, `supabase/migrations/20260601_equipment.sql`, `tasks/todo.md`.
- Behavior changed: added equipment/sponsor extraction from FIE profile HTML, existing Wikipedia `bio_text`, and federation profile URLs; rows use deterministic UUIDv5 IDs and Supabase upsert on `id`.
- Verification: FIE/Wikipedia probe succeeded after network escalation; `pytest tests/test_equipment.py -v` passed 8/8; `py_compile` passed for `scrape_equipment.py` and `tests/test_equipment.py`; full `pytest tests/ -v` ran 612 tests with 575 passed and 37 unrelated failures in incomplete/missing other-agent modules.
- Remaining risks: arbitrary federation profile pages are generic HTML extraction only; production quality depends on profile URLs existing in `fs_fencers` or metadata and on Agent 27 adding `bio_text`.

---

## Active Work: Agent 65 — Competition Format & Prize Money

- [x] Read project lessons and current task state.
- [x] Probe FIE competition detail page and invitation PDF structure.
- [x] Write failing parser/upsert/migration tests with captured FIE-like fixtures.
- [x] Add `fs_competition_details` migration SQL.
- [x] Implement `scrape_competition_details.py` with FIE detail/PDF extraction, upsert, state, and run logging.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- FIE detail pages expose `window._competition`, `_athletes`, `_pools`, `_tableau`, and `_downloadLinks`.
- Participant count comes from `_competition.fencerCount`; invitation PDFs can contain entry-fee/prize money text.
- Use `competition_url_id` when present, with `fie_id` fallback for the FIE detail URL.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_competition_details.py`, `tests/test_competition_details.py`, `supabase/migrations/20260601_competition_details.sql`, `tasks/todo.md`.
- Behavior changed: adds `fs_competition_details`; scraper finds FIE tournaments without details, parses FIE detail window variables for participants/pools/DE rounds/countries, extracts entry fee and prize pool from invitation/regulation PDFs, upserts on `tournament_id`, and records run/state summaries.
- Verification: `tests/test_competition_details.py -v` passed 5/5; relevant FIE/detail subset passed 24/24.
- Full suite: `.venv/bin/python -m pytest tests/ -v` is blocked by unrelated missing modules `scrape_cac_games` and `scrape_ncaa_regular`. Retrying with those ignored ran 567 tests: competition-details tests passed, but 86 unrelated in-progress agent tests failed.
- Risks: prize parsing is best-effort for published PDF text and may miss image-only PDFs or ambiguous prize schedules without currency markers.

---

## Active Work: Agent 31 — Paralympic Games Fencing

- [x] Read relevant project lessons and current task state.
- [x] Inspect `scrape_olympics.py`, IWAS/parafencing patterns, and existing parser tests.
- [x] Probe Olympedia and Paralympic.org URL/table structure.
- [x] Write failing tests for Paralympic edition event discovery, classification, result parsing, and DB row writes.
- [x] Implement `scrape_paralympics.py` with official archive discovery, tournament upserts, result inserts, fencer matching, state, and run logging.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Olympedia sport pages expose Olympic/Youth Olympic fencing (`FEN`) but the probe did not find Paralympic wheelchair fencing entries there.
- `paralympic.org` official result archive has stable pages like `/paris-2024-paralympic-games/results/wheelchair-fencing` and event pages with `Medallists` tables.

Final review:
- Files changed: `scrape_paralympics.py`, `tests/test_scrape_paralympics.py`, `tasks/todo.md`.
- Behavior changed: added official Paralympic wheelchair fencing event discovery for 1980-2024, medallist placement parsing, tournament upserts, result inserts, fencer matching, state, and run logging.
- Verification: targeted tests passed (`tests/test_scrape_paralympics.py tests/test_scrape_olympics.py`); syntax check passed; live-read parser probe found events for every configured edition and parsed sample 1980/2024 medallist rows.
- Remaining risks: full `tests/` command is currently blocked by unrelated collection errors for missing `scrape_cac_games.py` and `scrape_ncaa_regular.py`; DB load was not run because `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are not set; official archive event pages expose medal placements, not complete final classification rows for every athlete.

---

## Active Work: Agent 41 — Belgium Federation Scraper

- [x] Read project lessons and current task state.
- [x] Inspect existing federation scraper patterns, shared ranking helpers, and season utility state.
- [x] Probe Belgium national/regional ranking sources and identify public Ophardt combo coverage.
- [x] Write failing Belgium parser/fetch tests with realistic Ophardt fixtures.
- [x] Implement `scrape_fed_bel.py` with parser, fetcher, season fallback, dedupe, run logging, and writes.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `season_utils.py` is not present in this checkout; Belgium scraper should use a local fallback while remaining compatible with future `season_utils.normalize_season()`.
- Public national rankings are linked from `https://www.fencing-belgium.be/nationa-a-l` to Ophardt `https://fencing.ophardt.online/en/search/rankings/159`.
- FFCEB/VSB pages reference the national KBFS/FRBCE/Ophardt flow; no separate public regional ranking tables were found in the initial probe.
- Live validation parsed all 12 public combos: 464 total rows; no empty combos.
- `tests/test_fed_bel.py -v` passes; full `tests/ -v` currently stops on unrelated missing modules `scrape_cac_games` and `scrape_ncaa_regular`.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_bel.py`, `tests/test_fed_bel.py`, `tasks/todo.md`.
- Behavior changed: Belgium national rankings now fetch public Ophardt pages for 12 Senior/Junior individual combos, parse multilingual ranking tables, dedupe duplicate regional-style rows, attach source metadata, and write via `fed_rankings_common.write_rankings()`.
- Verification: targeted Belgium pytest, py_compile, live parse validation for all 12 public pages, and repo-wide pytest attempt.
- Remaining risk: Ophardt ranking IDs may change in a future season; the source index URL is recorded for reprobe.

---

## Active Work: Agent 42 — Switzerland Federation Scraper

- [x] Read project lessons and existing federation scraper patterns.
- [x] Probe `swiss-fencing.ch` and linked official Swiss Ophardt rankings.
- [x] Write failing Switzerland parser tests with realistic Swiss/Ophardt fixtures.
- [x] Implement `scrape_fed_sui.py` with public Swiss ranking IDs, parser, run logging, and season fallback.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `swiss-fencing.ch` `/classements`, `/rankings`, `/ranglisten`, and `/ranking` return 404, but the home page links `https://fencing.ophardt.online/fr/search/rankings/12` as "Nationales Ranking".
- The Ophardt Swiss "Circuit National" table exposes all 12 Senior/U20 Foil/Epee/Sabre Men/Women combos as public HTML pages.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_sui.py`, `tests/test_fed_sui.py`, `tasks/todo.md`.
- Behavior changed: Switzerland national rankings now fetch public Swiss/Ophardt HTML pages for 12 Senior/Junior individual combos, parse multilingual ranking tables, preserve accented names/clubs, skip DNS/DQ/summary rows, attach source metadata, and write via `fed_rankings_common.write_rankings()`.
- Verification: red/green targeted Switzerland pytest; `tests/test_fed_sui.py tests/test_fed_rankings_common.py -v`; `py_compile`; live non-writing parse validation for all 12 public pages.
- Remaining risk: Ophardt ranking IDs may change in a future season; source index and probed IDs are recorded for reprobe. Full `tests/ -v` is blocked by unrelated missing modules `scrape_cac_games` and `scrape_ncaa_regular`; federation subset has unrelated failures in other agent-owned files.

---

## Active Work: Agent 43 — Austria Federation Scraper

- [x] Read relevant project lessons and existing federation scraper patterns.
- [x] Probe `fencing.at` candidates and ÖFV public ranking pages.
- [x] Write failing parser tests with realistic German ÖFV ranking fixtures.
- [x] Implement `scrape_fed_aut.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused and relevant verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fencing.at` redirects to `www.fechten.at`, a KAC club site; requested candidate paths return WordPress 404 pages there.
- Correct public federation source is `https://www.oefv.com/de/intern:13/ranglisten-saison-2025-2026`.
- ÖFV ranking page uses GET for the default page and POST form fields `search[typ]`, `search[waffen]`, `search[altersklasse]`; response is server-rendered HTML.
- Public coverage found: Senior, Junior, and Cadet for Foil/Epee/Sabre and Men/Women.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_aut.py`, `tests/test_fed_aut.py`, `tasks/todo.md`.
- Behavior changed: added public ÖFV rankings scraper using POST form HTML, German header parsing, comma decimal handling, Senior/Junior/Cadet combos, season fallback compatible with `season_utils.normalize_season()`, run logging, and `fed_rankings_common.write_rankings()`.
- Verification: red test run failed first because `scrape_fed_aut` was missing; focused `tests/test_fed_aut.py -v` passed with 8 tests; `tests/test_fed_rankings_common.py -v` passed with 5 tests; `py_compile` passed; live read-only verification parsed 18/18 public combos and 540 rows from `https://www.oefv.com/de/intern:13/ranglisten-saison-2025-2026`.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran with 633 passed / 6 failed / 1 warning; remaining failures are unrelated IWAS parser tests in `tests/test_scrape_iwas.py`.
- Remaining risks: ÖFV may rotate season URLs; scraper detects current season, falls back to the probed season, and can discover the latest public ranking link from the federation home page.

---

## Active Work: Agent 16 — USA Fencing FRED Results

- [x] Read project lessons and current task state.
- [x] Read `askfred_scraper.py`, `scrape_results.py`, and `scrape_olympics.py` patterns.
- [x] Probe requested FRED hosts and current public AskFRED surface.
- [x] Write failing tests with captured public CSV/HTML fixture shape.
- [x] Implement `scrape_fred.py` with discovery, result parsing, fencer matching, and upserts.
- [x] Run focused and relevant full verification.
- [x] Final review: files changed, behavior changed, verification, risks.

---

## Active Work: Agent 78 - Scraper Health Monitoring Dashboard

- [x] Read relevant project lessons and current task state.
- [x] Inspect run logger, data quality views, scraper table usage, and dashboard/test surface.
- [x] Write failing tests for dashboard query blocks, stale/orphan checks, and mocked Streamlit import.
- [x] Implement `dashboard/queries.sql` with run status, data counts, stale source, and error-rate references.
- [x] Implement `dashboard/app.py` Streamlit pages for status, data counts, coverage map, and error log.
- [x] Add Streamlit/Plotly dashboard dependencies.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Prefer Agent 38 quality views when present, but keep direct table fallbacks so the dashboard still runs before those views are deployed.
- Do not edit `.github/workflows/`.

### Final Review: Agent 78 - Scraper Health Monitoring Dashboard

- Files changed: `dashboard/app.py`, `dashboard/queries.sql`, `tests/test_dashboard_queries.py`, `requirements.txt`, `tasks/todo.md`.
- Behavior changed: added a Streamlit dashboard with status, data counts, coverage map, and searchable error log pages; added SQL reference queries for run status, data counts, stale sources, orphan checks, and module error rates; added `streamlit` and `plotly` dashboard dependencies.
- Verification: red targeted tests first failed on missing dashboard files; final `./.venv/bin/python -m pytest tests/test_dashboard_queries.py -v` passed with 4 tests; `./.venv/bin/python -m py_compile dashboard/app.py` passed; real import check passed with Streamlit 1.58.0 and Plotly 6.7.0; Streamlit server smoke test served HTTP 200 on `127.0.0.1:8507` after port-binding approval.
- Full suite: `./.venv/bin/python -m pytest tests/ -q` ran after final edits and failed with 23 unrelated in-progress scraper failures, with 602 passing and 1 warning. Dashboard tests passed.
- Remaining risks: live Supabase page rendering was not exercised because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` were not set in this shell; large-table dashboard pages aggregate via REST fallbacks when Agent 38 materialized views are absent.

---

## Active Work: Agent 76 — Scraper Rate Limiting Service

- [x] Read relevant project lessons and current task state.
- [x] Confirm no existing rate limiter implementation or tests are present.
- [x] Write failing tests for timing accuracy, domain isolation, jitter, backoff, and invalid inputs.
- [x] Implement `scripts/rate_limiter.py` with per-domain wait, jitter, backoff, and callable usage.
- [x] Run targeted and full verification; document unrelated collection blockers.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep scope to `scripts/rate_limiter.py`, `tests/test_rate_limiter.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.

### Final Review: Agent 76 — Scraper Rate Limiting Service

- Files changed: `scripts/rate_limiter.py`, `tests/test_rate_limiter.py`, `tasks/todo.md`.
- Behavior changed: added a per-domain `RateLimiter` with deterministic request spacing, optional jitter, failure backoff after three failures, success reset, callable usage, and context-manager support.
- Verification: red run failed first because `scripts.rate_limiter` was missing; `./.venv/bin/python -m pytest tests/test_rate_limiter.py -v` passed with 10 tests; `./.venv/bin/python -m py_compile scripts/rate_limiter.py` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` stops during collection on unrelated missing modules `discover_competition_urls` and `enrich_locations`.
- Remaining risk: no scraper has been wired to use the limiter yet; this task only adds the service and tests.

---

**80 Codex Agents** — 5 bug fixes, 25 federation scrapers, 16 competition sources, 12 analytics engines, 11 enrichment, 9 data product, 1 CI merge.

Each agent = one file (or small file group), tests-first, no cross-dependencies. CI step edits batched at the end.

---

## Active Work: Agent 77 — Schema Migration Tooling

- [x] Read project lessons, current task state, and existing migration/test patterns.
- [x] Write failing tests for migration list, generate, dry-run, and hash mismatch handling.
- [x] Implement `scripts/migrate.py` with list/apply/generate/dry-run/status.
- [x] Write `supabase/migrations/README.md` usage examples and operational notes.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep scope to `scripts/migrate.py`, `supabase/migrations/README.md`, `tests/test_migrate_cli.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.

### Final Review: Agent 77 — Schema Migration Tooling

- Files changed: `scripts/migrate.py`, `supabase/migrations/README.md`, `tests/test_migrate_cli.py`, `tasks/todo.md`.
- Behavior changed: added migration discovery for `YYYYMMDD_*.sql` and existing `YYYYMMDDHHMMSS_*.sql`, applied/pending/failed status display, pending dry-runs, status summary, dated migration generation, SHA-256 mismatch blocking, and migration apply through `psql` plus `fs_schema_migrations` Supabase tracking upserts.
- Verification: red run of `./.venv/bin/python -m pytest tests/test_migrate_cli.py -v` failed before implementation with missing `scripts.migrate`; after implementation, `./.venv/bin/python -m py_compile scripts/migrate.py tests/test_migrate_cli.py` passed and `./.venv/bin/python -m pytest tests/test_migrate_cli.py -v` passed 6/6.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected broader active-agent tests and failed with 130 failed, 355 passed, 1 warning. All `tests/test_migrate_cli.py` tests passed inside the full run; failures were in unrelated active-agent modules such as CISM, competition details, federation scrapers, island/Maccabiah/Paralympics scrapers, and others.
- Remaining risk: `apply` requires a local `psql` binary and `SUPABASE_DB_URL` or `DATABASE_URL`; migrations using SQL that cannot run inside a transaction will fail because each file is applied with `--single-transaction`.

---

## Active Work: Agent 36 — Referee & Coach Data

- [x] Read relevant project lessons, task state, and existing scraper patterns.
- [x] Probe FIE referee source URLs and confirm `https://fie.org/referees/search` JSON structure.
- [x] Write failing tests for referee JSON/HTML/PDF parsing, coach staff parsing, relationship extraction, and Supabase upsert behavior.
- [x] Implement `scrape_referees.py` with FIE JSON primary source plus HTML/PDF fallbacks, run logging, and state summary.
- [x] Implement `scrape_coaches.py` with top-federation source discovery, coaching staff parsing, fencer-coach relationship capture, run logging, and state summary.
- [x] Add `supabase/migrations/20260601_referees.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Full `pytest tests/ -v` is currently blocked by unrelated collection error: `tests/test_scrape_ncaa_regular.py` imports missing `scrape_ncaa_regular.py` (Agent 20 scope). Use targeted tests plus full suite with that file ignored for Agent 36 regression coverage.
- Targeted Agent 36 verification passed: `py_compile`, `pytest tests/test_referees.py -v` (`8 passed`), `pdfplumber` import, and live read-only parser probes for FIE referees plus USA/France coach pages.
- FIE referee page script uses `/referees/search?fetchPage=N`; bounded live probe with five pages returned 500 referee rows, so `scrape_referees.py` paginates until an empty page or `FIE_REFEREES_MAX_SEARCH_PAGES`.
- Broader `pytest tests/ -v --ignore=tests/test_scrape_ncaa_regular.py` ran 601 collected tests and ended with unrelated pre-existing failures in other agents' modules (`scrape_fed_arg`, `scrape_fed_bra`, `scrape_fed_italy`, `scrape_fed_ned`, `scrape_engarde`, `scrape_iwas`, `scrape_masters_games`). Agent 36 tests passed within that run.
- Files changed for Agent 36: `scrape_referees.py`, `scrape_coaches.py`, `tests/test_referees.py`, `supabase/migrations/20260601_referees.sql`, `requirements.txt`, `tasks/todo.md`.

---

## Active Work: Agent 79 — Cross-Source Data Reconciliation

- [x] Read project lessons and current task state.
- [x] Inspect existing source tables, pagination patterns, script style, and test doubles.
- [x] Write failing reconciliation tests for FIE/federation matches, mismatches, and source-only rows.
- [x] Implement `scripts/reconcile_data.py` with source mapping, paginated reads, FIE ID matching, fallback matching, mismatch classification, CLI JSON output, run logging, and state summary.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Match by FIE ID first; fall back to normalized name+country only when FIE ID is unavailable.
- `fs_fencers` can contain duplicate rows per person; dedupe by stable source identity before comparing.
- Keep scope to `scripts/reconcile_data.py`, `tests/test_reconcile.py`, task/wiki memory, and no `.github/workflows/` changes.

Final review:
- Files changed: `scripts/reconcile_data.py`, `tests/test_reconcile.py`, `tasks/todo.md`.
- Behavior changed: added source reconciliation across `fs_fencers`, `fs_national_fed_rankings`, and Olympedia-tagged `fs_results`; reports matched, mismatched, source-only rows, and detailed JSON samples.
- Verification: red run failed on missing implementation; `.venv/bin/python -m pytest tests/test_reconcile.py -v` passed 4/4; `.venv/bin/python scripts/reconcile_data.py --help` passed; `.venv/bin/python -m py_compile scripts/reconcile_data.py tests/test_reconcile.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` is blocked before execution by unrelated missing module `scrape_cac_games` in `tests/test_scrape_cac_games.py`.
- Remaining risks: friendly source aliases are best-effort; unknown federation source names must match `fs_national_fed_rankings.source` exactly.

---

## Active Work: Agent 37 — FIE Competition URL ID Discovery

- [x] Read project lessons, current task state, and prior FIE discovery notes.
- [x] Inspect embedded `scrape_results.py` URL discovery and FIE URL behavior.
- [x] Write failing tests for standalone incremental discovery, URL ID extraction, skipped rows, and run logging.
- [x] Implement `discover_competition_urls.py` with FIE detail probing, 1 req/sec rate limit, Supabase updates, run logging, and state summary.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep CI workflow untouched; Agent 80 owns ordering.
- Live probe confirmed `https://fie.org/competitions/{id}` 404s while `https://fie.org/competitions/{season}/{competitionId}` works.

Final review:
- Files changed: `discover_competition_urls.py`, `tests/test_discover_urls.py`, `tasks/todo.md`.
- Behavior changed: standalone incremental discovery queries `fs_tournaments` rows with missing `competition_url_id`, non-null `fie_id`, and `has_results = true`; probes FIE detail URLs; falls back to FIE search + detail URL extraction; updates `competition_url_id`; records run logger/state summary.
- Verification: `tests/test_discover_urls.py` passed 7/7; `py_compile` passed for the new script and test.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran 438 tests with 320 passing and 118 unrelated failures from unfinished/missing agent modules and `.github/workflows/` expectations. Agent 37 tests passed in the full run.
- Remaining risk: CI ordering still needs Agent 80 to add `discover_competition_urls.py` before result scrapers in workflow YAML.

---

## Active Work: Agent 74 — Weapon Specialization Analysis

- [x] Read project lessons and current task state.
- [x] Inspect existing result, tournament, identity, run logger, and analytics patterns.
- [x] Write failing tests for single/multi-weapon classification, primary weapon, aggregate success rates, Junior-to-Senior transition, weapon switching, and Supabase fetch/report behavior.
- [x] Implement `compute_specialization.py` with identity-aware fs_results aggregation, tournament/fencer enrichment, run logging, and state summary.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Use `fs_fencer_identities` when available; fall back to raw `fs_results.fencer_id` and FIE ID mapping.
- `fs_results` weapons usually come from `fs_tournaments`; tolerate result-level `weapon`, `season`, and `category` fallbacks.
- Do not edit `.github/workflows/`.

### Final Review: Agent 74 — Weapon Specialization Analysis

- Files changed: `compute_specialization.py`, `tests/test_specialization.py`, `tasks/todo.md`.
- Behavior changed: added identity-aware specialization reporting from `fs_results` + `fs_tournaments`, including single vs multi-weapon classification, primary weapon tie-breaking by count/latest event/rank, specialist vs generalist aggregate metrics, Junior-to-Senior transition age/gap stats, and season-to-season primary weapon switch impact.
- Verification: red run failed with missing `compute_specialization`; final focused run `./.venv/bin/python -m pytest tests/test_specialization.py -v` passed 3 tests; adjacent analytics run `./.venv/bin/python -m pytest tests/test_specialization.py tests/test_career_stats.py tests/test_transfers.py -v` passed 8 tests; `./.venv/bin/python -m py_compile compute_specialization.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` could not complete normally because unrelated collection errors remain in other agents' missing modules such as `scrape_cac_games`; with `--continue-on-collection-errors`, the new specialization tests passed but the suite still had unrelated in-progress failures.
- Remaining risk: no new persistence table or migration was added; the computation reports via return value, run log metadata, CLI output, and `fs_scraper_state`.

---

## Active Work: Agent 71 - Performance vs Ranking Prediction

- [x] Read project lessons and current task state.
- [x] Inspect adjacent analytics engines, tests, run logger, and state patterns.
- [x] Write failing tests for delta aggregation, NULL ranks, mixed weapons, Supabase upsert behavior, optional career-stat mirroring, and migration SQL.
- [x] Implement `compute_performance_analysis.py` with paginated fetches, rank/weapon normalization, metric aggregation, run logging, state update, and optional `fs_fencer_career_stats.clutch_score` mirror.
- [x] Add `supabase/migrations/20260601_performance_analysis.sql` for `fs_fencer_performance_analysis`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Use current `fs_fencers.world_rank` as the expected placement approximation.
- Treat overperformance consistently with `delta = expected - actual`: actual rank numerically lower than expected is overperformance.
- Keep changes scoped to `compute_performance_analysis.py`, `tests/test_performance_analysis.py`, the performance migration, and task/wiki memory.
- Do not edit `.github/workflows/`.

### Final Review: Agent 71 - Performance vs Ranking Prediction

- Files changed: `compute_performance_analysis.py`, `tests/test_performance_analysis.py`, `supabase/migrations/20260601_performance_analysis.sql`, `tasks/todo.md`.
- Behavior changed: added performance-vs-ranking aggregation from `fs_results`, `fs_fencers.world_rank`, and `fs_tournaments.weapon`; writes per `(fencer_id, weapon)` metrics to `fs_fencer_performance_analysis`; skips missing fencer/rank/world-rank/weapon rows; optionally mirrors weighted per-fencer `clutch_score` into `fs_fencer_career_stats` only when that column exists.
- Verification: initial red run failed on missing module/migration; focused run `./.venv/bin/python -m pytest tests/test_performance_analysis.py -v` passed with 4 tests; `./.venv/bin/python -m py_compile compute_performance_analysis.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` ran from project root and failed due unrelated in-progress agent areas, with the new performance tests passing inside the full run. Final full summary: 274 passed, 118 failed, 1 warning.
- Remaining risk: `world_rank` is current-rank approximation, not historical competition-time rank; optional career-stat mirroring uses weighted average across weapon rows because `fs_fencer_career_stats` is keyed only by `fencer_id`.

---

## Active Work: Agent 64 — Fencer Nationality History

- [x] Read relevant project lessons and current task state.
- [x] Inspect Wikidata SPARQL pattern, identity grouping, transfer cross-checks, run logging, and state patterns.
- [x] Write failing tests for timed P27 history, unordered multi-citizenship, identity-expanded fencer updates, transfer consistency checks, and optional transfer table absence.
- [x] Implement `enrich_nationality_history.py` with Wikidata SPARQL fetch, history parsing, fs_fencers metadata updates, identity expansion, transfer cross-checking, run logging, and state update.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep changes scoped to `enrich_nationality_history.py` and `tests/test_nationality_history.py`; do not edit `.github/workflows/`.
- `fs_fencer_identities` and `fs_fencer_transfers` may be absent in some deployments; nationality enrichment should continue without those optional tables.

Final review:
- Files changed: `enrich_nationality_history.py`, `tests/test_nationality_history.py`, `tasks/todo.md`.
- Behavior changed: added Wikidata P27 statement parsing for fencers with multiple citizenship countries, ordered histories via P580/P582 when available, unordered deterministic lists without qualifiers, identity-expanded `fs_fencers.metadata.nationality_history` updates, and `fs_fencer_transfers` consistency metadata when present.
- Verification: RED run failed on missing `enrich_nationality_history`; targeted nationality tests passed after implementation; related Wikidata and transfer regression tests passed; py_compile passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` is blocked by unrelated collection errors for missing `discover_competition_urls` and `enrich_locations`. Retrying with only those two tests ignored produced 216 passed, 115 failed, and 9 errors from other incomplete agent areas, not this scoped change.
- Remaining risks: no live Wikidata network probe was run because this reuses the existing `scrape_wikidata.py` endpoint/pattern and tests mock SPARQL responses; production rows depend on deployed optional `fs_fencer_identities`/`fs_fencer_transfers` schemas for the extra expansion/check metadata.

---

## Active Work: Agent 73 — Fencer Longevity Analysis

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing analytics compute/test/migration patterns.
- [x] Write failing tests for active, retired, unknown, and single-season fencer longevity metrics.
- [x] Add `supabase/migrations/20260601_longevity.sql` for `fs_fencer_longevity`.
- [x] Implement `compute_longevity.py` with paginated reads, date/season normalization, run logging, state update, and batched upserts.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep scope to `compute_longevity.py`, `tests/test_longevity.py`, `supabase/migrations/20260601_longevity.sql`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Single-season fencers should keep `career_years = 0` while avoiding division by zero for `competitions_per_season`.

### Final Review: Agent 73 — Fencer Longevity Analysis

- Files changed: `compute_longevity.py`, `tests/test_longevity.py`, `supabase/migrations/20260601_longevity.sql`, `tasks/todo.md`.
- Behavior changed: added a full longevity recomputation job that reads `fs_fencers`, `fs_results`, and `fs_tournaments`, computes first/last competition dates, parsed first/last seasons, career years, competitions per season, and `active`/`likely_retired`/`unknown` status, then upserts rows into `fs_fencer_longevity`.
- Verification: red run failed first for missing module/migration; `./.venv/bin/python -m pytest tests/test_longevity.py -v` passed 4 tests; `./.venv/bin/python -m py_compile compute_longevity.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` ran and failed with 112 existing unrelated failures; the 4 longevity tests passed inside that run.
- Remaining risks: duplicate physical fencers with multiple `fs_fencers` rows remain separate because the requested table keys by `fs_fencers.id`; full-suite health is currently blocked by other unfinished agent work.

---

## Active Work: Agent 72 — Medal Table Aggregation

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing compute/upsert/test patterns and medal/result columns.
- [x] Write failing tests for country, fencer, and tier medal aggregation plus migration DDL.
- [x] Implement `compute_medal_tables.py` with paginated reads, tier normalization, batched upserts, run logging, and state summary.
- [x] Add `supabase/migrations/20260601_medal_tables.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fs_results` may store country as `nationality` and/or `country`; prefer `country` with `nationality` fallback.
- Join `fs_tournaments` by `tournament_id` and normalize tiers to `Olympics`, `Worlds`, `GP`, `WC`, or `Continental`; skip tier rows only when tier or country is unavailable.
- Do not edit `.github/workflows/`.

### Final Review: Agent 72 — Medal Table Aggregation

- Files changed: `compute_medal_tables.py`, `supabase/migrations/20260601_medal_tables.sql`, `tests/test_medal_tables.py`, `tasks/todo.md`.
- Behavior changed: added medal aggregation from medaled `fs_results` rows into scoped `fs_medal_tables` records for countries, fencers, and tier+country groups; joins `fs_tournaments` for normalized tier labels; falls back from `country` to `nationality`; upserts on deterministic `id`; records run log and state.
- Verification: red run failed first for missing module/migration; `./.venv/bin/python -m pytest tests/test_medal_tables.py -v` passed 4 tests; `./.venv/bin/python -m py_compile compute_medal_tables.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected 424 tests, with 306 passed, 118 failed, and 1 warning. All `tests/test_medal_tables.py` tests passed; failures are in unrelated in-progress agent areas such as CISM, competition details, federation scrapers, and reconcile.
- Remaining risk: the compute job upserts current aggregate rows but does not delete stale `fs_medal_tables` rows for source medal rows that later disappear or change country/fencer/tier.

---

## Active Work: Agent 39 — Export API + CLI

- [x] Read relevant lessons, current task state, and table dependency prompts.
- [x] Confirm `api.py`, `cli_export.py`, `docs/api.yaml`, `tests/test_api.py`, and `tests/test_cli_export.py` are new in this checkout.
- [x] Write failing FastAPI and CLI export tests with mocked Supabase pagination.
- [x] Implement `api.py` with API-key auth, in-memory rate limiting, CORS, read-only routes, Supabase pagination, and endpoint handlers.
- [x] Implement `cli_export.py` with JSON/CSV export, filters, automatic pagination, and stderr progress.
- [x] Write `docs/api.yaml` OpenAPI 3.0 spec.
- [x] Add required FastAPI runtime dependencies.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Dependent tables from other agents are expected: `fs_fencer_career_stats`, `fs_fencer_social_media`, `fs_fencer_equipment`, `fs_head_to_head`, and `fs_country_depth`.
- This agent will not edit `.github/workflows/`.

Final review:
- Files changed: `api.py`, `cli_export.py`, `docs/api.yaml`, `tests/test_api.py`, `tests/test_cli_export.py`, `requirements.txt`, `tasks/todo.md`.
- Behavior changed: added read-only FastAPI routes with API-key auth, per-key in-memory rate limiting, CORS, Supabase pagination, optional enrichment table reads, JSON response envelopes, and CLI JSON/CSV exports with automatic pagination/progress.
- Verification: initial red run failed for missing `fastapi`, then for missing `api`/`cli_export`; installed declared FastAPI deps with `uv pip install`; targeted `./.venv/bin/python -m pytest tests/test_api.py tests/test_cli_export.py -v` passed 16 tests; app import/server route smoke passed; CLI help smoke passed; `./.venv/bin/python -m py_compile api.py cli_export.py tests/test_api.py tests/test_cli_export.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected 454 tests, with 336 passed, 118 failed, and 1 warning. Agent 39 tests passed; failures are in unrelated active-agent areas such as CISM, competition details, federation scrapers, and reconcile.
- Remaining risk: API fields for career/social/equipment/H2H/country depth require other agents' tables to exist in production; fencer profile enrichment reads return null/empty if optional tables are absent, but H2H/country-depth endpoints expect their analytics tables.

---

## Active Work: Agent 70 — Strength of Field Metric

- [x] Read project lessons, task state, and nearby analytics patterns.
- [x] Write failing tests for per-tournament strength aggregation and Supabase upsert behavior.
- [x] Add `supabase/migrations/20260601_strength_of_field.sql` defining `fs_competition_strength`.
- [x] Implement `compute_strength_of_field.py` with paginated reads, rank filtering, batched upserts, run logging, and state update.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Score is `sum(101 - world_rank) / ranked participant count`.
- Do not edit `.github/workflows/`.

### Final Review: Agent 70 — Strength of Field Metric

- Files changed: `compute_strength_of_field.py`, `supabase/migrations/20260601_strength_of_field.sql`, `tests/test_strength_of_field.py`, `tasks/todo.md`.
- Behavior changed: added full recomputation of `fs_competition_strength` from `fs_results` joined to `fs_fencers.world_rank`; de-duplicates participant fencers per tournament; ignores missing, null, zero, and non-integer ranks; writes zero-ranked rows for tournaments that have results but no usable FIE ranks; upserts on `tournament_id`; records run log and state.
- Verification: targeted red run failed first with missing module/migration; `./.venv/bin/python -m pytest tests/test_strength_of_field.py -v` passed 3/3 after implementation; `./.venv/bin/python -m py_compile compute_strength_of_field.py` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` failed during collection on unrelated missing modules `discover_competition_urls` and `enrich_locations`. Retrying with those ignored then failed on unrelated missing `scripts.reconcile_data`. Retrying with all three ignored ran 307 tests: 201 passed, 97 failed, 9 errors, all outside `tests/test_strength_of_field.py`.
- Remaining risks: the compute job rewrites/upserts current aggregate rows but does not delete stale `fs_competition_strength` rows if all source results for a tournament are later removed.

---

## Active Work: Agent 66 — Fencing Club Ratings & Reviews

- [x] Read relevant project lessons and current task state.
- [x] Inspect scraper, Supabase, state, run logger, and club-ranking patterns.
- [x] Probe external review source URL/API shapes before parser implementation.
- [x] Write failing tests for club normalization, Google Maps parsing, no-key behavior, idempotent upsert payloads, and migration SQL.
- [x] Implement `scrape_club_reviews.py` with optional Maps API, forum mention aggregation, state, logging, and source-specific upserts.
- [x] Add `supabase/migrations/20260601_club_reviews.sql` for `fs_club_reviews`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Do not scrape Google Maps HTML; use the Places API only when `MAPS_API_KEY` is set.
- `fs_club_rankings` is optional in this checkout; query it opportunistically and continue if unavailable.
- Keep source-specific ratings separate via unique `(normalized_club_name, city, country, source)`.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_club_reviews.py`, `tests/test_club_reviews.py`, `supabase/migrations/20260601_club_reviews.sql`, `tasks/todo.md`.
- Behavior changed: added deterministic club-review rows from optional Google Maps Places API and forum mention searches; skips Google Maps cleanly when `MAPS_API_KEY` is absent; fetches city-qualified clubs from `fs_fencers` and optional `fs_club_rankings`; upserts source-specific rows on `(normalized_club_name, city, country, source)`.
- Verification: red run failed first with missing module/migration; `.venv/bin/python -m pytest tests/test_club_reviews.py -v` passed 7/7; `.venv/bin/python -m py_compile scrape_club_reviews.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran 431 tests and failed with 120 unrelated failures from other in-progress agents/workflow files; Agent 66 tests passed inside that run.
- Remaining risks: Reddit unauthenticated search returned HTTP 403 during probe, so runtime treats that source as best-effort and logs/skips failures; Google Maps coverage requires `MAPS_API_KEY`.

---

## Active Work: Agent 63 — Fencer Physical Stats

- [x] Read relevant project lessons and current task state.
- [x] Probe FIE athlete profile and Wikipedia REST HTML source structures.
- [x] Write failing parser, update-payload, Supabase update, and migration tests.
- [x] Implement `scrape_physical_stats.py` using FIE profile and Wikipedia infobox sources.
- [x] Add `supabase/migrations/20260601_physical_stats.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Store `height` and `reach` in centimeters and `weight` in kilograms to match existing `scraper.py` height behavior.
- Preserve existing non-null physical stats; fill only missing fields and set per-field metadata sources.
- Do not edit `.github/workflows/`.

### Final Review: Agent 63 — Fencer Physical Stats

- Files changed: `scrape_physical_stats.py`, `supabase/migrations/20260601_physical_stats.sql`, `tests/test_scrape_physical_stats.py`, `tasks/todo.md`.
- Behavior changed: added nullable physical-stat columns, FIE/Wikipedia parsing for height/weight/reach, per-field source metadata, row updates by `fs_fencers.id`, run logging, and scraper state summary.
- Verification: RED targeted run failed on missing `scrape_physical_stats` and missing migration; focused run `./.venv/bin/python -m pytest tests/test_scrape_physical_stats.py -v` passed 6 tests; `./.venv/bin/python -m py_compile scrape_physical_stats.py` passed; live non-mutating smoke check parsed Wikipedia `Arianna_Errigo` as height 181 cm and weight 64 kg, and handled a FIE profile with no physical stats.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected 482 tests but failed in unrelated in-progress areas with missing modules such as `scrape_cism`, `scrape_competition_details`, `scrape_wikipedia_bios`, `scrape_youth_majors`, and missing `.github/workflows/live_results.yml`.
- Remaining risk: FIE pages are inconsistent; the observed FIE sample did not expose physical stats, so FIE coverage depends on profile pages carrying recognizable height/weight/reach labels or JSON keys.

---

## Active Work: Agent 33 — Fencer Name Variant Database

- [x] Read relevant project lessons and current identity table contract.
- [x] Write failing tests for script detection, identity grouping, source dedupe, migration DDL, and Supabase upsert behavior.
- [x] Implement `compute_name_variants.py` using `fs_fencer_identities` row-id/FIE-id grouping.
- [x] Add `supabase/migrations/20260601_name_variants.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

---

## Active Work: Agent 60 — South American Games Scraper

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing Olympics scraper/test pattern and confirm continental-games scraper is absent in this checkout.
- [x] Probe Olympedia and ODESUR for South American Games fencing coverage and record viable public structures.
- [x] Write failing tests for Spanish/Portuguese event classification and result row parsing.
- [x] Implement `scrape_south_american_games.py` with edition/event discovery, result parsing, tournament/result upserts, run logging, and state tracking.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Source IDs must be `south_american_games:{edition_id}:{event_code}`.
- Probe result: Olympedia has Olympic/YOG fencing only; current `odesur.org` exposes no historical result tables; ASU2022 official URLs no longer resolve. Public structured medalist tables currently import for 2010 and 2022.
- Live parser verification found 2/12 historical editions with structured pages, 24 events, no duplicate `(edition_id, event_code)` keys, and no missing countries.
- Verification: `pytest tests/test_scrape_south_american_games.py -v` passed; `pytest tests/test_scrape_south_american_games.py tests/test_scrape_olympics.py -v` passed; `py_compile` passed. Full `pytest tests/ -v` is red in unrelated agent areas including Italy, Netherlands, Engarde, FRED, and IWAS.
- Do not edit `.github/workflows/`.

---

## Active Work: Agent 54 — Israel Federation Scraper

- [x] Read project lessons and current task state.
- [x] Inspect existing federation scraper patterns and shared helpers.
- [x] Probe `fencing.org.il`, Hebrew/English ranking paths, and linked public ranking endpoints; record URL/method/format/coverage.
- [x] Write failing parser tests with realistic Hebrew/English fixtures from the probed source shape.
- [x] Implement `scrape_fed_isr.py` with parser, fetcher, current season compatibility, run logging, and ranking writes.
- [x] Run focused verification and relevant scraper tests; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Keep scope to `scrape_fed_isr.py`, `tests/test_fed_isr.py`, and task/wiki memory.
- Do not edit `.github/workflows/`.
- Probe result: `/ranking`, `/rankings`, `/he/ranking`, and `/תחרויות` return 404; `/דירוג` is veteran-only XLSX links; current `https://podiumcomp.com/site/isrisf` returns Cloudflare 403 (`cf-mitigated: challenge`); `https://www.fencing.org.il/דירוגים-עונה-2023-2024/` publishes all 12 Senior/Junior Foil/Epee/Sabre Men/Women XLSX files via GET.

Final review:
- Files changed: `scrape_fed_isr.py`, `tests/test_fed_isr.py`, `tasks/todo.md`.
- Behavior changed: adds Israel federation scraper for 2023-2024 public XLSX archive; preserves Hebrew names; records current PodiumComp URL as blocked metadata.
- Verification: `pytest tests/test_fed_isr.py -v` passed 7/7; federation/common regression subset passed 17/17; live GET+parse verified rows for 12/12 combos.
- Remaining risk: full `pytest tests/ -v` stops during collection on missing unrelated `scrape_cac_games` module.

---

## Active Work: Agent 67 — Equipment Reviews Database

- [x] Read project lessons and current task state.
- [x] Inspect existing scraper, Supabase, and test patterns.
- [x] Probe known fencing retailer product listing URLs and record viable source structures.
- [x] Write failing parser/upsert/migration tests using realistic listing fixtures.
- [x] Implement `scrape_equipment_reviews.py` with parser, fetcher, Supabase upsert, run logging, and state tracking.
- [x] Add `supabase/migrations/20260601_equipment_reviews.sql` for `fs_equipment_reviews`.
- [x] Run focused and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Populate from at least three retailers; prioritize Absolute Fencing, Leon Paul, and Blue Gauntlet when probes are viable.
- Keep changes scoped to `scrape_equipment_reviews.py`, `tests/test_equipment_reviews.py`, the equipment migration, and task/wiki memory.
- Do not edit `.github/workflows/`.

Probe findings:
- Absolute Fencing Gear: `https://www.absolutefencinggear.com/uniforms/lame/foil`, Magento `li.product-item`, 14 products.
- Leon Paul: `https://www.leonpaul.com/fencing-clothing-uniforms.html`, Magento `li.product-item`, 17 products in live dry-run.
- Blue Gauntlet: `https://www.blue-gauntlet.com/`, `.product-item.alternative`, 3 featured products.
- Allstar: `https://allstar.de/en/clothing-footwear/electric-jackets/`, Shopware `.product-box`, 24 products in live dry-run.

### Final Review: Agent 67 — Equipment Reviews Database

- Files changed: `scrape_equipment_reviews.py`, `tests/test_equipment_reviews.py`, `supabase/migrations/20260601_equipment_reviews.sql`, `tasks/todo.md`.
- Behavior changed: added an equipment-review/product-listing scraper for Absolute Fencing, Leon Paul, Blue Gauntlet, and Allstar; extracts product name, inferred brand, category, price/currency, rating, review count, URL, metadata, and scrape timestamp; upserts idempotently to `fs_equipment_reviews` on `url`; records run log and `equipment_reviews:last_run` state.
- Migration changed: added `public.fs_equipment_reviews` with requested columns, URL uniqueness for upsert, value checks, RLS enabled, service-role DML grant, and source/brand indexes.
- Verification: `./.venv/bin/python -m pytest tests/test_equipment_reviews.py -v` passed 7 tests; `./.venv/bin/python -m py_compile scrape_equipment_reviews.py` passed; live dry-run with fake Supabase client parsed 58 products across 4 sources with 0 failed and 0 skipped.
- Full test command: latest `./.venv/bin/python -m pytest tests/ -v` run stopped at collection with unrelated `tests/test_scrape_ncaa_regular.py` importing missing `scrape_ncaa_regular`; an earlier full run before that file appeared showed all 7 equipment tests passing inside the suite but failed later on unrelated incomplete parallel agent modules/tests.
- Remaining risk: retailer DOMs can change; PBT and Fencing.net were probed but not included in the default source set because the probed pages did not expose stable product-card listing structure comparable to the four implemented sources.

---

## Active Work: Agent 59 — World Masters Games

- [x] Read relevant project lessons and current task state.
- [x] Inspect Olympics pattern plus current Masters scraper and tests.
- [x] Probe `imga.ch` and Olympedia source shape for veteran fencing results.
- [x] Write failing parser tests for veteran age-category extraction and result rows.
- [x] Implement scoped `scrape_masters_games.py` updates.
- [x] Run targeted and relevant verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Preserve veteran category/age band labels from event names.
- Use source IDs in the form `masters:{edition_id}:{event_code}`.
- Do not edit `.github/workflows/`.
- Source probe: IMGA public archive exposes fencing as PDFs. `Fencing-Results-WMG-1998.pdf` is image-only and is skipped with a warning. `All-fencing-results-2019.pdf` is extractable and live parser smoke test found 29 events, 150 rows, age categories `Cat.0`-`Cat.4`. The 2019 PDF exposes the country header but not row-level country values through pdfplumber, so rows keep `country=None` instead of guessing.
- Olympedia probe: no World Masters Games fencing result tables found; scraper uses IMGA archive sources.
- Changed files: `scrape_masters_games.py`, `tests/test_scrape_masters_games.py`, `tasks/todo.md`.
- Verification: `pytest tests/test_scrape_masters_games.py -v` passed (`5 passed`); `py_compile scrape_masters_games.py` passed; `pytest tests/test_scrape_olympics.py tests/test_scrape_masters_games.py -v` passed (`9 passed`); live read-only IMGA parser smoke passed with the image-only warning above.
- Full suite note: final `pytest tests/ -q` is not clean in this checkout: 633 passed, 6 failed, all in unrelated `tests/test_scrape_iwas.py`.

---

## Active Work: Agent 58 — Maccabiah Games

- [x] Read relevant project lessons and current task state.
- [x] Probe Olympedia and `maccabiah.com` for public Maccabiah fencing result structures.
- [x] Inspect `scrape_olympics.py`, existing Maccabiah scraper state, and tests.
- [x] Write failing tests for olympedia-like tables, official-site rows, and no-results pages.
- [x] Implement `scrape_maccabiah.py` discovery/parsing/upsert behavior with state and run logging.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Use source IDs shaped as `maccabiah:{edition_id}:{event_code}`.
- Keep changes scoped to `scrape_maccabiah.py` and `tests/test_scrape_maccabiah.py`; do not edit `.github/workflows/`.
- Probe findings: Olympedia search/pages expose Olympic result tables and Maccabiah athlete mentions, not Maccabiah editions. `m21.maccabiah.com` links fencing to `https://engarde-service.com/app.php?id=2502G6`; Engarde endpoints expose structured 2022 Maccabiah individual/team data. `m20.maccabiah.com` fencing page is regulations-only and no public structured results were found.

Final review:
- Files changed: `scrape_maccabiah.py`, `tests/test_scrape_maccabiah.py`, `tasks/todo.md`.
- Behavior changed: Added Maccabiah fencing scraper with official Engarde discovery/results parsing, Olympedia-like HTML fallback parsing, official HTML table parsing, no-results stub documentation, Supabase tournament/result writes, state persistence, and run logging.
- Verification: `pytest tests/test_scrape_maccabiah.py -v` passed; `pytest tests/test_scrape_maccabiah.py tests/test_scrape_olympics.py -v` passed; `py_compile` passed; live smoke found 29 structured 2022 Maccabiah events plus one 2017 stub and parsed rows for all 29.
- Remaining risk: Full `pytest tests/ -v` is blocked before execution by unrelated missing module `scrape_ncaa_regular` imported by `tests/test_scrape_ncaa_regular.py`.

---

## Active Work: Agent 52 — Hong Kong Federation Scraper

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing federation ranking helpers, season utilities, and British scraper pattern.
- [x] Probe `fencing.org.hk` ranking URLs and record public ranking coverage.
- [x] Write failing parser tests with realistic bilingual Hong Kong fixtures.
- [x] Implement `scrape_fed_hkg.py` using `fed_rankings_common`, `ScraperRunLogger`, and `season_utils`.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `season_utils.py` exists in this checkout; Hong Kong scraper should use `normalize_season(current_fie_season())`.
- Probe result: `fencing.org.hk` candidate paths failed publicly; `http://www.hkfa.org.hk/EN/ranking.html?mID=8` and `TC/ranking.html?mID=8` list all 12 requested Open/Senior and U20/Junior PDF rankings.
- Live validation parsed all 12 combos with nonzero rows; first rows preserved English names and Traditional Chinese `metadata.alt_name`.
- Targeted tests pass: `.venv/bin/python -m pytest tests/test_fed_hkg.py -v` (8 passed).
- Full suite currently has unrelated pre-existing failures: 23 failed, 601 passed in `test_fed_sgp.py`, `test_scrape_engarde.py`, `test_scrape_iwas.py`, and `test_scrape_wikipedia_bios.py`.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_hkg.py`, `tests/test_fed_hkg.py`, `tasks/todo.md`.
- Behavior changed: added HKFA/HKG national federation scraper for 12 public Senior/Open and Junior/U20 PDF rankings, bilingual parser, PDF extraction, run logging, and tied-rank storage metadata.
- Verification performed: targeted HKG pytest passed (9/9), live no-write validation parsed 12/12 combos, py_compile passed, diff check passed. Full suite remains blocked by unrelated failures.
- Remaining risks: HKFA uses self-signed HTTPS, so scraper uses HTTP working URLs; source PDFs do not expose club values; tied published ranks are stored with unique rank slots and `metadata.published_rank` due shared upsert key limitations.

---

## Active Work: Agent 38 - Data Quality Automation

- [x] Read project lessons and current task state.
- [x] Inspect scraper state, run logger, existing table usage, and migration/test patterns.
- [x] Write failing tests for healthy views, all-stale critical state, orphan-count warning, and refresh failure.
- [x] Implement `scripts/data_quality_check.py` with materialized view refresh, view summaries, anomaly checks, state tracking, and run logging.
- [x] Add `supabase/migrations/20260601_coverage_views.sql` for data quality materialized views and refresh RPC.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- Supabase Python has no direct raw SQL execution in the existing project pattern, so the check script should refresh through a migration-created RPC.
- Avoid letting the `data_quality_check` run log mask stale main scraper modules when deciding whether all scrapers are stale.
- `fs_results` stores result country as `nationality`; orphan grouping should use `fs_tournaments.type` through `tournament_id`.
- Do not edit `.github/workflows/`.

### Final Review: Agent 38 Data Quality Automation

- Files changed: `scripts/data_quality_check.py`, `supabase/migrations/20260601_coverage_views.sql`, `tests/test_data_quality_check.py`, `tasks/todo.md`.
- Behavior changed: added materialized quality views, a service-role refresh RPC, deterministic data-quality reporting, stale-pipeline critical detection, source-coverage warnings, orphan-count baseline tracking in `scraper_state`, and run logging for the check.
- Verification: initial focused test run failed on missing `scripts.data_quality_check`; after implementation, `.venv/bin/python -m pytest tests/test_data_quality_check.py -v` passed with 5 tests, `.venv/bin/python -m py_compile scripts/data_quality_check.py` passed, and `git diff --check` passed.
- Full suite: latest `.venv/bin/python -m pytest tests/ -v` could not complete because unrelated collection now stops on missing `scrape_cac_games` for `tests/test_scrape_cac_games.py`; earlier full-suite attempts also hit unrelated missing/unfinished modules such as `enrich_locations`, `compute_country_analytics`, `compute_name_variants`, and existing IWAS parser failures.
- Remaining risks: migration was not applied to a live Supabase database in this session, so runtime validation of `REFRESH MATERIALIZED VIEW` ownership/grants remains pending until deployment.

---

## Active Work: Agent 26 — Fencer Transfer Tracker

- [x] Read project lessons and current task state.
- [x] Inspect ranking history, results, run logger, state, and Supabase patterns.
- [x] Write failing tests for confirmed consecutive-season transfers, uncertain same-season result transfers, idempotent upsert payloads, FIE ID fallback, and Wikidata nationality metadata cross-checks.
- [x] Implement `compute_transfers.py` with paginated fetches, deterministic transfer IDs, run logging, state summary, and optional nationality-history cross-reference.
- [x] Add `supabase/migrations/20260601_transfers.sql` for `fs_fencer_transfers`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fs_rankings_history` writers currently store `fie_fencer_id`; some deployments may also have `fencer_id`. Transfer computation should use `fencer_id` when present and fall back to mapping `fie_fencer_id` through `fs_fencers`.
- `fs_results` may use `nationality` and/or `country`; prefer `country` with `nationality` fallback.
- Use deterministic UUIDv5 IDs for idempotent upsert on `id`; nullable `competition_id` is not safe as the conflict key.
- Agent 64 is not present in this checkout. If `fs_fencers.metadata.nationality_history` exists, use it only as a metadata cross-check.

### Final Review: Agent 26 Fencer Transfer Tracker

- Files changed: `compute_transfers.py`, `supabase/migrations/20260601_transfers.sql`, `tests/test_transfers.py`, `tasks/todo.md`.
- Behavior changed: added confirmed transfer detection from consecutive `fs_rankings_history` seasons, uncertain transfer detection from same-season `fs_results`, FIE ID fallback through `fs_fencers`, deterministic UUIDv5 upsert IDs, run logging, state summary, and optional `metadata.nationality_history` cross-check.
- Verification: red run failed on missing `compute_transfers`; after implementation, `.venv/bin/python -m pytest tests/test_transfers.py -v` passed with 3 tests and `.venv/bin/python -m py_compile compute_transfers.py` passed.
- Full-suite check: `.venv/bin/python -m pytest tests/ -v` collected 175 tests; 155 passed and 20 failed in unrelated in-progress areas (`compute_country_analytics`, `compute_name_variants`, `enrich_nationality_history`, and existing IWAS parser expectations). Agent 26 tests passed in that run.
- Remaining risks: production row counts depend on deployed schema details; live population was not run because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are not set in this shell. The loader falls back from `fencer_id` to `fie_fencer_id`, but duplicate `fs_fencers` rows still choose a deterministic raw row until Agent 2 identity grouping is fully available.

---

## Active Work: Agent 44 — Sweden Federation Scraper

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing federation ranking helpers and British scraper pattern.
- [x] Probe `swefencing.se` ranking URLs and record format/coverage.
- [x] Write failing parser tests with realistic Swedish fixtures.
- [x] Implement `scrape_fed_swe.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `swefencing.se` and `www.swefencing.se` did not resolve. Current public federation page is `https://svenskfaktning.se/tavling/nationella-och-regionala-tavlingsserier/`.
- Public data source is Ophardt `GET text/html` at `https://fencing.ophardt.online/sv/search/rankings/3?season=2025`; Sweden national Senior/U20 Foil/Epee Men/Women are public, national Sabre Senior/U20 Men/Women are blank/missing.
- `season_utils.py` is present but `current_fie_season()` returned an older range on 2026-06-01, so `scrape_fed_swe.current_season()` computes the active end-year locally and uses `season_utils.normalize_season()` only for formatting.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_swe.py`, `tests/test_fed_swe.py`, `tasks/todo.md`.
- Behavior changed: added Sweden federation ranking scraper with Ophardt discovery/static fallback, Swedish/Ophardt parser, ranking date metadata, run logging, and skipped-combo reporting.
- Verification: `pytest tests/test_fed_swe.py -v` passed 9/9; `py_compile` passed; live no-write scraper run parsed 8/12 public combos with 0 failed and 4 skipped; full `pytest tests/ -v` is blocked by unrelated collection errors in `tests/test_scrape_cac_games.py` and `tests/test_scrape_youth_majors.py`.
- Remaining risks: Supabase write count was 0 in local validation because no Supabase credentials are configured; public national Sabre rankings are currently unavailable in the Ophardt national ranking table.

---

## Active Work: Agent 45 — Denmark Federation Scraper

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing federation ranking helpers, British scraper pattern, and Ophardt-based scraper pattern.
- [x] Probe `fencing.dk`, `faegtning.dk`, and Ophardt public ranking URLs; record format/coverage.
- [x] Write failing parser tests with realistic Danish Ophardt fixtures.
- [x] Implement `scrape_fed_den.py` using `fed_rankings_common`, `ScraperRunLogger`, public Ophardt discovery, and season fallback.
- [x] Run targeted and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fencing.dk/ranglister`, `/ranking`, and `/resultater/rangliste` redirect to `trekanten.org` and return 404.
- Current public DFF source is `https://www.faegtning.dk/staevner/ranglister/`, which links to Ophardt index `https://fencing.ophardt.online/en/search/rankings/10`.
- Ophardt index is public HTML via GET. Senior and U20 pages are linked for all six weapon/gender combinations; Junior Women Sabre currently has a public page with zero ranking rows.
- `season_utils.py` is present in this checkout, but its `current_fie_season()` is a start-year value while `season_to_string()` expects an end-year. Denmark computes the active `YYYY-YYYY` range locally and normalizes with `season_utils.normalize_season()` when available.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `scrape_fed_den.py`, `tests/test_fed_den.py`, `tasks/todo.md`.
- Behavior changed: new Denmark scraper discovers public Ophardt ranking URLs from the DFF index, parses Danish/Ophardt ranking tables, writes national ranking rows, logs failed/skipped combos, and records state metadata.
- Verification performed: red/green `pytest tests/test_fed_den.py -v`; live no-write parse check found 12/12 URLs, 11 combos with rows, 1 empty public combo; no-database entrypoint run exited 0 with failed=0 skipped=1; full `pytest tests/ -v` is blocked by unrelated missing `scrape_ncaa_regular`.
- Remaining risk: public Ophardt page structure or season-index default can change; scraper logs missing URLs and skips public empty pages without failing the run.

---

## Active Work: Agent 40 — Netherlands Federation Scraper

- [x] Read relevant project lessons and existing federation scraper patterns.
- [x] Probe `knfb.nl` ranking URLs and record public ranking coverage.
- [x] Write failing parser tests with realistic Dutch ranking fixtures.
- [x] Implement `scrape_fed_ned.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused and relevant full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Probe notes:
- `https://knfb.nl/{ranglijsten,wedstrijdsport/ranglijsten,rankings,ranking}` returned HTTP 200 text/html but no ranking content or links.
- Public KNAS rankings are linked from `knas.nl` and hosted at `https://knas.onzeranglijsten.net/`.
- Method: GET. Response format: server-rendered UTF-8 HTML tables.
- Public coverage: all 12 Senior/Junior Foil/Epee/Sabre Men/Women individual combos.
- Table headers: `Plaats`, `Schermer`, `Vereniging`, `Punten`; data rows contain rank, fencer ID, name, club ID, club, points.

Final review:
- Files changed: `scrape_fed_ned.py`, `tests/test_fed_ned.py`, `tasks/todo.md`.
- Behavior changed: added Netherlands KNAS scraper with fixed public ranking URL map, Dutch table parser, decimal-comma support, DNS/DQ/summary-row skipping, active-season fallback compatible with `season_utils.normalize_season()`, run logging, failed/skipped combo metadata, and Supabase ranking writes through `fed_rankings_common.write_rankings()`.
- Verification performed: red `pytest tests/test_fed_ned.py -v` failed on missing module; red season-boundary test caught stale shared season output; green `pytest tests/test_fed_ned.py -v` passed 11 tests; `py_compile` passed; live read-only parse check fetched 12/12 combos and parsed rows from all 12; no-write `main()` smoke parsed/would-write 626 rows with failed=0 skipped=0.
- Broader verification: `pytest tests/ -v` currently runs 643 tests with 636 passed and 7 unrelated failures in camps inline-name parsing and IWAS parser expectations.
- Remaining risk: KNAS `rls` IDs may change in a future season; scraper logs failed combos and skips cleanly, but URL remapping would be needed if the public index changes.

---

## Active Work: Agent 23 — Fencer Career Stats Aggregation

- [x] Read project lessons and current task state.
- [x] Inspect result, bout, identity-resolution, run logger, state, and upsert patterns.
- [x] Write failing tests for result aggregation, identity grouping, medal counts, rank averages, and bout touch totals.
- [x] Add `fs_fencer_career_stats` migration SQL.
- [x] Implement `compute_career_stats.py` with paginated fetches, identity-aware grouping, touch aggregation, run logging, state update, and batched upserts.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fs_fencer_identities` may be absent in some environments; career stats should fall back to raw `fs_results.fencer_id` grouping.
- Current lessons warn that `fs_fencers` can contain duplicate rows per person; prefer identity `canonical_id` grouping when available.
- Do not edit `.github/workflows/`.

Final review:
- Files changed: `compute_career_stats.py`, `supabase/migrations/20260601_career_stats.sql`, `tests/test_career_stats.py`, `tasks/todo.md`.
- Behavior changed: career stats aggregate result placements by canonical fencer identity when available, dedupe duplicate identity rows per tournament, add bout touch totals, and upsert into `fs_fencer_career_stats`.
- Verification: `tests/test_career_stats.py` passed; `py_compile` passed. Full `tests/ -v` ran and Agent 23 tests passed, but the suite still has unrelated failures in missing `compute_country_analytics`, `compute_name_variants`, `enrich_nationality_history`, missing/empty migrations for those agents, and existing IWAS parser expectations.
- Remaining risks: migration was not applied to a live Supabase database in this session; Data API access is intentionally not granted by the migration.

---

## Active Work: Agent 22 — Head-to-Head Stats Engine

- [x] Read relevant project lessons and existing bout schema.
- [x] Write failing tests for canonical pair aggregation, reversed bouts, null scores, missing IDs, missing weapon/date, and Supabase upsert behavior.
- [x] Implement `compute_head_to_head.py` with paginated reads, tournament weapon/date fallback, canonical UUID pairing, aggregation, run logging, and state summary.
- [x] Add `supabase/migrations/20260601_head_to_head.sql`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

### Final Review: Agent 22 — Head-to-Head Stats Engine

- Files changed: `compute_head_to_head.py`, `supabase/migrations/20260601_head_to_head.sql`, `tests/test_head_to_head.py`, `tasks/todo.md`.
- Behavior changed: added full recomputation of `fs_head_to_head` from scored `fs_bouts` rows with non-null `fencer_a`/`fencer_b`; groups by lower UUID first plus weapon; derives weapon/date from `fs_tournaments`; skips incomplete, malformed, same-fencer, or weaponless bouts; upserts on `fencer_a_id,fencer_b_id,weapon`; records run log and state.
- Verification: initial targeted red run failed with missing module/migration; `./.venv/bin/python -m pytest tests/test_head_to_head.py -v` passed with 3 tests; `./.venv/bin/python -m py_compile compute_head_to_head.py` passed.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected 152 tests, with 137 passed and 15 failed. The new H2H tests passed; failures were unrelated pre-existing/incomplete Agent areas: missing `compute_career_stats`, missing `compute_country_analytics`, missing `compute_transfers`, and existing IWAS parser expectations returning empty rows.
- Remaining risk: the compute job upserts current aggregate rows but does not delete stale `fs_head_to_head` rows for pairs/weapons that disappear from source bouts.

---

## Active Work: Agent 3 - Orphan Result Matching Engine

- [x] Inspect project lessons for fencer matching constraints.
- [x] Confirm `fs_results` and `fs_national_fed_rankings` matching columns from current code/schema notes.
- [x] Write failing tests for FIE ID, exact name/country, normalized name/country, fuzzy name/country, NCAA school, Olympedia athlete ID, ambiguity handling, and FIE priority.
- [x] Implement `scripts/match_orphan_results.py` with deterministic indexes, batch updates, unmatched logging, run logging, and state summary.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fs_results` uses `nationality` as the source country column, with some FIE rows also carrying `country`.
- `fs_national_fed_rankings` uses `country`, `fie_id`, nullable `fencer_id`, and JSON `metadata`.
- No `fs_fencer_identities` implementation is present in this checkout; match against raw `fs_fencers`.

### Final Review: Agent 3 - Orphan Result Matching Engine

- Files changed: `scripts/match_orphan_results.py`, `tests/test_orphan_matching.py`, `tasks/todo.md`.
- Behavior changed: added orphan matching for `fs_results` and `fs_national_fed_rankings` using FIE ID, exact/normalized/fuzzy name+country, NCAA `metadata.school`, and Olympedia `metadata.olympedia_athlete_id`; unmatched and ambiguous rows are written to `unmatched_orphans.log`.
- Verification: red run failed with missing `scripts` module; final focused run `./.venv/bin/python -m pytest tests/test_orphan_matching.py -v` passed with 11 tests.
- Full test command: `./.venv/bin/python -m pytest tests/ -v` collected 152 tests, with 137 passed and 15 failed in unrelated in-progress areas: missing `compute_career_stats`, missing `compute_country_analytics`, missing `compute_transfers`, and existing IWAS parser failures.
- Remaining risk: without Agent 2 identities, duplicate `fs_fencers` rows are resolved conservatively; same-FIE duplicates choose a deterministic row, but true same-country homonyms without a shared FIE ID remain ambiguous and logged.

---

## Active Work: Agent 7 — South Korea Federation Scraper

- [x] Read relevant project lessons and existing federation scraper patterns.
- [x] Probe `koreafencing.org` and record working public ranking URLs/API coverage.
- [x] Write failing parser tests with realistic Korean fixtures.
- [x] Implement `scrape_fed_kor.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused and relevant full verification.
- [x] Final review: files changed, behavior changed, verification, risks.

Probe notes:
- `koreafencing.org` and `www.koreafencing.org` did not resolve from network probes.
- Current public KFA site is `https://fencing.sports.or.kr/`, returning `200 text/html;charset=UTF-8`.
- Candidate national ranking paths such as `/ranking`, `/rank`, `/ranking/list`, `/ranking/rankList`, `/player/ranking`, `/api/rankings`, and `/api/ranking` returned Korean 404 pages.
- `/player/profList` is public registered-player HTML with `No`, `이름`, `소속`, etc., but no ranking points.
- `/player/nationalProfList` is public national-team roster HTML, but no ranking points.
- `/game/finishRank` is a public POST JSON competition result endpoint; completed event `COMPM00680` exposed senior individual Foil/Epee/Sabre Men/Women final standings with Hangul names, but this is competition result data, not national season rankings. Junior national ranking combos were not found.

### Final Review: Agent 7 — South Korea Federation Scraper

- Files changed: `scrape_fed_kor.py`, `tests/test_fed_kor.py`, `tasks/todo.md`.
- Behavior changed: added a conservative KFA scraper stub that logs probe evidence and skips all 12 standard ranking combos until a public national ranking endpoint is verified; parser supports Korean ranking tables, Hangul primary names, published romanized alternate names, decimal commas, summary/DNS/DQ row skipping, and probed KFA `finishRank` JSON shape.
- Verification: red run failed with missing `scrape_fed_kor`; final focused run `.venv/bin/python -m pytest tests/test_fed_kor.py -v` passed 6 tests. `.venv/bin/python -m py_compile scrape_fed_kor.py tests/test_fed_kor.py` passed. `.venv/bin/python scrape_fed_kor.py` exited 0 with `written=0`, `failed=0`, `skipped=12`, `combos_working=0/12`.
- Full test command: `.venv/bin/python -m pytest tests/ -v` collected 589 items but stopped on unrelated collection error `tests/test_scrape_ncaa_regular.py` missing `scrape_ncaa_regular`. Federation subset command `.venv/bin/python -m pytest tests/test_fed_*.py -v` passed the new KOR tests but failed unrelated incomplete agents: missing `scrape_fed_arg`, `scrape_fed_bra`, `scrape_fed_hkg`, and current `scrape_fed_italy` XLS parser expectations.
- Remaining risk: if KFA publishes national season ranking pages later, `RANKING_URL_TEMPLATES` must be populated after a fresh probe; the current scraper intentionally avoids writing competition final standings as national rankings.

## Active Work: Agent 15 — Egypt Federation Scraper

- [x] Read relevant project lessons and existing federation scraper patterns.
- [x] Probe `egfencing.com` and current Egypt public ranking URLs/API coverage.
- [x] Write failing parser/fetch tests with realistic Arabic/English fixtures.
- [x] Implement `scrape_fed_egy.py` using `fed_rankings_common`, `ScraperRunLogger`, and season fallback.
- [x] Run focused and relevant full verification.
- [x] Final review: files changed, behavior changed, verification, risks.

### Final Review: Agent 15 — Egypt Federation Scraper

- Files changed: `scrape_fed_egy.py`, `tests/test_fed_egy.py`, `tasks/todo.md`.
- Behavior changed: added Egypt national federation ranking scraping for 12 public Senior/Junior Foil/Epee/Sabre Men/Women detail pages, with Arabic/English table parsing, RTL name preservation, decimal-comma support, DNS/DQ/summary row skipping, run logging, and Supabase ranking-row writes.
- Probe evidence: `egfencing.com` resolves to `https://www.egfencing.com/`; public rankings are available as UTF-8 Arabic HTML at `https://www.fencingegypt.org/EFF/Ranking/OverallRankingDetails.aspx?OverAllRankingID=<id>`. Live read-only probe parsed all 12 configured combos.
- Verification: red run failed with missing `scrape_fed_egy`; final focused run `.venv/bin/python -m pytest tests/test_fed_egy.py -v` passed 11 tests. Live read-only probe returned `WORKING=12/12`.
- Full test command: `.venv/bin/python -m pytest tests/ -v` collected 579 items but stopped on unrelated collection error `tests/test_scrape_ncaa_regular.py` missing `scrape_ncaa_regular`.
- Remaining risk: the Egypt site is ASP.NET/WebForms and can change `OverAllRankingID` values; current detail pages are public GET HTML and should be reprobed if rankings disappear.

## Active Work: Agent 21 — Youth/Junior Major Results

- [x] Read relevant project lessons and existing FIE/Olympedia scraper patterns.
- [x] Probe `fs_tournaments`, FIE API, and Olympedia EYOF event structure.
- [x] Write failing tests for youth-major FIE filtering, EYOF parsing, upserts, and state tracking.
- [x] Implement `scrape_youth_majors.py` and `tests/test_scrape_youth_majors.py`.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Final review:
- Files changed: `scrape_youth_majors.py`, `tests/test_scrape_youth_majors.py`, `tasks/todo.md`.
- Behavior changed: adds Cadet/Junior World Championship discovery from FIE with month fallback for 500ing seasons, season-aware `source_id` handling for repeated FIE `competitionId` values, youth-world result scraping despite `hasResults=0`, Olympedia EYOF parser/upsert support, and `scraper_state` done markers.
- Probe findings: FIE exposes youth worlds for seasons 2003-2019 and 2021-2026; 2020 returns no youth-world season. FIE season-wide search fails for 2004, 2008, and 2009, but month fallback returns 18 events each. Olympedia `/editions` and `/sports/FEN` currently contain no EYOF markers; scraper supports EYOF if Olympedia adds EYOF edition rows or `EYOF_OLYMPEDIA_EDITIONS` is supplied.
- Verification: `tests/test_scrape_youth_majors.py` passed 9 tests; relevant FIE/Olympedia subset passed 20 tests; `py_compile` passed. Full `tests/ -v` collection is blocked by unrelated existing errors in `tests/test_scrape_cac_games.py` and `tests/test_scrape_ncaa_regular.py`.
- Remaining risks: live `fs_tournaments` missing-season query could not run because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are not set in this shell. EYOF cannot ingest live rows until Olympedia exposes EYOF pages or edition IDs are configured.

---

## Active Work: Agent 34 — Venue / Location Geocoding

- [x] Read relevant project lessons, task state, wiki notes, and existing scraper patterns.
- [x] Write failing tests for venue extraction, Nominatim parsing, incremental skips, rate-limit sleep, ungeocodable locations, duplicate venue aggregation, and tournament metadata linking.
- [x] Add `supabase/migrations/YYYYMMDD_venues.sql` defining `fs_venues` with unique `(name, city, country)`.
- [x] Implement `enrich_locations.py` with Nominatim geocoding, venue upsert, tournament metadata linking, run logging, and scraper state.
- [x] Run targeted and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Final review:
- Files changed: `enrich_locations.py`, `supabase/migrations/20260601_venues.sql`, `tests/test_venues.py`, `tasks/todo.md`.
- Behavior changed: adds `fs_venues`; geocodes tournament city/country via Nominatim with User-Agent and 1 req/sec spacing; extracts venue names from dash/known-venue patterns; reuses existing city geocodes; links tournaments through `metadata.venue_id`; records processed and ungeocodable locations in scraper state.
- Verification: Nominatim probe returned HTTP 200 and expected list response; `tests/test_venues.py -v` passed 10/10; `py_compile enrich_locations.py` passed; `git diff --check` passed.
- Full suite: `pytest tests/ -v` does not pass in current shared worktree. Latest run stops during collection because `tests/test_scrape_cac_games.py` imports missing `scrape_cac_games`.
- Remaining risks: venue extraction is heuristic; no live Supabase migration/application check was run; full-suite health is blocked by unrelated active agent files.

## Active Work: Agent 20 — NCAA Regular Season Results

- [x] Read relevant project lessons and task state.
- [x] Inspect existing NCAA, result, and bout scraper patterns.
- [x] Probe NCAA regular-season sources and record viable URL/data structure.
- [x] Write failing NCAA regular-season parser/upsert tests with realistic fixture data.
- [x] Implement `scrape_ncaa_regular.py` with tournament, result, and bout upserts.
- [x] Run focused and full verification.
- [x] Final review: files changed, behavior changed, verification, risks.

Final review:
- Files changed: `scrape_ncaa_regular.py`, `tests/test_scrape_ncaa_regular.py`, `tasks/todo.md`.
- Behavior changed: new NCAA regular-season scraper discovers recent ACC score-sheet PDFs, parses text-extractable dual-meet weapon sheets into bout rows, groups weapon sheets into dual-meet tournaments, summarizes per-fencer results, matches fencers by normalized name + USA, and upserts tournaments/results/bouts with state and run logging.
- Probe record: ACC score-sheet PDFs for 2022-2025 are public and text-extractable; 2026 ACC score-sheet PDFs currently return 404; Ivy public pages expose standings but FencingTimeLive bout data redirects to login; St. John's/Duke school PDFs probed as scanned/image-only or oversized and are skipped unless text becomes extractable.
- Verification: red test run failed first on missing `scrape_ncaa_regular`; focused `tests/test_scrape_ncaa_regular.py -v` passed 12/12; NCAA focused `tests/test_scrape_ncaa.py tests/test_scrape_ncaa_regular.py -v` passed 19/19; live no-write ACC parser sweep parsed 2022-2025 available PDFs into 56 dual meets and 1,512 bouts, with 2026 not found.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran 650 tests; Agent 20 tests passed, but suite ended with 13 unrelated failures in `tests/test_scholarships.py` and `tests/test_scrape_iwas.py`.
- Remaining risks: coverage is strongest for ACC text score sheets, not all top-50 NCAA programs; FencingTimeLive login and scanned school PDFs prevent public bout parsing without new credentials/OCR/source access; `fs_bouts.weapon`/`metadata` are attempted and stripped only if deployment schema rejects them.

---

## Active Work: Agent 35 — Live Results Watcher

- [x] Read relevant project lessons and existing result/bout/state/logger patterns.
- [x] Write failing tests for active tournament polling and new result/bout detection across checks.
- [x] Implement `watch_live_results.py` with active tournament query, FIE fetch/parse, state hashes, additive upserts, and run logging.
- [x] Run focused and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Final review:
- Files changed: `watch_live_results.py`, `tests/test_live_results.py`, `tasks/todo.md`.
- Behavior changed: live watcher queries active FIE tournaments, fetches competition pages, parses results and bouts, stores result/bout hashes in `fs_scraper_state`, upserts only newly observed rows, updates `last_checked`, and logs run metadata.
- Verification: `tests/test_live_results.py -v` passed; `tests/test_live_results.py tests/test_scrape_fie_history.py -v` passed; `py_compile` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran after requirements sync and reached 155 passed / 20 failed. Failures were unrelated pre-existing/missing agent-owned modules or migrations (`compute_country_analytics`, `compute_name_variants`, `enrich_nationality_history`) plus existing IWAS parser expectations.
- Remaining risks: assumes `fs_results` has a usable `tournament_id,fie_fencer_id` conflict target; if a deployment lacks it, add a migration or fallback path.

---

## Active Work: Agent 25 — Country Depth + Club Rankings

- [x] Read relevant project lessons and current task state.
- [x] Inspect existing ranking, Supabase upsert, run logging, and migration patterns.
- [x] Write failing tests for country depth buckets, ranked-row filtering, club normalization, and Supabase upsert behavior.
- [x] Implement `compute_country_analytics.py` with paginated `fs_fencers` reads, aggregations, run logging, and state summary.
- [x] Add `fs_country_depth` and `fs_club_rankings` migration.
- [x] Run focused and full verification; fix failures.
- [x] Final review: files changed, behavior changed, verification, risks.

Notes:
- `fs_fencer_identities` is preferred by project lessons, but this checkout has only tests/prompts for it; no current implementation or migration is present, so Agent 25 will aggregate raw `fs_fencers` rows.
- No external site probe is needed; this task reads existing Supabase tables only.

Final review:
- Files changed: `compute_country_analytics.py`, `supabase/migrations/20260601032714_country_club_rankings.sql`, `tests/test_country_analytics.py`, `tasks/todo.md`.
- Behavior changed: added country depth top-16/32/64 aggregation and normalized club rankings from `fs_fencers`, with paginated reads, batched Supabase upserts, run logging, and scraper state summary.
- Verification: red test run failed first for missing module/migration; focused tests passed (`tests/test_country_analytics.py`, 4 passed); syntax check passed; scoped regression passed with `tests/test_fed_rankings_common.py` (9 passed).
- Full suite: `.venv/bin/python -m pytest tests/ -v` could not complete because unrelated collection blockers remain for missing `discover_competition_urls`, `scripts.reconcile_data`, and `enrich_locations`.
- Remaining risks: `fs_fencer_identities` is not implemented in this checkout, so analytics intentionally aggregate raw `fs_fencers` rows; RLS is enabled on new public tables without read policies pending product/API access decisions.

---

## BATCH A: BUG FIXES (5 agents)

### A1 — Fix Italy Scraper (BIFF .xls parser)
- **Files:** `scrape_fed_italy.py`, `tests/test_fed_italy.py`, `requirements.txt`
- Add `xlrd` + `openpyxl` to requirements
- Federscherma.it serves rankings as .xls files (BIFF format) — download, parse, upsert
- Probe first to confirm current URL and file format
- **Deliverable:** Italy produces `fs_national_fed_rankings` rows

### A2 — Canonical Fencer Identity Resolution
- **Files:** `scripts/merge_fencer_identities.py`, `supabase/migrations/YYYYMMDD_fencer_identities.sql`, `tests/test_fencer_identity.py`
- New table: `fs_fencer_identities` (canonical_id uuid → all fie_ids + names for same person)
- Deduplicate `fs_fencers` rows where same person appears across weapons/categories
- Merge script: finds matches by (normalized name + country) and same `fie_id`
- **Deliverable:** Migration SQL + merge script + tests, fencer identity graph in DB

### A3 — Orphan Result Matching Engine
- **Files:** `scripts/match_orphan_results.py`, `tests/test_orphan_matching.py`
- Scan `fs_results` for rows with `fencer_id = NULL`
- Match by name+country against `fs_fencers` (improved: fuzzy match, club cross-ref)
- Batch update matched rows. Log unmatched for manual review
- **Deliverable:** Script that reduces NULL fencer_id results by 80%+

### A4 — Engarde Rewrite + Non-FIE Expansion
- **Files:** `scrape_engarde.py`, `tests/test_scrape_engarde.py`
- Current scraper hits 404 on many endpoints — rewrite with current Engarde API structure
- Implement pool/DE detail parsing (currently skipped)
- Add more Engarde event sources (UK, Ireland, Australia, etc.)
- **Deliverable:** Working Engarde scraper with bout data

### A5 — Compute Pipeline Cleanup
- **Files:** `compute_national_rankings.py`, `tests/test_compute_rankings.py`, `fed_rankings_common.py`, `season_utils.py`
- Fix `result_weight` to use tournament `type` field instead of string matching
- New `season_utils.py`: `season_to_string()`, `season_from_string()`, `current_fie_season()`
- Add weapon combo dedup in `scraper.py` (prevent race conditions on upsert)
- **Deliverable:** Accurate ranking computation, clean season utils

---

## BATCH B: FEDERATION SCRAPERS — TIER 1 (10 agents)

Each follows exact pattern: `scrape_fed_{country}.py`, `tests/test_fed_{country}.py`, probe-first, `fed_rankings_common.py` interface.

### B1 — Hungary (MVSZ)
- **Source:** hunfencing.hu / magyarvivaszszovetseg.hu
- **Deliverable:** Hungary national rankings

### B2 — South Korea (KFA)
- **Source:** koreafencing.org — Korean HTML, Hangul text extraction
- **Deliverable:** South Korea national rankings

### B3 — China (CFA)
- **Source:** fencing.org.cn — Chinese HTML, CJK text handling
- **Deliverable:** China national rankings

### B4 — Japan (JFA)
- **Source:** fencing-jpn.jp — Japanese HTML
- **Deliverable:** Japan national rankings
- **Agent 9 plan:** Probe source URLs; add parser tests for Japanese PDF-derived ranking text; implement `scrape_fed_jpn.py` with 12 public Senior/Junior Foil/Epee/Sabre Men/Women PDF URLs; add `pdfplumber` dependency; run `pytest tests/test_fed_jpn.py -v`.
- **Probe status:** `fencing-jpn.jp` public PDF assets work for all 12 combos; `jfa-fencing.jp` DNS failed; `/cms/wp-json/` routes returned 404.
- **Final review:** Added PDF-backed Japan scraper and parser tests. Live no-write parse returned rows for 12/12 public PDFs. `pytest tests/test_fed_jpn.py -v` passed 8/8. Full `pytest tests/ -v` is blocked by unrelated collection errors after dependency sync: missing `scrape_cac_games.py` and a syntax error in `tests/test_scrape_youth_majors.py`; broad federation glob now also includes unrelated in-progress Italy XLS tests.

### B5 — Russia (RUS)
- **Source:** rusfencing.ru — Russian HTML
- **Deliverable:** Russia national rankings

### B6 — Poland (PZS)
- **Source:** pzszerm.pl — Polish HTML
- **Deliverable:** Poland national rankings

### B7 — Ukraine (NFFU)
- **Source:** fencing.ua or nffu.gov.ua
- **Deliverable:** Ukraine national rankings

### B8 — Romania (FR)
- **Source:** federatia-de-scrima.ro
- **Deliverable:** Romania national rankings

### B9 — Spain (RFEE)
- **Source:** rfeespada.es
- **Deliverable:** Spain national rankings

### B10 — Egypt (EGF)
- **Source:** egfencing.com — English/Arabic HTML or PDF
- **Deliverable:** Egypt + first African federation rankings

---

## BATCH C: NEW COMPETITION SOURCES — TIER 1 (6 agents)

### C1 — USA Fencing FRED Results
- **Files:** `scrape_fred.py`, `tests/test_scrape_fred.py`
- USA Fencing's new FRED platform replacing AskFRED — API discovery probe
- **Deliverable:** USA domestic tournament results

### C2 — Youth Olympics + World Fencing Games
- **Files:** `scrape_youth_olympics.py`, `tests/test_scrape_youth_olympics.py`
- Youth Olympic Games (2010, 2014, 2018, 2026) + World Fencing Games (2023+)
- **Deliverable:** YOG + WFG tournament+results

### C3 — Universiade / World University Fencing
- **Files:** `scrape_universiade.py`, `tests/test_scrape_universiade.py`
- FISU World University Games — source: fisu.net or olympedia
- **Deliverable:** University Games tournament+results

### C4 — Continental Games
- **Files:** `scrape_continental_games.py`, `tests/test_scrape_continental_games.py`
- Pan American, Asian, European, African Games
- **Deliverable:** Continental multi-sport fencing results

### C5 — NCAA Regular Season Results
- **Files:** `scrape_ncaa_regular.py`, `tests/test_scrape_ncaa_regular.py`
- Individual NCAA dual meet results (beyond existing championship scraper)
- Top-50 programs focus
- **Deliverable:** NCAA regular season bout data

### C6 — Youth/Junior Major Results
- **Files:** `scrape_youth_majors.py`, `tests/test_scrape_youth_majors.py`
- Cadet/Junior Worlds, EFC Cadet/Junior Circuit, EYOF
- **Deliverable:** Complete youth/junior results

---

## BATCH D: AGGREGATION & ANALYTICS — TIER 1 (5 agents)

### D1 — Head-to-Head Stats Engine
- **Files:** `compute_head_to_head.py`, `supabase/migrations/YYYYMMDD_head_to_head.sql`, `tests/test_head_to_head.py`
- Aggregate `fs_bouts` into `fs_head_to_head`: fencer_a, fencer_b, weapon, wins, touches, last_meeting
- **Deliverable:** Queryable H2H records for every fencer pair

### D2 — Fencer Career Stats Aggregation
- **Files:** `compute_career_stats.py`, `supabase/migrations/YYYYMMDD_career_stats.sql`, `tests/test_career_stats.py`
- Per fencer: total competitions, medals by tier, best/avg rank, weapons used, category transitions
- **Deliverable:** Career stats for every fencer in DB

### D3 — Rankings Trends + Points Projection
- **Files:** `compute_rankings_trends.py`, `supabase/migrations/YYYYMMDD_rankings_trends.sql`, `tests/test_rankings_trends.py`
- Ranking trajectory (↑↓→ per season), points projection estimator
- **Deliverable:** Fencer ranking trends + projected ranks

#### Agent 24 plan
- [x] Add tests for rank/points trend deltas, first appearances, grouping, gaps, and Supabase upsert behavior.
- [x] Add `fs_rankings_trends` migration with composite conflict key.
- [x] Implement `compute_rankings_trends.py` with paged history loading, pure trend computation, batched upserts, and run logging.
- [x] Run targeted rankings trend tests.
- [x] Run full test suite; current tree stops on unrelated collection errors for missing `scripts.data_quality_check` and `scripts.download_headshots`.

### Final Review: Agent 24 Rankings Trends + Points Projection
- Files changed: `compute_rankings_trends.py`, `supabase/migrations/20260601_rankings_trends.sql`, `tests/test_rankings_trends.py`, `tasks/todo.md`.
- Behavior changed: computes per-fencer/weapon/category ranking trends from `fs_rankings_history`, writes `up`/`down`/`stable`/`new`, rank/points deltas, and 3-season weighted moving-average projections to `fs_rankings_trends`.
- Verification: `./.venv/bin/python -m pytest tests/test_rankings_trends.py -v` passed with 6 tests; `./.venv/bin/python -m py_compile compute_rankings_trends.py` passed.
- Full suite: `./.venv/bin/python -m pytest tests/ -v` currently fails during collection on unrelated missing modules `scripts.data_quality_check` and `scripts.download_headshots`.
- Remaining risks: `fs_rankings_trends.fencer_id` stores FIE IDs from `fs_rankings_history.fie_fencer_id` because current ranking history rows do not expose local `fs_fencers.id`.

### D4 — Country Depth + Club Rankings
- **Files:** `compute_country_analytics.py`, `supabase/migrations/YYYYMMDD_country_club_rankings.sql`, `tests/test_country_analytics.py`
- Per-country squad depth (top 16/32/64), club rankings
- **Deliverable:** Country power rankings + club leaderboards

### D5 — Fencer Transfer Tracker
- **Files:** `compute_transfers.py`, `supabase/migrations/YYYYMMDD_transfers.sql`, `tests/test_transfers.py`
- Detect country changes across seasons from rankings history
- **Deliverable:** Fencer nationality change database

---

## BATCH E: ENRICHMENT & MEDIA — TIER 1 (4 agents)

### E1 — Wikipedia Bio Text Enrichment
- **Files:** `scrape_wikipedia_bios.py`, `tests/test_scrape_wikipedia_bios.py`
- Fetch Wikipedia abstracts via REST API for fencers with wikidata_id
- New column: `bio_text`, also `nickname`, `birth_place`, `height`, `weight`
- **Deliverable:** Fencer biographies for 2000+ fencers

### E2 — Fencer Social Media Presence
- **Files:** `scrape_social_media.py`, `supabase/migrations/YYYYMMDD_social_media.sql`, `tests/test_social_media.py`
- Wikidata social media properties + federation profile scraping
- **Deliverable:** Social media links for fencers

### E3 — Fencer Media Pipeline
- **Files:** `scripts/download_headshots.py`, `supabase/storage/`
- Download headshots to Supabase Storage, resize, serve via CDN
- YouTube match video discovery
- **Deliverable:** Self-hosted headshot gallery + match video links

### E4 — Equipment & Brand Data
- **Files:** `scrape_equipment.py`, `supabase/migrations/YYYYMMDD_equipment.sql`, `tests/test_equipment.py`
- Equipment sponsors per fencer from FIE profiles, federation sites, forums
- **Deliverable:** What each fencer uses + who sponsors them

---

## BATCH F: NEW COMPETITION SOURCES — TIER 2 (2 agents)

### F1 — Paralympic Games Fencing
- **Files:** `scrape_paralympics.py`, `tests/test_scrape_paralympics.py`
- Paralympic fencing from olympedia.org (1980 Roma → present)
- **Deliverable:** Complete Paralympic fencing history

### F2 — Fencing News + Injury/Absence Tracker
- **Files:** `scrape_news.py`, `supabase/migrations/YYYYMMDD_news.sql`, `tests/test_news.py`
- Scrape FIE news, federation press, fencing sites
- NLP classify: "competition_report", "injury", "transfer", "rule_change", "general"
- Track injury/absence mentions for fencer availability
- **Deliverable:** Fencing news archive + injury tracking

---

## BATCH G: AGGREGATION & ANALYTICS — TIER 2 (2 agents)

### G1 — Fencer Name Variant Database
- **Files:** `compute_name_variants.py`, `supabase/migrations/YYYYMMDD_name_variants.sql`, `tests/test_name_variants.py`
- All name spellings across sources, per fencer identity
- Handle Hangul/Cyrillic/CJK/Arabic alongside Latin
- **Deliverable:** Multi-script fencer name lookup

### G2 — Venue / Location Geocoding
- **Files:** `enrich_locations.py`, `supabase/migrations/YYYYMMDD_venues.sql`, `tests/test_venues.py`
- Extract venue names, geocode all tournament locations
- New table: `fs_venues`
- **Deliverable:** Geocoded fencing venue database

---

## BATCH H: DATA PRODUCT & INFRASTRUCTURE — TIER 1 (5 agents)

### H1 — Live Results Watcher
- **Files:** `watch_live_results.py`, `tests/test_live_results.py`
- Separate 15-min GitHub Actions workflow
- Poll FIE results feed for in-progress competitions
- **Deliverable:** Near-real-time competition results

### H2 — Referee & Coach Data
- **Files:** `scrape_referees.py`, `scrape_coaches.py`, `tests/test_referees.py`, `supabase/migrations/YYYYMMDD_referees.sql`
- FIE referee list, national team coaches per federation
- fencer→coach relationships
- **Deliverable:** Complete FIE referee database + coaches

### H3 — FIE Competition URL ID Discovery
- **Files:** `discover_competition_urls.py`, `tests/test_discover_urls.py`
- Extract from `scrape_results.py` as standalone step
- Finds `competition_url_id` for tournaments missing it
- **Deliverable:** More tournaments get results scraped

### H4 — Data Quality Automation
- **Files:** `scripts/data_quality_check.py`, `supabase/migrations/YYYYMMDD_coverage_views.sql`
- Daily coverage report, schema validation, staleness alerts
- Views: `v_fencer_source_coverage`, `v_scraper_health`
- **Deliverable:** Automated data quality monitoring

### H5 — Export API + CLI
- **Files:** `api.py`, `cli_export.py`, `supabase/edge_functions/`, `docs/api.yaml`
- REST API (key-auth, rate-limited), CLI export tool, OpenAPI spec
- **Deliverable:** The "people would pay for" API layer

---

## BATCH I: FEDERATION SCRAPERS — TIER 2 (15 agents)

Same pattern as Batch B: probe first, `scrape_fed_{cc}.py`, tests, `fed_rankings_common.py`.

### I1 — Netherlands (NFF)
- **Source:** knfb.nl
- **Deliverable:** Netherlands national rankings

### I2 — Belgium (FBB)
- **Source:** fencing-belgium.be
- **Deliverable:** Belgium national rankings

### I3 — Switzerland (Swiss Fencing)
- **Source:** swiss-fencing.ch
- **Deliverable:** Switzerland national rankings

### I4 — Austria (ÖFV)
- **Source:** fencing.at
- **Deliverable:** Austria national rankings

### I5 — Sweden (SFF)
- **Source:** swefencing.se
- **Deliverable:** Sweden national rankings

### I6 — Denmark (DFF)
- **Source:** fencing.dk
- **Deliverable:** Denmark national rankings

### I7 — Norway (NFF)
- **Source:** fencing.no
- **Deliverable:** Norway national rankings

### I8 — Finland (SLY)
- **Source:** fencing.fi
- **Deliverable:** Finland national rankings

### I9 — Australia (AFF)
- **Source:** ausfencing.org
- **Deliverable:** Australia national rankings

### I10 — New Zealand (NZFA)
- **Source:** fencing.org.nz
- **Deliverable:** New Zealand national rankings

### I11 — Brazil (CBE)
- **Source:** cbesgrima.org.br — Portuguese HTML
- **Deliverable:** Brazil national rankings

### I12 — Argentina (FAA)
- **Source:** esgrima.org.ar — Spanish HTML
- **Deliverable:** Argentina national rankings

### I13 — Hong Kong (HKFA)
- **Source:** fencing.org.hk — English/Chinese
- **Deliverable:** Hong Kong national rankings

### I14 — Singapore (FFS)
- **Source:** fencing.org.sg
- **Deliverable:** Singapore national rankings

### I15 — Israel (IFA)
- **Source:** fencing.org.il — Hebrew/English
- **Deliverable:** Israel national rankings

---

## BATCH J: MORE COMPETITION SOURCES — TIER 3 (8 agents)

### J1 — Commonwealth Fencing Championships
- **Files:** `scrape_commonwealth.py`, `tests/test_scrape_commonwealth.py`
- Commonwealth fencing results — source: commonwealtfencing.org or olympedia
- **Deliverable:** Commonwealth fencing tournament+results

### J2 — CISM World Military Games
- **Files:** `scrape_cism.py`, `tests/test_cism.py`
- World Military Sports Council fencing results
- **Deliverable:** Military Games fencing results

### J3 — Mediterranean Games
- **Files:** `scrape_mediterranean_games.py`, `tests/test_mediterranean_games.py`
- Mediterranean Games fencing (1951+)
- **Deliverable:** Mediterranean Games results

### J4 — Maccabiah Games
- **Files:** `scrape_maccabiah.py`, `tests/test_maccabiah.py`
- Maccabiah Games fencing (Jewish Olympics)
- **Deliverable:** Maccabiah fencing results

### J5 — World Masters Games
- **Files:** `scrape_masters_games.py`, `tests/test_masters_games.py`
- World Masters Games veteran fencing
- **Deliverable:** Masters Games results

### J6 — South American Games
- **Files:** `scrape_south_american_games.py`, `tests/test_south_american_games.py`
- ODESUR Games fencing results (1978+)
- **Deliverable:** South American Games results

### J7 — Central American & Caribbean Games
- **Files:** `scrape_central_american_games.py`, `tests/test_central_american_games.py`
- CAC Games fencing results (1938+)
- **Deliverable:** CAC Games results

### J8 — Island Games / Oceania Games
- **Files:** `scrape_island_games.py`, `tests/test_island_games.py`
- NatWest Island Games and Oceania Zonal Championships fencing
- **Deliverable:** Island/Oceania fencing results

---

## BATCH K: ENRICHMENT — TIER 2 (7 agents)

### K1 — Fencer Physical Stats
- **Files:** `scrape_physical_stats.py`, `tests/test_scrape_physical_stats.py`
- Height, reach, weight from FIE athlete profiles + Wikipedia
- **Deliverable:** Complete physical measurements for fencers

### K2 — Fencer Nationality History
- **Files:** `enrich_nationality_history.py`, `tests/test_nationality_history.py`
- Country of citizenship + country of birth from Wikidata
- Naturalization date tracking
- **Deliverable:** Nationality history per fencer

### K3 — Competition Format & Prize Money
- **Files:** `scrape_competition_details.py`, `supabase/migrations/YYYYMMDD_competition_details.sql`, `tests/test_competition_details.py`
- Format (pool size, DE rounds), entry fees, prize money from FIE + competition sites
- New table: `fs_competition_details`
- **Deliverable:** Competition metadata enrichment

### K4 — Fencing Club Ratings & Reviews
- **Files:** `scrape_club_reviews.py`, `tests/test_club_reviews.py`
- Scrape fencing club reviews from Google Maps, fencing forums
- Aggregate ratings, number of coaches, member count
- **Deliverable:** Club quality metrics database

### K5 — Equipment Reviews Database
- **Files:** `scrape_equipment_reviews.py`, `supabase/migrations/YYYYMMDD_equipment_reviews.sql`, `tests/test_equipment_reviews.py`
- Scrape fencing equipment reviews from retailers, forums, youtube
- Brand, model, rating, price bracket
- **Deliverable:** Fencing gear review database

### K6 — Training Camps Directory
- **Files:** `scrape_training_camps.py`, `supabase/migrations/YYYYMMDD_camps.sql`, `tests/test_camps.py`
- Scrape fencing camp listings from federation sites, camp aggregators
- Location, dates, coaches, cost per camp
- **Deliverable:** Fencing training camp directory

### K7 — US College Fencing Scholarships
- **Files:** `scrape_college_scholarships.py`, `supabase/migrations/YYYYMMDD_scholarships.sql`, `tests/test_scholarships.py`
- NCAA fencing scholarship data per college
- Roster size, scholarship availability, coach contact
- **Deliverable:** College fencing scholarship database

---

## BATCH L: ANALYTICS — TIER 3 (5 agents)

### L1 — Strength of Field Metric
- **Files:** `compute_strength_of_field.py`, `supabase/migrations/YYYYMMDD_strength_of_field.sql`, `tests/test_strength_of_field.py`
- Per competition: average world rank of participants, number of top-16 fencers
- Competition difficulty score (weighted by fencer quality)
- **Deliverable:** Competition difficulty ratings

### L2 — Performance vs Ranking Prediction
- **Files:** `compute_performance_analysis.py`, `tests/test_performance_analysis.py`
- Expected rank vs actual rank analysis per fencer
- Over-performers and under-performers: who exceeds their seed
- **Deliverable:** Fencer "clutch" metric

### L3 — Medal Table Aggregation
- **Files:** `compute_medal_tables.py`, `supabase/migrations/YYYYMMDD_medal_tables.sql`, `tests/test_medal_tables.py`
- Medal counts: per country, per fencer, per competition tier, per edition
- Historical medal table for every Olympic/World Championship
- **Deliverable:** Complete fencing medal tables

### L4 — Fencer Longevity Analysis
- **Files:** `compute_longevity.py`, `tests/test_longevity.py`
- Career length, competitions per season, active vs retired detection
- Age at first/last competition
- **Deliverable:** Fencer career longevity metrics

### L5 — Weapon Specialization Analysis
- **Files:** `compute_specialization.py`, `tests/test_specialization.py`
- Multi-weapon vs single-weapon success rates
- Category transition analysis (Junior→Senior conversion rates)
- Weapon switching patterns
- **Deliverable:** Weapon specialization insights

---

## BATCH M: DATA INFRASTRUCTURE (5 agents)

### M1 — Supabase RLS + Multi-Tenant Access
- **Files:** `supabase/migrations/YYYYMMDD_rls_policies.sql`
- Row-level security policies for public vs authenticated access
- API key-based tenant isolation for paying subscribers
- Read-only views for public consumption
- **Deliverable:** Secure multi-tenant data access

### M2 — Scraper Rate Limiting Service
- **Files:** `scripts/rate_limiter.py`, `tests/test_rate_limiter.py`
- Centralized rate limiter shared across all scrapers
- Per-domain delay, jitter, backoff configuration
- Prevents IP blocking from any source
- **Deliverable:** Polite, configurable rate limiting

### M3 — Schema Migration Tooling
- **Files:** `scripts/migrate.py`, `supabase/migrations/README.md`
- CLI tool to apply migrations in order
- Migration template generator
- Dry-run mode for safety
- **Deliverable:** Clean schema management

### M4 — Scraper Health Monitoring Dashboard
- **Files:** `dashboard/app.py`, `dashboard/queries.sql`
- Streamlit dashboard showing scraper status, data counts, error rates
- Success/failure trends per source
- Coverage maps by country
- **Deliverable:** Live scraper health dashboard

### M5 — Cross-Source Data Reconciliation
- **Files:** `scripts/reconcile_data.py`, `tests/test_reconcile.py`
- Compare overlapping data across sources (e.g., FIE vs federation rankings)
- Flag discrepancies: name spelling, rank, points
- Automated reconciliation report
- **Deliverable:** Cross-source data trust metrics

---

## FINAL MERGE: CI + SCHEMA

### Z1 — CI Workflow Merge
- **Files:** `.github/workflows/scraper.yml`, `.github/workflows/live_results.yml`, `.github/workflows/weekly_analytics.yml`
- Merge all new scraper steps into correct CI workflows
- 6-hour cron: all scrapers + enrichment + compute
- 15-min cron: live results watcher only
- Weekly cron: full analytics recompute
- **Deliverable:** Complete CI pipeline — 80 agents integrated without conflicts

---

## Summary Table

| Batch | Count | Category | Key Files Created |
|-------|-------|----------|-------------------|
| A | 5 | Bug fixes | scrape_fed_italy.py, merge_fencer_identities.py, match_orphan_results.py, scrape_engarde.py, compute_national_rankings.py |
| B | 10 | Federation T1 | scrape_fed_{hun,kor,chn,jpn,rus,pol,ukr,rou,esp,egy}.py |
| C | 6 | Competition T1 | scrape_fred.py, scrape_youth_olympics.py, scrape_universiade.py, scrape_continental_games.py, scrape_ncaa_regular.py, scrape_youth_majors.py |
| D | 5 | Analytics T1 | compute_head_to_head.py, compute_career_stats.py, compute_rankings_trends.py, compute_country_analytics.py, compute_transfers.py |
| E | 4 | Enrichment T1 | scrape_wikipedia_bios.py, scrape_social_media.py, download_headshots.py, scrape_equipment.py |
| F | 2 | Competition T2 | scrape_paralympics.py, scrape_news.py |
| G | 2 | Analytics T2 | compute_name_variants.py, enrich_locations.py |
| H | 5 | Data product T1 | watch_live_results.py, scrape_referees.py, discover_competition_urls.py, data_quality_check.py, api.py, cli_export.py |
| I | 15 | Federation T2 | scrape_fed_{ned,bel,sui,aut,swe,den,nor,fin,aus,nzl,bra,arg,hkg,sgp,isr}.py |
| J | 8 | Competition T3 | scrape_commonwealth.py, scrape_cism.py, scrape_mediterranean.py, scrape_maccabiah.py, scrape_masters.py, scrape_south_american.py, scrape_cac.py, scrape_island_games.py |
| K | 7 | Enrichment T2 | scrape_physical_stats.py, enrich_nationality.py, scrape_competition_details.py, scrape_club_reviews.py, scrape_equipment_reviews.py, scrape_camps.py, scrape_scholarships.py |
| L | 5 | Analytics T3 | compute_strength_of_field.py, compute_performance_analysis.py, compute_medal_tables.py, compute_longevity.py, compute_specialization.py |
| M | 5 | Infrastructure | RLS migration, rate_limiter.py, migrate.py, dashboard/, reconcile_data.py |
| Z | 1 | CI merge | .github/workflows/*.yml |
| **Total** | **80** | | |

---

## Key Constraints for All Agents

1. **Tests-first:** Write failing test fixtures with real HTML/JSON samples before implementing parser
2. **No cross-dependencies:** Each agent works on its own files — no agent edits another agent's code
3. **Existing patterns:** ScraperRunLogger, scraper_state, supabase upsert on_conflict, fed_rankings_common
4. **continue-on-error:** Never break the pipeline
5. **Idempotent:** Safe to rerun — incremental state, conflict-aware upserts
6. **CI edits:** ONLY Agent Z1 touches workflow files — all other agents provide CI YAML snippets in their deliverable notes
7. **Probe first:** Run a probe script to confirm URL structure before writing any parser code
8. **Non-Latin scripts:** Use regex + transliteration for Hangul/Cyrillic/CJK/Arabic name matching
9. **Data source dies?** Document the dead URL and move on — don't block on one source

---

## Active: A1 Fix Italy Scraper (BIFF XLS)

Plan:
- [x] Read lessons, current task state, wiki notes, and relevant scraper/common files.
- [x] Probe Federscherma ranking URLs and confirm XLS download structure.
- [x] Add workbook parser tests for XLSX, BIFF XLS, column mapping, empty sheet, and header-only sheet.
- [x] Add `xlrd`, `openpyxl`, and BIFF test generation support to requirements.
- [x] Replace Italy HTML parsing path with XLS discovery/download/parsing.
- [x] Run focused and full relevant verification.
- [x] Record final review with changed files, behavior, verification, and risks.

### Final Review: A1 Fix Italy Scraper

- Files changed: `scrape_fed_italy.py`, `tests/test_fed_italy.py`, `requirements.txt`, `tasks/todo.md`.
- Behavior changed: Italy scraper now discovers latest Federscherma Senior/Junior ranking documents via WordPress REST, downloads the document-manager spreadsheet, parses OpenXML first and BIFF XLS via `xlrd` fallback, filters the six weapon/gender sheets per category, and writes rows through `fed_rankings_common.write_rankings()`.
- Probe record: `/classifiche/` still redirects to the old 2010 post; current documents are `RANKING ASSOLUTI 2025-26 N.20/26` (`ID_file=202391`) and `RANKING GIOVANI 2025-2026 N.14/26` (`ID_file=200196`). Live no-write parsing found rows for 12/12 combos.
- Verification: red test run failed on missing `parse_rankings_xls` and old `parse_rankings_table`; `pytest tests/test_fed_italy.py -v` passed 8/8 after implementation; `py_compile scrape_fed_italy.py` passed; scraper entrypoint with Supabase env unset parsed 12/12 combos with failed=0/skipped=0; full `pytest tests/ -v` ran 630 passed, 6 failed in unrelated `tests/test_scrape_iwas.py`.
- Remaining risks: Federscherma document slugs/REST ordering may change; discovery is title-filtered but depends on the WordPress REST search result ordering.

---

## Agent 10 — Russia Federation Scraper

- [x] Read existing lessons and federation scraper patterns.
- [x] Probe rusfencing.ru requested paths and live rating filters.
- [x] Write failing tests for Cyrillic ranking table parsing and fetch URL behavior.
- [x] Implement `scrape_fed_rus.py` with live `rating.php` GET filters.
- [x] Run focused Russia scraper tests.
- [x] Run relevant broader verification.
- [x] Update final review with files, behavior, verification, and risks.

### Final Review

- Files changed: `scrape_fed_rus.py`, `tests/test_fed_rus.py`, `tasks/todo.md`.
- Behavior changed: Russia rankings now fetch public `rusfencing.ru/rating.php` GET-filtered HTML for all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos; parser extracts Cyrillic rank/name/organization/points rows and optional Latin alternate names into metadata.
- Probe record: `/rating`, `/rankings`, and `/sport/ranking` returned 404; `GET https://www.rusfencing.ru/rating.php` returned server-rendered HTML. Public combo coverage verified at 12/12.
- Verification: failing tests first showed missing `scrape_fed_rus`; `pytest tests/test_fed_rus.py -v` passed 7/7; live no-write fetch+parse passed 12/12 combos; `pytest tests/test_fed_rus.py tests/test_fed_rankings_common.py -v` passed 12/12; `py_compile` passed for the new files.
- Full suite: `pytest tests/ -v` currently fails outside this agent scope (330 passed, 117 failed), mainly missing/unimplemented other agent modules and missing workflow files owned by Agent 80.
- Remaining risks: Russia site may rotate internal numeric filter IDs; current IDs were live-probed and documented in `scrape_fed_rus.py`.

---

## Agent 5 Execution Plan — Compute Pipeline Cleanup

- [x] Add failing tests for `season_utils.py` conversions and invalid inputs.
- [x] Add failing tests for `compute_national_rankings.result_weight()` preferring `fs_tournaments.type`.
- [x] Add failing tests for `scraper.py` fencer dedup by `fie_id` across weapon combos.
- [x] Implement `season_utils.py` and wire scoped season formatting helpers.
- [x] Update `result_weight()` to prefer mapped tournament types, then fall back to tournament text.
- [x] Refactor `scraper.py` to collect combo rows, dedupe by `fie_id`, and upsert the deduped rows.
- [x] Run targeted tests, then `.venv/bin/python -m pytest tests/ -v`.
- [x] Record final files, behavior, verification, and remaining risks.

### Final Review

- Files changed: `season_utils.py`, `tests/test_season_utils.py`, `tests/test_compute_rankings.py`, `compute_national_rankings.py`, `scraper.py`, `fed_rankings_common.py`, `scrape_fed_british.py`, `scrape_fed_canada.py`, `scrape_fed_france.py`, `scrape_fed_germany.py`, `scrape_fed_italy.py`, `tasks/todo.md`.
- Behavior changed: season conversion is centralized; federation ranking rows normalize season strings; national result weighting checks `fs_tournaments.type` before name/category fallback; FIE fencer scraping now collects all combo rows, dedupes by `fie_id`, and upserts the most complete row once.
- Verification: red tests failed first for missing utilities/old behavior; targeted Agent 5 suite passed (`60 passed`); touched files compile under `.venv/bin/python`.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed during collection on unrelated missing modules `scripts.data_quality_check` and `scripts.download_headshots`. Retrying with those two ignored ran 155 tests with 140 passed and 15 unrelated failures in missing Agent D/H/G modules and existing IWAS parser tests.
- Remaining risks: `scraper.py` still upserts on `fie_id,weapon,category` because the existing database conflict target appears to use that key; dedup prevents new cross-combo duplicate payload rows but does not merge historical database duplicates by itself.

---

## Agent 4 — Engarde Rewrite + Non-FIE Expansion

### Plan
- [x] Read `tasks/lessons.md` and `tasks/todo.md`; apply Engarde endpoint lesson.
- [x] Read current `scrape_engarde.py` completely and inspect `scrape_bouts.py` for `fs_bouts` row shape.
- [x] Probe Engarde listing, tournament, result, pool, and DE endpoints.
- [x] Write failing tests in `tests/test_scrape_engarde.py` using probed HTML structures.
- [x] Rewrite `scrape_engarde.py` for multi-service discovery, results, bouts, state, and 1.5s rate limit.
- [x] Run targeted tests: `.venv/bin/python -m pytest tests/test_scrape_engarde.py -v`.
- [x] Run broader relevant tests if safe: `.venv/bin/python -m pytest tests/ -v`.
- [x] Update Wiki-Brain/session log and final review.

### Risks / Edge Cases
- Engarde endpoints rotate and can return 404/fallback HTML or SQL-like endpoint errors.
- Legacy result pages use both `/competition/{org}/{event}/{competition}/page.htm` and `index.php?Organisme=...&Event=...&Compe=...&page=...`.
- Pool and tableau pages are free-form HTML tables, so parsing must tolerate French/English labels, byes, missing scores, and team pages.
- `fs_bouts.id` may be UUID or database-generated depending on deployment; mirror `scrape_bouts.py` UUID fallback behavior.
- Import-time Supabase setup should not block parser tests.

### Final Review
- Files changed: `scrape_engarde.py`, `tests/test_scrape_engarde.py`, `tasks/todo.md`.
- Behavior changed: Engarde discovery now queries global, UK, Ireland, Australia, and France service filters; parser handles tournament JSON, competition XML, final classification tables, pool matrices, and DE bracket tables; results are delete+reinserted; bouts are UUIDv5-upserted; `done_ids` are persisted through `scraper_state`; requests are rate-limited to 1.5s by default.
- Probe evidence: `getCompeForDisplay.php` returned XML rows for global/GBR/AUS/FRA and empty XML for IRL; `getTournoisForDisplay.php` returned JSON events; `getTournois.php` returned organism event JSON for rfee/scfu/nsw_sfl/life/hunfencing/occ; direct `clasfinal.htm`, `poules1.htm`, and `tableau*.htm` pages returned result/pool/DE HTML.
- Verification performed: targeted red test failed before implementation; targeted green test passed with `6 passed`; live parser check parsed 257 results, 711 pool bouts, 32 DE bouts, and 5 UK competition rows; `git diff --check` passed.
- Full suite result: `.venv/bin/python -m pytest tests/ -v` ran 637 tests with 630 passed and 7 pre-existing unrelated failures in `tests/test_scrape_iwas.py` and `tests/test_scrape_ncaa_regular.py::test_parse_score_sheet_texts_counts_forfeited_bouts`; the same 7 failures reproduce when run alone.
- Remaining risks: live Engarde pages are semi-structured HTML and may need parser adjustment if bracket markup changes; Engarde IRL returned no current country-filter rows in this probe; `fs_bouts` rows may contain null fencer IDs when name+country matching fails.

---

## Active Work: A2 Canonical Fencer Identity Resolution

- [x] Inspect `fs_fencers` write paths in `scraper.py` and result/fencer helper code.
- [x] Write failing tests for FIE ID grouping, no-FIE name+country grouping, ambiguous no-match cases, unicode normalization, and idempotent upsert behavior.
- [x] Add `fs_fencer_identities` migration with deterministic rerun-safe script payload support.
- [x] Implement `scripts/merge_fencer_identities.py` using FIE ID exact grouping first, normalized name+country fallback, and ambiguity reporting.
- [x] Run `./.venv/bin/python -m pytest tests/test_fencer_identity.py -v` and fix failures.
- [x] Add final review notes with files changed, behavior changed, verification, and residual risks.

### Final Review: A2 Canonical Fencer Identity Resolution

- Files changed: `scripts/merge_fencer_identities.py`, `supabase/migrations/20260601_fencer_identities.sql`, `tests/test_fencer_identity.py`, `tasks/todo.md`.
- Behavior changed: added deterministic identity grouping for duplicate `fs_fencers` rows by exact FIE ID first, then normalized no-FIE name+country fallback; ambiguous no-FIE rows are reported and skipped.
- Verification: focused red run failed with missing `scripts` module; after implementation, `./.venv/bin/python -m pytest tests/test_fencer_identity.py -v` passed with 6 tests.
- Additional check: `./.venv/bin/python scripts/merge_fencer_identities.py --help` exits 0.
- Remaining risk: full `./.venv/bin/python -m pytest tests/ -v` currently fails during collection on unrelated `tests/test_rankings_trends.py` because `compute_rankings_trends` is missing.

---

## Agent 8 — China Federation Scraper Plan

- [x] Probe `fencing.org.cn`, `cnfencing.org.cn`, `sport.gov.cn`, and discovered public China fencing platform URLs for ranking pages/API endpoints.
- [x] Record working URL, method, response format, and public combo coverage evidence.
  - `fencing.org.cn` and `cnfencing.org.cn`: DNS resolution failed from the approved network probe.
  - `fencing.sport.org.cn`: connection reset from approved probe.
  - `https://www.sport.gov.cn/zjzx/`: public HTML, no ranking table/API found in initial probe.
  - `https://fencing.yy-sport.com.cn/`: public SPA; API GET `https://fencing.yy-sport.com.cn/fencingapi/rankinfo/total/week?...` returns JSON.
  - Public combos confirmed: `PS` Senior and `PJ` Junior for `F/E/S` × `M/F` returned records for season `2026`, week `第二十一周(05月18日至05月24日)`.
- [x] Write failing tests in `tests/test_fed_chn.py` for Chinese headers, CJK names, empty/no-table pages, and skipped DNS/DQ/summary rows.
- [x] Implement `scrape_fed_chn.py` with scoped constants, 12 ranking combos, parser, fetcher, season fallback, logger, and write path.
- [x] Run targeted pytest and relevant full scraper tests.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Final Review

- Files changed: `scrape_fed_chn.py`, `tests/test_fed_chn.py`, `tasks/todo.md`.
- Behavior changed: added China federation rankings scraper using public `fencing.yy-sport.com.cn` JSON API, with JSON/HTML parsing, CJK preservation, 12 Senior/Junior combo coverage, API pagination, season fallback, and `ScraperRunLogger` integration.
- Verification performed:
  - Red test confirmed before implementation: `tests/test_fed_chn.py` failed with `ModuleNotFoundError`.
  - Targeted tests: `.venv/bin/python -m pytest tests/test_fed_chn.py -v` → 7 passed.
  - Compile check: `.venv/bin/python -m py_compile scrape_fed_chn.py` → passed.
  - Live bounded API probe: all 12/12 combos returned rows from `https://fencing.yy-sport.com.cn/fencingapi/rankinfo/total/week`.
  - Live full scraper fetch path: all 12/12 combos parsed, with counts from 125 to 248 rows per combo.
  - Full suite: `.venv/bin/python -m pytest tests/ -v` → 633 passed, 7 failed in unrelated existing `tests/test_camps.py` and `tests/test_scrape_iwas.py`.
- Remaining risks: source uses an SSL chain that failed local certificate verification, so the scraper sets `VERIFY_SSL = False`; the API caps page size at 20 and may be slower due pagination.

---

## Active Work: Agent 33 — Fencer Name Variant Database

- [x] Read relevant project lessons and Agent 2 identity table contract.
- [x] Write failing tests for script detection, identity grouping, source dedupe, migration DDL, and Supabase upsert behavior.
- [x] Implement `compute_name_variants.py` using `fs_fencer_identities` row-id/FIE-id grouping.
- [x] Add `supabase/migrations/20260601_name_variants.sql`.
- [x] Run targeted and full verification; record unrelated full-suite blocker.
- [x] Final review: files changed, behavior changed, verification, risks.

### Final Review: Agent 33 — Fencer Name Variant Database

- Files changed: `compute_name_variants.py`, `supabase/migrations/20260601_name_variants.sql`, `tests/test_name_variants.py`, `tasks/todo.md`.
- Behavior changed: added a per-identity name variant computation using `fs_fencer_identities.fs_fencer_row_ids` first and `fie_ids` fallback for `fs_results` / `fs_national_fed_rankings`; detects Latin, Hangul, CJK, Cyrillic, Arabic, and Other scripts; dedupes on `(fencer_id, name, script)` while preserving all contributing sources in metadata.
- Verification: red run of `.venv/bin/python -m pytest tests/test_name_variants.py -v` failed for missing module/migration; after implementation, the same command passed `4 passed`. Dependency path `.venv/bin/python -m pytest tests/test_name_variants.py tests/test_fencer_identity.py -v` passed `10 passed`. `.venv/bin/python compute_name_variants.py --help` and `.venv/bin/python -m py_compile compute_name_variants.py` exited 0.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed during collection on unrelated `tests/test_api.py` because `fastapi` is not installed in the venv.
- Remaining risk: migration assumes Agent 2's `fs_fencer_identities` table is applied before this compute runs; stale variants are not deleted if source names are later removed.

---

## Agent 49 — New Zealand Federation Scraper Plan

- [x] Read project lessons/todo and inspect existing federation scraper patterns.
- [x] Probe New Zealand public ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_nzl.py` using realistic FeNZ API/table fixtures.
- [x] Implement `scrape_fed_nzl.py` with parser, API fetcher, season helper, state note, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_nzl.py -v`.
- [x] Run relevant regression tests for federation common/scraper behavior.
- [x] Update final review notes with files changed, behavior, verification, and remaining risks.

### Final Review: Agent 49 New Zealand Federation Scraper

- Files changed: `scrape_fed_nzl.py`, `tests/test_fed_nzl.py`, `tasks/todo.md`.
- Probe evidence: requested `www.fencing.org.nz/{rankings,results,competitions/rankings}` paths returned 404; `https://results.fencing.org.nz/` is a JS portal; public data is available at `GET https://api.fencing.org.nz/public/ranking?weapon=<foil|epee|sabre>&cat=<open|u20>` as JSON served with `text/html`.
- Combos working: 12/12 live API smoke check with row counts: Senior/open Foil 93/48, Epee 137/69, Sabre 51/25 for Men/Women; Junior/u20 Foil 59/36, Epee 69/50, Sabre 25/19.
- Behavior changed: added FeNZ parser for selected API JSON plus English HTML-table fallback; preserves UTF-8 names, parses decimal commas, skips DNS/DQ/summary rows, stores region/uid/category/ranking update metadata, writes via `fed_rankings_common.write_rankings`, and records last combo state via `scraper_state`.
- Verification: red test run failed first with missing `scrape_fed_nzl`; focused NZL tests now pass (`9 passed`); unaffected federation/common subset passes (`54 passed`); live FeNZ smoke check passes for all 12 combos after network escalation.
- Full suite: `.venv/bin/python -m pytest tests/ -v` currently fails on unrelated unfinished agents/modules (129 failed, 364 passed), including CISM, competition details, several unimplemented federation scrapers, news/referees/youth scrapers, and existing Italy XLS-transition tests.
- Remaining risks: `write_rankings` returns 0 without Supabase credentials, so live write count was not exercised; FeNZ API currently serves JSON as `text/html`, so fetch keeps JSON parsing tolerant.

---

## Agent 27 — Wikipedia Bio Text Enrichment

- [x] Read `tasks/lessons.md`, `tasks/todo.md`, and `scrape_wikidata.py`.
- [x] Inspect run logger, scraper state, migration, and test patterns.
- [x] Probe Wikipedia API title/summary/infobox behavior for fencer Wikidata IDs.
- [x] Write failing tests in `tests/test_scrape_wikipedia_bios.py` for language choice, title lookup, summary extraction, infobox/bio detail extraction, cursor state, and update payloads.
- [x] Add `supabase/migrations/20260601033334_wikipedia_bios.sql` with nullable `fs_fencers` columns.
- [x] Implement `scrape_wikipedia_bios.py` with Supabase query, Wikidata-to-title lookup, language fallback, 1 req/sec throttling, incremental state, run logging, and safe partial-failure handling.
- [x] Run targeted test and full suite verification; fix failures.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Final Review: Agent 27 — Wikipedia Bio Text Enrichment

- Files changed: `scrape_wikipedia_bios.py`, `tests/test_scrape_wikipedia_bios.py`, `supabase/migrations/20260601033334_wikipedia_bios.sql`, `tasks/todo.md`.
- Behavior changed: added nullable biography fields to `fs_fencers`; scraper loads fencers with `metadata->>wikidata_id` and null `bio_text`, resolves Wikidata sitelinks to nationality-preferred Wikipedia languages with English fallback, fetches REST summaries, parses infobox/bio details, updates existing rows without overwriting non-null enrichment fields, rate limits requests, and stores `last_fencer_id`.
- Probe finding: `https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&titles=Q...` returns a missing page for raw Wikidata IDs, so the implementation uses Wikidata `Special:EntityData/{QID}.json` sitelinks before Wikipedia REST/API calls.
- Verification: red run failed with missing `scrape_wikipedia_bios`; focused `.venv/bin/python -m pytest tests/test_scrape_wikipedia_bios.py -v` passed 9 tests; `.venv/bin/python -m py_compile scrape_wikipedia_bios.py` passed; `.venv/bin/python -m pytest tests/test_scrape_wikidata.py tests/test_scrape_wikipedia_bios.py -v` passed 14 tests; live Lee Kiefer API validation returned bio URL, height, weight, and `Cleveland, Ohio, U.S.` birth place.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran with Agent 27 tests passing, but failed overall with 23 unrelated failures in in-progress Agent SGP/Engarde/IWAS/NCAA regular-season areas.
- Remaining risks: non-English infobox parsing covers common European labels but may miss CJK/Arabic localized labels; skipped rows remain `bio_text IS NULL` and will be retried on future runs.

---

## Agent 28 — Fencer Social Media Presence

- [x] Read project lessons/todo and inspect `scrape_wikidata.py`, logger/state helpers, migration style, and parser test style.
- [x] Probe FIE athlete profile structure for federation-profile social links and footer/header false positives.
- [x] Write failing tests in `tests/test_social_media.py` for Wikidata SPARQL properties, profile HTML extraction, JSON/social `sameAs` extraction, matching, upsert conflict, and state cursor behavior.
- [x] Add `supabase/migrations/20260601_social_media.sql` for `fs_fencer_social_media`.
- [x] Implement `scrape_social_media.py` with Wikidata pass, FIE profile pass, Supabase upsert, run logging, and scraper state cursor.
- [x] Run targeted tests and relevant full verification; fix failures.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Final Review: Agent 28 — Fencer Social Media Presence

- Files changed: `scrape_social_media.py`, `supabase/migrations/20260601_social_media.sql`, `tests/test_social_media.py`, `tasks/todo.md`.
- Behavior changed: added `fs_fencer_social_media`; scraper collects Wikidata social properties P2003/P2002/P2397/P7085/P2013, matches fencer rows by `metadata.wikidata_id` then `fie_id`, parses profile social links from visible anchors and embedded JSON, ignores header/footer federation social links, and upserts by `fencer_id,platform`.
- Verification: red run failed with missing `scrape_social_media`; focused `.venv/bin/python -m pytest tests/test_social_media.py -v` passed 6 tests; nearby `.venv/bin/python -m pytest tests/test_scrape_wikidata.py tests/test_social_media.py -v` passed 11 tests; `.venv/bin/python -m py_compile scrape_social_media.py tests/test_social_media.py` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed during collection on unrelated missing `scrape_cac_games` and `scrape_ncaa_regular`. Retrying with those ignored produced 481 passed and 86 unrelated failures in other in-progress agent modules.
- Remaining risks: FIE athlete profiles currently show only global federation social footer/header links for the probed athlete, so profile scraping may often skip rather than write until athlete-specific social links exist in profile HTML/JSON. No RLS policy was added; migration follows existing project table style.

---

## Agent 12 — Ukraine Federation Scraper Plan

- [x] Read project lessons/todo and inspect existing federation scraper patterns.
- [x] Probe NFFU public ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_ukr.py` using realistic NFFU PDF-extracted text fixtures.
- [x] Implement `scrape_fed_ukr.py` with PDF text extraction, Ukrainian parser, retry/backoff, season fallback, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_ukr.py -v`.
- [x] Run relevant federation regression tests.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Live Verification Note
- Root cause found: live fetch failed before the request because `HEADERS["Referer"]` contained Cyrillic characters; Python HTTP headers must be latin-1 encodable. Added a regression test before fixing.

### Final Review: Agent 12 Ukraine Federation Scraper

- Files changed: `scrape_fed_ukr.py`, `tests/test_fed_ukr.py`, `tasks/todo.md`.
- Behavior changed: added NFFU Ukraine national rankings scraper for all 12 Senior/Junior Foil/Epee/Sabre Men/Women public PDF combinations; parser handles Ukrainian Cyrillic PDF text and HTML headers, decimal commas, empty/no-data pages, and DNS/DQ/summary rows.
- Probe result: `fencing.ua/reyting`, `/rankings`, and `/zmahannya/reyting` redirect to `https://www.nffu.org.ua/`; `nffu.gov.ua` does not resolve; working index is `GET https://www.nffu.org.ua/рейтинги/` returning HTML with public PDF links.
- Live verification: all 12/12 configured combinations fetched and parsed from public PDFs with row counts: Foil Men Senior 79, Foil Women Senior 71, Epee Men Senior 133, Epee Women Senior 104, Sabre Men Senior 59, Sabre Women Senior 50, Foil Men Junior 66, Foil Women Junior 74, Epee Men Junior 90, Epee Women Junior 87, Sabre Men Junior 45, Sabre Women Junior 46.
- Verification passed: initial red test failed on missing module; header regression failed before fix; `.venv/bin/python -m pytest tests/test_fed_ukr.py -v` passed with 10 tests; `.venv/bin/python -m py_compile scrape_fed_ukr.py tests/test_fed_ukr.py` passed; federation regression command passed with 43 tests; `git diff --check -- scrape_fed_ukr.py tests/test_fed_ukr.py tasks/todo.md` passed.
- Full suite: `.venv/bin/python -m pytest tests/ -v` failed during collection on unrelated missing `scrape_ncaa_regular`; rerun ignoring that blocker produced 486 passed and 86 unrelated failures in unfinished modules such as `scrape_fed_hkg`, `scrape_fred`, `scrape_commonwealth`, `scrape_continental_games`, `scrape_youth_majors`, and existing Italy/IWAS/Masters tests.
- Remaining risk: NFFU PDF filenames include dates/months and may need future URL refresh if the federation replaces PDFs without keeping old links.

---

## Agent 14 — Spain Federation Scraper Plan

- [x] Read project lessons/todo and inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and season utility status.
- [x] Probe RFEE Spain ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_esp.py` using realistic Skermo/RFEE HTML fixtures.
- [x] Implement `scrape_fed_esp.py` with Skermo GET fetcher, Spanish parser, season fallback, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_esp.py -v`.
- [x] Run relevant federation regression tests.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- `https://www.rfeespada.es/{ranking,clasificaciones,rankings}`: DNS resolution failed from local probe.
- Current RFEE site `https://esgrima.es/` links Ranking to `https://app.skermo.org/ranking-rfee/public/RFEE`.
- Public request method: `GET`.
- Response format: server-rendered HTML table.
- Working URL pattern: `https://app.skermo.org/ranking-rfee/public/RFEE?setLang=es&season=16&weapon={E|F|S}&category={7|6}&gender={M|W}`.
- Public combos: all 12 Senior/Junior Foil/Epee/Sabre Men/Women returned rows for season `2025-2026`.

### Final Review

- Files changed: `scrape_fed_esp.py`, `tests/test_fed_esp.py`, `tasks/todo.md`.
- Behavior changed: added RFEE/Spain national ranking scraper using public Skermo GET HTML tables; parses Spanish headers, split first/surname columns, Spanish decimal commas/thousands separators, rank-prefixed names, accented characters, and skips DNS/DQ/summary/no-data rows.
- Public combo coverage: 12/12 target combos returned rows for season `2025-2026` in the live non-writing smoke check.
- Verification:
  - Red run: `.venv/bin/python -m pytest tests/test_fed_esp.py -v` failed with missing `scrape_fed_esp`.
  - Focused: `.venv/bin/python -m pytest tests/test_fed_esp.py -v` passed 8/8.
  - Live no-write smoke: all 12 `RANKING_COMBOS` fetched and parsed rows for pinned `2025-2026`.
  - Relevant federation subset: `.venv/bin/python -m pytest tests/test_fed_esp.py tests/test_fed_british.py tests/test_fed_france.py tests/test_fed_germany.py tests/test_fed_rankings_common.py -v` passed 29/29.
  - Full suite: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/ -v` ran 627 tests: 604 passed, 23 unrelated failures in `tests/test_fed_sgp.py`, `tests/test_scrape_engarde.py`, `tests/test_scrape_iwas.py`, and `tests/test_scrape_ncaa_regular.py`.
- Remaining risks: Skermo season IDs are mapped from known public form values and inferred for future seasons; if Skermo changes the select IDs or table layout, the scraper will log failed/no-row combos rather than crash.

---

## Agent 11 — Poland Federation Scraper Plan

- [x] Read project lessons/todo and inspect existing federation scraper patterns.
- [x] Probe PZS Poland public ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_pol.py` using realistic PZS HTML fixtures.
- [x] Implement `scrape_fed_pol.py` with Polish index discovery, parser, fetcher, season fallback, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_pol.py -v`.
- [x] Run relevant federation regression tests.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- `https://pzszerm.pl/ranking`: 404.
- `https://pzszerm.pl/klasyfikacje`: 200 redirect/final URL `https://pzszerm.pl/zawody/klasyfikacje/`.
- `https://pzszerm.pl/rankingi`: 404.
- Working request method: `GET` with browser-like headers.
- Response format: server-rendered HTML.
- Working URL pattern: `https://pzszerm.pl/zawody/klasyfikacje/klasyfikacja/?id={id}` discovered from the index page.
- Public combos: all 12 Senior/Junior Foil/Epee/Sabre Men/Women returned ranking tables for season `2025-2026`.

### Final Review: Agent 11 Poland Federation Scraper

- Files changed: `scrape_fed_pol.py`, `tests/test_fed_pol.py`, `tasks/todo.md`.
- Behavior changed: added PZS ranking index discovery, Polish table parser, current-season fallback, transient HTTP retry/backoff, Supabase write path through `fed_rankings_common.write_rankings()`, and run logging.
- Probe result: `GET https://pzszerm.pl/zawody/klasyfikacje/` is the working index; `/ranking` and `/rankingi` return 404; all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public.
- Live validation: discovered 12/12 combos; parsed row counts ranged from 57 to 103 rows per combo.
- Verification: `.venv/bin/python -m pytest tests/test_fed_pol.py -v` passed 7 tests; `.venv/bin/python -m pytest tests/test_fed_pol.py tests/test_fed_british.py tests/test_fed_rankings_common.py -v` passed 17 tests; `.venv/bin/python -m py_compile scrape_fed_pol.py` passed.
- Full suite note: `.venv/bin/python -m pytest tests/ -v` still fails during collection on unrelated missing module `scrape_ncaa_regular`.
- Remaining risk: live Supabase writes were not executed in this session; validation was no-write fetch/parse only.

---

## Agent 48 — Australia Federation Scraper Plan

- [x] Read project lessons/todo and inspect existing federation scraper patterns.
- [x] Probe Australian Fencing public ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_aus.py` using realistic AFF HTML fixtures.
- [x] Implement `scrape_fed_aus.py` with AFF HTML table parsing, state metadata, season normalization, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_aus.py -v`.
- [x] Run relevant federation regression tests.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- `https://www.ausfencing.org/rankings/`: GET 200, text/html, category landing page, no ranking tables.
- `https://www.ausfencing.org/results/`: GET 200, text/html, historical results/titles tables, not current rankings.
- `https://www.ausfencing.org/national-rankings/`: GET 404.
- `https://www.ausfencing.org/events/results/`: GET 200 redirected to `/results/`.
- Working URLs: `https://www.ausfencing.org/open-rankings/` for Senior and `https://www.ausfencing.org/junior-rankings/` for Junior.
- Request method: GET with browser-like headers.
- Response format: server-rendered HTML tables.
- Public combos: all 12 Senior/Junior Foil/Epee/Sabre Men/Women returned public ranking tables.

### Final Review

- Files changed: `scrape_fed_aus.py`, `tests/test_fed_aus.py`, `tasks/todo.md`.
- Behavior changed: added Australia federation rankings scraper for AFF public Senior/Open and Junior HTML tables; parses state suffixes into `metadata.state`, keeps club when present, handles decimal commas, skips DNS/DQ/summary/unranked rows, normalizes season strings, records probe/last-run state, and logs failed combos.
- Verification: RED test run failed on missing `scrape_fed_aus`; after implementation, `.venv/bin/python -m pytest tests/test_fed_aus.py -v` passed 12 tests.
- Additional verification: `.venv/bin/python -m pytest tests/test_fed_aus.py tests/test_fed_rankings_common.py tests/test_season_utils.py tests/test_fed_british.py -v` passed 33 tests; `.venv/bin/python -m py_compile scrape_fed_aus.py tests/test_fed_aus.py` exited 0.
- Live read-only check: `https://www.ausfencing.org/open-rankings/` and `/junior-rankings/` parsed rows for 12/12 public combos.
- Full suite: `.venv/bin/python -m pytest tests/ -v` is blocked during collection by unrelated missing module `scrape_ncaa_regular` (earlier run also hit missing `scrape_cac_games`).
- Remaining risk: AFF accordion markup/table order could change; scraper first matches section labels and falls back to current six-table order.

---

## Agent 13 — Romania Federation Scraper Plan

- [x] Read project lessons/todo and inspect `scrape_fed_british.py`, `fed_rankings_common.py`, and season utility status.
- [x] Probe Romania federation public ranking URLs and identify public combo coverage.
- [x] Write failing tests in `tests/test_fed_rou.py` using realistic Romanian PDF-extracted text and HTML fixtures.
- [x] Implement `scrape_fed_rou.py` with Romanian parser, PDF text extraction, partial combo handling, season fallback, logger, and write path.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_fed_rou.py -v`.
- [x] Run relevant federation regression tests if scoped changes can affect shared behavior.
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- `https://federatia-de-scrima.ro/{clasamente,rankinguri,rezultate/clasament}`: DNS resolution failed from local and escalated probes.
- Current federation site: `https://frscrima.ro/`.
- `https://frscrima.ro/clasamente`: GET 404, text/html, no tables.
- `https://frscrima.ro/rankinguri`: GET 404, text/html, no tables.
- `https://frscrima.ro/rezultate/clasament`: GET 200, redirected/final image `https://frscrima.ro/wp-content/uploads/2014/05/clasament.jpg`, not a parseable ranking table.
- Working index URL: `https://frscrima.ro/ranking-national/`.
- Request method: GET with browser-like headers.
- Response format: WordPress HTML page linking static ranking PDFs; individual combo files are `application/pdf`.
- Public target combos: 6/12 Junior Foil/Epee/Sabre Men/Women PDFs. Senior Foil/Epee/Sabre Men/Women links were not found on the ranking page, ranking category, or WordPress search/API probes.

### Final Review

- Files changed: `scrape_fed_rou.py`, `tests/test_fed_rou.py`, `tasks/todo.md`.
- Behavior changed: added a Romania federation scraper for public Junior ranking PDFs with Romanian HTML/PDF text parsing, Romanian header/diacritic support, season fallback, run logging, common row building, and `write_rankings()` output. Senior combos stay in `RANKING_COMBOS` but are skipped with metadata because no public URLs were found.
- Verification: red test run failed first with `ModuleNotFoundError: No module named 'scrape_fed_rou'`; focused `.venv/bin/python -m pytest tests/test_fed_rou.py -v` passed 6/6 after implementation; live read-only smoke discovered 6/12 URLs and parsed all six Junior PDFs with nonzero rows.
- Broader checks: `.venv/bin/python -m pytest tests/ -v` is blocked by unrelated missing modules `scrape_cac_games` and `scrape_ncaa_regular`; `tests/test_fed_*.py` currently has unrelated failures in in-progress `fed_fin`, `fed_hkg`, `fed_italy`, and `fed_kor` tests.
- Remaining risks: Senior Romania rankings are unavailable from the probed public sources; the scraper depends on `pdfplumber` for the current public PDF format.

---

## Agent 32 — Fencing News + Injury/Absence Tracker Plan

- [x] Read project lessons/todo and inspect existing scraper, logger, state, migration, and test patterns.
- [x] Probe FIE and British Fencing news pages to confirm current listing/article structures.
- [x] Write failing tests in `tests/test_news.py` using realistic FIE and British Fencing fixture HTML.
- [x] Implement `scrape_news.py` with source listing fetch, article parsing, classification, fencer matching, content hashing, state/logging, and Supabase upsert.
- [x] Add SQL migration for `fs_articles`.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_news.py -v`.
- [x] Run full test suite: `.venv/bin/python -m pytest tests/ -v` (blocked by unrelated missing `scrape_ncaa_regular.py` during collection).
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- `https://fie.org/articles`: GET 200, text/html. Listing links use relative `/articles/{id}` URLs. Representative cards include a title and article path.
- `https://fie.org/articles/1651`: GET 200, text/html. Representative article uses `h1` for title, `.Article-content-label` for date text such as `27 May 2026`, and `.Article-content-body` for body paragraphs.
- `https://www.britishfencing.com/news/`: GET 200, text/html. Main news page includes a featured `.o-newsBanner` / `.o-newsBox` card and `Read Full story` article links.
- `https://www.britishfencing.com/upcoming-fencing-events-may-june-2026/`: GET 200, text/html. Representative article uses `h1` for title, `meta[property="article:published_time"]` for date, and body paragraphs for article text.

### Final Review

- Files changed: `scrape_news.py`, `supabase/migrations/20260601_news.sql`, `tests/test_news.py`, `tasks/todo.md`.
- Behavior changed: added FIE and British Fencing news scraping into `fs_articles`; classifies injury/transfer/rule-change/competition/general articles; stores body text in metadata, summaries, hashes, and matched fencer IDs; upserts by URL.
- Verification: focused red run failed with missing `scrape_news`; focused green run passed 8/8; live parser smoke returned FIE listing_count=18/body_len=4088 and British listing_count=1/body_len=1052; `py_compile scrape_news.py` passed.
- Full-suite status: `.venv/bin/python -m pytest tests/ -v` failed before running tests because unrelated `tests/test_scrape_ncaa_regular.py` imports missing `scrape_ncaa_regular`.
- Remaining risks: British Fencing currently exposes one server-rendered story on the main news page; more stories may require following its AJAX loader later. Fencer matching is best-effort exact-name matching with two-token reversed aliases.

---

## Agent 19 — Continental Games

### Plan
- [x] Read project lessons and current task context.
- [x] Inspect `scrape_olympics.py` and existing scraper tests.
- [x] Probe Olympedia and official fallback source structures.
- [x] Write failing tests for Pan American, Asian, European, and African Games fixtures.
- [x] Implement `scrape_continental_games.py` with discovery, parsing, classification, tournament upsert, result upsert, logger, and state handling.
- [x] Run targeted and full test verification.
- [x] Add final review notes with files changed, behavior, verification, and residual risks.

### Probe Findings
- Olympedia `/editions` is Olympic-only for this task.
- Olympedia list pages provide available medal data for:
  - Summer Pan American Games: `/lists/11/manual`
  - Asian Games: `/lists/114/manual`
  - European Games: `/lists/143/manual` (probed fencing rows currently only include 2015)
- Olympedia list index did not expose African Games fencing; the reachable official fallback is the 2019 African Games fencing PDF at `https://www.jar2019.ma/resultats/resJA2019/pdf/JA2019/FE/JA2019_FE_C99_FE0000000.pdf`.
- Accra 2023 and European Games results domains failed DNS resolution during local probes, so those sources must be optional rather than required runtime dependencies.

### Final Review
- Files changed: `scrape_continental_games.py`, `tests/test_scrape_continental_games.py`, `tasks/todo.md`.
- Behavior changed: new continental Games scraper discovers Pan American, Asian, and European Games medal rows from Olympedia list pages, resolves athlete gender from Olympedia profiles when event notes omit gender, parses the official 2019 African Games fencing PDF final standings, groups rows by `{type}:{edition_id}:{event_code}`, upserts tournaments, and rewrites result rows idempotently.
- Verification: red tests first failed with missing `scrape_continental_games`; focused tests passed 7/7; scoped regression with `tests/test_scrape_olympics.py` passed 11/11; live non-DB African PDF validation found 135 rows across 12 events; live non-DB Olympedia sample resolved 10 European rows from page 1 with 7 cached athlete genders; full `tests/ -v` ran 632 passed and 7 failed outside this agent scope.
- Remaining risks: Olympedia manual lists only include Olympians who won continental medals, not necessarily every participant or non-Olympian medalist; European Games 2019 appears to have no fencing and Olympedia currently exposes only 2015 fencing rows; Accra 2023 and EOC result domains failed DNS during probe, so 2023 official fallbacks are not active.

---

## Agent 17 — Youth Olympics + World Fencing Games Plan

- [x] Read project lessons/todo and inspect `scrape_olympics.py` patterns.
- [x] Probe Olympedia Youth Olympic fencing edition/event/result structures.
- [x] Probe FIE/search and public web sources for World Fencing Games / 2023 Bali; verify the available 2023 fencing source.
- [x] Write failing tests in `tests/test_scrape_youth_olympics.py` with captured realistic fixtures.
- [x] Implement `scrape_youth_olympics.py` with YOG + WFG discovery, parsing, Supabase upserts, state, and logging.
- [x] Run focused tests: `.venv/bin/python -m pytest tests/test_scrape_youth_olympics.py -v`.
- [x] Run full tests: `.venv/bin/python -m pytest tests/ -v` (existing unrelated failures remain).
- [x] Add final review notes with files changed, behavior, verification, and remaining risks.

### Probe Notes

- Olympedia `/editions` identifies Youth Olympic editions as ids `65` Singapore 2010, `67` Nanjing 2014, `69` Buenos Aires 2018, and `71` Dakar 2026.
- Olympedia Youth edition FEN pages use `/editions/{id}/sports/FEN` with duplicate `/results/{id}` links; 2010/2014/2018 each exposed 6 individual events plus one mixed team event. Dakar 2026 currently exposes no fencing result links.
- Youth result pages use `table.table-striped` with headers `Pos`, `Competitor`, `NOC`, and medal text; no bib-number column.
- Public search/FIE probes found no 2023 Bali World Fencing Games fencing competition. The available 2023 multi-sport fencing source is Riyadh 2023 World Combat Games, with official archived Swiss Timing fencing results book PDF and 12 fencing events.

### Final Review: Agent 17 — Youth Olympics + World Fencing Games

- Files changed: `scrape_youth_olympics.py`, `tests/test_scrape_youth_olympics.py`, `requirements.txt`, `tasks/todo.md`.
- Behavior changed: new scraper discovers 18 current YOG individual events from Olympedia; parses YOG results with no bib-number column; parses 12 Riyadh 2023 World Combat Games fencing events from the archived Swiss Timing PDF; upserts tournaments using `yog:{edition_id}:{result_id}` and `wfg:{year}:{event_code}` source IDs; inserts `fs_results` with best-effort individual fencer matching and team rows left unmatched.
- Verification: focused new tests passed (`7 passed`); relevant regression set passed (`30 passed`); live parser-only smoke check parsed 18 YOG events and 12 WFG/WCG events.
- Full suite: `.venv/bin/python -m pytest tests/ -v` ran with this scraper's tests passing, but failed on unrelated pre-existing areas: camps date parsing, missing `scrape_fed_sgp.py`, Engarde API mismatch, and IWAS parser expectations.
- Remaining risk: Supabase write path was not run because `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` were not present in the environment.
