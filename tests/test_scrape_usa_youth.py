import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


PUBLIC_YOUTH_RESULTS_HTML = """
<html><body>
  <h1>Rain City Super Youth Circuit (SYC) Results</h1>
  <p>
    NOTE: The results below are unofficial and possibly stale. For complete results,
    please visit <a href="https://member.usafencing.org/details/tournaments/9099">
    the official Tournament page at USA Fencing</a>.
  </p>

  <a name="11111111-1111-4111-8111-111111111111"></a>
  <div class="card mb-4">
    <div class="card-header">
      <span>Y14 Men's Epee</span>
      <a href="/events/aaaaaaa1-1111-4111-8111-111111111111">View Round Results</a>
    </div>
    <div class="card-body">
      <a href="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results/11111111-1111-4111-8111-111111111111">
        View Full Results
      </a>
    </div>
  </div>

  <a name="22222222-2222-4222-8222-222222222222"></a>
  <div class="card mb-4">
    <div class="card-header">
      <span>Youth 12 Women's Foil</span>
      <a href="/events/bbbbbbb2-2222-4222-8222-222222222222">View Round Results</a>
    </div>
    <div class="card-body">
      <a href="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results/22222222-2222-4222-8222-222222222222">
        View Full Results
      </a>
    </div>
  </div>

  <a name="33333333-3333-4333-8333-333333333333"></a>
  <div class="card mb-4">
    <div class="card-header"><span>Y10 Men's Saber</span></div>
    <div class="card-body">
      <a href="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results/33333333-3333-4333-8333-333333333333">
        View Full Results
      </a>
    </div>
  </div>

  April 25 - 28 2025
  Rain City Fencing Center
  <a href="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results.csv">Download Results</a>
</body></html>
"""


PUBLIC_YOUTH_CSV = """Date,Tournament,Event,Weapon,Event Gender,Rating Restriction,Age Restriction,Event Rating,Event Size,Place,Competitor Last Name,Competitor First Name,Club,Division,FIE ID,Rating Before Event,Rating Earned
2025-04-25,Rain City Super Youth Circuit (SYC),Y14 Men's Epee,Epee,Men,Open,Y14,,54,1,Kim,Alex,RainCityFencing,WA,998877,C2024,B2025
2025-04-25,Rain City Super Youth Circuit (SYC),Youth 12 Women's Foil,Foil,Women,Open,Youth 12,,41,2,Stone,Maya,NorthwestFC,OR,,D2024,C2025
2025-04-25,Rain City Super Youth Circuit (SYC),Y12 Women's Foil,Foil,Women,Open,Y12,,41,3,Unmatched,Minor,OnlyClub,CA,,U,
2025-04-25,Rain City Super Youth Circuit (SYC),Y10 Men's Saber,Saber,Men,Open,Y10,,24,1,Too,Young,YouthClub,WA,,U,E2025
2025-04-25,Local RYC,Y14 Men's Epee,Epee,Men,Open,Y14,,12,1,Regional,Only,LocalClub,WA,,U,E2025
"""


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")
        self.headers = {"content-type": "text/html"}
        self.url = "https://www.askfred.net/example"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.kwargs = {}
        self.filters = []

    def upsert(self, payload, **kwargs):
        self.action = "upsert"
        self.payload = payload
        self.kwargs = kwargs
        return self

    def select(self, payload):
        self.action = "select"
        self.payload = payload
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def execute(self):
        self.client.operations.append(
            {
                "table": self.name,
                "action": self.action,
                "payload": self.payload,
                "kwargs": self.kwargs,
                "filters": self.filters,
            }
        )
        return FakeResult(self.client.select_data.get(self.name, []))


class FakeSupabase:
    def __init__(self):
        self.operations = []
        self.select_data = {}

    def table(self, name):
        return FakeTable(self, name)


def test_parse_public_fred_youth_fixture_filters_y12_y14_and_normalizes_fields():
    from scrape_usa_youth import (
        TournamentRef,
        build_tournament_rows,
        group_youth_csv_rows,
        parse_csv_results,
        parse_event_cards,
    )

    event_map = parse_event_cards(PUBLIC_YOUTH_RESULTS_HTML)
    grouped = group_youth_csv_rows(parse_csv_results(PUBLIC_YOUTH_CSV), event_map)
    tournament_rows = build_tournament_rows(
        TournamentRef(
            tournament_id="a80a125e-8e83-426f-9e4a-5893289b03b4",
            name="Rain City Super Youth Circuit (SYC)",
            results_path="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results",
        ),
        grouped,
    )

    assert sorted(event["age_group"] for event in grouped.values()) == ["Y12", "Y14"]
    assert len(tournament_rows) == 2
    y14 = next(row for row in tournament_rows if row["category"] == "Y14")
    y12 = next(row for row in tournament_rows if row["category"] == "Y12")
    assert y14["weapon"] == "Epee"
    assert y14["gender"] == "Men"
    assert y14["start_date"] == "2025-04-25"
    assert y14["source_id"] == "usa_youth:fred:11111111-1111-4111-8111-111111111111"
    assert y14["metadata"]["source_url"].endswith("/results/11111111-1111-4111-8111-111111111111")
    assert y14["metadata"]["fred_platform"] == "public_fred"
    assert y12["weapon"] == "Foil"
    assert y12["gender"] == "Women"
    assert y12["metadata"]["fred_event_name"] == "Youth 12 Women's Foil"


def test_normalize_age_group_accepts_y12_y14_variants_and_rejects_other_ages():
    from scrape_usa_youth import normalize_age_group

    assert normalize_age_group("Y14 Men's Saber") == "Y14"
    assert normalize_age_group("Youth 14 Women's Foil") == "Y14"
    assert normalize_age_group("Y-12 Mixed Epee") == "Y12"
    assert normalize_age_group("Youth-12 Women's Saber") == "Y12"
    assert normalize_age_group("Under 14 Men's Foil") == "Y14"
    assert normalize_age_group("Y10 Men's Foil") is None
    assert normalize_age_group("Cadet Women's Epee") is None


def test_collect_result_rows_matches_fie_first_then_identity_name_country_and_skips_unmatched():
    from scrape_usa_youth import (
        build_fencer_index,
        collect_result_rows,
        group_youth_csv_rows,
        parse_csv_results,
        parse_event_cards,
    )

    grouped = group_youth_csv_rows(parse_csv_results(PUBLIC_YOUTH_CSV), parse_event_cards(PUBLIC_YOUTH_RESULTS_HTML))
    fencer_index = build_fencer_index(
        fencer_rows=[
            {"id": "row-fie", "fie_id": "998877", "name": "Different Name", "country": "United States"},
            {"id": "row-identity", "fie_id": None, "name": "Maya Stone", "country": "United States"},
            {"id": "wrong-country", "fie_id": None, "name": "Minor Unmatched", "country": "Canada"},
        ],
        identity_rows=[
            {
                "id": "identity-maya",
                "canonical_name": "Maya Stone",
                "country": "United States",
                "fie_ids": [],
                "fs_fencer_row_ids": ["row-identity"],
            }
        ],
    )
    rows, unmatched = collect_result_rows(
        grouped,
        {
            "usa_youth:fred:11111111-1111-4111-8111-111111111111": 101,
            "usa_youth:fred:22222222-2222-4222-8222-222222222222": 102,
        },
        fencer_index,
    )

    assert [row["name"] for row in rows] == ["Alex Kim", "Maya Stone"]
    assert [row["fencer_id"] for row in rows] == ["row-fie", "row-identity"]
    assert rows[0]["fie_fencer_id"] == "998877"
    assert rows[0]["metadata"]["match_method"] == "fie_id"
    assert rows[0]["medal"] == "Gold"
    assert rows[1]["metadata"]["match_method"] == "identity_name_country"
    assert rows[1]["metadata"]["fred_club"] == "NorthwestFC"
    assert all(row["fencer_id"] for row in rows)
    assert unmatched == [
        {
            "name": "Minor Unmatched",
            "club": "OnlyClub",
            "division": "CA",
            "event": "Youth 12 Women's Foil",
            "source_url": "https://www.askfred.net/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results/22222222-2222-4222-8222-222222222222",
            "reason": "no_explicit_match",
        }
    ]


def test_probe_sources_stubs_blocked_endpoints_without_fetching_private_usa_fencing_pages():
    from scrape_usa_youth import probe_sources

    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        assert "member.usafencing.org" not in url
        assert "profile" not in url.lower()
        return {"status_code": 200, "url": url, "public": True}

    report = probe_sources(fetcher=fake_fetch, fetch_public=True)

    assert fetched == ["https://www.askfred.net/results?has_results=true&page=1"]
    assert report["public_sources"][0]["status_code"] == 200
    assert report["blocked_sources"] == [
        {
            "url": "https://member.usafencing.org/details/tournaments/{id}",
            "reason": "linked final authority pages may require member/session access; scraper does not fetch them",
        },
        {
            "url": "https://fred.usafencing.org/",
            "reason": "no public result application confirmed during probe; scraper uses public FRED result exports instead",
        },
        {
            "url": "https://fred.fencing.org/",
            "reason": "no public result application confirmed during probe; scraper uses public FRED result exports instead",
        },
    ]


def test_scrape_tournament_fetches_only_public_result_page_and_csv(monkeypatch):
    import scrape_usa_youth

    fetched = []

    def fake_request(path_or_url, **kwargs):
        fetched.append(path_or_url)
        if path_or_url.endswith(".csv"):
            return FakeResponse(PUBLIC_YOUTH_CSV)
        return FakeResponse(PUBLIC_YOUTH_RESULTS_HTML)

    monkeypatch.setattr(scrape_usa_youth, "request_get", fake_request)
    monkeypatch.setattr(scrape_usa_youth, "polite_sleep", lambda: None)
    monkeypatch.setattr(scrape_usa_youth, "upsert_tournaments", lambda rows: {row["source_id"]: 100 + idx for idx, row in enumerate(rows)})
    monkeypatch.setattr(scrape_usa_youth, "upsert_results", lambda rows: None)

    scrape_usa_youth.scrape_tournament(
        scrape_usa_youth.TournamentRef(
            tournament_id="a80a125e-8e83-426f-9e4a-5893289b03b4",
            name="Rain City Super Youth Circuit (SYC)",
            results_path="/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results",
        ),
        fencer_index=scrape_usa_youth.build_fencer_index(
            fencer_rows=[
                {"id": "row-fie", "fie_id": "998877", "name": "Alex Kim", "country": "United States"},
                {"id": "row-name", "fie_id": None, "name": "Maya Stone", "country": "United States"},
            ],
            identity_rows=[],
        ),
    )

    assert fetched == [
        "/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results.csv",
        "/tournaments/a80a125e-8e83-426f-9e4a-5893289b03b4/results",
    ]
    assert not any("member.usafencing.org" in url for url in fetched)
    assert not any("profile" in url.lower() or "/fencers/" in url.lower() for url in fetched)


def test_upsert_results_rejects_null_fencer_orphans(monkeypatch):
    import scrape_usa_youth

    monkeypatch.setattr(scrape_usa_youth, "supabase", FakeSupabase())

    with pytest.raises(ValueError, match="fencer_id"):
        scrape_usa_youth.upsert_results(
            [
                {
                    "tournament_id": 101,
                    "fencer_id": None,
                    "name": "Minor Unmatched",
                    "rank": 1,
                }
            ]
        )
