import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]


RESULTS_INDEX_HTML = """
<html><body>
  <a href="/tournaments/661f29e6-b496-4262-91a4-26d8b0833ef8">Tournament</a>
  <a href="/tournaments/661f29e6-b496-4262-91a4-26d8b0833ef8/conversation">Conversation</a>
  <a href="/tournaments/661f29e6-b496-4262-91a4-26d8b0833ef8/results">View Results</a>
  <a href="/tournaments/d482fe9d-4420-4122-83c8-27305c3376fa/results">January NAC Results</a>
  <a href="/tournaments/d482fe9d-4420-4122-83c8-27305c3376fa/results">Duplicate</a>
  <span>1 of 3 pages</span>
</body></html>
"""


EVENT_CARDS_HTML = """
<html><body>
  <div class="alert">
    For complete results, please visit
    <a href="https://member.usafencing.org/details/tournaments/9099">the official Tournament page at USA Fencing</a>.
  </div>

  <a name="eb05099a-882e-4852-8e34-c8a4f335b35d"></a>
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between align-items-center">
      <span>Vet Combined Women&#39;s Epee</span>
    </div>
    <div class="card-body">
      <a href="/tournaments/9e83a990-db92-4e10-889f-4e5e32f9497a/results/eb05099a-882e-4852-8e34-c8a4f335b35d">View Full Results</a>
    </div>
  </div>

  <a name="b433ec16-26f2-4db9-88c5-1a96f8d29585"></a>
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between align-items-center">
      <span>Division I Men&#39;s Saber</span>
      <a href="/events/b433ec16-26f2-4db9-88c5-1a96f8d29585">View Round Results</a>
    </div>
    <div class="card-body">
      <a href="/tournaments/9e83a990-db92-4e10-889f-4e5e32f9497a/results/b433ec16-26f2-4db9-88c5-1a96f8d29585">View Full Results</a>
    </div>
  </div>
</body></html>
"""


ROUND_ONLY_EVENT_CARD_HTML = """
<html><body>
  <a name="e9f3d294-d94c-42b3-905a-0485b6e7b87c"></a>
  <div class="card mb-4">
    <div class="card-header d-flex flex-column flex-md-row justify-content-between align-items-md-center">
      <span>Senior Mixed Foil</span>
      <span><small>14 Competitors, E1 Event</small></span>
      <a href="/events/e9f3d294-d94c-42b3-905a-0485b6e7b87c">View Round Results</a>
    </div>
    <div class="card-body p-0 overflow-scroll">
      <table><tbody>
        <tr><td>1</td><td>Swain, Taylor</td><td>NAPAVLYFA</td><td>U</td><td>E2026</td></tr>
      </tbody></table>
    </div>
  </div>
</body></html>
"""


RESULTS_CSV = """Date, Tournament, Event, Weapon, Event Gender, Rating Restriction, Age Resitrction, Event Rating, Event Size, Place, Competitor Last Name, Competitor First Name, Club, Usfa Number, Rating Before Event, Rating Earned
2025-01-03,January NAC,Vet Combined Women&#39;s Epee,Epee,Women,Open,VetCombined,,63,1,Hansen,Kira,Academy Of Fencing Masters (AFM),100313729,A2025,A2025
2025-01-03,January NAC,Vet Combined Women&#39;s Epee,Epee,Women,Open,VetCombined,,63,2,Marchant,Sandra,Rogue Fencing Academy,100041444,A2025,
2025-01-03,January NAC,Division I Men&#39;s Saber,Saber,Men,Open,Senior,A4,210,1,Kim,Alex,Fencers Club,,A2024,A2024
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, fake, name):
        self.fake = fake
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

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def select(self, columns):
        self.action = "select"
        self.payload = columns
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def execute(self):
        self.fake.operations.append(
            {
                "table": self.name,
                "action": self.action,
                "payload": self.payload,
                "kwargs": self.kwargs,
                "filters": self.filters,
            }
        )
        return FakeResult(self.fake.select_data.get(self.name, []))


class FakeSupabase:
    def __init__(self):
        self.operations = []
        self.select_data = {}

    def table(self, name):
        return FakeTable(self, name)


def test_parse_results_index_discovers_unique_result_tournaments():
    from scrape_fred import parse_results_index

    refs, total_pages = parse_results_index(RESULTS_INDEX_HTML)

    assert total_pages == 3
    assert [ref.tournament_id for ref in refs] == [
        "661f29e6-b496-4262-91a4-26d8b0833ef8",
        "d482fe9d-4420-4122-83c8-27305c3376fa",
    ]
    assert refs[0].results_path == "/tournaments/661f29e6-b496-4262-91a4-26d8b0833ef8/results"


def test_parse_event_cards_maps_display_names_to_event_ids():
    from scrape_fred import normalize_name_key, parse_event_cards

    event_map = parse_event_cards(EVENT_CARDS_HTML)

    womens_epee = event_map[normalize_name_key("Vet Combined Women's Epee")]
    mens_saber = event_map[normalize_name_key("Division I Men's Saber")]
    assert womens_epee["event_id"] == "eb05099a-882e-4852-8e34-c8a4f335b35d"
    assert womens_epee["source_id"] == "fred:eb05099a-882e-4852-8e34-c8a4f335b35d"
    assert mens_saber["round_event_id"] == "b433ec16-26f2-4db9-88c5-1a96f8d29585"


def test_parse_event_cards_uses_round_event_id_when_full_result_link_missing():
    from scrape_fred import normalize_name_key, parse_event_cards

    event_map = parse_event_cards(ROUND_ONLY_EVENT_CARD_HTML)

    mixed_foil = event_map[normalize_name_key("Senior Mixed Foil")]
    assert mixed_foil["event_id"] == "e9f3d294-d94c-42b3-905a-0485b6e7b87c"
    assert mixed_foil["source_id"] == "fred:e9f3d294-d94c-42b3-905a-0485b6e7b87c"
    assert mixed_foil["event_path"] == "/events/e9f3d294-d94c-42b3-905a-0485b6e7b87c"


def test_csv_rows_group_into_fred_tournament_rows():
    from scrape_fred import (
        TournamentRef,
        build_tournament_rows,
        group_csv_rows,
        parse_csv_results,
        parse_event_cards,
    )

    rows = parse_csv_results(RESULTS_CSV)
    grouped = group_csv_rows(rows, parse_event_cards(EVENT_CARDS_HTML))
    tournament_rows = build_tournament_rows(
        TournamentRef(
            tournament_id="9e83a990-db92-4e10-889f-4e5e32f9497a",
            name="January NAC",
            results_path="/tournaments/9e83a990-db92-4e10-889f-4e5e32f9497a/results",
        ),
        grouped,
    )

    assert len(tournament_rows) == 2
    womens_epee = next(row for row in tournament_rows if row["weapon"] == "Epee")
    assert womens_epee["source_id"] == "fred:eb05099a-882e-4852-8e34-c8a4f335b35d"
    assert womens_epee["name"] == "January NAC: Vet Combined Women's Epee"
    assert womens_epee["season"] == "2025"
    assert womens_epee["gender"] == "Women"
    assert womens_epee["category"] == "VetCombined"
    assert womens_epee["type"] == "FRED"
    assert womens_epee["metadata"]["fred_tournament_uuid"] == "9e83a990-db92-4e10-889f-4e5e32f9497a"


def test_fred_result_dedup_index_is_scoped_to_fred_rows():
    migration = (ROOT / "supabase/migrations/20260602_fred_result_dedup.sql").read_text()

    assert "metadata ? 'fred_fencer_key'" in migration


def test_collect_result_rows_matches_usa_fencers_by_id_then_name_country():
    from scrape_fred import build_fencer_index, collect_result_rows, group_csv_rows, parse_csv_results, parse_event_cards

    fencer_index = build_fencer_index(
        [
            {
                "id": "fencer-by-usfa",
                "name": "Someone Else",
                "country": "United States",
                "metadata": {"usafencing_id": "100313729"},
            },
            {
                "id": "fencer-by-name",
                "name": "Sandra Marchant",
                "country": "United States",
                "metadata": {},
            },
            {
                "id": "wrong-country",
                "name": "Alex Kim",
                "country": "Canada",
                "metadata": {},
            },
        ]
    )
    grouped = group_csv_rows(parse_csv_results(RESULTS_CSV), parse_event_cards(EVENT_CARDS_HTML))
    rows, unmatched = collect_result_rows(
        grouped,
        {
            "fred:eb05099a-882e-4852-8e34-c8a4f335b35d": 101,
            "fred:b433ec16-26f2-4db9-88c5-1a96f8d29585": 102,
        },
        fencer_index,
    )

    kira = next(row for row in rows if row["name"] == "Kira Hansen")
    sandra = next(row for row in rows if row["name"] == "Sandra Marchant")
    alex = next(row for row in rows if row["name"] == "Alex Kim")
    assert kira["fencer_id"] == "fencer-by-usfa"
    assert kira["fie_fencer_id"] is None  # INTEGER column; FRED key stored in metadata
    assert kira["metadata"]["fred_fencer_key"] == "fred:usfa:100313729"
    assert kira["metadata"]["match_method"] == "usa_fencing_id"
    assert sandra["fencer_id"] == "fencer-by-name"
    assert sandra["metadata"]["match_method"] == "exact_name_country"
    assert alex["fencer_id"] is None
    assert alex["nationality"] == "United States"
    assert unmatched == ["Alex Kim"]


def test_upserts_use_source_id_and_result_conflict_keys(monkeypatch):
    import scrape_fred

    fake = FakeSupabase()
    fake.select_data["fs_tournaments"] = [
        {"id": 101, "source_id": "fred:eb05099a-882e-4852-8e34-c8a4f335b35d"}
    ]
    monkeypatch.setattr(scrape_fred, "supabase", fake)

    tournament_ids = scrape_fred.upsert_tournaments(
        [{"source_id": "fred:eb05099a-882e-4852-8e34-c8a4f335b35d", "name": "January NAC"}]
    )
    scrape_fred.upsert_results(
        [
            {
                "tournament_id": 101,
                "fie_fencer_id": "fred:usfa:100313729",
                "name": "Kira Hansen",
                "rank": 1,
            }
        ]
    )

    tournament_upsert = fake.operations[0]
    result_upsert = fake.operations[-1]
    assert tournament_ids == {"fred:eb05099a-882e-4852-8e34-c8a4f335b35d": 101}
    assert tournament_upsert["table"] == "fs_tournaments"
    assert tournament_upsert["action"] == "upsert"
    assert tournament_upsert["kwargs"] == {"on_conflict": "source_id"}
    assert result_upsert["table"] == "fs_results"
    assert result_upsert["action"] == "upsert"
    assert result_upsert["kwargs"] == {"on_conflict": "tournament_id,name"}
