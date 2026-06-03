from __future__ import annotations

import hashlib
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

SOURCE = "fencing_net"
STATE_SOURCE = "fencingnet_products"
UPSERT_BATCH_SIZE = 100
REQUEST_DELAY = 1.0
DEFAULT_START_URLS = ("https://fencing.net/reviews/",)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class ParsedPage:
    products: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    skipped_private: bool = False
    skip_reason: str | None = None


BRAND_PATTERNS = (
    (re.compile(r"\bnike\b", re.I), "Nike"),
    (re.compile(r"\badidas\b", re.I), "Adidas"),
    (re.compile(r"\bleon\s+paul\b|\blp\b", re.I), "Leon Paul"),
    (re.compile(r"\babsolute\b|\baf\b", re.I), "Absolute Fencing"),
    (re.compile(r"\bblue\s+gauntlet\b|\bbg\b", re.I), "Blue Gauntlet"),
    (re.compile(r"\ballstar\b", re.I), "Allstar"),
    (re.compile(r"\buhlmann\b", re.I), "Uhlmann"),
    (re.compile(r"\bnegrini\b", re.I), "Negrini"),
    (re.compile(r"\bpbt\b", re.I), "PBT"),
    (re.compile(r"\bfolo\b", re.I), "FOLO"),
    (re.compile(r"\bprieur\b", re.I), "Prieur"),
    (re.compile(r"\bbf\b|\bblaise\s+fr[eè]res\b", re.I), "Blaise Freres"),
)

CATEGORY_PATTERNS = (
    (re.compile(r"\bepee\b.*\bblade\b|\bblade\b.*\bepee\b", re.I), "Epee Blades"),
    (re.compile(r"\bfoil\b.*\bblade\b|\bblade\b.*\bfoil\b", re.I), "Foil Blades"),
    (re.compile(r"\bsabre\b.*\bblade\b|\bblade\b.*\bsabre\b", re.I), "Sabre Blades"),
    (re.compile(r"\bblade\b", re.I), "Blades"),
    (re.compile(r"\bshoe\b|\bballestra\b", re.I), "Shoes"),
    (re.compile(r"\bglove\b", re.I), "Gloves"),
    (re.compile(r"\bmask\b", re.I), "Masks"),
    (re.compile(r"\blame\b|\bjacket\b|\bpants\b|\bknickers\b", re.I), "Clothing"),
    (re.compile(r"\bweapon\b|\bepee\b|\bfoil\b|\bsabre\b", re.I), "Weapons"),
    (re.compile(r"\bbag\b", re.I), "Bags"),
)

PRIVATE_PATTERNS = (
    re.compile(r"\byou must be logged in\b", re.I),
    re.compile(r"\blog in to (?:view|reply|continue|access)\b", re.I),
    re.compile(r"\blogin required\b", re.I),
    re.compile(r"\bmembers only\b", re.I),
    re.compile(r"\bprivate (?:forum|content)\b", re.I),
)

REVIEW_TEXT_SELECTORS = (
    ".comment-content",
    ".review-text",
    ".review-content",
    ".bbp-reply-content",
    ".message-body",
    ".entry-content p",
    "article p",
)


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


def canonical_url(soup: BeautifulSoup, source_url: str) -> str:
    link = soup.select_one("link[rel='canonical'][href]")
    if link:
        return urljoin(source_url, link["href"]).split("#", 1)[0]
    return source_url.split("#", 1)[0]


def source_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path:
        return path.removesuffix("/")
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def iter_json_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


def normalize_rating(value: Any, best_rating: Any = None) -> float | None:
    try:
        rating = float(str(value).strip())
    except (TypeError, ValueError):
        return None

    best = None
    if best_rating not in (None, ""):
        try:
            best = float(str(best_rating).strip())
        except (TypeError, ValueError):
            best = None

    if best and best > 0:
        rating = rating / best * 5
    elif rating > 10:
        rating = rating / 20
    elif rating > 5:
        rating = rating / 2

    if rating < 0:
        return None
    return round(min(rating, 5.0), 1)


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else None


def structured_data(soup: BeautifulSoup) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in iter_json_nodes(parsed):
            node_type = node.get("@type")
            if isinstance(node_type, list):
                node_types = {str(item).lower() for item in node_type}
            else:
                node_types = {str(node_type).lower()} if node_type else set()

            if "product" in node_types and not data.get("name"):
                data["name"] = clean_text(node.get("name"))
            elif "review" in node_types and not data.get("review_title"):
                data["review_title"] = clean_text(node.get("name") or node.get("headline"))

            brand = node.get("brand")
            if brand and not data.get("brand"):
                if isinstance(brand, dict):
                    data["brand"] = clean_text(brand.get("name"))
                else:
                    data["brand"] = clean_text(brand)
            if node.get("category") and not data.get("category"):
                data["category"] = clean_text(node.get("category"))

            rating_node = node.get("aggregateRating") or node.get("reviewRating")
            if isinstance(rating_node, dict):
                if data.get("rating") is None:
                    data["rating"] = normalize_rating(
                        rating_node.get("ratingValue"),
                        rating_node.get("bestRating"),
                    )
                if data.get("review_count") is None:
                    data["review_count"] = (
                        parse_int(rating_node.get("reviewCount"))
                        or parse_int(rating_node.get("ratingCount"))
                    )
    return {key: value for key, value in data.items() if value is not None}


def is_private_or_login_page(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ", strip=True)
    has_strong_private_text = any(pattern.search(text) for pattern in PRIVATE_PATTERNS)
    has_login_form = bool(
        soup.select_one("form#loginform, form[action*='login'], input[name='log'], input[name='pwd']")
    )
    has_public_article_text = bool(
        soup.select_one(
            "article .entry-content, article .bbp-reply-content, "
            "article .comment-content, article .message-body, article p"
        )
    )
    return has_strong_private_text or (has_login_form and not has_public_article_text)


def title_from_page(soup: BeautifulSoup, source_url: str) -> str:
    for selector in ("h1.entry-title", "article h1", "h1", "title"):
        element = soup.select_one(selector)
        text = clean_text(element.get_text(" ", strip=True) if element else None)
        if text:
            return re.sub(r"\s*[-|]\s*Fencing\.net\s*$", "", text, flags=re.I)
    return source_id_from_url(source_url).replace("-", " ").title()


def strip_review_words(title: str) -> str:
    name = re.sub(r"^\s*review\s*:\s*", "", title, flags=re.I)
    name = re.sub(r"\s+(?:fencing\s+)?(?:product\s+)?reviews?\s*$", "", name, flags=re.I)
    return clean_text(name) or title


def infer_brand(*values: str | None) -> str:
    text = " ".join(value for value in values if value)
    for pattern, brand in BRAND_PATTERNS:
        if pattern.search(text):
            return brand
    return "Unknown"


def infer_category(*values: str | None) -> str:
    text = " ".join(value for value in values if value)
    for pattern, category in CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return "Equipment"


def category_from_page(soup: BeautifulSoup) -> str | None:
    for selector in (".cat-links a", "a[rel='category tag']", ".breadcrumb a", ".breadcrumbs a"):
        for element in soup.select(selector):
            text = clean_text(element.get_text(" ", strip=True))
            if text and text.lower() not in {"reviews", "equipment reviews", "fencing.net"}:
                return text
    return None


def review_date_from_page(soup: BeautifulSoup) -> str | None:
    time_element = soup.select_one("time[datetime]")
    if time_element and time_element.get("datetime"):
        value = str(time_element["datetime"]).strip()
        return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) else value
    time_text = clean_text(soup.select_one("time").get_text(" ", strip=True) if soup.select_one("time") else None)
    return time_text


def rating_and_count_from_text(text: str) -> tuple[float | None, int | None]:
    reader_match = re.search(
        r"reader\s+rating\s+([0-9][0-9,]*)\s+votes?\s+([0-9]+(?:\.[0-9]+)?)",
        text,
        re.I,
    )
    if reader_match:
        return normalize_rating(reader_match.group(2)), parse_int(reader_match.group(1))

    count = None
    count_match = re.search(r"([0-9][0-9,]*)\s+(?:votes?|reviews?|ratings?)\b", text, re.I)
    if count_match:
        count = parse_int(count_match.group(1))

    rating = None
    rating_match = re.search(
        r"(?:rating|score)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|out of)\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.I,
    )
    if rating_match:
        rating = normalize_rating(rating_match.group(1), rating_match.group(2))
    else:
        plain_rating = re.search(r"(?:rating|score)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\b", text, re.I)
        if plain_rating:
            rating = normalize_rating(plain_rating.group(1))

    return rating, count


def extract_rating_and_count(soup: BeautifulSoup, structured: dict[str, Any]) -> tuple[float | None, int | None]:
    rating = structured.get("rating")
    review_count = structured.get("review_count")
    if rating is not None and review_count is not None:
        return rating, review_count

    parts = []
    for selector in (
        ".review-total-wrapper",
        ".review-total-box",
        ".review-total",
        ".user-rate-wrap",
        ".wp-review-user-rating",
        "[itemprop='aggregateRating']",
        "[class*='rating']",
    ):
        for element in soup.select(selector):
            parts.append(element.get_text(" ", strip=True))
            for attr in ("content", "title", "aria-label", "data-rating"):
                if element.get(attr):
                    parts.append(str(element[attr]))
    text_rating, text_count = rating_and_count_from_text(" ".join(parts))
    return rating if rating is not None else text_rating, review_count if review_count is not None else text_count


def image_url_from_page(soup: BeautifulSoup, source_url: str) -> str | None:
    for selector, attr in (
        ("meta[property='og:image']", "content"),
        ("article img[src]", "src"),
    ):
        element = soup.select_one(selector)
        if element and element.get(attr):
            return urljoin(source_url, element[attr])
    return None


def snippet_hash(source_url: str, product_name: str, review_date: str | None, snippet: str) -> str:
    value = "|".join([source_url, product_name, review_date or "", snippet])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def extract_review_snippets(soup: BeautifulSoup) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for selector in REVIEW_TEXT_SELECTORS:
        for element in soup.select(selector):
            text = clean_text(element.get_text(" ", strip=True))
            if not text or len(text) < 40:
                continue
            if any(pattern.search(text) for pattern in PRIVATE_PATTERNS):
                continue
            snippet = text[:500]
            marker = hashlib.sha256(snippet.encode("utf-8")).hexdigest()
            if marker in seen:
                continue
            seen.add(marker)
            snippets.append(snippet)
    return snippets[:12]


def parse_review_page(html: str, source_url: str, *, scraped_at: str | None = None) -> ParsedPage:
    soup = BeautifulSoup(html, "html.parser")
    if is_private_or_login_page(soup):
        return ParsedPage(products=[], reviews=[], skipped_private=True, skip_reason="private_or_login")

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    page_url = canonical_url(soup, source_url)
    data = structured_data(soup)
    title = title_from_page(soup, page_url)
    product_name = strip_review_words(data.get("name") or title)
    page_text = soup.get_text(" ", strip=True)
    brand = data.get("brand") or infer_brand(product_name, title, page_text)
    category = data.get("category") or category_from_page(soup) or infer_category(product_name, title, page_text)
    rating, review_count = extract_rating_and_count(soup, data)
    review_date = review_date_from_page(soup)
    source_id = source_id_from_url(page_url)

    product = {
        "source": SOURCE,
        "source_id": source_id,
        "name": product_name,
        "brand": brand,
        "category": category,
        "weapon": None,
        "price": None,
        "currency": "USD",
        "image_url": image_url_from_page(soup, page_url),
        "product_url": page_url,
        "stock_status": None,
        "metadata": {
            "page_title": title,
            "source_url": page_url,
            "review_date": review_date,
            "rating": rating,
            "review_count": review_count,
        },
        "scraped_at": scraped_at,
    }
    product["metadata"] = {key: value for key, value in product["metadata"].items() if value is not None}

    reviews: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for snippet in extract_review_snippets(soup):
        review_hash = snippet_hash(page_url, product_name, review_date, snippet)
        if review_hash in seen_hashes:
            continue
        seen_hashes.add(review_hash)
        reviews.append(
            {
                "product_name": product_name,
                "brand": brand,
                "category": category,
                "rating": rating,
                "review_count": review_count,
                "price": None,
                "currency": "USD",
                "source": SOURCE,
                "url": f"{page_url}#review-{review_hash}",
                "metadata": {
                    "source_url": page_url,
                    "review_hash": review_hash,
                    "review_date": review_date,
                    "text_snippet": snippet,
                    "page_title": title,
                },
                "scraped_at": scraped_at,
            }
        )

    return ParsedPage(products=[product], reviews=reviews)


def discover_review_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    if is_private_or_login_page(soup):
        return []

    links: list[str] = []
    seen: set[str] = set()
    base_path = urlparse(base_url).path.rstrip("/")
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"]).split("#", 1)[0]
        parsed = urlparse(href)
        path = parsed.path.rstrip("/")
        if parsed.netloc and parsed.netloc.lower() not in {"fencing.net", "www.fencing.net"}:
            continue
        is_current_review = path.startswith("/reviews/") and path != "/reviews"
        is_legacy_review = bool(re.match(r"/\d+/.+(?:review|blade|glove|shoes?)", path, re.I))
        if not (is_current_review or is_legacy_review):
            continue
        if path == base_path or any(skip in path for skip in ("/feed", "/comment-page-", "/page/")):
            continue
        if href not in seen:
            seen.add(href)
            links.append(href)
    return links


def fetch_url(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def valid_product_row(row: dict[str, Any]) -> bool:
    return bool(row.get("source") and row.get("source_id") and row.get("name") and row.get("product_url"))


def valid_review_row(row: dict[str, Any]) -> bool:
    return bool(row.get("product_name") and row.get("brand") and row.get("url"))


def upsert_batches(
    client,
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    on_conflict: str,
    validator: Callable[[dict[str, Any]], bool],
) -> tuple[int, int]:
    written = 0
    failed = 0
    valid_rows = [row for row in rows if validator(row)]

    for index in range(0, len(valid_rows), UPSERT_BATCH_SIZE):
        batch = valid_rows[index : index + UPSERT_BATCH_SIZE]
        try:
            client.table(table_name).upsert(batch, on_conflict=on_conflict).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {table_name} upsert batch {index // UPSERT_BATCH_SIZE} failed: {exc}")
    return written, failed


def upsert_products(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    return upsert_batches(
        client,
        table_name="fs_products",
        rows=rows,
        on_conflict="source,source_id",
        validator=valid_product_row,
    )


def upsert_reviews(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    return upsert_batches(
        client,
        table_name="fs_equipment_reviews",
        rows=rows,
        on_conflict="url",
        validator=valid_review_row,
    )


def scrape_fencingnet_products(
    *,
    client=None,
    start_urls: Iterable[str] | None = None,
    fetcher: Callable[[str], str] = fetch_url,
    max_pages: int = 50,
    request_delay: float = 0.0,
    log_run: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger("scrape_fencingnet_products").start() if log_run else None
    previous_state = get_state(STATE_SOURCE, "last_run")

    products_by_id: dict[str, dict[str, Any]] = {}
    reviews_by_url: dict[str, dict[str, Any]] = {}
    failed = skipped = private_skipped = fetched = 0
    urls_to_fetch = list(start_urls or DEFAULT_START_URLS)
    seen_urls: set[str] = set()

    try:
        while urls_to_fetch and len(seen_urls) < max_pages:
            url = urls_to_fetch.pop(0)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            try:
                html = fetcher(url)
            except Exception as exc:
                failed += 1
                print(f"  Fencing.net fetch failed for {url}: {exc}")
                continue
            fetched += 1

            discovered = discover_review_links(html, url)
            if discovered:
                for link in discovered:
                    if link not in seen_urls and link not in urls_to_fetch and len(seen_urls) + len(urls_to_fetch) < max_pages:
                        urls_to_fetch.append(link)
                if request_delay:
                    time.sleep(request_delay)
                continue

            parsed = parse_review_page(html, url)
            if parsed.skipped_private:
                private_skipped += 1
                skipped += 1
                continue
            if not parsed.products and not parsed.reviews:
                skipped += 1
                continue

            for product in parsed.products:
                products_by_id[product["source_id"]] = product
            for review in parsed.reviews:
                reviews_by_url[review["url"]] = review

            if request_delay:
                time.sleep(request_delay)

        product_written, product_failed = upsert_products(client, list(products_by_id.values()))
        review_written, review_failed = upsert_reviews(client, list(reviews_by_url.values()))
        failed += product_failed + review_failed

        summary = {
            "fetched": fetched,
            "products_read": len(products_by_id),
            "reviews_read": len(reviews_by_url),
            "product_written": product_written,
            "review_written": review_written,
            "written": product_written + review_written,
            "failed": failed,
            "skipped": skipped,
            "private_skipped": private_skipped,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(previous_state, dict) and previous_state.get("scraped_at"):
            summary["previous_scraped_at"] = previous_state["scraped_at"]

        set_state(STATE_SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=failed,
                skipped=skipped,
                metadata={
                    "fetched": fetched,
                    "products_read": len(products_by_id),
                    "reviews_read": len(reviews_by_url),
                    "private_skipped": private_skipped,
                },
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Fencing.net product review scrape starting - {datetime.now(timezone.utc).isoformat()}")
    summary = scrape_fencingnet_products(request_delay=REQUEST_DELAY)
    print(
        "Fencing.net scrape complete: "
        f"{summary['product_written']} products, {summary['review_written']} reviews written; "
        f"{summary['failed']} failed; {summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
