from __future__ import annotations

import os
import re
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

SOURCE = "blue_gauntlet"
STATE_SOURCE = "blue_gauntlet_products"
PRODUCT_TABLE = "fs_products"
BASE_URL = "https://www.blue-gauntlet.com/"
UPSERT_BATCH_SIZE = 100
REQUEST_RPS = 0.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_LISTING_URLS = (
    BASE_URL,
    "https://www.blue-gauntlet.com/Clearance_c_311.html",
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
    "updated_at",
}

CURRENCY_BY_SYMBOL = {"$": "USD", "£": "GBP", "€": "EUR"}
MONEY_RE = re.compile(r"([$£€])\s*([0-9][0-9.,]*)")
PRODUCT_ID_RE = re.compile(r"_p_(\d+)\.html", re.I)
CATEGORY_URL_RE = re.compile(r"_c_\d+\.html(?:$|[?#])", re.I)


@dataclass(frozen=True)
class ParsedPrice:
    amount: float | None
    currency: str | None
    regular_amount: float | None = None
    is_sale: bool = False
    raw_text: str | None = None


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def absolute_url(url: str | None, *, base_url: str = BASE_URL) -> str | None:
    if not url:
        return None
    return urljoin(base_url, url).split("#", 1)[0]


def parse_money_number(raw: str) -> float | None:
    text = raw.strip()
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = ".".join(parts) if len(parts[-1]) == 2 else "".join(parts)
    try:
        return float(text)
    except ValueError:
        return None


def _money_matches(text: str) -> list[tuple[float, str, int]]:
    matches: list[tuple[float, str, int]] = []
    for match in MONEY_RE.finditer(text):
        prefix = text[max(0, match.start() - 24) : match.start()].lower()
        if "saving" in prefix:
            continue
        amount = parse_money_number(match.group(2))
        if amount is None:
            continue
        matches.append((amount, CURRENCY_BY_SYMBOL.get(match.group(1), "USD"), match.start()))
    return matches


def parse_price(text: str | None) -> ParsedPrice:
    cleaned = clean_text(text)
    if not cleaned:
        return ParsedPrice(None, None)

    matches = _money_matches(cleaned)
    if not matches:
        return ParsedPrice(None, None, raw_text=cleaned)

    sale_match = re.search(
        r"(?:on\s+sale|sale\s+price|your\s+price|our\s+price)\s*:?\s*([$£€])\s*([0-9][0-9.,]*)",
        cleaned,
        re.I,
    )
    if sale_match:
        amount = parse_money_number(sale_match.group(2))
        currency = CURRENCY_BY_SYMBOL.get(sale_match.group(1), "USD")
        if amount is not None:
            regulars = [value for value, _currency, _pos in matches if value > amount]
            return ParsedPrice(
                amount=amount,
                currency=currency,
                regular_amount=max(regulars) if regulars else None,
                is_sale=bool(regulars) or bool(re.search(r"\bsale\b", cleaned, re.I)),
                raw_text=cleaned,
            )

    if re.search(r"\bsale\b", cleaned, re.I) and len(matches) > 1:
        amount, currency, _pos = min(matches, key=lambda item: item[0])
        regulars = [value for value, _currency, _pos in matches if value > amount]
        return ParsedPrice(
            amount=amount,
            currency=currency,
            regular_amount=max(regulars) if regulars else None,
            is_sale=True,
            raw_text=cleaned,
        )

    amount, currency, _pos = min(matches, key=lambda item: item[0])
    return ParsedPrice(amount=amount, currency=currency, raw_text=cleaned)


def normalize_stock_status(text: str | None) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return "unknown"
    lowered = cleaned.lower()
    if re.search(r"\b(out\s+of\s+stock|sold\s+out|back\s*ordered|unavailable)\b", lowered):
        return "out_of_stock"
    if re.search(r"\bin\s+stock\b", lowered):
        return "in_stock"
    if "waiting list" in lowered:
        return "out_of_stock"
    return "unknown"


def infer_weapon(*parts: str | None) -> str | None:
    text = " ".join(part for part in parts if part).lower()
    if not text:
        return None
    if re.search(r"\b(3[-\s]?wpn|three[-\s]?weapon|all[-\s]?weapon|universal)\b", text):
        return "All"

    weapons: list[str] = []
    if re.search(r"\bfoil\b", text):
        weapons.append("Foil")
    if re.search(r"\b(epee|epée)\b", text):
        weapons.append("Epee")
    if re.search(r"\b(saber|sabre)\b", text):
        weapons.append("Sabre")
    return ",".join(weapons) if weapons else None


def infer_brand(name: str | None) -> str:
    text = name or ""
    if re.search(r"uhlmann\s*/\s*allstar|uhlmann.*allstar|allstar.*uhlmann", text, re.I):
        return "Uhlmann/Allstar"
    for pattern, brand in (
        (r"\bblue\s+gauntlet\b|\bbg\b", "Blue Gauntlet"),
        (r"\ballstar\b", "Allstar"),
        (r"\buhlmann\b", "Uhlmann"),
        (r"\bprieur\b", "Prieur"),
        (r"\bpbt\b", "PBT"),
        (r"\bfolo\b", "FOLO"),
        (r"\bnegrini\b", "Negrini"),
        (r"\bkempa\b", "Kempa"),
        (r"\bleon\s+paul\b", "Leon Paul"),
        (r"\babsolute\b", "Absolute Fencing"),
    ):
        if re.search(pattern, text, re.I):
            return brand
    return "Blue Gauntlet"


def source_id_from_url(product_url: str | None) -> str | None:
    if not product_url:
        return None
    match = PRODUCT_ID_RE.search(product_url)
    if match:
        return match.group(1)
    path = urlparse(product_url).path.strip("/")
    return path or None


def normalize_sku(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"^part\s+number\s*:?", "", text, flags=re.I).strip()
    return text or None


def stable_source_id(*, sku: str | None = None, product_url: str | None = None) -> str | None:
    return normalize_sku(sku) or source_id_from_url(product_url)


def _first_text(element, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        found = element.select_one(selector)
        if not found:
            continue
        if found.name == "img":
            text = found.get("alt") or found.get("title")
        else:
            text = found.get_text(" ", strip=True)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned
    return None


def _first_product_url(element) -> str | None:
    for selector in (".name[href]", ".name a[href]", ".product-name[href]", ".product-name a[href]", "a[href]"):
        found = element.select_one(selector)
        if found and found.get("href"):
            return absolute_url(found.get("href"))
    return None


def _first_image_url(element) -> str | None:
    for selector in (
        ".main-image img",
        ".product-image img",
        "[itemprop='image']",
        "img[data-src]",
        "img[src]",
    ):
        found = element.select_one(selector)
        if not found:
            continue
        src = found.get("data-src") or found.get("src")
        image_url = absolute_url(src)
        if image_url:
            return image_url
    return None


def _price_text(element) -> str | None:
    parts = []
    for selector in (".price", ".product-price", "[class*='price']", "#price"):
        parts.extend(found.get_text(" ", strip=True) for found in element.select(selector))
    return clean_text(" ".join(parts)) or clean_text(element.get_text(" ", strip=True))


def _review_count(element) -> int | None:
    parts = []
    for selector in (".reviews", "[class*='review']", "[alt*='Rating']"):
        for found in element.select(selector):
            parts.append(found.get_text(" ", strip=True))
            for attr in ("alt", "title", "aria-label"):
                if found.get(attr):
                    parts.append(found[attr])
    text = " ".join(parts)
    match = re.search(r"\((\d+)\)|(\d+)\s+reviews?", text, re.I)
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def _category_from_listing(soup: BeautifulSoup, fallback: str | None = None) -> str | None:
    title = _first_text(soup, ("h1", ".page_headers", ".category-title", "title"))
    return title or fallback


def _category_from_detail(soup: BeautifulSoup) -> str | None:
    breadcrumb_texts = [
        clean_text(node.get_text(" ", strip=True))
        for node in soup.select(".breadcrumbs a, .breadcrumb a, [class*='breadcrumb'] a")
    ]
    categories = [
        text
        for text in breadcrumb_texts
        if text and text.lower() not in {"home", "blue gauntlet"}
    ]
    return categories[-1] if categories else None


def _sku_from_detail(soup: BeautifulSoup) -> str | None:
    for selector in (".product-id", ".part-number", "[class*='part']", "[id*='part']"):
        found = soup.select_one(selector)
        if not found:
            continue
        match = re.search(
            r"part\s+number\s*:?\s*([A-Za-z0-9][A-Za-z0-9._/-]*)",
            found.get_text(" ", strip=True),
            re.I,
        )
        if match:
            return normalize_sku(match.group(1))

    text = soup.get_text(" ", strip=True)
    match = re.search(r"part\s+number\s*:?\s*([A-Za-z0-9][A-Za-z0-9._/-]*)", text, re.I)
    return normalize_sku(match.group(1)) if match else None


def _availability_text(soup: BeautifulSoup) -> str | None:
    for selector in (".availability", "[class*='availability']", "#availability"):
        found = soup.select_one(selector)
        if found:
            return clean_text(found.get_text(" ", strip=True))
    text = soup.get_text(" ", strip=True)
    match = re.search(r"availability\s*:?\s*(in\s+stock|out\s+of\s+stock|sold\s+out)", text, re.I)
    return clean_text(match.group(1)) if match else None


def _description_text(soup: BeautifulSoup) -> str | None:
    for selector in (
        "#description",
        ".product-description",
        "[itemprop='description']",
        "#tab-description",
        ".tab-content",
    ):
        found = soup.select_one(selector)
        if found:
            return clean_text(found.get_text(" ", strip=True))
    return None


def _metadata_for_price(price: ParsedPrice, *, price_text: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if price_text:
        metadata["price_text"] = price_text
    if price.regular_amount is not None:
        metadata["regular_price"] = price.regular_amount
    if price.is_sale:
        metadata["sale"] = True
    return metadata


def parse_listing_products(
    html: str,
    *,
    listing_url: str | None = None,
    category: str | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    category = category or _category_from_listing(soup)
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for card in soup.select(".product-item"):
        name = _first_text(card, (".name", ".product-name", ".product-item-name", "a[href]"))
        product_url = _first_product_url(card)
        if not name or not product_url:
            continue

        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        price_text = _price_text(card)
        price = parse_price(price_text)
        stock_status = normalize_stock_status(card.get_text(" ", strip=True))
        product_source_id = source_id_from_url(product_url)
        metadata = _metadata_for_price(price, price_text=price_text)
        metadata.update(
            {
                "listing_url": listing_url,
                "source_product_id": product_source_id,
                "review_count": _review_count(card),
            }
        )

        rows.append(
            {
                "source": SOURCE,
                "source_id": stable_source_id(product_url=product_url),
                "name": name,
                "brand": infer_brand(name),
                "category": category,
                "weapon": infer_weapon(name, category),
                "price": price.amount,
                "currency": price.currency or "USD",
                "image_url": _first_image_url(card),
                "product_url": product_url,
                "stock_status": stock_status,
                "metadata": {key: value for key, value in metadata.items() if value is not None},
                "scraped_at": scraped_at,
                "updated_at": scraped_at,
            }
        )

    return rows


def parse_detail_product(
    html: str,
    *,
    product_url: str,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    product_url = absolute_url(product_url) or product_url
    name = _first_text(soup, ("h1", ".page_headers", ".product-title", ".name")) or ""
    category = _category_from_detail(soup)
    price_text = _price_text(soup)
    price = parse_price(price_text)
    sku = _sku_from_detail(soup)
    source_product_id = source_id_from_url(product_url)
    description = _description_text(soup)

    metadata = _metadata_for_price(price, price_text=price_text)
    metadata.update(
        {
            "sku": sku,
            "source_product_id": source_product_id,
            "description": description,
        }
    )

    return {
        "source": SOURCE,
        "source_id": stable_source_id(sku=sku, product_url=product_url),
        "name": name,
        "brand": infer_brand(name),
        "category": category,
        "weapon": infer_weapon(name, category),
        "price": price.amount,
        "currency": price.currency or "USD",
        "description": description,
        "image_url": _first_image_url(soup),
        "product_url": product_url,
        "stock_status": normalize_stock_status(_availability_text(soup)),
        "metadata": {key: value for key, value in metadata.items() if value is not None},
        "scraped_at": scraped_at,
        "updated_at": scraped_at,
    }


def merge_product_rows(listing_row: dict[str, Any], detail_row: dict[str, Any] | None) -> dict[str, Any]:
    if not detail_row:
        return listing_row

    merged = {**listing_row, **{key: value for key, value in detail_row.items() if value is not None}}
    listing_metadata = listing_row.get("metadata") or {}
    detail_metadata = detail_row.get("metadata") or {}
    merged["metadata"] = {**listing_metadata, **detail_metadata}
    if listing_row.get("category") and detail_row.get("category") != listing_row.get("category"):
        merged["metadata"]["listing_category"] = listing_row.get("category")
    if listing_row.get("stock_status") == "out_of_stock" and detail_row.get("stock_status") == "unknown":
        merged["stock_status"] = "out_of_stock"
    return merged


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def _row_for_upsert(row: dict[str, Any]) -> dict[str, Any]:
    upsert_row = {key: row.get(key) for key in PRODUCT_COLUMNS if key in row}
    metadata = dict(upsert_row.get("metadata") or {})
    if row.get("description") and "description" not in metadata:
        metadata["description"] = row["description"]
    upsert_row["metadata"] = metadata
    return upsert_row


def upsert_products(client, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    skipped = sum(1 for row in rows if not valid_product_row(row))
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not valid_product_row(row):
            continue
        deduped[(row["source"], row["source_id"])] = row

    valid_rows = list(deduped.values())
    written = 0
    failed = 0
    for index in range(0, len(valid_rows), UPSERT_BATCH_SIZE):
        batch = valid_rows[index : index + UPSERT_BATCH_SIZE]
        try:
            client.table(PRODUCT_TABLE).upsert(
                [_row_for_upsert(row) for row in batch],
                on_conflict="source,source_id",
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_products upsert batch {index // UPSERT_BATCH_SIZE} failed: {exc}")

    return written, failed, skipped


def fetch_page(
    url: str,
    *,
    rate_limiter: RateLimiter | None = None,
    session: Any = requests,
) -> str:
    domain = urlparse(url).netloc or "www.blue-gauntlet.com"
    if rate_limiter:
        rate_limiter.wait(domain, REQUEST_RPS)
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        if rate_limiter:
            rate_limiter.record_success(domain)
        return response.text
    except Exception:
        if rate_limiter:
            rate_limiter.record_failure(domain)
        raise


def discover_category_urls(html: str, *, base_url: str = BASE_URL) -> list[tuple[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    discovered: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        url = absolute_url(href, base_url=base_url)
        if not url or url in seen or not CATEGORY_URL_RE.search(url):
            continue
        seen.add(url)
        discovered.append((url, clean_text(anchor.get_text(" ", strip=True))))
    return discovered


def _fetch_with_injected_fetcher(
    url: str,
    *,
    fetcher: Callable[[str], str],
    rate_limiter: RateLimiter | None,
) -> str:
    if fetcher is fetch_page:
        return fetch_page(url, rate_limiter=rate_limiter)
    domain = urlparse(url).netloc or "www.blue-gauntlet.com"
    if rate_limiter:
        rate_limiter.wait(domain, REQUEST_RPS)
    try:
        html = fetcher(url)
        if rate_limiter:
            rate_limiter.record_success(domain)
        return html
    except Exception:
        if rate_limiter:
            rate_limiter.record_failure(domain)
        raise


def scrape_blue_gauntlet_products(
    *,
    client=None,
    listing_urls: Iterable[str] | None = None,
    fetcher: Callable[[str], str] = fetch_page,
    rate_limiter: RateLimiter | None = None,
    log_run: bool = True,
    discover_categories: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    rate_limiter = rate_limiter or RateLimiter(default_rps=REQUEST_RPS, jitter=0.2, backoff=5.0)
    run_log = ScraperRunLogger("scrape_blue_gauntlet_products").start() if log_run else None
    previous_state = get_state(STATE_SOURCE, "last_run")

    listing_queue: list[tuple[str, str | None]] = [
        (absolute_url(url) or url, None) for url in (listing_urls or DEFAULT_LISTING_URLS)
    ]
    queued = {url for url, _category in listing_queue}
    products: list[dict[str, Any]] = []
    read = failed = skipped = 0

    try:
        index = 0
        while index < len(listing_queue):
            listing_url, category_hint = listing_queue[index]
            index += 1
            try:
                listing_html = _fetch_with_injected_fetcher(
                    listing_url,
                    fetcher=fetcher,
                    rate_limiter=rate_limiter,
                )
            except Exception as exc:
                failed += 1
                print(f"  Blue Gauntlet listing fetch failed for {listing_url}: {exc}")
                continue

            if discover_categories and listing_url.rstrip("/") == BASE_URL.rstrip("/"):
                for category_url, category_name in discover_category_urls(listing_html):
                    if category_url not in queued:
                        listing_queue.append((category_url, category_name))
                        queued.add(category_url)

            listing_rows = parse_listing_products(
                listing_html,
                listing_url=listing_url,
                category=category_hint,
            )
            read += len(listing_rows)
            if not listing_rows:
                skipped += 1
                continue

            for listing_row in listing_rows:
                detail_row = None
                try:
                    detail_html = _fetch_with_injected_fetcher(
                        listing_row["product_url"],
                        fetcher=fetcher,
                        rate_limiter=rate_limiter,
                    )
                    detail_row = parse_detail_product(
                        detail_html,
                        product_url=listing_row["product_url"],
                        scraped_at=listing_row.get("scraped_at"),
                    )
                except Exception as exc:
                    failed += 1
                    listing_row.setdefault("metadata", {})["detail_error"] = str(exc)[:300]
                    print(f"  Blue Gauntlet detail fetch/parse failed for {listing_row['product_url']}: {exc}")
                products.append(merge_product_rows(listing_row, detail_row))

        written, upsert_failed, upsert_skipped = upsert_products(client, products)
        failed += upsert_failed
        skipped += upsert_skipped

        summary = {
            "read": read,
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "listing_urls": len(queued),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(STATE_SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={"read": read, "listing_urls": len(queued)},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Blue Gauntlet product scrape starting - {datetime.now(timezone.utc).isoformat()}")
    summary = scrape_blue_gauntlet_products()
    print(
        "Blue Gauntlet product scrape complete - "
        f"read={summary['read']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}, "
        f"listing_urls={summary['listing_urls']}"
    )


if __name__ == "__main__":
    main()
