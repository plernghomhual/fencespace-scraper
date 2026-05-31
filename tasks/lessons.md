## Lesson: FIE Season Number Format

### Anti-Pattern
Different files use different season formats. `scraper.py` uses integer year (2026 = 2025/2026 season). Federation scrapers use "2025-2026" range strings.

### Pattern
Add a shared utility in `fed_rankings_common.py` or new `season_utils.py` with:
- `season_to_string(season_int)` → "2025-2026"
- `season_from_string(season_str)` → 2026
- `current_fie_season()` → int (based on month: if month < 7, current year = last year's season)

### Trigger
When writing any new scraper that stores a season value.

---

## Lesson: Fencer Matching Is Best-Effort

### Anti-Pattern
Result importers accept NULL `fencer_id`, creating orphan rows in `fs_results`. No cross-source fencer identity system exists.

### Pattern
Always match fencers by FIE ID first, then name+country. Accept NULL only as last resort. Log unmatched names for batch processing later. Never block insert on failed match.

### Trigger
When writing any result importer.

---

## Lesson: Italy Scraper Needs .xls Support

### Anti-Pattern
Federscherma.it only serves rankings as BIFF .xls files. The current scraper has HTML parsing code that never matches Olympic weapon tables.

### Pattern
Add `xlrd` and `openpyxl` to requirements.txt. Download .xls files, parse with xlrd (old format) or openpyxl (new format). Write rankings via `fed_rankings_common.write_rankings()`.

### Trigger
When working on `scrape_fed_italy.py` or adding any federation scraper.

---

## Lesson: FIE Veteran Events Have Wrong hasResults Flag

### Anti-Pattern
FIE API incorrectly sets `hasResults=0` for all veteran events, preventing result scraping.

### Pattern
Override `has_results=True` for past veteran events (those with an `endDate`). Already fixed in `scrape_fie_history.py` — check that fix exists before editing.

### Trigger
When working on FIE competition discovery.

---

## Lesson: fs_fencers Has Duplicate Rows Per Person

### Anti-Pattern
Same physical fencer gets multiple rows because upsert conflict is on `(fie_id, weapon, category)`. A fencer in 3 weapons × 2 categories = 6 rows.

### Pattern
Use `fs_fencer_identities` table to group rows belonging to the same person. When matching results or computing stats, query via identity group, not individual rows.

### Trigger
When building any aggregation or matching layer.

---

## Lesson: Engarde Endpoints Rotate / Return 404

### Anti-Pattern
Engarde service PHP endpoints change format. POST to `/prog/getTournoisForDisplay.php` gets stale.

### Pattern
Probe endpoints before each implementation. Use `?` form-encoded params. Expect occasional breakage. Log failures clearly.

### Trigger
When working on `scrape_engarde.py`.

---

## Lesson: AskFRED Is Deprecated

### Anti-Pattern
AskFRED.com is a legacy site serving CSV exports. No stable API, no FIE IDs.

### Pattern
USA Fencing has a new FRED platform (check for API). The AskFRED scraper should be replaced, not maintained. New USA data should come from the FRED platform directly.

### Trigger
When working on USA domestic results.

---

## Lesson: All scrapers share `.github/workflows/scraper.yml`

### Anti-Pattern
Multiple agents editing the same CI file creates merge conflicts.

### Pattern
Only one designated agent edits the workflow file at the end. All other agents leave CI untouched. Provide CI YAML snippets in their PR description for the CI merge agent.

### Trigger
When planning parallel agent work.
