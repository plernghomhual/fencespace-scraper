from pathlib import Path

PBT_DEALERS_HTML = """
<html><body>
  <h1>DEALERS</h1>
  <div class="panel">
    <div class="panel-heading"><h5>United States</h5></div>
    <div class="panel-body">
      <p><strong>East Coast - Blue Gauntlet</strong></p>
      <p>280 North Midland Ave.<br>Bldg W, suite 138<br>
      Saddle Brook, NJ. 07663<br>Tel.: 201-797-3332<br>
      Email: service@blue-gauntletservice.com</p>
      <a href="https://www.blue-gauntlet.com">Website</a>
      <hr>
      <p><strong>West Coast - The Fencing Post</strong></p>
      <p>Saul &amp; Victoria Mendoza<br>Suite D<br>
      1770 S. Escondido Blvd<br>Escondido, CA 92025</p>
      <a href="https://www.thefencingpost.com">Website</a>
    </div>
  </div>
  <div class="panel">
    <div class="panel-heading"><h5>Belgium - EXCLUSIVE</h5></div>
    <div class="panel-body">
      <p><strong>HLVDM Solutions VOF</strong></p>
      <p>Lange Violettestraat 128<br>9000 Ghent<br>Belgium<br>
      Email: info@schermwinkel.be</p>
      <a href="https://www.schermwinkel.be">Website</a>
    </div>
  </div>
</body></html>
"""


PBT_DEALER_NODE_HTML = """
<html><body>
  <div class="panel">
    <div class="panel-heading"><h5>Australia</h5></div>
    <div class="panel-collapse collapse">
      <div class="dealer">
        <div class="name"><strong>Melbourne Area P.I. Design Pty Ltd</strong></div>
        <div class="content">
          <p><strong>Haluk Yeter<br></strong>Chadstone Victoria 3148<br>
          <strong>Phone:</strong> 613 9808 3843<br>
          <strong>Email:</strong> <a href="mailto:halukyeter@bigpond.com">halukyeter@bigpond.com</a></p>
          <a href="http://pidesign.com.au">Website</a>
        </div>
      </div>
    </div>
  </div>
</body></html>
"""


UHLMANN_DISTRIBUTORS_HTML = """
<html><body>
  <main>
    <h1>Distributors</h1>
    <ul>
      <li>
        <strong>Blue Gauntlet Fencing Gear Inc.</strong><br>
        Building K<br>
        280 N. Midland Ave<br>
        07663 Saddle Brook<br>
        United States of America<br>
        <a href="https://www.blue-gauntlet.com">Merchant URL</a>
        <a href="tel:+12017973332">Call</a>
        <a href="mailto:service@blue-gauntletservice.com">Mail</a>
      </li>
      <li>
        <strong>Escrime Diffusion</strong><br>
        66 Bd du Maréchal Joffre<br>
        92340 Bourg la Reine<br>
        France<br>
        <a href="https://www.escrime-diffusion.fr">Shop</a>
      </li>
    </ul>
  </main>
</body></html>
"""


BLUE_GAUNTLET_CONTACT_HTML = """
<html><body>
  <h1>Contact Us</h1>
  <h3>Blue Gauntlet</h3>
  <p>280 North Midland Ave.</p>
  <p>Bldg K</p>
  <p>Saddle Brook, NJ. 07663</p>
  <p>US</p>
  <p>Phone: 201-797-3332 or 1-800-819-5180</p>
  <h3>Business Hours:</h3>
</body></html>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None

    def upsert(self, rows, on_conflict):
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
        return FakeResult([])


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_fencing_stores_migration_defines_table_and_dedupe_constraint():
    migration = Path("supabase/migrations/20260602_fencing_stores.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencing_stores" in normalized
    assert "name text not null" in normalized
    assert "brand text" in normalized
    assert "source text not null" in normalized
    assert "website text" in normalized
    assert "city text" in normalized
    assert "country text" in normalized
    assert "address text" in normalized
    assert "latitude numeric" in normalized
    assert "longitude numeric" in normalized
    assert "phone text" in normalized
    assert "email text" in normalized
    assert "source_url text" in normalized
    assert "metadata jsonb not null default '{}'" in normalized
    assert "scraped_at timestamptz not null default now()" in normalized
    assert "dedupe_key text not null" in normalized
    assert "unique (dedupe_key)" in normalized
    assert "enable row level security" in normalized
    assert "idx_fs_fencing_stores_country_city" in normalized


def test_parse_pbt_dealers_extracts_country_grouped_dealers():
    from scrape_fencing_stores import StoreSource, parse_pbt_dealers

    source = StoreSource(
        source="pbt_dealers",
        brand="PBT Fencing",
        url="https://shop.pbtfencing.com/dealers?lang=euro_foreign",
        parser="pbt_dealers",
    )

    stores = parse_pbt_dealers(PBT_DEALERS_HTML, source)

    assert len(stores) == 3
    blue = stores[0]
    assert blue["name"] == "East Coast - Blue Gauntlet"
    assert blue["brand"] == "PBT Fencing"
    assert blue["source"] == "pbt_dealers"
    assert blue["country"] == "United States"
    assert blue["city"] == "Saddle Brook"
    assert blue["address"] == "280 North Midland Ave., Bldg W, suite 138, Saddle Brook, NJ. 07663"
    assert blue["phone"] == "201-797-3332"
    assert blue["email"] == "service@blue-gauntletservice.com"
    assert blue["website"] == "https://www.blue-gauntlet.com"
    assert blue["source_url"] == source.url
    assert blue["metadata"]["parser"] == "pbt_dealers"


def test_parse_pbt_dealers_extracts_live_dealer_nodes():
    from scrape_fencing_stores import StoreSource, parse_pbt_dealers

    source = StoreSource(
        source="pbt_dealers",
        brand="PBT Fencing",
        url="https://shop.pbtfencing.com/dealers?lang=euro_foreign",
        parser="pbt_dealers",
    )

    stores = parse_pbt_dealers(PBT_DEALER_NODE_HTML, source)

    assert len(stores) == 1
    store = stores[0]
    assert store["name"] == "Melbourne Area P.I. Design Pty Ltd"
    assert store["country"] == "Australia"
    assert store["address"] == "Chadstone Victoria 3148"
    assert store["phone"] == "613 9808 3843"
    assert store["email"] == "halukyeter@bigpond.com"
    assert store["website"] == "http://pidesign.com.au"


def test_parse_uhlmann_distributors_extracts_list_items():
    from scrape_fencing_stores import StoreSource, parse_uhlmann_distributors

    source = StoreSource(
        source="uhlmann_distributors",
        brand="Uhlmann",
        url="https://uhlmann-fechtsport.com/en/company/distributors/",
        parser="uhlmann_distributors",
    )

    stores = parse_uhlmann_distributors(UHLMANN_DISTRIBUTORS_HTML, source)

    assert len(stores) == 2
    assert stores[0]["name"] == "Blue Gauntlet Fencing Gear Inc."
    assert stores[0]["country"] == "United States of America"
    assert stores[0]["city"] == "Saddle Brook"
    assert stores[0]["address"] == "Building K, 280 N. Midland Ave, 07663 Saddle Brook"
    assert stores[0]["phone"] == "+12017973332"
    assert stores[0]["email"] == "service@blue-gauntletservice.com"
    assert stores[0]["website"] == "https://www.blue-gauntlet.com"
    assert stores[1]["name"] == "Escrime Diffusion"
    assert stores[1]["city"] == "Bourg la Reine"
    assert stores[1]["country"] == "France"


def test_parse_contact_store_extracts_single_retail_location():
    from scrape_fencing_stores import StoreSource, parse_contact_store

    source = StoreSource(
        source="blue_gauntlet_contact",
        brand="Blue Gauntlet",
        url="https://www.blue-gauntlet.com/crm.asp?action=contactus",
        parser="contact_store",
        default_name="Blue Gauntlet",
        default_country="United States",
    )

    stores = parse_contact_store(BLUE_GAUNTLET_CONTACT_HTML, source)

    assert len(stores) == 1
    store = stores[0]
    assert store["name"] == "Blue Gauntlet"
    assert store["address"] == "280 North Midland Ave., Bldg K, Saddle Brook, NJ. 07663"
    assert store["city"] == "Saddle Brook"
    assert store["country"] == "United States"
    assert store["phone"] == "201-797-3332"


def test_normalized_name_address_country_dedupes_cross_source_duplicates():
    from scrape_fencing_stores import dedupe_stores, normalize_dedupe_key

    first = {
        "name": "Blue Gauntlet Fencing Gear Inc.",
        "brand": "Uhlmann",
        "source": "uhlmann_distributors",
        "address": "Building K, 280 N. Midland Ave, 07663 Saddle Brook",
        "country": "United States of America",
        "source_url": "https://uhlmann.example/distributors",
        "metadata": {"parser": "uhlmann_distributors"},
    }
    duplicate = {
        "name": "Blue Gauntlet Fencing Gear Inc",
        "brand": "PBT Fencing",
        "source": "pbt_dealers",
        "address": "Building K 280 North Midland Avenue Saddle Brook NJ 07663",
        "country": "USA",
        "source_url": "https://pbt.example/dealers",
        "metadata": {"parser": "pbt_dealers"},
    }
    different_address = {
        **first,
        "address": "150 West 28th Street, New York, NY 10001",
        "source_url": "https://other.example/dealers",
    }

    assert normalize_dedupe_key(first) == normalize_dedupe_key(duplicate)

    stores = dedupe_stores([first, duplicate, different_address])

    assert len(stores) == 2
    merged = stores[0]
    assert merged["dedupe_key"] == normalize_dedupe_key(first)
    assert merged["metadata"]["duplicate_source_urls"] == ["https://pbt.example/dealers"]
    assert merged["metadata"]["sources"] == ["uhlmann_distributors", "pbt_dealers"]
    assert merged["metadata"]["brands"] == ["Uhlmann", "PBT Fencing"]


def test_scrape_fencing_stores_upserts_without_geocoder_and_rate_limits():
    from scrape_fencing_stores import FetchedContent, StoreSource, scrape_fencing_stores

    sources = [
        StoreSource(
            source="blue_gauntlet_contact",
            brand="Blue Gauntlet",
            url="https://www.blue-gauntlet.com/crm.asp?action=contactus",
            parser="contact_store",
            default_name="Blue Gauntlet",
            default_country="United States",
        ),
        StoreSource(
            source="blue_gauntlet_contact_mirror",
            brand="Blue Gauntlet",
            url="https://mirror.example/blue-gauntlet",
            parser="contact_store",
            default_name="Blue Gauntlet",
            default_country="USA",
        ),
    ]

    def fetcher(source):
        return FetchedContent(
            content=BLUE_GAUNTLET_CONTACT_HTML.encode("utf-8"),
            content_type="text/html",
            final_url=source.url,
        )

    slept = []
    client = FakeSupabase()

    summary = scrape_fencing_stores(
        client=client,
        sources=sources,
        fetcher=fetcher,
        geocoder=None,
        sleeper=lambda seconds: slept.append(seconds),
        request_delay=0.25,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "sources": 2,
        "parsed": 2,
        "written": 1,
        "failed": 0,
        "skipped": 0,
        "missing_location": 0,
        "ambiguous_location": 0,
    }
    assert slept == [0.25]
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencing_stores"
    assert upsert["on_conflict"] == "dedupe_key"
    row = upsert["rows"][0]
    assert row["name"] == "Blue Gauntlet"
    assert row["latitude"] is None
    assert row["longitude"] is None
    assert row["dedupe_key"]
