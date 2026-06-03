import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"


EBAY_SEARCH_HTML = """
<html>
  <body>
    <ul class="srp-results">
      <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.com/itm/365935929238?itmmeta=abc">
          <span class="s-item__title">Leon Paul FIE Electric Epee Blade #5 - used once</span>
        </a>
        <span class="s-item__price">US $89.99</span>
        <span class="s-item__location s-item__itemLocation">from Brooklyn, New York</span>
        <span class="s-item__subtitle">Pre-Owned</span>
        <span class="s-item__sellerInfoText">Sold by jane.doe.fencing</span>
      </li>
      <li class="s-item">
        <a class="s-item__link" href="https://www.ebay.com/itm/226111222333">
          <span class="s-item__title">Absolute Fencing 1600N Mask Medium</span>
        </a>
        <span class="s-item__price">$120.00</span>
        <span class="s-item__location">from Austin, TX</span>
        <span class="s-item__subtitle">Used</span>
      </li>
      <li class="s-item s-item__pl-on-bottom">
        <a class="s-item__link" href="https://www.ebay.com/itm/placeholder"></a>
        <span class="s-item__title">Shop on eBay</span>
      </li>
    </ul>
  </body>
</html>
"""


GENERIC_MARKETPLACE_HTML = """
<html>
  <body>
    <article class="listing-card" data-listing-id="">
      <a href="/listing/used-scoring-box">Favero scoring machine with two body cords</a>
      <span class="price">EUR 175</span>
      <span class="location">Berlin, Germany</span>
      <span class="seller">Maria Seller</span>
      <p>Contact maria@example.test or +1 555 0100 for photos.</p>
    </article>
    <article class="listing-card" data-listing-id="">
      <a href="/listing/used-scoring-box?ref=mirror">Favero scoring machine with two body cords</a>
      <span class="price">EUR 175</span>
      <span class="location">Berlin, Germany</span>
    </article>
  </body>
</html>
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
        return FakeResult(self.pending_rows)


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_ebay_search_results_extracts_public_listing_metadata():
    from scrape_secondhand_equipment import parse_ebay_search_results

    rows = parse_ebay_search_results(
        EBAY_SEARCH_HTML,
        source_url="https://www.ebay.com/sch/i.html?_nkw=used+fencing+gear",
        scraped_at=NOW,
    )

    assert len(rows) == 2
    assert rows[0]["source"] == "ebay"
    assert rows[0]["listing_id"] == "365935929238"
    assert rows[0]["title"] == "Leon Paul FIE Electric Epee Blade #5 - used once"
    assert rows[0]["category"] == "weapon"
    assert rows[0]["weapon"] == "epee"
    assert rows[0]["price"] == 89.99
    assert rows[0]["currency"] == "USD"
    assert rows[0]["location"] == "Brooklyn, New York"
    assert rows[0]["listing_url"] == "https://www.ebay.com/itm/365935929238"
    assert rows[0]["status"] == "active"
    assert rows[0]["posted_at"] is None
    assert rows[0]["scraped_at"] == NOW
    assert rows[0]["metadata"]["condition"] == "Pre-Owned"
    assert rows[0]["metadata"]["source_url"].startswith("https://www.ebay.com/sch/")


def test_classify_listing_is_conservative_for_weapon_and_category():
    from scrape_secondhand_equipment import classify_listing

    assert classify_listing("Leon Paul FIE epee blade #5", "") == {
        "weapon": "epee",
        "category": "weapon",
    }
    assert classify_listing("Absolute Fencing mask 1600N", "") == {
        "weapon": None,
        "category": "protective_gear",
    }
    assert classify_listing("Foil lame jacket with body cord", "") == {
        "weapon": "foil",
        "category": "uniform",
    }
    assert classify_listing("Favero scoring machine and reel", "") == {
        "weapon": None,
        "category": "scoring_equipment",
    }
    assert classify_listing("Fencing gear bundle", "") == {
        "weapon": None,
        "category": "other",
    }


def test_metadata_minimizes_seller_pii_and_redacts_contact_details():
    from scrape_secondhand_equipment import parse_generic_listing_cards

    rows = parse_generic_listing_cards(
        GENERIC_MARKETPLACE_HTML,
        source="public_test_market",
        source_url="https://example.test/market",
        scraped_at=NOW,
    )

    assert len(rows) == 2
    seller_hash = hashlib.sha256("Maria Seller".encode("utf-8")).hexdigest()
    assert rows[0]["metadata"]["seller_display_hash"] == seller_hash
    serialized_metadata = repr(rows[0]["metadata"])
    assert "Maria Seller" not in serialized_metadata
    assert "maria@example.test" not in serialized_metadata
    assert "+1 555 0100" not in serialized_metadata
    assert "seller" not in rows[0]


def test_dedupe_uses_source_listing_id_and_url_hash_fallback():
    from scrape_secondhand_equipment import dedupe_listings

    first = {
        "source": "public_test_market",
        "listing_id": "",
        "title": "Favero scoring machine with two body cords",
        "listing_url": "https://example.test/listing/used-scoring-box",
        "metadata": {},
    }
    duplicate = {
        **first,
        "listing_url": "https://example.test/listing/used-scoring-box?utm_source=mirror",
    }
    different_source = {
        **first,
        "source": "other_market",
    }

    rows = dedupe_listings([first, duplicate, different_source])

    assert len(rows) == 2
    assert rows[0]["listing_id"].startswith("url_sha256:")
    assert rows[0]["metadata"]["dedupe_key"].startswith("public_test_market:")
    assert rows[0]["metadata"]["duplicate_listing_urls"] == [
        "https://example.test/listing/used-scoring-box?utm_source=mirror"
    ]


def test_upsert_secondhand_rows_uses_source_listing_id_conflict():
    from scrape_secondhand_equipment import upsert_secondhand_rows

    client = FakeSupabase()
    rows = [
        {
            "source": "ebay",
            "listing_id": "365935929238",
            "title": "Leon Paul FIE Electric Epee Blade #5",
            "category": "weapon",
            "weapon": "epee",
            "listing_url": "https://www.ebay.com/itm/365935929238",
            "metadata": {},
        }
    ]

    assert upsert_secondhand_rows(client, rows) == 1
    assert client.upserts == [
        {
            "table": "fs_secondhand_equipment",
            "rows": rows,
            "on_conflict": "source,listing_id",
        }
    ]


def test_secondhand_equipment_migration_defines_safe_idempotent_table():
    migration = Path("supabase/migrations/20260602_secondhand_equipment.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_secondhand_equipment" in normalized
    assert "source text not null" in normalized
    assert "listing_id text not null" in normalized
    assert "title text not null" in normalized
    assert "category text" in normalized
    assert "weapon text" in normalized
    assert "price numeric" in normalized
    assert "currency text" in normalized
    assert "location text" in normalized
    assert "listing_url text not null" in normalized
    assert "posted_at timestamptz" in normalized
    assert "status text" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "unique (source, listing_id)" in normalized
    assert "enable row level security" in normalized
