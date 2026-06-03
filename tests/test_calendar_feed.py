import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TOURNAMENT_ROWS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "source_id": "fie:2026:12345",
        "name": "Cairo World Cup, Senior; Men's Epee",
        "season": 2026,
        "type": "FIE",
        "country": "Egypt",
        "location": "Cairo",
        "weapon": "Epee",
        "gender": "Men",
        "category": "Senior",
        "start_date": "2026-02-13",
        "end_date": "2026-02-15",
        "updated_at": "2026-01-10T09:30:00+00:00",
        "metadata": {"source": "fie", "competition_url_id": "12345"},
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "source_id": "askfred:event:paris-foil",
        "name": "Paris Foil Open",
        "season": 2026,
        "type": "AskFRED",
        "country": "France",
        "location": "Paris",
        "weapon": "Foil",
        "gender": "Women",
        "category": "Senior",
        "start_date": "2026-03-01",
        "end_date": "2026-03-01",
        "metadata": {"source": "askfred"},
    },
]


def test_ics_generation_uses_stable_uid_and_all_day_dates():
    import calendar_feed

    filters = calendar_feed.CalendarFeedFilters(
        federation="FIE",
        country="egypt",
        weapon="Epee",
        category="Senior",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        limit=50,
    )

    ics = calendar_feed.generate_ics_feed(
        TOURNAMENT_ROWS,
        filters=filters,
        generated_at=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
        calendar_name="FenceSpace FIE Epee",
    )

    assert ics.endswith("\r\n")
    assert "BEGIN:VCALENDAR\r\n" in ics
    assert "VERSION:2.0\r\n" in ics
    assert "BEGIN:VEVENT\r\n" in ics
    assert "UID:fencespace-9cb3c3872cb018e9340f1de9d210c8f1@calendar.fencespace.app\r\n" in ics
    assert "DTSTAMP:20260602T120000Z\r\n" in ics
    assert "DTSTART;VALUE=DATE:20260213\r\n" in ics
    assert "DTEND;VALUE=DATE:20260216\r\n" in ics
    assert "LAST-MODIFIED:20260110T093000Z\r\n" in ics
    assert "SUMMARY:Cairo World Cup\\, Senior\\; Men's Epee\r\n" in ics
    assert "LOCATION:Cairo\\, Egypt\r\n" in ics
    assert "CATEGORIES:FIE,Epee,Senior\r\n" in ics
    assert "Paris Foil Open" not in ics

    renamed = [dict(TOURNAMENT_ROWS[0], name="Renamed Cairo World Cup")]
    renamed_ics = calendar_feed.generate_ics_feed(
        renamed,
        filters=filters,
        generated_at=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )
    assert "UID:fencespace-9cb3c3872cb018e9340f1de9d210c8f1@calendar.fencespace.app\r\n" in renamed_ics


def test_filter_validation_normalizes_safe_values_and_caps_limit():
    import calendar_feed

    filters = calendar_feed.validate_calendar_filters(
        federation=" fie ",
        country=" egypt ",
        weapon="épée",
        category=" senior ",
        date_from="2026-01-01",
        date_to="2026-12-31",
        timezone_name="America/New_York",
        limit=99999,
    )

    assert filters.federation == "FIE"
    assert filters.country == "Egypt"
    assert filters.weapon == "Epee"
    assert filters.category == "Senior"
    assert filters.date_from == date(2026, 1, 1)
    assert filters.date_to == date(2026, 12, 31)
    assert filters.timezone_name == "America/New_York"
    assert filters.limit == calendar_feed.MAX_RESULT_LIMIT


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"weapon": "Longsword"}, "weapon"),
        ({"date_from": "2026-12-31", "date_to": "2026-01-01"}, "date_from"),
        ({"date_from": "31-12-2026"}, "YYYY-MM-DD"),
        ({"timezone_name": "Mars/Base"}, "timezone"),
        ({"country": "US\nA"}, "control"),
        ({"limit": 0}, "limit"),
    ],
)
def test_filter_validation_rejects_unsafe_values(kwargs, message):
    import calendar_feed

    with pytest.raises(ValueError, match=message):
        calendar_feed.validate_calendar_filters(**kwargs)


def test_empty_feed_is_valid_calendar_without_events():
    import calendar_feed

    ics = calendar_feed.generate_ics_feed(
        [],
        filters=calendar_feed.validate_calendar_filters(country="USA"),
        generated_at=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
        calendar_name="FenceSpace Empty",
    )

    assert "BEGIN:VCALENDAR\r\n" in ics
    assert "X-WR-CALNAME:FenceSpace Empty\r\n" in ics
    assert "BEGIN:VEVENT" not in ics
    assert ics.endswith("END:VCALENDAR\r\n")


def test_generation_caps_events_and_skips_rows_without_start_dates():
    import calendar_feed

    start = date(2026, 1, 1)
    rows = [
        {
            "source_id": f"fie:cap:{index}",
            "name": f"Event {index}",
            "type": "FIE",
            "country": "USA",
            "weapon": "Sabre",
            "category": "Senior",
            "start_date": (start + timedelta(days=index)).isoformat(),
            "end_date": (start + timedelta(days=index)).isoformat(),
        }
        for index in range(calendar_feed.MAX_RESULT_LIMIT + 25)
    ]
    rows.append(
        {
            "source_id": "fie:cap:no-date",
            "name": "No Date Event",
            "type": "FIE",
            "country": "USA",
            "weapon": "Sabre",
            "category": "Senior",
        }
    )

    filters = calendar_feed.validate_calendar_filters(federation="FIE", limit=99999)
    ics = calendar_feed.generate_ics_feed(rows, filters=filters)

    assert ics.count("BEGIN:VEVENT\r\n") == calendar_feed.MAX_RESULT_LIMIT
    assert "No Date Event" not in ics


def test_filtering_skips_malformed_row_values_instead_of_crashing():
    import calendar_feed

    rows = [
        {
            "source_id": "bad:weapon",
            "name": "Bad Weapon Event",
            "type": "FIE",
            "country": "USA",
            "weapon": "Longsword",
            "category": "Senior",
            "start_date": "2026-02-01",
            "end_date": "2026-02-01",
        },
        {
            "source_id": "good:epee",
            "name": "Good Epee Event",
            "type": "FIE",
            "country": "USA",
            "weapon": "Epee",
            "category": "Senior",
            "start_date": "2026-02-02",
            "end_date": "2026-02-02",
        },
    ]

    filters = calendar_feed.validate_calendar_filters(federation="FIE", weapon="Epee")
    ics = calendar_feed.generate_ics_feed(rows, filters=filters)

    assert "Good Epee Event" in ics
    assert "Bad Weapon Event" not in ics


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTournamentQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.gte_filters = []
        self.lte_filters = []
        self.orders = []
        self.range_args = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def gte(self, column, value):
        self.gte_filters.append((column, value))
        return self

    def lte(self, column, value):
        self.lte_filters.append((column, value))
        return self

    def order(self, column):
        self.orders.append(column)
        return self

    def range(self, start, end):
        self.range_args = (start, end)
        return self

    def execute(self):
        rows = list(self.rows)
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        for column, value in self.gte_filters:
            rows = [row for row in rows if row.get(column) and row.get(column) >= value]
        for column, value in self.lte_filters:
            rows = [row for row in rows if row.get(column) and row.get(column) <= value]
        if self.range_args:
            start, end = self.range_args
            rows = rows[start : end + 1]
        return FakeResponse(rows)


class FakeSupabaseClient:
    def __init__(self, rows):
        self.query = FakeTournamentQuery(rows)
        self.tables = []

    def table(self, table_name):
        self.tables.append(table_name)
        return self.query


def test_api_compatible_client_helper_applies_filters_and_capped_range():
    import calendar_feed

    fake = FakeSupabaseClient(TOURNAMENT_ROWS)
    ics = calendar_feed.generate_ics_feed_from_client(
        fake,
        federation="FIE",
        country="Egypt",
        weapon="Epee",
        category="Senior",
        date_from="2026-01-01",
        date_to="2026-12-31",
        limit=99999,
        generated_at=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert fake.tables == ["fs_tournaments"]
    assert fake.query.selected == calendar_feed.TOURNAMENT_SELECT_COLUMNS
    assert ("type", "FIE") in fake.query.filters
    assert ("country", "Egypt") in fake.query.filters
    assert ("weapon", "Epee") in fake.query.filters
    assert ("category", "Senior") in fake.query.filters
    assert fake.query.gte_filters == [("start_date", "2026-01-01")]
    assert fake.query.lte_filters == [("start_date", "2026-12-31")]
    assert fake.query.orders == ["start_date"]
    assert fake.query.range_args == (0, calendar_feed.MAX_RESULT_LIMIT - 1)
    assert "Cairo World Cup" in ics
    assert "Paris Foil Open" not in ics


def test_cli_generates_ics_from_input_json(tmp_path, capsys):
    import calendar_feed

    input_path = tmp_path / "tournaments.json"
    input_path.write_text(json.dumps(TOURNAMENT_ROWS))

    status = calendar_feed.main(
        [
            "--input",
            str(input_path),
            "--federation",
            "FIE",
            "--weapon",
            "Epee",
            "--from-date",
            "2026-01-01",
            "--to-date",
            "2026-12-31",
        ]
    )

    captured = capsys.readouterr()
    assert status == 0
    assert captured.err == ""
    assert "BEGIN:VCALENDAR\r\n" in captured.out
    assert "UID:fencespace-9cb3c3872cb018e9340f1de9d210c8f1@calendar.fencespace.app\r\n" in captured.out
    assert "Paris Foil Open" not in captured.out
