from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scripts.rate_limiter import RateLimiter


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "leon_paul"
BRAND = "Leon Paul"
BASE_URL = "https://www.leonpaul.com/"
UPSERT_BATCH_SIZE = int(os.environ.get("LEONPAUL_UPSERT_BATCH_SIZE", "100"))
REQUEST_RPS = float(os.environ.get("LEONPAUL_REQUEST_RPS", "0.5"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CATEGORY_URLS: dict[str, str] = {
    "Clothing": "https://www.leonpaul.com/fencing-clothing-uniforms.html",
    "Masks": "https://www.leonpaul.com/fencing-masks.html",
    "Weapons": "https://www.leonpaul.com/fencing-weapons.html",
    "Bags": "https://www.leonpaul.com/fencing-bags.html",
}

CURRENCY_BY_SYMBOL = {
    "\u00a3": "GBP",
    "$": "USD",
    "\u20ac": "EUR",
}
MONEY_RE = re.compile(r"([\u00a3$\u20ac])\s*([0-9][0-9.,]*)")
WEAPON_PATTERNS = (
    (re.compile(r"\bfoil\b", re.I), "foil"),
    (re.compile(r"\bepee\b|\bep\u00e9e\b", re.I), "epee"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "sabre"),
)
STOCK_PATTERNS = (
    (re.compile(r"\bout\s+of\s+stock\b|\bunavailable\b", re.I), "out_of_stock"),
    (re.compile(r"\bback\s*order\b|\bpre\s*order\b", re.I), "backorder"),
    (re.compile(r"\bin\s+stock\b|\bavailable\b", re.I), "in_stock"),
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value)).replace("\xa0", " ")
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_money_number(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = ".".join(parts) if len(parts[-1]) == 2 else "".join(parts)
    try:
        return float(text)
    except ValueError:
        return None


def parse_price(text: str | None) -> tuple[float | None, str | None, str | None]:
    price_text = clean_text(text)
    if not price_text:
        return None, None, None

    values: list[tuple[float, str]] = []
    for symbol, raw_number in MONEY_RE.findall(price_text):
        price = parse_money_number(raw_number)
        if price is not None:
            values.append((price, CURRENCY_BY_SYMBOL[symbol]))

    if not values:
        return None, None, price_text

    price, currency = min(values, key=lambda item: item[0])
    return price, currency, price_text


def first_text(root, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        element = root.select_one(selector)
        if not element:
            continue
        text = element.get("alt") or element.get("title") if element.name == "img" else element.get_text(" ", strip=True)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned
    return None


def first_url(root, selectors: Iterable[str], base_url: str) -> str | None:
    for selector in selectors:
        element = root.select_one(selector)
        if element and element.get("href"):
            return urljoin(base_url, element["href"]).split("#", 1)[0]
    element = root.find("a", href=True)
    if element:
        return urljoin(base_url, element["href"]).split("#", 1)[0]
    return None


def first_image_url(root, base_url: str) -> str | None:
    image = root.select_one("img")
    if not image:
        return None
    for attr in ("src", "data-src", "data-original", "data-lazy"):
        value = image.get(attr)
        if value and not value.startswith("data:"):
            return urljoin(base_url, value)
    return None


def source_id_from_url(product_url: str | None) -> str | None:
    if not product_url:
        return None
    path = urlparse(product_url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    slug = re.sub(r"\.html?$", "", slug, flags=re.I)
    return slug or None


def infer_weapon(*texts: str | None) -> str | None:
    combined = " ".join(text for text in texts if text)
    for pattern, weapon in WEAPON_PATTERNS:
        if pattern.search(combined):
            return weapon
    return None


def stock_status_from_text(text: str | None) -> str:
    if not text:
        return "unknown"
    for pattern, status in STOCK_PATTERNS:
        if pattern.search(text):
            return status
    return "unknown"


def price_text_from(root) -> str | None:
    pieces: list[str] = []
    for element in root.select(".price, .price-box, [data-price-amount]"):
        if element.get("data-price-amount"):
            pieces.append(str(element["data-price-amount"]))
        pieces.append(element.get_text(" ", strip=True))
    return clean_text(" ".join(piece for piece in pieces if piece))


def parse_listing_products(
    listing_html: str,
    listing_url: str,
    *,
    category: str | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(listing_html, "html.parser")
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for card in soup.select("li.product-item, .product-item"):
        product_url = first_url(card, (".product-item-link", ".product-item-name a", "a[href]"), listing_url)
        name = first_text(card, (".product-item-link", ".product-item-name", ".name", "a[href]"))
        if not product_url or not name:
            continue

        source_id = (
            clean_text(card.get("data-product-sku") or card.get("data-sku"))
            or clean_text(card.get("data-product-id"))
            or source_id_from_url(product_url)
        )
        if not source_id:
            continue

        unique_key = f"{source_id}:{product_url}"
        if unique_key in seen:
            continue
        seen.add(unique_key)

        raw_price_text = price_text_from(card)
        price, currency, normalized_price_text = parse_price(raw_price_text)
        card_text = clean_text(card.get_text(" ", strip=True))
        stock_status = stock_status_from_text(card_text)
        image_url = first_image_url(card, listing_url)

        metadata = {
            "listing_url": listing_url,
            "listing_source_id": source_id,
            "price_text": normalized_price_text,
        }
        if card.get("data-product-id"):
            metadata["product_id"] = clean_text(card["data-product-id"])
        if price is None:
            metadata["missing_price_reason"] = "price_not_found"

        rows.append(
            {
                "source": SOURCE,
                "source_id": source_id,
                "name": name,
                "brand": BRAND,
                "category": category,
                "weapon": infer_weapon(name, category),
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


def parse_breadcrumb_category(soup: BeautifulSoup) -> str | None:
    crumbs = [
        clean_text(element.get_text(" ", strip=True))
        for element in soup.select(".breadcrumbs a, .breadcrumbs strong, .breadcrumbs .item")
    ]
    crumbs = [crumb for crumb in crumbs if crumb and crumb.lower() not in {"home"}]
    if len(crumbs) >= 2:
        return crumbs[-2]
    return crumbs[0] if crumbs else None


def select_label(soup: BeautifulSoup, element) -> str:
    element_id = element.get("id")
    if element_id:
        label = soup.select_one(f"label[for='{element_id}']")
        if label:
            text = clean_text(label.get_text(" ", strip=True))
            if text:
                return text
    return clean_text(element.get("name") or element_id) or "Option"


def parse_variant_options(soup: BeautifulSoup) -> dict[str, list[str]]:
    variants: dict[str, list[str]] = {}

    for select in soup.select("select"):
        values = [
            clean_text(option.get_text(" ", strip=True))
            for option in select.select("option")
            if option.get("value")
        ]
        values = [value for value in values if value]
        if values:
            variants[select_label(soup, select)] = list(dict.fromkeys(values))

    for attribute in soup.select(".swatch-attribute"):
        label_element = attribute.select_one(".swatch-attribute-label")
        label = clean_text(label_element.get_text(" ", strip=True)) if label_element else None
        label = label or clean_text(attribute.get("attribute-code") or attribute.get("data-attribute-code"))
        values = [
            clean_text(option.get("option-label") or option.get("aria-label") or option.get_text(" ", strip=True))
            for option in attribute.select(".swatch-option")
        ]
        values = [value for value in values if value]
        if label and values:
            variants[label] = list(dict.fromkeys(values))

    return variants


def parse_sku(soup: BeautifulSoup) -> str | None:
    for selector in ("[itemprop='sku']", ".product.attribute.sku .value", ".sku"):
        value = first_text(soup, (selector,))
        if value and value.lower() != "sku":
            return value
    sku_match = re.search(r"\bSKU\s*[:#]?\s*([A-Za-z0-9_.-]+)", soup.get_text(" ", strip=True), re.I)
    return sku_match.group(1) if sku_match else None


def parse_detail_product(detail_html: str, product_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(detail_html, "html.parser")
    heading = first_text(soup, ("h1.page-title", "h1", "[itemprop='name']"))
    sku = parse_sku(soup)
    raw_price_text = price_text_from(soup)
    price, currency, normalized_price_text = parse_price(raw_price_text)
    page_text = clean_text(soup.get_text(" ", strip=True)) or ""
    variant_options = parse_variant_options(soup)

    metadata: dict[str, Any] = {
        "detail_url": product_url,
        "detail_price_text": normalized_price_text,
    }
    if variant_options:
        metadata["variant_options"] = variant_options
        metadata["variant_count"] = sum(len(values) for values in variant_options.values())
    if price is None:
        if re.search(r"\b(region|select your region|view prices|currency)\b", page_text, re.I):
            metadata["missing_price_reason"] = "region_or_price_not_visible"
        else:
            metadata["missing_price_reason"] = "price_not_found"

    category = parse_breadcrumb_category(soup)
    stock_text = clean_text(
        " ".join(element.get_text(" ", strip=True) for element in soup.select(".stock, .availability"))
    )

    return {
        "source_id": sku or source_id_from_url(product_url),
        "name": heading,
        "brand": BRAND,
        "category": category,
        "weapon": infer_weapon(heading, category),
        "price": price,
        "currency": currency,
        "image_url": first_image_url(soup, product_url),
        "product_url": product_url,
        "stock_status": stock_status_from_text(stock_text),
        "variant_options": variant_options,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def merge_metadata(listing: dict[str, Any], detail: dict[str, Any] | None) -> dict[str, Any]:
    metadata = dict(listing.get("metadata") or {})
    if not detail:
        return metadata

    detail_metadata = dict(detail.get("metadata") or {})
    detail_missing_price = detail_metadata.pop("missing_price_reason", None)
    if detail_missing_price:
        metadata["detail_missing_price_reason"] = detail_missing_price
    for key, value in detail_metadata.items():
        if value is not None:
            metadata[key] = value
    if detail.get("variant_options"):
        metadata["variant_options"] = detail["variant_options"]
    if detail.get("source_id"):
        metadata["detail_source_id"] = detail["source_id"]
    return metadata


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def build_product_row(
    listing: dict[str, Any],
    detail: dict[str, Any] | None = None,
    *,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    detail = detail or {}
    metadata = merge_metadata(listing, detail)
    row = {
        "source": SOURCE,
        "source_id": first_non_empty(detail.get("source_id"), listing.get("source_id")),
        "name": first_non_empty(detail.get("name"), listing.get("name")),
        "brand": BRAND,
        "category": first_non_empty(detail.get("category"), listing.get("category")),
        "weapon": first_non_empty(detail.get("weapon"), listing.get("weapon")),
        "price": first_non_empty(detail.get("price"), listing.get("price")),
        "currency": first_non_empty(detail.get("currency"), listing.get("currency")),
        "image_url": first_non_empty(detail.get("image_url"), listing.get("image_url")),
        "product_url": first_non_empty(detail.get("product_url"), listing.get("product_url")),
        "stock_status": first_non_empty(detail.get("stock_status"), listing.get("stock_status"), "unknown"),
        "metadata": {key: value for key, value in metadata.items() if value is not None},
        "scraped_at": scraped_at or listing.get("scraped_at") or datetime.now(timezone.utc).isoformat(),
    }
    if row["price"] is None and "missing_price_reason" not in row["metadata"]:
        row["metadata"]["missing_price_reason"] = "price_not_found"
    return row


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def upsert_products(client, rows: list[dict[str, Any]], batch_size: int = UPSERT_BATCH_SIZE) -> tuple[int, int]:
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
    failed += len(rows) - len(valid_rows)
    return written, failed


def fetch_page(
    url: str,
    *,
    session: requests.Session | None = None,
    rate_limiter: RateLimiter | None = None,
) -> dict[str, Any]:
    session = session or requests.Session()
    limiter = rate_limiter or RateLimiter(default_rps=REQUEST_RPS)
    domain = urlparse(url).netloc or "www.leonpaul.com"
    limiter.wait(domain, REQUEST_RPS)
    try:
        response = session.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        response.raise_for_status()
        limiter.record_success(domain)
        return {"html": response.text, "url": response.url, "status_code": response.status_code}
    except Exception:
        limiter.record_failure(domain)
        raise


def coerce_fetch_result(result: Any, requested_url: str) -> tuple[str, str]:
    if isinstance(result, str):
        return result, requested_url
    if isinstance(result, Mapping):
        html_text = result.get("html") or result.get("text")
        final_url = result.get("url") or requested_url
        if html_text is None:
            raise ValueError("fetcher mapping must include html or text")
        return str(html_text), str(final_url)
    if isinstance(result, tuple) and len(result) >= 1:
        html_text = result[0]
        final_url = result[1] if len(result) > 1 else requested_url
        return str(html_text), str(final_url)
    raise TypeError(f"Unsupported fetcher result for {requested_url}: {type(result).__name__}")


def scrape_leonpaul(
    *,
    client=None,
    category_urls: Mapping[str, str] | None = None,
    fetcher: Callable[[str], Any] = fetch_page,
    log_run: bool = True,
    max_products: int | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    categories = dict(category_urls or CATEGORY_URLS)
    run_log = ScraperRunLogger("scrape_leonpaul").start() if log_run else None
    previous_state = get_state(SOURCE, "last_run")

    read = written = failed = skipped = 0
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        for category, listing_url in categories.items():
            try:
                listing_html, final_listing_url = coerce_fetch_result(fetcher(listing_url), listing_url)
                listing_rows = parse_listing_products(listing_html, final_listing_url, category=category)
            except Exception as exc:
                failed += 1
                print(f"  Leon Paul listing fetch/parse failed for {listing_url}: {exc}")
                continue

            if not listing_rows:
                skipped += 1
                continue

            for listing in listing_rows:
                if max_products is not None and read >= max_products:
                    break
                product_url = listing["product_url"]
                if product_url in seen_urls:
                    continue
                seen_urls.add(product_url)
                read += 1

                detail: dict[str, Any] | None = None
                try:
                    detail_html, final_product_url = coerce_fetch_result(fetcher(product_url), product_url)
                    detail = parse_detail_product(detail_html, final_product_url)
                except Exception as exc:
                    failed += 1
                    listing.setdefault("metadata", {})["detail_fetch_error"] = str(exc)[:500]

                rows.append(build_product_row(listing, detail))

            if max_products is not None and read >= max_products:
                break

        if rows:
            batch_written, batch_failed = upsert_products(client, rows)
            written += batch_written
            failed += batch_failed

        summary = {
            "read": read,
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata={"read": read})
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Leon Paul product scrape starting - {datetime.now(timezone.utc).isoformat()}")
    summary = scrape_leonpaul()
    print(
        "Leon Paul product scrape complete - "
        f"read={summary['read']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()
