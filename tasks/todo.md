# Operation: Insane Fencing Database

**30 Codex Agents** — 5 bug fixes, 10 new federation scrapers, 6 new competition sources, 5 analytics engines, 4 enrichment pipelines.

Each agent = one file (or small file group), tests-first, no cross-dependencies. CI step edits batched at the end.

---

## Current Session: Unblock pre-commit

- [x] Reproduce remaining `ruff` and `pytest-quick` failures.
- [x] Identify root cause for `test_mock_fng_api_failure_activates_fallback`.
- [x] Apply smallest scoped fix for lint/test failures.
- [x] Verify with focused tests and relevant pre-commit hooks.

### Final Review

- Files changed: actual hook failures were in sibling repo `/Users/plernghomhual/Documents/Algorithm`, not this `fencespace-scraper` checkout; fixed `tests/test_cli.py` and `tests/test_mock_ingest.py` there. This file records the investigation.
- Behavior changed: mocked ingest tests now clear `kairos.live._LIVE_DATA_CACHE` before/after each test, so fallback tests are isolated from prior successful fetches.
- Verification performed: focused ruff, ruff-format check, focused pytest, fast pytest hook command, and full `pre-commit run --all-files` in Algorithm.
- Remaining risks: Algorithm has many pre-existing staged/unstaged files; commit contents should be reviewed before staging/committing.

---

## BATCH A: BUG FIXES (5 agents)

### A1 — Fix Italy Scraper (BIFF .xls parser)
- **Files:** `scrape_fed_italy.py`, `tests/test_fed_italy.py`, `requirements.txt`
- Add `xlrd` + `openpyxl` to requirements
- Federscherma.it serves rankings as .xls files (BIFF format) — download, parse, upsert
- Probe first to confirm current URL and file format
- Follow existing fed scraper pattern
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
- Batch update matched rows
- Log unmatched for manual review
- **Deliverable:** Script that reduces NULL fencer_id results by 80%+

### A4 — Engarde Rewrite + Non-FIE Expansion
- **Files:** `scrape_engarde.py`, `tests/test_scrape_engarde.py`
- Current scraper hits 404 on many endpoints — rewrite with current Engarde API structure
- Implement pool/DE detail parsing (currently skipped)
- Add more Engarde event sources (Engarde services in UK, Ireland, Australia, etc.)
- **Deliverable:** Working Engarde scraper with bout data

### A5 — Compute Pipeline Cleanup
- **Files:** `compute_national_rankings.py`, `tests/test_compute_rankings.py`, `fed_rankings_common.py`
- Fix `result_weight` to use tournament `type` field instead of string matching
- Add season format normalizer: `FIE_year → season_string` and `season_string → FIE_year`
- Add weapon combo dedup in `scraper.py` (prevent race conditions on upsert)
- **Deliverable:** Accurate ranking computation, clean season utils

---

## BATCH B: NEW FEDERATION SCRAPERS (10 agents)

Each follows exact pattern: `scrape_fed_{country}.py`, `tests/test_fed_{country}.py`, probe-first, `fed_rankings_common.py` interface.

### B1 — Hungary (MVSZ)
- **Source:** hunfencing.hu / magyarvivaszszovetseg.hu
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Unknown — HTML or JSON (probe first)
- **Deliverable:** Hungary national rankings in `fs_national_fed_rankings`

### B2 — South Korea (KFA)
- **Source:** koreafencing.org
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Korean HTML — handle Hangul text for club/name extraction
- **Deliverable:** South Korea national rankings

### B3 — China (CFA)
- **Source:** fencing.org.cn or equivalent
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Chinese HTML
- **Deliverable:** China national rankings

### B4 — Japan (JFA)
- **Source:** fencing-jpn.jp
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Japanese HTML
- **Deliverable:** Japan national rankings

### B5 — Russia (RUS)
- **Source:** rusfencing.ru
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Russian HTML — probe first
- **Deliverable:** Russia national rankings

### B6 — Poland (PZS)
- **Source:** pzszerm.pl
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Polish HTML
- **Deliverable:** Poland national rankings

### B7 — Ukraine (NFFU)
- **Source:** fencing.ua or nffu.gov.ua
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Ukrainian HTML
- **Deliverable:** Ukraine national rankings

### B8 — Romania (FR)
- **Source:** federatia-de-scrima.ro
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Romanian HTML
- **Deliverable:** Romania national rankings

### B9 — Spain (RFEE)
- **Source:** rfeespada.es
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** Spanish HTML
- **Deliverable:** Spain national rankings

### B10 — Egypt (EGF)
- **Source:** egfencing.com
- **Combos:** Senior + Junior, all 3 weapons, both genders
- **Format:** English/Arabic HTML or PDF
- **Deliverable:** Egypt + first African federation rankings

---

## BATCH C: NEW COMPETITION SOURCES (6 agents)

### C1 — USA Fencing FRED Results
- **Files:** `scrape_fred.py`, `tests/test_scrape_fred.py`
- USA Fencing's new platform replacing AskFRED
- Needs API discovery probe (likely GraphQL or REST endpoints used by FRED platform)
- Tournament results + fencer data with USA Fencing IDs
- Cross-link to `fs_fencers` via name+country
- **Deliverable:** USA domestic tournament results from new platform

### C2 — Youth Olympics + World Fencing Games
- **Files:** `scrape_youth_olympics.py`, `tests/test_scrape_youth_olympics.py`
- Youth Olympic Games (2010, 2014, 2018, 2026) — olympedia has these
- World Fencing Games (2023+ — new multi-sport format, check FIE site)
- **Deliverable:** YOG + WFG tournament+results in DB

### C3 — Universiade / World University Fencing
- **Files:** `scrape_universiade.py`, `tests/test_scrape_universiade.py`
- FISU World University Games fencing results
- Source: fisu.net or olympedia
- **Deliverable:** University Games tournament+results

### C4 — Continental Games (PanAm / Asian / European / African)
- **Files:** `scrape_continental_games.py`, `tests/test_scrape_continental_games.py`
- Pan American Games, Asian Games, European Games, African Games
- Some on olympedia, some on sport-specific sites
- **Deliverable:** Continental multi-sport fencing results

### C5 — NCAA Regular Season Results
- **Files:** `scrape_ncaa_regular.py`, `tests/test_scrape_ncaa_regular.py`
- Beyond the existing championship scraper — individual NCAA dual meet results
- Source: ncaa.fencingresults.com or individual college team sites
- Focus on top-50 programs
- **Deliverable:** NCAA regular season bout data + results

### C6 — Youth/Junior Major Results
- **Files:** `scrape_youth_majors.py`, `tests/test_scrape_youth_majors.py`
- Cadet/Junior World Championships, EFC Cadet/Junior Circuit
- Already partially covered by FIE history — scrape missing editions
- European Youth Olympic Festival (EYOF)
- **Deliverable:** Complete youth/junior competition results

---

## BATCH D: AGGREGATION & ANALYTICS (5 agents)

### D1 — Head-to-Head Stats Engine
- **Files:** `compute_head_to_head.py`, `supabase/migrations/YYYYMMDD_head_to_head.sql`, `tests/test_head_to_head.py`
- Aggregate `fs_bouts` into `fs_head_to_head` table
- Fields: fencer_a_id, fencer_b_id, weapon, a_wins, b_wins, a_touches, b_touches, last_meeting
- Run after bout scraper in CI
- **Deliverable:** Queryable H2H records for every fencer pair

### D2 — Fencer Career Stats Aggregation
- **Files:** `compute_career_stats.py`, `supabase/migrations/YYYYMMDD_career_stats.sql`, `tests/test_career_stats.py`
- Aggregate `fs_results` into `fs_fencer_career_stats`
- Fields per fencer: total competitions, medals by tier (Gold/Silver/Bronze), best rank, avg rank, weapons used, category transitions
- **Deliverable:** Career stats for every fencer in DB

### D3 — Rankings Trends + Points Projection
- **Files:** `compute_rankings_trends.py`, `supabase/migrations/YYYYMMDD_rankings_trends.sql`, `tests/test_rankings_trends.py`
- From `fs_rankings_history`: compute ranking trajectory (↑↓→ per season)
- Points projection: estimate next ranking based on current season results
- Store as materialized view or table
- **Deliverable:** Fencer ranking trends + projected ranks

### D4 — Country Depth + Club Rankings
- **Files:** `compute_country_analytics.py`, `supabase/migrations/YYYYMMDD_country_club_rankings.sql`, `tests/test_country_analytics.py`
- Per-country squad depth: fencers in top 16, top 32, top 64 by weapon/gender
- Club rankings: aggregate all fencers per club across all competitions
- Countries ranked by total points, medals, squad depth
- **Deliverable:** Country power rankings + club leaderboards

### D5 — Fencer Transfer Tracker
- **Files:** `compute_transfers.py`, `supabase/migrations/YYYYMMDD_transfers.sql`, `tests/test_transfers.py`
- Detect fencer country changes across seasons in rankings history
- Build `fs_fencer_transfers` table: fencer_id, from_country, to_country, season, competition
- **Deliverable:** Fencer nationality change database

---

## BATCH E: ENRICHMENT & MEDIA (4 agents)

### E1 — Wikipedia Bio Text Enrichment
- **Files:** `scrape_wikipedia_bios.py`, `tests/test_scrape_wikipedia_bios.py`
- For fencers with `metadata.wikidata_id`, call Wikipedia REST API to fetch abstract
- New column: `bio_text` on `fs_fencers`
- Also fetch `nickname`, `birth_place`, `height`, `weight` from Wikipedia infobox
- **Deliverable:** Fencer biographies for 2000+ fencers

### E2 — Fencer Social Media Presence
- **Files:** `scrape_social_media.py`, `supabase/migrations/YYYYMMDD_social_media.sql`, `tests/test_social_media.py`
- Wikidata has social media properties: Instagram (P2003), Twitter/X (P2002), YouTube (P2397), TikTok (P7085), Facebook (P2013)
- Also scrape fencer federation profiles for social links
- Store in `fs_fencer_social_media` table or metadata jsonb
- **Deliverable:** Social media links for fencers

### E3 — Fencer Media Pipeline
- **Files:** `scripts/download_headshots.py`, `supabase/storage/`
- Download headshot images from Wikimedia Commons URLs to Supabase Storage
- Resize to standard dimensions, serve via CDN
- YouTube match video discovery: search YouTube API for "fencing {fencer_name}"
- **Deliverable:** Self-hosted fencer headshot gallery + match video links

### E4 — Equipment & Brand Data
- **Files:** `scrape_equipment.py`, `supabase/migrations/YYYYMMDD_equipment.sql`, `tests/test_equipment.py`
- Scrape fencer sponsor/equipment data from federation profiles, Wikipedia, fencing equipment forums
- New table: `fs_fencer_equipment` — fencer_id, brand, equipment_type (weapon, mask, jacket, etc.), sponsor_name
- Sources: FIE athlete profiles, federation profiles, news scraping
- **Deliverable:** What each fencer uses + who sponsors them

---

## BATCH F: DATA PRODUCT (2 agents)

### F1 — Live Results Watcher
- **Files:** `watch_live_results.py`, `tests/test_live_results.py`
- Poll FIE results feed for in-progress competitions
- Detect new results since last check and upsert
- Separate GitHub Actions step that runs every 30 min (separate workflow)
- **Deliverable:** Near-real-time FIE competition results

### F2 — Referee & Coach Data
- **Files:** `scrape_referees.py`, `scrape_coaches.py`, `tests/test_referees.py`, `supabase/migrations/YYYYMMDD_referees.sql`
- FIE referee list (FIE website)
- National team coaches per federation
- New tables: `fs_referees`, `fs_coaches`, `fs_fencer_coach_relationship`
- **Deliverable:** Complete FIE referee database + national team coaches

---

## FINAL MERGE: CI + SCHEMA INTEGRATION

### G1 — CI Workflow Merge
- **Files:** `.github/workflows/scraper.yml`
- Add all new scraper steps in correct order
- Add new materialized view compute steps after scrapers
- Add weekly full-suite workflow + fast hourly workflow (live results only)
- **Deliverable:** Complete CI pipeline with all 30 new agents integrated

---

## Summary Table

| Batch | Count | Category | Key Files Created |
|-------|-------|----------|-------------------|
| A | 5 | Bug fixes | scrape_fed_italy.py, merge_fencer_identities.py, match_orphan_results.py, scrape_engarde.py, compute_national_rankings.py |
| B | 10 | Federation scrapers | scrape_fed_{hun,kor,chn,jpn,rus,pol,ukr,rou,esp,egy}.py |
| C | 6 | Competition sources | scrape_fred.py, scrape_youth_olympics.py, scrape_universiade.py, scrape_continental_games.py, scrape_ncaa_regular.py, scrape_youth_majors.py |
| D | 5 | Analytics engines | compute_head_to_head.py, compute_career_stats.py, compute_rankings_trends.py, compute_country_analytics.py, compute_transfers.py |
| E | 4 | Enrichment | scrape_wikipedia_bios.py, scrape_social_media.py, download_headshots.py, scrape_equipment.py |
| F | 2 | Data product | watch_live_results.py, scrape_referees.py, scrape_coaches.py |
| G | 1 | CI merge | .github/workflows/scraper.yml |
| **Total** | **33** | | |

---

## Key Constraints for All Agents

1. **Tests-first:** Write failing test fixtures with real HTML/JSON samples before implementation
2. **No cross-dependencies:** Each agent works on its own files — no agent edits another agent's code
3. **Existing patterns:** Follow established conventions (ScraperRunLogger, scraper_state, supabase upsert, fed_rankings_common)
4. **continue-on-error:** Never break the pipeline
5. **Idempotent:** Safe to rerun — uses incremental state, conflict-aware upserts
6. **CI edits:** Only Agent G1 touches the workflow file — all other agents leave it
