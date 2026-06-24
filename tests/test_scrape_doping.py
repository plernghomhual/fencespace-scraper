from pathlib import Path
from typing import Any

FIE_SANCTIONS_PDF_TEXT = """
SANCTIONS (1. Black cards, 2. Communicated by NFs, 3. FIE Disciplinary Panel, 4. ADVRs)
1. Black cards
Name Nationality Competition Offence Sanction Start Date End date
Daniel Jerent SUI Men's Epee World Cup (Fujairah, UAE), 10.01.2026 t.109 Black card 10.01.2026 10.03.2026
4. ADVRs (Anti-doping Rules Violations)
Name Nationality
Ms Anna Kun (HUN)
Decision of the FIE Doping Disciplinary Tribunal of 10 May 2024
Art. 2.4 FIE ADR (three missed tests within a twelve-month period)
Sanctions:
-Period of Ineligibility of two years from 10 May 2024 until 9 May 2026;
-Disqualification of all of Ms Kun's results earned from the date of the third missed test (i.e. 24 August 2023) through the commencement
 of the period of Ineligibility (i.e. 10 May 2024) including forfeiture of any medals, points and prizes;
-A fine of CHF 5'000.- is imposed on Ms Kun.
"""


ITA_POTENTIAL_ADRV_TEXT = """
5 April 2024
The ITA has notified fencer Anna Kun (Hungary) of a potential anti-doping rule violation
The International Testing Agency (ITA), leading an independent anti-doping program for the Federation Internationale d'Escrime (FIE), confirms that it has notified Hungarian fencer Anna Kun of a potential Anti-Doping Rule Violation for a combination of three Whereabouts Failures within a twelve-month period.
The case will be referred to the FIE Doping Disciplinary Tribunal in charge of hearings and adjudication of anti-doping matters.
Pursuant to the FIE ADR and World Anti-Doping Code, Anna Kun is not subject to a mandatory provisional suspension pending the resolution of the matter.
"""


CLEARED_CASE_TEXT = """
The FIE Doping Disciplinary Tribunal found that Example Fencer did not commit an Anti-Doping Rule Violation.
The provisional suspension is lifted and the case is dismissed with no period of ineligibility.
"""


APPEAL_CASE_TEXT = """
The Athlete has appealed the first instance decision to the Court of Arbitration for Sport.
The period of ineligibility is stayed pending appeal and the case is not final.
"""


FIE_CLEAN_SPORT_STUB_HTML = """
<html>
  <body>
    <h1>Clean Sport</h1>
    <p>A full list of sanctioned Fencers and Fencer Support Personnel in the sport of Fencing can be found below.</p>
    <h2>Table of Sanctions</h2>
    <p>International Fencing Federation to complete table if applicable.</p>
  </body>
</html>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None
        self.filters = []
        self._limit = None

    def select(self, _columns):
        return self

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def execute(self):
        if self.rows is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])

        rows = list(self.client.table_rows.get(self.name, []))
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif op == "ilike":
                rows = [row for row in rows if row.get(column, "").lower() == value.lower()]
        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, table_rows=None):
        self.table_rows = table_rows or {}
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_doping_migration_defines_public_record_table_shape():
    migration = Path("supabase/migrations/20260602_doping.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_anti_doping_records" in normalized
    assert "fencer_id uuid" in normalized
    assert "athlete_name text not null" in normalized
    assert "athlete_country text" in normalized
    assert "record_date date" in normalized
    assert "record_type text not null" in normalized
    assert "test_type text" in normalized
    assert "sanction text" in normalized
    assert "authority text not null" in normalized
    assert "source_url text not null" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "unique (source_url, athlete_name, record_type, record_date)" in normalized
    assert "enable row level security" in normalized


def test_parse_fie_sanctions_pdf_extracts_only_public_adrv_record():
    from scrape_doping import parse_fie_sanctions_pdf_text

    rows = parse_fie_sanctions_pdf_text(
        FIE_SANCTIONS_PDF_TEXT,
        source_url="https://static.fie.org/uploads/39/196318-SANCTIONS.pdf",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["athlete_name"] == "Anna Kun"
    assert row["athlete_country"] == "HUN"
    assert row["record_date"] == "2024-05-10"
    assert row["record_type"] == "sanction"
    assert row["case_status"] == "resolved"
    assert row["test_type"] == "whereabouts_failures"
    assert row["authority"] == "FIE Doping Disciplinary Tribunal"
    assert row["source_url"] == "https://static.fie.org/uploads/39/196318-SANCTIONS.pdf"
    assert "Period of Ineligibility of two years" in row["sanction"]
    assert "Black card" not in row["sanction"]
    assert row["metadata"]["source_kind"] == "fie_sanctions_pdf"
    assert row["metadata"]["rule_violation"].startswith("Art. 2.4 FIE ADR")


def test_parse_ita_news_classifies_potential_case_without_sanction():
    from scrape_doping import parse_ita_news_article_text

    row = parse_ita_news_article_text(
        ITA_POTENTIAL_ADRV_TEXT,
        source_url="https://ita.sport/news/the-ita-has-notified-fencer-anna-kun-hungary-of-a-potential-anti-doping-rule-violation/",
    )

    assert row["athlete_name"] == "Anna Kun"
    assert row["athlete_country"] == "HUN"
    assert row["record_date"] == "2024-04-05"
    assert row["record_type"] == "potential_adrv"
    assert row["case_status"] == "under_review"
    assert row["test_type"] == "whereabouts_failures"
    assert row["sanction"] is None
    assert row["metadata"]["legal_note"] == "potential_adrv_not_a_sanction"


def test_classify_cleared_and_appeal_cases_are_not_sanctions():
    from scrape_doping import build_official_case_record

    cleared = build_official_case_record(
        athlete_name="Example Fencer",
        athlete_country="USA",
        record_date="2026-01-20",
        text=CLEARED_CASE_TEXT,
        authority="FIE Doping Disciplinary Tribunal",
        source_url="https://example.test/cleared-official-case",
    )
    appeal = build_official_case_record(
        athlete_name="Appeal Fencer",
        athlete_country="FRA",
        record_date="2026-02-15",
        text=APPEAL_CASE_TEXT,
        authority="Court of Arbitration for Sport",
        source_url="https://example.test/appeal-official-case",
    )

    assert cleared["record_type"] == "cleared_case"
    assert cleared["case_status"] == "cleared"
    assert cleared["sanction"] is None
    assert appeal["record_type"] == "appeal"
    assert appeal["case_status"] == "appeal_pending"
    assert appeal["sanction"] is None


def test_match_fencer_requires_strong_evidence_and_logs_ambiguous_names(capsys):
    from scrape_doping import attach_fencer_match

    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": "fencer-a", "name": "Anna Kun", "country": "HUN", "date_of_birth": "1995-01-01"},
                {"id": "fencer-b", "name": "Anna Kun", "country": "HUN", "date_of_birth": "1997-01-01"},
            ]
        }
    )
    row = {
        "athlete_name": "Anna Kun",
        "athlete_country": "HUN",
        "metadata": {},
    }

    matched = attach_fencer_match(client, row)

    assert matched["fencer_id"] is None
    assert matched["metadata"]["match_status"] == "ambiguous"
    assert matched["metadata"]["match_method"] == "name_country"
    assert matched["metadata"]["match_candidates"] == ["fencer-a", "fencer-b"]
    assert "ambiguous anti-doping fencer match" in capsys.readouterr().out


def test_match_fencer_uses_name_country_date_when_unique():
    from scrape_doping import attach_fencer_match

    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": "fencer-a", "name": "Anna Kun", "country": "HUN", "date_of_birth": "1995-01-01"},
                {"id": "fencer-b", "name": "Anna Kun", "country": "HUN", "date_of_birth": "1997-01-01"},
            ]
        }
    )
    row = {
        "athlete_name": "Anna Kun",
        "athlete_country": "HUN",
        "metadata": {"athlete_date_of_birth": "1997-01-01"},
    }

    matched = attach_fencer_match(client, row)

    assert matched["fencer_id"] == "fencer-b"
    assert matched["metadata"]["match_status"] == "matched"
    assert matched["metadata"]["match_method"] == "name_country_date"


def test_parse_clean_sport_stub_returns_no_public_records():
    from scrape_doping import DopingSource, FetchedContent, parse_fetched_content

    source = DopingSource(
        url="https://fie.org/fie/documents/clean-sport/11",
        source_kind="fie_clean_sport",
        authority="FIE",
    )
    fetched = FetchedContent(
        content=FIE_CLEAN_SPORT_STUB_HTML.encode("utf-8"),
        content_type="text/html",
        final_url=source.url,
    )

    assert parse_fetched_content(source, fetched) == []


def test_scrape_doping_upserts_public_records_and_rate_limits_sources():
    from scrape_doping import DopingSource, FetchedContent, scrape_doping

    sources = [
        DopingSource(
            url="https://static.fie.org/uploads/39/196318-SANCTIONS.pdf",
            source_kind="fie_sanctions_pdf",
            authority="FIE",
        ),
        DopingSource(
            url="https://fie.org/fie/documents/clean-sport/11",
            source_kind="fie_clean_sport",
            authority="FIE",
        ),
    ]

    def fetcher(source):
        if source.source_kind == "fie_sanctions_pdf":
            return FetchedContent(
                content=FIE_SANCTIONS_PDF_TEXT.encode("utf-8"),
                content_type="text/plain",
                final_url=source.url,
            )
        return FetchedContent(
            content=FIE_CLEAN_SPORT_STUB_HTML.encode("utf-8"),
            content_type="text/html",
            final_url=source.url,
        )

    sleeps: list[Any] = []
    client = FakeSupabase()

    summary = scrape_doping(
        client=client,
        sources=sources,
        fetcher=fetcher,
        sleeper=sleeps.append,
        rate_limit_seconds=0.25,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "sources": 2,
        "parsed": 1,
        "written": 1,
        "failed": 0,
        "skipped": 1,
        "ambiguous": 0,
    }
    assert sleeps == [0.25]
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_anti_doping_records"
    assert upsert["on_conflict"] == "source_url,athlete_name,record_type,record_date"
    assert upsert["rows"][0]["athlete_name"] == "Anna Kun"
