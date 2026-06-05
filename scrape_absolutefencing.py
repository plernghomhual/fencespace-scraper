from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "absolute_fencing"
STATE_SOURCE = "absolute_fencing_products"
BASE_URL = "https://www.absolutefencinggear.com/"
ROBOTS_URL = urljoin(BASE_URL, "robots.txt")
UPSERT_BATCH_SIZE = 100
REQUEST_DELAY = 1.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_LISTING_URLS = (
    "https://www.absolutefencinggear.com/uniforms/lame/foil",
    "https://www.absolutefencinggear.com/uniforms/lame/epee",
    "https://www.absolutefencinggear.com/uniforms/lame/sabre",
    "https://www.absolutefencinggear.com/weapons/foil",
    "https://www.absolutefencinggear.com/weapons/epee",
    "https://www.absolutefencinggear.com/weapons/sabre",
    "https://www.absolutefencinggear.com/masks",
    "https://www.absolutefencinggear.com/gloves",
    "https://www.absolutefencinggear.com/body-cords",
)

CURRENCY_BY_SYMBOL = {"$": "USD", "£": "GBP", "€": "EUR"}
MONEY_RE = re.compile(r"([$£€])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")

BRAND_PATTERNS = (
    (re.compile(r"\babsolute\b|\baf\b", re.I), "Absolute Fencing"),
    (re.compile(r"\bleon\s+paul\b|\blp\b", re.I), "Leon Paul"),
    (re.compile(r"\bblue\s+gauntlet\b|\bbg\b", re.I), "Blue Gauntlet"),
    (re.compile(r"\ballstar\b", re.I), "Allstar"),
    (re.compile(r"\buhlmann\b", re.I), "Uhlmann"),
    (re.compile(r"\bnegrini\b", re.I), "Negrini"),
    (re.compile(r"\bpbt\b", re.I), "PBT"),
    (re.compile(r"\badidas\b", re.I), "Adidas"),
    (re.compile(r"\bfavero\b", re.I), "Favero"),
    (re.compile(r"\bfolo\b", re.I), "FOLO"),
    (re.compile(r"\bprieur\b", re.I), "Prieur"),
    (re.compile(r"\bstm\b", re.I), "STM"),
    (re.compile(r"\bvniti\b", re.I), "Vniti"),
)


@dataclass(frozen=True)
class RobotsPolicy:
    disallow: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    crawl_delay: float | None = None

    def can_fetch(self, url: str) -> bool:
        path = urlparse(url).path or "/"
        if any(path.startswith(rule) for rule in self.allow if rule):
            return True
        return not any(path.startswith(rule) for rule in self.disallow if rule)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_money_number(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts[-1]) == 2:
            text = ".".join(parts)
        else:
            text = "".join(parts)
    try:
        return float(text)
    except ValueError:
        return None


def normalize_price(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    values: list[tuple[float, str]] = []
    for symbol, raw_number in MONEY_RE.findall(text):
        price = parse_money_number(raw_number)
        if price is not None:
            values.append((price, CURRENCY_BY_SYMBOL[symbol]))
    if not values:
        return None, None
    price, currency = min(values, key=lambda item: item[0])
    return price, currency


def normalize_stock_status(text: str | None) -> str | None:
    value = clean_text(text)
    if not value:
        return None
    lowered = value.lower()
    if any(term in lowered for term in ("out of stock", "sold out", "unavailable")):
        return "out_of_stock"
    if any(term in lowered for term in ("backorder", "back ordered", "back-ordered", "preorder", "pre-order")):
        return "backorder"
    if "discontinued" in lowered:
        return "discontinued"
    if "limited" in lowered:
        return "limited"
    if any(term in lowered for term in ("in stock", "available")):
        return "in_stock"
    return None


def normalize_weapon(*values: str | None) -> str | None:
    for value in values:
        text = (value or "").lower()
        if re.search(r"\bfoil\b", text):
            return "Foil"
        if re.search(r"\bepee\b|\bepée\b", text):
            return "Epee"
        if re.search(r"\bsabre\b|\bsaber\b", text):
            return "Sabre"
    return None


def normalize_category(*values: str | None) -> str | None:
    for value in values:
        text = (value or "").lower()
        if "complete electric set" in text or "weapon set" in text or "electric set" in text:
            return "Weapon Sets"
        if "lame" in text or "lamé" in text:
            return "Lames"
        if "mask" in text:
            return "Masks"
        if "glove" in text:
            return "Gloves"
        if any(term in text for term in ("jacket", "pants", "knickers", "uniform", "plastron", "underarm")):
            return "Uniforms"
        if "cord" in text:
            return "Cords"
        if "bag" in text:
            return "Bags"
        if any(term in text for term in ("blade", "weapon")):
            return "Weapons"

    text = " ".join(value for value in values if value).lower()
    if any(term in text for term in ("blade", "weapon", "foil", "epee", "sabre", "saber")):
        return "Weapons"
    return "Catalog"


def infer_brand(name: str | None, fallback: str = "Absolute Fencing") -> str:
    text = name or ""
    for pattern, brand in BRAND_PATTERNS:
        if pattern.search(text):
            return brand
    return fallback


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] or path.strip("/")
    slug = re.sub(r"\.html?$", "", slug, flags=re.I)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", slug).strip("-").lower()
    return slug or re.sub(r"[^A-Za-z0-9_-]+", "-", url).strip("-").lower()


def source_id_for(product_url: str, sku: str | None = None) -> str:
    cleaned_sku = clean_text(sku)
    if cleaned_sku:
        return cleaned_sku
    return slug_from_url(product_url)


def first_text(soup, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        if element.name == "img":
            text = element.get("alt") or element.get("title")
        else:
            text = element.get_text(" ", strip=True)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned
    return None


def first_attr(soup, selectors: Iterable[str], attrs: Iterable[str]) -> str | None:
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        for attr in attrs:
            value = clean_text(element.get(attr))
            if value:
                return value
    return None


def select_texts(soup, selectors: Iterable[str]) -> list[str]:
    texts: list[str] = []
    for selector in selectors:
        texts.extend(
            cleaned
            for cleaned in (clean_text(element.get_text(" ", strip=True)) for element in soup.select(selector))
            if cleaned
        )
    return texts


def image_from_element(card, base_url: str) -> str | None:
    value = first_attr(
        card,
        ("img.product-image-photo", "img.product-image", "img[src]", "img[data-src]"),
        ("src", "data-src", "data-original"),
    )
    if not value:
        return None
    return urljoin(base_url, value)


def product_url_from_card(card, base_url: str) -> str | None:
    for selector in (".product-item-link", ".product-item-name a[href]", ".product-name a[href]", "a[href]"):
        element = card.select_one(selector)
        if element and element.get("href"):
            return urljoin(base_url, element["href"]).split("#", 1)[0]
    return None


def parse_listing_products(
    html: str,
    *,
    listing_url: str | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or utc_now()
    base_url = listing_url or BASE_URL
    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()

    for card in soup.select("li.product-item, .products .product-item, [data-product-id]"):
        product_url = product_url_from_card(card, base_url)
        name = first_text(card, (".product-item-link", ".product-item-name", ".product-name", ".name", "a[href]"))
        if not name or not product_url:
            continue

        source_id = source_id_for(product_url)
        if source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)

        price_text = clean_text(" ".join(select_texts(card, (".price", ".price-box", "[data-price-amount]"))))
        if not price_text:
            price_text = clean_text(card.get_text(" ", strip=True))
        price, currency = normalize_price(price_text)
        stock_text = clean_text(" ".join(select_texts(card, (".stock", ".availability"))))
        stock_status = normalize_stock_status(stock_text or card.get_text(" ", strip=True))
        category = normalize_category(name, product_url, listing_url)
        weapon = normalize_weapon(name, product_url, listing_url)
        image_url = image_from_element(card, base_url)

        metadata = {
            "listing_url": listing_url,
            "price_text": price_text,
            "stock_text": stock_text,
        }

        rows.append(
            {
                "source": SOURCE,
                "source_id": source_id,
                "name": name,
                "brand": infer_brand(name),
                "category": category,
                "weapon": weapon,
                "price": price,
                "currency": currency or "USD",
                "image_url": image_url,
                "product_url": product_url,
                "stock_status": stock_status,
                "metadata": {key: value for key, value in metadata.items() if value},
                "scraped_at": scraped_at,
            }
        )

    return rows


def _json_ld_values(soup: BeautifulSoup) -> list[Any]:
    values: list[Any] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            values.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return values


def _find_json_ld_product(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        for item in value:
            found = _find_json_ld_product(item)
            if found:
                return found
    if isinstance(value, dict):
        types = value.get("@type") or value.get("type")
        if isinstance(types, str):
            types = [types]
        if any(str(item).lower() == "product" for item in (types or [])):
            return value
        for key in ("@graph", "graph", "itemListElement"):
            found = _find_json_ld_product(value.get(key))
            if found:
                return found
    return None


def json_ld_product(soup: BeautifulSoup) -> dict[str, Any]:
    for value in _json_ld_values(soup):
        product = _find_json_ld_product(value)
        if product:
            return product
    return {}


def _brand_from_json(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("name"))
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        for item in value:
            brand = _brand_from_json(item)
            if brand:
                return brand
    return None


def _image_from_json(value: Any) -> str | None:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        for item in value:
            image = _image_from_json(item)
            if image:
                return image
    if isinstance(value, dict):
        return _image_from_json(value.get("url") or value.get("contentUrl"))
    return None


def _offer_from_json(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers")
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                return offer
        return {}
    if isinstance(offers, dict):
        return offers
    return {}


def _price_from_offer(offer: dict[str, Any]) -> tuple[float | None, str | None]:
    currency = clean_text(offer.get("priceCurrency"))
    raw_price = offer.get("price")
    price = None
    if raw_price is not None:
        price = parse_money_number(str(raw_price))
    if price is None:
        price, parsed_currency = normalize_price(clean_text(offer.get("priceSpecification")))
        currency = currency or parsed_currency
    return price, currency


def _stock_from_offer(offer: dict[str, Any]) -> str | None:
    availability = clean_text(offer.get("availability"))
    if availability:
        availability = availability.rsplit("/", 1)[-1]
    return normalize_stock_status(availability)


def breadcrumbs_text(soup: BeautifulSoup) -> str | None:
    crumbs = select_texts(soup, (".breadcrumbs a", ".breadcrumbs strong", "nav.breadcrumbs a"))
    return clean_text(" ".join(crumbs))


def parse_product_detail(
    html: str,
    *,
    product_url: str,
    listing_row: dict[str, Any] | None = None,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    product = json_ld_product(soup)
    offer = _offer_from_json(product)
    listing_row = dict(listing_row or {})
    metadata = dict(listing_row.get("metadata") or {})
    scraped_at = scraped_at or listing_row.get("scraped_at") or utc_now()

    json_name = clean_text(product.get("name"))
    name = json_name or first_text(soup, (".page-title .base", "span.base", "h1", "[itemprop='name']")) or listing_row.get("name")
    sku = clean_text(product.get("sku")) or first_text(
        soup,
        (
            ".product.attribute.sku .value",
            "[itemprop='sku']",
            ".sku .value",
            ".product-info-stock-sku .value",
        ),
    )
    source_id = source_id_for(product_url, sku=sku)
    listing_source_id = clean_text(listing_row.get("source_id"))

    offer_price, offer_currency = _price_from_offer(offer)
    detail_price_text = clean_text(" ".join(select_texts(soup, (".product-info-price .price", ".price-box .price", ".price"))))
    detail_price, detail_currency = normalize_price(detail_price_text)

    price = offer_price if offer_price is not None else detail_price
    if price is None:
        price = listing_row.get("price")
    currency = offer_currency or detail_currency or listing_row.get("currency") or "USD"

    stock_text = clean_text(" ".join(select_texts(soup, (".stock", ".availability"))))
    stock_status = _stock_from_offer(offer) or normalize_stock_status(stock_text) or listing_row.get("stock_status")
    crumbs = breadcrumbs_text(soup)
    category = listing_row.get("category") or normalize_category(crumbs, name, product_url)
    weapon = listing_row.get("weapon") or normalize_weapon(crumbs, name, product_url)

    image = _image_from_json(product.get("image"))
    image_url = image or first_attr(soup, ("meta[property='og:image']", "meta[name='twitter:image']"), ("content",))
    if not image_url:
        image_url = image_from_element(soup, product_url)
    if image_url:
        image_url = urljoin(product_url, image_url)

    description = first_text(soup, (".product.attribute.description .value", "[itemprop='description']", ".description"))
    brand = _brand_from_json(product.get("brand")) or infer_brand(name, listing_row.get("brand") or "Absolute Fencing")

    if sku:
        metadata["sku"] = sku
    if description:
        metadata["description"] = description
    if crumbs:
        metadata["breadcrumbs"] = crumbs
    if detail_price_text:
        metadata["detail_price_text"] = detail_price_text
    if stock_text:
        metadata["detail_stock_text"] = stock_text
    if listing_source_id and listing_source_id != source_id:
        metadata["listing_source_id"] = listing_source_id
    metadata["detail_status"] = "parsed"

    return {
        "source": SOURCE,
        "source_id": source_id,
        "name": name,
        "brand": brand,
        "category": category,
        "weapon": weapon,
        "price": price,
        "currency": currency,
        "image_url": image_url or listing_row.get("image_url"),
        "product_url": product_url,
        "stock_status": stock_status,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
        "scraped_at": scraped_at,
    }


def fallback_detail_row(listing_row: dict[str, Any], detail_status: str) -> dict[str, Any]:
    row = dict(listing_row)
    metadata = dict(row.get("metadata") or {})
    metadata["detail_status"] = detail_status
    row["metadata"] = metadata
    return row


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def dedupe_products(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not valid_product_row(row):
            continue
        key = (str(row["source"]), str(row["source_id"]))
        if key not in deduped:
            deduped[key] = row
    return list(deduped.values())


def upsert_products(client, rows: list[dict[str, Any]], batch_size: int = UPSERT_BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    valid_rows = dedupe_products(rows)
    for index in range(0, len(valid_rows), batch_size):
        batch = valid_rows[index : index + batch_size]
        try:
            client.table("fs_products").upsert(batch, on_conflict="source,source_id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_products upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def fetch_url(url: str, *, session: requests.Session | None = None, timeout: int = 20) -> str | None:
    active_session = session or requests.Session()
    if not active_session.headers.get("User-Agent"):
        active_session.headers.update(HEADERS)
    response = active_session.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def parse_robots_txt(text: str | None, user_agent: str = "FenceSpaceBot") -> RobotsPolicy:
    if not text:
        return RobotsPolicy()

    disallow: list[str] = []
    allow: list[str] = []
    crawl_delay: float | None = None
    active = False
    group_has_rules = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        lowered_key = key.lower()
        if lowered_key == "user-agent":
            if group_has_rules:
                active = False
                group_has_rules = False
            lowered_value = value.lower()
            active = lowered_value in {"*", user_agent.lower()}
            continue
        if not active:
            continue
        group_has_rules = True
        if lowered_key == "disallow" and value:
            disallow.append(value)
        elif lowered_key == "allow" and value:
            allow.append(value)
        elif lowered_key == "crawl-delay":
            try:
                crawl_delay = float(value)
            except ValueError:
                pass

    return RobotsPolicy(disallow=tuple(disallow), allow=tuple(allow), crawl_delay=crawl_delay)


def load_robots_policy(
    *,
    fetcher: Callable[[str], str | None],
    robots_fetcher: Callable[[str], str | None] | None = None,
) -> RobotsPolicy:
    active_fetcher = robots_fetcher
    if active_fetcher is None and fetcher is fetch_url:
        active_fetcher = fetcher
    if active_fetcher is None:
        return RobotsPolicy()
    try:
        return parse_robots_txt(active_fetcher(ROBOTS_URL))
    except Exception as exc:
        print(f"  robots.txt probe failed for {ROBOTS_URL}: {exc}")
        return RobotsPolicy()


def rate_limit(policy: RobotsPolicy, request_delay: float) -> None:
    delay = max(request_delay, policy.crawl_delay or 0)
    if delay > 0:
        time.sleep(delay)


def _source_ids_for_state(rows: Iterable[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        source_id = clean_text(row.get("source_id"))
        if source_id:
            values.add(source_id)
        listing_source_id = clean_text((row.get("metadata") or {}).get("listing_source_id"))
        if listing_source_id:
            values.add(listing_source_id)
    return values


def scrape_absolutefencing(
    *,
    client=None,
    listing_urls: Iterable[str] | None = None,
    fetcher: Callable[[str], str | None] = fetch_url,
    robots_fetcher: Callable[[str], str | None] | None = None,
    dry_run: bool = False,
    log_run: bool = True,
    request_delay: float = REQUEST_DELAY,
    respect_robots: bool = True,
    update_state: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if not dry_run:
        client = client or get_supabase_client()

    run_log = ScraperRunLogger("scrape_absolutefencing").start() if log_run else None
    listing_urls = tuple(listing_urls or DEFAULT_LISTING_URLS)
    robots_policy = load_robots_policy(fetcher=fetcher, robots_fetcher=robots_fetcher) if respect_robots else RobotsPolicy()
    done_source_ids = set(get_state(STATE_SOURCE, "done_source_ids") or []) if update_state else set()
    scraped_at = utc_now()
    summary: dict[str, Any] = {
        "read": 0,
        "written": 0,
        "failed": 0,
        "skipped": 0,
        "pages": 0,
        "dry_run": dry_run,
        "scraped_at": scraped_at,
    }

    try:
        for listing_url in listing_urls:
            if respect_robots and not robots_policy.can_fetch(listing_url):
                summary["skipped"] += 1
                continue

            try:
                html = fetcher(listing_url)
                rate_limit(robots_policy, request_delay)
            except Exception as exc:
                summary["failed"] += 1
                print(f"  listing fetch failed for {listing_url}: {exc}")
                continue

            if html is None:
                summary["skipped"] += 1
                continue

            summary["pages"] += 1
            listing_rows = parse_listing_products(html, listing_url=listing_url, scraped_at=scraped_at)
            summary["read"] += len(listing_rows)
            product_rows: list[dict[str, Any]] = []

            for listing_row in listing_rows:
                listing_source_id = listing_row["source_id"]
                if not force and listing_source_id in done_source_ids:
                    summary["skipped"] += 1
                    continue
                if dry_run:
                    summary["skipped"] += 1
                    continue

                product_url = listing_row["product_url"]
                if respect_robots and not robots_policy.can_fetch(product_url):
                    product_rows.append(fallback_detail_row(listing_row, "robots_disallowed"))
                    continue

                try:
                    detail_html = fetcher(product_url)
                    rate_limit(robots_policy, request_delay)
                except Exception as exc:
                    row = fallback_detail_row(listing_row, "error")
                    row["metadata"]["detail_error"] = str(exc)[:500]
                    product_rows.append(row)
                    continue

                if detail_html is None:
                    product_rows.append(fallback_detail_row(listing_row, "not_found"))
                    continue

                detail_row = parse_product_detail(
                    detail_html,
                    product_url=product_url,
                    listing_row=listing_row,
                    scraped_at=scraped_at,
                )
                product_rows.append(detail_row)

            if not product_rows:
                continue

            written, failed = upsert_products(client, product_rows)
            summary["written"] += written
            summary["failed"] += failed
            if written:
                done_source_ids.update(_source_ids_for_state(product_rows))
                if update_state:
                    set_state(STATE_SOURCE, "done_source_ids", sorted(done_source_ids))

        if update_state and not dry_run:
            set_state(STATE_SOURCE, "last_run", summary)

        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Absolute Fencing product scrape starting - {utc_now()}")
    summary = scrape_absolutefencing()
    print(
        "Absolute Fencing product scrape complete - "
        f"read={summary['read']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}, "
        f"pages={summary['pages']}"
    )


if __name__ == "__main__":
    main()
