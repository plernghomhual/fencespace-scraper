from typing import Any, cast
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"

PUBLIC_CAMP_REVIEW_HTML = """
<html>
  <body>
    <section id="testimonials">
      <article class="testimonial review" data-camp="Pre-Nationals Epee Camp">
        <h3>Pre-Nationals Epee Camp</h3>
        <div class="stars" aria-label="5 out of 5 stars"></div>
        <blockquote>
          My daughter came home sharper, more confident, and ready for Summer Nationals.
          Coach feedback was specific and the bouting was intense.
        </blockquote>
        <p class="reviewer">Jordan Smith, parent</p>
        <a href="/camp#pre-nationals-review">Read more</a>
      </article>
      <script type="application/ld+json">
      {
        "@type": "SportsActivityLocation",
        "name": "Hooked on Fencing",
        "aggregateRating": {
          "@type": "AggregateRating",
          "ratingValue": "4.8",
          "reviewCount": "23"
        }
      }
      </script>
    </section>
  </body>
</html>
"""

GOOGLE_PLACES_DETAILS = {
    "status": "OK",
    "result": {
        "name": "Pre-Nationals Epee Camp",
        "place_id": "ChIJ-camp-review",
        "rating": 4.7,
        "user_ratings_total": 31,
        "url": "https://www.google.com/maps/place/?q=place_id:ChIJ-camp-review",
        "reviews": [
            {
                "author_name": "Avery Parent",
                "rating": 5,
                "text": "Clear coaching, strong footwork blocks, and careful supervision.",
                "time": 1781136000,
            }
        ],
    },
}

CAMP_ROWS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Pre-Nationals Epee Camp",
        "organizer": "Hooked on Fencing",
        "city": "North Royalton",
        "country": "USA",
        "start_date": "2026-06-15",
        "end_date": "2026-06-19",
        "source_url": "https://www.hookedonfencing.org/camp",
        "metadata": {},
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Pre-Nationals Epee Camp",
        "organizer": "Other Fencing",
        "city": "Columbus",
        "country": "USA",
        "start_date": "2026-06-15",
        "end_date": "2026-06-19",
        "source_url": "https://example.test/camp",
        "metadata": {},
    },
]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append({"table": self.name, "columns": columns})
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.name == "fs_training_camps":
            return FakeResult(self.client.camps)
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            }
        )
        return FakeResult([])


class FakeSupabase:
    def __init__(self, camps=None):
        self.camps = camps or []
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_public_review_html_extracts_review_and_aggregate_rating():
    from scrape_camp_reviews import ReviewSource, parse_public_review_html

    source = ReviewSource(
        url="https://www.hookedonfencing.org/camp",
        organizer="Hooked on Fencing",
        city="North Royalton",
        country="USA",
        source_kind="club_page",
    )

    reviews = parse_public_review_html(PUBLIC_CAMP_REVIEW_HTML, source)

    assert reviews == [
        {
            "camp_name": "Pre-Nationals Epee Camp",
            "organizer": "Hooked on Fencing",
            "city": "North Royalton",
            "country": "USA",
            "source": "club_page",
            "rating": 5.0,
            "review_count": 1,
            "review_text_snippet": (
                "My daughter came home sharper, more confident, and ready for Summer Nationals. "
                "Coach feedback was specific and the bouting was intense."
            ),
            "reviewer_name": "Jordan Smith, parent",
            "source_url": "https://www.hookedonfencing.org/camp#pre-nationals-review",
            "metadata": {
                "source_kind": "club_page",
                "aggregate_rating": 4.8,
                "aggregate_review_count": 23,
            },
        }
    ]


def test_parse_public_review_html_keeps_multiple_cards_inside_testimonials_section():
    from scrape_camp_reviews import ReviewSource, parse_public_review_html

    html = """
    <section id="testimonials">
      <article class="review" data-camp="Pre-Nationals Epee Camp">
        <h3>Pre-Nationals Epee Camp</h3>
        <p aria-label="5 out of 5 stars"></p>
        <blockquote>Excellent bouting and focused lessons.</blockquote>
        <p class="reviewer">Parent One</p>
      </article>
      <article class="review" data-camp="Pre-Season Foil Camp">
        <h3>Pre-Season Foil Camp</h3>
        <p aria-label="4 out of 5 stars"></p>
        <blockquote>Good drills and a clear schedule.</blockquote>
        <p class="reviewer">Parent Two</p>
      </article>
    </section>
    """
    source = ReviewSource(url="https://example.test/camps", source_kind="club_page")

    reviews = parse_public_review_html(html, source)

    assert [review["camp_name"] for review in reviews] == [
        "Pre-Nationals Epee Camp",
        "Pre-Season Foil Camp",
    ]
    assert [review["rating"] for review in reviews] == [5.0, 4.0]


def test_google_places_parser_and_no_key_dry_run(capsys):
    from scrape_camp_reviews import (
        query_google_places_camp_reviews,
        parse_google_places_details_response,
    )

    camp = CAMP_ROWS[0]
    reviews = parse_google_places_details_response(
        GOOGLE_PLACES_DETAILS,
        camp,
        search_query="Pre-Nationals Epee Camp Hooked on Fencing North Royalton",
    )

    assert reviews[0]["source"] == "google_places"
    assert reviews[0]["rating"] == 5.0
    assert reviews[0]["review_count"] == 31
    assert reviews[0]["reviewer_name"] == "Avery Parent"
    assert reviews[0]["metadata"]["place_id"] == "ChIJ-camp-review"
    assert reviews[0]["metadata"]["aggregate_rating"] == 4.7

    class Session:
        def get(self, *args, **kwargs):
            raise AssertionError("HTTP should not be called without MAPS_API_KEY")

    assert query_google_places_camp_reviews(camp, maps_api_key=None, session=Session()) == []
    assert "MAPS_API_KEY not set" in capsys.readouterr().out


def test_match_review_to_camp_uses_disambiguators_and_logs_ambiguity():
    from scrape_camp_reviews import match_review_to_camp

    exact_review = {
        "camp_name": "Pre-Nationals Epee Camp",
        "organizer": "Hooked on Fencing",
        "city": "North Royalton",
        "country": "USA",
        "start_date": "2026-06-15",
        "end_date": "2026-06-19",
    }
    ambiguity_log: list[Any] = []

    matched = match_review_to_camp(exact_review, CAMP_ROWS, ambiguity_log=ambiguity_log)

    matched = cast(dict[str, Any], matched)
    assert matched["id"] == "11111111-1111-1111-1111-111111111111"
    assert ambiguity_log == []

    ambiguous_review = {"camp_name": "Pre-Nationals Epee Camp"}
    matched = cast(dict[str, Any], match_review_to_camp(ambiguous_review, CAMP_ROWS, ambiguity_log=ambiguity_log))

    assert matched is None
    assert ambiguity_log == [
        {
            "camp_name": "Pre-Nationals Epee Camp",
            "reason": "ambiguous_match",
            "candidate_ids": [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ],
        }
    ]


def test_build_review_row_minimizes_pii_and_uses_stable_source_hash():
    from scrape_camp_reviews import build_review_row

    review = {
        "camp_name": "Pre-Nationals Epee Camp",
        "organizer": "Hooked on Fencing",
        "source": "club_page",
        "rating": 5,
        "review_count": 1,
        "review_text_snippet": "Strong bouting, useful feedback, and careful supervision.",
        "reviewer_name": "Jordan Smith, parent",
        "source_url": "https://www.hookedonfencing.org/camp#pre-nationals-review",
        "metadata": {"source_kind": "club_page", "reviewer_email": "jordan@example.test"},
    }

    first = build_review_row(review, CAMP_ROWS[0], scraped_at=NOW)
    second = build_review_row(review, CAMP_ROWS[0], scraped_at=NOW)

    assert first == second
    assert first["camp_id"] == CAMP_ROWS[0]["id"]
    assert first["camp_name"] == "Pre-Nationals Epee Camp"
    assert first["source"] == "club_page"
    assert first["reviewer_hash"]
    assert first["reviewer_hash"] != "Jordan Smith, parent"
    assert first["source_hash"]
    assert "Jordan" not in str(first)
    assert "jordan@example.test" not in str(first)
    assert first["metadata"] == {"source_kind": "club_page"}


def test_dedupe_and_upsert_write_only_review_table():
    from scrape_camp_reviews import (
        ReviewSource,
        FetchedContent,
        scrape_camp_reviews,
    )

    source = ReviewSource(
        url="https://www.hookedonfencing.org/camp",
        organizer="Hooked on Fencing",
        city="North Royalton",
        country="USA",
        source_kind="club_page",
    )

    def fetcher(_source, **_kwargs):
        return FetchedContent(
            content=PUBLIC_CAMP_REVIEW_HTML.encode("utf-8"),
            content_type="text/html",
            final_url="https://www.hookedonfencing.org/camp",
        )

    client = FakeSupabase(camps=[CAMP_ROWS[0]])
    summary = scrape_camp_reviews(
        client=client,
        sources=[source, source],
        fetcher=fetcher,
        maps_api_key=None,
        request_delay=0,
        log_run=False,
        update_state=False,
        scraped_at=NOW,
    )

    assert summary == {
        "camps_seen": 1,
        "sources_seen": 2,
        "review_rows": 1,
        "written": 1,
        "failed": 0,
        "skipped": 2,
        "ambiguous": 0,
    }
    assert client.selects == [
        {
            "table": "fs_training_camps",
            "columns": (
                "id,name,organizer,city,country,start_date,end_date,source_url,metadata"
            ),
        }
    ]
    assert client.upserts == [
        {
            "table": "fs_training_camp_reviews",
            "rows": client.upserts[0]["rows"],
            "on_conflict": "source,source_url,source_hash",
        }
    ]
    assert len(client.upserts[0]["rows"]) == 1
    assert client.upserts[0]["rows"][0]["camp_name"] == "Pre-Nationals Epee Camp"


def test_camp_reviews_migration_defines_review_storage_only():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_camp_reviews.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_training_camp_reviews" in normalized
    assert "camp_id uuid" in normalized
    assert "camp_name text not null" in normalized
    assert "source text not null" in normalized
    assert "rating numeric" in normalized
    assert "review_count integer" in normalized
    assert "review_text_snippet text" in normalized
    assert "reviewer_hash text" in normalized
    assert "source_url text not null" in normalized
    assert "source_hash text not null" in normalized
    assert "metadata jsonb" in normalized
    assert "unique (source, source_url, source_hash)" in normalized
    assert "references public.fs_training_camps" not in normalized
