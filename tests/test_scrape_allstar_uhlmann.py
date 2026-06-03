from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-06-02T00:00:00+00:00"


ALLSTAR_LISTING_HTML = """
<html><body>
<div class="cms-listing-row">
  <div class="cms-listing-col">
    <div class="card product-box box-standard" data-product-id="all-1000" data-product-number="350010">
      <a class="product-image-link" href="/en/startex-fie-fencing-jacket-men/350010-50-rh">
        <img src="/media/catalog/product/startex-men.jpg" alt="Startex FIE Fencing Jacket Men">
      </a>
      <a class="product-name" href="/en/startex-fie-fencing-jacket-men/350010-50-rh">
        Startex FIE Fencing Jacket Men
      </a>
      <div class="product-price-info">
        <span class="product-price">€309.00*</span>
      </div>
      <div class="delivery-information">Available, delivery time 2-5 days</div>
    </div>
  </div>
  <div class="cms-listing-col">
    <div class="card product-box box-standard" data-product-number="350010">
      <a class="product-name" href="/en/startex-fie-fencing-jacket-men/350010-50-rh">
        Duplicate Startex FIE Fencing Jacket Men
      </a>
      <span class="product-price">€309.00*</span>
    </div>
  </div>
</div>
</body></html>
"""


UHLMANN_LISTING_HTML = """
<html><body>
<div class="cms-listing-row">
  <div class="cms-listing-col">
    <div class="card product-box box-standard">
      <a class="product-image-link" href="/en/jacket-basic-boys-350n/100051-164-lh">
        <img data-src="/media/catalog/product/basic-boys.jpg" alt="jacket Basic boys 350N">
      </a>
      <a class="product-name" href="/en/jacket-basic-boys-350n/100051-164-lh">
        jacket "Basic" boys 350N
      </a>
      <div class="product-price">€99.00*</div>
      <div class="delivery-information">Planned for production</div>
    </div>
  </div>
  <div class="cms-listing-col">
    <div class="card product-box box-standard">
      <a class="product-name" href="/en/epee-blade-el.-compl.-french-mrf-bf-fie-blue-d-epee-point-lux/124137b-d-10048">
        epee blade el. compl. French MRF "BF" FIE, blue, D, epee point "LUX"
      </a>
      <span class="product-price">€219.80*</span>
    </div>
  </div>
</div>
</body></html>
"""


UHLMANN_DETAIL_HTML = """
<html><head>
  <meta property="og:image" content="https://uhlmann-fechtsport.com/media/catalog/product/basic-detail.jpg">
</head><body>
<nav class="breadcrumb">
  <a class="breadcrumb-link">Shop</a>
  <a class="breadcrumb-link">Clothing</a>
  <a class="breadcrumb-link">Fencing suits</a>
</nav>
<h1 class="product-detail-name">jacket "Basic" boys 350N</h1>
<div class="product-detail-price">€99.00*</div>
<div class="delivery-information">Planned for production</div>
<div class="product-detail-ordernumber-container">
  Product number: <span class="product-detail-ordernumber">100051/164/LH</span>
</div>
</body></html>
"""


NO_PRICE_LISTING_HTML = """
<html><body>
<div class="cms-listing-col">
  <div class="card product-box box-standard" data-product-number="MASK-LOGIN-1">
    <a class="product-name" href="/en/fie-mask-special/MASK-LOGIN-1">FIE mask special</a>
    <div class="product-price-info">Log in to view prices</div>
  </div>
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


def test_parse_allstar_shopware_listing_keeps_allstar_brand_and_eur_price():
    from scrape_allstar_uhlmann import ALLSTAR_UNIFORMS, parse_listing_products

    rows = parse_listing_products(ALLSTAR_LISTING_HTML, ALLSTAR_UNIFORMS, scraped_at=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "allstar"
    assert row["source_id"] == "350010"
    assert row["name"] == "Startex FIE Fencing Jacket Men"
    assert row["brand"] == "Allstar"
    assert row["category"] == "Uniforms"
    assert row["weapon"] is None
    assert row["price"] == pytest.approx(309.0)
    assert row["currency"] == "EUR"
    assert row["image_url"] == "https://allstar.de/media/catalog/product/startex-men.jpg"
    assert row["product_url"] == "https://allstar.de/en/startex-fie-fencing-jacket-men/350010-50-rh"
    assert row["stock_status"] == "in_stock"
    assert row["metadata"]["listing_url"].endswith("/en/clothing-footwear/uniforms/")


def test_parse_uhlmann_listing_and_detail_prefers_detail_product_number():
    from scrape_allstar_uhlmann import UHLMANN_FENCING_SUITS, build_product_row, parse_listing_products, parse_product_detail

    listing_rows = parse_listing_products(UHLMANN_LISTING_HTML, UHLMANN_FENCING_SUITS, scraped_at=NOW)
    detail = parse_product_detail(
        UHLMANN_DETAIL_HTML,
        product_url="https://uhlmann-fechtsport.com/en/jacket-basic-boys-350n/100051-164-lh",
        listing=UHLMANN_FENCING_SUITS,
    )
    row = build_product_row(listing_rows[0], detail, scraped_at=NOW)

    assert len(listing_rows) == 2
    assert row["source"] == "uhlmann"
    assert row["source_id"] == "100051/164/LH"
    assert row["name"] == 'jacket "Basic" boys 350N'
    assert row["brand"] == "Uhlmann"
    assert row["category"] == "Uniforms"
    assert row["weapon"] is None
    assert row["price"] == pytest.approx(99.0)
    assert row["currency"] == "EUR"
    assert row["stock_status"] == "planned_production"
    assert row["image_url"].endswith("basic-detail.jpg")
    assert row["metadata"]["listing_source_id"] == "100051-164-lh"
    assert row["metadata"]["sku"] == "100051/164/LH"

    blade = listing_rows[1]
    assert blade["source"] == "uhlmann"
    assert blade["brand"] == "Uhlmann"
    assert blade["category"] == "Weapons & Accessories"
    assert blade["weapon"] == "epee"
    assert blade["price"] == pytest.approx(219.8)


def test_normalizes_german_english_categories_weapons_and_eur_prices():
    from scrape_allstar_uhlmann import normalize_category, normalize_price, normalize_weapon

    assert normalize_category("Fechtanzüge") == "Uniforms"
    assert normalize_category("Fencing suits") == "Uniforms"
    assert normalize_category("Waffen und Zubehör") == "Weapons & Accessories"
    assert normalize_category("Degenklingen") == "Weapons & Accessories"
    assert normalize_category("Masken") == "Masks"
    assert normalize_category("Meldeanlagen") == "Scoring Equipment"

    assert normalize_weapon("Florettklinge") == "foil"
    assert normalize_weapon("Degen Körperkabel") == "epee"
    assert normalize_weapon("Säbel Maske") == "sabre"

    assert normalize_price("€148.50* €171.00* (13.16% saved)") == (pytest.approx(148.5), "EUR", "€148.50* €171.00* (13.16% saved)")
    assert normalize_price("1.234,50 €") == (pytest.approx(1234.5), "EUR", "1.234,50 €")
    assert normalize_price("Log in to view prices") == (None, None, "Log in to view prices")


def test_blocked_no_price_catalog_row_is_kept_with_reason():
    from scrape_allstar_uhlmann import UHLMANN_MASKS, parse_listing_products

    rows = parse_listing_products(NO_PRICE_LISTING_HTML, UHLMANN_MASKS, scraped_at=NOW)

    assert len(rows) == 1
    assert rows[0]["source"] == "uhlmann"
    assert rows[0]["source_id"] == "MASK-LOGIN-1"
    assert rows[0]["price"] is None
    assert rows[0]["currency"] is None
    assert rows[0]["category"] == "Masks"
    assert rows[0]["metadata"]["missing_price_reason"] == "price_not_public"
    assert rows[0]["metadata"]["price_text"] == "Log in to view prices"


def test_upsert_products_uses_shared_fs_products_conflict_key():
    from scrape_allstar_uhlmann import upsert_products

    client = FakeClient()
    rows = [
        {
            "source": "allstar",
            "source_id": "350010",
            "name": "Startex FIE Fencing Jacket Men",
            "brand": "Allstar",
            "category": "Uniforms",
            "weapon": None,
            "price": 309.0,
            "currency": "EUR",
            "image_url": "https://allstar.de/media/catalog/product/startex-men.jpg",
            "product_url": "https://allstar.de/en/startex-fie-fencing-jacket-men/350010-50-rh",
            "stock_status": "in_stock",
            "metadata": {},
            "scraped_at": NOW,
        },
        {
            "source": "allstar",
            "source_id": "350010",
            "name": "Duplicate",
            "brand": "Allstar",
            "product_url": "https://allstar.de/en/startex-fie-fencing-jacket-men/350010-50-rh",
        },
    ]

    written, failed = upsert_products(client, rows, batch_size=50)

    assert (written, failed) == (1, 0)
    assert client.upserts == [
        {
            "table": "fs_products",
            "rows": [rows[0]],
            "on_conflict": "source,source_id",
        }
    ]


def test_scraper_fetches_both_brands_writes_state_and_upserts(monkeypatch):
    from scrape_allstar_uhlmann import ALLSTAR_UNIFORMS, UHLMANN_FENCING_SUITS, scrape_allstar_uhlmann

    fetches = []
    states = []

    def fake_fetch(url):
        fetches.append(url)
        if url == ALLSTAR_UNIFORMS.listing_url:
            return ALLSTAR_LISTING_HTML
        if url == UHLMANN_FENCING_SUITS.listing_url:
            return UHLMANN_LISTING_HTML
        if url.endswith("startex-fie-fencing-jacket-men/350010-50-rh"):
            return None
        if url.endswith("jacket-basic-boys-350n/100051-164-lh"):
            return UHLMANN_DETAIL_HTML
        if url.endswith("epee-blade-el.-compl.-french-mrf-bf-fie-blue-d-epee-point-lux/124137b-d-10048"):
            return None
        raise AssertionError(f"unexpected fetch: {url}")

    monkeypatch.setattr("scrape_allstar_uhlmann.get_state", lambda source, key: None)
    monkeypatch.setattr("scrape_allstar_uhlmann.set_state", lambda source, key, value: states.append((source, key, value)))

    client = FakeClient()
    summary = scrape_allstar_uhlmann(
        client=client,
        listings=(ALLSTAR_UNIFORMS, UHLMANN_FENCING_SUITS),
        fetcher=fake_fetch,
        log_run=False,
        request_delay=0,
    )

    assert summary["read"] == 3
    assert summary["written"] == 3
    assert summary["failed"] == 0
    assert {row["source"] for row in client.upserts[0]["rows"]} == {"allstar", "uhlmann"}
    assert {row["brand"] for row in client.upserts[0]["rows"]} == {"Allstar", "Uhlmann"}
    assert fetches[:2] == [ALLSTAR_UNIFORMS.listing_url, ALLSTAR_UNIFORMS.detail_url_for("https://allstar.de/en/startex-fie-fencing-jacket-men/350010-50-rh")]
    assert states[-2][0:2] == ("allstar_uhlmann_products", "done_source_ids")
    assert "allstar:350010" in states[-2][2]
    assert "uhlmann:100051/164/LH" in states[-2][2]
    assert states[-1][0:2] == ("allstar_uhlmann_products", "last_run")
