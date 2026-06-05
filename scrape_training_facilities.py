import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "scrape_training_facilities"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
BATCH_SIZE = 100

FREE_EMAIL_DOMAINS = {
    "aol.com",
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "me.com",
    "msn.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
}
PUBLIC_EMAIL_PREFIXES = {
    "admin",
    "admissions",
    "club",
    "contact",
    "enquiries",
    "enquiry",
    "fencing",
    "hello",
    "info",
    "membership",
    "office",
    "reception",
    "registrar",
    "support",
    "team",
}
PRIVATE_CONTACT_HINTS = {
    "cell",
    "coach mobile",
    "direct",
    "emergency",
    "guardian",
    "home",
    "mobile",
    "parent",
    "personal",
    "private",
    "sms",
}
PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}"
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

WEAPON_PATTERNS = (
    ("epee", re.compile(r"\b(?:epee|eppee|epe|épée)\b", re.I)),
    ("foil", re.compile(r"\bfoil\b", re.I)),
    ("saber", re.compile(r"\b(?:saber|sabre)\b", re.I)),
)
PROGRAM_PATTERNS = (
    ("adult classes", re.compile(r"\badult(?:s)?\b", re.I)),
    ("beginner", re.compile(r"\b(?:beginner|introductory|learn to fence)\b", re.I)),
    ("camp", re.compile(r"\bcamps?\b", re.I)),
    ("open bouting", re.compile(r"\bopen\s+bouting\b", re.I)),
    ("private lessons", re.compile(r"\bprivate\s+lessons?\b", re.I)),
    ("youth", re.compile(r"\b(?:youth|junior|kids|children)\b", re.I)),
)

COUNTRY_ALIASES = {
    "united states": "USA",
    "united states of america": "USA",
    "us": "USA",
    "u.s.": "USA",
    "usa": "USA",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
}


@dataclass(frozen=True)
class DirectorySource:
    url: str
    name: str
    country: str | None = None
    source_kind: str = "directory"
    parser: str = "html"


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


DEFAULT_SOURCES = [
    DirectorySource(
        url=(
            "https://member.usafencing.org/clubs?q=&division=&state=&club_type="
            "&sort=name&page=1&perPage=50"
        ),
        name="USA Fencing club directory",
        country="USA",
        source_kind="federation_api",
        parser="usafencing_api",
    ),
    DirectorySource(
        url="https://www.britishfencing.com/clubfinder/",
        name="British Fencing Club Finder",
        country="United Kingdom",
        source_kind="federation_page",
        parser="html",
    ),
    DirectorySource(
        url="https://www.britishfencing.com/members/clubs/affiliated-club-list/",
        name="British Fencing affiliated club list",
        country="United Kingdom",
        source_kind="federation_page",
        parser="html",
    ),
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_source(source: DirectorySource) -> FetchedContent:
    headers = dict(HEADERS)
    if source.parser.endswith("api"):
        headers.update({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    response = requests.get(
        source.url, headers=headers, timeout=25, allow_redirects=True
    )
    response.raise_for_status()
    return FetchedContent(
        content=response.content,
        content_type=response.headers.get("content-type", ""),
        final_url=response.url,
    )


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def fold_text(value: Any) -> str:
    text = clean_text(value).casefold()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def canonical_country(value: Any) -> str | None:
    country = clean_text(value)
    if not country:
        return None
    return COUNTRY_ALIASES.get(fold_text(country), country)


def normalize_url(value: Any, base_url: str | None = None) -> str | None:
    url = clean_text(value)
    if not url:
        return None
    if base_url:
        url = urljoin(base_url, url)
    parsed = urlparse(url)
    if not parsed.scheme and "." in url:
        url = f"https://{url}"
        parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return url


def website_domain(website: str | None) -> str | None:
    if not website:
        return None
    parsed = urlparse(website)
    host = parsed.netloc.casefold()
    return host[4:] if host.startswith("www.") else host or None


def is_private_context(line: str) -> bool:
    folded = fold_text(line)
    return any(hint in folded for hint in PRIVATE_CONTACT_HINTS)


def is_public_email(email: str, website: str | None = None, context: str = "") -> bool:
    if is_private_context(context):
        return False
    local, _, domain = email.casefold().partition("@")
    if not local or not domain or domain in FREE_EMAIL_DOMAINS:
        return False
    if local in PUBLIC_EMAIL_PREFIXES:
        return True
    site_domain = website_domain(website)
    return bool(site_domain and domain.endswith(site_domain) and "." not in local)


def normalize_phone(value: str) -> str:
    return clean_text(value).strip(" .,;:")


def is_public_phone(phone: str, context: str = "") -> bool:
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return False
    return not is_private_context(context)


def extract_public_contact(text: str, *, website: str | None = None) -> dict[str, str]:
    contact: dict[str, str] = {}
    lines = [line for line in (clean_text(line) for line in text.splitlines()) if line]
    if not lines and text:
        lines = [clean_text(text)]

    for line in lines:
        for match in EMAIL_RE.finditer(line):
            email = match.group(0)
            if "email" not in contact and is_public_email(email, website, line):
                contact["email"] = email
        for match in PHONE_RE.finditer(line):
            phone = normalize_phone(match.group(0))
            if "phone" not in contact and is_public_phone(phone, line):
                contact["phone"] = phone
    return contact


def merge_public_contact(*contacts: dict[str, str] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        for key, value in contact.items():
            if key not in merged and clean_text(value):
                merged[key] = clean_text(value)
    return merged


def parse_weapons(text: str) -> list[str]:
    found = [weapon for weapon, pattern in WEAPON_PATTERNS if pattern.search(text)]
    if re.search(r"\ball\s+weapons\b|\bthree[-\s]?weapon\b", text, flags=re.I):
        found = ["epee", "foil", "saber"]
    return sorted(set(found))


def parse_programs(text: str) -> list[str]:
    return sorted(
        {
            program
            for program, pattern in PROGRAM_PATTERNS
            if pattern.search(text)
        }
    )


def clean_list(values: Iterable[Any] | None) -> list[str]:
    if not values:
        return []
    return sorted({clean_text(value).casefold() for value in values if clean_text(value)})


def address_from_parts(*parts: Any) -> str | None:
    values = [clean_text(part).strip(" ,") for part in parts if clean_text(part)]
    if not values:
        return None
    return ", ".join(dict.fromkeys(values))


def address_from_public_address(address: dict[str, Any]) -> str | None:
    formatted = clean_text(address.get("formatted_address"))
    if formatted:
        return formatted
    return address_from_parts(
        address.get("street1") or address.get("address1"),
        address.get("street2") or address.get("address2"),
        address.get("city"),
        address.get("state"),
        address.get("zip") or address.get("postcode"),
    )


def parse_address_line(value: Any, source: DirectorySource | None = None) -> tuple[str | None, str | None, str | None]:
    address = clean_text(value).strip(" ,")
    if not address:
        return None, None, canonical_country(source.country if source else None)

    parts = [part.strip() for part in address.split(",") if clean_text(part)]
    city = None
    country = canonical_country(source.country if source else None)
    if len(parts) >= 3:
        city = clean_text(parts[-2])
        country = canonical_country(parts[-1]) or country
    elif len(parts) == 2:
        city = clean_text(parts[-1])
    return address, city, country


def _jsonld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        queue = payload if isinstance(payload, list) else [payload]
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
                continue
            objects.append(item)
    return objects


def _jsonld_type(value: Any) -> set[str]:
    if isinstance(value, list):
        return {fold_text(item) for item in value}
    return {fold_text(value)}


def _address_from_jsonld(value: Any, source: DirectorySource) -> tuple[str | None, str | None, str | None]:
    if isinstance(value, dict):
        address = address_from_parts(
            value.get("streetAddress"),
            value.get("addressLocality"),
            value.get("addressRegion"),
            value.get("postalCode"),
            value.get("addressCountry"),
        )
        country = canonical_country(value.get("addressCountry")) or source.country
        return address, clean_text(value.get("addressLocality")) or None, canonical_country(country)
    return parse_address_line(value, source)


def _facility_type_from_jsonld(types: set[str]) -> str:
    if any("school" in item for item in types):
        return "school"
    if any("sportsactivitylocation" in item or "sportsclub" in item for item in types):
        return "club"
    return "training_facility"


def record_from_fields(
    *,
    name: Any,
    address: Any,
    city: Any = None,
    country: Any = None,
    website: Any = None,
    contact_public: dict[str, str] | None = None,
    weapons: Iterable[Any] | None = None,
    programs: Iterable[Any] | None = None,
    facility_type: str = "club",
    source: DirectorySource,
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict | None:
    clean_name = clean_text(name)
    clean_address = clean_text(address)
    clean_country = canonical_country(country) or canonical_country(source.country)
    if not clean_name or not clean_address:
        return None

    row = {
        "name": clean_name,
        "type": clean_text(facility_type) or "training_facility",
        "address": clean_address,
        "city": clean_text(city) or None,
        "country": clean_country,
        "website": normalize_url(website, source.url),
        "contact_public": dict(contact_public or {}),
        "weapons": clean_list(weapons),
        "programs": clean_list(programs),
        "source_url": source_url or source.url,
        "metadata": {
            "source_kind": source.source_kind,
            "source_name": source.name,
            "parser": source.parser,
            **(metadata or {}),
        },
    }
    return {key: value for key, value in row.items() if value not in (None, "", [])}


def parse_usafencing_facilities(payload: dict[str, Any], source: DirectorySource) -> list[dict]:
    models = ((payload.get("indexData") or {}).get("models") or [])
    rows: list[dict] = []
    for club in models:
        if club.get("inactive"):
            continue
        public_address = club.get("publicAddress") if isinstance(club.get("publicAddress"), dict) else {}
        address = address_from_public_address(public_address)
        if not address:
            continue
        club_type = club.get("club_type") or club.get("type") or "club"
        if isinstance(club_type, dict):
            club_type = club_type.get("label") or "club"
        metadata = {
            "usafencing_id": club.get("id"),
            "usafencing_slug": club.get("slug"),
            "division": (club.get("division") or {}).get("label"),
            "region": (club.get("region") or {}).get("label"),
            "club_type": clean_text(club_type),
        }
        _rec = record_from_fields(
            name=club.get("name"),
            address=address,
            city=public_address.get("city"),
            country=source.country,
            website=club.get("website"),
            facility_type="club",
            source=source,
            metadata={key: value for key, value in metadata.items() if value},
        )
        if _rec is not None:
            rows.append(_rec)
    return [row for row in rows if row]


def record_from_jsonld(item: dict[str, Any], source: DirectorySource) -> dict | None:
    types = _jsonld_type(item.get("@type"))
    if not any(
        token in item_type
        for item_type in types
        for token in ("localbusiness", "sportsactivitylocation", "sportsclub", "school")
    ):
        return None
    address, city, country = _address_from_jsonld(item.get("address"), source)
    website = normalize_url(item.get("url") or item.get("sameAs"), source.url)
    contact = merge_public_contact(
        {"email": str(item.get("email") or "")} if is_public_email(clean_text(item.get("email")), website) else None,
        {"phone": str(item.get("telephone") or "")} if is_public_phone(clean_text(item.get("telephone"))) else None,
    )
    return record_from_fields(
        name=item.get("name"),
        address=address,
        city=city,
        country=country,
        website=website,
        contact_public=contact,
        facility_type=_facility_type_from_jsonld(types),
        source=source,
        metadata={"jsonld_type": sorted(types)},
    )


def _candidate_blocks(soup: BeautifulSoup) -> list[Tag]:
    blocks: list[Tag] = []
    selector = (
        "[class*='club'], [class*='facility'], [class*='location'], "
        "[class*='listing'], [class*='result'], [class*='card'], "
        "[id*='club'], [id*='facility'], [id*='location']"
    )
    for element in soup.select(selector):
        if not isinstance(element, Tag):
            continue
        text = clean_text(element.get_text(" ", strip=True))
        if len(text) < 20:
            continue
        if element.find(["h1", "h2", "h3", "h4", "a"]) and element not in blocks:
            blocks.append(element)
    if not blocks and soup.body:
        blocks.append(soup.body)
    return blocks


def _name_from_block(block: Tag) -> str | None:
    for tag_name in ("h1", "h2", "h3", "h4"):
        heading = block.find(tag_name)
        if heading:
            text = clean_text(heading.get_text(" ", strip=True))
            if text:
                return text
    link = block.find("a")
    if link:
        text = clean_text(link.get_text(" ", strip=True))
        if text and not re.search(r"\b(?:website|email|contact|directions)\b", text, re.I):
            return text
    return None


def _address_from_block(block: Tag, source: DirectorySource) -> tuple[str | None, str | None, str | None]:
    for element in block.select("[class*='address'], [itemprop*='address']"):
        address, city, country = parse_address_line(element.get_text(" ", strip=True), source)
        if address:
            return address, city, country

    lines = [clean_text(line) for line in block.get_text("\n", strip=True).splitlines()]
    for line in lines:
        folded = fold_text(line)
        if "address" in folded and "," in line:
            candidate = re.sub(r"^address\s*[:\-]\s*", "", line, flags=re.I)
            address, city, country = parse_address_line(candidate, source)
            if address:
                return address, city, country
        if "," in line and re.search(r"\d", line) and not EMAIL_RE.search(line):
            address, city, country = parse_address_line(line, source)
            if address:
                return address, city, country
    return None, None, canonical_country(source.country)


def _website_from_block(block: Tag, source: DirectorySource) -> str | None:
    for link in block.find_all("a", href=True):
        url = normalize_url(link.get("href"), source.url)
        if not url:
            continue
        if urlparse(url).netloc and url != source.url:
            return url
    return None


def record_from_html_block(block: Tag, source: DirectorySource) -> dict | None:
    name = _name_from_block(block)
    address, city, country = _address_from_block(block, source)
    website = _website_from_block(block, source)
    text = block.get_text("\n", strip=True)
    return record_from_fields(
        name=name,
        address=address,
        city=city,
        country=country,
        website=website,
        contact_public=extract_public_contact(text, website=website),
        weapons=parse_weapons(text),
        programs=parse_programs(text),
        facility_type="club",
        source=source,
    )


def parse_facilities_from_html(html: str, source: DirectorySource) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = [record_from_jsonld(item, source) for item in _jsonld_objects(soup)]
    rows.extend(record_from_html_block(block, source) for block in _candidate_blocks(soup))
    return dedupe_facilities(row for row in rows if row)


def parse_fetched_content(source: DirectorySource, fetched: FetchedContent) -> list[dict]:
    content_type = fetched.content_type.lower()
    text = fetched.content.decode("utf-8", errors="replace")
    parse_source = DirectorySource(
        url=fetched.final_url or source.url,
        name=source.name,
        country=source.country,
        source_kind=source.source_kind,
        parser=source.parser,
    )

    if source.parser == "usafencing_api" or "json" in content_type:
        payload = json.loads(text)
        return parse_usafencing_facilities(payload, parse_source)
    return parse_facilities_from_html(text, parse_source)


def source_with_page(source: DirectorySource, page: int) -> DirectorySource:
    parsed = urlparse(source.url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    url = urlunparse(parsed._replace(query=urlencode(query)))
    return DirectorySource(
        url=url,
        name=source.name,
        country=source.country,
        source_kind=source.source_kind,
        parser=source.parser,
    )


def parse_usafencing_fetched(source: DirectorySource, fetched: FetchedContent) -> tuple[list[dict], bool]:
    payload = json.loads(fetched.content.decode("utf-8", errors="replace"))
    parse_source = DirectorySource(
        url=fetched.final_url or source.url,
        name=source.name,
        country=source.country,
        source_kind=source.source_kind,
        parser=source.parser,
    )
    pages = (payload.get("indexData") or {}).get("pages") or {}
    return parse_usafencing_facilities(payload, parse_source), bool(pages.get("hasMorePages"))


def fetch_and_parse_source(
    source: DirectorySource,
    fetcher: Callable[[DirectorySource], FetchedContent],
    *,
    max_pages: int = 100,
) -> list[dict]:
    if source.parser != "usafencing_api":
        return parse_fetched_content(source, fetcher(source))

    rows: list[dict] = []
    page = 1
    while page <= max_pages:
        paged_source = source_with_page(source, page)
        page_rows, has_more = parse_usafencing_fetched(paged_source, fetcher(paged_source))
        rows.extend(page_rows)
        if not has_more:
            break
        page += 1
    return rows


def address_key(value: Any) -> str:
    text = fold_text(value)
    text = re.sub(r"[.,#]", " ", text)
    replacements = {
        r"\bst\b": "street",
        r"\bave\b": "avenue",
        r"\brd\b": "road",
        r"\bblvd\b": "boulevard",
        r"\bdr\b": "drive",
        r"\bste\b": "suite",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def name_key(value: Any) -> str:
    text = fold_text(value).replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def country_key(value: Any) -> str:
    return fold_text(canonical_country(value) or "")


def dedupe_key(row: dict) -> tuple[str, str, str]:
    return (name_key(row.get("name")), address_key(row.get("address")), country_key(row.get("country")))


def merge_lists(*values: Iterable[Any] | None) -> list[str]:
    merged: set[str] = set()
    for group in values:
        for value in group or []:
            cleaned = clean_text(value).casefold()
            if cleaned:
                merged.add(cleaned)
    return sorted(merged)


def dedupe_facilities(rows: Iterable[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str], dict] = {}
    for raw_row in rows:
        row = dict(raw_row)
        row["name"] = clean_text(row.get("name"))
        row["address"] = clean_text(row.get("address"))
        row["country"] = canonical_country(row.get("country"))
        row["weapons"] = clean_list(row.get("weapons"))
        row["programs"] = clean_list(row.get("programs"))
        row["contact_public"] = dict(row.get("contact_public") or {})
        row["metadata"] = dict(row.get("metadata") or {})
        key = dedupe_key(row)
        if not all(key):
            continue

        if key not in deduped:
            deduped[key] = {k: v for k, v in row.items() if v not in (None, "", [])}
            continue

        existing = deduped[key]
        duplicate_url = row.get("source_url")
        if duplicate_url and duplicate_url != existing.get("source_url"):
            urls = existing.setdefault("metadata", {}).setdefault("duplicate_source_urls", [])
            if duplicate_url not in urls:
                urls.append(duplicate_url)

        existing["contact_public"] = merge_public_contact(
            existing.get("contact_public"), row.get("contact_public")
        )
        existing["weapons"] = merge_lists(existing.get("weapons"), row.get("weapons"))
        existing["programs"] = merge_lists(existing.get("programs"), row.get("programs"))
        for field in ("city", "website", "lat", "lon"):
            if not existing.get(field) and row.get(field):
                existing[field] = row[field]

    return list(deduped.values())


def fetch_all(query: Any, batch_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = query.range(offset, offset + batch_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < batch_size:
            return rows
        offset += batch_size


def facilities_from_existing_clubs(client: Any) -> list[dict]:
    try:
        query = client.table("fs_clubs").select(
            "name,address,city,country,website,instagram,twitter,facebook,metadata"
        )
        club_rows = fetch_all(query)
    except Exception as exc:
        print(f"[{SOURCE}] existing fs_clubs source skipped: {exc}")
        return []

    facilities: list[dict] = []
    source = DirectorySource(
        url="fs_clubs",
        name="Existing fs_clubs",
        source_kind="existing_fs_clubs",
        parser="existing_table",
    )
    for club in club_rows:
        metadata = (club.get("metadata") if isinstance(club.get("metadata"), dict) else {}) or {}
        contact = {
            key: clean_text(club.get(key))
            for key in ("instagram", "twitter", "facebook")
            if clean_text(club.get(key))
        }
        row = record_from_fields(
            name=club.get("name"),
            address=club.get("address"),
            city=club.get("city"),
            country=club.get("country"),
            website=club.get("website"),
            contact_public=contact,
            weapons=metadata.get("weapons") if isinstance(metadata.get("weapons"), list) else [],
            programs=metadata.get("programs") if isinstance(metadata.get("programs"), list) else [],
            facility_type="club",
            source=source,
            source_url=None,
            metadata={"source_kind": "existing_fs_clubs"},
        )
        if row:
            row["metadata"] = {"source_kind": "existing_fs_clubs"}
            row["source_url"] = None
            row.setdefault("programs", [])
            row.setdefault("weapons", [])
            facilities.append(row)
    return facilities


def _coerce_geocode(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        lat = value.get("lat") or value.get("latitude")
        lon = value.get("lon") or value.get("longitude")
    else:
        lat = getattr(value, "lat", None) or getattr(value, "latitude", None)
        lon = getattr(value, "lon", None) or getattr(value, "longitude", None)
    try:
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def configured_geocoder() -> Callable[[dict], Any] | None:
    provider = clean_text(os.environ.get("TRAINING_FACILITIES_GEOCODER_PROVIDER")).casefold()
    if not provider:
        return None
    if provider in {"nominatim", "osm"}:
        from enrich_locations import geocode_location

        return lambda row: geocode_location(
            clean_text(row.get("city") or row.get("address")),
            clean_text(row.get("country")),
        )
    if provider == "mapbox":
        token = os.environ.get("MAPBOX_GEOCODING_TOKEN")
        if not token:
            return None

        def geocode_mapbox(row: dict) -> dict | None:
            query = " ".join(
                part
                for part in [
                    clean_text(row.get("address")),
                    clean_text(row.get("city")),
                    clean_text(row.get("country")),
                ]
                if part
            )
            if not query:
                return None
            response = requests.get(
                "https://api.mapbox.com/geocoding/v5/mapbox.places/"
                f"{requests.utils.quote(query)}.json",
                params={"access_token": token, "limit": 1},
                timeout=20,
            )
            response.raise_for_status()
            features = response.json().get("features") or []
            if not features:
                return None
            lon, lat = features[0].get("center") or [None, None]
            return {"lat": lat, "lon": lon}

        return geocode_mapbox
    return None


def geocode_rows(rows: list[dict], geocoder: Callable[[dict], Any] | None) -> int:
    if not geocoder:
        return 0
    geocoded = 0
    for row in rows:
        if row.get("lat") is not None and row.get("lon") is not None:
            continue
        result = _coerce_geocode(geocoder(row))
        if not result:
            continue
        row["lat"], row["lon"] = result
        geocoded += 1
    return geocoded


def prepare_rows_for_upsert(rows: Iterable[dict]) -> list[dict]:
    scraped_at = datetime.now(timezone.utc).isoformat()
    prepared: list[dict] = []
    for row in rows:
        clean_row = {
            key: value
            for key, value in dict(row).items()
            if value not in (None, "", []) and key not in {"latitude", "longitude"}
        }
        clean_row.setdefault("contact_public", {})
        clean_row.setdefault("metadata", {})
        clean_row["scraped_at"] = scraped_at
        prepared.append(clean_row)
    return prepared


def batch_upsert_training_facilities(client: Any, rows: list[dict]) -> int:
    if not rows:
        return 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table("fs_training_facilities").upsert(
            batch, on_conflict="name,address,country"
        ).execute()
    return len(rows)


def scrape_training_facilities(
    *,
    client=None,
    sources: Iterable[DirectorySource] | None = None,
    fetcher: Callable[[DirectorySource], FetchedContent] = fetch_source,
    geocoder: Callable[[dict], Any] | None = None,
    include_existing_clubs: bool = True,
    log_run: bool = True,
    update_state: bool = True,
) -> dict:
    source_list = list(sources or DEFAULT_SOURCES)
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    parsed_rows: list[dict] = []
    failed = 0
    skipped = 0
    existing_clubs = 0

    try:
        for source in source_list:
            try:
                rows = fetch_and_parse_source(source, fetcher)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.url}: {exc}")
                continue
            if not rows:
                skipped += 1
            parsed_rows.extend(rows)

        if client and include_existing_clubs:
            existing_rows = facilities_from_existing_clubs(client)
            existing_clubs = len(existing_rows)
            parsed_rows.extend(existing_rows)

        rows = dedupe_facilities(parsed_rows)
        geocoded = geocode_rows(rows, geocoder if geocoder is not None else configured_geocoder())
        prepared = prepare_rows_for_upsert(rows)
        written = batch_upsert_training_facilities(client, prepared) if client else 0
        summary = {
            "sources": len(source_list),
            "parsed": len(parsed_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "existing_clubs": existing_clubs,
            "geocoded": geocoded,
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
    summary = scrape_training_facilities()
    print(
        "training facilities: "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
