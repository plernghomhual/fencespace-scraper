from __future__ import annotations


SPORT_INDEX_HTML = """
<html><body>
<table>
  <tr>
    <td><a href="/editions/1">Athens 1896</a></td>
    <td><a href="/editions/1/sports/FEN">Fencing</a></td>
  </tr>
  <tr>
    <td><a href="/editions/21">Atlanta 1996</a></td>
    <td><a href="/editions/21/sports/FEN">Fencing</a></td>
  </tr>
  <tr>
    <td><a href="/editions/25">Sydney 2000</a></td>
    <td><a href="/editions/25/sports/FEN">Fencing</a></td>
  </tr>
</table>
</body></html>
"""


EDITION_HTML = """
<html><body>
<h1>Fencing at the 1896 Summer Olympics</h1>
<table>
  <tr><th>Event</th><th>Date</th></tr>
  <tr>
    <td><a href="/results/72001">Foil, Individual, Men</a></td>
    <td>7 April 1896</td>
  </tr>
  <tr>
    <td><a href="/results/72002">Épée, Team, Men</a></td>
    <td>9 April 1896</td>
  </tr>
</table>
</body></html>
"""


INDIVIDUAL_RESULT_HTML = """
<html><body>
<table class="table table-striped">
  <tr><th>Rank</th><th>Competitor</th><th>NOC</th><th>Medal</th></tr>
  <tr>
    <td>1</td>
    <td><a href="/athletes/222">Nedo Nadi</a></td>
    <td><a href="/countries/ITA">Italy</a></td>
    <td>Gold</td>
  </tr>
  <tr>
    <td>2</td>
    <td><a href="/athletes/333">Renée Garilhe</a></td>
    <td><a href="/countries/FRA">France</a></td>
    <td>Silver</td>
  </tr>
  <tr>
    <td>=3</td>
    <td>Ágnes Geréb</td>
    <td>Hungary</td>
    <td>Bronze</td>
  </tr>
  <tr>
    <td></td>
    <td>Сергей Шариков</td>
    <td><a href="/countries/URS">Soviet Union</a></td>
    <td>Bronze</td>
  </tr>
</table>
</body></html>
"""


TEAM_RESULT_HTML = """
<html><body>
<table class="table table-striped">
  <tr><th>Rank</th><th>Team</th><th>NOC</th><th>Medal</th></tr>
  <tr>
    <td>1</td>
    <td><a href="/countries/FRA">France</a></td>
    <td>FRA</td>
    <td>Gold</td>
  </tr>
  <tr>
    <td>2</td>
    <td>Great Britain</td>
    <td><a href="/countries/GBR">Great Britain</a></td>
    <td>Silver</td>
  </tr>
</table>
</body></html>
"""


class FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.urls: list[str] = []

    def get(self, url: str) -> str | None:
        self.urls.append(url)
        return self.pages.get(url)


def test_parse_sport_index_keeps_pre_2000_fencing_editions():
    from scrape_historical_olympedia import parse_sport_index

    editions = parse_sport_index(SPORT_INDEX_HTML)

    assert [edition["edition_id"] for edition in editions] == ["1", "21"]
    assert editions[0] == {
        "edition_id": "1",
        "edition_name": "Athens 1896",
        "year": 1896,
        "url": "https://www.olympedia.org/editions/1/sports/FEN",
    }


def test_parse_edition_events_builds_individual_and_team_source_urls():
    from scrape_historical_olympedia import parse_edition_events

    edition = {
        "edition_id": "1",
        "edition_name": "Athens 1896",
        "year": 1896,
        "url": "https://www.olympedia.org/editions/1/sports/FEN",
    }

    events = parse_edition_events(EDITION_HTML, edition)

    assert [event["source_id"] for event in events] == [
        "olympedia:1:72001",
        "olympedia:1:72002",
    ]
    assert events[0]["tournament"] == "Athens 1896 - Foil, Individual, Men"
    assert events[0]["classification"] == {
        "weapon": "Foil",
        "gender": "Men",
        "team": False,
        "category": "Senior",
    }
    assert events[1]["classification"] == {
        "weapon": "Epee",
        "gender": "Men",
        "team": True,
        "category": "Senior",
    }
    assert events[1]["source_url"] == "https://www.olympedia.org/results/72002"


def test_parse_result_rows_handles_historical_country_ties_and_unicode_names():
    from scrape_historical_olympedia import parse_result_rows

    event = {
        "source_id": "olympedia:10:73001",
        "source_url": "https://www.olympedia.org/results/73001",
        "classification": {"team": False},
    }

    rows = parse_result_rows(INDIVIDUAL_RESULT_HTML, event)

    assert rows == [
        {
            "rank": 1,
            "medal": "Gold",
            "name": "Nedo Nadi",
            "country": "ITA",
            "country_name": "Italy",
            "team": False,
            "athlete_id": "222",
            "source_url": "https://www.olympedia.org/results/73001",
        },
        {
            "rank": 2,
            "medal": "Silver",
            "name": "Renée Garilhe",
            "country": "FRA",
            "country_name": "France",
            "team": False,
            "athlete_id": "333",
            "source_url": "https://www.olympedia.org/results/73001",
        },
        {
            "rank": 3,
            "medal": "Bronze",
            "name": "Ágnes Geréb",
            "country": "HUN",
            "country_name": "Hungary",
            "team": False,
            "athlete_id": None,
            "source_url": "https://www.olympedia.org/results/73001",
        },
        {
            "rank": 3,
            "medal": "Bronze",
            "name": "Сергей Шариков",
            "country": "URS",
            "country_name": "Soviet Union",
            "team": False,
            "athlete_id": None,
            "source_url": "https://www.olympedia.org/results/73001",
        },
    ]


def test_parse_result_rows_handles_team_results_without_fencer_identity():
    from scrape_historical_olympedia import parse_result_rows

    event = {
        "source_id": "olympedia:10:73002",
        "source_url": "https://www.olympedia.org/results/73002",
        "classification": {"team": True},
    }

    rows = parse_result_rows(TEAM_RESULT_HTML, event)

    assert rows == [
        {
            "rank": 1,
            "medal": "Gold",
            "name": "France",
            "country": "FRA",
            "country_name": "France",
            "team": True,
            "athlete_id": None,
            "source_url": "https://www.olympedia.org/results/73002",
        },
        {
            "rank": 2,
            "medal": "Silver",
            "name": "Great Britain",
            "country": "GBR",
            "country_name": "Great Britain",
            "team": True,
            "athlete_id": None,
            "source_url": "https://www.olympedia.org/results/73002",
        },
    ]


def test_build_result_rows_matches_explicitly_and_logs_unmatched_individuals():
    from scrape_historical_olympedia import build_fencer_index, build_result_rows

    event = {
        "source_id": "olympedia:10:73001",
        "event_name": "Foil, Individual, Men",
        "classification": {"team": False},
        "source_url": "https://www.olympedia.org/results/73001",
    }
    fencer_index = build_fencer_index(
        [
            {"id": "fie-match", "fie_id": "999", "name": "Different Name", "country": "USA"},
            {
                "id": "athlete-match",
                "fie_id": None,
                "name": "Nedo Nadi",
                "country": "ITA",
                "metadata": {"olympedia_athlete_id": "222"},
            },
            {"id": "canonical-match", "name": "Agnes Gereb", "country": "HUN"},
            {"id": "unicode-match", "name": "Сергей Шариков", "country": "URS"},
        ]
    )
    result_rows = [
        {"rank": 1, "name": "Wrong Name", "country": "USA", "fie_fencer_id": "999", "team": False},
        {"rank": 2, "name": "Nedo Nadi", "country": "ITA", "athlete_id": "222", "team": False},
        {"rank": 3, "name": "Ágnes Geréb", "country": "HUN", "team": False},
        {"rank": 4, "name": "Сергей Шариков", "country": "URS", "team": False},
        {"rank": 5, "name": "Mystery Fencer", "country": "FRA", "team": False},
    ]

    db_rows, unmatched = build_result_rows("tournament-1", event, result_rows, fencer_index)

    assert [row["fencer_id"] for row in db_rows] == [
        "fie-match",
        "athlete-match",
        "canonical-match",
        "unicode-match",
    ]
    assert [row["metadata"]["match_method"] for row in db_rows] == [
        "fie_id",
        "olympedia_athlete_id",
        "canonical_name_country",
        "canonical_name_country",
    ]
    assert unmatched == [
        {
            "source_id": "olympedia:10:73001",
            "source_url": "https://www.olympedia.org/results/73001",
            "name": "Mystery Fencer",
            "country": "FRA",
            "athlete_id": None,
            "fie_fencer_id": None,
            "reason": "unmatched_individual_fencer",
        }
    ]
    assert "Mystery Fencer" not in {row["name"] for row in db_rows}


def test_build_result_rows_allows_team_rows_without_orphaning_individuals():
    from scrape_historical_olympedia import build_result_rows

    event = {
        "source_id": "olympedia:10:73002",
        "event_name": "Épée, Team, Men",
        "classification": {"team": True},
        "source_url": "https://www.olympedia.org/results/73002",
    }
    result_rows = [{"rank": 1, "name": "France", "country": "FRA", "team": True, "medal": "Gold"}]

    db_rows, unmatched = build_result_rows("tournament-2", event, result_rows, {"fie": {}, "athlete": {}, "canonical": {}})

    assert unmatched == []
    assert db_rows[0]["fencer_id"] is None
    assert db_rows[0]["metadata"]["team"] is True
    assert db_rows[0]["metadata"]["match_method"] == "team_result"


def test_crawl_resume_skips_done_result_pages_and_persists_new_done_state():
    from scrape_historical_olympedia import OLYMPEDIA_BASE, crawl_historical_olympedia

    edition_url = f"{OLYMPEDIA_BASE}/editions/1/sports/FEN"
    done_result_url = f"{OLYMPEDIA_BASE}/results/72001"
    new_result_url = f"{OLYMPEDIA_BASE}/results/72002"
    pages = {
        f"{OLYMPEDIA_BASE}/sports/FEN": SPORT_INDEX_HTML,
        edition_url: EDITION_HTML,
        new_result_url: TEAM_RESULT_HTML,
    }
    fetcher = FakeFetcher(pages)
    written_events = []
    state_updates = []
    sleeps = []

    def process_event(event, rows):
        written_events.append((event["source_id"], len(rows)))
        return len(rows)

    result = crawl_historical_olympedia(
        fetcher=fetcher,
        done_source_ids={"olympedia:1:72001"},
        process_event=process_event,
        persist_done=lambda done: state_updates.append(sorted(done)),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )

    assert result == {"written": 1, "failed": 0, "skipped": 1}
    assert written_events == [("olympedia:1:72002", 2)]
    assert done_result_url not in fetcher.urls
    assert new_result_url in fetcher.urls
    assert state_updates[-1] == ["olympedia:1:72001", "olympedia:1:72002"]
    assert sleeps
