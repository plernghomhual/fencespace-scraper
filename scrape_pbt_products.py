from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "pbt"
STATE_SOURCE = "pbt_products"
BASE_URL = "https://shop.pbtfencing.com/"
REQUEST_DELAY = float(os.environ.get("PBT_PRODUCTS_REQUEST_DELAY", "1.0"))
UPSERT_BATCH_SIZE = int(os.environ.get("PBT_PRODUCTS_UPSERT_BATCH_SIZE", "100"))

DEFAULT_LISTING_URLS = (
    "https://shop.pbtfencing.com/webshop/fencing-clothing-2?lang=euro_foreign",
    "https://shop.pbtfencing.com/webshop/fencing-masks-3?lang=euro_foreign",
    "https://shop.pbtfencing.com/webshop/weapons-blades-4?lang=euro_foreign",
    "https://shop.pbtfencing.com/webshop/fencing-bags-5?lang=euro_foreign",
    "https://shop.pbtfencing.com/webshop/fencing-shoes-socks-1?lang=euro_foreign",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CURRENCY_BY_MARKER = {
    "$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "Ft": "HUF",
    "HUF": "HUF",
}
PRICE_NUMBER_RE = r"[0-9][0-9\s.,]*"
PREFIX_PRICE_RE = re.compile(rf"([$€£])\s*({PRICE_NUMBER_RE})")
SUFFIX_PRICE_RE = re.compile(rf"({PRICE_NUMBER_RE})\s*(€|EUR|Ft|HUF|\$|USD|£|GBP)", re.I)

CATEGORY_PATTERNS = (
    (re.compile(r"\buniforms?\b|\bprotectors?\b|\b800\s*n\b", re.I), "Uniforms & Protectors"),
    (re.compile(r"\belectric\s+jackets?\b", re.I), "Electric Jackets"),
    (re.compile(r"\bgloves?\b|\bcuffs?\b", re.I), "Gloves & Cuffs"),
    (re.compile(r"\bfencing\s+clothing\b|\bclothing\b", re.I), "Fencing Clothing"),
    (re.compile(r"\bfoil\s+masks?\b|\bepee\s+masks?\b|\bepée\s+masks?\b|\bsabre\s+masks?\b|\bmasks?\b", re.I), "Masks"),
    (re.compile(r"\bweapons?\b|\bblades?\b", re.I), "Weapons & Blades"),
    (re.compile(r"\bbags?\b|\brollbags?\b", re.I), "Fencing Bags"),
    (re.compile(r"\bshoes?\b|\bsocks?\b", re.I), "Fencing Shoes & Socks"),
    (re.compile(r"\bcoach\b", re.I), "Coach Gear"),
    (re.compile(r"\brepair\b", re.I), "Repair Items"),
)

WEAPON_PATTERNS = (
    (re.compile(r"\bsabre\b|\bsaber\b|\bkard\b", re.I), "sabre"),
    (re.compile(r"\bfoil\b|\btor\b|\btőr\b", re.I), "foil"),
    (re.compile(r"\bepee\b|\bepée\b|\bépée\b|\bparbajtor\b|\bpárbajtőr\b", re.I), "epee"),
)

SKU_LABELS = {"sku", "cikkszam", "cikkszám", "article_number", "item_number"}


class BlockedAccessError(RuntimeError):
    pass


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
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


def label_key(value: Any) -> str:
    text = strip_accents(str(value or "")).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    aliases = {
        "cikkszam": "sku",
        "sku": "sku",
        "fegyver": "weapon",
        "fegyvernem": "weapon",
        "weapon": "weapon",
        "keszlet": "stock",
        "stock": "stock",
        "availability": "stock",
        "level": "level",
        "type": "type",
        "meret": "size",
        "size": "size",
    }
    return aliases.get(text, text)


def parse_money_number(raw: str) -> float | None:
    text = raw.replace("\xa0", " ").strip()
    text = re.sub(r"\s+", "", text)
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
        if decimal_digits in {1, 2}:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def parse_price(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None

    values: list[tuple[float, str]] = []
    seen: set[tuple[float, str]] = set()
    for marker, raw_number in PREFIX_PRICE_RE.findall(text):
        currency = CURRENCY_BY_MARKER[marker]
        price = parse_money_number(raw_number)
        if price is not None and (price, currency) not in seen:
            values.append((price, currency))
            seen.add((price, currency))

    for raw_number, marker in SUFFIX_PRICE_RE.findall(text):
        normalized_marker = marker.upper()
        currency = CURRENCY_BY_MARKER.get(marker) or CURRENCY_BY_MARKER.get(normalized_marker)
        price = parse_money_number(raw_number)
        if currency and price is not None and (price, currency) not in seen:
            values.append((price, currency))
            seen.add((price, currency))

    if not values:
        return None, None
    return min(values, key=lambda item: item[0])


def normalize_category(*values: str | None) -> str | None:
    candidates = [clean_text(value) for value in values if clean_text(value)]
    for pattern, normalized in CATEGORY_PATTERNS:
        for candidate in candidates:
            if pattern.search(candidate or ""):
                return normalized
    return candidates[0].title() if candidates else None


def normalize_weapon(*values: str | None) -> str | None:
    normalized_values = [strip_accents(value or "") for value in values if value]
    for pattern, weapon in WEAPON_PATTERNS:
        for value in normalized_values:
            if pattern.search(value):
                return weapon
    return None


def normalize_stock_status(text: str | None) -> str | None:
    normalized = compare_text(text)
    if not normalized:
        return None

    if any(token in normalized for token in ("out of stock", "sold out", "unavailable", "nincs keszleten", "elfogyott")):
        return "out_of_stock"
    if "only" in normalized and "left" in normalized:
        return "limited"
    if any(token in normalized for token in ("limited", "low stock", "csak")):
        return "limited"
    if any(token in normalized for token in ("in stock", "available", "add to cart", "keszleten", "raktaron")):
        return "in_stock"
    return None


def absolute_url(url: str | None, base_url: str = BASE_URL) -> str | None:
    if not url:
        return None
    return urljoin(base_url, url.strip())


def source_id_from_url(url: str | None) -> str:
    parsed = urlparse(url or "")
    slug = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if slug:
        return slug
    digest = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16]
    return f"url-{digest}"


def listing_root_key(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    return parsed.scheme, parsed.netloc, parsed.path.rstrip("/")


def text_from_elements(elements: Iterable[Any]) -> str | None:
    return clean_text(" ".join(element.get_text(" ", strip=True) for element in elements))


def first_text(container: Any, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        element = container.select_one(selector)
        if not element:
            continue
        text = element.get("content") if element.name == "meta" else element.get_text(" ", strip=True)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned
    return None


def first_url(container: Any, selectors: Iterable[str], *, base_url: str = BASE_URL) -> str | None:
    for selector in selectors:
        element = container.select_one(selector)
        if element and element.get("href"):
            return absolute_url(element["href"], base_url)
    return None


def image_url_from_container(container: Any, *, base_url: str = BASE_URL) -> str | None:
    meta = container.select_one("meta[property='og:image'], meta[name='twitter:image']")
    if meta and meta.get("content"):
        return absolute_url(meta["content"], base_url)

    for selector in (
        "img.product-image-photo",
        ".product.media img",
        ".gallery-placeholder img",
        ".fotorama img",
        "img",
    ):
        image = container.select_one(selector)
        if not image:
            continue
        for attr in ("src", "data-src", "data-original"):
            if image.get(attr) and not str(image[attr]).startswith("data:"):
                return absolute_url(image[attr], base_url)
    return None


def price_text_from_container(container: Any) -> str | None:
    price_nodes = container.select(".price-box, .price-container, .price-final_price, .price")
    if price_nodes:
        return text_from_elements(price_nodes)
    return None


def stock_status_from_container(container: Any, extra_text: str | None = None) -> str | None:
    parts: list[str] = []
    for element in container.select(".stock, .availability, .product-info-stock-sku, button, .actions-primary"):
        text = element.get_text(" ", strip=True)
        if text:
            parts.append(text)
        for attr in ("title", "aria-label"):
            if element.get(attr):
                parts.append(str(element[attr]))
    if extra_text:
        parts.append(extra_text)
    return normalize_stock_status(" ".join(parts))


def listing_cards(soup: BeautifulSoup) -> list[Any]:
    cards = soup.select("li.product-item")
    if cards:
        return cards
    cards = soup.select(".products .product-item")
    if cards:
        return cards
    return soup.select(".product-item-info")


def parse_listing_products(
    html: str,
    *,
    listing_url: str,
    category_hint: str | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    category = normalize_category(category_hint, listing_url)
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for card in listing_cards(soup):
        name = first_text(card, (".product-item-link", ".product.name a", ".product-item-name", "a[href]"))
        product_url = first_url(
            card,
            (".product-item-link", ".product.name a", "a.product-item-photo", "a[href]"),
        )
        if not name or not product_url:
            continue
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        price_text = price_text_from_container(card)
        price, currency = parse_price(price_text)
        row = {
            "source": SOURCE,
            "source_id": source_id_from_url(product_url),
            "name": name,
            "brand": "PBT",
            "category": category,
            "weapon": normalize_weapon(name, category_hint),
            "price": price,
            "currency": currency,
            "image_url": image_url_from_container(card),
            "product_url": product_url,
            "stock_status": stock_status_from_container(card),
            "metadata": {
                key: value
                for key, value in {
                    "listing_url": listing_url,
                    "price_text": price_text,
                }.items()
                if value
            },
            "scraped_at": scraped_at,
        }
        rows.append(row)

    return rows


def extract_sku(soup: BeautifulSoup) -> str | None:
    sku = first_text(
        soup,
        (
            ".product.attribute.sku .value",
            "[itemprop='sku']",
            ".sku .value",
            ".product-info-main .sku",
        ),
    )
    if sku and label_key(sku) not in SKU_LABELS:
        return sku

    for element in soup.find_all(string=True):
        label = label_key(element)
        if label not in SKU_LABELS:
            continue
        parent = element.parent
        if not parent:
            continue
        sibling = parent.find_next(
            string=lambda value: bool(value and clean_text(value) and label_key(value) not in SKU_LABELS)
        )
        if sibling:
            return clean_text(sibling)
    return None


def extract_additional_attributes(soup: BeautifulSoup) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for table in soup.select(".additional-attributes, table.data, table.additional-attributes"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key_text = clean_text(cells[0].get_text(" ", strip=True))
            value_text = clean_text(" ".join(cell.get_text(" ", strip=True) for cell in cells[1:]))
            if not key_text or not value_text:
                continue
            attributes[label_key(key_text)] = value_text
    return attributes


def extract_category_candidates(soup: BeautifulSoup, listing_row: dict[str, Any] | None) -> list[str]:
    candidates = [
        element.get_text(" ", strip=True)
        for element in soup.select(
            ".breadcrumbs a, .breadcrumbs strong, .category-link, "
            ".product.attribute.category a, .product-info-main a"
        )
    ]
    if listing_row and listing_row.get("category"):
        candidates.append(str(listing_row["category"]))
    return [candidate for candidate in (clean_text(value) for value in candidates) if candidate]


def extract_option_sizes(soup: BeautifulSoup) -> list[str]:
    sizes: list[str] = []

    for swatch in soup.select(".swatch-attribute"):
        label = first_text(swatch, (".swatch-attribute-label",))
        if label_key(label) != "size":
            continue
        for option in swatch.select(".swatch-option, [option-label]"):
            text = clean_text(option.get("option-label") or option.get_text(" ", strip=True))
            if text and text not in sizes:
                sizes.append(text)

    for select in soup.select("select[name*='super_attribute'], select[id*='attribute']"):
        for option in select.select("option"):
            text = clean_text(option.get_text(" ", strip=True))
            if not text or compare_text(text).startswith(("choose", "select", "valassz")):
                continue
            if text not in sizes:
                sizes.append(text)

    return sizes


def extract_size_chart(soup: BeautifulSoup) -> dict[str, list[str]]:
    charts: dict[str, list[str]] = {}
    for table in soup.select(".size-chart table, table"):
        rows = table.select("tr")
        table_data: dict[str, list[str]] = {}
        for row in rows:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key = clean_text(cells[0].get_text(" ", strip=True))
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells[1:]]
            values = [value for value in values if value]
            if key and values:
                table_data[key] = values

        keys = " ".join(table_data)
        if re.search(r"order\s+size|height\s+cm|sleeve|lenght|length|méret", keys, re.I):
            charts.update(table_data)
    return charts


def discover_pagination_urls(html: str, listing_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    current_root = listing_root_key(listing_url)
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.select(".pages a[href], .toolbar a[href], a[href*='?p='], a[href*='&p=']"):
        href = absolute_url(link.get("href"), listing_url)
        if not href or href == listing_url:
            continue
        if listing_root_key(href) != current_root:
            continue

        link_text = compare_text(" ".join([link.get_text(" ", strip=True), link.get("aria-label", ""), link.get("title", "")]))
        if "p=" not in href and not re.search(r"\b(page|next|previous|prev)\b|\b\d+\b", link_text):
            continue
        if href not in seen:
            urls.append(href)
            seen.add(href)
    return urls


def parse_product_detail(
    html: str,
    *,
    product_url: str,
    listing_row: dict[str, Any] | None = None,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    attributes = extract_additional_attributes(soup)

    name = first_text(soup, ("h1.page-title", ".page-title", "h1"))
    if not name and listing_row:
        name = listing_row.get("name")

    sku = attributes.get("sku") or extract_sku(soup)
    price_text = price_text_from_container(soup)
    price, currency = parse_price(price_text)

    category_candidates = extract_category_candidates(soup, listing_row)
    category = normalize_category(*category_candidates)
    if not category and listing_row:
        category = listing_row.get("category")

    overview = first_text(soup, (".product.attribute.overview", ".product.attribute.description", ".product-info-main"))
    weapon = normalize_weapon(attributes.get("weapon"), name, overview, " ".join(category_candidates))
    stock_status = stock_status_from_container(soup, attributes.get("stock"))
    image_url = image_url_from_container(soup) or (listing_row or {}).get("image_url")
    sizes = extract_option_sizes(soup)
    size_chart = extract_size_chart(soup)

    metadata = dict((listing_row or {}).get("metadata") or {})
    metadata.update(
        {
            key: value
            for key, value in {
                "sku": sku,
                "price_text": price_text or metadata.get("price_text"),
                "sizes": sizes or None,
                "size_chart": size_chart or None,
            }.items()
            if value
        }
    )
    for key, value in attributes.items():
        if key not in {"sku", "weapon", "stock"} and value:
            metadata[key] = value

    absolute_product_url = absolute_url(product_url) or product_url
    return {
        "source": SOURCE,
        "source_id": sku or (listing_row or {}).get("source_id") or source_id_from_url(absolute_product_url),
        "name": name,
        "brand": "PBT",
        "category": category,
        "weapon": weapon,
        "price": price if price is not None else (listing_row or {}).get("price"),
        "currency": currency or (listing_row or {}).get("currency"),
        "image_url": image_url,
        "product_url": absolute_product_url,
        "stock_status": stock_status or (listing_row or {}).get("stock_status"),
        "metadata": metadata,
        "scraped_at": scraped_at,
    }


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code in {401, 403, 429, 503}:
        raise BlockedAccessError(f"{response.status_code} blocked for {url}")
    response.raise_for_status()
    return response.text


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def upsert_product_rows(client: Any, rows: list[dict[str, Any]], *, batch_size: int = UPSERT_BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    valid_rows = [row for row in rows if valid_product_row(row)]

    for index in range(0, len(valid_rows), batch_size):
        batch = valid_rows[index : index + batch_size]
        try:
            client.table("fs_products").upsert(batch, on_conflict="source,source_id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_products upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def category_hint_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.replace("-", " ")
    return normalize_category(path)


def scrape_pbt_products(
    *,
    client: Any | None = None,
    listing_urls: Iterable[str] = DEFAULT_LISTING_URLS,
    fetcher: Callable[[str], str] = fetch_html,
    request_delay: float = REQUEST_DELAY,
    log_run: bool = True,
    max_pages: int = 20,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    initial_listing_urls = tuple(listing_urls)
    pending_listing_urls = list(initial_listing_urls)
    queued_counts: dict[tuple[str, str, str], int] = {}
    for url in pending_listing_urls:
        root = listing_root_key(url)
        queued_counts[root] = queued_counts.get(root, 0) + 1

    seen_listing_urls: set[str] = set()
    run_log = ScraperRunLogger("scrape_pbt_products").start() if log_run else None
    previous_state = get_state(STATE_SOURCE, "last_run")

    read = written = failed = skipped = blocked = 0
    errors: list[str] = []
    source_ids: set[str] = set()

    try:
        while pending_listing_urls:
            listing_url = pending_listing_urls.pop(0)
            if listing_url in seen_listing_urls:
                continue
            seen_listing_urls.add(listing_url)

            try:
                listing_html = fetcher(listing_url)
                listing_rows = parse_listing_products(
                    listing_html,
                    listing_url=listing_url,
                    category_hint=category_hint_from_url(listing_url),
                )
            except BlockedAccessError as exc:
                blocked += 1
                failed += 1
                errors.append(str(exc))
                print(f"  PBT listing blocked for {listing_url}: {exc}")
                continue
            except Exception as exc:
                failed += 1
                errors.append(f"{listing_url}: {exc}")
                print(f"  PBT listing fetch/parse failed for {listing_url}: {exc}")
                continue

            for next_url in discover_pagination_urls(listing_html, listing_url):
                root = listing_root_key(next_url)
                if next_url in seen_listing_urls or next_url in pending_listing_urls:
                    continue
                if queued_counts.get(root, 0) >= max_pages:
                    continue
                pending_listing_urls.append(next_url)
                queued_counts[root] = queued_counts.get(root, 0) + 1

            read += len(listing_rows)
            if not listing_rows:
                skipped += 1
                continue

            product_rows: list[dict[str, Any]] = []
            for listing_row in listing_rows:
                detail_url = listing_row["product_url"]
                try:
                    detail_html = fetcher(detail_url)
                    product_row = parse_product_detail(
                        detail_html,
                        product_url=detail_url,
                        listing_row=listing_row,
                    )
                except BlockedAccessError as exc:
                    blocked += 1
                    failed += 1
                    product_row = dict(listing_row)
                    product_row["metadata"] = dict(product_row.get("metadata") or {})
                    product_row["metadata"]["detail_blocked"] = str(exc)
                    errors.append(f"{detail_url}: {exc}")
                    print(f"  PBT detail blocked for {detail_url}: {exc}")
                except Exception as exc:
                    failed += 1
                    product_row = dict(listing_row)
                    product_row["metadata"] = dict(product_row.get("metadata") or {})
                    product_row["metadata"]["detail_error"] = str(exc)
                    errors.append(f"{detail_url}: {exc}")
                    print(f"  PBT detail fetch/parse failed for {detail_url}: {exc}")

                product_rows.append(product_row)
                if product_row.get("source_id"):
                    source_ids.add(str(product_row["source_id"]))

                if request_delay:
                    time.sleep(request_delay)

            batch_written, batch_failed = upsert_product_rows(client, product_rows)
            written += batch_written
            failed += batch_failed

        summary = {
            "read": read,
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "blocked": blocked,
            "source_ids": len(source_ids),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "errors": errors[:10],
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(STATE_SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={"read": read, "blocked": blocked, "source_ids": sorted(source_ids), "errors": errors[:5]},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"PBT products scrape starting - {datetime.now(timezone.utc).isoformat()}")
    summary = scrape_pbt_products()
    print(
        "PBT products scrape complete - "
        f"read={summary['read']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}, blocked={summary['blocked']}"
    )


if __name__ == "__main__":
    main()
