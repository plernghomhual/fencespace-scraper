import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]


FIE_QUOTE_HTML = """
<html lang="en">
  <body>
    <h1>Training Camp educates, inspires young fencers ahead of Junior and Cadet World Championships</h1>
    <div class="Article-content">
      <div class="Article-content-label">27 May 2026</div>
      <div class="Article-content-body">
        <p>An international training camp organised by the FIE brought together young fencers in Rio de Janeiro.</p>
        <p>"It's a very great experience with all of these amazing fencers from all these different countries," said 19-year-old sabreur Daniel Posy (HAI).</p>
        <p>"It's nice because you get to talk to everybody and get to know them, both on the track and culturally," said Lucia Ognenovich, a 16-year-old epeeist from Argentina.</p>
      </div>
    </div>
  </body>
</html>
"""


USA_QUOTE_HTML = """
<html lang="en">
  <body>
    <h1>Lee Kiefer Become Team USA's First Women's Foil World Champion</h1>
    <time datetime="2025-07-25T14:09:00-04:00">Jul 25, 2025</time>
    <main>
      <p>TBILISI, Georgia - Kiefer became the first U.S. woman ever to win the crown.</p>
      <p>"It's so freaking cool. I've been chasing this for so long, it has been eluding me, and we put a lot of the details together at the right time. So thank you to my coach and Gerek and everyone else. This extra sentence is present so the scraper has to keep only a short excerpt instead of storing a long transcript-like quote," Kiefer said.</p>
    </main>
  </body>
</html>
"""


SPANISH_QUOTE_HTML = """
<html lang="es">
  <body>
    <h1>Copa del Mundo de Esgrima</h1>
    <time datetime="2026-02-10T12:00:00+00:00">10 febrero 2026</time>
    <article>
      <p>"Estoy muy feliz de competir en casa y compartir este momento con mi equipo," dijo Jose Garcia.</p>
    </article>
  </body>
</html>
"""


def test_quotes_migration_defines_copyright_conscious_table_shape():
    migration = ROOT / "supabase" / "migrations" / "20260602_quotes.sql"
    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_quotes" in normalized
    assert "quote_excerpt text not null" in normalized
    assert "check (char_length(quote_excerpt) <= 320)" in normalized
    assert "speaker text not null" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "source_title text not null" in normalized
    assert "source_url text not null" in normalized
    assert "published_at timestamptz" in normalized
    assert "language text not null" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "unique (quote_hash)" in normalized
    assert "full_body" not in normalized
    assert "transcript text" not in normalized


def test_parse_fie_article_extracts_said_quotes_from_realistic_fixture():
    from scrape_quotes import extract_quote_candidates, parse_article

    article = parse_article(
        source="fie_news",
        source_site="fie.org",
        url="https://fie.org/articles/1651",
        html=FIE_QUOTE_HTML,
    )
    quotes = extract_quote_candidates(article)

    assert article.title.startswith("Training Camp educates")
    assert article.published_at == "2026-05-27T00:00:00+00:00"
    assert article.language == "en"
    assert [(q.speaker, q.quote_excerpt) for q in quotes] == [
        (
            "Daniel Posy",
            "It's a very great experience with all of these amazing fencers from all these different countries,",
        ),
        (
            "Lucia Ognenovich",
            "It's nice because you get to talk to everybody and get to know them, both on the track and culturally,",
        ),
    ]
    assert all(len(q.quote_excerpt) <= 320 for q in quotes)


def test_build_quote_rows_limits_excerpts_and_matches_speaker_from_context():
    from scrape_quotes import MAX_QUOTE_EXCERPT_CHARS, build_quote_rows, extract_quote_candidates, parse_article

    article = parse_article(
        source="usa_fencing_news",
        source_site="usafencing.org",
        url="https://www.usafencing.org/news/2025/july/25/lee-kiefer-become-team-usa-s-first-women-s-foil-world-champion",
        html=USA_QUOTE_HTML,
    )
    candidates = extract_quote_candidates(article)
    rows = build_quote_rows(
        article,
        candidates,
        known_fencers=[
            {"id": "fencer-lee", "name": "Lee Kiefer", "fie_id": "12345"},
            {"id": "fencer-jordan", "name": "Jordan Lee", "fie_id": "99999"},
        ],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["speaker"] == "Kiefer"
    assert row["fencer_id"] == "fencer-lee"
    assert len(row["quote_excerpt"]) <= MAX_QUOTE_EXCERPT_CHARS
    assert row["metadata"]["speaker_match"]["status"] == "context_full_name"
    assert row["metadata"]["speaker_match"]["matched_name"] == "Lee Kiefer"
    assert "This extra sentence" not in row["metadata"]


def test_ambiguous_speaker_names_are_not_linked():
    from scrape_quotes import build_quote_rows, extract_quote_candidates, parse_article

    html = """
    <html><body>
      <h1>Fencing awards announced</h1>
      <article><p>"This medal belongs to the team," said Jordan Lee.</p></article>
    </body></html>
    """
    article = parse_article(source="test_news", source_site="example.test", url="https://example.test/a", html=html)
    rows = build_quote_rows(
        article,
        extract_quote_candidates(article),
        known_fencers=[
            {"id": "jordan-us", "name": "Jordan Lee", "fie_id": "111"},
            {"id": "jordan-can", "name": "Jordan Lee", "fie_id": "222"},
        ],
    )

    assert rows[0]["fencer_id"] is None
    assert rows[0]["metadata"]["speaker_match"]["status"] == "ambiguous"
    assert rows[0]["metadata"]["speaker_match"]["candidate_ids"] == ["jordan-us", "jordan-can"]


def test_multilingual_quote_preserves_unicode_and_language():
    from scrape_quotes import build_quote_rows, extract_quote_candidates, parse_article

    article = parse_article(
        source="federation_news",
        source_site="example.es",
        url="https://example.es/noticias/copa",
        html=SPANISH_QUOTE_HTML,
    )
    rows = build_quote_rows(
        article,
        extract_quote_candidates(article),
        known_fencers=[{"id": "garcia", "name": "Jose Garcia", "fie_id": "777"}],
    )

    assert rows[0]["language"] == "es"
    assert rows[0]["speaker"] == "Jose Garcia"
    assert rows[0]["fencer_id"] == "garcia"
    assert "feliz de competir" in rows[0]["quote_excerpt"]


def test_dedupe_quotes_drops_exact_duplicates_but_keeps_translations():
    from scrape_quotes import dedupe_quote_rows

    rows = [
        {
            "quote_hash": "same",
            "quote_excerpt": "I am proud of the team.",
            "speaker": "Alex Kim",
            "language": "en",
            "source_url": "https://example.test/article",
            "metadata": {"canonical_source_url": "https://example.test/article"},
        },
        {
            "quote_hash": "same",
            "quote_excerpt": "I am proud of the team.",
            "speaker": "Alex Kim",
            "language": "en",
            "source_url": "https://example.test/article?lang=en",
            "metadata": {"canonical_source_url": "https://example.test/article"},
        },
        {
            "quote_hash": "translated",
            "quote_excerpt": "Estoy orgulloso del equipo.",
            "speaker": "Alex Kim",
            "language": "es",
            "source_url": "https://example.test/article?lang=es",
            "metadata": {"canonical_source_url": "https://example.test/article"},
        },
    ]

    deduped = dedupe_quote_rows(rows)

    assert [row["quote_hash"] for row in deduped] == ["same", "translated"]
    assert deduped[0]["metadata"]["duplicate_source_urls"] == ["https://example.test/article?lang=en"]
    assert deduped[1]["language"] == "es"


def test_scrape_source_returns_stub_for_blocked_press_pages_without_fetching():
    from scrape_quotes import scrape_source

    session = ExplodingSession()
    rows, failed, skipped, successful_urls, stubs = scrape_source(
        session=session,
        source_config={
            "source": "fie_press_conferences",
            "source_site": "fie.org",
            "listing_url": "https://fie.org/media",
            "blocked": True,
            "block_reason": "No public static transcript endpoint found during probe.",
        },
        known_fencers=[],
        seen_hashes=set(),
    )

    assert rows == []
    assert failed == 0
    assert skipped == 1
    assert successful_urls == []
    assert stubs == [
        {
            "source": "fie_press_conferences",
            "source_site": "fie.org",
            "url": "https://fie.org/media",
            "reason": "No public static transcript endpoint found during probe.",
        }
    ]
    assert session.calls == []


def test_upsert_quotes_uses_quote_hash_conflict_key():
    from scrape_quotes import upsert_quotes

    client = FakeSupabaseClient()
    rows = [
        {"quote_hash": "a", "quote_excerpt": "First quote", "source_url": "https://example.test/a"},
        {"quote_hash": "a", "quote_excerpt": "First quote duplicate", "source_url": "https://example.test/a?lang=en"},
        {"quote_hash": "b", "quote_excerpt": "Second quote", "source_url": "https://example.test/b"},
    ]

    written = upsert_quotes(client, rows, batch_size=100)

    assert written == 2
    assert client.tables["fs_quotes"].upserts == [
        (
            [
                {"quote_hash": "a", "quote_excerpt": "First quote duplicate", "source_url": "https://example.test/a?lang=en"},
                {"quote_hash": "b", "quote_excerpt": "Second quote", "source_url": "https://example.test/b"},
            ],
            "quote_hash",
        )
    ]


class ExplodingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        raise AssertionError("blocked source should not fetch")


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
        return FakeResult()


class FakeResult:
    data: list[object] = []
