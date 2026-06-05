from typing import Any, cast
import json
from datetime import date, datetime, timezone


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, html_pages):
        self.html_pages = list(html_pages)
        self.urls = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        return FakeResponse(self.html_pages.pop(0))


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.filters = []
        self.in_values = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def upsert(self, rows, on_conflict=None):
        self.operation = "upsert"
        self.payload = rows
        self.client.upserts.append(
            {"table": self.name, "rows": rows, "on_conflict": on_conflict}
        )
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        self.client.filters.append((self.name, "eq", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        self.client.filters.append((self.name, "lte", column, value))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        self.client.filters.append((self.name, "gte", column, value))
        return self

    def in_(self, column, values):
        self.in_values = (column, set(values))
        self.client.filters.append((self.name, "in", column, tuple(values)))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        self.filters.append(("not_is", column, value))
        self.client.filters.append((self.name, "not_is", column, value))
        return self

    def execute(self):
        if self.operation == "select" and self.name == "fs_tournaments":
            return FakeResult(self.client.tournaments)
        if self.operation == "select" and self.name == "fs_fencers":
            column, values = cast(tuple[str, list[Any]], self.in_values)
            rows = [row for row in self.client.fencers if row.get(column) in values]
            return FakeResult(rows)
        if self.operation == "update" and self.name == "fs_tournaments":
            self.client.updates.append(
                {"table": self.name, "payload": self.payload, "filters": self.filters}
            )
            return FakeResult([])
        if self.operation == "upsert":
            return FakeResult([])
        raise AssertionError(f"unexpected {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, tournaments, fencers=None):
        self.tournaments = tournaments
        self.fencers = fencers or []
        self.selects = []
        self.filters = []
        self.upserts = []
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)


def competition_html(result_rows, tableau_bouts):
    return f"""
    <html><body><script>
    window._competition = {json.dumps({"competitionId": 9001, "tableauList": [
      {"suiteTableId": "main", "tableId": "64", "name": "Table of 64"}
    ]})};
    window._results = {json.dumps({"rows": result_rows})};
    window._tableau = {json.dumps([{"suiteTableId": "main", "rounds": {"64": tableau_bouts}}])};
    </script></body></html>
    """


def result_rows(*rows):
    return [
        {
            "rank": str(rank),
            "name": name,
            "fencerId": fie_id,
            "nationality": country,
            "country": country,
            "victory": "5",
            "matches": "6",
            "td": "30",
            "tr": "20",
            "diff": "10",
        }
        for rank, name, fie_id, country in rows
    ]


def tableau_bout(id_a, id_b, score_a, score_b, winner):
    return {
        "fencer1": {"fencerId": id_a, "score": score_a, "isWinner": winner == id_a},
        "fencer2": {"fencerId": id_b, "score": score_b, "isWinner": winner == id_b},
    }


def test_watcher_upserts_only_new_results_and_bouts_between_checks(monkeypatch):
    import watch_live_results

    tournament = {
        "id": "t-1",
        "name": "Live Grand Prix",
        "season": 2026,
        "start_date": "2026-01-27",
        "end_date": "2026-01-29",
        "competition_url_id": "9001",
    }
    client = FakeSupabase(
        tournaments=[tournament],
        fencers=[
            {"id": "fencer-100", "fie_id": "100"},
            {"id": "fencer-200", "fie_id": "200"},
            {"id": "fencer-300", "fie_id": "300"},
        ],
    )
    first_html = competition_html(
        result_rows((1, "LEE KIEFER", 100, "USA"), (2, "ALICE VOLPI", 200, "ITA")),
        [tableau_bout(100, 200, 15, 12, 100)],
    )
    second_html = competition_html(
        result_rows(
            (1, "LEE KIEFER", 100, "USA"),
            (2, "ALICE VOLPI", 200, "ITA"),
            (3, "MARIA SANTOS", 300, "BRA"),
        ),
        [
            tableau_bout(100, 200, 15, 12, 100),
            tableau_bout(300, 200, 15, 14, 300),
        ],
    )
    session = FakeSession([first_html, second_html])
    state: dict[Any, Any] = {}

    monkeypatch.setattr(
        watch_live_results,
        "get_state",
        lambda source, key: state.get((source, key)),
    )
    monkeypatch.setattr(
        watch_live_results,
        "set_state",
        lambda source, key, value: state.__setitem__((source, key), value),
    )

    first = watch_live_results.watch_live_results(
        client=client,
        session=session,
        today=date(2026, 1, 28),
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
    )
    second = watch_live_results.watch_live_results(
        client=client,
        session=session,
        today=date(2026, 1, 28),
        now=datetime(2026, 1, 28, 12, 15, tzinfo=timezone.utc),
        log_run=False,
    )

    result_upserts = [call for call in client.upserts if call["table"] == "fs_results"]
    bout_upserts = [call for call in client.upserts if call["table"] == "fs_bouts"]

    assert first["tournaments_checked"] == 1
    assert first["new_results"] == 2
    assert first["new_bouts"] == 1
    assert second["tournaments_checked"] == 1
    assert second["new_results"] == 1
    assert second["new_bouts"] == 1
    assert len(result_upserts) == 2
    assert len(result_upserts[0]["rows"]) == 2
    assert result_upserts[0]["on_conflict"] == "tournament_id,fie_fencer_id"
    assert len(result_upserts[1]["rows"]) == 1
    assert result_upserts[1]["rows"][0]["name"] == "Maria Santos"
    assert len(bout_upserts) == 2
    assert len(bout_upserts[0]["rows"]) == 1
    assert bout_upserts[0]["on_conflict"] == "id"
    assert len(bout_upserts[1]["rows"]) == 1
    assert state[("live_watcher", "last_checked_t-1")].startswith("2026-01-28T12:15:00")
    assert len(state[("live_watcher", "result_hashes_t-1")]) == 3
    assert len(state[("live_watcher", "bout_hashes_t-1")]) == 2
    assert "https://fie.org/competitions/2026/9001" in session.urls


def test_watcher_exits_quickly_when_no_active_tournaments():
    import watch_live_results

    client = FakeSupabase(tournaments=[])
    session = FakeSession([])

    summary = watch_live_results.watch_live_results(
        client=client,
        session=session,
        today=date(2026, 1, 28),
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
    )

    assert summary == {
        "tournaments_checked": 0,
        "new_results": 0,
        "new_bouts": 0,
        "tournament_ids": [],
        "failed": 0,
        "skipped": 0,
    }
    assert session.urls == []
    assert client.upserts == []
    assert ("fs_tournaments", "lte", "start_date", "2026-01-28") in client.filters
    assert ("fs_tournaments", "gte", "end_date", "2026-01-26") in client.filters
    assert ("fs_tournaments", "not_is", "competition_url_id", "null") in client.filters
