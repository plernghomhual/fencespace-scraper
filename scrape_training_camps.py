import io
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "scrape_training_camps"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
BATCH_SIZE = 100

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)

CURRENCIES = {
    "$": "USD",
    "usd": "USD",
    "us$": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "chf": "CHF",
}

GENERIC_HEADINGS = {
    "camp",
    "camps",
    "summer camp",
    "fencing camps",
    "featured camps",
    "share",
    "contact us",
    "follow us",
    "phone",
    "email",
    "address",
    "success!",
    "camp dates",
    "camp hours",
    "camp focus",
    "competitive camps",
    "2026 competitive fencing camps",
    "pre-nationals and pre-season camps",
}


@dataclass(frozen=True)
class CampSource:
    url: str
    organizer: str
    city: str | None = None
    country: str | None = None
    source_kind: str = "club"


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


DEFAULT_SOURCES = [
    CampSource(
        url="https://www.eurofencing.info/activities/camps",
        organizer="European Fencing Confederation",
        source_kind="federation_index",
    ),
    CampSource(
        url="https://www.eurofencing.info/getFile/case%3Ashow/id%3A497082",
        organizer="European Fencing Confederation",
        source_kind="federation_pdf",
    ),
    CampSource(
        url="https://www.apexfencing.net/camp/competitive-camps/",
        organizer="Apex Fencing Academy",
        city="Research Triangle",
        country="USA",
        source_kind="club",
    ),
    CampSource(
        url="https://www.capfencing.com/camps",
        organizer="Capital Fencing Academy",
        city="North Jersey",
        country="USA",
        source_kind="club",
    ),
    CampSource(
        url="https://www.missionfencing.com/camps",
        organizer="Mission Fencing Center",
        country="USA",
        source_kind="club",
    ),
    CampSource(
        url="https://www.nwfencing.org/camps/",
        organizer="Northwest Fencing Center",
        city="Portland",
        country="USA",
        source_kind="club",
    ),
    CampSource(
        url="https://www.hookedonfencing.org/camp",
        organizer="Hooked on Fencing",
        city="North Royalton",
        country="USA",
        source_kind="club",
    ),
    CampSource(
        url="https://www.californiafencingcamp.com/",
        organizer="California Fencing Camp",
        city="Pebble Beach",
        country="USA",
        source_kind="club",
    ),
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_source(source: CampSource) -> FetchedContent:
    response = requests.get(
        source.url, headers=HEADERS, timeout=25, allow_redirects=True
    )
    response.raise_for_status()
    return FetchedContent(
        content=response.content,
        content_type=response.headers.get("content-type", ""),
        final_url=response.url,
    )


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def has_camp_word(value: str) -> bool:
    return bool(re.search(r"\b(?:camp|camps|training)\b", ascii_lower(value)))


def strip_ordinals(value: str) -> str:
    return re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", value, flags=re.I)


def normalize_date_text(value: str) -> str:
    value = strip_ordinals(clean_text(value))
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*-\s*(\d{1,2})\s+\1\s+(\d{4})\b",
        r"\1 \2-\3, \4",
        value,
        flags=re.I,
    )
    return value


def month_number(value: str) -> int:
    key = value.strip(".").lower()
    if key not in MONTHS:
        raise ValueError(f"unknown month {value!r}")
    return MONTHS[key]


def iso_date(year: int, month: int, day: int) -> str:
    return date(year, month, day).isoformat()


def parse_date_range(text: str) -> tuple[str | None, str | None]:
    normalized = normalize_date_text(text)

    dot_range = re.search(
        r"\b(?P<d1>\d{1,2})\.(?P<m1>\d{1,2})\.\s*-\s*"
        r"(?P<d2>\d{1,2})\.(?P<m2>\d{1,2})\.(?P<y>\d{4})\b",
        normalized,
    )
    if dot_range:
        year = int(dot_range.group("y"))
        return (
            iso_date(year, int(dot_range.group("m1")), int(dot_range.group("d1"))),
            iso_date(year, int(dot_range.group("m2")), int(dot_range.group("d2"))),
        )

    full_numeric_range = re.search(
        r"\b(?P<a>\d{1,2})[./](?P<b>\d{1,2})[./](?P<y1>\d{4})\s*-\s*"
        r"(?P<c>\d{1,2})[./](?P<d>\d{1,2})[./](?P<y2>\d{4})\b",
        normalized,
    )
    if full_numeric_range:
        year1 = int(full_numeric_range.group("y1"))
        year2 = int(full_numeric_range.group("y2"))
        if "." in full_numeric_range.group(0):
            start_month = int(full_numeric_range.group("b"))
            start_day = int(full_numeric_range.group("a"))
            end_month = int(full_numeric_range.group("d"))
            end_day = int(full_numeric_range.group("c"))
        else:
            start_month = int(full_numeric_range.group("a"))
            start_day = int(full_numeric_range.group("b"))
            end_month = int(full_numeric_range.group("c"))
            end_day = int(full_numeric_range.group("d"))
        return (
            iso_date(year1, start_month, start_day),
            iso_date(year2, end_month, end_day),
        )

    compact_numeric = re.search(
        r"\b(?P<y>20\d{2})\b.{0,40}?"
        r"(?P<m1>\d{1,2})/(?P<d1>\d{1,2})\s*-\s*"
        r"(?:[A-Za-z]+,\s*)?(?P<m2>\d{1,2})/(?P<d2>\d{1,2})\b",
        normalized,
    )
    if compact_numeric:
        year = int(compact_numeric.group("y"))
        return (
            iso_date(year, int(compact_numeric.group("m1")), int(compact_numeric.group("d1"))),
            iso_date(year, int(compact_numeric.group("m2")), int(compact_numeric.group("d2"))),
        )

    prior_year_month_range = re.search(
        rf"\b(?P<y>20\d{{2}})\b.{{0,80}}?\b"
        rf"(?P<m1>{MONTH_PATTERN})\.?\s+(?P<d1>\d{{1,2}})\s*-\s*"
        rf"(?:(?P<m2>{MONTH_PATTERN})\.?\s+)?(?P<d2>\d{{1,2}})\b",
        normalized,
        flags=re.I,
    )
    if prior_year_month_range:
        year = int(prior_year_month_range.group("y"))
        start_month = month_number(prior_year_month_range.group("m1"))
        end_month = month_number(
            prior_year_month_range.group("m2") or prior_year_month_range.group("m1")
        )
        end_year = year + 1 if end_month < start_month else year
        return (
            iso_date(year, start_month, int(prior_year_month_range.group("d1"))),
            iso_date(end_year, end_month, int(prior_year_month_range.group("d2"))),
        )

    month_range = re.search(
        rf"\b(?P<m1>{MONTH_PATTERN})\.?\s+(?P<d1>\d{{1,2}})\s*-\s*"
        rf"(?:(?P<m2>{MONTH_PATTERN})\.?\s+)?(?P<d2>\d{{1,2}}),?\s*(?P<y>\d{{4}})\b",
        normalized,
        flags=re.I,
    )
    if month_range:
        year = int(month_range.group("y"))
        start_month = month_number(month_range.group("m1"))
        end_month = month_number(month_range.group("m2") or month_range.group("m1"))
        end_year = year + 1 if end_month < start_month else year
        return (
            iso_date(year, start_month, int(month_range.group("d1"))),
            iso_date(end_year, end_month, int(month_range.group("d2"))),
        )

    single_month = re.search(
        rf"\b(?P<m1>{MONTH_PATTERN})\.?\s+(?P<d1>\d{{1,2}}),?\s*(?P<y>\d{{4}})\b",
        normalized,
        flags=re.I,
    )
    if single_month:
        day = int(single_month.group("d1"))
        month = month_number(single_month.group("m1"))
        year = int(single_month.group("y"))
        value = iso_date(year, month, day)
        return value, value

    return None, None


def parse_cost(text: str) -> tuple[float | int | None, str]:
    normalized = clean_text(text)
    patterns = [
        r"(?P<currency>\$|€|£|USD|US\$|EUR|GBP|CHF)\s*(?P<amount>\d[\d,]*(?:[.,]\d{2})?)",
        r"(?P<amount>\d[\d,]*(?:[.,]\d{2})?)\s*(?P<currency>USD|EUR|GBP|CHF|euros?|EURO)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.I)
        if not match:
            continue
        currency = CURRENCIES.get(match.group("currency").lower(), match.group("currency").upper())
        amount_text = match.group("amount").replace(",", "")
        if currency == "EUR" and "," in match.group("amount") and "." not in match.group("amount"):
            amount_text = match.group("amount").replace(",", ".")
        amount = float(amount_text)
        if amount.is_integer():
            amount = int(amount)
        return amount, currency
    return None, "USD"


def parse_weapons(text: str) -> list[str]:
    lowered = ascii_lower(text)
    if "all-weapons" in lowered or "all weapons" in lowered or "3-weapon" in lowered:
        return ["epee", "foil", "saber"]

    weapons = []
    for canonical, variants in {
        "epee": ["epee", "eppee", "epee", "epe"],
        "foil": ["foil"],
        "saber": ["saber", "sabre"],
    }.items():
        if any(re.search(rf"\b{re.escape(variant)}\b", lowered) for variant in variants):
            weapons.append(canonical)
    return weapons


def parse_coaches(text: str) -> list[str]:
    coaches: list[str] = []
    pattern = re.compile(
        r"\bCoach\s+([A-Z][A-Za-z' .-]+?)(?=\s+(?:and\s+)?Coach\b|[,.;\n]|$)"
    )
    for match in pattern.finditer(text):
        name = clean_text(match.group(1)).strip(" .,-")
        if name and name not in coaches:
            coaches.append(name)
    return coaches


def parse_max_participants(text: str) -> int | None:
    match = re.search(
        r"(?:limited to|maximum of|max(?:imum)?|spaces? (?:are )?limited to)\s+(\d{1,3})",
        text,
        flags=re.I,
    )
    return int(match.group(1)) if match else None


def parse_host(text: str, fallback: str) -> str:
    match = re.search(r"\bHost:\s*(.+?)(?:\n|Venue:|Date:|Costs?:|$)", text, flags=re.I | re.S)
    if not match:
        return fallback
    host = clean_text(match.group(1))
    host = re.split(r"\s+in cooperation\s+with\s+", host, flags=re.I)[0]
    return host or fallback


def parse_location(text: str, source: CampSource) -> tuple[str | None, str | None]:
    if source.city and source.country:
        return source.city, source.country

    parsed_city = None
    parsed_country = None
    postal_match = re.search(
        r"\b\d{4,6}\s+([A-Z][A-Za-z .'-]+),\s*([A-Z][A-Za-z '-]+)\b",
        text,
    )
    if postal_match:
        parsed_city = clean_text(postal_match.group(1))
        parsed_country = clean_text(postal_match.group(2))

    venue_match = re.search(
        r"\bVenue:\s*.+?,\s*([A-Z][A-Za-z .'-]+),\s*([A-Z][A-Za-z '-]+)\b",
        text,
        flags=re.I,
    )
    if venue_match and not parsed_city:
        parsed_city = clean_text(venue_match.group(1))
        parsed_country = clean_text(venue_match.group(2))

    held_in = re.search(
        r"\bin\s+([A-Z][A-Za-z .'-]+?),\s*([A-Z][A-Za-z '-]+?)(?:[.;]|$)",
        text,
    )
    if held_in and not parsed_city:
        parsed_city = clean_text(held_in.group(1))
        parsed_country = clean_text(held_in.group(2))

    return source.city or parsed_city, source.country or parsed_country


def create_camp_record(
    *,
    name: str,
    text: str,
    source: CampSource,
    source_url: str | None = None,
) -> dict | None:
    cleaned_name = clean_text(name).strip(":- ")
    if not cleaned_name:
        return None

    start_date, end_date = parse_date_range(text)
    if not start_date:
        return None

    organizer = parse_host(text, source.organizer)
    city, country = parse_location(text, source)
    cost, currency = parse_cost(text)
    record = {
        "name": cleaned_name,
        "organizer": organizer,
        "city": city,
        "country": country,
        "start_date": start_date,
        "end_date": end_date,
        "coaches": parse_coaches(text),
        "cost": cost,
        "currency": currency,
        "weapons_covered": parse_weapons(f"{cleaned_name} {text}"),
        "max_participants": parse_max_participants(text),
        "source_url": source_url or source.url,
        "metadata": {
            "source_kind": source.source_kind,
            "source_organizer": source.organizer,
        },
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    return {key: value for key, value in record.items() if value is not None}


def heading_level(tag: Tag) -> int:
    try:
        return int(tag.name[1])
    except (TypeError, ValueError):
        return 6


def segment_for_heading(heading: Tag) -> str:
    level = heading_level(heading)
    parts = [heading.get_text(" ", strip=True)]
    for sibling in heading.next_siblings:
        if isinstance(sibling, Tag) and re.fullmatch(r"h[1-6]", sibling.name or ""):
            if heading_level(sibling) <= level:
                break
        if isinstance(sibling, Tag):
            parts.append(sibling.get_text(" ", strip=True))
        elif isinstance(sibling, str):
            parts.append(sibling)
    return clean_text(" ".join(parts))


def is_camp_heading(text: str) -> bool:
    normalized = ascii_lower(clean_text(text)).strip(":- ")
    if not normalized or normalized in GENERIC_HEADINGS:
        return False
    return has_camp_word(normalized)


def parse_index_links(soup: BeautifulSoup, source: CampSource) -> list[dict]:
    camps: list[dict] = []
    seen_texts: set[str] = set()
    for link in soup.find_all("a"):
        text = clean_text(link.get_text(" ", strip=True))
        if not text or text in seen_texts:
            continue
        if "camp" not in ascii_lower(text) and "training" not in ascii_lower(text):
            continue
        record = create_camp_record(
            name=text,
            text=text,
            source=source,
            source_url=urljoin(source.url, link.get("href") or source.url),
        )
        if record:
            camps.append(record)
            seen_texts.add(text)
    return camps


def inline_camp_name(line: str) -> str | None:
    lowered = ascii_lower(line).strip()
    if lowered.startswith(("this camp", "the camp", "during the camp", "camp will")):
        return None

    candidate = ""
    if ":" in line and line.index(":") <= 100:
        candidate = line.split(":", 1)[0]
    elif "," in line:
        before_comma, after_comma = line.split(",", 1)
        if parse_date_range(after_comma)[0]:
            candidate = before_comma
    else:
        date_start = re.search(
            rf"\b(?:{MONTH_PATTERN}|\d{{1,2}}[./]\d{{1,2}}|20\d{{2}})\b",
            line,
            flags=re.I,
        )
        if date_start:
            candidate = line[: date_start.start()]

    candidate = clean_text(candidate).strip(" ,-:")
    normalized = ascii_lower(candidate).strip(":- ")
    if not candidate or normalized in GENERIC_HEADINGS:
        return None
    if normalized.startswith(("this camp", "the camp", "sign up")):
        return None
    if re.match(r"^\w+\s+camps?\s+throughout\b", normalized):
        return None
    if not has_camp_word(normalized):
        return None
    if len(candidate) > 100:
        return None
    return candidate.strip(" ,-:–—")


def is_specific_fallback_title(title: str) -> bool:
    normalized = ascii_lower(clean_text(title)).strip(":- ")
    if not normalized or normalized in GENERIC_HEADINGS:
        return False
    if any(
        phrase in normalized
        for phrase in ("about our camps", "camps at ", "camp dates", " activity ")
    ):
        return False
    return ("camp" in normalized or "training" in normalized) and len(title) <= 120


def is_nearby_camp_name(line: str) -> bool:
    text = clean_text(line).strip(" ,-:")
    normalized = ascii_lower(text).strip(":- ")
    if not text or normalized in GENERIC_HEADINGS:
        return False
    if text[0].islower() or text.endswith("."):
        return False
    if normalized.startswith(
        ("this camp", "the camp", "and ", "cost ", "the cost", "sign up")
    ):
        return False
    if any(
        phrase in normalized
        for phrase in ("about our camps", "camps at ", "camp dates", " activity ")
    ):
        return False
    if re.match(r"^\w+\s+camps?\s+throughout\b", normalized):
        return False
    return bool(re.search(r"\bcamps?\b", normalized)) and len(text) <= 100


def parse_inline_camp_lines(text: str, source: CampSource) -> list[dict]:
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    camps: list[dict] = []
    seen_names: set[str] = set()

    for index, line in enumerate(lines):
        lowered = ascii_lower(line)
        if not has_camp_word(line):
            continue

        context = "\n".join(lines[max(0, index - 3) : index + 8])
        line_has_date = bool(parse_date_range(line)[0])
        context_has_date = bool(parse_date_range(context)[0])
        if not line_has_date and not context_has_date:
            continue

        name = inline_camp_name(line)
        if not name and context_has_date and is_nearby_camp_name(line):
            name = clean_text(line).strip(" ,-:")
        if not name:
            continue
        if name in seen_names:
            continue

        record = create_camp_record(name=name, text=context, source=source)
        if record:
            camps.append(record)
            seen_names.add(name)
    return camps


def parse_camps_from_html(html: str, source: CampSource) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    camps = parse_index_links(soup, source)
    seen_keys = {
        (camp["name"], camp.get("start_date"), camp.get("end_date")) for camp in camps
    }

    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = clean_text(heading.get_text(" ", strip=True))
        if not is_camp_heading(heading_text):
            continue
        segment = segment_for_heading(heading)
        record = create_camp_record(name=heading_text, text=segment, source=source)
        if not record:
            continue
        key = (record["name"], record.get("start_date"), record.get("end_date"))
        if key not in seen_keys:
            camps.append(record)
            seen_keys.add(key)

    for record in parse_inline_camp_lines(soup.get_text("\n", strip=True), source):
        key = (record["name"], record.get("start_date"), record.get("end_date"))
        if key not in seen_keys:
            camps.append(record)
            seen_keys.add(key)

    if not camps:
        title = soup.title.get_text(" ", strip=True) if soup.title else source.organizer
        text = soup.get_text("\n", strip=True)
        if is_specific_fallback_title(title):
            record = create_camp_record(name=title, text=text, source=source)
            if record:
                camps.append(record)

    return camps


def parse_camps_from_text(text: str, source: CampSource) -> list[dict]:
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    name = next((line for line in lines if "camp" in ascii_lower(line)), source.organizer)
    record = create_camp_record(name=name, text=text, source=source)
    return [record] if record else []


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_fetched_content(source: CampSource, fetched: FetchedContent) -> list[dict]:
    content_type = fetched.content_type.lower()
    if "pdf" in content_type or fetched.content.startswith(b"%PDF"):
        text = extract_pdf_text(fetched.content)
        camps = parse_camps_from_text(text, source)
    elif "html" in content_type:
        camps = parse_camps_from_html(fetched.content.decode("utf-8", errors="replace"), source)
    else:
        camps = parse_camps_from_text(fetched.content.decode("utf-8", errors="replace"), source)

    for camp in camps:
        camp["source_url"] = fetched.final_url or camp.get("source_url") or source.url
    return camps


def dedupe_key(camp: dict) -> tuple[str, str, str | None, str | None]:
    return (
        ascii_lower(camp.get("name", "")),
        ascii_lower(camp.get("organizer", "")),
        camp.get("start_date"),
        camp.get("end_date"),
    )


def dedupe_camps(camps: Iterable[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str | None, str | None], dict] = {}
    for camp in camps:
        key = dedupe_key(camp)
        if not key[0]:
            continue
        if key not in deduped:
            camp = dict(camp)
            camp["metadata"] = dict(camp.get("metadata") or {})
            deduped[key] = camp
            continue

        existing = deduped[key]
        duplicate_url = camp.get("source_url")
        if duplicate_url and duplicate_url != existing.get("source_url"):
            urls = existing.setdefault("metadata", {}).setdefault("duplicate_source_urls", [])
            if duplicate_url not in urls:
                urls.append(duplicate_url)

        for field in ("coaches", "weapons_covered"):
            current = existing.get(field) or []
            for value in camp.get(field) or []:
                if value not in current:
                    current.append(value)
            if current:
                existing[field] = current

    return list(deduped.values())


def batch_upsert_training_camps(client, rows: list[dict]) -> int:
    if not rows:
        return 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table("fs_training_camps").upsert(
            batch, on_conflict="name,organizer,start_date,end_date"
        ).execute()
    return len(rows)


def scrape_training_camps(
    *,
    client=None,
    sources: Iterable[CampSource] | None = None,
    fetcher: Callable[[CampSource], FetchedContent] = fetch_source,
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
        for source in sources:
            try:
                fetched = fetcher(source)
                source_rows = parse_fetched_content(source, fetched)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.url}: {exc}")
                continue

            if not source_rows:
                skipped += 1
            parsed_rows.extend(source_rows)

        rows = dedupe_camps(parsed_rows)
        written = batch_upsert_training_camps(client, rows) if client else 0
        summary = {
            "sources": len(sources),
            "parsed": len(parsed_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
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
    summary = scrape_training_camps()
    print(
        "training camps: "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
