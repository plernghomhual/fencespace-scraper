import pytest


CLEARANCE_LISTING_FIXTURE = """
<html><body>
<h1>Clearance</h1>
<div class="product-item alternative">
  <a href="BG-soft-leather-3-wpn-universal-GLOVE_p_100.html">
    <img src="assets/images/bg-soft-glove_thumbnail.jpg" alt="BG soft leather 3-wpn universal GLOVE">
  </a>
  <a class="name" href="BG-soft-leather-3-wpn-universal-GLOVE_p_100.html">
    BG soft leather 3-wpn universal GLOVE
  </a>
  <span class="reviews"><img alt="Average Rating"> (1)</span>
  <span class="price">Sale <s>$23.00</s> On sale $12.00</span>
  <span>In Stock</span>
</div>
<div class="product-item">
  <a class="name" href="/Kempa-Attack-JUNIOR-Final-Sale_p_200.html">
    Kempa Attack JUNIOR ( Final Sale )
  </a>
  <span class="price">Sale <del>$100.00</del> On sale $90.00</span>
  <span>Out of Stock</span>
</div>
</body></html>
"""


DETAIL_FIXTURE = """
<html><body>
<div class="breadcrumbs">
  <a>Home</a> &gt; <a>Fencing Books and DVDs</a> &gt; <a>Fencing Books</a>
  &gt; FIE Fencing Calendar 2026 Uhlmann/Allstar
</div>
<h1>FIE Fencing Calendar 2026 Uhlmann/Allstar</h1>
<div class="main-image">
  <img src="/assets/images/UHAS-K02.jpg" alt="FIE Fencing Calendar 2026 Uhlmann/Allstar">
</div>
<div class="product-id">Part Number:UHAS-K02</div>
<h3>Price</h3>
<div class="price">Your Price: $8.00</div>
<h4>Availability:</h4>
<div class="availability">In Stock</div>
<div id="description">
  <p>2022 FIE Fencing Calendar</p>
  <p>Uhlmann/ Allstar available</p>
  <p>With this calendar give a gift or decorate your wall.</p>
</div>
</body></html>
"""


class FakeResult:
    data = []


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


class FakeLimiter:
    def __init__(self):
        self.waits = []
        self.successes = []
        self.failures = []

    def wait(self, domain, rps=None):
        self.waits.append((domain, rps))

    def record_success(self, domain):
        self.successes.append(domain)

    def record_failure(self, domain):
        self.failures.append(domain)


class FakeRunLog:
    def __init__(self, module):
        self.module = module
        self.completed = None
        self.errors = []

    def start(self):
        return self

    def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
        self.completed = {
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "metadata": metadata or {},
        }

    def error(self, exc_str):
        self.errors.append(exc_str)


def test_parse_listing_products_extracts_sale_price_stock_image_and_weapon():
    from scrape_blue_gauntlet_products import parse_listing_products

    rows = parse_listing_products(
        CLEARANCE_LISTING_FIXTURE,
        listing_url="https://www.blue-gauntlet.com/Clearance_c_311.html",
        category="Clearance",
        scraped_at="2026-06-02T12:00:00+00:00",
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "BG soft leather 3-wpn universal GLOVE"
    assert rows[0]["source"] == "blue_gauntlet"
    assert rows[0]["source_id"] == "100"
    assert rows[0]["category"] == "Clearance"
    assert rows[0]["weapon"] == "All"
    assert rows[0]["price"] == pytest.approx(12.0)
    assert rows[0]["currency"] == "USD"
    assert rows[0]["stock_status"] == "in_stock"
    assert rows[0]["product_url"] == "https://www.blue-gauntlet.com/BG-soft-leather-3-wpn-universal-GLOVE_p_100.html"
    assert rows[0]["image_url"] == "https://www.blue-gauntlet.com/assets/images/bg-soft-glove_thumbnail.jpg"
    assert rows[0]["metadata"]["regular_price"] == 23.0
    assert rows[0]["metadata"]["sale"] is True
    assert rows[0]["metadata"]["review_count"] == 1


def test_parse_detail_product_extracts_sku_category_description_and_canonical_url():
    from scrape_blue_gauntlet_products import parse_detail_product

    row = parse_detail_product(
        DETAIL_FIXTURE,
        product_url="https://www.blue-gauntlet.com/FIE-Fencing-Calendar-2026-UhlmannAllstar-_p_4381.html",
        scraped_at="2026-06-02T12:00:00+00:00",
    )

    assert row["source"] == "blue_gauntlet"
    assert row["source_id"] == "UHAS-K02"
    assert row["name"] == "FIE Fencing Calendar 2026 Uhlmann/Allstar"
    assert row["brand"] == "Uhlmann/Allstar"
    assert row["category"] == "Fencing Books"
    assert row["weapon"] is None
    assert row["price"] == pytest.approx(8.0)
    assert row["currency"] == "USD"
    assert row["description"] == (
        "2022 FIE Fencing Calendar Uhlmann/ Allstar available "
        "With this calendar give a gift or decorate your wall."
    )
    assert row["image_url"] == "https://www.blue-gauntlet.com/assets/images/UHAS-K02.jpg"
    assert row["product_url"] == "https://www.blue-gauntlet.com/FIE-Fencing-Calendar-2026-UhlmannAllstar-_p_4381.html"
    assert row["stock_status"] == "in_stock"
    assert row["metadata"]["sku"] == "UHAS-K02"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("In Stock", "in_stock"),
        ("Out of Stock", "out_of_stock"),
        ("Sold Out - Put me on the Waiting List", "out_of_stock"),
        ("Put me on the Waiting List", "out_of_stock"),
        ("Availability: Ships in 2 weeks", "unknown"),
    ],
)
def test_normalize_stock_status_handles_known_labels(text, expected):
    from scrape_blue_gauntlet_products import normalize_stock_status

    assert normalize_stock_status(text) == expected


def test_parse_price_prefers_on_sale_price_and_tracks_regular_price():
    from scrape_blue_gauntlet_products import parse_price

    price = parse_price("Sale $100.00 On sale $90.00")

    assert price.amount == pytest.approx(90.0)
    assert price.currency == "USD"
    assert price.regular_amount == pytest.approx(100.0)
    assert price.is_sale is True


def test_upsert_products_dedupes_by_source_and_source_id():
    from scrape_blue_gauntlet_products import upsert_products

    client = FakeClient()
    rows = [
        {
            "source": "blue_gauntlet",
            "source_id": "BG-GLOVE",
            "name": "BG glove",
            "brand": "Blue Gauntlet",
            "category": "Clearance",
            "weapon": "all",
            "price": 12.0,
            "currency": "USD",
            "image_url": None,
            "product_url": "https://www.blue-gauntlet.com/BG_p_100.html",
            "stock_status": "in_stock",
            "metadata": {},
        },
        {
            "source": "blue_gauntlet",
            "source_id": "BG-GLOVE",
            "name": "BG glove",
            "brand": "Blue Gauntlet",
            "category": "Clearance",
            "weapon": "all",
            "price": 10.0,
            "currency": "USD",
            "image_url": None,
            "product_url": "https://www.blue-gauntlet.com/BG_p_100.html",
            "stock_status": "out_of_stock",
            "metadata": {},
        },
    ]

    written, failed, skipped = upsert_products(client, rows)

    assert (written, failed, skipped) == (1, 0, 0)
    assert client.upserts == [
        {
            "table": "fs_products",
            "rows": [rows[1]],
            "on_conflict": "source,source_id",
        }
    ]


def test_scrape_blue_gauntlet_products_fetches_details_logs_and_updates_state(monkeypatch):
    import scrape_blue_gauntlet_products as scraper

    detail_url = "https://www.blue-gauntlet.com/BG-soft-leather-3-wpn-universal-GLOVE_p_100.html"
    detail_html = DETAIL_FIXTURE.replace(
        "FIE Fencing Calendar 2026 Uhlmann/Allstar",
        "BG soft leather 3-wpn universal GLOVE",
    ).replace("UHAS-K02", "BG-GLOVE")

    fetched = {
        "https://www.blue-gauntlet.com/Clearance_c_311.html": CLEARANCE_LISTING_FIXTURE,
        detail_url: detail_html,
        "https://www.blue-gauntlet.com/Kempa-Attack-JUNIOR-Final-Sale_p_200.html": detail_html.replace(
            "BG-GLOVE", "KEMPA-ATTACK"
        ),
    }
    states = []
    run_logs = []

    def fake_fetcher(url):
        return fetched[url]

    def fake_run_logger(module):
        log = FakeRunLog(module)
        run_logs.append(log)
        return log

    monkeypatch.setattr(scraper, "get_state", lambda source, key: None)
    monkeypatch.setattr(scraper, "set_state", lambda source, key, value: states.append((source, key, value)))
    monkeypatch.setattr(scraper, "ScraperRunLogger", fake_run_logger)

    client = FakeClient()
    limiter = FakeLimiter()
    summary = scraper.scrape_blue_gauntlet_products(
        client=client,
        listing_urls=("https://www.blue-gauntlet.com/Clearance_c_311.html",),
        fetcher=fake_fetcher,
        rate_limiter=limiter,
    )

    assert summary["read"] == 2
    assert summary["written"] == 2
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert len(client.upserts[0]["rows"]) == 2
    assert {row["source_id"] for row in client.upserts[0]["rows"]} == {"BG-GLOVE", "KEMPA-ATTACK"}
    assert limiter.waits
    assert all(domain == "www.blue-gauntlet.com" for domain, _rps in limiter.waits)
    assert states[-1][0:2] == ("blue_gauntlet_products", "last_run")
    assert states[-1][2]["written"] == 2
    assert run_logs[0].module == "scrape_blue_gauntlet_products"
    assert run_logs[0].completed["written"] == 2
