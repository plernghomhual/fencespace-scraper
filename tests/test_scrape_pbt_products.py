import pytest


LISTING_HTML = """
<html><body>
<ol class="products list items product-items">
  <li class="item product product-item">
    <div class="product-item-info">
      <a class="product photo product-item-photo"
         href="https://shop.pbtfencing.com/electric-sabre-jacket-inox-washable-for-men1001?lang=euro_foreign">
        <span class="product-image-container">
          <img class="product-image-photo"
               src="/media/catalog/product/cache/sabre-jacket.jpg"
               alt="Electric sabre jacket INOX, washable for men.." />
        </span>
      </a>
      <strong class="product name product-item-name">
        <a class="product-item-link"
           href="https://shop.pbtfencing.com/electric-sabre-jacket-inox-washable-for-men1001?lang=euro_foreign">
          Electric sabre jacket INOX, washable for men..
        </a>
      </strong>
      <span class="price-container price-final_price">
        <span class="old-price"><span class="price">203,20 €</span></span>
        <span class="special-price"><span class="price">160,00 €</span></span>
      </span>
      <button title="Add to Cart">Add to Cart</button>
    </div>
  </li>
  <li class="item product product-item">
    <a class="product-item-link" href="/foil-mask-fie-1600n3301">
      Foil mask FIE 1600 N
    </a>
    <span class="price">€120.50</span>
    <div class="stock unavailable">Out of stock</div>
  </li>
</ol>
</body></html>
"""


DETAIL_HTML = """
<html><head>
  <meta property="og:image" content="https://shop.pbtfencing.com/media/catalog/product/primera.jpg" />
</head><body>
  <nav class="breadcrumbs">
    <a href="/">Home</a>
    <a href="/webshop/fencing-clothing-2">Fencing clothing</a>
    <a href="/webshop/uniforms-protectors">Uniforms &amp; protectors</a>
    <a href="/webshop/800n-fie-uniforms">800N FIE uniforms</a>
  </nav>
  <h1 class="page-title"><span>Electric foil jacket INOX PINK, washable for women</span></h1>
  <div class="product-info-main">
    <div class="price-box price-final_price">
      <span class="old-price"><span class="price">216,03 €</span></span>
      <span class="special-price"><span class="price">170,10 €</span></span>
    </div>
    <div class="stock available">Only %1 left</div>
    <div class="product attribute sku">
      <strong>SKU</strong>
      <div class="value">25002</div>
    </div>
    <div class="product attribute overview">
      <div class="value">Women foil electric jacket with washable INOX lame.</div>
    </div>
    <div class="swatch-attribute size">
      <span class="swatch-attribute-label">Méret</span>
      <div class="swatch-attribute-options">
        <div class="swatch-option text">38</div>
        <div class="swatch-option text">40</div>
        <div class="swatch-option text">42</div>
      </div>
    </div>
    <select id="attribute84" name="super_attribute[84]">
      <option value="">Choose Size</option>
      <option value="44">44</option>
      <option value="46">46</option>
    </select>
  </div>
  <table class="data table additional-attributes">
    <tr><th>weapon</th><td>Foil</td></tr>
    <tr><th>type</th><td>Women</td></tr>
    <tr><th>Level</th><td>FIE</td></tr>
  </table>
  <div class="size-chart">
    <table>
      <tr><th>Order size</th><td>38</td><td>40</td><td>42</td></tr>
      <tr><th>Height cm I</th><td>158-164</td><td>164-170</td><td>164-170</td></tr>
      <tr><th>Sleeve lenght F</th><td>59</td><td>60</td><td>61</td></tr>
    </table>
  </div>
</body></html>
"""


HUNGARIAN_DETAIL_HTML = """
<html><body>
  <h1>Penge Dynamo-PBT párbajtőr</h1>
  <span class="price">28 490 Ft</span>
  <div class="product attribute sku"><strong>Cikkszám</strong><div class="value">3556</div></div>
  <table class="data table additional-attributes">
    <tr><th>Fegyvernem</th><td>Párbajtőr</td></tr>
    <tr><th>Készlet</th><td>Nincs készleten</td></tr>
  </table>
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


def test_parse_listing_products_extracts_magento_cards_and_normalizes_fields():
    from scrape_pbt_products import parse_listing_products

    rows = parse_listing_products(
        LISTING_HTML,
        listing_url="https://shop.pbtfencing.com/webshop/fencing-clothing-2?lang=euro_foreign",
        category_hint="Fencing clothing",
        scraped_at="2026-06-02T12:00:00+00:00",
    )

    assert len(rows) == 2
    assert rows[0]["source"] == "pbt"
    assert rows[0]["source_id"] == "electric-sabre-jacket-inox-washable-for-men1001"
    assert rows[0]["name"] == "Electric sabre jacket INOX, washable for men.."
    assert rows[0]["brand"] == "PBT"
    assert rows[0]["category"] == "Fencing Clothing"
    assert rows[0]["weapon"] == "sabre"
    assert rows[0]["price"] == pytest.approx(160.0)
    assert rows[0]["currency"] == "EUR"
    assert rows[0]["stock_status"] == "in_stock"
    assert rows[0]["image_url"] == "https://shop.pbtfencing.com/media/catalog/product/cache/sabre-jacket.jpg"
    assert rows[0]["product_url"].endswith("electric-sabre-jacket-inox-washable-for-men1001?lang=euro_foreign")
    assert rows[0]["metadata"]["listing_url"].endswith("fencing-clothing-2?lang=euro_foreign")
    assert rows[0]["scraped_at"] == "2026-06-02T12:00:00+00:00"

    assert rows[1]["source_id"] == "foil-mask-fie-1600n3301"
    assert rows[1]["weapon"] == "foil"
    assert rows[1]["price"] == pytest.approx(120.5)
    assert rows[1]["stock_status"] == "out_of_stock"


def test_parse_product_detail_extracts_sku_categories_images_stock_and_size_metadata():
    from scrape_pbt_products import parse_product_detail

    row = parse_product_detail(
        DETAIL_HTML,
        product_url="https://shop.pbtfencing.com/fencing-jacket-fie-800-n-primera-for-men25002?lang=euro_foreign",
        listing_row={"metadata": {"listing_url": "https://shop.pbtfencing.com/webshop/fencing-clothing-2"}},
        scraped_at="2026-06-02T12:00:00+00:00",
    )

    assert row["source"] == "pbt"
    assert row["source_id"] == "25002"
    assert row["name"] == "Electric foil jacket INOX PINK, washable for women"
    assert row["brand"] == "PBT"
    assert row["category"] == "Uniforms & Protectors"
    assert row["weapon"] == "foil"
    assert row["price"] == pytest.approx(170.1)
    assert row["currency"] == "EUR"
    assert row["image_url"] == "https://shop.pbtfencing.com/media/catalog/product/primera.jpg"
    assert row["stock_status"] == "limited"
    assert row["product_url"].endswith("fencing-jacket-fie-800-n-primera-for-men25002?lang=euro_foreign")
    assert row["metadata"]["sku"] == "25002"
    assert row["metadata"]["type"] == "Women"
    assert row["metadata"]["level"] == "FIE"
    assert row["metadata"]["sizes"] == ["38", "40", "42", "44", "46"]
    assert row["metadata"]["size_chart"]["Order size"] == ["38", "40", "42"]
    assert row["metadata"]["size_chart"]["Height cm I"] == ["158-164", "164-170", "164-170"]


def test_parse_product_detail_normalizes_hungarian_labels_stock_and_huf_price():
    from scrape_pbt_products import parse_product_detail

    row = parse_product_detail(
        HUNGARIAN_DETAIL_HTML,
        product_url="https://shop.pbtfencing.com/penge-dynamo-pbt-parbajtor3556?lang=hu",
    )

    assert row["source_id"] == "3556"
    assert row["weapon"] == "epee"
    assert row["price"] == pytest.approx(28490.0)
    assert row["currency"] == "HUF"
    assert row["stock_status"] == "out_of_stock"
    assert row["metadata"]["sku"] == "3556"


@pytest.mark.parametrize(
    ("raw", "expected_price", "expected_currency"),
    [
        ("As low as €279.40 €220.00", 220.0, "EUR"),
        ("203,20 € 160,00 €", 160.0, "EUR"),
        ("From $1,250.50", 1250.5, "USD"),
        ("28 490 Ft", 28490.0, "HUF"),
        ("No public price", None, None),
    ],
)
def test_parse_price_handles_prefix_suffix_multilingual_prices(raw, expected_price, expected_currency):
    from scrape_pbt_products import parse_price

    price, currency = parse_price(raw)

    if expected_price is None:
        assert price is None
    else:
        assert price == pytest.approx(expected_price)
    assert currency == expected_currency


def test_upsert_product_rows_uses_shared_product_schema_conflict_key():
    from scrape_pbt_products import upsert_product_rows

    client = FakeClient()
    rows = [
        {
            "source": "pbt",
            "source_id": "25002",
            "name": "Electric foil jacket INOX PINK, washable for women",
            "brand": "PBT",
            "category": "Uniforms & Protectors",
            "weapon": "foil",
            "price": 170.1,
            "currency": "EUR",
            "image_url": "https://shop.pbtfencing.com/media/catalog/product/primera.jpg",
            "product_url": "https://shop.pbtfencing.com/fencing-jacket-fie-800-n-primera-for-men25002",
            "stock_status": "limited",
            "metadata": {"sku": "25002"},
            "scraped_at": "2026-06-02T12:00:00+00:00",
        }
    ]

    written, failed = upsert_product_rows(client, rows, batch_size=100)

    assert (written, failed) == (1, 0)
    assert client.upserts == [
        {
            "table": "fs_products",
            "rows": rows,
            "on_conflict": "source,source_id",
        }
    ]


def test_scrape_pbt_products_fetches_details_rate_limits_and_records_state(monkeypatch):
    import scrape_pbt_products

    listing_url = "https://shop.pbtfencing.com/webshop/fencing-clothing-2?lang=euro_foreign"
    detail_url = "https://shop.pbtfencing.com/electric-sabre-jacket-inox-washable-for-men1001?lang=euro_foreign"
    fixtures = {
        listing_url: LISTING_HTML,
        detail_url: DETAIL_HTML,
        "https://shop.pbtfencing.com/foil-mask-fie-1600n3301": HUNGARIAN_DETAIL_HTML,
    }
    states = []
    sleeps = []

    monkeypatch.setattr(scrape_pbt_products, "get_state", lambda source, key: None)
    monkeypatch.setattr(
        scrape_pbt_products,
        "set_state",
        lambda source, key, value: states.append((source, key, value)),
    )
    monkeypatch.setattr(scrape_pbt_products.time, "sleep", lambda seconds: sleeps.append(seconds))

    client = FakeClient()
    summary = scrape_pbt_products.scrape_pbt_products(
        client=client,
        listing_urls=(listing_url,),
        fetcher=lambda url: fixtures[url],
        request_delay=0.25,
        log_run=False,
    )

    assert summary["read"] == 2
    assert summary["written"] == 2
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert client.upserts[0]["table"] == "fs_products"
    assert {row["source_id"] for row in client.upserts[0]["rows"]} == {"25002", "3556"}
    assert states[-1][0:2] == ("pbt_products", "last_run")
    assert states[-1][2]["written"] == 2
    assert sleeps == [0.25, 0.25]


def test_scrape_pbt_products_follows_category_pagination(monkeypatch):
    import scrape_pbt_products

    first_page = """
    <html><body>
      <ol class="products">
        <li class="product-item">
          <a class="product-item-link" href="/first-product1001">First sabre product</a>
          <span class="price">10,00 €</span>
        </li>
      </ol>
      <div class="pages">
        <a class="page" href="/webshop/fencing-clothing-2?p=2&amp;lang=euro_foreign">Page 2</a>
      </div>
    </body></html>
    """
    second_page = """
    <html><body>
      <ol class="products">
        <li class="product-item">
          <a class="product-item-link" href="/second-product2002">Second foil product</a>
          <span class="price">20,00 €</span>
        </li>
      </ol>
    </body></html>
    """
    first_detail = """
    <html><body><h1>First sabre product</h1><span class="price">10,00 €</span>
    <div class="product attribute sku"><strong>SKU</strong><div class="value">1001</div></div></body></html>
    """
    second_detail = """
    <html><body><h1>Second foil product</h1><span class="price">20,00 €</span>
    <div class="product attribute sku"><strong>SKU</strong><div class="value">2002</div></div></body></html>
    """
    listing_url = "https://shop.pbtfencing.com/webshop/fencing-clothing-2?lang=euro_foreign"
    second_listing_url = "https://shop.pbtfencing.com/webshop/fencing-clothing-2?p=2&lang=euro_foreign"
    fixtures = {
        listing_url: first_page,
        second_listing_url: second_page,
        "https://shop.pbtfencing.com/first-product1001": first_detail,
        "https://shop.pbtfencing.com/second-product2002": second_detail,
    }
    calls = []
    monkeypatch.setattr(scrape_pbt_products, "get_state", lambda source, key: None)
    monkeypatch.setattr(scrape_pbt_products, "set_state", lambda source, key, value: None)

    def fetcher(url):
        calls.append(url)
        return fixtures[url]

    client = FakeClient()
    summary = scrape_pbt_products.scrape_pbt_products(
        client=client,
        listing_urls=(listing_url,),
        fetcher=fetcher,
        request_delay=0,
        log_run=False,
        max_pages=5,
    )

    assert summary["read"] == 2
    assert summary["written"] == 2
    assert second_listing_url in calls
    assert {row["source_id"] for call in client.upserts for row in call["rows"]} == {"1001", "2002"}


def test_scrape_pbt_products_handles_blocked_listing_without_raising(monkeypatch):
    import scrape_pbt_products

    states = []
    monkeypatch.setattr(scrape_pbt_products, "get_state", lambda source, key: None)
    monkeypatch.setattr(
        scrape_pbt_products,
        "set_state",
        lambda source, key, value: states.append((source, key, value)),
    )

    def blocked_fetcher(_url):
        raise scrape_pbt_products.BlockedAccessError("403 blocked")

    summary = scrape_pbt_products.scrape_pbt_products(
        client=FakeClient(),
        listing_urls=("https://shop.pbtfencing.com/webshop/fencing-clothing-2?lang=euro_foreign",),
        fetcher=blocked_fetcher,
        request_delay=0,
        log_run=False,
    )

    assert summary["read"] == 0
    assert summary["written"] == 0
    assert summary["failed"] == 1
    assert summary["skipped"] == 0
    assert summary["blocked"] == 1
    assert "403 blocked" in states[-1][2]["errors"][0]
