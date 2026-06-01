import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


EDITION = {
    "edition_id": "paris-2024-paralympic-games",
    "edition_name": "Paris 2024 Paralympic Games",
    "year": "2024",
    "url": "https://www.paralympic.org/paris-2024-paralympic-games/results/wheelchair-fencing",
}


# Fixture follows the official paralympic.org sport page shape probed on 2026-06-01:
# table 1 is "Events and Medallists"; the first cell links to the event result page.
SPORT_PAGE_HTML = """
<html><body>
<h1>Results Archive - Paris 2024 Paralympic Games - Wheelchair Fencing</h1>
<table><tr><td>medal standings</td></tr></table>
<table>
  <tr><th>Events</th><th></th><th></th><th></th></tr>
  <tr>
    <td><a href="/paris-2024-paralympic-games/results/wheelchair-fencing/men-s-epee-individual-category">Men's Epee Individual Category A</a></td>
    <td>Gang Sun</td><td>Piers Gilliver</td><td>Hakan Akkaya</td>
  </tr>
  <tr>
    <td><a href="/paris-2024-paralympic-games/results/wheelchair-fencing/women-s-foil-team">Women's Foil Team</a></td>
    <td>People's Republic of China</td><td>Hungary</td><td>Italy</td>
  </tr>
</table>
</body></html>
"""


# Fixture follows the official event page shape:
# first table is "Medallists"; later tables are bouts/pools and must not become placements.
EVENT_PAGE_HTML = """
<html><body>
<h2>Wheelchair Fencing - Men's Epee Individual Category A</h2>
<table>
  <tr><th class="left medallists" colspan="4" scope="col">Medallists</th></tr>
  <tr>
    <td class="right Ranking"><span>1</span></td>
    <td class="left NPC"><a class="npc-flag" title="People's Republic of China"><abbr>CHN</abbr></a></td>
    <td class="left Athlete"><a class="athlete-name" href="/gang-sun"><span class="athlete">Gang Sun</span></a></td>
    <td class="center Medal"><div class="MEDG"></div></td>
  </tr>
  <tr>
    <td class="right Ranking"><span>2</span></td>
    <td class="left NPC"><a class="npc-flag" title="Great Britain"><abbr>GBR</abbr></a></td>
    <td class="left Athlete"><a class="athlete-name" href="/piers-gilliver"><span class="athlete">Piers Gilliver</span></a></td>
    <td class="center Medal"><div class="MEDS"></div></td>
  </tr>
  <tr>
    <td class="right Ranking"><span>3</span></td>
    <td class="left NPC"><a class="npc-flag" title="Turkiye"><abbr>TUR</abbr></a></td>
    <td class="left Athlete"><a class="athlete-name" href="/hakan-akkaya"><span class="athlete">Hakan Akkaya</span></a></td>
    <td class="center Medal"><div class="MEDB"></div></td>
  </tr>
</table>
<table>
  <tr><th>NPC</th><th>Athlete</th><th>NPC</th><th>Athlete</th><th>Points1</th><th>Date</th></tr>
  <tr><td>TUR</td><td>Hakan Akkaya</td><td>ITA</td><td>Emanuele Lambertini</td><td>15-13</td><td>2024-09-06</td></tr>
</table>
</body></html>
"""


TEAM_EVENT_PAGE_HTML = """
<html><body>
<h2>Wheelchair Fencing - Women's Foil Team</h2>
<table>
  <tr><th class="left medallists" colspan="4" scope="col">Medallists</th></tr>
  <tr>
    <td class="right Ranking"><span>1</span></td>
    <td class="left NPC"><a class="npc-flag" title="People's Republic of China"><abbr>CHN</abbr></a></td>
    <td class="left Team">People's Republic of China Xufeng Zou Rong Xiao Haiyan Gu Yuandong Chen</td>
    <td class="center Medal"><div class="MEDG"></div></td>
  </tr>
</table>
</body></html>
"""


def test_paralympic_editions_cover_1980_to_2024():
    from scrape_paralympics import PARALYMPIC_EDITIONS

    years = [edition["year"] for edition in PARALYMPIC_EDITIONS]
    assert years[0] == "1980"
    assert years[-1] == "2024"
    assert "tokyo-2020" in {edition["edition_id"] for edition in PARALYMPIC_EDITIONS}
    assert "paris-2024-paralympic-games" in {edition["edition_id"] for edition in PARALYMPIC_EDITIONS}


def test_parse_sport_page_discovers_event_links():
    from scrape_paralympics import parse_sport_page

    events = parse_sport_page(SPORT_PAGE_HTML, EDITION)

    assert len(events) == 2
    assert events[0]["event_name"] == "Men's Epee Individual Category A"
    assert events[0]["event_code"] == "men-s-epee-individual-category"
    assert events[0]["edition_id"] == "paris-2024-paralympic-games"
    assert events[0]["event_url"].endswith("/men-s-epee-individual-category")
    assert events[1]["event_code"] == "women-s-foil-team"


def test_classify_event_modern_and_legacy_classes():
    from scrape_paralympics import classify_event

    assert classify_event("Men's Epee Individual Category A") == {
        "weapon": "Epee",
        "gender": "Men",
        "team": False,
        "disability_class": "A",
        "classification_description": "minimal impairment",
    }
    assert classify_event("Women's Individual Foil Cat. B")["disability_class"] == "B"
    assert classify_event("Men's Epee Individual 1C-3")["disability_class"] == "1C-3"
    assert classify_event("Women's Epee Team Cat. Open")["team"] is True


def test_parse_results_page_returns_medal_placements_only():
    from scrape_paralympics import parse_results_page

    rows = parse_results_page(EVENT_PAGE_HTML, {**EDITION, "event_code": "men-s-epee-individual-category"})

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "Gang Sun",
        "country": "CHN",
        "country_name": "People's Republic of China",
        "medal": "Gold",
        "athlete_slug": "gang-sun",
        "team": False,
    }
    assert rows[2]["medal"] == "Bronze"
    assert not any(row["name"] == "Emanuele Lambertini" for row in rows)


def test_parse_results_page_handles_team_medallists():
    from scrape_paralympics import parse_results_page

    rows = parse_results_page(TEAM_EVENT_PAGE_HTML, {**EDITION, "event_code": "women-s-foil-team"})

    assert rows == [
        {
            "rank": 1,
            "name": "People's Republic of China Xufeng Zou Rong Xiao Haiyan Gu Yuandong Chen",
            "country": "CHN",
            "country_name": "People's Republic of China",
            "medal": "Gold",
            "athlete_slug": None,
            "team": True,
        }
    ]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.filters = []
        self.on_conflict = None

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def delete(self):
        self.action = "delete"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        if self.action == "upsert":
            self.client.upserts.append((self.name, self.payload, self.on_conflict))
            return FakeResult([{"id": "tournament-1"}])
        if self.action == "delete":
            self.client.deletes.append((self.name, tuple(self.filters)))
            return FakeResult()
        if self.action == "insert":
            self.client.inserts.append((self.name, self.payload))
            return FakeResult(self.payload)
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.upserts = []
        self.deletes = []
        self.inserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_upsert_tournament_uses_required_source_id_and_metadata(monkeypatch):
    import scrape_paralympics

    fake = FakeClient()
    event = {
        **EDITION,
        "event_name": "Men's Epee Individual Category A",
        "event_code": "men-s-epee-individual-category",
        "event_url": "https://www.paralympic.org/paris-2024-paralympic-games/results/wheelchair-fencing/men-s-epee-individual-category",
    }
    classification = scrape_paralympics.classify_event(event["event_name"])
    monkeypatch.setattr(scrape_paralympics, "supabase", fake)

    tournament_id = scrape_paralympics.upsert_tournament(event, classification)

    assert tournament_id == "tournament-1"
    table_name, row, on_conflict = fake.upserts[0]
    assert table_name == "fs_tournaments"
    assert on_conflict == "source_id"
    assert row["source_id"] == "paralympics:paris-2024-paralympic-games:men-s-epee-individual-category"
    assert row["type"] == "paralympics"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior A"
    assert row["metadata"]["disability_class"] == "A"
    assert row["metadata"]["classification_description"] == "minimal impairment"


def test_upsert_results_deletes_and_inserts_with_fencer_matching(monkeypatch):
    import scrape_paralympics

    fake = FakeClient()
    rows = scrape_paralympics.parse_results_page(
        EVENT_PAGE_HTML,
        {**EDITION, "event_code": "men-s-epee-individual-category"},
    )
    event = {
        **EDITION,
        "event_name": "Men's Epee Individual Category A",
        "event_code": "men-s-epee-individual-category",
        "event_url": "https://www.paralympic.org/paris-2024-paralympic-games/results/wheelchair-fencing/men-s-epee-individual-category",
    }
    classification = scrape_paralympics.classify_event(event["event_name"])
    monkeypatch.setattr(scrape_paralympics, "supabase", fake)
    monkeypatch.setattr(
        scrape_paralympics,
        "_match_fencer",
        lambda name, country: "fencer-1" if (name, country) == ("Gang Sun", "CHN") else None,
    )

    written = scrape_paralympics.upsert_results("tournament-1", rows, event, classification)

    assert rows[0]["name"] == "Gang Sun"
    assert written == 3
    assert fake.deletes == [("fs_results", (("tournament_id", "tournament-1"),))]
    table_name, inserted = fake.inserts[0]
    assert table_name == "fs_results"
    assert inserted[0]["fencer_id"] == "fencer-1"
    assert inserted[0]["nationality"] == "CHN"
    assert inserted[0]["medal"] == "Gold"
    assert inserted[0]["metadata"]["paralympic_athlete_slug"] == "gang-sun"
    assert inserted[0]["metadata"]["disability_class"] == "A"
