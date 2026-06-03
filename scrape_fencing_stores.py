from __future__ import annotations

import html
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from run_logger import ScraperRunLogger
from scraper_state import set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_fencing_stores"
BATCH_SIZE = int(os.environ.get("FENCING_STORES_BATCH_SIZE", "100"))
REQUEST_DELAY = float(os.environ.get("FENCING_STORES_REQUEST_DELAY", "1.0"))
REQUEST_TIMEOUT = int(os.environ.get("FENCING_STORES_REQUEST_TIMEOUT", "25"))
GEOCODER_URL = os.environ.get("FENCING_STORES_GEOCODER_URL")
GEOCODER_KEY = os.environ.get("FENCING_STORES_GEOCODER_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FenceSpaceBot/1.0; "
        "+https://fencespace.app)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(
    r"(?:tel(?:\.|ephone)?|phone|mobile|mob|call|whatsapp|telefon|fax)"
    r"\s*[:/]?\s*([+()0-9][0-9+().\-\s]{5,})",
    re.I,
)
POSTAL_CITY_RE = re.compile(r"\b\d{4,6}\s+([A-Z][A-Za-z .'-]+)\b")
US_CITY_RE = re.compile(r"\b([A-Z][A-Za-z .'-]+),\s*[A-Z]{2}\.?\s*\d{5}\b")

COUNTRY_ALIASES = {
    "u s": "united states",
    "u s a": "united states",
    "us": "united states",
    "usa": "united states",
    "united states": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "u k": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
}

US_STATE_ABBREVIATIONS = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "ia",
    "id",
    "il",
    "in",
    "ks",
    "ky",
    "la",
    "ma",
    "md",
    "me",
    "mi",
    "mn",
    "mo",
    "ms",
    "mt",
    "nc",
    "nd",
    "ne",
    "nh",
    "nj",
    "nm",
    "nv",
    "ny",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "va",
    "vt",
    "wa",
    "wi",
    "wv",
    "wy",
}

LINE_NOISE = {
    "website",
    "shop",
    "merchant url",
    "call",
    "mail",
    "email",
    "phone",
    "tel",
    "fax",
    "business hours",
    "opening hours",
    "hours",
}

STOP_MARKERS = (
    "business hours",
    "opening hours",
    "store hours",
    "contact form",
    "customer service",
    "submit",
    "required fields",
    "privacy policy",
)


@dataclass(frozen=True)
class StoreSource:
    source: str
    brand: str
    url: str
    parser: str
    default_name: str | None = None
    default_city: str | None = None
    default_country: str | None = None
    default_address: str | None = None
    default_phone: str | None = None
    default_email: str | None = None
    default_website: str | None = None


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


DEFAULT_SOURCES = (
    StoreSource(
        source="pbt_dealers",
        brand="PBT Fencing",
        url="https://shop.pbtfencing.com/dealers?lang=euro_foreign",
        parser="pbt_dealers",
    ),
    StoreSource(
        source="uhlmann_distributors",
        brand="Uhlmann",
        url="https://uhlmann-fechtsport.com/en/company/distributors/",
        parser="uhlmann_distributors",
    ),
    StoreSource(
        source="absolute_fencing_contact",
        brand="Absolute Fencing",
        url="https://www.absolutefencinggear.com/contact/",
        parser="contact_store",
        default_name="Absolute Fencing Gear",
        default_city="Bridgewater",
        default_country="United States",
        default_address="28 Chimney Rock Rd, Bridgewater, NJ 08807",
        default_website="https://www.absolutefencinggear.com/",
    ),
    StoreSource(
        source="blue_gauntlet_contact",
        brand="Blue Gauntlet",
        url="https://www.blue-gauntlet.com/crm.asp?action=contactus",
        parser="contact_store",
        default_name="Blue Gauntlet",
        default_city="Saddle Brook",
        default_country="United States",
        default_address="280 North Midland Ave., Bldg K, Saddle Brook, NJ. 07663",
        default_phone="201-797-3332",
        default_website="https://www.blue-gauntlet.com/",
    ),
    StoreSource(
        source="leon_paul_contact",
        brand="Leon Paul",
        url="https://www.leonpaul.com/leon-paul-contact-us",
        parser="contact_store",
        default_name="Leon Paul",
        default_city="London",
        default_country="United Kingdom",
        default_address="Unit 19 Garrick Industrial Centre, Irving Way, Hendon, London, NW9 6AQ",
        default_website="https://www.leonpaul.com/",
    ),
    StoreSource(
        source="allstar_contact",
        brand="Allstar",
        url="https://allstar.de/unternehmen/kontakt/dein-weg-zu-allstar/",
        parser="contact_store",
        default_name="Allstar Fecht-Center",
        default_city="Kusterdingen",
        default_country="Germany",
        default_address="In der Braike 13, 72127 Kusterdingen",
        default_website="https://allstar.de/",
    ),
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_source(source: StoreSource) -> FetchedContent:
    response = requests.get(
        source.url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    return FetchedContent(
        content=response.content,
        content_type=response.headers.get("content-type", ""),
        final_url=response.url,
    )


def clean_text(value: Any) -> str:
    raw = "" if value is None else str(value)
    text = html.unescape(raw).replace("\xa0", " ")
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def text_lines(value: str) -> list[str]:
    lines = []
    for line in value.splitlines():
        cleaned = clean_text(line).strip(" ,;")
        if cleaned:
            lines.append(cleaned)
    return lines


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def compact_key_text(value: str) -> str:
    text = strip_accents(unicodedata.normalize("NFKC", value)).casefold()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: str | None) -> str:
    text = compact_key_text(value or "")
    return COUNTRY_ALIASES.get(text, text)


def normalize_address(value: str | None) -> str:
    text = compact_key_text(value or "")
    replacements = {
        r"\bn\b": "north",
        r"\bs\b": "south",
        r"\be\b": "east",
        r"\bw\b": "west",
        r"\bave\b": "avenue",
        r"\bav\b": "avenue",
        r"\brd\b": "road",
        r"\bst\b": "street",
        r"\bblvd\b": "boulevard",
        r"\bste\b": "suite",
        r"\bbldg\b": "building",
        r"\busa\b": "united states",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    tokens = [token for token in text.split() if token not in US_STATE_ABBREVIATIONS]
    text = " ".join(tokens)
    text = re.sub(
        r"\b(\d{5})(?:\s+)([a-z]+(?:\s+[a-z]+){0,3})$",
        r"\2 \1",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def normalize_dedupe_key(store: dict) -> str:
    name = compact_key_text(store.get("name") or "")
    address = normalize_address(store.get("address") or "")
    country = normalize_country(store.get("country") or "")
    return "|".join((name, address, country))


def first_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def first_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    phone = clean_text(match.group(1)).strip(" .,-")
    return phone or None


def is_phone_like_line(line: str) -> bool:
    text = clean_text(line)
    digits = re.sub(r"\D", "", text)
    if len(digits) < 6:
        return False
    return not re.search(r"[A-Za-z]", text)


def first_website(links: Iterable[Tag], base_url: str) -> str | None:
    for link in links:
        href = link.get("href")
        if not href:
            continue
        href = clean_text(href)
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        return urljoin(base_url, href)
    return None


def tel_href(links: Iterable[Tag]) -> str | None:
    for link in links:
        href = clean_text(link.get("href"))
        if href.startswith("tel:"):
            return href.removeprefix("tel:").strip()
    return None


def mailto_href(links: Iterable[Tag]) -> str | None:
    for link in links:
        href = clean_text(link.get("href"))
        if href.startswith("mailto:"):
            return href.removeprefix("mailto:").split("?", 1)[0].strip()
    return None


def line_is_noise(line: str) -> bool:
    lowered = compact_key_text(line)
    return lowered in LINE_NOISE or lowered.startswith(("tel ", "phone ", "email "))


def looks_like_contact_name(line: str) -> bool:
    text = clean_text(line)
    words = text.split()
    if not words or len(words) > 4:
        return False
    if any(char.isdigit() for char in text):
        return False
    if "," in text or "@" in text:
        return False
    address_terms = {"street", "straat", "road", "avenue", "ave", "blvd", "suite", "building"}
    if any(term in compact_key_text(text).split() for term in address_terms):
        return False
    return sum(1 for word in words if word[:1].isupper()) >= min(2, len(words))


def country_from_heading(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\s*-\s*exclusive\b", "", text, flags=re.I)
    return clean_text(text)


def extract_city(address: str | None, country: str | None = None) -> str | None:
    if not address:
        return None
    us_match = US_CITY_RE.search(address)
    if us_match:
        return clean_text(us_match.group(1)).strip(".")

    postal_match = POSTAL_CITY_RE.search(address)
    if postal_match:
        return clean_text(postal_match.group(1)).strip(".")

    parts = [clean_text(part).strip(".") for part in address.split(",")]
    parts = [part for part in parts if part]
    country_key = normalize_country(country)
    for part in reversed(parts):
        if any(char.isdigit() for char in part):
            city_match = re.search(r"\b([A-Z][A-Za-z .'-]+)\b", part)
            if city_match:
                return clean_text(city_match.group(1)).strip(".")
            continue
        if normalize_country(part) == country_key:
            continue
        if len(part) <= 50:
            return part
    return None


def create_store_record(
    *,
    name: str,
    source: StoreSource,
    address_lines: list[str],
    country: str | None = None,
    city: str | None = None,
    website: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict | None:
    cleaned_name = clean_text(name).strip(":- ")
    if not cleaned_name:
        return None

    clean_address_lines = [
        clean_text(line).strip(" ,;")
        for line in address_lines
        if clean_text(line).strip(" ,;") and not line_is_noise(line)
    ]
    address = ", ".join(clean_address_lines) or source.default_address
    record = {
        "name": cleaned_name,
        "brand": source.brand,
        "source": source.source,
        "website": website or source.default_website,
        "city": city or source.default_city or extract_city(address, country),
        "country": country or source.default_country,
        "address": address,
        "latitude": None,
        "longitude": None,
        "phone": phone or source.default_phone,
        "email": email or source.default_email,
        "source_url": source.url,
        "metadata": {
            "parser": source.parser,
            **(metadata or {}),
        },
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    record["dedupe_key"] = normalize_dedupe_key(record)
    return record


def split_chunks_by_hr(container: Tag) -> list[tuple[list[str], list[Tag]]]:
    chunks: list[tuple[list[str], list[Tag]]] = []
    lines: list[str] = []
    links: list[Tag] = []

    def flush() -> None:
        nonlocal lines, links
        filtered = [
            line for line in lines if line and compact_key_text(line) not in LINE_NOISE
        ]
        if filtered:
            chunks.append((filtered, list(links)))
        lines = []
        links = []

    for child in container.children:
        if isinstance(child, Tag) and child.name == "hr":
            flush()
            continue
        if isinstance(child, Tag):
            if child.name == "a" and child.get("href"):
                links.append(child)
            links.extend(child.find_all("a", href=True))
            child_text = child.get_text("\n", strip=True)
            lines.extend(text_lines(child_text))
        elif isinstance(child, str):
            lines.extend(text_lines(child))
    flush()
    return chunks


def parse_dealer_chunk(
    lines: list[str],
    links: list[Tag],
    source: StoreSource,
    country: str,
) -> dict | None:
    if not lines:
        return None
    name = lines[0]
    text = "\n".join(lines)
    email = mailto_href(links) or first_email(text)
    phone = tel_href(links) or first_phone(text)
    website = first_website(links, source.url)
    address_lines = []
    candidate_lines = lines[1:]
    if len(candidate_lines) >= 2 and looks_like_contact_name(candidate_lines[0]):
        candidate_lines = candidate_lines[1:]
    for line in candidate_lines:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or is_phone_like_line(line):
            continue
        if line_is_noise(line):
            continue
        address_lines.append(line)
    return create_store_record(
        name=name,
        source=source,
        address_lines=address_lines,
        country=country,
        website=website,
        phone=phone,
        email=email,
    )


def parse_pbt_dealers(html_text: str, source: StoreSource) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    stores: list[dict] = []
    for heading in soup.find_all(["h3", "h4", "h5"]):
        country = country_from_heading(heading.get_text(" ", strip=True))
        if not country or compact_key_text(country) in {"dealers", "webshop"}:
            continue
        panel = heading.find_parent(
            lambda tag: isinstance(tag, Tag)
            and "panel" in (tag.get("class") or [])
        )
        if not panel:
            panel = heading.parent.parent if heading.parent else None
        body = panel.find(class_=re.compile(r"\bpanel-body\b")) if isinstance(panel, Tag) else None
        dealer_nodes = panel.find_all(class_=lambda value: value and "dealer" in str(value).split())
        if dealer_nodes:
            for dealer in dealer_nodes:
                name_element = dealer.find(class_=lambda value: value and "name" in str(value).split())
                content = dealer.find(class_=lambda value: value and "content" in str(value).split())
                name = clean_text(name_element.get_text(" ", strip=True)) if name_element else ""
                if not name:
                    continue
                lines = [name]
                if content:
                    lines.extend(text_lines(content.get_text("\n", strip=True)))
                    links = content.find_all("a", href=True)
                else:
                    lines.extend(text_lines(dealer.get_text("\n", strip=True)))
                    links = dealer.find_all("a", href=True)
                record = parse_dealer_chunk(lines, links, source, country)
                if record:
                    stores.append(record)
            continue
        if body:
            for lines, links in split_chunks_by_hr(body):
                record = parse_dealer_chunk(lines, links, source, country)
                if record:
                    stores.append(record)
    return stores


def parse_uhlmann_distributors(html_text: str, source: StoreSource) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    stores: list[dict] = []
    for item in soup.find_all("li"):
        lines = [
            line
            for line in text_lines(item.get_text("\n", strip=True))
            if not line_is_noise(line)
        ]
        if len(lines) < 4:
            continue
        if compact_key_text(lines[0]) in {"company", "products", "distributors"}:
            continue
        links = item.find_all("a", href=True)
        country = lines[-1]
        address_lines = lines[1:-1]
        if not address_lines:
            continue
        record = create_store_record(
            name=lines[0],
            source=source,
            address_lines=address_lines,
            country=country,
            website=first_website(links, source.url),
            phone=tel_href(links) or first_phone("\n".join(lines)),
            email=mailto_href(links) or first_email("\n".join(lines)),
        )
        if record:
            stores.append(record)
    return stores


def candidate_contact_lines(soup: BeautifulSoup, source: StoreSource) -> list[str]:
    lines = text_lines(soup.get_text("\n", strip=True))
    if not lines:
        return []

    start = 0
    markers = [
        source.default_name or "",
        "our location",
        "address",
        "retail shop",
        "showroom",
        "headquarter",
    ]
    for index, line in enumerate(lines):
        lowered = compact_key_text(line)
        if any(marker and compact_key_text(marker) in lowered for marker in markers):
            start = index + 1
            break

    selected: list[str] = []
    for line in lines[start:]:
        lowered = compact_key_text(line)
        if any(marker in lowered for marker in STOP_MARKERS):
            break
        if source.default_name and compact_key_text(line) == compact_key_text(source.default_name):
            continue
        selected.append(line)
        if len(selected) >= 10:
            break
    return selected


def parse_contact_store(html_text: str, source: StoreSource) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    lines = candidate_contact_lines(soup, source)
    text = "\n".join(lines) or soup.get_text("\n", strip=True)
    phone = first_phone(text) or source.default_phone
    email = first_email(text) or source.default_email
    links = soup.find_all("a", href=True)
    website = first_website(links, source.url) or source.default_website
    address_lines = []
    for line in lines:
        lowered = compact_key_text(line)
        if not line:
            continue
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        if normalize_country(line) == normalize_country(source.default_country):
            continue
        if lowered in {"contact us", "address", "our location"}:
            continue
        address_lines.append(line)

    record = create_store_record(
        name=source.default_name or source.brand,
        source=source,
        address_lines=address_lines,
        country=source.default_country,
        website=website,
        phone=phone,
        email=email,
    )
    return [record] if record else []


PARSERS: dict[str, Callable[[str, StoreSource], list[dict]]] = {
    "pbt_dealers": parse_pbt_dealers,
    "uhlmann_distributors": parse_uhlmann_distributors,
    "contact_store": parse_contact_store,
}


def parse_fetched_content(source: StoreSource, fetched: FetchedContent) -> list[dict]:
    parser = PARSERS.get(source.parser)
    if parser is None:
        raise ValueError(f"unknown parser {source.parser!r}")
    text = fetched.content.decode("utf-8", errors="replace")
    rows = parser(text, source)
    for row in rows:
        row["source_url"] = fetched.final_url or row.get("source_url") or source.url
        row["dedupe_key"] = normalize_dedupe_key(row)
    return rows


def merge_metadata(existing: dict, incoming: dict) -> None:
    metadata = existing.setdefault("metadata", {})
    incoming_metadata = incoming.get("metadata") or {}
    for key, value in incoming_metadata.items():
        metadata.setdefault(key, value)

    duplicate_url = incoming.get("source_url")
    if duplicate_url and duplicate_url != existing.get("source_url"):
        urls = metadata.setdefault("duplicate_source_urls", [])
        if duplicate_url not in urls:
            urls.append(duplicate_url)

    for field, key in (("source", "sources"), ("brand", "brands")):
        values = metadata.setdefault(key, [])
        for value in (existing.get(field), incoming.get(field)):
            if value and value not in values:
                values.append(value)


def dedupe_stores(stores: Iterable[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for store in stores:
        key = normalize_dedupe_key(store)
        if not key.replace("|", ""):
            continue
        if key not in deduped:
            row = dict(store)
            row["metadata"] = dict(row.get("metadata") or {})
            row["dedupe_key"] = key
            row["metadata"].setdefault("sources", [row.get("source")] if row.get("source") else [])
            row["metadata"].setdefault("brands", [row.get("brand")] if row.get("brand") else [])
            deduped[key] = row
            continue

        existing = deduped[key]
        merge_metadata(existing, store)
        for field in ("website", "city", "country", "address", "phone", "email"):
            if not existing.get(field) and store.get(field):
                existing[field] = store[field]
    return list(deduped.values())


def default_geocoder() -> Callable[[dict], Any] | None:
    if not GEOCODER_URL:
        return None

    def geocode(row: dict) -> Any:
        query = ", ".join(
            value
            for value in (row.get("address"), row.get("city"), row.get("country"))
            if value
        )
        if not query:
            return None
        params = {"q": query, "format": "json", "limit": 2}
        if GEOCODER_KEY:
            params["key"] = GEOCODER_KEY
        response = requests.get(
            GEOCODER_URL,
            headers=HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return geocode


def geocode_rows(rows: list[dict], geocoder: Callable[[dict], Any] | None) -> int:
    ambiguous = 0
    if geocoder is None:
        for row in rows:
            row.setdefault("latitude", None)
            row.setdefault("longitude", None)
        return ambiguous

    for row in rows:
        row.setdefault("latitude", None)
        row.setdefault("longitude", None)
        if row.get("latitude") is not None and row.get("longitude") is not None:
            continue
        if not row.get("address") or not row.get("country"):
            continue
        try:
            result = geocoder(row)
        except Exception as exc:
            row.setdefault("metadata", {})["geocoder_error"] = str(exc)[:300]
            continue
        if not result:
            continue
        if isinstance(result, list):
            if len(result) != 1:
                row.setdefault("metadata", {})["geocoder_ambiguous"] = len(result)
                ambiguous += 1
                continue
            result = result[0]
        if not isinstance(result, dict):
            continue
        lat = result.get("latitude", result.get("lat"))
        lon = result.get("longitude", result.get("lon"))
        if lat is None or lon is None:
            continue
        row["latitude"] = float(lat)
        row["longitude"] = float(lon)
    return ambiguous


def location_warning_counts(rows: list[dict]) -> tuple[int, int]:
    missing = 0
    ambiguous = 0
    for row in rows:
        metadata = row.get("metadata") or {}
        if not row.get("address") or not row.get("country"):
            missing += 1
            print(
                f"[{SOURCE}] missing location data: "
                f"{row.get('source')} {row.get('name')}"
            )
        if metadata.get("geocoder_ambiguous"):
            ambiguous += 1
            print(
                f"[{SOURCE}] ambiguous geocode: "
                f"{row.get('source')} {row.get('name')}"
            )
    return missing, ambiguous


def batch_upsert_fencing_stores(client, rows: list[dict]) -> int:
    if not rows:
        return 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table("fs_fencing_stores").upsert(
            batch,
            on_conflict="dedupe_key",
        ).execute()
    return len(rows)


def scrape_fencing_stores(
    *,
    client=None,
    sources: Iterable[StoreSource] | None = None,
    fetcher: Callable[[StoreSource], FetchedContent] = fetch_source,
    geocoder: Callable[[dict], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    request_delay: float = REQUEST_DELAY,
    log_run: bool = True,
    update_state: bool = True,
) -> dict:
    sources = list(sources or DEFAULT_SOURCES)
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    parsed_rows: list[dict] = []
    failed = 0
    skipped = 0
    try:
        for index, source in enumerate(sources):
            if index > 0 and request_delay > 0:
                sleeper(request_delay)
            try:
                fetched = fetcher(source)
                source_rows = parse_fetched_content(source, fetched)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.source} {source.url}: {exc}")
                continue
            if not source_rows:
                skipped += 1
                print(f"[{SOURCE}] source skipped with no stores: {source.source}")
            parsed_rows.extend(source_rows)

        rows = dedupe_stores(parsed_rows)
        ambiguous_from_geocoder = geocode_rows(rows, geocoder or default_geocoder())
        missing_location, ambiguous_location = location_warning_counts(rows)
        ambiguous_location = max(ambiguous_location, ambiguous_from_geocoder)
        written = batch_upsert_fencing_stores(client, rows) if client else 0
        summary = {
            "sources": len(sources),
            "parsed": len(parsed_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "missing_location": missing_location,
            "ambiguous_location": ambiguous_location,
        }

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_fencing_stores()
    print(
        "fencing stores: "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
