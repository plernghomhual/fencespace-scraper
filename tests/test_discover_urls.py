import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import discover_competition_urls as discover


class FakeResponse:
    def __init__(self, status_code=200, url="", json_data=None, text=""):
        self.status_code = status_code
        self.url = url
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.post_responses.pop(0)


class FakeNotProxy:
    def __init__(self, table):
        self.table = table

    def is_(self, column, value):
        self.table.ops.append(("not_is", column, value))
        return self.table


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.ops = []
        self.payload = None
        self.not_ = FakeNotProxy(self)

    def select(self, columns):
        self.ops.append(("select", columns))
        return self

    def is_(self, column, value):
        self.ops.append(("is", column, value))
        return self

    def eq(self, column, value):
        self.ops.append(("eq", column, value))
        if self.payload is not None:
            self.client.updates.append((self.name, column, value, self.payload))
        return self

    def update(self, payload):
        self.payload = payload
        self.ops.append(("update", payload))
        return self

    def range(self, start, end):
        self.ops.append(("range", start, end))
        return self

    def execute(self):
        self.client.tables.append((self.name, list(self.ops)))
        data = self.client.next_query_data() if self.payload is None else []
        return type("Result", (), {"data": data})()


class FakeClient:
    def __init__(self, query_data=None, query_pages=None):
        self.query_data = list(query_data or [])
        self.query_pages = list(query_pages) if query_pages is not None else None
        self.tables = []
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)

    def next_query_data(self):
        if self.query_pages is not None:
            return self.query_pages.pop(0)
        return self.query_data


class FakeRunLogger:
    def __init__(self):
        self.started = False
        self.completed = None
        self.error_message = None

    def start(self):
        self.started = True
        return self

    def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
        self.completed = {
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "metadata": metadata,
        }

    def error(self, exc_str):
        self.error_message = exc_str


def test_extract_competition_url_id_accepts_plain_and_season_urls():
    assert discover.extract_competition_url_id("https://fie.org/competitions/387") == "387"
    assert discover.extract_competition_url_id("https://fie.org/competitions/2024/387") == "387"
    assert discover.extract_competition_url_id("https://fie.org/competitions/2024/387?tab=results") == "387"
    assert discover.extract_competition_url_id("https://fie.org/competitions/not-a-number") is None


def test_fetch_pending_tournaments_queries_only_missing_fie_result_rows():
    rows = [{"id": "t1", "fie_id": 387, "has_results": True, "competition_url_id": None}]
    client = FakeClient(query_data=rows)

    result = discover.fetch_pending_tournaments(client)

    assert result == rows
    assert client.tables == [
        (
            "fs_tournaments",
            [
                ("select", "id,fie_id,name,season,weapon,gender,start_date"),
                ("is", "competition_url_id", "null"),
                ("not_is", "fie_id", "null"),
                ("eq", "has_results", True),
                ("range", 0, 999),
            ],
        )
    ]


def test_fetch_pending_tournaments_paginates_all_missing_rows():
    client = FakeClient(
        query_pages=[
            [
                {"id": "t1", "fie_id": 1},
                {"id": "t2", "fie_id": 2},
            ],
            [{"id": "t3", "fie_id": 3}],
        ]
    )

    result = discover.fetch_pending_tournaments(client, page_size=2)

    assert [row["id"] for row in result] == ["t1", "t2", "t3"]
    assert client.tables[0][1][-1] == ("range", 0, 1)
    assert client.tables[1][1][-1] == ("range", 2, 3)


def test_rate_limiter_waits_before_second_request():
    times = iter([10.0, 10.25])
    slept: list[Any] = []
    limiter = discover.RateLimiter(
        min_interval=1.0,
        time_func=lambda: next(times),
        sleep_func=slept.append,
    )

    limiter.wait()
    limiter.wait()

    assert slept == [0.75]


def test_process_tournaments_updates_url_id_from_detail_page():
    client = FakeClient()
    session = FakeSession(
        get_responses=[
            FakeResponse(200, "https://fie.org/competitions/2024/387"),
        ]
    )
    tournaments = [
        {
            "id": "t1",
            "fie_id": 387,
            "season": "2024",
            "name": "Grand Prix du Qatar",
            "weapon": "Epee",
            "gender": "Men",
            "start_date": "2024-01-30",
        }
    ]

    result = discover.process_tournaments(client, session, tournaments, rate_limiter=discover.NoopRateLimiter())

    assert result == discover.DiscoveryResult(written=1, failed=0, skipped=0)
    assert client.updates == [("fs_tournaments", "id", "t1", {"competition_url_id": "387"})]
    assert session.calls == [
        ("GET", "https://fie.org/competitions/2024/387", {"allow_redirects": True, "timeout": 20})
    ]


def test_process_tournaments_falls_back_to_search_then_detail_url():
    client = FakeClient()
    session = FakeSession(
        get_responses=[
            FakeResponse(404, "https://fie.org/competitions/2024/99999"),
            FakeResponse(200, "https://fie.org/competitions/2024/387"),
        ],
        post_responses=[
            FakeResponse(
                200,
                "https://fie.org/competitions/search",
                {
                    "items": [
                        {
                            "competitionId": 387,
                            "name": "Grand Prix du Qatar",
                            "startDate": "30-01-2024",
                            "weapon": "epee",
                            "gender": "men",
                            "category": "senior",
                            "hasResults": 0,
                        }
                    ],
                    "pageSize": 300,
                },
            )
        ],
    )
    tournaments = [
        {
            "id": "t1",
            "fie_id": 99999,
            "season": 2024,
            "name": "Grand Prix du Qatar",
            "weapon": "Epee",
            "gender": "Men",
            "start_date": "2024-01-30",
        }
    ]

    result = discover.process_tournaments(client, session, tournaments, rate_limiter=discover.NoopRateLimiter())

    assert result == discover.DiscoveryResult(written=1, failed=0, skipped=0)
    assert client.updates == [("fs_tournaments", "id", "t1", {"competition_url_id": "387"})]
    assert session.calls[0][0:2] == ("GET", "https://fie.org/competitions/2024/99999")
    assert session.calls[1][0:2] == ("POST", "https://fie.org/competitions/search")
    assert session.calls[2][0:2] == ("GET", "https://fie.org/competitions/2024/387")
    assert session.calls[1][2]["json"]["fromDate"] == "2024-01-01"
    assert session.calls[1][2]["json"]["toDate"] == "2024-01-31"


def test_main_logs_counts_and_writes_state(monkeypatch):
    client = FakeClient(
        query_data=[
            {
                "id": "t1",
                "fie_id": 387,
                "season": "2024",
                "name": "Grand Prix du Qatar",
                "weapon": "Epee",
                "gender": "Men",
                "start_date": "2024-01-30",
            }
        ]
    )
    session = FakeSession(
        get_responses=[
            FakeResponse(200, "https://fie.org/competitions/2024/387"),
        ]
    )
    logger = FakeRunLogger()
    states = []
    monkeypatch.setattr(discover, "get_state", lambda source, key: {"last_completed_at": "old"})
    monkeypatch.setattr(discover, "set_state", lambda source, key, value: states.append((source, key, value)))

    result = discover.main(
        client=client,
        session=session,
        logger_factory=lambda _: logger,
        rate_limiter=discover.NoopRateLimiter(),
    )

    assert result == discover.DiscoveryResult(written=1, failed=0, skipped=0)
    assert logger.started is True
    completed = cast(dict[str, Any], logger.completed)
    assert completed["written"] == 1
    assert completed["failed"] == 0
    assert completed["skipped"] == 0
    assert states[0][0:2] == (discover.SOURCE, "summary")
    assert states[0][2]["written"] == 1
    assert states[0][2]["previous_completed_at"] == "old"
