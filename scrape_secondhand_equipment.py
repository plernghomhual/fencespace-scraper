import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "scrape_secondhand_equipment"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
REQUEST_TIMEOUT = 25
BATCH_SIZE = 100

EBAY_USED_SEARCH_URLS = [
    "https://www.ebay.com/sch/i.html?_nkw=used+fencing+gear&_sacat=0&LH_ItemCondition=3000",
    "https://www.ebay.com/sch/i.html?_nkw=fencing+epee+used&_sacat=0&LH_ItemCondition=3000",
    "https://www.ebay.com/sch/i.html?_nkw=fencing+foil+used&_sacat=0&LH_ItemCondition=3000",
    "https://www.ebay.com/sch/i.html?_nkw=fencing+sabre+used&_sacat=0&LH_ItemCondition=3000",
]

CURRENCY_ALIASES = {
    "$": "USD",
    "us$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "chf": "CHF",
    "cad": "CAD",
    "c$": "CAD",
    "aud": "AUD",
    "a$": "AUD",
}

CONTACT_RE = re.compile(
    r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|"
    r"(\+?\d[\d .()/-]{7,}\d)",
    re.IGNORECASE,
)
EBAY_ITEM_RE = re.compile(r"/itm/(?:[^/?#]+/)?(?P<id>\d{8,})")
PII_METADATA_KEYS = {
    "seller",
    "seller_name",
    "seller_display",
    "seller_display_name",
    "seller_info",
    "seller_public_name",
}


@dataclass(frozen=True)
class MarketplaceSource:
    source: str
    url: str
    parser: str = "ebay_search"


@dataclass(frozen=True)
class FetchedPage:
    text: str
    final_url: str
    status_code: int = 200
    content_type: str = "text/html"


DEFAULT_SOURCES = [
    MarketplaceSource(source="ebay", url=url, parser="ebay_search")
    for url in EBAY_USED_SEARCH_URLS
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\xa0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def hash_display_name(value: str) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()


def redact_contact_text(value: str) -> str:
    return clean_text(CONTACT_RE.sub("[redacted]", value))


def normalize_listing_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", clean_text(url))
    parsed = urlparse(absolute)
    path = re.sub(r"/+$", "", parsed.path)
    ebay_match = EBAY_ITEM_RE.search(path)
    if ebay_match:
        path = f"/itm/{ebay_match.group('id')}"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_listing_url(url).encode("utf-8")).hexdigest()


def extract_listing_id(source: str, listing_url: str, raw_id: str | None = None) -> str:
    raw_id = clean_text(raw_id)
    if raw_id:
        return raw_id

    if source == "ebay":
        match = EBAY_ITEM_RE.search(urlparse(listing_url).path)
        if match:
            return match.group("id")

    return f"url_sha256:{url_hash(listing_url)}"


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized_key = key.lower()
        if value in (None, "", [], {}):
            continue
        if normalized_key in PII_METADATA_KEYS:
            seller_value = clean_text(str(value))
            if seller_value:
                sanitized["seller_display_hash"] = hash_display_name(seller_value)
            continue
        if isinstance(value, str):
            redacted = redact_contact_text(value)
            if redacted and "[redacted]" not in redacted:
                sanitized[key] = redacted
            continue
        if isinstance(value, dict):
            nested = sanitize_metadata(value)
            if nested:
                sanitized[key] = nested
            continue
        sanitized[key] = value
    return sanitized


def parse_price(value: str | None) -> tuple[float | int | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None

    match = re.search(
        r"(?P<currency>US\s*\$|A\s*\$|C\s*\$|\$|€|£|USD|EUR|GBP|CHF|CAD|AUD)"
        r"\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\s*"
            r"(?P<currency>USD|EUR|GBP|CHF|CAD|AUD|euro)",
            text,
            flags=re.IGNORECASE,
        )
    if not match:
        return None, None

    currency_key = re.sub(r"\s+", "", match.group("currency")).lower()
    currency = CURRENCY_ALIASES.get(currency_key, match.group("currency").upper())
    amount = float(match.group("amount").replace(",", ""))
    if amount.is_integer():
        return int(amount), currency
    return amount, currency


def classify_listing(title: str, description: str | None = None) -> dict[str, str | None]:
    text = ascii_lower(f"{title} {description or ''}")
    weapon = None
    weapon_matches = [
        ("epee", r"\b(?:epee|epees|epee's)\b"),
        ("foil", r"\bfoils?\b"),
        ("sabre", r"\b(?:sabre|sabres|saber|sabers)\b"),
    ]
    found_weapons = [
        canonical for canonical, pattern in weapon_matches if re.search(pattern, text)
    ]
    if len(found_weapons) == 1:
        weapon = found_weapons[0]

    category_patterns = [
        (
            "uniform",
            r"\b(?:jacket|knickers|pants|breeches|uniform|lame|lam[eé]|underarm|plastron)\b",
        ),
        (
            "protective_gear",
            r"\b(?:mask|masks|glove|gloves|chest protector|protector|guard)\b",
        ),
        (
            "scoring_equipment",
            r"\b(?:scoring machine|score box|scoring box|reel|reels|body cord|bodycord|"
            r"floor cord|floor cable|tester|favero|allstar box)\b",
        ),
        (
            "weapon",
            r"\b(?:blade|blades|weapon|weapons|grip|pommel|bell guard|point|tip|"
            r"electric epee|electric foil|electric sabre)\b",
        ),
        ("bag_storage", r"\b(?:bag|weapon bag|fencing bag|roll bag)\b"),
    ]
    category = "other"
    for candidate, pattern in category_patterns:
        if re.search(pattern, text):
            category = candidate
            break

    return {"weapon": weapon, "category": category}


def strip_location_prefix(value: str) -> str:
    return re.sub(r"^(?:from|item location:)\s+", "", clean_text(value), flags=re.I)


def build_listing_row(
    *,
    source: str,
    title: str,
    listing_url: str,
    listing_id: str | None = None,
    price_text: str | None = None,
    location: str | None = None,
    description: str | None = None,
    status: str = "active",
    posted_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    scraped_at: str | None = None,
) -> dict[str, Any] | None:
    title = clean_text(title)
    if not title or title.lower() in {"shop on ebay", "sponsored items"}:
        return None

    canonical_url = normalize_listing_url(listing_url)
    if not canonical_url:
        return None

    price, currency = parse_price(price_text)
    classification = classify_listing(title, description)
    row = {
        "source": clean_text(source),
        "listing_id": extract_listing_id(source, canonical_url, listing_id),
        "title": title,
        "category": classification["category"],
        "weapon": classification["weapon"],
        "price": price,
        "currency": currency,
        "location": strip_location_prefix(location or "") or None,
        "listing_url": canonical_url,
        "posted_at": posted_at,
        "status": clean_text(status) or "active",
        "metadata": sanitize_metadata(metadata or {}),
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
    }
    return row


def first_text(root: Tag, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = root.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def first_attr(root: Tag, selectors: Iterable[str], attr: str) -> str:
    for selector in selectors:
        node = root.select_one(selector)
        if node and node.get(attr):
            return clean_text(str(node.get(attr)))
    return ""


def parse_ebay_search_results(
    html: str,
    *,
    source_url: str,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for item in soup.select("li.s-item"):
        link = first_attr(item, [".s-item__link", "a[href*='/itm/']"], "href")
        title = first_text(item, [".s-item__title", "h3", "a[href*='/itm/']"])
        if not link or "/itm/" not in link:
            continue

        condition = first_text(item, [".s-item__subtitle", ".SECONDARY_INFO"])
        seller = first_text(item, [".s-item__sellerInfoText", ".s-item__seller-info-text"])
        metadata = {
            "source_url": source_url,
            "condition": condition,
            "seller_public_name": re.sub(r"^sold by\s+", "", seller, flags=re.I),
        }
        row = build_listing_row(
            source="ebay",
            title=title,
            listing_url=normalize_listing_url(link, source_url),
            price_text=first_text(item, [".s-item__price", ".s-item__detail--primary"]),
            location=first_text(item, [".s-item__location", ".s-item__itemLocation"]),
            metadata=metadata,
            scraped_at=scraped_at,
        )
        if row:
            rows.append(row)
    return rows


def parse_generic_listing_cards(
    html: str,
    *,
    source: str,
    source_url: str,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.listing-card, .listing-card, [data-listing-id]")
    rows: list[dict[str, Any]] = []
    for card in cards:
        link = card.select_one("a[href]")
        if not link:
            continue
        listing_url = normalize_listing_url(str(link.get("href")), source_url)
        title = clean_text(link.get_text(" ", strip=True))
        seller = first_text(card, [".seller", "[data-seller]", ".seller-name"])
        metadata = {
            "source_url": source_url,
            "seller_public_name": seller,
        }
        row = build_listing_row(
            source=source,
            listing_id=clean_text(str(card.get("data-listing-id") or "")),
            title=title,
            listing_url=listing_url,
            price_text=first_text(card, [".price", "[data-price]"]),
            location=first_text(card, [".location", "[data-location]"]),
            description=first_text(card, ["p", ".description"]),
            metadata=metadata,
            scraped_at=scraped_at,
        )
        if row:
            rows.append(row)
    return rows


def dedupe_listings(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []
    for row in rows:
        normalized = dict(row)
        metadata = dict(normalized.get("metadata") or {})
        listing_url = normalize_listing_url(str(normalized.get("listing_url") or ""))
        source = clean_text(str(normalized.get("source") or ""))
        listing_id = clean_text(str(normalized.get("listing_id") or ""))
        if not listing_id:
            listing_id = f"url_sha256:{url_hash(listing_url)}"
        normalized["listing_url"] = listing_url
        normalized["listing_id"] = listing_id
        key = f"{source}:{listing_id}"
        metadata["dedupe_key"] = key
        normalized["metadata"] = metadata

        if key not in deduped:
            deduped[key] = normalized
            ordered_keys.append(key)
            continue

        existing = deduped[key]
        duplicate_urls = existing.setdefault("metadata", {}).setdefault(
            "duplicate_listing_urls", []
        )
        original_url = str(row.get("listing_url") or "")
        if original_url and original_url != existing.get("listing_url"):
            duplicate_urls.append(original_url)

    return [deduped[key] for key in ordered_keys]


def upsert_secondhand_rows(
    supabase,
    rows: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        if not batch:
            continue
        supabase.table("fs_secondhand_equipment").upsert(
            batch, on_conflict="source,listing_id"
        ).execute()
        written += len(batch)
    return written


def fetch_source(source: MarketplaceSource) -> FetchedPage:
    response = requests.get(
        source.url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
    )
    response.raise_for_status()
    return FetchedPage(
        text=response.text,
        final_url=response.url,
        status_code=response.status_code,
        content_type=response.headers.get("content-type", ""),
    )


def page_requires_private_access(html: str) -> bool:
    text = ascii_lower(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return any(
        marker in text
        for marker in (
            "captcha",
            "verify you are a human",
            "access denied",
            "sign in to your account",
            "enable javascript and cookies",
        )
    )


def parse_source_page(
    source: MarketplaceSource,
    page: FetchedPage,
    *,
    scraped_at: str,
) -> list[dict[str, Any]]:
    if page_requires_private_access(page.text):
        return []
    if source.parser == "ebay_search":
        return parse_ebay_search_results(
            page.text, source_url=page.final_url or source.url, scraped_at=scraped_at
        )
    if source.parser == "generic_cards":
        return parse_generic_listing_cards(
            page.text,
            source=source.source,
            source_url=page.final_url or source.url,
            scraped_at=scraped_at,
        )
    raise ValueError(f"unknown parser {source.parser!r}")


def scrape_secondhand_equipment(
    client,
    sources: Iterable[MarketplaceSource] | None = None,
    fetcher: Callable[[MarketplaceSource], FetchedPage] = fetch_source,
    update_state_enabled: bool = False,
) -> dict[str, int]:
    sources = list(sources or DEFAULT_SOURCES)
    scraped_at = datetime.now(timezone.utc).isoformat()
    parsed_rows: list[dict[str, Any]] = []
    failed = 0
    skipped = 0

    for source in sources:
        try:
            page = fetcher(source)
            rows = parse_source_page(source, page, scraped_at=scraped_at)
            if not rows:
                skipped += 1
            parsed_rows.extend(rows)
        except Exception as exc:
            failed += 1
            print(f"[secondhand_equipment] {source.source} fetch/parse failed: {exc}")

    deduped_rows = dedupe_listings(parsed_rows)
    written = upsert_secondhand_rows(client, deduped_rows) if client and deduped_rows else 0
    summary = {
        "sources": len(sources),
        "parsed": len(parsed_rows),
        "written": written,
        "failed": failed,
        "skipped": skipped,
    }
    if update_state_enabled:
        set_state(
            SOURCE,
            "last_run",
            {**summary, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
    return summary


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous second-hand equipment state: {previous_state}")

        client = get_supabase_client()
        summary = scrape_secondhand_equipment(
            client, sources=DEFAULT_SOURCES, update_state_enabled=True
        )
        run_log.complete(
            written=summary["written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Second-hand equipment scraper complete: "
            f"{summary['written']} rows written, "
            f"{summary['failed']} failed sources, "
            f"{summary['skipped']} skipped sources"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
