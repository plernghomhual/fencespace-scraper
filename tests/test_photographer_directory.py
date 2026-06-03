import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"


FENCINGPHOTOS_ABOUT_HTML = """
<html>
  <head><title>about - FencingPhotos.com</title></head>
  <body>
    <h1>About FencingPhotos</h1>
    <p>
      Since 2003, FencingPhotos has covered the world of fencing with
      professional, documentary-style photography. As the official photographer
      for the International Fencing Federation (FIE) and USA Fencing, we've
      produced more than two million images from Olympic Games, world and zonal
      championships, grand prix and world cup tournaments, and other major and
      official events.
    </p>
    <p>By Serge Timacheff</p>
    <p>Contact: <a href="mailto:serge@timacheff.com">serge@timacheff.com</a></p>
    <p><a href="https://www.fencingphotos.com/">explore fencingphotos.com</a></p>
  </body>
</html>
"""


FIE_PRESSKIT_TEXT = """
FIE PHOTOGRAPHER
Serge Timacheff: serge@fencingphotos.com
CONTACTS
Media Manager media@example.org
Event official website: www.bourges2016.com
Official site of the International Fencing Federation: www.fie.org
"""


FLICKR_GALLERY_HTML = """
<html>
  <head>
    <title>2010 YOG Day 2 | Flickr</title>
    <meta name="description" content="2010 Youth Olympic Games. The second day
    of fencing featured Men's Epee and Women's Sabre. All photos
    S.Timacheff/FencingPhotos.com">
  </head>
  <body>
    <h1>2010 YOG Day 2</h1>
    <p>2010 Youth Olympic Games. All photos S.Timacheff/FencingPhotos.com</p>
    <a href="https://www.flickr.com/photos/fencingnet/albums/72157624625104299/">
      View album
    </a>
  </body>
</html>
"""


PRIVATE_EMAIL_NOISE_HTML = """
<html><body>
  <h1>January NAC gallery</h1>
  <p>Competitor Jane Doe can be reached at jane.private@example.com.</p>
  <p>Official photographer: Serge Timacheff / FencingPhotos.com.</p>
  <p>Photographer contact: <a href="mailto:serge@fencingphotos.com">Email Serge</a></p>
</body></html>
"""


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTournamentQuery:
    def __init__(self, client):
        self.client = client
        self.filters = []

    def select(self, columns):
        self.filters.append(("select", columns))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, count):
        self.filters.append(("limit", count))
        return self

    def execute(self):
        self.client.queries.append(self.filters)
        return FakeResponse(
            [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "source_id": "yog:2010:fencing",
                    "name": "2010 Youth Olympic Games - Fencing",
                    "metadata": {"source_url": "https://olympics.com/yog/2010/fencing"},
                }
            ]
        )


class FakeUpsertQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name

    def upsert(self, rows, on_conflict):
        self.client.upserts.append((self.table_name, rows, on_conflict))
        return self

    def execute(self):
        return FakeResponse([])


class FakeSupabase:
    def __init__(self):
        self.queries = []
        self.upserts = []

    def table(self, table_name):
        if table_name == "fs_tournaments":
            return FakeTournamentQuery(self)
        return FakeUpsertQuery(self, table_name)


def test_parse_directory_html_extracts_public_business_contact_and_regions():
    from scrape_photographer_directory import PhotographerSource, parse_directory_html

    source = PhotographerSource(
        url="https://www.fencingphotos.com/about",
        source_kind="business_directory",
        regions=["USA", "International"],
    )

    rows = parse_directory_html(FENCINGPHOTOS_ABOUT_HTML, source, scraped_at=NOW)

    assert rows == [
        {
            "name": "Serge Timacheff",
            "business": "FencingPhotos.com",
            "website": "https://www.fencingphotos.com/",
            "email": "serge@timacheff.com",
            "public_contact": "mailto:serge@timacheff.com",
            "regions": ["USA", "International"],
            "event_urls": [],
            "source_url": "https://www.fencingphotos.com/about",
            "metadata": {
                "source_kind": "business_directory",
                "source_title": "about - FencingPhotos.com",
                "official_for": ["FIE", "USA Fencing"],
            },
            "scraped_at": NOW,
        }
    ]


def test_parse_text_presskit_extracts_event_photographer_without_media_contacts():
    from scrape_photographer_directory import PhotographerSource, parse_directory_text

    source = PhotographerSource(
        url="https://static.fie.org/uploads/9/46343-AS.2-Bourges%20Press%20Kit%202016_V2-3.pdf",
        source_kind="federation_presskit",
        event_name="2016 Bourges Junior and Cadet World Championships",
        event_url="https://www.bourges2016.com/",
        regions=["International"],
    )

    rows = parse_directory_text(FIE_PRESSKIT_TEXT, source, scraped_at=NOW)

    assert len(rows) == 1
    assert rows[0]["name"] == "Serge Timacheff"
    assert rows[0]["business"] == "FencingPhotos.com"
    assert rows[0]["email"] == "serge@fencingphotos.com"
    assert rows[0]["event_urls"] == ["https://www.bourges2016.com/"]
    assert rows[0]["metadata"]["event_name"] == "2016 Bourges Junior and Cadet World Championships"
    assert "media@example.org" not in str(rows[0])


def test_parse_gallery_html_extracts_credit_and_event_link():
    from scrape_photographer_directory import PhotographerSource, parse_gallery_html

    source = PhotographerSource(
        url="https://www.flickr.com/photos/fencingnet/albums/72157624625104299/",
        source_kind="public_gallery",
        regions=["International"],
    )

    rows = parse_gallery_html(FLICKR_GALLERY_HTML, source, scraped_at=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Serge Timacheff"
    assert row["business"] == "FencingPhotos.com"
    assert row["website"] == "https://www.fencingphotos.com/"
    assert row["event_urls"] == [
        "https://www.flickr.com/photos/fencingnet/albums/72157624625104299/"
    ]
    assert row["metadata"]["event_name"] == "2010 YOG Day 2"


def test_public_contact_filtering_ignores_unrelated_private_emails():
    from scrape_photographer_directory import PhotographerSource, parse_directory_html

    rows = parse_directory_html(
        PRIVATE_EMAIL_NOISE_HTML,
        PhotographerSource(
            url="https://example.org/january-nac-gallery",
            source_kind="event_gallery",
            event_name="January NAC",
        ),
        scraped_at=NOW,
    )

    assert len(rows) == 1
    assert rows[0]["email"] == "serge@fencingphotos.com"
    assert "jane.private@example.com" not in str(rows[0])


def test_dedupe_merges_by_normalized_business_website_and_contact():
    from scrape_photographer_directory import dedupe_photographers

    rows = [
        {
            "name": "Serge Timacheff",
            "business": "FencingPhotos.com",
            "website": "https://www.fencingphotos.com/home-page",
            "email": "serge@timacheff.com",
            "public_contact": "mailto:serge@timacheff.com",
            "regions": ["USA"],
            "event_urls": ["https://www.fencingphotos.com/usa-fencing-event-photos"],
            "source_url": "https://www.fencingphotos.com/about",
            "metadata": {"source_kind": "business_directory"},
            "scraped_at": NOW,
        },
        {
            "name": "S. Timacheff",
            "business": "FencingPhotos",
            "website": "http://fencingphotos.com/",
            "email": "serge@fencingphotos.com",
            "public_contact": "mailto:serge@fencingphotos.com",
            "regions": ["International"],
            "event_urls": ["https://www.bourges2016.com/"],
            "source_url": "https://static.fie.org/press-kit.pdf",
            "metadata": {"source_kind": "federation_presskit", "event_name": "Bourges 2016"},
            "scraped_at": NOW,
        },
    ]

    deduped = dedupe_photographers(rows)

    assert len(deduped) == 1
    row = deduped[0]
    assert row["name"] == "Serge Timacheff"
    assert row["business"] == "FencingPhotos.com"
    assert row["normalized_key"] == "fencingphotos|web:fencingphotos.com"
    assert row["regions"] == ["USA", "International"]
    assert row["event_urls"] == [
        "https://www.fencingphotos.com/usa-fencing-event-photos",
        "https://www.bourges2016.com/",
    ]
    assert row["metadata"]["duplicate_source_urls"] == ["https://static.fie.org/press-kit.pdf"]


def test_tournament_linking_adds_matches_when_event_name_is_clear():
    from scrape_photographer_directory import link_photographers_to_tournaments

    fake = FakeSupabase()
    rows = [
        {
            "name": "Serge Timacheff",
            "business": "FencingPhotos.com",
            "website": "https://www.fencingphotos.com/",
            "regions": ["International"],
            "event_urls": ["https://www.flickr.com/photos/fencingnet/albums/72157624625104299/"],
            "source_url": "https://www.flickr.com/photos/fencingnet/albums/72157624625104299/",
            "metadata": {"event_name": "2010 Youth Olympic Games"},
            "scraped_at": NOW,
        }
    ]

    linked = link_photographers_to_tournaments(fake, rows)

    assert linked[0]["tournament_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert linked[0]["metadata"]["linked_tournaments"] == [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "source_id": "yog:2010:fencing",
            "name": "2010 Youth Olympic Games - Fencing",
        }
    ]
    assert fake.queries[0][1] == ("ilike", "name", "%2010 Youth Olympic Games%")


def test_upsert_photographer_rows_uses_normalized_key_conflict():
    from scrape_photographer_directory import upsert_photographer_rows

    fake = FakeSupabase()
    rows = [
        {
            "normalized_key": "fencingphotos|web:fencingphotos.com",
            "name": "Serge Timacheff",
            "business": "FencingPhotos.com",
        }
    ]

    assert upsert_photographer_rows(fake, rows) == 1
    assert fake.upserts == [
        ("fs_event_photographers", rows, "normalized_key"),
    ]


def test_photographer_migration_defines_safe_public_directory_table():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_photographers.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_event_photographers" in normalized
    assert "business text" in normalized
    assert "website text" in normalized
    assert "email text" in normalized
    assert "public_contact text" in normalized
    assert "regions text[]" in normalized
    assert "event_urls text[]" in normalized
    assert "tournament_ids uuid[]" in normalized
    assert "source_url text" in normalized
    assert "metadata jsonb" in normalized
    assert "scraped_at timestamptz" in normalized
    assert "unique (normalized_key)" in normalized
