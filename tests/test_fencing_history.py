from pathlib import Path

import pytest


FIE_HISTORY_HTML = """
<html>
  <body>
    <h1>Fencing History</h1>
    <p>Women's foil is only introduced in 1924 while women's epee will wait
    until 1996 and women's sabre the 21st century.</p>
    <p>Further to the problems raised during the Olympic Games of 1908 and
    of 1912 which led to the boycott of France at the Games of Stockholm,
    it is on Rene Lacroix's initiative, on 29 November 1913, in the lounges
    of the Automobile Club of France, that the FIE was created and that it
    adopted the 1st rules at epee.</p>
    <p>It was necessary to wait until 1931 to see the experimentation of the
    first electric control apparatus.</p>
    <p>We know the continuation: the electric apparatus of signalisation of
    hits was adopted by the federation in 1936.</p>
  </body>
</html>
"""


BRITANNICA_HISTORY_HTML = """
<html>
  <body>
    <p>As a result, in 1913 the Federation Internationale d'Escrime was
    founded and thereafter was the governing body of international fencing
    for amateurs, both in the Olympic Games and in world championships.</p>
    <p>In 1936 the electrical epee was adopted for competition, eliminating
    the sometimes inaccurate determinations by fencing officials.</p>
    <p>In 1955 electrical scoring was introduced for foil competitions,
    making its Olympic debut at the 1956 Games.</p>
  </body>
</html>
"""


USAF_NONCOMBATIVITY_HTML = """
<html>
  <body>
    <h1>Updated Unwillingness to Fight (Non-Combativity) Rules Take Effect
    Jan. 1, 2023</h1>
    <p>The rule changes, enforced at all USA Fencing tournaments beginning
    Jan. 1, 2023, affect how P-Cards are awarded for unwillingness to fight,
    also known as non-combativity.</p>
    <p>On November 26, 2022 during the 2022 FIE Congress, a proposal to
    change the Unwillingness to Fight (Non-Combativity) Rules was presented
    and passed by the FIE.</p>
  </body>
</html>
"""


SABRE_TIMING_TEXT = """
NEW RULES FOR THE 2016-17 SEASON
Characteristics to be modified
Time for double hit | Former rules 120 ms +/- 10 | New rules 170 ms +/- 10
Scoring apparatuses with the new modification are marked FIE 2016.
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


def test_migration_creates_fencing_history_events_table():
    sql = Path("supabase/migrations/20260602_fencing_history.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS public.fs_fencing_history_events" in sql
    assert "event_date date" in sql
    assert "event_year integer NOT NULL" in sql
    assert "category text NOT NULL" in sql
    assert "title text NOT NULL" in sql
    assert "description text NOT NULL" in sql
    assert "affected_weapons text[] NOT NULL" in sql
    assert "source_url text NOT NULL" in sql
    assert "confidence numeric" in sql
    assert "metadata jsonb NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "UNIQUE (category, event_year, title)" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "USING gin (affected_weapons)" in sql
    assert "confidence >= 0" in sql
    assert "confidence <= 1" in sql


def test_parse_fie_history_fixture_extracts_cited_timeline_events():
    from scrape_fencing_history import parse_fie_history_page

    events = parse_fie_history_page(FIE_HISTORY_HTML, "https://fie.org/fie/history")

    titles = {event["title"] for event in events}
    assert "FIE founded and first epee rules adopted" in titles
    assert "First electric control apparatus experimented" in titles
    assert "Electric hit-signalling apparatus adopted by FIE" in titles
    assert "Women's foil introduced at the Olympic Games" in titles
    assert "Women's epee added to the Olympic programme" in titles
    assert {event["source_url"] for event in events} == {"https://fie.org/fie/history"}
    assert {event["category"] for event in events} >= {
        "governance",
        "equipment",
        "scoring_timing",
        "rule_change",
    }


def test_parse_britannica_fixture_adds_electric_foil_evidence():
    from scrape_fencing_history import parse_britannica_history_page

    events = parse_britannica_history_page(
        BRITANNICA_HISTORY_HTML,
        "https://www.britannica.com/sports/fencing/Organized-sport",
    )

    foil = [event for event in events if event["title"] == "Electrical scoring introduced for foil"]
    assert len(foil) == 1
    assert foil[0]["event_year"] == 1955
    assert foil[0]["affected_weapons"] == ["foil"]
    assert foil[0]["metadata"]["olympic_debut_year"] == 1956
    assert foil[0]["source_url"] == "https://www.britannica.com/sports/fencing/Organized-sport"


def test_parse_usaf_noncombativity_fixture_requires_fie_congress_evidence():
    from scrape_fencing_history import parse_usaf_noncombativity_page

    events = parse_usaf_noncombativity_page(
        USAF_NONCOMBATIVITY_HTML,
        "https://www.usafencing.org/news/2022/december/19/updated-unwillingness-to-fight-noncombativity-rules-take-effect-jan-1-2023",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_date"] == "2023-01-01"
    assert event["event_year"] == 2023
    assert event["category"] == "rule_change"
    assert event["title"] == "Updated non-combativity P-Card rules take effect"
    assert event["affected_weapons"] == ["epee", "foil", "sabre"]
    assert event["metadata"]["fie_congress_date"] == "2022-11-26"


def test_parse_sabre_timing_fixture_extracts_lockout_change():
    from scrape_fencing_history import parse_sabre_timing_text

    events = parse_sabre_timing_text(
        SABRE_TIMING_TEXT,
        "https://static.fie.org/uploads/28/141008-123895-new%20rules%20for%20sabre_cover_ang.pdf",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_year"] == 2016
    assert event["title"] == "Sabre double-hit timing changed to 170 ms"
    assert event["affected_weapons"] == ["sabre"]
    assert event["metadata"]["former_timing_ms"] == 120
    assert event["metadata"]["new_timing_ms"] == 170


def test_validate_event_requires_citation_source_url():
    from scrape_fencing_history import validate_event

    with pytest.raises(ValueError, match="source_url"):
        validate_event(
            {
                "event_year": 1936,
                "category": "equipment",
                "title": "Uncited event",
                "description": "This should not be accepted.",
                "affected_weapons": ["epee"],
                "confidence": 0.5,
                "metadata": {},
            }
        )


def test_dedupe_merges_duplicate_sources_and_conflicting_dates():
    from scrape_fencing_history import dedupe_events

    events = [
        {
            "event_date": None,
            "event_year": 1936,
            "category": "scoring_timing",
            "title": "Electric epee adopted for competition",
            "description": "FIE history dates adoption to 1936.",
            "affected_weapons": ["epee"],
            "source_url": "https://fie.org/fie/history",
            "confidence": 0.9,
            "metadata": {"source_name": "FIE"},
        },
        {
            "event_date": None,
            "event_year": 1936,
            "category": "scoring_timing",
            "title": "Electric epee adopted for competition",
            "description": "Duplicate citation.",
            "affected_weapons": ["epee"],
            "source_url": "https://www.britannica.com/sports/fencing/Organized-sport",
            "confidence": 0.85,
            "metadata": {"source_name": "Britannica"},
        },
        {
            "event_date": None,
            "event_year": 1933,
            "category": "scoring_timing",
            "title": "Electric epee adopted for competition",
            "description": "A history source dates the same apparatus adoption to 1933.",
            "affected_weapons": ["epee"],
            "source_url": "https://www.fencingmaster.com/history/history.htm",
            "confidence": 0.7,
            "metadata": {"source_name": "Fencing history source"},
        },
    ]

    deduped = dedupe_events(events)

    assert len(deduped) == 1
    row = deduped[0]
    assert row["event_year"] == 1936
    assert row["source_url"] == "https://fie.org/fie/history"
    assert row["metadata"]["source_urls"] == [
        "https://fie.org/fie/history",
        "https://www.britannica.com/sports/fencing/Organized-sport",
        "https://www.fencingmaster.com/history/history.htm",
    ]
    assert row["metadata"]["conflicting_dates"] == [
        {
            "event_date": None,
            "event_year": 1933,
            "source_url": "https://www.fencingmaster.com/history/history.htm",
        }
    ]


def test_collect_history_events_are_frontend_ready_and_cited():
    from scrape_fencing_history import collect_history_events

    events = collect_history_events(include_remote=False)

    assert len(events) >= 8
    assert events == sorted(events, key=lambda row: (row["event_year"], row["title"]))
    categories = {event["category"] for event in events}
    assert {"governance", "rule_change", "equipment", "scoring_timing"} <= categories
    for event in events:
        assert event["source_url"].startswith("https://")
        assert isinstance(event["metadata"], dict)
        assert isinstance(event["affected_weapons"], list)
        assert 0 <= event["confidence"] <= 1


def test_scrape_fencing_history_upserts_deduped_rows(monkeypatch):
    from scrape_fencing_history import scrape_fencing_history

    fake = FakeSupabase()
    monkeypatch.setattr("scrape_fencing_history.set_state", lambda *args, **kwargs: None)

    written = scrape_fencing_history(supabase=fake, include_remote=False)

    assert written >= 8
    assert len(fake.upserts) == 1
    upsert = fake.upserts[0]
    assert upsert["table"] == "fs_fencing_history_events"
    assert upsert["on_conflict"] == "category,event_year,title"
    assert len(upsert["rows"]) == written
    assert all(row["source_url"] for row in upsert["rows"])
    assert upsert["rows"] == sorted(upsert["rows"], key=lambda row: (row["event_year"], row["title"]))
