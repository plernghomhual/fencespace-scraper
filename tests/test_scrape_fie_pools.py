import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import scrape_fie_pools as pools

NORMAL_POOL_HTML = """
<html><body>
<script>
window._competition = {"competitionId":147,"name":"Coupe du Monde","type":"individual"};
window._pools = {
  "rounds": [
    {
      "roundId": "pools",
      "name": "Pools",
      "pools": [
        {
          "poolId": 1,
          "rows": [
            {
              "fencerId": "1001",
              "lastName": "ALPHA",
              "firstName": "Alice",
              "country": "USA",
              "matches": [
                null,
                {"score": "V5", "v": true, "boutOrder": 1},
                {"score": "D4", "v": false, "boutOrder": 3}
              ]
            },
            {
              "fencerId": "1002",
              "name": "BETA Bob",
              "nationality": "FRA",
              "matches": [
                {"score": "D2", "v": false, "boutOrder": 1},
                null,
                {"score": "V5", "v": true, "boutOrder": 2, "priority": true}
              ]
            },
            {
              "id": "1003",
              "fullName": "GAMMA Cara",
              "countryCode": "ITA",
              "matches": [
                {"score": "V5", "v": true, "boutOrder": 3},
                {"score": "D3", "v": false, "boutOrder": 2},
                null
              ]
            }
          ]
        }
      ]
    }
  ]
};
</script>
</body></html>
"""


WITHDRAWAL_POOL_HTML = """
<script>
window._competition = {"competitionId":160,"name":"Coupe du Monde","type":"individual"};
window._poules = [
  {
    "id": "A",
    "name": "Poule 1",
    "rows": [
      {
        "fencer": {"id": "2001", "name": "WITHDRAWN Fencer", "country": "GER"},
        "matches": [null, {"score": "A", "v": false, "withdrawn": true, "order": 4}]
      },
      {
        "fencer": {"id": "2002", "name": "ACTIVE Fencer", "country": "HUN"},
        "matches": [{"score": "V", "v": true, "order": 4}, null]
      }
    ]
  }
];
</script>
"""


INCOMPLETE_POOL_HTML = """
<script>
window._competition = {"type":"individual"};
window._pools = {"pools": [
  {"poolId": 2, "rows": [
    {"fencerId": "3001", "name": "ONE A", "country": "USA",
     "matches": [null, {"score": "V5", "v": true, "boutOrder": 1}, {"score": "", "v": null, "boutOrder": 2}]},
    {"fencerId": "3002", "name": "TWO B", "country": "CAN",
     "matches": [null, null, {"score": null, "v": null, "boutOrder": 3}]},
    {"fencerId": "3003", "name": "THREE C", "country": "MEX",
     "matches": [{"score": "", "v": null, "boutOrder": 2}, {"score": "", "v": null, "boutOrder": 3}, null]}
  ]}
]};
</script>
"""


TEAM_POOL_HTML = """
<script>
window._competition = {"competitionId":827,"name":"Coupe du Monde par equipes","type":"team"};
window._pools = {"pools": [
  {"poolId": 1, "rows": [
    {"fencerId": "4001", "name": "SHOULD Skip", "country": "USA", "matches": [null, {"score": "V5", "v": true}]},
    {"fencerId": "4002", "name": "ALSO Skip", "country": "FRA", "matches": [{"score": "D1", "v": false}, null]}
  ]}
]};
</script>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.on_conflict = None
        self.filters = []
        self.in_filter = None

    def select(self, columns):
        self.action = "select"
        self.columns = columns
        return self

    def in_(self, column, values):
        self.in_filter = (column, list(values))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def limit(self, _count):
        return self

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.name == "fs_fencers" and self.action == "select":
            if self.in_filter:
                ids = set(self.in_filter[1])
                return FakeResult(
                    [
                        row
                        for row in self.client.fencers_by_fie_id
                        if str(row.get("fie_id")) in ids
                    ]
                )
            filters = {(op, column): value for op, column, value in self.filters}
            name = filters.get(("ilike", "name"))
            country = filters.get(("eq", "country"))
            row = self.client.fencers_by_name_country.get((name, country))
            return FakeResult([row] if row else [])
        if self.action == "upsert":
            self.client.upserts.append((self.name, self.payload, self.on_conflict))
            return FakeResult(self.payload if isinstance(self.payload, list) else [self.payload])
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.fencers_by_fie_id = [
            {"id": "uuid-alpha", "fie_id": "1001", "name": "Different Name", "country": "USA"},
            {"id": "uuid-beta", "fie_id": "1002", "name": "BETA Bob", "country": "FRA"},
            {"id": "uuid-active", "fie_id": "2002", "name": "ACTIVE Fencer", "country": "HUN"},
        ]
        self.fencers_by_name_country = {
            ("GAMMA Cara", "ITA"): {"id": "uuid-gamma", "fie_id": None, "name": "GAMMA Cara", "country": "ITA"},
        }
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_normal_pool_fixture_extracts_bout_details():
    bouts = pools.parse_pool_bouts_from_html(
        "tournament-1", NORMAL_POOL_HTML, "https://fie.org/competitions/2026/147"
    )

    assert len(bouts) == 3
    first = bouts[0]
    assert first["pool_round"] == "Pools"
    assert first["poule_number"] == "1"
    assert first["bout_order"] == 1
    assert first["fencer_a_fie_id"] == "1001"
    assert first["fencer_a_name"] == "ALPHA Alice"
    assert first["country_a"] == "USA"
    assert first["fencer_b_fie_id"] == "1002"
    assert first["score_a"] == 5
    assert first["score_b"] == 2
    assert first["winner_fie_id"] == "1001"
    assert first["source_url"] == "https://fie.org/competitions/2026/147"

    priority_bout = next(b for b in bouts if b["fencer_a_fie_id"] == "1002" and b["fencer_b_fie_id"] == "1003")
    assert priority_bout["priority_a"] is True
    assert priority_bout["winner_fie_id"] == "1002"


def test_parse_withdrawal_fixture_keeps_marker_without_inventing_scores():
    bouts = pools.parse_pool_bouts_from_html(
        "tournament-2", WITHDRAWAL_POOL_HTML, "https://www.fie.org/competitions/2026/160"
    )

    assert len(bouts) == 1
    bout = bouts[0]
    assert bout["withdrawal_a"] is True
    assert bout["score_a"] is None
    assert bout["score_b"] is None
    assert bout["winner_fie_id"] == "2002"
    assert bout["bout_order"] == 4


def test_parse_incomplete_scores_skips_scoreless_unresolved_bouts():
    bouts = pools.parse_pool_bouts_from_html(
        "tournament-3", INCOMPLETE_POOL_HTML, "https://fie.org/competitions/2026/999"
    )

    assert len(bouts) == 1
    assert bouts[0]["fencer_a_fie_id"] == "3001"
    assert bouts[0]["score_a"] == 5
    assert bouts[0]["score_b"] is None
    assert bouts[0]["winner_fie_id"] == "3001"


def test_parse_team_event_returns_empty():
    assert pools.parse_pool_bouts_from_html("team-1", TEAM_POOL_HTML, "https://fie.org/competitions/2026/827") == []


def test_bout_rows_for_db_are_fs_bouts_compatible_and_deduped():
    client = FakeClient()
    parsed = pools.parse_pool_bouts_from_html(
        "tournament-1", NORMAL_POOL_HTML, "https://fie.org/competitions/2026/147"
    )

    written, unmatched = pools.write_pool_bouts(client, parsed)

    assert written == 3
    assert unmatched == []
    table, payload, conflict = client.upserts[0]
    assert table == "fs_bouts"
    assert conflict == "id"
    allowed = {"id", "tournament_id", "fencer_a_id", "fencer_b_id", "score_a", "score_b", "round", "winner_id"}
    assert all(set(row) <= allowed for row in payload)
    assert payload[0]["fencer_a_id"] == "uuid-alpha"
    assert payload[0]["fencer_b_id"] == "uuid-beta"
    assert payload[0]["winner_id"] == "uuid-alpha"
    assert not any("source_url" in row or "bout_order" in row for row in payload)


def test_write_pool_bouts_logs_unmatched_names_and_uses_name_country_fallback(capsys):
    client = FakeClient()
    parsed = pools.parse_pool_bouts_from_html(
        "tournament-1", NORMAL_POOL_HTML, "https://fie.org/competitions/2026/147"
    )
    parsed.append(
        {
            **parsed[0],
            "id": pools.make_bout_id("tournament-1", "pool:unmatched"),
            "source_key": "pool:unmatched",
            "fencer_a_fie_id": "9999",
            "fencer_a_name": "MISSING Fencer",
            "country_a": "ESP",
            "fencer_b_fie_id": "1003",
            "fencer_b_name": "GAMMA Cara",
            "country_b": "ITA",
            "winner_fie_id": "1003",
        }
    )

    written, unmatched = pools.write_pool_bouts(client, parsed)

    assert written == 4
    assert unmatched == ["MISSING Fencer (ESP, FIE 9999)"]
    output = capsys.readouterr().out
    assert "Unmatched FIE pool fencers: MISSING Fencer (ESP, FIE 9999)" in output
    last = client.upserts[0][1][-1]
    assert last["fencer_a_id"] is None
    assert last["fencer_b_id"] == "uuid-gamma"
    assert last["winner_id"] == "uuid-gamma"


def test_scrape_fie_pools_records_state_and_run_log(monkeypatch):
    completed = {}
    state_calls = []

    class FakeRunLog:
        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, message):
            completed["error"] = message

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            completed["module"] = self.module
            return FakeRunLog()

    tournaments = [
        {"id": "tournament-1", "name": "Individual", "season": "2026", "competition_url_id": "147", "has_results": True},
        {"id": "team-1", "name": "Team World Cup", "season": "2026", "competition_url_id": "827", "has_results": True},
    ]

    monkeypatch.setattr(pools, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(pools, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(pools, "get_state", lambda source, key: None)
    monkeypatch.setattr(pools, "set_state", lambda source, key, value: state_calls.append((source, key, value)))
    monkeypatch.setattr(pools, "fetch_pool_tournaments", lambda client, limit=None: tournaments[:limit])
    monkeypatch.setattr(
        pools,
        "fetch_competition_page",
        lambda session, tournament: ("https://fie.org/competitions/2026/147", NORMAL_POOL_HTML),
    )
    monkeypatch.setattr(pools, "_fie_limiter", None)
    monkeypatch.setattr(pools.time, "sleep", lambda _seconds: None)

    result = pools.scrape_fie_pools(limit=2)

    assert result["written"] == 3
    assert result["failed"] == 0
    assert result["skipped"] == 1
    assert result["parsed_tournaments"] == 1
    assert completed == {
        "module": "scrape_fie_pools",
        "written": 3,
        "failed": 0,
        "skipped": 1,
    }
    assert state_calls[0][0:2] == ("scrape_fie_pools", "last_run")
    assert state_calls[0][2]["written"] == 3
