from pathlib import Path
from typing import Any

import pytest

ABSOLUTE_FIXTURE = """
<html><body>
<ol class="products list items product-items">
  <li class="item product product-item">
    <a class="product-item-link" href="https://www.absolutefencinggear.com/absolute-men-s-f-z-foil-lame-30-64.html">
      ABSOLUTE MEN'S F/Z FOIL LAME (30 ~ 64)
    </a>
    <div class="price-box">As low as <span class="price">$82.00</span></div>
    <div class="rating-summary"><span style="width:80%">80%</span></div>
    <div class="reviews-actions"><a>3 Reviews</a></div>
  </li>
  <li class="item product product-item">
    <a class="product-item-link" href="https://www.absolutefencinggear.com/negrini-stainless-steel-men-s-foil-lame.html">
      Negrini Stainless Steel Men's Foil Lame
    </a>
    <div class="price-box">As low as <span class="price">$209.00</span></div>
  </li>
</ol>
</body></html>
"""


LEON_PAUL_FIXTURE = """
<html><body>
<ol class="products list items product-items">
  <li class="item product product-item">
    <a class="product-item-link" href="https://www.leonpaul.com/mens-apex-fie-jacket.html">
      Apex FIE Mens Jacket
    </a>
    <span class="price">£314.20</span>
    <span class="price">£261.83</span>
  </li>
</ol>
</body></html>
"""


BLUE_GAUNTLET_FIXTURE = """
<html><body>
<div class="product-item alternative">
  <a class="name" href="Special-Country-Flag-point-tape_p_4292.html">Special Country Flag point tape</a>
  <span class="reviews">(0)</span>
  <span class="price">Your Price: $11.99</span>
  <span>In Stock</span>
</div>
</body></html>
"""


ALLSTAR_FIXTURE = """
<html><body>
<div class="cms-listing-col col-sm-6 col-lg-4 col-xl-3">
  <div class="card product-box box-standard">
    <a class="product-name" href="https://allstar.de/en/ultralight-electric-jacket-men-foil/1165h-44-rh">
      UltraLight Electric Jacket Men Foil
    </a>
    <div class="product-description">UltraLight - the lightest allstar electric jacket.</div>
    <div class="product-price-info"><span class="product-price">€209.00</span></div>
    <span class="product-ordernumber">1165H</span>
  </div>
</div>
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


def test_parse_absolute_listing_extracts_products_rating_and_brand():
    from scrape_equipment_reviews import RETAILERS, parse_listing_products

    rows = parse_listing_products(ABSOLUTE_FIXTURE, RETAILERS["absolute_fencing"])

    assert len(rows) == 2
    assert rows[0]["product_name"] == "ABSOLUTE MEN'S F/Z FOIL LAME (30 ~ 64)"
    assert rows[0]["brand"] == "Absolute Fencing"
    assert rows[0]["category"] == "Lames"
    assert rows[0]["price"] == pytest.approx(82.0)
    assert rows[0]["currency"] == "USD"
    assert rows[0]["rating"] == pytest.approx(4.0)
    assert rows[0]["review_count"] == 3
    assert rows[0]["source"] == "absolute_fencing"
    assert rows[0]["url"].endswith("absolute-men-s-f-z-foil-lame-30-64.html")
    assert rows[1]["brand"] == "Negrini"


def test_parse_leon_paul_listing_uses_current_lowest_price_when_two_prices_exist():
    from scrape_equipment_reviews import RETAILERS, parse_listing_products

    rows = parse_listing_products(LEON_PAUL_FIXTURE, RETAILERS["leon_paul"])

    assert len(rows) == 1
    assert rows[0]["product_name"] == "Apex FIE Mens Jacket"
    assert rows[0]["brand"] == "Leon Paul"
    assert rows[0]["price"] == pytest.approx(261.83)
    assert rows[0]["currency"] == "GBP"


def test_parse_blue_gauntlet_listing_resolves_relative_urls_and_review_count():
    from scrape_equipment_reviews import RETAILERS, parse_listing_products

    rows = parse_listing_products(BLUE_GAUNTLET_FIXTURE, RETAILERS["blue_gauntlet"])

    assert len(rows) == 1
    assert rows[0]["product_name"] == "Special Country Flag point tape"
    assert rows[0]["brand"] == "Blue Gauntlet"
    assert rows[0]["price"] == pytest.approx(11.99)
    assert rows[0]["currency"] == "USD"
    assert rows[0]["review_count"] == 0
    assert rows[0]["url"] == "https://www.blue-gauntlet.com/Special-Country-Flag-point-tape_p_4292.html"


def test_parse_allstar_listing_extracts_shopware_product_cards():
    from scrape_equipment_reviews import RETAILERS, parse_listing_products

    rows = parse_listing_products(ALLSTAR_FIXTURE, RETAILERS["allstar"])

    assert len(rows) == 1
    assert rows[0]["product_name"] == "UltraLight Electric Jacket Men Foil"
    assert rows[0]["brand"] == "Allstar"
    assert rows[0]["category"] == "Electric Jackets"
    assert rows[0]["price"] == pytest.approx(209.0)
    assert rows[0]["currency"] == "EUR"
    assert rows[0]["metadata"]["sku"] == "1165H"


def test_upsert_equipment_reviews_uses_url_conflict_key():
    from scrape_equipment_reviews import upsert_equipment_reviews

    client = FakeClient()
    rows: list[dict[str, Any]] = [
        {
            "product_name": "Apex FIE Mens Jacket",
            "brand": "Leon Paul",
            "category": "Clothing",
            "rating": None,
            "review_count": None,
            "price": 261.83,
            "currency": "GBP",
            "source": "leon_paul",
            "url": "https://www.leonpaul.com/mens-apex-fie-jacket.html",
            "metadata": {},
        }
    ]

    written, failed = upsert_equipment_reviews(client, rows)

    assert (written, failed) == (1, 0)
    assert client.upserts == [
        {
            "table": "fs_equipment_reviews",
            "rows": rows,
            "on_conflict": "url",
        }
    ]


def test_scrape_equipment_reviews_populates_at_least_three_sources(monkeypatch):
    from scrape_equipment_reviews import (
        RETAILERS,
        scrape_equipment_reviews,
    )

    fixtures = {
        RETAILERS["absolute_fencing"].listing_urls[0]: ABSOLUTE_FIXTURE,
        RETAILERS["leon_paul"].listing_urls[0]: LEON_PAUL_FIXTURE,
        RETAILERS["blue_gauntlet"].listing_urls[0]: BLUE_GAUNTLET_FIXTURE,
    }
    states = []

    monkeypatch.setattr("scrape_equipment_reviews.get_state", lambda source, key: None)
    monkeypatch.setattr(
        "scrape_equipment_reviews.set_state",
        lambda source, key, value: states.append((source, key, value)),
    )

    client = FakeClient()
    result = scrape_equipment_reviews(
        client=client,
        retailers=[
            RETAILERS["absolute_fencing"],
            RETAILERS["leon_paul"],
            RETAILERS["blue_gauntlet"],
        ],
        fetcher=lambda url: fixtures[url],
        log_run=False,
    )

    assert result["written"] == 4
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["sources"] == 3
    assert {row["source"] for call in client.upserts for row in call["rows"]} == {
        "absolute_fencing",
        "leon_paul",
        "blue_gauntlet",
    }
    assert states[-1][0:2] == ("equipment_reviews", "last_run")
    assert states[-1][2]["written"] == 4


def test_equipment_reviews_migration_defines_table_constraints_and_service_role_access():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_equipment_reviews.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_equipment_reviews" in normalized
    assert "product_name text not null" in normalized
    assert "brand text not null" in normalized
    assert "rating numeric(3,1)" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "unique (url)" in normalized
    assert "enable row level security" in normalized
    assert "grant select, insert, update, delete on public.fs_equipment_reviews to service_role" in normalized
