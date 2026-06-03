import io
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "scrape_photographer_directory"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
BATCH_SIZE = 100
REQUEST_TIMEOUT = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHOTO_BUSINESS_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&' .-]*(?:Photography|Photos|Photo|Media|Images)(?:\.com)?)\b"
)
PRIVATE_EMAIL_CONTEXT = {
    "athlete",
    "competitor",
    "entry",
    "fencer",
    "parent",
    "registration",
    "student",
}
PUBLIC_EMAIL_CONTEXT = {
    "business",
    "contact",
    "email",
    "gallery",
    "photo",
    "photographer",
    "photography",
}


@dataclass(frozen=True)
class PhotographerSource:
    url: str
    source_kind: str
    name: str | None = None
    business: str | None = None
    website: str | None = None
    email: str | None = None
    public_contact: str | None = None
    regions: list[str] = field(default_factory=list)
    event_name: str | None = None
    event_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


DEFAULT_SOURCES = [
    PhotographerSource(
        url="https://www.fencingphotos.com/about",
        source_kind="business_directory",
        business="FencingPhotos.com",
        website="https://www.fencingphotos.com/",
        regions=["USA", "International"],
        metadata={
            "coverage_note": "Local live probe was blocked by sandbox DNS; source is a known public fencing photography business page."
        },
    ),
    PhotographerSource(
        url="https://www.fencingphotos.com/home-page",
        source_kind="business_directory",
        business="FencingPhotos.com",
        website="https://www.fencingphotos.com/",
        regions=["USA", "International"],
        metadata={
            "coverage_note": "Local live probe was blocked by sandbox DNS; source is a known public fencing photography business page."
        },
    ),
    PhotographerSource(
        url="https://www.flickr.com/photos/fencingnet/albums/72157624625104299/",
        source_kind="public_gallery",
        business="FencingPhotos.com",
        website="https://www.fencingphotos.com/",
        regions=["International"],
        event_name="2010 Youth Olympic Games",
        metadata={"coverage_note": "Public gallery source discovered from public web search evidence."},
    ),
    PhotographerSource(
        url="https://static.fie.org/uploads/9/46343-AS.2-Bourges%20Press%20Kit%202016_V2-3.pdf",
        source_kind="federation_presskit",
        business="FencingPhotos.com",
        website="https://www.fencingphotos.com/",
        regions=["International"],
        event_name="2016 Bourges Junior and Cadet World Championships",
        event_url="https://www.bourges2016.com/",
        metadata={"coverage_note": "Public FIE press-kit source discovered from public web search evidence."},
    ),
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_source(source: PhotographerSource) -> FetchedContent:
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
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def ascii_lower(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(value))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def normalize_url(value: Any, base_url: str | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if base_url:
        text = urljoin(base_url, text)
    if text.startswith("//"):
        text = f"https:{text}"
    if text.startswith("www."):
        text = f"https://{text}"
    if "://" not in text and not text.startswith("mailto:"):
        text = f"https://{text}"
    if text.startswith("mailto:"):
        email = text.split(":", 1)[1].split("?", 1)[0].strip().lower()
        return f"mailto:{email}" if EMAIL_RE.fullmatch(email) else None

    parsed = urlparse(text)
    if not parsed.netloc:
        return None
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def website_domain(value: Any) -> str | None:
    url = normalize_url(value)
    if not url or url.startswith("mailto:"):
        return None
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def normalize_name(value: Any) -> str:
    lowered = ascii_lower(value)
    lowered = lowered.replace(".com", "")
    lowered = re.sub(r"\b(?:llc|inc|ltd|limited|the)\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def unique_values(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def official_for(text: str) -> list[str]:
    lowered = ascii_lower(text)
    values = []
    if "international fencing federation" in lowered or re.search(r"\bfie\b", lowered):
        values.append("FIE")
    if "usa fencing" in lowered:
        values.append("USA Fencing")
    return values


def source_title(soup: BeautifulSoup) -> str | None:
    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        if title:
            return title
    return None


def text_lines(text: str) -> list[str]:
    return [clean_text(line) for line in re.split(r"[\r\n]+", text) if clean_text(line)]


def public_email_from_lines(lines: Iterable[str]) -> str | None:
    for line in lines:
        emails = EMAIL_RE.findall(line)
        if not emails:
            continue
        lowered = ascii_lower(line)
        words = set(re.findall(r"[a-z]+", lowered))
        if words & PRIVATE_EMAIL_CONTEXT:
            continue
        if words & PUBLIC_EMAIL_CONTEXT:
            return emails[0].lower()
    return None


def extract_mailto(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    for anchor in soup.find_all("a", href=True):
        href = normalize_url(anchor.get("href"))
        if not href or not href.startswith("mailto:"):
            continue
        email = href.split(":", 1)[1]
        return email, href
    return None, None


def contact_link(soup: BeautifulSoup, base_url: str) -> str | None:
    for anchor in soup.find_all("a", href=True):
        text = ascii_lower(anchor.get_text(" ", strip=True))
        href = ascii_lower(anchor.get("href"))
        if "contact" not in text and "contact" not in href:
            continue
        normalized = normalize_url(anchor.get("href"), base_url=base_url)
        if normalized:
            return normalized
    return None


def detect_business(text: str, source: PhotographerSource) -> str | None:
    if source.business:
        return source.business
    lowered = ascii_lower(text)
    if "fencingphotos" in lowered:
        return "FencingPhotos.com"
    match = PHOTO_BUSINESS_RE.search(text)
    return clean_text(match.group(1)) if match else None


def detect_name(text: str, source: PhotographerSource) -> str | None:
    if source.name:
        return source.name
    lowered = ascii_lower(text)
    if "serge timacheff" in lowered or "s.timacheff" in lowered or "s timacheff" in lowered:
        return "Serge Timacheff"

    by_match = re.search(r"\bby\s+([A-Z][A-Za-z .'-]{2,60})\b", text)
    if by_match:
        return clean_text(by_match.group(1))

    photographer_match = re.search(
        r"\bphotographer\s*[:\-]\s*([A-Z][A-Za-z .'-]{2,60})(?:/|,|\.|$)",
        text,
        flags=re.IGNORECASE,
    )
    if photographer_match:
        return clean_text(photographer_match.group(1))
    return None


def detect_website(soup: BeautifulSoup | None, text: str, source: PhotographerSource) -> str | None:
    if source.website:
        return normalize_url(source.website)
    if soup:
        for anchor in soup.find_all("a", href=True):
            href = normalize_url(anchor.get("href"), base_url=source.url)
            if not href or href.startswith("mailto:"):
                continue
            domain = website_domain(href) or ""
            if any(token in domain for token in ("photo", "fencingphotos")):
                return href
    if "fencingphotos" in ascii_lower(text):
        return "https://www.fencingphotos.com/"
    return None


def extract_event_urls(soup: BeautifulSoup | None, source: PhotographerSource, *, gallery: bool = False) -> list[str]:
    urls = []
    if source.event_url:
        normalized = normalize_url(source.event_url, base_url=source.url)
        if normalized:
            urls.append(normalized)
    if gallery:
        normalized = normalize_url(source.url)
        if normalized:
            urls.append(normalized)
    if soup:
        for anchor in soup.find_all("a", href=True):
            text = ascii_lower(anchor.get_text(" ", strip=True))
            href = ascii_lower(anchor.get("href"))
            if not any(token in text or token in href for token in ("event", "gallery", "album", "tournament")):
                continue
            normalized = normalize_url(anchor.get("href"), base_url=source.url)
            if normalized:
                urls.append(normalized)
    return unique_values(urls)


def infer_event_name(soup: BeautifulSoup, source: PhotographerSource) -> str | None:
    if source.event_name:
        return source.event_name
    heading = soup.find("h1")
    if heading:
        text = clean_text(heading.get_text(" ", strip=True))
        if text:
            return text
    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        if title:
            return clean_text(title.split("|", 1)[0])
    return None


def base_metadata(
    source: PhotographerSource,
    *,
    title: str | None = None,
    text: str = "",
    event_name: str | None = None,
) -> dict[str, Any]:
    metadata = dict(source.metadata or {})
    metadata["source_kind"] = source.source_kind
    if title:
        metadata["source_title"] = title
    event = event_name or source.event_name
    if event:
        metadata["event_name"] = event
    official = official_for(text)
    if official:
        metadata["official_for"] = official
    return metadata


def make_record(
    *,
    source: PhotographerSource,
    text: str,
    scraped_at: str,
    soup: BeautifulSoup | None = None,
    title: str | None = None,
    gallery: bool = False,
    event_name: str | None = None,
) -> dict | None:
    business = detect_business(text, source)
    name = detect_name(text, source)
    if not business and not name:
        return None

    website = detect_website(soup, text, source)
    email = clean_text(source.email).lower() or None
    public_contact = normalize_url(source.public_contact) if source.public_contact else None
    if soup and not email:
        email, mailto = extract_mailto(soup)
        public_contact = public_contact or mailto
    if not email:
        email = public_email_from_lines(text_lines(text))
    if email and not public_contact:
        public_contact = f"mailto:{email}"
    if soup and not public_contact:
        public_contact = contact_link(soup, source.url)

    record = {
        "name": name,
        "business": business,
        "website": website,
        "email": email,
        "public_contact": public_contact,
        "regions": unique_values(source.regions),
        "event_urls": extract_event_urls(soup, source, gallery=gallery),
        "source_url": source.url,
        "metadata": base_metadata(source, title=title, text=text, event_name=event_name),
        "scraped_at": scraped_at,
    }
    return {key: value for key, value in record.items() if value is not None}


def parse_directory_html(
    html: str,
    source: PhotographerSource,
    scraped_at: str | None = None,
) -> list[dict]:
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text("\n", strip=True))
    lowered = ascii_lower(text)
    if not any(token in lowered for token in ("photo", "photographer", "gallery", "fencingphotos")):
        return []
    record = make_record(
        source=source,
        text=text,
        scraped_at=scraped_at,
        soup=soup,
        title=source_title(soup),
    )
    return [record] if record else []


def parse_directory_text(
    text: str,
    source: PhotographerSource,
    scraped_at: str | None = None,
) -> list[dict]:
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    lines = text_lines(text)
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if "photographer" not in ascii_lower(line):
            continue
        blocks.append(" ".join(lines[index : index + 3]))

    rows = []
    for block in blocks:
        record = make_record(
            source=source,
            text=block,
            scraped_at=scraped_at,
            event_name=source.event_name,
        )
        if record:
            rows.append(record)
    return rows


def parse_gallery_html(
    html: str,
    source: PhotographerSource,
    scraped_at: str | None = None,
) -> list[dict]:
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text("\n", strip=True))
    descriptions = [
        clean_text(meta.get("content"))
        for meta in soup.find_all("meta")
        if ascii_lower(meta.get("name") or meta.get("property")) in {"description", "og description", "og:description"}
    ]
    combined = clean_text(" ".join([text, *descriptions]))
    if "photo" not in ascii_lower(combined) and "fencingphotos" not in ascii_lower(combined):
        return []
    event_name = infer_event_name(soup, source)
    record = make_record(
        source=source,
        text=combined,
        scraped_at=scraped_at,
        soup=soup,
        title=source_title(soup),
        gallery=True,
        event_name=event_name,
    )
    return [record] if record else []


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_fetched_content(source: PhotographerSource, fetched: FetchedContent) -> list[dict]:
    content_type = fetched.content_type.lower()
    source = PhotographerSource(
        **{
            **source.__dict__,
            "url": fetched.final_url or source.url,
        }
    )
    if "pdf" in content_type or fetched.content.startswith(b"%PDF"):
        return parse_directory_text(extract_pdf_text(fetched.content), source)
    html = fetched.content.decode("utf-8", errors="replace")
    if source.source_kind in {"public_gallery", "event_gallery"}:
        return parse_gallery_html(html, source)
    return parse_directory_html(html, source)


def photographer_key(row: dict[str, Any]) -> str | None:
    label = normalize_name(row.get("business") or row.get("name"))
    if not label:
        return None
    domain = website_domain(row.get("website"))
    if domain:
        return f"{label}|web:{domain}"
    email = clean_text(row.get("email")).lower()
    if email:
        return f"{label}|email:{email}"
    public_contact = normalize_url(row.get("public_contact"))
    if public_contact:
        return f"{label}|contact:{public_contact}"
    return label


def prefer_value(existing: Any, incoming: Any) -> Any:
    return existing if clean_text(existing) else incoming


def dedupe_photographers(rows: Iterable[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        key = photographer_key(row)
        if not key:
            continue
        row["normalized_key"] = key
        row["regions"] = unique_values(row.get("regions") or [])
        row["event_urls"] = unique_values(row.get("event_urls") or [])
        row["metadata"] = dict(row.get("metadata") or {})
        if key not in deduped:
            deduped[key] = row
            continue

        existing = deduped[key]
        for field_name in ("name", "business", "website", "email", "public_contact", "source_url", "scraped_at"):
            existing[field_name] = prefer_value(existing.get(field_name), row.get(field_name))
        existing["regions"] = unique_values([*(existing.get("regions") or []), *(row.get("regions") or [])])
        existing["event_urls"] = unique_values([*(existing.get("event_urls") or []), *(row.get("event_urls") or [])])

        duplicate_url = row.get("source_url")
        if duplicate_url and duplicate_url != existing.get("source_url"):
            duplicate_urls = existing.setdefault("metadata", {}).setdefault("duplicate_source_urls", [])
            if duplicate_url not in duplicate_urls:
                duplicate_urls.append(duplicate_url)
        for meta_key, meta_value in (row.get("metadata") or {}).items():
            if meta_key not in existing["metadata"]:
                existing["metadata"][meta_key] = meta_value
    return list(deduped.values())


def link_photographers_to_tournaments(client, rows: list[dict]) -> list[dict]:
    if not client:
        return rows
    linked_rows = []
    for raw in rows:
        row = dict(raw)
        metadata = dict(row.get("metadata") or {})
        event_name = clean_text(metadata.get("event_name"))
        if len(event_name) < 6:
            linked_rows.append(row)
            continue
        try:
            result = (
                client.table("fs_tournaments")
                .select("id,source_id,name,metadata")
                .ilike("name", f"%{event_name}%")
                .limit(5)
                .execute()
            )
        except Exception as exc:
            metadata["tournament_link_error"] = str(exc)[:300]
            row["metadata"] = metadata
            linked_rows.append(row)
            continue

        matches = [
            {"id": item.get("id"), "source_id": item.get("source_id"), "name": item.get("name")}
            for item in (getattr(result, "data", None) or [])
            if item.get("id")
        ]
        if matches:
            row["tournament_ids"] = [item["id"] for item in matches]
            metadata["linked_tournaments"] = matches
            row["metadata"] = metadata
        linked_rows.append(row)
    return linked_rows


def upsert_photographer_rows(client, rows: list[dict]) -> int:
    if not rows:
        return 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table("fs_event_photographers").upsert(
            batch,
            on_conflict="normalized_key",
        ).execute()
    return len(rows)


def scrape_photographer_directory(
    *,
    client=None,
    sources: Iterable[PhotographerSource] | None = None,
    fetcher: Callable[[PhotographerSource], FetchedContent] = fetch_source,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
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
                rows = parse_fetched_content(source, fetched)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.url}: {exc}")
                continue
            if not rows:
                skipped += 1
            parsed_rows.extend(rows)

        rows = dedupe_photographers(parsed_rows)
        if client:
            rows = link_photographers_to_tournaments(client, rows)
        written = upsert_photographer_rows(client, rows) if client else 0
        summary = {
            "sources": len(sources),
            "parsed": len(parsed_rows),
            "deduped": len(rows),
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
    summary = scrape_photographer_directory()
    print(
        "event photographers: "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
