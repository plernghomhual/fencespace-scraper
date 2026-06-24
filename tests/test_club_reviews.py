import os
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"


def test_normalize_club_name_strips_common_noise():
    from scrape_club_reviews import normalize_club_name

    assert normalize_club_name("  Fiamme-Oro  ") == "fiamme oro"
    assert normalize_club_name("A.S.D. Fiamme Oro") == "fiamme oro"
    assert normalize_club_name("Club d'Escrime de Levallois") == "club d escrime de levallois"
    assert normalize_club_name("") is None


def test_parse_google_maps_response_extracts_rating_and_review_count():
    from scrape_club_reviews import ClubCandidate, parse_google_maps_response

    club = ClubCandidate(
        name="Massialas Foundation",
        city="San Francisco",
        country="USA",
    )
    payload = {
        "status": "OK",
        "results": [
            {
                "name": "Massialas Foundation",
                "rating": 4.8,
                "user_ratings_total": 87,
                "place_id": "ChIJ-fencing",
                "formatted_address": "1590 Bryant St, San Francisco, CA 94103",
                "business_status": "OPERATIONAL",
                "types": ["point_of_interest", "establishment"],
            }
        ],
    }

    review = parse_google_maps_response(
        payload,
        club,
        search_query="fencing club Massialas Foundation San Francisco",
    )

    assert review == {
        "source": "google_maps",
        "rating": 4.8,
        "review_count": 87,
        "review_summary": "Google Maps rating 4.8 from 87 reviews",
        "source_url": "https://www.google.com/maps/place/?q=place_id:ChIJ-fencing",
        "metadata": {
            "business_status": "OPERATIONAL",
            "formatted_address": "1590 Bryant St, San Francisco, CA 94103",
            "google_name": "Massialas Foundation",
            "place_id": "ChIJ-fencing",
            "search_query": "fencing club Massialas Foundation San Francisco",
            "types": ["point_of_interest", "establishment"],
        },
    }


def test_google_maps_no_key_skips_without_http_call(capsys):
    from scrape_club_reviews import ClubCandidate, query_google_maps_review

    class Session:
        def get(self, *args, **kwargs):
            raise AssertionError("HTTP should not be called when MAPS_API_KEY is missing")

    result = query_google_maps_review(
        ClubCandidate(name="Blade Club", city="Boston", country="USA"),
        maps_api_key=None,
        session=Session(),
    )

    assert result is None
    assert "MAPS_API_KEY not set" in capsys.readouterr().out


def test_forum_parsers_extract_review_thread_mentions():
    from scrape_club_reviews import parse_fencing_net_search_html, parse_reddit_search_response

    reddit = cast(dict[str, Any], parse_reddit_search_response(
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Reviews of Massialas Foundation?",
                            "permalink": "/r/Fencing/comments/abc/reviews/",
                            "num_comments": 12,
                            "score": 9,
                        }
                    }
                ]
            }
        },
        "Massialas Foundation",
    ))
    fencing_net = cast(dict[str, Any], parse_fencing_net_search_html(
        """
        <html><body>
          <a href="/forums/threads/massialas-foundation-review.123/">
            Massialas Foundation review thread
          </a>
          <a href="/forums/threads/unrelated.456/">Unrelated club</a>
        </body></html>
        """,
        "Massialas Foundation",
    ))

    assert reddit["review_count"] == 1
    assert "Reviews of Massialas Foundation?" in reddit["review_summary"]
    assert reddit["metadata"]["threads"][0]["url"] == "https://www.reddit.com/r/Fencing/comments/abc/reviews/"
    assert fencing_net["review_count"] == 1
    assert fencing_net["source_url"] == "https://fencing.net/forums/threads/massialas-foundation-review.123/"


def test_build_review_row_and_upsert_are_idempotent():
    from scrape_club_reviews import (
        ClubCandidate,
        build_review_row,
        upsert_review_rows,
    )

    club = ClubCandidate(name="Massialas Foundation", city="San Francisco", country="USA")
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

    assert first == second
    assert first["normalized_club_name"] == "massialas foundation"
    assert first["city"] == "San Francisco"
    assert first["country"] == "USA"
    assert first["source"] == "google_maps"
    assert first["metadata"] == {"place_id": "ChIJ-fencing"}

    class FakeResponse:
        data = []

    class FakeTable:
        def __init__(self):
            self.calls = []

        def upsert(self, rows, on_conflict):
            self.calls.append({"rows": rows, "on_conflict": on_conflict})
            return self

        def execute(self):
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.review_table = FakeTable()

        def table(self, name):
            assert name == "fs_club_reviews"
            return self.review_table

    client = FakeClient()
    assert upsert_review_rows(client, [first], batch_size=10) == 1
    assert client.review_table.calls == [
        {
            "rows": [first],
            "on_conflict": "normalized_club_name,city,country,source",
        }
    ]


def test_fetch_distinct_clubs_merges_sources_and_skips_missing_city():
    from scrape_club_reviews import fetch_distinct_clubs

    class FakeResponse:
        def __init__(self, data):
            self.data = data

    class FakeQuery:
        def __init__(self, client, table_name):
            self.client = client
            self.table_name = table_name
            self.start = 0
            self.end = None

        def select(self, columns):
            self.client.selects.append((self.table_name, columns))
            if self.table_name == "fs_club_rankings" and columns == "club,country,city,metadata":
                raise RuntimeError("city column absent")
            return self

        def range(self, start, end):
            self.start = start
            self.end = end
            return self

        def execute(self):
            rows = self.client.tables[self.table_name]
            return FakeResponse(rows[self.start : cast(int, self.end) + 1])

    class FakeClient:
        def __init__(self):
            self.tables = {
                "fs_fencers": [
                    {
                        "club": " Massialas Foundation ",
                        "country": "USA",
                        "city": "San Francisco",
                        "metadata": {},
                    },
                    {"club": "Blade Club", "country": "USA", "metadata": {}},
                ],
                "fs_club_rankings": [
                    {
                        "club": "massialas-foundation",
                        "country": "USA",
                        "metadata": {"city": "San Francisco"},
                    }
                ],
            }
            self.selects = []

        def table(self, table_name):
            return FakeQuery(self, table_name)

    clubs = fetch_distinct_clubs(FakeClient(), page_size=10)

    assert clubs == [
        {
            "name": "Massialas Foundation",
            "normalized_name": "massialas foundation",
            "city": "San Francisco",
            "country": "USA",
            "source_tables": ["fs_fencers", "fs_club_rankings"],
        }
    ]


def test_club_reviews_migration_defines_table_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_club_reviews.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_club_reviews" in normalized
    assert "normalized_club_name text not null" in normalized
    assert "rating numeric" in normalized
    assert "review_count integer" in normalized
    assert "metadata jsonb" in normalized
    assert "unique (normalized_club_name, city, country, source)" in normalized
