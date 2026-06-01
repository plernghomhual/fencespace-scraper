import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIE_LISTING_HTML = """
<html>
  <body>
    <a href="/articles/1649">
      Alina Mikhailova Leads _AIN to Women's Sabre Gold in Lima with a Spectacular Comeback
    </a>
    <a href="/articles/1648">Switzerland Triumphs on Home Soil to Claim Berne Epee Team Gold</a>
    <a href="/competitions">Competitions</a>
    <a href="/articles/1649">Duplicate card for same story</a>
  </body>
</html>
"""


FIE_ARTICLE_HTML = """
<html>
  <body>
    <h1>Alina Mikhailova Leads _AIN to Women's Sabre Gold in Lima with a Spectacular Comeback</h1>
    <div class="Article-content">
      <div class="Article-content-label">25 May 2026</div>
      <div class="Article-content-body">
        <p>Alina Mikhailova won gold at the Women's Sabre World Cup in Lima.</p>
        <p>The final result confirmed a spectacular comeback and a major podium finish.</p>
      </div>
    </div>
    <div class="Article-links">
      <p>This related-story block should not be included in the article body.</p>
    </div>
  </body>
</html>
"""


BRITISH_LISTING_HTML = """
<html>
  <body>
    <div class="o-newsBanner">
      <div class="o-newsBox">
        <span>29/05/2026- Latest News</span>
        <h2>UPCOMING FENCING EVENTS - MAY-JUNE 2026</h2>
        <p>This is a snapshot of some of the upcoming fencing events across the UK.</p>
        <a href="https://www.britishfencing.com/upcoming-fencing-events-may-june-2026/">
          Read Full story
        </a>
      </div>
    </div>
  </body>
</html>
"""


BRITISH_ARTICLE_HTML = """
<html>
  <head>
    <meta property="article:published_time" content="2026-05-29T15:03:17+00:00" />
    <meta property="og:title" content="UPCOMING FENCING EVENTS - MAY-JUNE 2026 - BRITISH FENCING" />
  </head>
  <body>
    <h1>UPCOMING FENCING EVENTS - MAY-JUNE 2026</h1>
    <main>
      <p>This is a snapshot of some of the upcoming fencing events across the UK for May and June 2026.</p>
      <p>Don't miss your chance to enter before entries close.</p>
    </main>
  </body>
</html>
"""


def test_parse_fie_listing_extracts_unique_article_urls():
    from scrape_news import parse_fie_listing

    articles = parse_fie_listing(FIE_LISTING_HTML)

    assert articles == [
        {
            "title": "Alina Mikhailova Leads _AIN to Women's Sabre Gold in Lima with a Spectacular Comeback",
            "url": "https://fie.org/articles/1649",
        },
        {
            "title": "Switzerland Triumphs on Home Soil to Claim Berne Epee Team Gold",
            "url": "https://fie.org/articles/1648",
        },
    ]


def test_parse_fie_article_extracts_title_date_and_body():
    from scrape_news import parse_fie_article

    article = parse_fie_article("https://fie.org/articles/1649", FIE_ARTICLE_HTML)

    assert article["title"] == "Alina Mikhailova Leads _AIN to Women's Sabre Gold in Lima with a Spectacular Comeback"
    assert article["published_at"] == "2026-05-25T00:00:00+00:00"
    assert "Women's Sabre World Cup in Lima" in article["body"]
    assert "related-story block" not in article["body"]


def test_parse_british_listing_extracts_featured_story_url():
    from scrape_news import parse_british_fencing_listing

    articles = parse_british_fencing_listing(BRITISH_LISTING_HTML)

    assert articles == [
        {
            "title": "UPCOMING FENCING EVENTS - MAY-JUNE 2026",
            "url": "https://www.britishfencing.com/upcoming-fencing-events-may-june-2026/",
        }
    ]


def test_parse_british_article_extracts_meta_date_and_body():
    from scrape_news import parse_british_fencing_article

    article = parse_british_fencing_article(
        "https://www.britishfencing.com/upcoming-fencing-events-may-june-2026/",
        BRITISH_ARTICLE_HTML,
    )

    assert article["title"] == "UPCOMING FENCING EVENTS - MAY-JUNE 2026"
    assert article["published_at"] == "2026-05-29T15:03:17+00:00"
    assert article["body"].startswith("This is a snapshot of some of the upcoming fencing events")


def test_classify_article_uses_keyword_priority():
    from scrape_news import classify_article

    assert classify_article("Olympic champion sidelined", "Recovery from surgery continues.") == "injury"
    assert classify_article("Fencer switches federations", "A new country request was approved.") == "transfer"
    assert classify_article("FIE Congress update", "A rule change creates a new format.") == "rule_change"
    assert classify_article("World Cup gold", "The final result gave France the team gold medal.") == "competition_report"
    assert classify_article("Training camp opens", "Athletes attended education sessions.") == "general"


def test_extract_related_fencer_ids_matches_names_with_boundaries():
    from scrape_news import extract_related_fencer_ids

    known = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Alina Mikhailova"},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Sarah Noutcha"},
        {"id": "33333333-3333-3333-3333-333333333333", "name": "Kim"},
    ]
    text = "Alina Mikhailova defeated Sarah Noutcha. The kimono sponsor was unrelated."

    assert extract_related_fencer_ids(text, known) == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]


def test_build_article_row_classifies_and_preserves_body_metadata():
    from scrape_news import build_article_row

    row = build_article_row(
        source="fie_news",
        source_site="fie.org",
        url="https://fie.org/articles/1649",
        title="World Cup gold",
        published_at="2026-05-25T00:00:00+00:00",
        body="Alina Mikhailova won gold at the Women's Sabre World Cup in Lima. " * 12,
        known_fencers=[{"id": "11111111-1111-1111-1111-111111111111", "name": "Alina Mikhailova"}],
    )

    assert row["category"] == "competition_report"
    assert row["related_fencer_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert row["summary"].endswith("...")
    assert row["content_hash"]
    assert row["metadata"]["body"].startswith("Alina Mikhailova won gold")


def test_upsert_articles_dedupes_by_url_before_writing():
    from scrape_news import upsert_articles

    client = FakeSupabaseClient()
    rows = [
        {"url": "https://fie.org/articles/1", "title": "Original"},
        {"url": "https://fie.org/articles/1", "title": "Updated"},
        {"url": "https://fie.org/articles/2", "title": "Second"},
    ]

    written = upsert_articles(client, rows, batch_size=2)

    assert written == 2
    assert client.tables["fs_articles"].upserts == [
        (
            [
                {"url": "https://fie.org/articles/1", "title": "Updated"},
                {"url": "https://fie.org/articles/2", "title": "Second"},
            ],
            "url",
        )
    ]


class FakeSupabaseClient:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        table = self.tables.setdefault(name, FakeTable())
        return table


class FakeTable:
    def __init__(self):
        self.upserts = []
        self._rows = None
        self._on_conflict = None

    def upsert(self, rows, on_conflict):
        self._rows = rows
        self._on_conflict = on_conflict
        return self

    def execute(self):
        self.upserts.append((self._rows, self._on_conflict))
        return FakeResult(self._rows)


class FakeResult:
    def __init__(self, data):
        self.data = data
