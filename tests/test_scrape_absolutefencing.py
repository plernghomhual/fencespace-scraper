import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]


LISTING_HTML = """
<html><body>
<ol class="products list items product-items">
  <li class="item product product-item">
    <a class="product-item-link" href="/absolute-men-s-f-z-foil-lame-30-64.html">
      ABSOLUTE MEN'S F/Z FOIL LAME (30 ~ 64)
    </a>
    <img class="product-image-photo" src="/media/catalog/product/cache/foil-lame.jpg" alt="Foil lame">
    <div class="price-box">As low as <span class="price">$82.00</span></div>
    <div class="stock available"><span>In stock</span></div>
  </li>
  <li class="item product product-item">
    <a class="product-item-link" href="/absolute-men-s-f-z-foil-lame-30-64.html">
      Duplicate should be ignored
    </a>
    <span class="price">$82.00</span>
  </li>
  <li class="item product product-item">
    <a class="product-item-link" href="https://www.absolutefencinggear.com/epee-complete-electric-set.html">
      Economy Epee Complete Electric Set
    </a>
    <span class="price">$119.50</span>
    <span class="stock unavailable">Out of Stock</span>
  </li>
</ol>
</body></html>
"""


DETAIL_HTML = """
<html><head>
  <meta property="og:image" content="https://www.absolutefencinggear.com/media/catalog/product/f/o/foil-lame.jpg">
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "sku": "AF-35011",
      "brand": {"@type": "Brand", "name": "Absolute Fencing"},
      "name": "Absolute Men's F/Z Foil Lame",
      "image": "https://www.absolutefencinggear.com/media/catalog/product/f/o/foil-lame-json.jpg",
      "offers": {
        "@type": "Offer",
        "price": "82.00",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock"
      }
    }
  </script>
</head><body>
  <div class="breadcrumbs">
    <a>Home</a><a>Uniforms</a><a>Lame</a><strong>Foil Lame</strong>
  </div>
  <span class="base" data-ui-id="page-title-wrapper">Absolute Men's F/Z Foil Lame</span>
  <div class="product attribute sku"><strong>SKU</strong><div class="value">AF-35011</div></div>
  <div class="product-info-price"><span class="price">$82.00</span></div>
  <div class="stock available"><span>In stock</span></div>
  <div class="product attribute description"><div class="value">FIE-ready foil lame for competition.</div></div>
</body></html>
"""


NOT_FOUND_HTML = "<html><body><h1>404 Not Found</h1></body></html>"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None

    def upsert(self, rows, on_conflict=None):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            }
        )
        return FakeResult(self.rows if isinstance(self.rows, list) else [self.rows])


class FakeClient:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_products_migration_defines_shared_table_shape():
    sql = (ROOT / "supabase/migrations/20260602_products.sql").read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_products" in normalized
    for column in [
        "source text not null",
        "source_id text not null",
        "name text not null",
        "brand text",
        "category text",
        "weapon text",
        "price numeric",
        "currency text default 'usd'",
        "image_url text",
        "product_url text not null",
        "stock_status text",
        "metadata jsonb default '{}'",
        "scraped_at timestamptz default now()",
    ]:
        assert column in normalized
    assert "unique (source, source_id)" in normalized
    assert "check (price is null or price >= 0)" in normalized
    assert "enable row level security" in normalized
    assert "grant select, insert, update, delete on public.fs_products to service_role" in normalized


def test_parse_listing_products_dedupes_and_normalizes_magento_cards():
    from scrape_absolutefencing import parse_listing_products

    rows = parse_listing_products(
        LISTING_HTML,
        listing_url="https://www.absolutefencinggear.com/uniforms/lame/foil",
        scraped_at="2026-06-02T00:00:00+00:00",
    )

    assert len(rows) == 2
    foil = rows[0]
    assert foil["source"] == "absolute_fencing"
    assert foil["source_id"] == "absolute-men-s-f-z-foil-lame-30-64"
    assert foil["name"] == "ABSOLUTE MEN'S F/Z FOIL LAME (30 ~ 64)"
    assert foil["brand"] == "Absolute Fencing"
    assert foil["category"] == "Lames"
    assert foil["weapon"] == "Foil"
    assert foil["price"] == pytest.approx(82.0)
    assert foil["currency"] == "USD"
    assert foil["stock_status"] == "in_stock"
    assert foil["product_url"] == "https://www.absolutefencinggear.com/absolute-men-s-f-z-foil-lame-30-64.html"
    assert foil["image_url"] == "https://www.absolutefencinggear.com/media/catalog/product/cache/foil-lame.jpg"
    assert foil["metadata"]["listing_url"].endswith("/uniforms/lame/foil")

    epee = rows[1]
    assert epee["weapon"] == "Epee"
    assert epee["category"] == "Weapon Sets"
    assert epee["stock_status"] == "out_of_stock"


def test_parse_product_detail_prefers_structured_data_and_sku_source_id():
    from scrape_absolutefencing import parse_product_detail

    row = parse_product_detail(
        DETAIL_HTML,
        product_url="https://www.absolutefencinggear.com/absolute-men-s-f-z-foil-lame-30-64.html",
        listing_row={"source_id": "absolute-men-s-f-z-foil-lame-30-64", "category": "Lames"},
        scraped_at="2026-06-02T00:00:00+00:00",
    )

    assert row["source"] == "absolute_fencing"
    assert row["source_id"] == "AF-35011"
    assert row["name"] == "Absolute Men's F/Z Foil Lame"
    assert row["brand"] == "Absolute Fencing"
    assert row["category"] == "Lames"
    assert row["weapon"] == "Foil"
    assert row["price"] == pytest.approx(82.0)
    assert row["currency"] == "USD"
    assert row["image_url"].endswith("foil-lame-json.jpg")
    assert row["stock_status"] == "in_stock"
    assert row["metadata"]["sku"] == "AF-35011"
    assert row["metadata"]["detail_status"] == "parsed"


def test_price_and_stock_normalization_handles_ranges_sale_and_unknowns():
    from scrape_absolutefencing import normalize_price, normalize_stock_status

    assert normalize_price("As low as $82.00") == (82.0, "USD")
    assert normalize_price("Regular Price $120.00 Special Price $99.95") == (99.95, "USD")
    assert normalize_price("Call for price") == (None, None)
    assert normalize_stock_status("In stock") == "in_stock"
    assert normalize_stock_status("Out of Stock") == "out_of_stock"
    assert normalize_stock_status("Backordered - ships soon") == "backorder"
    assert normalize_stock_status("") is None


def test_upsert_products_dedupes_by_source_and_source_id():
    from scrape_absolutefencing import upsert_products

    rows = [
        {"source": "absolute_fencing", "source_id": "AF-35011", "name": "A", "product_url": "https://example.test/a"},
        {"source": "absolute_fencing", "source_id": "AF-35011", "name": "A duplicate", "product_url": "https://example.test/a"},
        {"source": "absolute_fencing", "source_id": "AF-99001", "name": "B", "product_url": "https://example.test/b"},
    ]
    client = FakeClient()

    written, failed = upsert_products(client, rows)

    assert (written, failed) == (2, 0)
    assert client.upserts == [
        {
            "table": "fs_products",
            "rows": [rows[0], rows[2]],
            "on_conflict": "source,source_id",
        }
    ]


def test_scraper_handles_detail_404_and_records_state(monkeypatch):
    from scrape_absolutefencing import scrape_absolutefencing

    def fetcher(url):
        if url.endswith("/uniforms/lame/foil"):
            return LISTING_HTML
        if url.endswith("absolute-men-s-f-z-foil-lame-30-64.html"):
            return DETAIL_HTML
        if url.endswith("epee-complete-electric-set.html"):
            return None
        raise AssertionError(f"unexpected url: {url}")

    states = []
    monkeypatch.setattr("scrape_absolutefencing.get_state", lambda source, key: [] if key == "done_source_ids" else None)
    monkeypatch.setattr("scrape_absolutefencing.set_state", lambda source, key, value: states.append((source, key, value)))

    client = FakeClient()
    summary = scrape_absolutefencing(
        client=client,
        listing_urls=("https://www.absolutefencinggear.com/uniforms/lame/foil",),
        fetcher=fetcher,
        log_run=False,
        request_delay=0,
    )

    assert summary["read"] == 2
    assert summary["written"] == 2
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    upserted = client.upserts[0]["rows"]
    assert {row["source_id"] for row in upserted} == {"AF-35011", "epee-complete-electric-set"}
    fallback = next(row for row in upserted if row["source_id"] == "epee-complete-electric-set")
    assert fallback["metadata"]["detail_status"] == "not_found"
    assert states[-2][0:2] == ("absolute_fencing_products", "done_source_ids")
    assert set(states[-2][2]) == {
        "AF-35011",
        "absolute-men-s-f-z-foil-lame-30-64",
        "epee-complete-electric-set",
    }
    assert states[-1][0:2] == ("absolute_fencing_products", "last_run")


def test_incremental_run_skips_already_completed_source_ids(monkeypatch):
    from scrape_absolutefencing import scrape_absolutefencing

    def fetcher(url):
        if url.endswith("/uniforms/lame/foil"):
            return LISTING_HTML
        raise AssertionError(f"detail fetch should be skipped for {url}")

    monkeypatch.setattr(
        "scrape_absolutefencing.get_state",
        lambda source, key: ["absolute-men-s-f-z-foil-lame-30-64", "epee-complete-electric-set"]
        if key == "done_source_ids"
        else None,
    )
    monkeypatch.setattr("scrape_absolutefencing.set_state", lambda source, key, value: None)

    client = FakeClient()
    summary = scrape_absolutefencing(
        client=client,
        listing_urls=("https://www.absolutefencinggear.com/uniforms/lame/foil",),
        fetcher=fetcher,
        log_run=False,
        request_delay=0,
    )

    assert summary["read"] == 2
    assert summary["written"] == 0
    assert summary["skipped"] == 2
    assert client.upserts == []


def test_no_credentials_dry_run_uses_fixture_fetcher_without_upsert(monkeypatch):
    from scrape_absolutefencing import scrape_absolutefencing

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setattr("scrape_absolutefencing.get_state", lambda source, key: None)
    monkeypatch.setattr("scrape_absolutefencing.set_state", lambda source, key, value: None)

    summary = scrape_absolutefencing(
        client=None,
        listing_urls=("https://www.absolutefencinggear.com/uniforms/lame/foil",),
        fetcher=lambda url: LISTING_HTML if url.endswith("/uniforms/lame/foil") else NOT_FOUND_HTML,
        dry_run=True,
        log_run=False,
        request_delay=0,
    )

    assert summary["dry_run"] is True
    assert summary["read"] == 2
    assert summary["written"] == 0
    assert summary["skipped"] == 2
    assert summary["failed"] == 0
