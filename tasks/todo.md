# Mypy Untyped Definitions Cleanup

## Plan

- [x] Read `tasks/lessons.md` and existing `tasks/todo.md`.
- [x] Enable `check_untyped_defs = true` in `pyproject.toml`.
- [x] Capture `/tmp/mypy_untyped_baseline.txt` before fixing errors.
- [x] Fix test-file errors in batches, preserving test assertions.
- [x] Fix scraper/source-file errors in batches with specific ignores only where appropriate.
- [x] Run final mypy verification.
- [x] Run final pytest verification.
- [x] Record final review: files changed, behavior changed, verification, remaining risks.

## Notes

- Do not change runtime behavior beyond safe `None` guards and annotations.
- Do not use bare `# type: ignore`.
- Do not push or commit.

## Refactor Follow-Up Plan

- [x] Remove noisy dynamic-data suppressions from scraper files with 5+ new ignores.
- [x] Re-run mypy after the scraper refactor.
- [x] Re-run pytest after the scraper refactor.
- [x] Produce a layman's changelog covering all changed/fixed/added work.

## Final Review

### Files Changed

- `pyproject.toml`
- 25 source Python files
- 102 test Python files
- `tasks/todo.md`
- `tasks/layman_changelog.md`

### Behavior Changed

- Enabled `check_untyped_defs = true`.
- Added type annotations, no-op casts, and real `None` narrowing in tests/source.
- Refactored the highest-noise scraper files so this work now adds no `# type: ignore` suppressions.

### Verification

- `.venv/bin/python -m mypy . --ignore-missing-imports 2>&1 | tail -3`
  - `Success: no issues found in 493 source files`
- `.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5`
  - `1964 passed, 1 skipped, 1 warning in 27.39s`

### Remaining Risks

- Existing older project `# type: ignore` comments remain outside this mypy cleanup.
- No file now has 5+ new suppressions from this work.

## Refactor Follow-Up Review

### Files Changed

- Refactored `scrape_cac_games.py`, `scrape_olympics.py`, `scrape_south_american_games.py`, `scrape_youth_majors.py`, `scrape_continental_games.py`, `scrape_masters_games.py`, `scrape_paralympics.py`, and `scrape_youth_olympics.py` to remove the noisy dynamic-data suppressions.
- Added `tasks/layman_changelog.md`.

### Behavior Changed

- Added safe database-client helpers and regex guards in the highest-noise scraper files.
- Added clearer list/dict annotations for scraper manifests and parsed result rows.
- Did not change scraper outputs, test assertions, commits, pushes, or deployments.

### Verification

- `.venv/bin/python -m mypy . --ignore-missing-imports 2>&1 | tail -3`
  - `Success: no issues found in 493 source files`
- `.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5`
  - `1964 passed, 1 skipped, 1 warning in 27.39s`

### Remaining Risks

- Existing older project `# type: ignore` comments remain outside this pass.
