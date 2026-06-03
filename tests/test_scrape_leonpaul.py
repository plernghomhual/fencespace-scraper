from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


LISTING_FIXTURE = """
<html><body>
<ol class="products list items product-items">
  <li class="item product product-item" data-product-id="1001" data-product-sku="J170A">
    <a class="product-item-link" href="/mens-apex-fie-jacket.html">
      Apex FIE Mens Jacket
    </a>
    <span class="price">£314.20</span>
    <span class="price">£261.83</span>
    <img class="product-image-photo" src="/media/catalog/product/a/p/apex-jacket.jpg" alt="Apex FIE Mens Jacket" />
  </li>
  <li class="item product product-item">
    <a class="product-item-link" href="https://www.leonpaul.com/lp-foil-blade.html">
      Leon Paul Foil Blade
    </a>
    <span class="price">$72.50</span>
    <div class="stock unavailable">Out of stock</div>
  </li>
</ol>
</body></html>
"""


DETAIL_FIXTURE = """
<html><body>
<div class="breadcrumbs">
  <a>Home</a><a>Fencing Clothing &amp; Uniforms</a><strong>Apex FIE Mens Jacket</strong>
</div>
<h1 class="page-title"><span>Apex FIE Mens Jacket</span></h1>
<div class="product attribute sku"><strong>SKU</strong><div class="value">J170A</div></div>
<div class="price-box">
  <span class="price">£314.20</span>
  <span class="price">£261.83</span>
</div>
<div class="stock available"><span>In stock</span></div>
<label for="attribute136">Size</label>
<select name="super_attribute[136]" id="attribute136">
  <option value="">Choose an Option...</option>
  <option value="52">Men's 52</option>
  <option value="54">Men's 54</option>
</select>
<div class="swatch-attribute" attribute-code="colour">
  <span class="swatch-attribute-label">Colour</span>
  <div class="swatch-option color" option-label="White"></div>
  <div class="swatch-option color" option-label="Black"></div>
</div>
</body></html>
"""


NO_PRICE_REGION_FIXTURE = """
<html><body>
<h1 class="page-title"><span>Region Redirect Product</span></h1>
<div class="product attribute sku"><div class="value">REDIRECT-1</div></div>
<div class="message notice">Please select your region to view prices.</div>
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


def test_parse_listing_extracts_leon_paul_product_cards():
    from scrape_leonpaul import parse_listing_products

    rows = parse_listing_products(
        LISTING_FIXTURE,
        "https://www.leonpaul.com/fencing-clothing-uniforms.html",
        category="Clothing",
    )

    assert len(rows) == 2
    assert rows[0]["source"] == "leon_paul"
    assert rows[0]["source_id"] == "J170A"
    assert rows[0]["name"] == "Apex FIE Mens Jacket"
    assert rows[0]["brand"] == "Leon Paul"
    assert rows[0]["category"] == "Clothing"
    assert rows[0]["weapon"] is None
    assert rows[0]["price"] == pytest.approx(261.83)
    assert rows[0]["currency"] == "GBP"
    assert rows[0]["image_url"] == "https://www.leonpaul.com/media/catalog/product/a/p/apex-jacket.jpg"
    assert rows[0]["product_url"] == "https://www.leonpaul.com/mens-apex-fie-jacket.html"
    assert rows[0]["stock_status"] == "unknown"
    assert rows[0]["metadata"]["listing_url"].endswith("fencing-clothing-uniforms.html")
    assert rows[1]["source_id"] == "lp-foil-blade"
    assert rows[1]["weapon"] == "foil"
    assert rows[1]["currency"] == "USD"
    assert rows[1]["stock_status"] == "out_of_stock"


def test_parse_detail_extracts_sku_category_stock_and_variants():
    from scrape_leonpaul import parse_detail_product

    detail = parse_detail_product(
        DETAIL_FIXTURE,
        "https://www.leonpaul.com/mens-apex-fie-jacket.html",
    )

    assert detail["source_id"] == "J170A"
    assert detail["name"] == "Apex FIE Mens Jacket"
    assert detail["category"] == "Fencing Clothing & Uniforms"
    assert detail["price"] == pytest.approx(261.83)
    assert detail["currency"] == "GBP"
    assert detail["stock_status"] == "in_stock"
    assert detail["variant_options"] == {
        "Size": ["Men's 52", "Men's 54"],
        "Colour": ["White", "Black"],
    }


def test_parse_price_normalizes_currency_symbols_and_missing_prices():
    from scrape_leonpaul import parse_price

    assert parse_price("£314.20 £261.83") == (pytest.approx(261.83), "GBP", "£314.20 £261.83")
    assert parse_price("Now USD $1,234.50") == (pytest.approx(1234.50), "USD", "Now USD $1,234.50")
    assert parse_price("€209,00") == (pytest.approx(209.0), "EUR", "€209,00")
    assert parse_price("Please select your region to view prices.") == (
        None,
        None,
        "Please select your region to view prices.",
    )


def test_build_product_row_prefers_detail_sku_and_records_region_price_blocker():
    from scrape_leonpaul import build_product_row, parse_detail_product, parse_listing_products

    listing_row = parse_listing_products(
        LISTING_FIXTURE,
        "https://www.leonpaul.com/fencing-clothing-uniforms.html",
        category="Clothing",
    )[0]
    detail = parse_detail_product(
        NO_PRICE_REGION_FIXTURE,
        "https://www.leonpaul.com/mens-apex-fie-jacket.html",
    )

    row = build_product_row(listing_row, detail, scraped_at="2026-06-02T00:00:00+00:00")

    assert row["source_id"] == "REDIRECT-1"
    assert row["name"] == "Region Redirect Product"
    assert row["price"] == pytest.approx(261.83)
    assert row["currency"] == "GBP"
    assert row["metadata"]["detail_missing_price_reason"] == "region_or_price_not_visible"
    assert row["scraped_at"] == "2026-06-02T00:00:00+00:00"


def test_upsert_products_uses_shared_source_source_id_conflict_key():
    from scrape_leonpaul import upsert_products

    client = FakeClient()
    rows = [
        {
            "source": "leon_paul",
            "source_id": "J170A",
            "name": "Apex FIE Mens Jacket",
            "brand": "Leon Paul",
            "category": "Clothing",
            "weapon": None,
            "price": 261.83,
            "currency": "GBP",
            "image_url": "https://www.leonpaul.com/media/catalog/product/a/p/apex-jacket.jpg",
            "product_url": "https://www.leonpaul.com/mens-apex-fie-jacket.html",
            "stock_status": "in_stock",
            "metadata": {"variant_options": {"Size": ["Men's 52"]}},
            "scraped_at": "2026-06-02T00:00:00+00:00",
        }
    ]

    written, failed = upsert_products(client, rows, batch_size=50)

    assert (written, failed) == (1, 0)
    assert client.upserts == [
        {
            "table": "fs_products",
            "rows": rows,
            "on_conflict": "source,source_id",
        }
    ]


def test_scrape_leonpaul_fetches_details_writes_state_and_upserts(monkeypatch):
    from scrape_leonpaul import scrape_leonpaul

    states = []
    fetches = []
    client = FakeClient()

    def fake_fetch(url):
        fetches.append(url)
        if url.endswith("fencing-clothing-uniforms.html"):
            return {"html": LISTING_FIXTURE, "url": url}
        return {"html": DETAIL_FIXTURE, "url": url}

    monkeypatch.setattr("scrape_leonpaul.get_state", lambda source, key: None)
    monkeypatch.setattr("scrape_leonpaul.set_state", lambda source, key, value: states.append((source, key, value)))

    summary = scrape_leonpaul(
        client=client,
        category_urls={"Clothing": "https://www.leonpaul.com/fencing-clothing-uniforms.html"},
        fetcher=fake_fetch,
        log_run=False,
        max_products=1,
    )

    assert summary["read"] == 1
    assert summary["written"] == 1
    assert summary["failed"] == 0
    assert fetches == [
        "https://www.leonpaul.com/fencing-clothing-uniforms.html",
        "https://www.leonpaul.com/mens-apex-fie-jacket.html",
    ]
    assert client.upserts[0]["table"] == "fs_products"
    assert states[-1][0:2] == ("leon_paul", "last_run")
    assert states[-1][2]["written"] == 1


def test_products_migration_defines_shared_schema_for_catalog_scrapers():
    migration = ROOT / "supabase" / "migrations" / "20260602_products.sql"
    sql = " ".join(migration.read_text().lower().split())

    assert "create table if not exists public.fs_products" in sql
    assert "source text not null" in sql
    assert "source_id text not null" in sql
    assert "name text not null" in sql
    assert "brand text not null" in sql
    assert "price numeric" in sql
    assert "currency text" in sql
    assert "image_url text" in sql
    assert "product_url text not null" in sql
    assert "stock_status text" in sql
    assert "metadata jsonb default '{}'" in sql
    assert "unique (source, source_id)" in sql
    assert "enable row level security" in sql
