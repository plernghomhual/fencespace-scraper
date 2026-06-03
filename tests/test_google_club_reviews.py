import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.client.upserts.append(
            {"table": self.table_name, "rows": rows, "on_conflict": on_conflict}
        )
        return self

    def execute(self):
        rows = self.client.tables.get(self.table_name, [])
        if self.end is None:
            return FakeResponse(rows)
        return FakeResponse(rows[self.start : self.end + 1])


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_no_key_skips_google_without_http_call(capsys):
    from scrape_google_club_reviews import scrape_google_club_reviews

    class Session:
        def get(self, *args, **kwargs):
            raise AssertionError("HTTP should not be called when MAPS_API_KEY is missing")

    client = FakeClient(
        {
            "fs_club_reviews": [
                {
                    "club_name": "massialas-foundation",
                    "normalized_club_name": "massialas foundation",
                    "city": "San Francisco",
                    "country": "USA",
                    "metadata": {},
                    "source": "other_reviews",
                }
            ],
            "fs_club_rankings": [
                {
                    "club": "MASSIALAS FOUNDATION",
                    "city": "San Francisco",
                    "country": "USA",
                    "metadata": {},
                }
            ],
            "fs_fencers": [
                {
                    "club": "Massialas Foundation",
                    "city": "San Francisco",
                    "country": "USA",
                    "metadata": {},
                }
            ],
        }
    )

    summary = scrape_google_club_reviews(
        client,
        maps_api_key=None,
        session=Session(),
        request_delay=0,
        page_size=25,
    )

    assert summary == {
        "clubs_seen": 1,
        "review_rows": 0,
        "written": 0,
        "failed": 0,
        "skipped": 1,
    }
    assert client.upserts == []
    assert {table_name for table_name, _columns in client.selects} == {
        "fs_club_reviews",
        "fs_club_rankings",
        "fs_fencers",
    }
    assert "MAPS_API_KEY not set; skipping Google Places lookups" in capsys.readouterr().out


def test_parse_google_places_response_extracts_rating_count_url_and_metadata():
    from scrape_google_club_reviews import ClubCandidate, parse_google_places_response

    club = ClubCandidate(
        name="Massialas Foundation",
        city="San Francisco",
        country="USA",
        normalized_name="massialas foundation",
        source_tables=("fs_fencers",),
    )
    search_payload = {
        "status": "OK",
        "results": [
            {
                "name": "Massialas Foundation",
                "rating": 4.8,
                "user_ratings_total": 87,
                "place_id": "ChIJ-fencing",
                "formatted_address": "1590 Bryant St, San Francisco, CA 94103, USA",
                "business_status": "OPERATIONAL",
                "types": ["point_of_interest", "establishment"],
            }
        ],
    }
    details_payload = {
        "status": "OK",
        "result": {
            "name": "Massialas Foundation",
            "rating": "4.9",
            "user_ratings_total": "91",
            "place_id": "ChIJ-fencing",
            "url": "https://maps.google.com/?cid=123",
            "formatted_address": "1590 Bryant St, San Francisco, CA 94103, USA",
            "business_status": "OPERATIONAL",
            "types": ["point_of_interest", "establishment"],
            "website": "https://mteamfencing.com/",
            "international_phone_number": "+1 415-555-0100",
            "geometry": {"location": {"lat": 37.767, "lng": -122.411}},
        },
    }

    review = parse_google_places_response(
        search_payload,
        club,
        search_query="fencing club Massialas Foundation San Francisco USA",
        details_payload=details_payload,
    )

    assert review == {
        "source": "google_maps",
        "rating": 4.9,
        "review_count": 91,
        "review_summary": "Google Maps rating 4.9 from 91 reviews",
        "source_url": "https://maps.google.com/?cid=123",
        "metadata": {
            "business_status": "OPERATIONAL",
            "formatted_address": "1590 Bryant St, San Francisco, CA 94103, USA",
            "google_name": "Massialas Foundation",
            "international_phone_number": "+1 415-555-0100",
            "location": {"lat": 37.767, "lng": -122.411},
            "match_score": 5,
            "place_id": "ChIJ-fencing",
            "search_query": "fencing club Massialas Foundation San Francisco USA",
            "types": ["point_of_interest", "establishment"],
            "website": "https://mteamfencing.com/",
        },
    }


def test_build_review_row_and_upsert_are_source_specific_and_idempotent():
    from scrape_google_club_reviews import (
        ClubCandidate,
        build_review_row,
        upsert_review_rows,
    )

    club = ClubCandidate(
        name="Massialas Foundation",
        city="San Francisco",
        country="USA",
        normalized_name="massialas foundation",
        source_tables=("fs_club_reviews", "fs_fencers"),
    )
    review = {
        "source": "google_maps",
        "rating": 4.8,
        "review_count": 87,
        "review_summary": "Google Maps rating 4.8 from 87 reviews",
        "source_url": "https://www.google.com/maps/place/?q=place_id:ChIJ-fencing",
        "metadata": {"place_id": "ChIJ-fencing"},
    }

    first = build_review_row(club, review, scraped_at=NOW)
    second = build_review_row(club, review, scraped_at=NOW)
    client = FakeClient({})

    assert first == second
    assert first["source"] == "google_maps"
    assert first["metadata"]["place_id"] == "ChIJ-fencing"
    assert first["metadata"]["source_tables"] == ["fs_club_reviews", "fs_fencers"]
    assert upsert_review_rows(client, [first], batch_size=10) == 1
    assert client.upserts == [
        {
            "table": "fs_club_reviews",
            "rows": [first],
            "on_conflict": "normalized_club_name,city,country,source",
        }
    ]


def test_ambiguous_place_match_returns_none_and_logs(capsys):
    from scrape_google_club_reviews import ClubCandidate, parse_google_places_response

    club = ClubCandidate(
        name="Blade Club",
        city="Boston",
        country="USA",
        normalized_name="blade club",
    )
    payload = {
        "status": "OK",
        "results": [
            {
                "name": "Blade Club",
                "rating": 4.6,
                "user_ratings_total": 11,
                "place_id": "place-a",
                "formatted_address": "10 First St, Boston, MA, USA",
            },
            {
                "name": "Blade Club",
                "rating": 4.7,
                "user_ratings_total": 14,
                "place_id": "place-b",
                "formatted_address": "20 Second St, Boston, MA, USA",
            },
        ],
    }

    review = parse_google_places_response(
        payload,
        club,
        search_query="fencing club Blade Club Boston USA",
    )

    assert review is None
    assert "Ambiguous Google Places match for Blade Club" in capsys.readouterr().out
