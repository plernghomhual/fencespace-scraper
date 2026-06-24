import pytest

PUBLIC_REVIEW_FIXTURE = """
<html>
  <head>
    <link rel="canonical" href="https://fencing.net/reviews/nike-air-zoom-fencing-shoes/" />
    <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Nike Air Zoom Fencing Shoes",
        "brand": {"name": "Nike"},
        "category": "Shoes",
        "aggregateRating": {"ratingValue": "5", "reviewCount": "39", "bestRating": "5"}
      }
    </script>
  </head>
  <body>
    <article class="post">
      <h1 class="entry-title">Nike Air Zoom Fencing Shoes Review</h1>
      <time class="entry-date" datetime="2024-08-29T12:00:00+00:00">August 29, 2024</time>
      <span class="cat-links"><a rel="category tag">Shoes</a></span>
      <div class="review-total-wrapper">
        <div class="user-rate-wrap">Reader Rating 39 Votes 5</div>
      </div>
      <div class="entry-content">
        <p>The Nike Air Zoom fencing shoe remains light, grippy, and stable on the strip.</p>
        <p>Heel cushioning is excellent, but the narrow fit will not work for every fencer.</p>
      </div>
    </article>
  </body>
</html>
"""


FORUM_STYLE_FIXTURE = """
<html><body>
  <aside><form id="loginform"><input name="log" /></form></aside>
  <article class="message">
    <h1>BF Blue FIE Epee Blade Review</h1>
    <time datetime="2010-01-07">January 7, 2010</time>
    <div class="bbp-reply-content">
      <p>The BF Blue FIE epee blade has a predictable flex and lasted through heavy club use.</p>
    </div>
    <div class="bbp-reply-content">
      <p>The BF Blue FIE epee blade has a predictable flex and lasted through heavy club use.</p>
    </div>
  </article>
</body></html>
"""


PRIVATE_FIXTURE = """
<html><body>
  <h1>Private Forum</h1>
  <p>You must be logged in to view this forum thread.</p>
  <form id="loginform"><input name="log" /></form>
</body></html>
"""


LISTING_FIXTURE = """
<html><body>
  <a href="https://fencing.net/reviews/nike-air-zoom-fencing-shoes/">Nike Air Zoom review</a>
  <a href="https://fencing.net/forums/private-thread/">Private thread</a>
</body></html>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.pending_rows = None
        self.pending_conflict = None

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.pending_rows,
                "on_conflict": self.pending_conflict,
            }
        )
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_public_fencingnet_review_extracts_product_and_review_rows():
    from scrape_fencingnet_products import parse_review_page

    parsed = parse_review_page(
        PUBLIC_REVIEW_FIXTURE,
        "https://fencing.net/reviews/nike-air-zoom-fencing-shoes/",
        scraped_at="2026-06-02T20:00:00+00:00",
    )

    assert not parsed.skipped_private
    assert len(parsed.products) == 1
    product = parsed.products[0]
    assert product["source"] == "fencing_net"
    assert product["source_id"] == "reviews/nike-air-zoom-fencing-shoes"
    assert product["name"] == "Nike Air Zoom Fencing Shoes"
    assert product["brand"] == "Nike"
    assert product["category"] == "Shoes"
    assert product["product_url"] == "https://fencing.net/reviews/nike-air-zoom-fencing-shoes/"
    assert product["metadata"]["rating"] == pytest.approx(5.0)
    assert product["metadata"]["review_count"] == 39

    assert len(parsed.reviews) == 2
    first_review = parsed.reviews[0]
    assert first_review["product_name"] == "Nike Air Zoom Fencing Shoes"
    assert first_review["brand"] == "Nike"
    assert first_review["category"] == "Shoes"
    assert first_review["rating"] == pytest.approx(5.0)
    assert first_review["review_count"] == 39
    assert first_review["source"] == "fencing_net"
    assert first_review["url"].startswith("https://fencing.net/reviews/nike-air-zoom-fencing-shoes/#review-")
    assert first_review["metadata"]["source_url"] == "https://fencing.net/reviews/nike-air-zoom-fencing-shoes/"
    assert first_review["metadata"]["review_date"] == "2024-08-29"
    assert "light, grippy" in first_review["metadata"]["text_snippet"]


def test_parse_private_login_only_page_skips_without_leaking_content():
    from scrape_fencingnet_products import parse_review_page

    parsed = parse_review_page(PRIVATE_FIXTURE, "https://fencing.net/forums/private-thread/")

    assert parsed.skipped_private
    assert parsed.products == []
    assert parsed.reviews == []


def test_forum_style_public_page_dedupes_reviews_by_stable_hash():
    from scrape_fencingnet_products import parse_review_page

    parsed = parse_review_page(FORUM_STYLE_FIXTURE, "https://fencing.net/482/bf-blue-fie-epee-blade-review/")
    repeated = parse_review_page(FORUM_STYLE_FIXTURE, "https://fencing.net/482/bf-blue-fie-epee-blade-review/")

    assert len(parsed.products) == 1
    assert parsed.products[0]["name"] == "BF Blue FIE Epee Blade"
    assert parsed.products[0]["brand"] == "Blaise Freres"
    assert parsed.products[0]["category"] == "Epee Blades"
    assert len(parsed.reviews) == 1
    assert parsed.reviews[0]["metadata"]["review_hash"] == repeated.reviews[0]["metadata"]["review_hash"]
    assert parsed.reviews[0]["url"] == repeated.reviews[0]["url"]


def test_upserts_products_and_reviews_to_expected_tables():
    from scrape_fencingnet_products import parse_review_page, upsert_products, upsert_reviews

    parsed = parse_review_page(PUBLIC_REVIEW_FIXTURE, "https://fencing.net/reviews/nike-air-zoom-fencing-shoes/")
    client = FakeClient()

    product_written, product_failed = upsert_products(client, parsed.products)
    review_written, review_failed = upsert_reviews(client, parsed.reviews)

    assert (product_written, product_failed) == (1, 0)
    assert (review_written, review_failed) == (2, 0)
    assert client.upserts[0]["table"] == "fs_products"
    assert client.upserts[0]["on_conflict"] == "source,source_id"
    assert client.upserts[1]["table"] == "fs_equipment_reviews"
    assert client.upserts[1]["on_conflict"] == "url"


def test_scrape_fencingnet_products_discovers_reviews_skips_private_and_records_state(monkeypatch):
    from scrape_fencingnet_products import scrape_fencingnet_products

    start_url = "https://fencing.net/reviews/"
    public_url = "https://fencing.net/reviews/nike-air-zoom-fencing-shoes/"
    private_url = "https://fencing.net/forums/private-thread/"
    fixtures = {
        start_url: LISTING_FIXTURE,
        public_url: PUBLIC_REVIEW_FIXTURE,
        private_url: PRIVATE_FIXTURE,
    }
    states = []

    monkeypatch.setattr("scrape_fencingnet_products.get_state", lambda source, key: None)
    monkeypatch.setattr(
        "scrape_fencingnet_products.set_state",
        lambda source, key, value: states.append((source, key, value)),
    )

    client = FakeClient()
    result = scrape_fencingnet_products(
        client=client,
        start_urls=[start_url, private_url],
        fetcher=lambda url: fixtures[url],
        log_run=False,
    )

    assert result["fetched"] == 3
    assert result["product_written"] == 1
    assert result["review_written"] == 2
    assert result["failed"] == 0
    assert result["skipped"] == 1
    assert result["private_skipped"] == 1
    assert [call["table"] for call in client.upserts] == ["fs_products", "fs_equipment_reviews"]
    assert states[-1][0:2] == ("fencingnet_products", "last_run")
    assert states[-1][2]["written"] == 3
