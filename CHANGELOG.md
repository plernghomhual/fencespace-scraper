# June 4–6, 2026 @Release
Summer Update #1

## - Fencer Career Statistics Are Now Live
^^ For the first time, FenceSpace is computing and serving real career stats for 6,669 fencers — win rates, bout counts, medal tallies — all derived from 144,000+ recorded bouts. Previously, this process was silently failing due to outdated internal column references.

## - Home Advantage Analysis: 107,000+ Results Processed
^^ FenceSpace now tracks whether fencers perform better when competing on home soil. Every recorded result has been classified as "home," "away," or "neutral," and average placements are compared across all weapons, categories, and competition tiers. Over 82,000 detail rows and 5,900 aggregate summaries are now in the database.

## - Name Variant Index Rebuilt: 14,800+ Entries
^^ Fencers' names appear differently across sources — FIE records, national rankings, and result sheets each use their own spelling conventions. A script that builds a unified name-variant index for every fencer was producing zero results due to stale identity references. Fixed and re-run: 14,834 name variants now stored across Latin, Cyrillic, CJK, Hangul, and Arabic scripts.

## - Season Stats and Rankings Trajectory Now Computing
^^ Two additional analytics tables — per-fencer season breakdowns (18,077 rows) and historical rankings trajectory (99,979 rows) — were empty. Their compute scripts are now repaired and fully populated.

## - Country Specialization Analytics
^^ A new table tracks which weapons and categories each country excels at, based on historical results. Every compute run now produces 32,796 rows of country-level specialization data that previously had nowhere to live.

## - Automated Rankings Refresh Scheduled
^^ Six recurring database jobs now automatically refresh materialized views for FIE rankings, national rankings, and related stats tables. Previously these views could go stale indefinitely with no mechanism to update them.

## - Subscriber Data Leak Patched
^^ Four database views were accidentally set up to run as the admin user, which meant anonymous visitors could indirectly read subscriber-only data (like career stats) through those views. All four are now fixed to run as the requesting user, so subscriber content is only visible to subscribers.

## - Database Security Hardened Across the Board
^^ We audited every table in the database. Nine tables had row-level security completely disabled. Another 25+ tables had security enabled but zero policies — so queries silently returned nothing, or worse, allowed access they shouldn't. Seven auth/session tables (csrf tokens, sessions, OAuth providers, etc.) now restrict access to the server only. All gaps are closed.

## - API Keys Are No Longer Stored in Plaintext
^^ API keys are now stored as hashes in the database, so a database breach can't expose active keys. The API, GraphQL server, and WebSocket server all now verify keys by hash. Existing clients continue to work during a transition window while keys are rotated.

## - Two Dangerous Database Functions Locked Down
^^ Two internal functions — one for bulk-updating fencer match records, another for incrementing marketplace usage — were callable by any logged-in user. Both have been restricted to service-role only.

## - OBS Overlay XSS Vulnerability Fixed
^^ The live broadcast overlay was injecting fencer names directly into HTML, which meant a fencer name containing script tags could run code in a broadcaster's browser. Names are now rendered safely. The overlay's auth token was also moved from the URL (where it appears in logs) to a proper header.

## - Marketplace Billing Authorization Added
^^ The marketplace billing endpoint was not verifying that the requesting API key actually owned the account being billed. Any authenticated user could theoretically initiate billing for another account. Ownership is now verified, and redirect URLs are validated against an allowlist.

## - Dashboard, WebSocket, and API Security Tightened
^^ Several additional hardening fixes: the dashboard now validates auth tokens before making database calls; WebSocket connections that pass API keys in the URL are rejected; REST API responses are filtered to a column allowlist to prevent over-fetching sensitive fields; push notification error messages no longer leak internal provider details.

## - CI Now Fails When Database Credentials Are Missing
^^ GitHub Actions workflows were silently continuing when the Supabase database URL wasn't set, which meant database migrations were never running in CI and test failures were being hidden. Workflows now fail immediately and loudly if required secrets are absent.

## - 21 Missing Foreign Key Indexes Added
^^ Twenty-one foreign key columns across the database had no indexes, which means queries joining or filtering on those columns were doing full table scans. All are now indexed.

## - RLS Policy Performance Optimized Across 9 Policies
^^ Nine row-level security policies were calling `auth.uid()` once per row, which adds up fast on large queries. All nine are updated to evaluate the user ID once per query instead — a significant speedup on any endpoint that filters by ownership.

## - Duplicate and Unused Indexes Cleaned Up
^^ Three redundant indexes were dropped: one that was never used (zero lifetime scans), one that duplicated the primary key, and one that duplicated a UNIQUE constraint. Fewer indexes means faster writes.

## - Python Code Quality Tooling Added
^^ Ruff (linter) and mypy (type checker) are now configured for the Python codebase and run automatically in CI. Any new code that introduces type errors or obvious style issues will be caught before merge.

---

On that note (the small bugs fixed):
- Fixed fencer stats script referencing 8 columns that were removed from the bouts table
- Fixed home advantage script crashing with a sort error on results with null country data
- Fixed home advantage script writing duplicate rows in the same upload batch (was causing 31k failures per run)
- Fixed education enrichment script broken by a Python library API change (supabase-py 2.x `.not_.is_()` syntax)
- Fixed name variant script crashing with foreign-key violations from deleted or merged fencer IDs
- Fixed name variant script surviving SSL network errors mid-run instead of aborting the whole job
- Fixed result-loss backfill script using old fencer column names (`fencer_a` → `fencer_a_id`)
- Fixed NCAA bout scraper using old column names (`fencer_a/b/winner` → `fencer_a_id/b_id/winner_id`)
- Fixed medal table script fetching non-existent columns, causing an immediate crash on every run
- Fixed prediction engine using wrong column names (`elo_rating` and `active` don't exist; `fencer_id` → `fie_fencer_id` in rankings trends)
- Fixed 7 data importers using a delete-then-insert pattern that could expose empty tables to live queries mid-scrape — all now use atomic upserts
- Fixed `fs_bouts` missing a UNIQUE constraint, which was silently blocking all bout upserts
- Fixed forum discussions table storing fencer IDs in the wrong type (bigint instead of uuid)
- Cleared 61 corrupted rows from the coach history table that were blocking clean repopulation
- Disabled betting anomaly detection (the database column it depended on was removed)
- Added primary keys to 3 tables that were missing them entirely
- Eliminated N+1 query patterns in 3 scripts (match orphan resolver, result-loss backfill, location enrichment) — now use bulk operations
- Reloaded the PostgREST schema cache to resolve stale-schema 204 errors on newly added columns
