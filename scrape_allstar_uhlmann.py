from __future__ import annotations

import html
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scripts.rate_limiter import RateLimiter


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

STATE_SOURCE = "allstar_uhlmann_products"
PRODUCT_TABLE = "fs_products"
ALLSTAR_BASE_URL = "https://allstar.de/"
UHLMANN_BASE_URL = "https://uhlmann-fechtsport.com/"
REQUEST_RPS = float(os.environ.get("ALLSTAR_UHLMANN_REQUEST_RPS", "0.5"))
REQUEST_DELAY = float(os.environ.get("ALLSTAR_UHLMANN_REQUEST_DELAY", "1.0"))
UPSERT_BATCH_SIZE = int(os.environ.get("ALLSTAR_UHLMANN_UPSERT_BATCH_SIZE", "100"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

EURO = "\u20ac"
PRICE_NUMBER_RE = r"[0-9][0-9\s.,]*"
PREFIX_PRICE_RE = re.compile(rf"({re.escape(EURO)}|EUR)\s*({PRICE_NUMBER_RE})", re.I)
SUFFIX_PRICE_RE = re.compile(rf"({PRICE_NUMBER_RE})\s*({re.escape(EURO)}|EUR)", re.I)


@dataclass(frozen=True)
class ListingConfig:
    source: str
    brand: str
    base_url: str
    listing_url: str
    category_hint: str

    def detail_url_for(self, product_url: str) -> str:
        return urljoin(self.base_url, product_url).split("#", 1)[0]


ALLSTAR_UNIFORMS = ListingConfig(
    source="allstar",
    brand="Allstar",
    base_url=ALLSTAR_BASE_URL,
    listing_url="https://allstar.de/en/clothing-footwear/uniforms/",
    category_hint="Fencing suits",
)
ALLSTAR_MASKS = ListingConfig(
    source="allstar",
    brand="Allstar",
    base_url=ALLSTAR_BASE_URL,
    listing_url="https://allstar.de/en/clothing-footwear/masks/",
    category_hint="Masks",
)
ALLSTAR_WEAPONS = ListingConfig(
    source="allstar",
    brand="Allstar",
    base_url=ALLSTAR_BASE_URL,
    listing_url="https://allstar.de/en/weapons-and-accessories/",
    category_hint="Weapons and accessories",
)
ALLSTAR_SCORING = ListingConfig(
    source="allstar",
    brand="Allstar",
    base_url=ALLSTAR_BASE_URL,
    listing_url="https://allstar.de/en/signaling-installations/score-units-lights/signaling-units/",
    category_hint="Signaling installations",
)
UHLMANN_FENCING_SUITS = ListingConfig(
    source="uhlmann",
    brand="Uhlmann",
    base_url=UHLMANN_BASE_URL,
    listing_url="https://uhlmann-fechtsport.com/en/shop/clothing/fencing-suits/",
    category_hint="Fencing suits",
)
UHLMANN_MASKS = ListingConfig(
    source="uhlmann",
    brand="Uhlmann",
    base_url=UHLMANN_BASE_URL,
    listing_url="https://uhlmann-fechtsport.com/en/shop/clothing/masks/",
    category_hint="Masks",
)
UHLMANN_WEAPONS = ListingConfig(
    source="uhlmann",
    brand="Uhlmann",
    base_url=UHLMANN_BASE_URL,
    listing_url="https://uhlmann-fechtsport.com/en/shop/weapons-and-accessories/",
    category_hint="Weapons and accessories",
)

DEFAULT_LISTINGS = (
    ALLSTAR_UNIFORMS,
    ALLSTAR_MASKS,
    ALLSTAR_WEAPONS,
    ALLSTAR_SCORING,
    UHLMANN_FENCING_SUITS,
    UHLMANN_MASKS,
    UHLMANN_WEAPONS,
)

PRODUCT_COLUMNS = {
    "source",
    "source_id",
    "name",
    "brand",
    "category",
    "weapon",
    "price",
    "currency",
    "image_url",
    "product_url",
    "stock_status",
    "metadata",
    "scraped_at",
}

_RATE_LIMITER = RateLimiter(default_rps=REQUEST_RPS, jitter=0.1, backoff=2.0)


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
    text = html.unescape(str(value)).replace("\xa0", " ")
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def compare_text(value: Any) -> str:
    text = strip_accents(str(value or "")).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_money_number(raw: str) -> float | None:
    text = raw.replace("\xa0", " ")
    text = re.sub(r"\s+", "", text).strip(".,")
    if not text:
        return None

    last_comma = text.rfind(",")
    last_dot = text.rfind(".")
    if last_comma >= 0 and last_dot >= 0:
        if last_comma > last_dot:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif last_comma >= 0:
        decimal_digits = len(text) - last_comma - 1
        text = text.replace(",", ".") if decimal_digits in {1, 2} else text.replace(",", "")
    elif last_dot >= 0:
        decimal_digits = len(text) - last_dot - 1
        if decimal_digits not in {1, 2}:
            text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


def normalize_price(text: str | None) -> tuple[float | None, str | None, str | None]:
    price_text = clean_text(text)
    if not price_text:
        return None, None, None

    values: list[tuple[float, str]] = []
    seen: set[float] = set()
    for _marker, raw_number in PREFIX_PRICE_RE.findall(price_text):
        price = parse_money_number(raw_number)
        if price is not None and price not in seen:
            values.append((price, "EUR"))
            seen.add(price)
    for raw_number, _marker in SUFFIX_PRICE_RE.findall(price_text):
        price = parse_money_number(raw_number)
        if price is not None and price not in seen:
            values.append((price, "EUR"))
            seen.add(price)

    if not values:
        return None, None, price_text
    return (*min(values, key=lambda item: item[0]), price_text)


def price_missing_reason(price_text: str | None) -> str | None:
    normalized = compare_text(price_text)
    if not normalized:
        return None
    if any(
        phrase in normalized
        for phrase in (
            "log in",
            "login",
            "register",
            "view prices",
            "view price",
            "price on request",
            "request price",
            "prices only",
            "not visible",
        )
    ):
        return "price_not_public"
    return "price_not_found"


def normalize_category(*values: str | None) -> str | None:
    candidates = [clean_text(value) for value in values if clean_text(value)]
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\blame\b|\blames\b|\bmetal\s+jacket\b|\bmetallwesten\b|\belectric\s+jacket\b", re.I), "Lames"),
        (re.compile(r"\bmask\b|\bmasks\b|\bmasken\b", re.I), "Masks"),
        (re.compile(r"\bmeldeanlagen\b|\bsignaling\b|\bscoring\b|\bscore\s+unit\b|\breel\b", re.I), "Scoring Equipment"),
        (re.compile(r"\bglove\b|\bgloves\b|\bhandschuhe\b", re.I), "Gloves"),
        (re.compile(r"\bshoe\b|\bshoes\b|\bsock\b|\bsocks\b|\bschuhe\b|\bsocken\b", re.I), "Shoes & Socks"),
        (re.compile(r"\bbag\b|\bbags\b|\btaschen\b", re.I), "Bags"),
        (
            re.compile(
                r"\bwaffen\b|\bzubehor\b|\bweapon\b|\bweapons\b|\bblade\b|\bblades\b|\bklinge\b|\bklingen\b|"
                r"degen|florett|sabel|saebel|\bepee\b|\bfoil\b|\bsabre\b|\bsaber\b",
                re.I,
            ),
            "Weapons & Accessories",
        ),
        (
            re.compile(
                r"\bfechtanzuge\b|\bfencing\s+suits\b|\buniform\b|\buniforms\b|\bclothing\b|\bjacket\b|"
                r"\bjacke\b|\bhose\b|\bpants\b|\bplastron\b",
                re.I,
            ),
            "Uniforms",
        ),
    )

    for candidate in candidates:
        comparable = compare_text(candidate)
        for pattern, normalized in patterns:
            if pattern.search(comparable):
                return normalized
    return candidates[0].title() if candidates else None  # type: ignore[union-attr]


def normalize_weapon(*values: str | None) -> str | None:
    comparable = compare_text(" ".join(value for value in values if value))
    if re.search(r"\bsabre\b|\bsaber\b|sabel|saebel", comparable):
        return "sabre"
    if re.search(r"\bepee\b|degen", comparable):
        return "epee"
    if re.search(r"\bfoil\b|florett", comparable):
        return "foil"
    return None


def normalize_stock_status(text: str | None) -> str:
    normalized = compare_text(text)
    if not normalized:
        return "unknown"
    if any(term in normalized for term in ("planned for production", "planned production", "produktion geplant")):
        return "planned_production"
    if any(term in normalized for term in ("out of stock", "sold out", "unavailable", "not available", "nicht verfugbar")):
        return "out_of_stock"
    if any(term in normalized for term in ("backorder", "back order", "preorder", "pre order")):
        return "backorder"
    if any(term in normalized for term in ("limited", "only left", "low stock")):
        return "limited"
    if any(term in normalized for term in ("available", "in stock", "delivery time", "lieferzeit", "add to cart")):
        return "in_stock"
    return "unknown"


def absolute_url(value: str | None, base_url: str) -> str | None:
    if not value:
        return None
    return urljoin(base_url, value).split("#", 1)[0]


def source_id_from_url(product_url: str | None) -> str | None:
    if not product_url:
        return None
    path = urlparse(product_url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    slug = re.sub(r"\.html?$", "", slug, flags=re.I)
    return slug or None


def first_text(container: Any, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        element = container.select_one(selector)
        if not element:
            continue
        text = element.get("content") if element.name == "meta" else element.get_text(" ", strip=True)
        if not text and element.name == "img":
            text = element.get("alt") or element.get("title")
        if not text:
            text = element.get("title") or element.get("aria-label")
        cleaned = clean_text(text)
        if cleaned:
            return cleaned
    return None


def first_url(container: Any, selectors: Iterable[str], base_url: str) -> str | None:
    for selector in selectors:
        element = container.select_one(selector)
        if element and element.get("href"):
            return absolute_url(element["href"], base_url)
    element = container.find("a", href=True)
    if element:
        return absolute_url(element["href"], base_url)
    return None


def image_url_from_container(container: Any, base_url: str) -> str | None:
    meta = container.select_one("meta[property='og:image'], meta[name='twitter:image']")
    if meta and meta.get("content"):
        return absolute_url(meta["content"], base_url)

    for selector in (
        ".product-detail-media img",
        ".gallery-slider-image",
        ".gallery-placeholder img",
        ".product-image-link img",
        "img.product-image",
        "img",
    ):
        image = container.select_one(selector)
        if not image:
            continue
        for attr in ("src", "data-src", "data-original", "data-lazy"):
            value = image.get(attr)
            if value and not str(value).startswith("data:"):
                return absolute_url(str(value), base_url)
        srcset = image.get("srcset") or image.get("data-srcset")
        if srcset:
            first = str(srcset).split(",", 1)[0].strip().split(" ", 1)[0]
            if first and not first.startswith("data:"):
                return absolute_url(first, base_url)
    return None


def price_text_from_container(container: Any) -> str | None:
    pieces: list[str] = []
    for element in container.select(".product-detail-price, .product-price, .price, .product-price-info, [data-price]"):
        if element.get("data-price"):
            pieces.append(str(element["data-price"]))
        text = element.get_text(" ", strip=True)
        if text:
            pieces.append(text)
    return clean_text(" ".join(pieces))


def product_number_from_container(container: Any) -> str | None:
    for element in (container, *container.select("[data-product-number], [data-product-sku], [data-sku], [data-product-id]")):
        for attr in ("data-product-number", "data-product-sku", "data-sku", "data-product-id"):
            value = clean_text(element.get(attr))
            if value:
                return value

    current = container
    for _ in range(3):
        if current is None:
            break
        for attr in ("data-product-number", "data-product-sku", "data-sku", "data-product-id"):
            value = clean_text(current.get(attr))
            if value:
                return value
        current = getattr(current, "parent", None)

    for selector in (
        ".product-detail-ordernumber",
        ".product-detail-product-number",
        ".product-ordernumber",
        ".product-number",
        "[itemprop='sku']",
        ".sku .value",
    ):
        value = first_text(container, (selector,))
        if value and compare_text(value) not in {"sku", "product number", "product no"}:
            return value

    text = clean_text(container.get_text(" ", strip=True))
    if not text:
        return None
    match = re.search(
        r"(?:product\s*(?:number|no\.?)|produktnummer|artikelnummer|article\s*number|sku)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9./_-]*)",
        text,
        re.I,
    )
    return match.group(1) if match else None


def listing_cards(soup: BeautifulSoup) -> list[Any]:
    for selector in (
        ".cms-listing-col",
        ".product-listing .product-box",
        ".product-listing .product-item",
        ".card.product-box",
        ".product-box",
        "li.product-item",
    ):
        cards = soup.select(selector)
        if cards:
            return cards
    return []


def parse_listing_products(
    listing_html: str,
    listing: ListingConfig,
    *,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(listing_html, "html.parser")
    scraped_at = scraped_at or utc_now()
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for card in listing_cards(soup):
        product_url = first_url(
            card,
            (
                ".product-name[href]",
                ".product-name a[href]",
                "a.product-name[href]",
                ".product-image-link[href]",
                "a[href]",
            ),
            listing.listing_url,
        )
        name = first_text(
            card,
            (
                ".product-name",
                ".product-title",
                ".product-name a",
                ".product-info a[title]",
                "a[title]",
                "a[href]",
            ),
        )
        if not product_url or not name:
            continue

        listing_source_id = product_number_from_container(card) or source_id_from_url(product_url)
        if not listing_source_id:
            continue

        dedupe_key = f"{listing.source}:{listing_source_id}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        price_text = price_text_from_container(card)
        if not price_text:
            text = clean_text(card.get_text(" ", strip=True))
            if text and (EURO in text or "EUR" in text.upper() or "price" in compare_text(text)):
                price_text = text
        price, currency, normalized_price_text = normalize_price(price_text)
        stock_text = clean_text(
            " ".join(
                element.get_text(" ", strip=True)
                for element in card.select(".delivery-information, .stock, .availability, .product-delivery-information")
            )
        )
        stock_status = normalize_stock_status(stock_text or card.get_text(" ", strip=True))
        image_url = image_url_from_container(card, listing.base_url)
        category = normalize_category(name, listing.category_hint, product_url)
        weapon = normalize_weapon(name, category, product_url)

        metadata: dict[str, Any] = {
            "listing_url": listing.listing_url,
            "listing_source_id": listing_source_id,
            "price_text": normalized_price_text,
            "stock_text": stock_text,
        }
        if price is None:
            reason = price_missing_reason(normalized_price_text)
            if reason:
                metadata["missing_price_reason"] = reason

        rows.append(
            {
                "source": listing.source,
                "source_id": listing_source_id,
                "name": name,
                "brand": listing.brand,
                "category": category,
                "weapon": weapon,
                "price": price,
                "currency": currency,
                "image_url": image_url,
                "product_url": product_url,
                "stock_status": stock_status,
                "metadata": {key: value for key, value in metadata.items() if value is not None},
                "scraped_at": scraped_at,
            }
        )

    return rows


def breadcrumb_values(soup: BeautifulSoup) -> list[str]:
    crumbs = [
        clean_text(element.get_text(" ", strip=True))
        for element in soup.select(".breadcrumb a, .breadcrumb-link, .breadcrumbs a, .breadcrumbs strong, .breadcrumb-item")
    ]
    return [crumb for crumb in crumbs if crumb and compare_text(crumb) not in {"home", "shop"}]


def parse_product_detail(
    detail_html: str,
    *,
    product_url: str,
    listing: ListingConfig | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(detail_html, "html.parser")
    base_url = listing.base_url if listing else product_url
    name = first_text(soup, (".product-detail-name", "h1.product-detail-name", "h1", "[itemprop='name']"))
    sku = product_number_from_container(soup)
    price_text = price_text_from_container(soup)
    price, currency, normalized_price_text = normalize_price(price_text)
    crumbs = breadcrumb_values(soup)
    stock_text = clean_text(
        " ".join(
            element.get_text(" ", strip=True)
            for element in soup.select(".delivery-information, .stock, .availability, .product-delivery-information")
        )
    )
    category_hint = listing.category_hint if listing else None
    category = normalize_category(name, *(reversed(crumbs)), category_hint, product_url)
    weapon = normalize_weapon(name, category, product_url, soup.get_text(" ", strip=True))
    image_url = image_url_from_container(soup, base_url)

    metadata: dict[str, Any] = {
        "detail_url": product_url,
        "detail_status": "parsed",
        "detail_price_text": normalized_price_text,
        "stock_text": stock_text,
    }
    if sku:
        metadata["sku"] = sku
    if crumbs:
        metadata["breadcrumbs"] = crumbs
    if price is None:
        reason = price_missing_reason(normalized_price_text or soup.get_text(" ", strip=True))
        if reason:
            metadata["missing_price_reason"] = reason

    return {
        "source": listing.source if listing else None,
        "source_id": sku or source_id_from_url(product_url),
        "name": name,
        "brand": listing.brand if listing else None,
        "category": category,
        "weapon": weapon,
        "price": price,
        "currency": currency,
        "image_url": image_url,
        "product_url": product_url,
        "stock_status": normalize_stock_status(stock_text or soup.get_text(" ", strip=True)),
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def build_product_row(
    listing_row: dict[str, Any],
    detail: dict[str, Any] | None = None,
    *,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    detail = detail or {}
    detail_metadata = detail.get("metadata") if isinstance(detail.get("metadata"), dict) else {}
    listing_metadata = listing_row.get("metadata") if isinstance(listing_row.get("metadata"), dict) else {}

    metadata: dict[str, Any] = dict(listing_metadata)  # type: ignore[arg-type]
    for key, value in detail_metadata.items():  # type: ignore[union-attr]
        if key == "missing_price_reason":
            metadata["detail_missing_price_reason"] = value
        else:
            metadata[key] = value
    if "detail_status" not in metadata:
        metadata["detail_status"] = "not_fetched"
    if listing_row.get("price") is None and detail.get("price") is None and "missing_price_reason" not in metadata:
        reason = metadata.get("detail_missing_price_reason") or "price_not_found"
        metadata["missing_price_reason"] = reason

    row = {
        "source": listing_row.get("source") or detail.get("source"),
        "source_id": detail.get("source_id") or listing_row.get("source_id"),
        "name": detail.get("name") or listing_row.get("name"),
        "brand": listing_row.get("brand") or detail.get("brand"),
        "category": detail.get("category") or listing_row.get("category"),
        "weapon": detail.get("weapon") or listing_row.get("weapon"),
        "price": detail.get("price") if detail.get("price") is not None else listing_row.get("price"),
        "currency": detail.get("currency") if detail.get("currency") is not None else listing_row.get("currency"),
        "image_url": detail.get("image_url") or listing_row.get("image_url"),
        "product_url": detail.get("product_url") or listing_row.get("product_url"),
        "stock_status": detail.get("stock_status") or listing_row.get("stock_status") or "unknown",
        "metadata": metadata,
        "scraped_at": scraped_at or listing_row.get("scraped_at") or utc_now(),
    }
    return {key: row.get(key) for key in PRODUCT_COLUMNS}


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def dedupe_product_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not valid_product_row(row):
            continue
        key = (str(row["source"]), str(row["source_id"]))
        if key not in deduped:
            deduped[key] = row
    return list(deduped.values())


def upsert_products(
    client: Any,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> tuple[int, int]:
    written = 0
    failed = 0
    valid_rows = dedupe_product_rows(rows)
    for index in range(0, len(valid_rows), batch_size):
        batch = valid_rows[index : index + batch_size]
        try:
            client.table(PRODUCT_TABLE).upsert(batch, on_conflict="source,source_id").execute()
            written += len(batch)
        except Exception as exc:
            print(f"  fs_products upsert batch {index // batch_size} failed: {exc}")
            for row in batch:
                try:
                    client.table(PRODUCT_TABLE).upsert([row], on_conflict="source,source_id").execute()
                    written += 1
                except Exception as row_exc:
                    failed += 1
                    print(f"    fs_products upsert failed for {row.get('source')}:{row.get('source_id')}: {row_exc}")
    return written, failed


def fetch_url(url: str) -> str | None:
    domain = urlparse(url).netloc
    if domain:
        _RATE_LIMITER.wait(domain, REQUEST_RPS)
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        if domain:
            _RATE_LIMITER.record_failure(domain)
        print(f"  Fetch failed for {url}: {exc}")
        return None
    if 200 <= response.status_code < 300:
        if domain:
            _RATE_LIMITER.record_success(domain)
        return response.text
    if domain:
        _RATE_LIMITER.record_failure(domain)
    print(f"  HTTP {response.status_code} for {url}")
    return None


def html_from_fetch_result(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, dict):
        value = result.get("html") or result.get("text")
        return str(value) if value is not None else None
    return str(result)


def scraper_key(row: dict[str, Any]) -> str:
    return f"{row.get('source')}:{row.get('source_id')}"


def scrape_allstar_uhlmann(
    *,
    client: Any = None,
    listings: Iterable[ListingConfig] | None = None,
    fetcher: Callable[[str], Any] = fetch_url,
    log_run: bool = True,
    request_delay: float = REQUEST_DELAY,
    max_products: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    client = client if client is not None else (None if dry_run else get_supabase_client())
    listings = tuple(listings or DEFAULT_LISTINGS)
    run_log = ScraperRunLogger("scrape_allstar_uhlmann").start() if log_run else None
    previous_state = get_state(STATE_SOURCE, "last_run")
    done_source_ids = set(get_state(STATE_SOURCE, "done_source_ids") or [])
    updated_done_source_ids = set(done_source_ids)

    read = written = failed = skipped = 0
    product_rows: list[dict[str, Any]] = []

    try:
        for listing in listings:
            listing_html = html_from_fetch_result(fetcher(listing.listing_url))
            if not listing_html:
                failed += 1
                continue

            for listing_row in parse_listing_products(listing_html, listing):
                read += 1
                listing_key = scraper_key(listing_row)
                if listing_key in done_source_ids:
                    skipped += 1
                    continue

                detail_url = listing.detail_url_for(str(listing_row["product_url"]))
                detail_html = html_from_fetch_result(fetcher(detail_url))
                if detail_html:
                    try:
                        detail = parse_product_detail(detail_html, product_url=detail_url, listing=listing)
                    except Exception as exc:
                        failed += 1
                        detail = {"metadata": {"detail_status": "parse_error", "detail_error": str(exc)[:300]}}
                else:
                    detail = {"metadata": {"detail_status": "not_found"}}

                row = build_product_row(listing_row, detail)
                product_rows.append(row)
                updated_done_source_ids.add(listing_key)
                updated_done_source_ids.add(scraper_key(row))

                if request_delay:
                    time.sleep(request_delay)
                if max_products is not None and len(product_rows) >= max_products:
                    break
            if max_products is not None and len(product_rows) >= max_products:
                break

        if dry_run or client is None:
            skipped += len(product_rows)
        elif product_rows:
            batch_written, batch_failed = upsert_products(client, product_rows)
            written += batch_written
            failed += batch_failed

        summary = {
            "read": read,
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "sources": sorted({row["source"] for row in product_rows if row.get("source")}),
            "scraped_at": utc_now(),
            "dry_run": dry_run,
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(STATE_SOURCE, "done_source_ids", sorted(updated_done_source_ids))
        set_state(STATE_SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={"read": read, "sources": summary["sources"], "dry_run": dry_run},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_allstar_uhlmann()
    print(
        "Allstar/Uhlmann scrape complete: read={read}, written={written}, "
        "failed={failed}, skipped={skipped}".format(**summary)
    )


if __name__ == "__main__":
    main()
