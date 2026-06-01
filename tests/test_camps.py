from pathlib import Path


HOOKED_ON_FENCING_HTML = """
<html>
  <body>
    <h1>Summer Camp</h1>
    <h3>Pre-Nationals Epee Camp</h3>
    <h4>June 15th - 19th, 2026</h4>
    <p>This camp is intended for competitive epee fencers aged 13 and up,
    and will be held at our facility in North Royalton, Ohio. The camp will
    take place from June 15 - June 19, 2026.</p>
    <p>The camp will focus on footwork and fitness, technique, tactics,
    sport psychology and plenty of fencing.</p>
    <p>Led by Coach Alex Smith and Coach Jamie Lee.</p>
    <p>The cost of the camp is $250 or $60 per day.</p>
    <p>Pre-Nationals Epee Camp, June 15th - 19th, 2026</p>
  </body>
</html>
"""


EFC_BASEL_PDF_TEXT = """
International Fencing Camp Basel 2026

As preparation for the season 2026/2027 we offer a training camp for
experienced U17, U20 and U23 Epee Fencers in Basel taking place
July 26 - August 01, 2026.

Host: Basler Fechtgarde in cooperation with Fechtgesellschaft Basel
Venue: Theaterstrasse 12, 4051 Basel, Switzerland
Costs: Until 31.01.2026 CHF 549
Contact: Philipp Pleier, Head coach Basler Fechtgarde
"""


CAPITAL_FENCING_HTML = """
<html>
  <body>
    <h2>FENCING CAMPS</h2>
    <p>Memorial Weekend Camp 2026:</p>
    <p>Saturday, 5/23 - Monday, 5/25</p>
    <p>3 full days of bouting, games, drills, footwork, strength &
    conditioning, and mental training.</p>
    <p>$350 per person for members. $400 for non-members.</p>
    <p>Led by world-renowned coaches Dariusz Gilman, Medhat El-Bakry,
    and Mostafa Ayman Zedan.</p>
  </body>
</html>
"""


GENERIC_CAMP_DATES_HTML = """
<html>
  <head><title>Camps at Example Fencing</title></head>
  <body>
    <h2>Camp Dates</h2>
    <p>June 22nd - 25th, 2026</p>
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

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            }
        )
        return FakeResult([])


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_club_html_extracts_camp_fields():
    from scrape_training_camps import CampSource, parse_camps_from_html

    source = CampSource(
        url="https://www.hookedonfencing.org/camp",
        organizer="Hooked on Fencing",
        city="North Royalton",
        country="USA",
        source_kind="club",
    )

    camps = parse_camps_from_html(HOOKED_ON_FENCING_HTML, source)

    assert len(camps) == 1
    camp = camps[0]
    assert camp["name"] == "Pre-Nationals Epee Camp"
    assert camp["organizer"] == "Hooked on Fencing"
    assert camp["city"] == "North Royalton"
    assert camp["country"] == "USA"
    assert camp["start_date"] == "2026-06-15"
    assert camp["end_date"] == "2026-06-19"
    assert camp["weapons_covered"] == ["epee"]
    assert camp["cost"] == 250
    assert camp["currency"] == "USD"
    assert camp["coaches"] == ["Alex Smith", "Jamie Lee"]
    assert camp["source_url"] == "https://www.hookedonfencing.org/camp"
    assert camp["metadata"]["source_kind"] == "club"


def test_parse_pdf_text_extracts_federation_camp_fields():
    from scrape_training_camps import CampSource, parse_camps_from_text

    source = CampSource(
        url="https://www.eurofencing.info/getFile/case%3Ashow/id%3A497082",
        organizer="European Fencing Confederation",
        source_kind="federation_pdf",
    )

    camps = parse_camps_from_text(EFC_BASEL_PDF_TEXT, source)

    assert len(camps) == 1
    camp = camps[0]
    assert camp["name"] == "International Fencing Camp Basel 2026"
    assert camp["organizer"] == "Basler Fechtgarde"
    assert camp["city"] == "Basel"
    assert camp["country"] == "Switzerland"
    assert camp["start_date"] == "2026-07-26"
    assert camp["end_date"] == "2026-08-01"
    assert camp["weapons_covered"] == ["epee"]
    assert camp["cost"] == 549
    assert camp["currency"] == "CHF"
    assert camp["metadata"]["source_kind"] == "federation_pdf"


def test_parse_html_uses_inline_camp_names_before_page_title_fallback():
    from scrape_training_camps import CampSource, parse_camps_from_html

    source = CampSource(
        url="https://www.capfencing.com/camps",
        organizer="Capital Fencing Academy",
        city="North Jersey",
        country="USA",
        source_kind="club",
    )

    camps = parse_camps_from_html(CAPITAL_FENCING_HTML, source)

    assert len(camps) == 1
    camp = camps[0]
    assert camp["name"] == "Memorial Weekend Camp 2026"
    assert camp["start_date"] == "2026-05-23"
    assert camp["end_date"] == "2026-05-25"
    assert camp["city"] == "North Jersey"
    assert camp["country"] == "USA"
    assert camp["cost"] == 350


def test_date_parser_ignores_state_abbreviations_and_uses_prior_year():
    from scrape_training_camps import parse_date_range

    text = (
        "Address: Durham, NC 27707. 2026 Pre-Season Camp: "
        "Aug 3 - Aug 7 with competitive bouting."
    )

    assert parse_date_range(text) == ("2026-08-03", "2026-08-07")


def test_parse_html_skips_generic_camp_date_labels():
    from scrape_training_camps import CampSource, parse_camps_from_html

    source = CampSource(
        url="https://example.test/camps",
        organizer="Example Fencing",
        country="USA",
        source_kind="club",
    )

    assert parse_camps_from_html(GENERIC_CAMP_DATES_HTML, source) == []


def test_dedupe_camps_merges_duplicate_source_urls():
    from scrape_training_camps import dedupe_camps

    duplicate_a = {
        "name": "Pre-Nationals Epee Camp",
        "organizer": "Hooked on Fencing",
        "start_date": "2026-06-15",
        "end_date": "2026-06-19",
        "source_url": "https://example.test/a",
        "metadata": {"source_kind": "club"},
    }
    duplicate_b = {
        **duplicate_a,
        "source_url": "https://example.test/b",
        "metadata": {"source_kind": "aggregator"},
    }
    different_dates = {
        **duplicate_a,
        "start_date": "2026-08-03",
        "end_date": "2026-08-07",
        "source_url": "https://example.test/c",
    }

    camps = dedupe_camps([duplicate_a, duplicate_b, different_dates])

    assert len(camps) == 2
    merged = camps[0]
    assert merged["source_url"] == "https://example.test/a"
    assert merged["metadata"]["duplicate_source_urls"] == ["https://example.test/b"]


def test_scrape_training_camps_upserts_deduped_rows():
    from scrape_training_camps import CampSource, FetchedContent, scrape_training_camps

    sources = [
        CampSource(
            url="https://www.hookedonfencing.org/camp",
            organizer="Hooked on Fencing",
            city="North Royalton",
            country="USA",
            source_kind="club",
        ),
        CampSource(
            url="https://www.hookedonfencing.org/camp?mirror=1",
            organizer="Hooked on Fencing",
            city="North Royalton",
            country="USA",
            source_kind="aggregator",
        ),
        CampSource(
            url="https://www.eurofencing.info/getFile/case%3Ashow/id%3A497082",
            organizer="European Fencing Confederation",
            source_kind="federation_pdf",
        ),
    ]

    def fetcher(source):
        if "eurofencing" in source.url:
            return FetchedContent(
                content=EFC_BASEL_PDF_TEXT.encode("utf-8"),
                content_type="text/plain",
                final_url=source.url,
            )
        return FetchedContent(
            content=HOOKED_ON_FENCING_HTML.encode("utf-8"),
            content_type="text/html",
            final_url=source.url,
        )

    client = FakeSupabase()

    summary = scrape_training_camps(
        client=client,
        sources=sources,
        fetcher=fetcher,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "sources": 3,
        "parsed": 3,
        "written": 2,
        "failed": 0,
        "skipped": 0,
    }
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_training_camps"
    assert upsert["on_conflict"] == "name,organizer,start_date,end_date"
    assert {row["name"] for row in upsert["rows"]} == {
        "Pre-Nationals Epee Camp",
        "International Fencing Camp Basel 2026",
    }


def test_camps_migration_defines_table_and_dedupe_constraint():
    migration = Path("supabase/migrations/20260601_camps.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_training_camps" in normalized
    assert "name text not null" in normalized
    assert "coaches text[]" in normalized
    assert "weapons_covered text[]" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "unique (name, organizer, start_date, end_date)" in normalized
    assert "create index if not exists idx_fs_training_camps_dates" in normalized
