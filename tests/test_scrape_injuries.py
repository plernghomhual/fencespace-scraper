import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"


FIE_ATHLETE_PROFILE_HTML = """
<html>
  <body>
    <h1>JERENT Daniel</h1>
    <h2>General Interest</h2>
    <p>Nicknames Dany (escrime-ffe.fr, 23 Feb 2014)</p>
    <p>Injuries He was unable to compete at the 2022 Challenge Monal event in Paris, France, due to a foot injury. (la1ere.francetvinfo.fr, 18 Apr 2022)</p>
    <p>He sustained a double femur fracture in a car accident in 2020. He underwent surgery and had a metal plate inserted into his left thigh. (lequipe.fr, 01 May 2020; Instagram profile, 28 Apr 2021)</p>
    <p>A back injury forced him to withdraw from the 2018 European Championships in Novi Sad, Serbia. (lequipe.fr, 16 Jun 2018)</p>
    <p>He sprained his ankle at the 2013 World University Games in Kazan, Russian Federation. (centrepressaeyron.fr, 01 Aug 2013; guadeloupe.la1ere.fr, 12 Jul 2013)</p>
    <p>Awards and honours He was named a Knight of the National Order of Merit in France.</p>
    <p>SANCTION He was suspended for one year by the French Anti-Doping Agency [AFLD]. (lequipe.fr, 17 May 2019)</p>
    <h2>Statistics</h2>
  </body>
</html>
"""


OFFICIAL_ANNOUNCEMENT_HTML = """
<html>
  <head><meta property="article:published_time" content="2026-05-29T15:03:17+00:00" /></head>
  <body>
    <h1>GBR selection update for Cairo World Cup</h1>
    <main>
      <p>British Fencing can confirm Alex Example has withdrawn from the Cairo World Cup due to illness.</p>
      <p>Jamie Foil will replace Alex in the team event.</p>
    </main>
  </body>
</html>
"""


def fencer_identity(
    identity_id="identity-alex",
    name="Alex Example",
    country="Great Britain",
    fie_ids=None,
    row_ids=None,
):
    return {
        "identity_id": identity_id,
        "fencer_row_id": (row_ids or ["row-alex"])[0],
        "fencer_name": name,
        "country": country,
        "fie_ids": fie_ids or ["12345"],
        "fs_fencer_row_ids": row_ids or ["row-alex"],
    }


def test_migration_defines_injury_absence_table_shape():
    migration = Path("supabase/migrations/20260602_injuries.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_injury_absences" in normalized
    assert "source_key text not null" in normalized
    assert "identity_id uuid" in normalized
    assert "fencer_row_id uuid" in normalized
    assert "fencer_name text not null" in normalized
    assert "event_name text" in normalized
    assert "event_date date" in normalized
    assert "status_type text not null" in normalized
    assert "'injury'" in normalized
    assert "'illness'" in normalized
    assert "'suspension'" in normalized
    assert "'personal_absence'" in normalized
    assert "'unknown'" in normalized
    assert "summary text not null" in normalized
    assert "source_excerpt text not null" in normalized
    assert "source_url text not null" in normalized
    assert "confidence numeric" in normalized
    assert "metadata jsonb not null default '{}'" in normalized
    assert "unique (source_key)" in normalized


def test_parse_fie_athlete_profile_extracts_public_injury_rows_only():
    from scrape_injuries import parse_fie_athlete_profile

    rows = parse_fie_athlete_profile(
        FIE_ATHLETE_PROFILE_HTML,
        source_url="https://fie.org/athletes/22557",
        fencer=fencer_identity(
            identity_id="identity-jerent",
            name="JERENT Daniel",
            country="France",
            fie_ids=["22557"],
            row_ids=["row-jerent"],
        ),
        scraped_at=NOW,
    )

    assert len(rows) == 4
    first = rows[0]
    assert first["identity_id"] == "identity-jerent"
    assert first["fencer_row_id"] == "row-jerent"
    assert first["fie_id"] == "22557"
    assert first["fencer_name"] == "JERENT Daniel"
    assert first["country"] == "France"
    assert first["status_type"] == "injury"
    assert "2022 Challenge Monal" in first["event_name"]
    assert first["event_date"] == "2022-04-18"
    assert "unable to compete" in first["summary"]
    assert "foot injury" in first["source_excerpt"]
    assert first["source_url"] == "https://fie.org/athletes/22557"
    assert first["source_site"] == "fie.org"
    assert first["confidence"] >= 0.9
    assert first["metadata"]["source_section"] == "Injuries"
    assert all("suspended" not in row["summary"].casefold() for row in rows)


def test_extract_article_mentions_from_official_announcement_without_speculation():
    from scrape_injuries import extract_article_mentions, parse_official_article

    article = parse_official_article(
        "https://www.britishfencing.com/selection-update-cairo-world-cup/",
        OFFICIAL_ANNOUNCEMENT_HTML,
        source="british_fencing_news",
    )

    rows, ambiguous = extract_article_mentions(
        article,
        known_fencers=[fencer_identity()],
        scraped_at=NOW,
    )

    assert ambiguous == []
    assert len(rows) == 1
    row = rows[0]
    assert row["status_type"] == "illness"
    assert row["event_name"] == "Cairo World Cup"
    assert row["event_date"] == "2026-05-29"
    assert row["summary"] == "British Fencing can confirm Alex Example has withdrawn from the Cairo World Cup due to illness."
    assert "diagnosis" not in row["metadata"]


def test_status_type_distinguishes_non_injury_absence_labels():
    from scrape_injuries import classify_status_type

    assert classify_status_type("Taylor Fencer withdrew due to illness.") == "illness"
    assert classify_status_type("Taylor Fencer was suspended for one year.") == "suspension"
    assert classify_status_type("Taylor Fencer is absent for personal reasons.") == "personal_absence"
    assert classify_status_type("Taylor Fencer withdrew from the event.") == "unknown"
    assert classify_status_type("Taylor Fencer had surgery after an injury.") == "injury"


def test_source_excerpt_is_limited_without_overflow():
    from scrape_injuries import build_injury_absence_row

    statement = (
        "Alex Example has withdrawn from the Cairo World Cup due to illness. "
        "This official update repeats public details without adding private medical information. "
        "No diagnosis is provided by the source."
    )

    row = build_injury_absence_row(
        fencer=fencer_identity(),
        statement=statement,
        status_type="illness",
        source_url="https://www.britishfencing.com/selection-update-cairo-world-cup/",
        source="british_fencing_news",
        source_site="britishfencing.com",
        event_name="Cairo World Cup",
        event_date="2026-05-29",
        scraped_at=NOW,
        excerpt_limit=120,
    )

    assert len(row["source_excerpt"]) <= 120
    assert row["source_excerpt"].endswith("...")
    assert row["summary"] == row["source_excerpt"]


def test_match_fencer_mentions_logs_ambiguous_names_without_guessing():
    from scrape_injuries import match_fencer_mentions

    known = [
        fencer_identity("identity-us", "Jordan Lee", "United States", ["555"], ["row-us"]),
        fencer_identity("identity-can", "Jordan Lee", "Canada", ["556"], ["row-can"]),
        fencer_identity("identity-kiefer", "Lee Kiefer", "United States", ["222"], ["row-kiefer"]),
    ]

    matches, ambiguous = match_fencer_mentions("Jordan Lee withdrew due to illness.", known)

    assert matches == []
    assert ambiguous == [
        {
            "mention": "Jordan Lee",
            "reason": "ambiguous_fencer_name",
            "candidate_identity_ids": ["identity-us", "identity-can"],
        }
    ]

    matches, ambiguous = match_fencer_mentions("Lee Kiefer withdrew due to illness.", known)
    assert [match["identity_id"] for match in matches] == ["identity-kiefer"]
    assert ambiguous == []


def test_blocked_source_stub_records_no_public_data_without_fencer_row():
    from scrape_injuries import build_no_public_data_stub

    stub = build_no_public_data_stub(
        source="fie_athlete_profiles",
        source_url="https://fie.org/athletes/22557",
        reason="blocked: 403 forbidden",
    )

    assert stub == {
        "source": "fie_athlete_profiles",
        "source_url": "https://fie.org/athletes/22557",
        "public_data_available": False,
        "reason": "blocked: 403 forbidden",
    }


def test_upsert_injury_absences_dedupes_by_source_key():
    from scrape_injuries import upsert_injury_absences

    client = FakeSupabase()
    rows = [
        {"source_key": "same", "summary": "older"},
        {"source_key": "same", "summary": "newer"},
        {"source_key": "other", "summary": "second"},
    ]

    written = upsert_injury_absences(client, rows, batch_size=2)

    assert written == 2
    assert client.upserts == [
        ("fs_fencer_injury_absences", [{"source_key": "same", "summary": "newer"}, {"source_key": "other", "summary": "second"}], "source_key")
    ]


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.pending_rows = None
        self.pending_conflict = None

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append((self.table_name, self.pending_rows, self.pending_conflict))
        return FakeResult(self.pending_rows)


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)
