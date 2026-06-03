from pathlib import Path

import pytest


FIE_RULES_HTML = """
<html>
  <body>
    <h1>Rules</h1>
    <ul>
      <li><a href="https://static.fie.org/uploads/37/185366-technical%20rules%20ang.pdf">
        Technical rules December 2025
      </a></li>
      <li><a href="https://static.fie.org/uploads/37/185364-material%20rules%20ang.pdf">
        Material rules December 2025
      </a></li>
      <li><a href="/fie/documents/equipment">Equipment</a></li>
    </ul>
  </body>
</html>
"""


BRITISH_FENCING_CONGRESS_HTML = """
<html>
  <body>
    <article>
      <h1>2025 FIE CONGRESS - SUMMARY DECISIONS</h1>
      <p>
        Significant rules and statute changes affecting entry fees, passivity,
        safeguarding, women's category, clothing and coaching following 2025 FIE
        Congress held in Bahrain on 22nd November.
      </p>
      <p>Highlights from decisions taken at the 2025 Congress include:</p>
      <ul>
        <li>
          Passivity - Removal of P-yellow card. This means straight to P-red on
          first minute of passivity, followed by P-black as before.
          (Start season 2026-27, more information to follow).
        </li>
        <li>
          Minimum Clothing - t.20 - Clarification that breeches and long socks
          are always required for warm-up and training.
        </li>
        <li>
          Women's Category Definition - only people who are female sex at birth
          and have not started female to male hormone treatment will be eligible
          to compete in the women's category. Effective immediately.
        </li>
      </ul>
      <p>Note 2. All changes unless otherwise indicated come into effect 1st January, 2026.</p>
    </article>
  </body>
</html>
"""


USA_NONCOMBATIVITY_HTML = """
<html>
  <body>
    <h1>Updated Unwillingness to Fight (Non-Combativity) Rules Take Effect Jan. 1, 2023</h1>
    <p>
      The rule changes, enforced at all USA Fencing tournaments beginning Jan. 1,
      2023, affect how P-Cards are awarded for unwillingness to fight, also known
      as non-combativity.
    </p>
    <p>
      The update concerns Rule t.124 and applies only to Direct Elimination bouts
      in individual and team events, primarily seen in epee.
    </p>
  </body>
</html>
"""


FENCING_ARCHIVE_HTML = """
<html>
  <body>
    <h1>FIE</h1>
    <h2>FIE Congresses</h2>
    <ul>
      <li><a href="https://www.fencingarchive.com/wp-content/uploads/fie/congress-FIE-2017-Report_ang_final.pdf">
        congress-FIE-2017-Report_ang_final.pdf (7.3 Mb)
      </a></li>
    </ul>
    <h2>FIE Rule Books</h2>
    <ul>
      <li><a href="https://www.fencingarchive.com/wp-content/uploads/fie/FIE%202016%20NEW%20RULES%20FOR%20THE%20SABER.pdf">
        FIE 2016 NEW RULES FOR THE SABER.pdf (572.21 Kb)
      </a></li>
      <li><a href="https://www.fencingarchive.com/wp-content/uploads/fie/FIE%202019-02%20Explanatory%20Note%20for%20UTF%20t.124.pdf">
        FIE 2019-02 Explanatory Note for UTF t.124.pdf (209.82 Kb)
      </a></li>
    </ul>
    <h2>FIE Miscellaneous Documents</h2>
    <ul>
      <li><a href="https://www.fencingarchive.com/wp-content/uploads/fie/2018%20FIE%20CONGRESS%20SUMMARY%20OF%20DECISIONS.pdf">
        2018 FIE CONGRESS SUMMARY OF DECISIONS.pdf (423.97 Kb)
      </a></li>
    </ul>
  </body>
</html>
"""


MISSING_DATE_HTML = """
<html>
  <body>
    <h1>FIE Congress Notes</h1>
    <ul>
      <li>Refereeing - Clarification of point-in-line wording for foil.</li>
    </ul>
  </body>
</html>
"""


def test_migration_defines_source_cited_date_aware_rule_change_table():
    sql = Path("supabase/migrations/20260602_rule_changes.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS public.fs_rule_changes" in sql
    assert "rule_key text NOT NULL UNIQUE" in sql
    assert "effective_date date" in sql
    assert "effective_season text" in sql
    assert "weapons_affected text[]" in sql
    assert "categories_affected text[]" in sql
    assert "rule_area text NOT NULL" in sql
    assert "summary text NOT NULL" in sql
    assert "source_url text NOT NULL" in sql
    assert "source_type text NOT NULL" in sql
    assert "source_title text" in sql
    assert "evidence_quote text" in sql
    assert "affected_competition_ids uuid[]" in sql
    assert "affected_seasons text[]" in sql
    assert "impact_analysis_status text NOT NULL DEFAULT 'not_analyzed'" in sql
    assert "impact_summary text" in sql
    assert "metadata jsonb NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "CONSTRAINT fs_rule_changes_source_url_required" in sql
    assert "CONSTRAINT fs_rule_changes_effective_required" in sql
    assert "CONSTRAINT fs_rule_changes_no_untested_impact_claims" in sql
    assert "ALTER TABLE public.fs_rule_changes ENABLE ROW LEVEL SECURITY" in sql


def test_parse_fie_rulebook_listing_extracts_rulebook_source_documents():
    from scrape_rule_changes import parse_fie_rulebook_listing

    docs = parse_fie_rulebook_listing(FIE_RULES_HTML)

    assert docs == [
        {
            "title": "Technical rules December 2025",
            "source_url": "https://static.fie.org/uploads/37/185366-technical%20rules%20ang.pdf",
            "source_type": "fie_rulebook",
            "document_area": "technical",
            "published_label": "December 2025",
        },
        {
            "title": "Material rules December 2025",
            "source_url": "https://static.fie.org/uploads/37/185364-material%20rules%20ang.pdf",
            "source_type": "fie_rulebook",
            "document_area": "material",
            "published_label": "December 2025",
        },
    ]


def test_parse_changelog_extracts_dates_seasons_weapons_categories_and_citations():
    from scrape_rule_changes import parse_rule_change_changelog

    rows = parse_rule_change_changelog(
        BRITISH_FENCING_CONGRESS_HTML,
        source_url="https://www.britishfencing.com/2025-fie-congress-summary-decisions/",
        source_type="federation_summary",
        published_at="2025-11-25",
    )

    by_area = {row["rule_area"]: row for row in rows}
    passivity = by_area["passivity"]
    assert passivity["effective_date"] is None
    assert passivity["effective_season"] == "2026-2027"
    assert passivity["weapons_affected"] == ["epee", "foil", "sabre"]
    assert passivity["categories_affected"] == ["individual", "team"]
    assert passivity["source_url"] == "https://www.britishfencing.com/2025-fie-congress-summary-decisions/"
    assert passivity["source_type"] == "federation_summary"
    assert passivity["impact_analysis_status"] == "not_analyzed"
    assert passivity["impact_summary"] is None

    clothing = by_area["equipment"]
    assert clothing["effective_date"] == "2026-01-01"
    assert clothing["effective_season"] == "2025-2026"
    assert clothing["categories_affected"] == []
    assert "breeches and long socks" in clothing["evidence_quote"]

    category = by_area["eligibility"]
    assert category["effective_date"] == "2025-11-25"
    assert category["effective_season"] == "2025-2026"
    assert category["categories_affected"] == ["senior", "junior", "cadet", "veteran"]


def test_parse_summary_body_handles_effective_date_weapon_filters_and_event_scope():
    from scrape_rule_changes import parse_rule_change_changelog

    rows = parse_rule_change_changelog(
        USA_NONCOMBATIVITY_HTML,
        source_url="https://www.usafencing.org/news/2022/december/19/updated-unwillingness-to-fight-noncombativity-rules-take-effect-jan-1-2023",
        source_type="federation_summary",
        published_at="2022-12-19",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["rule_area"] == "passivity"
    assert row["effective_date"] == "2023-01-01"
    assert row["effective_season"] == "2022-2023"
    assert row["weapons_affected"] == ["epee"]
    assert row["categories_affected"] == ["individual", "team"]
    assert row["affected_seasons"] == ["2022-2023"]
    assert row["metadata"]["event_scope"] == "direct_elimination"


def test_parse_fencing_archive_extracts_historical_documents_by_section():
    from scrape_rule_changes import parse_fencing_archive_documents

    docs = parse_fencing_archive_documents(FENCING_ARCHIVE_HTML)

    assert docs == [
        {
            "title": "congress-FIE-2017-Report_ang_final.pdf",
            "source_url": "https://www.fencingarchive.com/wp-content/uploads/fie/congress-FIE-2017-Report_ang_final.pdf",
            "source_type": "historical_archive",
            "document_area": "congress",
            "published_label": "2017",
        },
        {
            "title": "FIE 2016 NEW RULES FOR THE SABER.pdf",
            "source_url": "https://www.fencingarchive.com/wp-content/uploads/fie/FIE%202016%20NEW%20RULES%20FOR%20THE%20SABER.pdf",
            "source_type": "historical_archive",
            "document_area": "rulebook",
            "published_label": "2016",
        },
        {
            "title": "FIE 2019-02 Explanatory Note for UTF t.124.pdf",
            "source_url": "https://www.fencingarchive.com/wp-content/uploads/fie/FIE%202019-02%20Explanatory%20Note%20for%20UTF%20t.124.pdf",
            "source_type": "historical_archive",
            "document_area": "rulebook",
            "published_label": "2019-02",
        },
        {
            "title": "2018 FIE CONGRESS SUMMARY OF DECISIONS.pdf",
            "source_url": "https://www.fencingarchive.com/wp-content/uploads/fie/2018%20FIE%20CONGRESS%20SUMMARY%20OF%20DECISIONS.pdf",
            "source_type": "historical_archive",
            "document_area": "congress_decision",
            "published_label": "2018",
        },
    ]


def test_missing_date_candidates_are_flagged_and_filtered_before_storage():
    from scrape_rule_changes import parse_rule_change_changelog, valid_rule_change_rows

    candidates = parse_rule_change_changelog(
        MISSING_DATE_HTML,
        source_url="https://example.test/fie-congress-notes",
        source_type="fie_congress_decision",
    )
    rows, skipped = valid_rule_change_rows(candidates)

    assert len(candidates) == 1
    assert candidates[0]["metadata"]["date_status"] == "missing"
    assert rows == []
    assert skipped == 1


def test_manual_seed_fixture_supports_older_cited_rule_changes():
    from scrape_rule_changes import load_manual_seed_fixtures

    seeds = [
        {
            "summary": "Sabre lockout timing changed from 120ms to 170ms after the 2016 Olympics.",
            "effective_season": "2016-2017",
            "weapons_affected": ["sabre"],
            "categories_affected": ["senior", "junior"],
            "rule_area": "timing",
            "source_url": "https://fencing.net/15522/2015-fie-congress-summary/",
            "source_type": "historical_archive",
            "evidence_quote": "Blocking time on sabre goes from 120 to 170 milliseconds. Starts after Rio Olympics.",
        }
    ]

    rows = load_manual_seed_fixtures(seeds)

    assert len(rows) == 1
    assert rows[0]["rule_key"]
    assert rows[0]["effective_date"] is None
    assert rows[0]["effective_season"] == "2016-2017"
    assert rows[0]["weapons_affected"] == ["sabre"]
    assert rows[0]["metadata"]["manual_seed"] is True


def test_build_rule_change_row_requires_citation_effective_date_and_tested_impact_claims():
    from scrape_rule_changes import build_rule_change_row

    with pytest.raises(ValueError, match="source_url"):
        build_rule_change_row(
            summary="Missing source URL",
            effective_date="2026-01-01",
            rule_area="equipment",
            source_url="",
            source_type="federation_summary",
        )

    with pytest.raises(ValueError, match="effective_date or effective_season"):
        build_rule_change_row(
            summary="Missing date",
            rule_area="equipment",
            source_url="https://example.test/source",
            source_type="federation_summary",
        )

    with pytest.raises(ValueError, match="impact_summary"):
        build_rule_change_row(
            summary="Untested impact claim",
            effective_date="2026-01-01",
            rule_area="passivity",
            source_url="https://example.test/source",
            source_type="federation_summary",
            impact_summary="This increased comeback rates.",
        )

    row = build_rule_change_row(
        summary="Tested aggregate analysis with caveats.",
        effective_date="2026-01-01",
        rule_area="passivity",
        source_url="https://example.test/source",
        source_type="federation_summary",
        impact_summary="Aggregate test found a directional change with caveats.",
        impact_analysis_status="tested_with_caveats",
        metadata={"analysis_query": "tests/example.sql"},
    )
    assert row["impact_analysis_status"] == "tested_with_caveats"
    assert row["impact_summary"].startswith("Aggregate test")


def test_upsert_rule_changes_dedupes_by_rule_key_before_writing():
    from scrape_rule_changes import build_rule_change_row, upsert_rule_changes

    client = FakeSupabaseClient()
    first = build_rule_change_row(
        summary="Passivity update",
        effective_date="2023-01-01",
        rule_area="passivity",
        source_url="https://example.test/a",
        source_type="federation_summary",
    )
    updated = {**first, "summary": "Passivity update revised"}
    second = build_rule_change_row(
        summary="Equipment update",
        effective_date="2026-01-01",
        rule_area="equipment",
        source_url="https://example.test/b",
        source_type="federation_summary",
    )

    written = upsert_rule_changes(client, [first, updated, second], batch_size=10)

    assert written == 2
    assert client.tables["fs_rule_changes"].upserts == [
        ([updated, second], "rule_key")
    ]


class FakeSupabaseClient:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        table = self.tables.setdefault(name, FakeTable())
        return table


class FakeTable:
    def __init__(self):
        self.upserts = []
        self._rows = None
        self._on_conflict = None

    def upsert(self, rows, on_conflict):
        self._rows = rows
        self._on_conflict = on_conflict
        return self

    def execute(self):
        self.upserts.append((self._rows, self._on_conflict))
        return FakeResult(self._rows)


class FakeResult:
    def __init__(self, data):
        self.data = data
