Agent 1 — Audit Scraper Frontend + Write Migration Inventory

  You are preparing for the FenceSpace frontend migration.
  Your job: audit the scraper's placeholder frontend, write a complete inventory,
  and clean up the scraper repo. You do NOT touch any live real-frontend files except
  to CREATE one new inventory file.

  ## Repos

  SCRAPER: ~/Documents/FenceSpace-Scraper/fencespace-scraper/
  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/

  ## Step 1: Read the scraper frontend entirely

  Read every source file (not node_modules, not .next) in:
    ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Specifically read:
  - app/page.tsx, app/fencers/page.tsx, app/tournaments/page.tsx, app/rankings/page.tsx
  - app/layout.tsx, app/error.tsx, app/loading.tsx
  - components/BracketVisualizer.tsx
  - components/H2HComparison.tsx
  - components/CareerTimeline.tsx
  - components/FencerComparisonTool.tsx
  - components/CompetitionCalendar.tsx
  - components/AthleteQuiz.tsx
  - components/NewsFeed.tsx
  - components/RankingSparkline.tsx
  - components/CountryMedalHeatmap.tsx
  - components/FederationOverview.tsx
  - pages/head-to-head.tsx, pages/news.tsx
  - src/lib/api.ts, src/lib/types.ts, src/lib/fixtures.ts
  - package.json, tsconfig.json

  ## Step 2: Read the real frontend's data layer

  Read ~/Documents/FenceSpace-Fntend/fencespace/main.js (first 300 lines minimum)

  Extract and document:
  - How window.supabaseGet(table, queryString) works
  - PUBLIC_READ_TABLE_ALIASES map
  - How window.FS_RUNTIME_CONFIG is structured
  - Pattern for IIFE modules used across all pages
  - How auth (window.FsAuth) is exposed

  ## Step 3: Create the migration inventory

  CREATE (do not overwrite if it exists — append if it does):
  ~/Documents/FenceSpace-Fntend/fencespace/tasks/migration-inventory.md

  Contents:

  ### Section 1: Component Mapping
  For each scraper component/page:
  - Source file path
  - What it does (2-3 sentences)
  - Real frontend target (which file to extend)
  - Agent responsible
  - Supabase tables it needs
  - Status: PENDING

  Use this mapping:
  | Scraper source | Real frontend target | Agent |
  |---|---|---|
  | components/BracketVisualizer.tsx | bracket.js (extend) | 2 |
  | components/H2HComparison.tsx | h2h.js (extend) | 3 |
  | components/CareerTimeline.tsx | athlete/timeline/ (new page) | 4 |
  | components/FencerComparisonTool.tsx | fencers/compare/ (new page) | 4 |
  | components/CompetitionCalendar.tsx | events/main.js (extend) | 5 |
  | components/AthleteQuiz.tsx | quiz/ (new page) | 6 |
  | components/NewsFeed.tsx | index.html news section (extend) | 6 |
  | components/RankingSparkline.tsx | ranking-sparkline.js (new shared util) | 7 |
  | components/CountryMedalHeatmap.tsx | countries/main.js (extend) | 7 |
  | components/FederationOverview.tsx | countries/main.js (extend) | 7 |
  | app/page.tsx | index.html + main.js (extend) | 8 |
  | app/fencers/page.tsx | search/main.js (extend) | 8 |
  | app/tournaments/page.tsx | results/main.js (extend) | 8 |
  | app/rankings/page.tsx | rankings/ (extend) | 8 |
  | pages/head-to-head.tsx | h2h.js (extend) | 3 |
  | pages/news.tsx | news/ (new page or extend) | 6 |

  ### Section 2: API Contract
  For each function in src/lib/api.ts:
  - Function name
  - Parameters
  - What table/endpoint it reads
  - Equivalent window.supabaseGet call for real frontend

  ### Section 3: Type Definitions
  List every exported type from src/lib/types.ts with its shape.
  These tell migration agents what data fields each component expects.

  ### Section 4: Mock Fixtures
  List fixture shapes from src/lib/fixtures.ts —
  these are the exact data shapes migration agents must match from real Supabase tables.

  ### Section 5: Real Frontend Data Layer Reference
  Document the pattern every agent must follow:
  ```js
  // All data fetching in real frontend:
  window.supabaseGet(table, queryString) // returns Promise<any[]>
  window.supabasePost(table, body)        // for inserts (if available)

  // Config:
  window.FS_RUNTIME_CONFIG = { supabaseUrl, supabaseAnonKey, apiBase }

  // Table aliases (always use these, not raw fs_* names for reads):
  fs_fencers    → fs_public_fencers
  fs_tournaments → fs_public_tournaments
  fs_results    → fs_public_results
  fs_clubs      → fs_public_clubs
  fs_posts      → fs_public_posts

  // IIFE pattern (every real frontend JS file uses this):
  (() => {
    // code
    function init() { ... }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
      init();
    }
  })();

  // Safety guard at top of every function using supabaseGet:
  if (typeof window.supabaseGet !== 'function') return;

  Step 4: Clean up the scraper repo

  The scraper frontend is a disconnected Next.js placeholder — it has never served
  real users and runs in mock mode only. Remove it from the scraper repo.

  1. Delete:
  rm -rf ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/
  2. Read ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend_api_contract.py
    - If it contains only documentation/schema definitions with no runtime imports
  from other scraper scripts, delete it too.
    - If other scraper .py files import from it, keep it but add at the top:
    NOTE: The Next.js frontend has been removed. Features migrated to

    ~/Documents/FenceSpace-Fntend/fencespace/ (vanilla HTML/JS/CSS).

    See tasks/migration-inventory.md for details.

  3. Remove any frontend-specific entries from:
  ~/Documents/FenceSpace-Scraper/fencespace-scraper/.gitignore
  (keep Python, general entries — remove only Next.js / node_modules lines
  that no longer apply since the frontend directory is gone)

  Step 5: Verify

  Run:
    ls ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/ 2>&1
  Should output: "No such file or directory"

  Run:
    ls ~/Documents/FenceSpace-Fntend/fencespace/tasks/migration-inventory.md
  Should show the file exists.

  Report:
  - Number of scraper files removed
  - Sections written in inventory file
  - Any .py files kept vs deleted

  ---

  ## Agent 2 — Extend bracket.js with Full BracketVisualizer

  You are migrating the FenceSpace project.
  Your job: extend bracket.js in the real frontend with all features from the scraper's
  BracketVisualizer component. Add only — do not remove or overwrite any existing code.

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read everything before touching anything

  Read ALL of these before writing a single line:
  - ~/Documents/FenceSpace-Fntend/fencespace/bracket.js
  - ~/Documents/FenceSpace-Fntend/fencespace/tournament/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/tournament/main.js
  - ~/Documents/FenceSpace-Fntend/fencespace/tournament/styles.css
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/BracketVisualizer.tsx
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css (for CSS variable names)

  Map exactly:
  - What does bracket.js already do? What functions exist?
  - What does tournament/main.js already call from bracket.js?
  - What does BracketVisualizer.tsx do that bracket.js does NOT yet do?

  Only implement the delta — the missing features.

  Step 2: Features in BracketVisualizer.tsx to port

  1. normalizeBracket(bouts): group bouts by round, sort rounds in DE order
  (Table of 64 → 32 → 16 → Quarterfinals → Semifinals → Final)
  2. Bye handling: fencer_b null → render "BYE" with muted styling, auto-advance fencer_a
  3. Winner highlight: add is-winner class to winning fencer row
  4. Fencer links: fencer name → <a href="/athlete/?id={id}">
  5. Score display: show score_a and score_b, "–" if null
  6. Empty state: "No bracket data available" when bouts array is empty
  7. Loading state: skeleton placeholder while fetching
  8. Error state: error message if supabaseGet fails
  9. Mobile: horizontal scroll container wrapping all rounds
  10. Public API: window.FsBracket.render(containerEl, tournamentId, eventId)

  Step 3: Data fetching (add if missing from bracket.js)

  If bracket.js does not already fetch bout data, add:

  async function fetchBracketBouts(tournamentId, eventId) {
    if (typeof window.supabaseGet !== 'function') return [];
    const params = [
      `tournament_id=eq.${encodeURIComponent(tournamentId)}`,
      eventId ? `event_id=eq.${encodeURIComponent(eventId)}` : null,
      'phase=eq.DE',
      'order=round.asc,bout_order.asc',
      'select=*'
    ].filter(Boolean).join('&');
    return window.supabaseGet('fs_bouts', params).catch(() => []);
  }

  Step 4: HTML structure for match cards

  Only add CSS classes that don't exist yet in tournament/styles.css.
  Match the naming convention already used in that file.

  Required classes (add if missing):
  .fs-bracket-container { display: flex; overflow-x: auto; gap: 1rem; padding-bottom: 1rem; }
  .fs-bracket-round { display: flex; flex-direction: column; min-width: 200px; gap: 0.5rem; }
  .fs-bracket-round-label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--color-muted, #888); padding: 0.25rem 0; }
  .fs-bracket-match { border: 1px solid var(--color-border, #333); border-radius: 6px; overflow: hidden; }
  .fs-bracket-match-meta { font-size: 0.7rem; color: var(--color-muted, #888); padding: 0.25rem 0.5rem; border-bottom: 1px solid var(--color-border, #333); display: flex; justify-content: space-between; }
  .fs-bracket-row { display: flex; align-items: center; padding: 0.35rem 0.5rem; gap: 0.5rem; }
  .fs-bracket-row.is-winner { background: var(--color-surface-active, rgba(255,255,255,0.06)); font-weight: 600; }
  .fs-bracket-fencer { flex: 1; text-decoration: none; color: inherit; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.875rem; }
  .fs-bracket-score { font-variant-numeric: tabular-nums; font-size: 0.875rem; color: var(--color-muted, #888); min-width: 1.5rem; text-align: right; }
  .fs-bracket-bye .fs-bracket-fencer { color: var(--color-muted, #888); font-style: italic; }

  Step 5: Wire into tournament page

  After reading tournament/index.html and tournament/main.js:

  If a bracket section container already exists in index.html: extend it.
  If not: add a <section id="fs-bracket-section"> to tournament/index.html
  in a logical position (after results, before footer).

  In tournament/main.js: if bracket initialization is already called, leave it.
  If not: add a call to window.FsBracket.render() when tournament data loads,
  guarded by: if (window.FsBracket && typeof window.FsBracket.render === 'function')

  Add <script src="/bracket.js"></script> to tournament/index.html
  if it is not already there.

  Rules

  - Read existing files fully before any edit
  - Add only — never remove or overwrite existing functions
  - If a function already exists in bracket.js, do not redefine it — only add missing ones
  - Pure vanilla JS, IIFE pattern, no imports, no framework
  - window.supabaseGet for all data fetching
  - escapeHtml all fencer names and tournament data before innerHTML
  - No TypeScript, no JSX remnants

  ---

  ## Agent 3 — Extend h2h.js with Full H2HComparison

  You are migrating the FenceSpace project.
  Your job: extend h2h.js in the real frontend with all features from the scraper's
  H2HComparison component and head-to-head page. Add only — preserve everything existing.

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read everything before touching anything

  Read ALL of these:
  - ~/Documents/FenceSpace-Fntend/fencespace/h2h.js
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/H2HComparison.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/pages/head-to-head.tsx
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css
  - ~/Documents/FenceSpace-Fntend/fencespace/styles.css

  Also grep for "h2h" across the real frontend:
    grep -rl "h2h" ~/Documents/FenceSpace-Fntend/fencespace/ --include=".html" --include=".js"

  Read every file that references h2h.

  Map: what does h2h.js already do? What HTML elements does it expect?
  Only implement what is missing.

  Step 2: Features to port from H2HComparison.tsx

  1. Fencer search with autocomplete:
    - Debounced text input (300ms) → search fs_public_fencers by name
    - Dropdown shows: name, country, weapon, world_rank
    - Select sets fencer_a or fencer_b in state
    - Clear/reset button per picker
  2. H2H stats display:
    - Total bouts between the two
    - Fencer A wins / Fencer B wins
    - Win percentage bar (CSS width, not canvas)
    - Last meeting date + who won
    - Total touches scored by each
  3. Bout history table:
    - Per bout: date, tournament name (linked to /tournament/?id=X), score_a–score_b, winner highlighted
    - Sorted by date descending
    - Empty state: "These fencers have no recorded bouts against each other"
  4. URL params: ?fencer_a={id}&fencer_b={id}
    - On page load: if both params present, auto-run the lookup
    - Share button: updates URL without reload (history.pushState)
  5. API calls:
  // Fencer search
  window.supabaseGet('fs_public_fencers',
    `name=ilike.*${encodeURIComponent(q)}*&limit=10&select=id,name,country,weapon,world_rank`)

  // H2H aggregate record
  window.supabaseGet('fs_head_to_head',
    `or=(and(fencer_a_id.eq.${aId},fencer_b_id.eq.${bId}),and(fencer_a_id.eq.${bId},fencer_b_id.eq.${aId}))&limit=1`)

  // Individual bout history
  window.supabaseGet('fs_bouts',
    `or=(and(fencer_a_id.eq.${aId},fencer_b_id.eq.${bId}),and(fencer_a_id.eq.${bId},fencer_b_id.eq.${aId}))&order=created_at.desc&limit=50&select=*`)

  // Tournament names for bout history
  window.supabaseGet('fs_public_tournaments',
    `id=in.(${tournamentIds.join(',')})&select=id,name`)

  Step 3: Check for existing H2H HTML page

  Grep for h2h pages. If no dedicated H2H HTML page exists yet:
  - Check if h2h container exists anywhere in existing HTML files
  - If not, CREATE ~/Documents/FenceSpace-Fntend/fencespace/h2h/index.html

  When creating the new page, copy the exact <head>, nav, and footer structure
  from ~/Documents/FenceSpace-Fntend/fencespace/athlete/index.html —
  do not invent a new structure. Replace only the page-specific <main> content.

  Required HTML containers for h2h.js to target:
  <div id="fs-h2h-root">
    <div class="h2h-search-row">
      <div class="h2h-picker" id="h2h-picker-a">
        <input type="text" class="h2h-input" placeholder="Search fencer A…" autocomplete="off">
        <div class="h2h-dropdown" hidden></div>
        <div class="h2h-selected" hidden></div>
      </div>
      <div class="h2h-vs">vs</div>
      <div class="h2h-picker" id="h2h-picker-b">
        <input type="text" class="h2h-input" placeholder="Search fencer B…" autocomplete="off">
        <div class="h2h-dropdown" hidden></div>
        <div class="h2h-selected" hidden></div>
      </div>
    </div>
    <div id="h2h-loading" hidden>Loading…</div>
    <div id="h2h-stats" hidden></div>
    <div id="h2h-history" hidden></div>
    <div id="h2h-empty" hidden>Select two fencers to compare.</div>
  </div>

  Step 4: Extend h2h.js

  Add only the functions that do not already exist. If a function name already
  appears in h2h.js, do not redefine it — work around it or extend it.

  Wrap all new code inside the existing IIFE if one exists, or add a new adjacent IIFE.

  Step 5: Navigation

  If a new h2h/ page was created, check these files and add a nav link if missing:
  - ~/Documents/FenceSpace-Fntend/fencespace/tasks/_nav-template.html
  - ~/Documents/FenceSpace-Fntend/fencespace/index.html (mobile menu)

  Only add — do not remove or reorder existing nav items.

  Rules

  - Read existing h2h.js fully before editing
  - Add only — no removals, no overwrites of existing functions
  - Pure vanilla JS, IIFE pattern
  - window.supabaseGet for all data
  - Debounce search: 300ms
  - escapeHtml all user data before innerHTML
  - Guard: if (typeof window.supabaseGet !== 'function') return;

  ---

  ## Agent 4 — New Pages: CareerTimeline + FencerComparisonTool

  You are migrating the FenceSpace project.
  Your job: create two brand-new pages in the real frontend.
  These pages do not exist yet — you are adding, not modifying.
  You will also add small navigation links to existing pages (additive only).

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read the reference pattern

  Read these files to understand the exact page structure to replicate:
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/main.js
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/styles.css
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css
  - ~/Documents/FenceSpace-Fntend/fencespace/styles.css
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/CareerTimeline.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/FencerComparisonTool.tsx

  Note the exact head tags, nav structure, CSS includes, footer, script includes used in athlete/index.html.
  Your new pages must match this structure exactly.

  Task A: Career Timeline page

  New files to CREATE:

  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/timeline/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/timeline/main.js

  index.html structure:

  Copy the full  and nav/footer from athlete/index.html.
  Set title: "Career Timeline — FenceSpace"
  Main content container:
  <main class="ts-main">
    <div id="fs-timeline-header"></div>
    <div class="timeline-filters" id="timeline-filters" hidden>
      <div class="filter-group">
        <label>Weapon</label>
        <div class="btn-group" id="timeline-weapon-filter">
          <button class="btn-filter active" data-weapon="all">All</button>
          <button class="btn-filter" data-weapon="foil">Foil</button>
          <button class="btn-filter" data-weapon="epee">Épée</button>
          <button class="btn-filter" data-weapon="sabre">Sabre</button>
        </div>
      </div>
      <div class="filter-group">
        <label>Year</label>
        <select id="timeline-year-filter"><option value="all">All years</option></select>
      </div>
      <div class="filter-group">
        <label>Category</label>
        <select id="timeline-category-filter">
          <option value="all">All</option>
          <option value="Senior">Senior</option>
          <option value="Junior">Junior</option>
          <option value="Cadet">Cadet</option>
          <option value="Veteran">Veteran</option>
        </select>
      </div>
    </div>
    <div id="fs-timeline-list"></div>
    <div id="fs-timeline-loading" class="loading-state">Loading…</div>
    <div id="fs-timeline-empty" class="empty-state" hidden>No results found.</div>
    <div id="fs-timeline-error" class="error-state" hidden>Could not load career timeline.</div>
  </main>

  main.js implementation:

  (() => {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const FENCER_ID = params.get('id') || '';

    let allResults = [];
    let tournamentMap = {};
    let activeWeapon = 'all';
    let activeYear = 'all';
    let activeCategory = 'all';

    if (!FENCER_ID) {
      document.getElementById('fs-timeline-error').hidden = false;
      document.getElementById('fs-timeline-loading').hidden = true;
      return;
    }

    async function loadTimeline() {
      if (typeof window.supabaseGet !== 'function') return;

      // 1. Fetch fencer profile
      const [fencerRows] = await Promise.all([
        window.supabaseGet('fs_public_fencers', `id=eq.${encodeURIComponent(FENCER_ID)}&limit=1`)
      ]).catch(() => [[]]);

      const fencer = fencerRows && fencerRows[0];
      if (!fencer) {
        document.getElementById('fs-timeline-error').hidden = false;
        document.getElementById('fs-timeline-loading').hidden = true;
        return;
      }

      // Render header
      document.getElementById('fs-timeline-header').innerHTML = `
        <h1 class="ts-page-title">${escapeHtml(fencer.name || 'Unknown Fencer')}</h1>
        <p class="ts-page-subtitle">${escapeHtml(fencer.country || '')} · ${escapeHtml(fencer.weapon || '')} · <a href="/athlete/?id=${encodeURIComponent(FENCER_ID)}">View profile</a></p>
      `;
      document.title = `${fencer.name || 'Fencer'} — Career Timeline · FenceSpace`;

      // 2. Fetch results
      allResults = await window.supabaseGet('fs_public_results',
        `fencer_id=eq.${encodeURIComponent(FENCER_ID)}&order=date.desc.nullslast&limit=500&select=*`
      ).catch(() => []);

      if (!allResults.length) {
        document.getElementById('fs-timeline-empty').hidden = false;
        document.getElementById('fs-timeline-loading').hidden = true;
        document.getElementById('timeline-filters').hidden = true;
        return;
      }

      // 3. Fetch tournament names
      const tIds = [...new Set(allResults.map(r => r.tournament_id).filter(Boolean))];
      if (tIds.length) {
        const tournaments = await window.supabaseGet('fs_public_tournaments',
          `id=in.(${tIds.slice(0, 200).map(id => encodeURIComponent(id)).join(',')})&select=id,name,location`
        ).catch(() => []);
        tournaments.forEach(t => { tournamentMap[t.id] = t; });
      }

      // 4. Populate year filter
      const years = [...new Set(allResults.map(r => r.date ? r.date.slice(0, 4) : null).filter(Boolean))].sort().reverse();
      const yearSel = document.getElementById('timeline-year-filter');
      years.forEach(y => {
        const opt = document.createElement('option');
        opt.value = y; opt.textContent = y;
        yearSel.appendChild(opt);
      });

      document.getElementById('timeline-filters').hidden = false;
      document.getElementById('fs-timeline-loading').hidden = true;
      renderTimeline();
      bindFilters();
    }

    function renderTimeline() {
      const list = document.getElementById('fs-timeline-list');
      const filtered = allResults.filter(r => {
        if (activeWeapon !== 'all' && !(r.weapon || '').toLowerCase().includes(activeWeapon)) return false;
        if (activeYear !== 'all' && !(r.date || '').startsWith(activeYear)) return false;
        if (activeCategory !== 'all' && r.category !== activeCategory) return false;
        return true;
      });

      if (!filtered.length) {
        list.innerHTML = '';
        document.getElementById('fs-timeline-empty').hidden = false;
        return;
      }
      document.getElementById('fs-timeline-empty').hidden = true;

      list.innerHTML = filtered.map(r => {
        const t = tournamentMap[r.tournament_id] || {};
        const isPodium = r.place && Number(r.place) <= 3;
        const date = r.date ? new Date(r.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
        return `
          <article class="timeline-entry${isPodium ? ' timeline-entry--podium' : ''}" data-year="${escapeHtml((r.date || '').slice(0, 4))}" data-weapon="${escapeHtml((r.weapon || '').toLowerCase())}">
            <div class="timeline-date">${escapeHtml(date)}</div>
            <div class="timeline-content">
              <a class="timeline-tournament" href="/tournament/?id=${encodeURIComponent(r.tournament_id || '')}">${escapeHtml(t.name || r.tournament_id || 'Unknown tournament')}</a>
              <div class="timeline-meta">${[r.weapon, r.category, t.location].filter(Boolean).map(escapeHtml).join(' · ')}</div>
              <div class="timeline-result">
                <span class="timeline-place">${r.place ? `#${escapeHtml(String(r.place))}` : '—'}</span>
                ${r.points ? `<span class="timeline-points">${escapeHtml(String(r.points))} pts</span>` : ''}
              </div>
            </div>
          </article>
        `;
      }).join('');
    }

    function bindFilters() {
      document.getElementById('timeline-weapon-filter').addEventListener('click', e => {
        const btn = e.target.closest('[data-weapon]');
        if (!btn) return;
        activeWeapon = btn.dataset.weapon;
        document.querySelectorAll('#timeline-weapon-filter .btn-filter').forEach(b => b.classList.toggle('active', b === btn));
        renderTimeline();
      });
      document.getElementById('timeline-year-filter').addEventListener('change', e => {
        activeYear = e.target.value;
        renderTimeline();
      });
      document.getElementById('timeline-category-filter').addEventListener('change', e => {
        activeCategory = e.target.value;
        renderTimeline();
      });
    }

    function escapeHtml(str) {
      return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', loadTimeline, { once: true });
    } else {
      loadTimeline();
    }
  })();

  Add minimal CSS to athlete/styles.css (append only, don't replace existing styles):
  - .timeline-entry, .timeline-entry--podium, .timeline-date, .timeline-content
  - .timeline-tournament, .timeline-meta, .timeline-result, .timeline-place, .timeline-points

  Task B: Fencer Comparison page

  New files to CREATE:

  - ~/Documents/FenceSpace-Fntend/fencespace/fencers/compare/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/fencers/compare/main.js

  Read first (to understand fencer search pattern):

  - ~/Documents/FenceSpace-Fntend/fencespace/search/main.js
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/FencerComparisonTool.tsx

  Check if a /fencers/ directory already exists. If not, create it with compare/ inside.

  index.html structure (copy head/nav/footer from athlete/index.html):

  <main class="ts-main">
    <h1 class="ts-page-title">Compare Fencers</h1>
    <div class="compare-pickers">
      <div class="compare-picker" id="compare-picker-a">
        <input type="text" class="compare-input" placeholder="Search fencer A…" autocomplete="off">
        <div class="compare-dropdown" hidden></div>
        <div class="compare-selected" hidden></div>
      </div>
      <div class="compare-vs">vs</div>
      <div class="compare-picker" id="compare-picker-b">
        <input type="text" class="compare-input" placeholder="Search fencer B…" autocomplete="off">
        <div class="compare-dropdown" hidden></div>
        <div class="compare-selected" hidden></div>
      </div>
    </div>
    <div id="compare-table-wrap" hidden></div>
    <div id="compare-loading" hidden>Loading…</div>
    <div id="compare-empty">Select two fencers to compare their stats.</div>
  </main>

  main.js implementation:

  Implement:
  1. Fencer search autocomplete (same pattern as agent 3 — search fs_public_fencers)
  2. URL params: ?fencer_a={id}&fencer_b={id} — auto-load on page open
  3. Share button: history.pushState with both IDs
  4. Stats comparison table from:
    - fs_public_fencers: world_rank, fie_points, weapon, country, category
    - fs_fencer_career_stats: total_tournaments, total_bouts_won (if table exists)
    - fs_fencer_stats: win_rate, avg_place (if table exists)
  5. Winner highlight: lower world_rank = better; higher points/wins = better
  Add class stat-winner to the winning cell

  const STATS = [
    { key: 'world_rank', label: 'World Rank', lowerIsBetter: true },
    { key: 'fie_points', label: 'FIE Points', lowerIsBetter: false },
    { key: 'country', label: 'Country', compare: false },
    { key: 'weapon', label: 'Weapon', compare: false },
    { key: 'category', label: 'Category', compare: false },
  ];

  Step 3: Add navigation links (additive only)

  In ~/Documents/FenceSpace-Fntend/fencespace/athlete/index.html:
  Add a "Career Timeline →" link somewhere logical on the athlete page
  (after the athlete name/header section, as a secondary action link).
  Do not remove or reorder any existing content.

  In ~/Documents/FenceSpace-Fntend/fencespace/search/index.html (if it exists):
  Add a "Compare fencers →" link near the top.
  Do not remove or reorder any existing content.

  Rules

  - These are NEW files — full implementation required, not extensions
  - Follow the exact HTML pattern of athlete/index.html
  - Pure vanilla JS, IIFE pattern
  - window.supabaseGet for all data, guarded by typeof check
  - escapeHtml all data before innerHTML
  - No framework, no build step, no imports

  ---

  ## Agent 5 — Extend events/ with CompetitionCalendar Features

  You are migrating the FenceSpace project.
  Your job: extend the events/ page in the real frontend with full calendar features
  from the scraper's CompetitionCalendar component. Add only — preserve all existing code.

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read everything before touching anything

  Read ALL of these:
  - ~/Documents/FenceSpace-Fntend/fencespace/events/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/events/main.js
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/CompetitionCalendar.tsx
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css
  - ~/Documents/FenceSpace-Fntend/fencespace/styles.css

  Map:
  - What does events/main.js already implement?
  - What HTML elements/IDs does it already expect?
  - What does CompetitionCalendar.tsx have that events/ does not?

  Only implement the delta.

  Step 2: Features to add

  From CompetitionCalendar.tsx, identify which of these are missing in events/main.js
  and add only those:

  1. Tabs: Upcoming / Recent / All
    - Upcoming: date=gte.{today}&order=date.asc
    - Recent: date=lt.{today}&order=date.desc&limit=50
    - All: order=date.desc
    - If tabs already exist in a different form, extend them — don't replace
  2. Filters:
    - Weapon: All / Foil / Épée / Sabre
    - Category: All / Senior / Junior / Cadet / Veteran
    - Level: All / World Cup / Grand Prix / World Championships / Continental / National
    - If any filter already exists, skip it
  3. Text search: name=ilike.{query} (debounced 300ms)
    - If search already exists, skip
  4. Load more / pagination: offset-based, 24 per page, "Load more" button appends
    - If pagination already exists in a different form, extend it
  5. ICS export: client-side calendar file download
  function generateIcs(events) {
    const lines = [
      'BEGIN:VCALENDAR', 'VERSION:2.0',
      'PRODID:-//FenceSpace//Events//EN', 'CALSCALE:GREGORIAN',
    ];
    for (const ev of events) {
      const dtstart = (ev.date || '').replace(/-/g, '');
      if (!dtstart) continue;
      lines.push('BEGIN:VEVENT',
        `UID:fs-${ev.id}@fencespace`,
        `DTSTART;VALUE=DATE:${dtstart}`,
        `SUMMARY:${(ev.name || '').replace(/[,;\\]/g, s => '\\' + s)}`,
        `LOCATION:${(ev.location || '').replace(/[,;\\]/g, s => '\\' + s)}`,
        'END:VEVENT');
    }
    lines.push('END:VCALENDAR');
    return lines.join('\r\n');
  } 

  function downloadIcs(events) {
    const blob = new Blob([generateIcs(events)], { type: 'text/calendar' });
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob), download: 'fencespace-events.ics'
    });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  } 
  
  6. Query builder (add if missing):
  function buildEventsQuery(tab, weapon, category, level, search, offset) {
    const today = new Date().toISOString().split('T')[0];
    const parts = []; 
    if (tab === 'upcoming') parts.push(`date=gte.${today}`, 'order=date.asc');
    else if (tab === 'recent') parts.push(`date=lt.${today}`, 'order=date.desc');
    else parts.push('order=date.desc');
    if (weapon && weapon !== 'all') parts.push(`weapon=ilike.*${encodeURIComponent(weapon)}*`);
    if (category && category !== 'all') parts.push(`category=eq.${encodeURIComponent(category)}`);
    if (level && level !== 'all') parts.push(`level=eq.${encodeURIComponent(level)}`);
    if (search) parts.push(`name=ilike.*${encodeURIComponent(search)}*`);
    parts.push(`limit=24&offset=${offset || 0}&select=*`);
    return parts.join('&');
  } 

  Step 3: HTML additions to events/index.html

  Read the existing HTML first. Add ONLY what is missing:

  - If no tab buttons exist: add <div class="events-tabs" id="events-tabs"> before the event list
  - If no filter row exists: add <div class="events-filters" id="events-filters"> with weapon/category/level selects
  - If no search input exists: add <input type="text" id="events-search">
  - If no ICS button exists: add <button id="events-ics-btn" type="button">Export .ics</button>
  - If no load more button exists: add <button id="events-load-more" hidden>Load more</button> after event list

  For each addition: insert in a logical position relative to existing content.
  Do not move or remove any existing HTML elements.

  Step 4: Event card HTML

  If event cards are already rendered in main.js, check what fields they show.
  Add any missing fields (end_date, level badge, status badge, participant_count)
  to the existing card template — do not replace the template.

  Required fields to ensure are shown:
  - Tournament name (linked to /tournament/?id=X)
  - Date (+ end_date if available)
  - Location, country
  - Weapon, category
  - Level badge
  - Status badge (upcoming / ongoing / completed)
  - Participant count (if available from fs_competition_details)

  Rules

  - Read existing events/main.js fully before any edit
  - Add code only — never remove or overwrite existing functions
  - If a function already exists, do not redefine it
  - Append new code inside the existing IIFE or as a new adjacent IIFE
  - Pure vanilla JS
  - window.supabaseGet for data, guarded by typeof check
  - escapeHtml all data before innerHTML
  - Debounce search input: 300ms

  ---

  ## Agent 6 — AthleteQuiz (new page) + Extend NewsFeed

  You are migrating the FenceSpace project.
  Your job:
  A) Create a new AthleteQuiz page (does not exist in real frontend yet)
  B) Extend the home page news section with NewsFeed features (add only)

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read reference files

  Read ALL before touching anything:
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/index.html  (page pattern)
  - ~/Documents/FenceSpace-Fntend/fencespace/index.html          (home page — find news section)
  - ~/Documents/FenceSpace-Fntend/fencespace/main.js             (find existing news code)
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/AthleteQuiz.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/NewsFeed.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/pages/news.tsx
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css
  
  Task A: AthleteQuiz — New Page

  Check if ~/Documents/FenceSpace-Fntend/fencespace/quiz/ exists.
  If it does, read what's there and extend it. If not, create fresh.

  CREATE: ~/Documents/FenceSpace-Fntend/fencespace/quiz/index.html

  Copy the exact head/nav/footer from athlete/index.html.
  Set title: "FenceSpace Quiz"

  Main content:
  <main class="ts-main">
    <!-- Start screen -->
    <section id="quiz-start" class="quiz-screen">
      <h1 class="ts-page-title">FenceSpace Quiz</h1>
      <p>Test your fencing knowledge. 10 questions per round.</p>
      <button class="btn-primary" id="quiz-start-btn" type="button">Start quiz</button>
    </section>

    <!-- Question screen -->
    <section id="quiz-question" class="quiz-screen" hidden>
      <div class="quiz-progress">
        <div class="quiz-progress-bar"><div class="quiz-progress-fill" id="quiz-progress-fill"></div></div>
        <span id="quiz-progress-label">Question 1 of 10</span>
        <span class="quiz-streak" id="quiz-streak" hidden>🔥 <span id="quiz-streak-count">0</span> streak</span>
      </div>
      <div class="quiz-card">
        <p class="quiz-question" id="quiz-question-text"></p>
        <div class="quiz-options" id="quiz-options"></div>
        <div class="quiz-reveal" id="quiz-reveal" hidden>
          <p id="quiz-reveal-text"></p>
          <button class="btn-primary" id="quiz-next-btn" type="button">Next →</button>
        </div>
      </div>
    </section>
    
    <!-- End screen -->
    <section id="quiz-end" class="quiz-screen" hidden>
      <h2>Quiz complete!</h2>
      <p class="quiz-final-score">You scored <strong id="quiz-final-score-val">0</strong> / 10</p>
      <button class="btn-primary" id="quiz-play-again" type="button">Play again</button>
      <a href="/" class="btn-secondary">Back to home</a>
    </section>
  </main>

  CREATE: ~/Documents/FenceSpace-Fntend/fencespace/quiz/main.js

  (() => {
    if (typeof window === 'undefined') return;

    const TOTAL_QUESTIONS = 10;
    let questions = [];
    let currentIndex = 0;
    let score = 0;
    let streak = 0;

    // Screen management
    function showScreen(id) {
      ['quiz-start', 'quiz-question', 'quiz-end'].forEach(s => {
        const el = document.getElementById(s);
        if (el) el.hidden = s !== id;
      });
    }

    // Question generation from fencer data
    async function generateQuestions() {
      if (typeof window.supabaseGet !== 'function') return [];

      // Try fs_trivia_questions first (precomputed)
      const trivia = await window.supabaseGet('fs_trivia_questions',
        'order=random()&limit=20&select=*').catch(() => []);
      if (trivia && trivia.length >= 10) {
        return trivia.slice(0, 10).map(t => ({
          text: t.question,
          correct: t.correct_answer,
          options: shuffle([t.correct_answer, ...(t.wrong_answers || []).slice(0, 3)]),
          source: t.table || 'fs_trivia_questions'
        }));
      }

      // Fallback: generate from fencer data
      const fencers = await window.supabaseGet('fs_public_fencers',
        'world_rank=gte.1&world_rank=lte.500&order=random()&limit=40&select=id,name,country,weapon,world_rank'
      ).catch(() => []);

      if (!fencers || fencers.length < 8) return [];
      return buildQuestionsFromFencers(fencers).slice(0, TOTAL_QUESTIONS);
    }

    function buildQuestionsFromFencers(fencers) {
      const qs = [];
      const shuffled = shuffle([...fencers]);

      // Country questions
      for (let i = 0; i < Math.min(4, shuffled.length); i++) {
        const f = shuffled[i];
        if (!f.country || !f.name) continue;
        const wrong = shuffle(fencers.filter(x => x.country !== f.country).map(x => x.country).filter(Boolean))
          .filter((v, i, a) => a.indexOf(v) === i).slice(0, 3);
        if (wrong.length < 3) continue;
        qs.push({
          text: `Which country does ${f.name} represent?`,
          correct: f.country,
          options: shuffle([f.country, ...wrong]),
          source: 'fs_public_fencers'
        });
      }

      // Weapon questions
      for (let i = 4; i < Math.min(8, shuffled.length); i++) {
        const f = shuffled[i];
        if (!f.weapon || !f.name) continue;
        const weapons = ['Foil', 'Épée', 'Sabre'].filter(w => w.toLowerCase() !== (f.weapon || '').toLowerCase());
        qs.push({
          text: `What weapon does ${f.name} use?`,
          correct: f.weapon,
          options: shuffle([f.weapon, ...weapons]),
          source: 'fs_public_fencers'
        });
      }

      // Rank questions
      for (let i = 8; i < Math.min(12, shuffled.length); i++) {
        const f = shuffled[i];
        if (!f.world_rank || !f.name) continue;
        const rank = Number(f.world_rank);
        const wrongRanks = [rank + 5, rank - 3, rank + 12].filter(r => r > 0 && r !== rank).slice(0, 3);
        if (wrongRanks.length < 3) continue;
        qs.push({
          text: `What is ${f.name}'s current world ranking?`,
          correct: String(rank),
          options: shuffle([String(rank), ...wrongRanks.map(String)]),
          source: 'fs_public_fencers'
        });
      }

      return shuffle(qs);
    }

    function shuffle(arr) {
      const a = [...arr];
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    }

    function renderQuestion(q) {
      document.getElementById('quiz-question-text').textContent = q.text;
      document.getElementById('quiz-progress-label').textContent = `Question ${currentIndex + 1} of ${TOTAL_QUESTIONS}`;
      document.getElementById('quiz-progress-fill').style.width = `${((currentIndex) / TOTAL_QUESTIONS) * 100}%`;

      const opts = document.getElementById('quiz-options');
      opts.innerHTML = q.options.map(opt => `
        <button class="quiz-option" type="button" data-value="${escapeHtml(opt)}">${escapeHtml(opt)}</button>
      `).join('');

      document.getElementById('quiz-reveal').hidden = true;
      opts.addEventListener('click', handleOptionClick, { once: true });
    }

    function handleOptionClick(e) {
      const btn = e.target.closest('.quiz-option');
      if (!btn) return;
      const selected = btn.dataset.value;
      const q = questions[currentIndex];
      const isCorrect = selected === q.correct;

      document.querySelectorAll('.quiz-option').forEach(b => {
        b.disabled = true;
        if (b.dataset.value === q.correct) b.classList.add('is-correct');
        else if (b === btn && !isCorrect) b.classList.add('is-wrong');
      });

      if (isCorrect) { score++; streak++; } else { streak = 0; }

      const streakEl = document.getElementById('quiz-streak');
      const streakCount = document.getElementById('quiz-streak-count');
      if (streak >= 2) {
        streakEl.hidden = false;
        streakCount.textContent = streak;
      } else {
        streakEl.hidden = true;
      }

      const reveal = document.getElementById('quiz-reveal');
      document.getElementById('quiz-reveal-text').textContent = isCorrect
        ? `Correct! (source: ${q.source})`
        : `Not quite. The answer is: ${q.correct} (source: ${q.source})`;
      reveal.hidden = false;

      document.getElementById('quiz-next-btn').onclick = () => {
        currentIndex++;
        if (currentIndex >= questions.length) {
          showEndScreen();
        } else {
          renderQuestion(questions[currentIndex]);
        }
      };
    }

    function showEndScreen() {
      showScreen('quiz-end');
      document.getElementById('quiz-final-score-val').textContent = score;
      document.getElementById('quiz-progress-fill').style.width = '100%';
    }

    async function startQuiz() {
      showScreen('quiz-question');
      document.getElementById('quiz-options').innerHTML = '<p class="quiz-loading">Loading questions…</p>';
      questions = await generateQuestions();
      if (!questions.length) {
        document.getElementById('quiz-options').innerHTML = '<p class="quiz-error">Could not load questions. Try again.</p>';
        return;
      }
      score = 0; streak = 0; currentIndex = 0;
      renderQuestion(questions[0]);
    }

    function escapeHtml(str) {
      return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function init() {
      document.getElementById('quiz-start-btn')?.addEventListener('click', startQuiz);
      document.getElementById('quiz-play-again')?.addEventListener('click', () => { showScreen('quiz-start'); });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
      init();
    }
  })();

  CREATE: ~/Documents/FenceSpace-Fntend/fencespace/quiz/style.css

  Minimal styles for quiz screens, option buttons, correct/wrong states, progress bar.
  Use CSS variables from ts-system.css. No external dependencies.

  Task B: Extend NewsFeed on home page

  Read first:

  Search index.html for: id="news", class="news", "articles", "feed", "posts"
  Search main.js for: news, articles, posts, loadNews, renderNews

  If news section already exists in index.html:
  - Do NOT remove or replace it
  - Identify the container ID/class
  - In main.js, find the existing news function and extend it if it's missing fields
  
  If no news section exists in index.html:
  - Add a <section class="ts-section" id="fs-news-section"> before the closing body
  with <div id="fs-news-grid" class="news-grid"></div> inside

  In main.js (or at the bottom in a new adjacent IIFE if main.js is too complex to modify):
  Add a loadNewsSection() function:

  async function loadNewsSection() {
    const grid = document.getElementById('fs-news-grid');
    if (!grid || typeof window.supabaseGet !== 'function') return;

    let items = await window.supabaseGet('fs_articles',
      'order=published_at.desc&limit=6&select=id,title,excerpt,published_at,source,url'
    ).catch(() => []);

    if (!items || !items.length) {
      items = await window.supabaseGet('fs_posts',
        'order=created_at.desc&limit=6&select=id,title,content,created_at'
      ).catch(() => []);
    }

    if (!items || !items.length) {
      grid.innerHTML = '<p class="empty-state">No news available.</p>';
      return;
    }

    function truncate(str, n) { return str && str.length > n ? str.slice(0, n) + '…' : (str || ''); }
    function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function fmtDate(d) { try { return new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch { return d||''; } }

    grid.innerHTML = items.map(a => `
      <article class="news-card">
        <div class="news-card-meta">${escHtml(fmtDate(a.published_at||a.created_at))}${a.source ? ' · ' + escHtml(a.source) : ''}</div>
        <h3 class="news-card-title">${a.url ? `<a href="${escHtml(a.url)}" rel="noopener">${escHtml(a.title)}</a>` : escHtml(a.title)}</h3>
        <p class="news-card-excerpt">${escHtml(truncate(a.excerpt||a.content, 140))}</p>
      </article>
    `).join('');
  }

  Call loadNewsSection() from the existing init/DOMContentLoaded block in main.js
  (append the call — do not restructure the existing init sequence).

  CREATE: ~/Documents/FenceSpace-Fntend/fencespace/news/index.html + main.js

  Full news listing page. Copy head/nav/footer from athlete/index.html.
  Paginated list of articles: 20 per page, Load more button.
  Same data sources (fs_articles → fs_posts fallback).

  Navigation: add quiz and news links

  In ~/Documents/FenceSpace-Fntend/fencespace/index.html mobile menu:
  Add <a href="/quiz/" class="js-mobile-link">Quiz</a> after existing links.
  Add <a href="/news/" class="js-mobile-link">News</a> if not already present.
  Do not remove or reorder existing mobile menu links.

  In ~/Documents/FenceSpace-Fntend/fencespace/tasks/_nav-template.html:
  Add quiz and news entries if missing. Do not modify other entries.

  Rules

  - quiz/ pages: full new implementation
  - index.html / main.js: extend only, never remove
  - Pure vanilla JS, IIFE pattern
  - window.supabaseGet, guarded by typeof check
  - escapeHtml on all data before innerHTML
  - No framework, no build step

  ---

  ## Agent 7 — Extend rankings/ and countries/ with Analytics Visualizations

  You are migrating the FenceSpace project.
  Your job: extend the rankings/ and countries/ pages with three analytics visualizations
  from the scraper. Add only — preserve all existing code in both pages.

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/
  SCRAPER (source of features): ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/

  Step 1: Read everything before touching anything

  Read ALL of these:
  - ~/Documents/FenceSpace-Fntend/fencespace/countries/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/countries/main.js
  - ~/Documents/FenceSpace-Fntend/fencespace/rankings/index.html
  - (any rankings/main.js if it exists)
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/athlete/main.js
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/RankingSparkline.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/CountryMedalHeatmap.tsx
  - ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/components/FederationOverview.tsx
  - ~/Documents/FenceSpace-Fntend/fencespace/ts-system.css
  
  Map what each live page already does. Only add missing features.

  Task A: RankingSparkline — new shared utility

  Check if ~/Documents/FenceSpace-Fntend/fencespace/ranking-sparkline.js exists.
  If it does, read it and extend it. If not, create it.

  CREATE/EXTEND: ~/Documents/FenceSpace-Fntend/fencespace/ranking-sparkline.js

  (() => {
    if (typeof window === 'undefined') return;

    async function fetchRankHistory(fencerId, weapon, months) {
      if (typeof window.supabaseGet !== 'function') return [];
      const cutoff = new Date();
      cutoff.setMonth(cutoff.getMonth() - (months || 12));
      const params = [
        `fencer_id=eq.${encodeURIComponent(fencerId)}`,
        weapon ? `weapon=ilike.*${encodeURIComponent(weapon)}*` : null,
        `date=gte.${cutoff.toISOString().split('T')[0]}`,
        'order=date.asc',
        'select=world_rank,date'
      ].filter(Boolean).join('&');
      return window.supabaseGet('fs_rankings_history', params).catch(() => []);
    }

    function renderSparklineSvg(ranks, width, height) {
      width = width || 60; height = height || 20;
      if (!ranks || ranks.length < 2) return '<span class="sparkline-na" aria-label="No trend data">—</span>';
      const values = ranks.map(r => Number(r.world_rank)).filter(n => n > 0);
      if (values.length < 2) return '<span class="sparkline-na">—</span>';
      const max = Math.max(...values);
      const min = Math.min(...values);
      const range = max - min || 1;
      const points = values.map((v, i) => {
        const x = (i / (values.length - 1)) * width;
        const y = ((v - min) / range) * height; // lower rank = top of SVG (intentional: rank 1 = y=0)
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
      const trend = values[values.length - 1] < values[0] ? 'up' : values[values.length - 1] > values[0] ? 'down' : 'flat';
      const color = trend === 'up' ? 'var(--color-success, #4ade80)' : trend === 'down' ? 'var(--color-danger, #f87171)' : 'var(--color-muted, #888)';
      return `<svg class="sparkline sparkline--${trend}" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true">
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
    }

    // Attach sparklines to elements with data-sparkline-fencer-id attribute
    async function attachSparklines(containerEl) {
      const targets = (containerEl || document).querySelectorAll('[data-sparkline-fencer-id]');
      for (const el of targets) {
        const fencerId = el.dataset.sparklineFencerId;
        const weapon = el.dataset.sparklineWeapon || '';
        const history = await fetchRankHistory(fencerId, weapon, 12);
        el.innerHTML = renderSparklineSvg(history, 60, 20);
      }
    }

    window.FsSparkline = { fetchRankHistory, renderSparklineSvg, attachSparklines };
  })();

  Wire into athlete/index.html: add <script src="/ranking-sparkline.js"></script> if not present.
  In athlete/main.js: after fencer profile renders, call
  if (window.FsSparkline) window.FsSparkline.attachSparklines();
  if not already called. Append only.

  Task B: CountryMedalHeatmap — extend countries/ page

  Read countries/index.html for a container with id containing "medal" or "heatmap".
  If none exists, add <div id="fs-medal-heatmap"></div> to countries/index.html
  in a logical position (after the country list section, before footer). Do not move existing elements.

  In countries/main.js, add a function loadMedalHeatmap() (skip if already exists):

  async function loadMedalHeatmap() {
    const container = document.getElementById('fs-medal-heatmap');
    if (!container || typeof window.supabaseGet !== 'function') return;

    const medals = await window.supabaseGet('fs_medal_tables',
      'order=total.desc&limit=200&select=country,weapon,gold,silver,bronze,total'
    ).catch(() => []);

    if (!medals || !medals.length) {
      container.innerHTML = '<p class="empty-state">No medal data available.</p>';
      return;
    }

    // Build weapon × country matrix
    const weapons = [...new Set(medals.map(m => m.weapon).filter(Boolean))].sort();
    const countries = [...new Set(medals.map(m => m.country).filter(Boolean))].sort();
    const lookup = {};
    medals.forEach(m => { lookup[`${m.country}::${m.weapon}`] = m; });

    // Find max total for heat intensity
    const maxTotal = Math.max(...medals.map(m => Number(m.total) || 0), 1);

    function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function intensity(total) { return Math.min(0.9, (Number(total) || 0) / maxTotal); }

    const headerCells = `<th>Country</th>${weapons.map(w => `<th>${escHtml(w)}</th>`).join('')}`;
    const bodyRows = countries.map(country => {
      const cells = weapons.map(weapon => {
        const m = lookup[`${country}::${weapon}`];
        if (!m) return `<td class="heatmap-cell heatmap-cell--empty">—</td>`;
        const alpha = intensity(m.total);
        return `<td class="heatmap-cell" style="background:rgba(250,204,21,${alpha})" title="${escHtml(country)} ${escHtml(weapon)}: ${m.gold}🥇 ${m.silver}🥈 ${m.bronze}🥉">
          <span class="heatmap-total">${escHtml(String(m.total))}</span>
        </td>`;
      }).join('');
      return `<tr><td class="heatmap-country"><a href="/countries/?country=${encodeURIComponent(country)}">${escHtml(country)}</a></td>${cells}</tr>`;
    }).join('');

    container.innerHTML = `
      <h2 class="ts-section-title">Medal Heatmap</h2>
      <div class="heatmap-scroll">
        <table class="heatmap-table">
          <thead><tr>${headerCells}</tr></thead>
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    `;
  }

  Call loadMedalHeatmap() from the existing init block in countries/main.js (append the call only).

  Task C: FederationOverview — extend countries/ page

  In countries/main.js, add a function loadFederationOverview(countryCode) if it doesn't exist:

  async function loadFederationOverview(countryCode) {
    const container = document.getElementById('fs-federation-overview');
    if (!container || !countryCode || typeof window.supabaseGet !== 'function') return;

    const [fedRows, topFencers, medals] = await Promise.all([
      window.supabaseGet('fs_national_fed_rankings', `country=eq.${encodeURIComponent(countryCode)}&limit=1`),
      window.supabaseGet('fs_public_fencers', `country=eq.${encodeURIComponent(countryCode)}&world_rank=gte.1&order=world_rank.asc&limit=5&select=id,name,weapon,world_rank`),
      window.supabaseGet('fs_medal_tables', `country=eq.${encodeURIComponent(countryCode)}&order=total.desc`)
    ]).catch(() => [[], [], []]);

    const fed = fedRows && fedRows[0];
    function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    container.innerHTML = `
      <div class="fed-overview">
        <div class="fed-stats">
          ${fed ? `<div class="fed-stat"><span class="fed-stat-value">${escHtml(String(fed.fencer_count || '—'))}</span><span class="fed-stat-label">Fencers</span></div>` : ''}
          ${fed ? `<div class="fed-stat"><span class="fed-stat-value">#${escHtml(String(fed.team_rank || '—'))}</span><span class="fed-stat-label">Team rank</span></div>` : ''}
        </div>
        ${topFencers && topFencers.length ? `
          <div class="fed-top-fencers">
            <h3>Top Fencers</h3>
            <ul>${topFencers.map(f => `<li><a href="/athlete/?id=${encodeURIComponent(f.id)}">#${escHtml(String(f.world_rank))} ${escHtml(f.name)}</a> · ${escHtml(f.weapon)}</li>`).join('')}</ul>
          </div>` : ''}
        ${medals && medals.length ? `
          <div class="fed-medals">
            <h3>Medals by Weapon</h3>
            <ul>${medals.map(m => `<li>${escHtml(m.weapon)}: ${m.gold}🥇 ${m.silver}🥈 ${m.bronze}🥉</li>`).join('')}</ul>
          </div>` : ''}
      </div>
    `;
  }

  In countries/index.html, add <div id="fs-federation-overview"></div> near the top
  of the country detail section (or at a logical position, without moving existing elements).

  If countries/ already handles a ?country=XX URL param, call loadFederationOverview(countryCode)
  from the existing handler (append only).
  If not, add URL param detection:
  const countryParam = new URLSearchParams(window.location.search).get('country');
  if (countryParam) loadFederationOverview(countryParam);
  
  Rules

  - Read all existing files fully before any edit
  - Add only — never remove or overwrite existing functions or HTML
  - If any function already exists, skip it entirely
  - Pure vanilla JS, IIFE or extend existing IIFE
  - window.supabaseGet guarded by typeof check
  - escapeHtml all external data before innerHTML
  - SVG sparklines only — no canvas, no chart libraries

  ---

  ## Agent 8 — Extend Explorer Pages + Navigation Audit + Final Verification

  You are the final agent in the FenceSpace frontend migration.
  Your job:
  1. Extend the search/, results/, and rankings/ pages with data explorer features
  2. Audit and fix navigation across all pages
  3. Verify the migration is complete
  
  Add only — never remove or overwrite existing functionality.

  Repos

  REAL FRONTEND: ~/Documents/FenceSpace-Fntend/fencespace/

  Step 1: Read everything before touching anything

  Read ALL of these:
  - ~/Documents/FenceSpace-Fntend/fencespace/search/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/search/main.js
  - ~/Documents/FenceSpace-Fntend/fencespace/search/style.css
  - ~/Documents/FenceSpace-Fntend/fencespace/results/index.html
  - ~/Documents/FenceSpace-Fntend/fencespace/results/main.js
  - ~/Documents/FenceSpace-Fntend/fencespace/rankings/index.html
  - (any rankings/main.js if it exists — check with ls)
  - ~/Documents/FenceSpace-Fntend/fencespace/main.js (first 200 lines)
  - ~/Documents/FenceSpace-Fntend/fencespace/tasks/_nav-template.html
  - ~/Documents/FenceSpace-Fntend/fencespace/tasks/migration-inventory.md (from Agent 1)
  - ~/Documents/FenceSpace-Fntend/fencespace/index.html (nav structure)

  Map what each page already does. Only add missing features.

  Task A: Extend Fencer Search (search/ page)

  The scraper's /fencers page had:
  - Filter bar: weapon, gender (M/F), category, country dropdown
  - Sortable columns: world_rank (default asc), name, fie_points
  - 25 per page, offset-based load more
  - Each row links to /athlete/?id={id}
  - Columns: name, country, weapon, category, world_rank, fie_points
  
  Read search/main.js. For each feature above that is missing, add it.

  Add to search/main.js (inside or alongside existing IIFE):

  function buildFencerQuery(weapon, gender, category, nameSearch, sortBy, sortDir, offset) {
    const parts = [];
    if (weapon && weapon !== 'all') parts.push(`weapon=ilike.*${encodeURIComponent(weapon)}*`);
    if (gender && gender !== 'all') parts.push(`gender=eq.${encodeURIComponent(gender)}`);
    if (category && category !== 'all') parts.push(`category=eq.${encodeURIComponent(category)}`);
    if (nameSearch) parts.push(`name=ilike.*${encodeURIComponent(nameSearch)}*`);
    parts.push(`order=${sortBy || 'world_rank'}.${sortDir || 'asc'}`);
    parts.push(`limit=25&offset=${offset || 0}&select=*`);
    return parts.join('&');
  }

  If a fencer table is already rendered, check if it has all columns and filters.
  Add any missing columns to the row template (append to existing template, not replace).
  Add any missing filter controls to search/index.html (append to existing filter section).

  Task B: Extend Tournament Results (results/ page)

  The scraper's /tournaments page had:
  - Filter bar: weapon, category, level, year
  - Sort by: date (default desc), name, level
  - Each row: name (linked to /tournament/?id=X), date, location, weapon, category, level, participant_count
  - Pagination: 24 per page, load more

  Read results/main.js. Add what's missing:

  function buildTournamentQuery(weapon, category, level, year, nameSearch, sortBy, sortDir, offset) {
    const parts = [];
    if (weapon && weapon !== 'all') parts.push(`weapon=ilike.*${encodeURIComponent(weapon)}*`);
    if (category && category !== 'all') parts.push(`category=eq.${encodeURIComponent(category)}`);
    if (level && level !== 'all') parts.push(`level=eq.${encodeURIComponent(level)}`);
    if (year && year !== 'all') parts.push(`date=gte.${year}-01-01&date=lte.${year}-12-31`);
    if (nameSearch) parts.push(`name=ilike.*${encodeURIComponent(nameSearch)}*`);
    parts.push(`order=${sortBy || 'date'}.${sortDir || 'desc'}`);
    parts.push(`limit=24&offset=${offset || 0}&select=*`);
    return parts.join('&');
  }

  Task C: Rankings page

  Check if rankings/main.js exists:
  ls ~/Documents/FenceSpace-Fntend/fencespace/rankings/
  
  If rankings/main.js does NOT exist, create it. If it does, extend it.

  Required features from scraper's /rankings page:
  1. Weapon × gender tabs: Foil-M, Foil-F, Épée-M, Épée-F, Sabre-M, Sabre-F
  2. Category selector: Senior (default), Junior, Cadet
  3. Rankings table: rank, name (linked to /athlete/?id=X), country, fie_points
  4. Load more: 50 per page default, load 50 more per click
  5. Query: window.supabaseGet('fs_public_fencers', buildRankingQuery(weapon, gender, category, offset))

  function buildRankingQuery(weapon, gender, category, offset) {
    const cat = category || 'Senior';
    const fullCategory = `${gender === 'F' ? "Women's" : "Men's"} ${cat}`;
    return [
      `weapon=ilike.*${encodeURIComponent(weapon)}*`,
      `or=(category.eq.${encodeURIComponent(fullCategory)},category.ilike.*${encodeURIComponent(cat)}*)`,
      'world_rank=gte.1',
      'order=world_rank.asc',
      `limit=50&offset=${offset || 0}`,
      'select=id,name,country,weapon,world_rank,fie_points,category'
    ].join('&');
  }

  If rankings/index.html has no tab buttons or table container, add them
  (append to existing HTML, do not remove existing content):
  <div class="rankings-tabs" id="rankings-tabs">
    <button class="btn-tab active" data-weapon="Sabre" data-gender="M">Men's Sabre</button>
    <button class="btn-tab" data-weapon="Sabre" data-gender="F">Women's Sabre</button>
    <button class="btn-tab" data-weapon="Foil" data-gender="M">Men's Foil</button>
    <button class="btn-tab" data-weapon="Foil" data-gender="F">Women's Foil</button>
    <button class="btn-tab" data-weapon="Epee" data-gender="M">Men's Épée</button>
    <button class="btn-tab" data-weapon="Epee" data-gender="F">Women's Épée</button>
  </div>
  <div class="rankings-category-row">
    <select id="rankings-category">
      <option value="Senior">Senior</option>
      <option value="Junior">Junior</option>
      <option value="Cadet">Cadet</option>
    </select>
  </div>
  <div id="rankings-table-wrap"></div>
  <button id="rankings-load-more" hidden>Load more</button>

  Task D: Navigation audit

  Read the nav in every page:

  Check these files for their nav HTML:
  - index.html, athlete/index.html, tournament/index.html, search/index.html,
  results/index.html, events/index.html, countries/index.html, clubs/index.html,
  rankings/index.html, salle/index.html, forum/index.html
  - tasks/_nav-template.html
  
  Expected nav links (all pages should have these in mobile menu at minimum):

  - Rankings → /rankings/
  - Results → /results/
  - Events → /events/
  - The Salle → /salle/
  - Clubs → /clubs/
  - Countries → /countries/
  - Quiz → /quiz/  (new — if Agent 6 created it)
  - News → /news/  (new — if Agent 6 created it)

  For each page that is MISSING any of these links in its mobile menu:
  Add the missing link only. Do not reorder, do not remove existing links.

  Update _nav-template.html:

  Add quiz and news links if missing. This is the reference template —
  keep it current so future pages can copy from it.

  Task E: Migration completeness check

  Read ~/Documents/FenceSpace-Fntend/fencespace/tasks/migration-inventory.md

  For each item:
  - Check if the corresponding real frontend file now contains the feature
  - Use grep to verify key function names or HTML IDs exist

  # Bracket visualizer
  grep -c "FsBracket\|normalizeBracket" ~/Documents/FenceSpace-Fntend/fencespace/bracket.js

  # H2H
  grep -c "h2h-stats\|fs_head_to_head" ~/Documents/FenceSpace-Fntend/fencespace/h2h.js

  # Career timeline
  ls ~/Documents/FenceSpace-Fntend/fencespace/athlete/timeline/index.html 2>&1

  # Fencer compare
  ls ~/Documents/FenceSpace-Fntend/fencespace/fencers/compare/index.html 2>&1

  # Quiz
  ls ~/Documents/FenceSpace-Fntend/fencespace/quiz/index.html 2>&1

  # Sparkline
  ls ~/Documents/FenceSpace-Fntend/fencespace/ranking-sparkline.js 2>&1

  # Medal heatmap
  grep -c "fs-medal-heatmap\|loadMedalHeatmap" ~/Documents/FenceSpace-Fntend/fencespace/countries/main.js

  # News
  ls ~/Documents/FenceSpace-Fntend/fencespace/news/index.html 2>&1

  # Scraper frontend gone
  ls ~/Documents/FenceSpace-Scraper/fencespace-scraper/frontend/ 2>&1

  Update migration-inventory.md: mark each item COMPLETE or PARTIAL with evidence.

  Task F: Final report

  Write a summary to ~/Documents/FenceSpace-Fntend/fencespace/tasks/migration-complete.md:

  - What was added (list by page)
  - What was extended (list by file)
  - Navigation links confirmed across all pages
  - Any items that remain PARTIAL and why
  - New script/CSS includes needed (list any  tags that must be in HTML)

  Rules

  - Read all existing files fully before any edit
  - Add only — never remove or overwrite existing code
  - Pure vanilla JS, IIFE pattern or extend existing IIFE
  - window.supabaseGet guarded by typeof check
  - escapeHtml on all external data before innerHTML
  - No framework, no build step required

