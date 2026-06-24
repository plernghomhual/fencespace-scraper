from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

STATE_SOURCE = "equipment_reviews"
UPSERT_BATCH_SIZE = 100
REQUEST_DELAY = 1.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class RetailerConfig:
    source: str
    brand: str
    category: str
    base_url: str
    listing_urls: tuple[str, ...]
    card_selector: str
    name_selectors: tuple[str, ...]
    price_selectors: tuple[str, ...]
    rating_selectors: tuple[str, ...] = ()
    review_count_selectors: tuple[str, ...] = ()
    sku_selector: str | None = None


RETAILERS: dict[str, RetailerConfig] = {
    "absolute_fencing": RetailerConfig(
        source="absolute_fencing",
        brand="Absolute Fencing",
        category="Lames",
        base_url="https://www.absolutefencinggear.com/",
        listing_urls=("https://www.absolutefencinggear.com/uniforms/lame/foil",),
        card_selector="li.product-item",
        name_selectors=(".product-item-link", ".product-item-name", ".name", "a[href]"),
        price_selectors=(".price", ".price-box"),
        rating_selectors=(".rating-summary", ".rating-result", "[aria-label*='Rating']"),
        review_count_selectors=(".reviews-actions", ".reviews", "[href*='review']"),
    ),
    "leon_paul": RetailerConfig(
        source="leon_paul",
        brand="Leon Paul",
        category="Clothing",
        base_url="https://www.leonpaul.com/",
        listing_urls=("https://www.leonpaul.com/fencing-clothing-uniforms.html",),
        card_selector="li.product-item",
        name_selectors=(".product-item-link", ".product-item-name", ".name", "a[href]"),
        price_selectors=(".price", ".price-box"),
        rating_selectors=(".rating-summary", ".rating-result", "[aria-label*='Rating']"),
        review_count_selectors=(".reviews-actions", ".reviews", "[href*='review']"),
    ),
    "blue_gauntlet": RetailerConfig(
        source="blue_gauntlet",
        brand="Blue Gauntlet",
        category="Featured Products",
        base_url="https://www.blue-gauntlet.com/",
        listing_urls=("https://www.blue-gauntlet.com/",),
        card_selector=".product-item",
        name_selectors=(".name", ".product-name", "a[href]"),
        price_selectors=(".price", ".product-price"),
        rating_selectors=("[alt*='Rating']", ".rating"),
        review_count_selectors=(".reviews", "[alt*='Rating']", ".rating"),
    ),
    "allstar": RetailerConfig(
        source="allstar",
        brand="Allstar",
        category="Electric Jackets",
        base_url="https://allstar.de/en/",
        listing_urls=("https://allstar.de/en/clothing-footwear/electric-jackets/",),
        card_selector=".product-box",
        name_selectors=(".product-name", ".product-title", "a[href]"),
        price_selectors=(".product-price", ".product-price-info", ".price"),
        sku_selector=".product-ordernumber",
    ),
}

DEFAULT_RETAILERS = (
    RETAILERS["absolute_fencing"],
    RETAILERS["leon_paul"],
    RETAILERS["blue_gauntlet"],
    RETAILERS["allstar"],
)

BRAND_PATTERNS = (
    (re.compile(r"\bleon\s+paul\b|\blp\b", re.I), "Leon Paul"),
    (re.compile(r"\babsolute\b|\baf\b", re.I), "Absolute Fencing"),
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

CURRENCY_BY_SYMBOL = {"$": "USD", "£": "GBP", "€": "EUR"}
MONEY_RE = re.compile(r"([$£€])\s*([0-9][0-9.,]*)")


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


def first_text(card, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        element = card.select_one(selector)
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


def first_url(card, retailer: RetailerConfig) -> str | None:
    for selector in retailer.name_selectors:
        element = card.select_one(selector)
        if element and element.get("href"):
            return urljoin(retailer.base_url, element["href"])
    element = card.find("a", href=True)
    if not element:
        return None
    return urljoin(retailer.base_url, element["href"])


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


def parse_price(text: str | None) -> tuple[float | None, str | None]:
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


def price_from_card(card, retailer: RetailerConfig) -> tuple[float | None, str | None, str | None]:
    texts: list[str] = []
    for selector in retailer.price_selectors:
        texts.extend(element.get_text(" ", strip=True) for element in card.select(selector))
    if not texts:
        texts.append(card.get_text(" ", strip=True))
    price_text = clean_text(" ".join(texts))
    price, currency = parse_price(price_text)
    return price, currency, price_text


def parse_rating(text: str | None) -> float | None:
    if not text:
        return None
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        return round(float(percent_match.group(1)) / 20, 1)

    out_of_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:/|out of)\s*5", text, re.I)
    if out_of_match:
        return round(float(out_of_match.group(1)), 1)

    rating_match = re.search(r"\b([0-5](?:\.\d)?)\b", text)
    if rating_match:
        return round(float(rating_match.group(1)), 1)
    return None


def rating_from_card(card, retailer: RetailerConfig) -> float | None:
    parts = []
    for selector in retailer.rating_selectors:
        for element in card.select(selector):
            parts.append(element.get_text(" ", strip=True))
            for attr in ("aria-label", "title", "alt", "style"):
                if element.get(attr):
                    parts.append(element[attr])
            for child in element.find_all(True):
                for attr in ("aria-label", "title", "alt", "style"):
                    if child.get(attr):
                        parts.append(child[attr])
    return parse_rating(" ".join(parts))


def parse_review_count(text: str | None) -> int | None:
    if not text:
        return None
    review_match = re.search(r"(\d+)\s+reviews?", text, re.I)
    if review_match:
        return int(review_match.group(1))
    average_rating_match = re.search(r"average\s+rating\s*\(?\s*(\d+)\s*\)?", text, re.I)
    if average_rating_match:
        return int(average_rating_match.group(1))
    paren_match = re.search(r"\((\d+)\)", text)
    if paren_match:
        return int(paren_match.group(1))
    return None


def review_count_from_card(card, retailer: RetailerConfig) -> int | None:
    parts = []
    for selector in retailer.review_count_selectors:
        for element in card.select(selector):
            parts.append(element.get_text(" ", strip=True))
            for attr in ("aria-label", "title", "alt"):
                if element.get(attr):
                    parts.append(element[attr])
    return parse_review_count(" ".join(parts))


def infer_brand(product_name: str, default_brand: str) -> str:
    for pattern, brand in BRAND_PATTERNS:
        if pattern.search(product_name):
            return brand
    return default_brand


def sku_from_card(card, retailer: RetailerConfig) -> str | None:
    if not retailer.sku_selector:
        return None
    return first_text(card, (retailer.sku_selector,))


def parse_listing_products(
    html: str,
    retailer: RetailerConfig,
    *,
    listing_url: str | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = scraped_at or datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for card in soup.select(retailer.card_selector):
        product_name = first_text(card, retailer.name_selectors)
        product_url = first_url(card, retailer)
        if not product_name or not product_url:
            continue

        price, currency, price_text = price_from_card(card, retailer)
        rating = rating_from_card(card, retailer)
        review_count = review_count_from_card(card, retailer)
        sku = sku_from_card(card, retailer)
        product_url = product_url.split("#", 1)[0]
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        metadata = {
            "listing_url": listing_url,
            "price_text": price_text,
        }
        if sku:
            metadata["sku"] = sku

        rows.append(
            {
                "product_name": product_name,
                "brand": infer_brand(product_name, retailer.brand),
                "category": retailer.category,
                "rating": rating,
                "review_count": review_count,
                "price": price,
                "currency": currency or "USD",
                "source": retailer.source,
                "url": product_url,
                "metadata": {key: value for key, value in metadata.items() if value},
                "scraped_at": scraped_at,
            }
        )

    return rows


def fetch_listing(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def valid_review_row(row: dict[str, Any]) -> bool:
    return bool(row.get("product_name") and row.get("brand") and row.get("url"))


def upsert_equipment_reviews(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    written = 0
    failed = 0
    valid_rows = [row for row in rows if valid_review_row(row)]

    for index in range(0, len(valid_rows), UPSERT_BATCH_SIZE):
        batch = valid_rows[index : index + UPSERT_BATCH_SIZE]
        try:
            client.table("fs_equipment_reviews").upsert(
                batch,
                on_conflict="url",
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_equipment_reviews upsert batch {index // UPSERT_BATCH_SIZE} failed: {exc}")
    return written, failed


def scrape_equipment_reviews(
    *,
    client=None,
    retailers: Iterable[RetailerConfig] | None = None,
    fetcher: Callable[[str], str] = fetch_listing,
    log_run: bool = True,
    request_delay: float = 0.0,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    retailers = tuple(retailers or DEFAULT_RETAILERS)
    run_log = ScraperRunLogger("scrape_equipment_reviews").start() if log_run else None
    previous_state = get_state(STATE_SOURCE, "last_run")

    written = failed = skipped = read = 0
    successful_sources: set[str] = set()

    try:
        for retailer in retailers:
            for listing_url in retailer.listing_urls:
                try:
                    html = fetcher(listing_url)
                    rows = parse_listing_products(html, retailer, listing_url=listing_url)
                except Exception as exc:
                    failed += 1
                    print(f"  {retailer.source} fetch/parse failed for {listing_url}: {exc}")
                    continue

                read += len(rows)
                if not rows:
                    skipped += 1
                    continue

                batch_written, batch_failed = upsert_equipment_reviews(client, rows)
                written += batch_written
                failed += batch_failed
                if batch_written:
                    successful_sources.add(retailer.source)

                if request_delay:
                    time.sleep(request_delay)

        summary = {
            "read": read,
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "sources": len(successful_sources),
            "scraped_at": datetime.now(UTC).isoformat(),
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(STATE_SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={"sources": sorted(successful_sources), "read": read},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Equipment reviews scrape starting - {datetime.now(UTC).isoformat()}")
    summary = scrape_equipment_reviews(request_delay=REQUEST_DELAY)
    print(
        "Equipment reviews scrape complete - "
        f"read={summary['read']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}, "
        f"sources={summary['sources']}"
    )


if __name__ == "__main__":
    main()
