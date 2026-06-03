from __future__ import annotations

import html
import json
import os
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "scrape_sponsorships"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
FIE_BASE_URL = "https://fie.org/athletes"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
MAX_FENCERS = int(os.environ.get("SPONSORSHIP_FENCER_LIMIT", "1000"))
REQUEST_DELAY_SECONDS = float(os.environ.get("SPONSORSHIP_REQUEST_DELAY", "1.0"))
UPSERT_BATCH_SIZE = int(os.environ.get("SPONSORSHIP_UPSERT_BATCH_SIZE", "100"))

HEADERS = {
    "User-Agent": "FenceSpace/1.0 sponsorship scraper",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
}

SELECT_COLUMN_CANDIDATES = [
    "id,name,fie_id,country,bio_text,wikipedia_url,federation_profile_url,metadata",
    "id,name,fie_id,country,bio_text,metadata",
    "id,name,fie_id,country,metadata",
]

PROFILE_SOURCE_TYPES = {"official_athlete_page", "federation_profile"}
PUBLIC_SOURCE_TYPES = {
    "fencer_bio",
    "official_athlete_page",
    "federation_profile",
    "sponsor_page",
    "public_announcement",
}

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "Absolute Fencing": ("Absolute Fencing Gear", "Absolute Fencing", "AF"),
    "Allstar": ("Allstar", "Allstar Uhlmann"),
    "Airbnb": ("Airbnb", "AirBnB"),
    "Blue Gauntlet": ("Blue Gauntlet",),
    "Cash App": ("Cash App",),
    "Deloitte": ("Deloitte",),
    "FIGS": ("FIGS",),
    "Leon Paul": ("Leon Paul", "LP"),
    "Meta": ("Meta", "Facebook"),
    "Mercedes": ("Mercedes", "Mercedes-Benz"),
    "New Era Cap": ("New Era Cap", "New Era"),
    "Nike": ("Nike", "APS | Nike Fencing"),
    "PBT": ("PBT",),
    "Ralph Lauren": ("Ralph Lauren",),
    "Red Bull": ("Red Bull",),
    "Reformation": ("Reformation",),
    "Richard Mille": ("Richard Mille",),
    "Teeling Whiskey": ("Teeling Whiskey",),
    "Thorne": ("Thorne",),
    "Tinder": ("Tinder",),
    "Uhlmann": ("Uhlmann",),
}

BRAND_CATEGORIES = {
    "Absolute Fencing": "equipment",
    "Allstar": "equipment",
    "Blue Gauntlet": "equipment",
    "Leon Paul": "equipment",
    "Nike": "apparel",
    "PBT": "equipment",
    "Uhlmann": "equipment",
    "Red Bull": "beverage",
    "Thorne": "nutrition",
    "Teeling Whiskey": "beverage",
    "Ralph Lauren": "apparel",
    "New Era Cap": "apparel",
    "FIGS": "apparel",
    "Reformation": "apparel",
    "Richard Mille": "watch",
    "Cash App": "financial",
    "Deloitte": "professional_services",
    "Meta": "technology",
    "Mercedes": "automotive",
    "Airbnb": "travel",
    "Tinder": "technology",
}

EQUIPMENT_BRAND_LINKS = {
    "Absolute Fencing": "Absolute Fencing",
    "Allstar": "Allstar",
    "Blue Gauntlet": "Blue Gauntlet",
    "Leon Paul": "Leon Paul",
    "PBT": "PBT",
    "Uhlmann": "Uhlmann",
}

SHORT_ALIASES = {"AF", "LP"}

SPONSOR_SIGNAL_RE = re.compile(
    r"\b("
    r"sponsor(?:ed|ship|s)?|"
    r"partner(?:ed|s|ship)?|"
    r"ambassador(?:s|ship)?|"
    r"supported by|"
    r"backed by|"
    r"outfitted by|"
    r"official athlete|"
    r"welcomes?|"
    r"announc(?:ed|es|ing)"
    r")\b",
    re.IGNORECASE,
)
WEAK_OR_INFERRED_RE = re.compile(
    r"\b("
    r"may be|might be|could be|rumou?red|speculat(?:ed|ion)|"
    r"appeared|seen wearing|wore|wears|uses|used|social[- ]media|"
    r"instagram|tiktok|photo|picture|logo appears"
    r")\b",
    re.IGNORECASE,
)
PAST_DEAL_RE = re.compile(
    r"\b(past|previous|previously|former|formerly|expired|ended|until|through)\b",
    re.IGNORECASE,
)
PAGE_SPONSOR_RE = re.compile(
    r"\b(sponsors? and partners?|partners?|sponsors?|supported us|past work)\b",
    re.IGNORECASE,
)

_supabase = None


@dataclass(frozen=True)
class SponsorshipMention:
    sponsor_brand: str
    normalized_brand: str
    category: str
    source_type: str
    source_url: str
    evidence_text: str
    confidence: str
    status: str = "unknown"
    start_date: str | None = None
    end_date: str | None = None
    linked_equipment_brand: str | None = None
    metadata: dict[str, Any] | None = None


def get_supabase():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def clean_text(value: Any) -> str:
    raw = "" if value is None else str(value)
    raw = html.unescape(raw).replace("\xa0", " ")
    if "<" in raw and ">" in raw:
        soup = BeautifulSoup(raw, "html.parser")
        alt_texts = [
            tag.get("alt") or tag.get("title") or ""
            for tag in soup.find_all(["img", "meta"])
            if tag.get("alt") or tag.get("title")
        ]
        raw = " ".join([soup.get_text(" ", strip=True), *alt_texts])
    raw = unicodedata.normalize("NFKC", raw)
    return re.sub(r"\s+", " ", raw).strip()


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def compare_text(value: str) -> str:
    text = strip_accents(unicodedata.normalize("NFKC", value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_brand_key(brand: str) -> str:
    return compare_text(brand).replace(" ", "-")


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def name_in_text(text: str, fencer_name: str | None) -> bool:
    if not fencer_name:
        return True
    normalized_text = compare_text(text)
    normalized_name = compare_text(fencer_name)
    if not normalized_name:
        return True
    if normalized_name in normalized_text:
        return True
    parts = [part for part in normalized_name.split() if len(part) > 1]
    return len(parts) >= 2 and all(part in normalized_text for part in parts)


def sentence_window(text: str, position: int) -> str:
    start = max(text.rfind(mark, 0, position) for mark in ".!?\n")
    start = 0 if start < 0 else start + 1
    end_candidates = [idx for idx in (text.find(mark, position) for mark in ".!?\n") if idx >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end].strip()


def context_window(text: str, position: int, radius: int = 260) -> str:
    return text[max(0, position - radius) : min(len(text), position + radius)].strip()


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    flags = 0 if alias in SHORT_ALIASES else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", flags)


def iter_brand_hits(text: str) -> Iterable[tuple[str, str, re.Match[str]]]:
    aliases: list[tuple[str, str]] = []
    for brand, brand_aliases in BRAND_ALIASES.items():
        for alias in brand_aliases:
            aliases.append((brand, alias))
    aliases.sort(key=lambda item: len(item[1]), reverse=True)

    for brand, alias in aliases:
        for match in alias_pattern(alias).finditer(text):
            yield brand, alias, match


def date_from_year(year: str, *, end: bool = False) -> str:
    return f"{int(year):04d}-12-31" if end else f"{int(year):04d}-01-01"


def parse_public_dates(text: str) -> tuple[str | None, str | None]:
    year_range = re.search(
        r"\b(?:from\s+)?(?P<start>20\d{2}|19\d{2})\s*(?:to|-|through|until)\s*(?P<end>20\d{2}|19\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if year_range:
        return date_from_year(year_range.group("start")), date_from_year(year_range.group("end"), end=True)

    start_match = re.search(r"\b(?:since|from|starting)\s+(?P<start>20\d{2}|19\d{2})\b", text, flags=re.I)
    end_match = re.search(r"\b(?:until|through|ended in)\s+(?P<end>20\d{2}|19\d{2})\b", text, flags=re.I)
    start = date_from_year(start_match.group("start")) if start_match else None
    end = date_from_year(end_match.group("end"), end=True) if end_match else None
    return start, end


def status_for_evidence(text: str, end_date: str | None) -> str:
    if end_date:
        try:
            if date.fromisoformat(end_date) < date.today():
                return "expired"
        except ValueError:
            pass
    if PAST_DEAL_RE.search(text):
        return "expired"
    if re.search(r"\b(current|currently|new|announced|welcomes?|official)\b", text, flags=re.I):
        return "active"
    return "unknown"


def is_explicit_sponsorship_evidence(
    sentence: str,
    context: str,
    *,
    source_type: str,
    fencer_name: str | None,
) -> tuple[bool, str]:
    evidence = sentence or context
    if WEAK_OR_INFERRED_RE.search(evidence):
        return False, "weak_or_inferred"
    if SPONSOR_SIGNAL_RE.search(evidence) and name_in_text(context, fencer_name):
        return True, "sentence"
    if source_type == "sponsor_page" and PAGE_SPONSOR_RE.search(context) and name_in_text(context, fencer_name):
        return True, "page"
    if source_type in PROFILE_SOURCE_TYPES and SPONSOR_SIGNAL_RE.search(context) and name_in_text(context, fencer_name):
        return True, "profile"
    return False, "missing_explicit_signal"


def confidence_for_evidence(source_type: str, strength: str) -> str:
    if source_type in {"public_announcement", "official_athlete_page", "federation_profile"} and strength == "sentence":
        return "high"
    if source_type == "sponsor_page" and strength == "sentence":
        return "high"
    return "medium"


def mention_for_brand(
    *,
    brand: str,
    alias: str,
    evidence_text: str,
    source_type: str,
    source_url: str,
    confidence: str,
    metadata: dict[str, Any] | None = None,
) -> SponsorshipMention:
    start_date, end_date = parse_public_dates(evidence_text)
    status = status_for_evidence(evidence_text, end_date)
    linked_equipment_brand = EQUIPMENT_BRAND_LINKS.get(brand)
    mention_metadata = {
        "matched_alias": alias,
        "evidence_length": len(evidence_text),
    }
    if linked_equipment_brand:
        mention_metadata["related_tables"] = ["fs_fencer_equipment", "fs_equipment_reviews"]
    if metadata:
        mention_metadata.update(metadata)
    return SponsorshipMention(
        sponsor_brand=brand,
        normalized_brand=normalized_brand_key(brand),
        category=BRAND_CATEGORIES.get(brand, "other"),
        source_type=source_type,
        source_url=source_url,
        evidence_text=evidence_text[:600],
        confidence=confidence,
        status=status,
        start_date=start_date,
        end_date=end_date,
        linked_equipment_brand=linked_equipment_brand,
        metadata=mention_metadata,
    )


def extract_sponsorship_mentions(
    text: str,
    *,
    fencer_name: str | None,
    source_type: str,
    source_url: str,
) -> list[SponsorshipMention]:
    if source_type not in PUBLIC_SOURCE_TYPES and source_type != "social_media":
        return []

    cleaned = clean_text(text)
    if not cleaned:
        return []

    mentions: list[SponsorshipMention] = []
    seen: set[tuple[str, str]] = set()
    occupied_spans: list[tuple[int, int, str]] = []

    for brand, alias, match in iter_brand_hits(cleaned):
        if any(match.start() >= start and match.end() <= end and brand != existing for start, end, existing in occupied_spans):
            continue

        sentence = sentence_window(cleaned, match.start())
        context = context_window(cleaned, match.start())
        explicit, strength = is_explicit_sponsorship_evidence(
            sentence,
            context,
            source_type=source_type,
            fencer_name=fencer_name,
        )
        if not explicit:
            continue
        if alias in SHORT_ALIASES and strength != "sentence":
            continue

        evidence_text = sentence if strength == "sentence" and sentence else context
        key = (brand, source_url)
        if key in seen:
            continue
        seen.add(key)
        occupied_spans.append((match.start(), match.end(), brand))
        mentions.append(
            mention_for_brand(
                brand=brand,
                alias=alias,
                evidence_text=evidence_text,
                source_type=source_type,
                source_url=source_url,
                confidence=confidence_for_evidence(source_type, strength),
                metadata={
                    "fencer_name": fencer_name,
                    "evidence_strength": strength,
                },
            )
        )

    return mentions


def wikidata_time_to_date(value: Any, *, end: bool = False) -> str | None:
    if not isinstance(value, dict):
        return None
    time_value = value.get("time")
    if not isinstance(time_value, str) or len(time_value) < 5:
        return None
    match = re.match(r"^[+-](?P<year>\d{4})(?:-(?P<month>\d{2}))?(?:-(?P<day>\d{2}))?", time_value)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month") or ("12" if end else "01"))
    day = int(match.group("day") or ("31" if end else "01"))
    if month == 0:
        month = 12 if end else 1
    if day == 0:
        day = 31 if end else 1
    return date(year, month, day).isoformat()


def qualifier_date(claim: dict[str, Any], property_id: str, *, end: bool = False) -> str | None:
    qualifiers = claim.get("qualifiers")
    if not isinstance(qualifiers, dict):
        return None
    values = qualifiers.get(property_id)
    if not isinstance(values, list) or not values:
        return None
    return wikidata_time_to_date(values[0].get("datavalue", {}).get("value"), end=end)


def extract_wikidata_sponsorships(
    payload: dict[str, Any],
    *,
    entity_id: str,
    sponsor_labels: dict[str, str] | None = None,
    source_url: str,
) -> list[SponsorshipMention]:
    sponsor_labels = sponsor_labels or {}
    entity = payload.get("entities", {}).get(entity_id, {})
    claims = entity.get("claims", {}).get("P859", [])
    mentions: list[SponsorshipMention] = []
    seen: set[str] = set()

    for claim in claims:
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict):
            continue
        sponsor_id = value.get("id")
        if not sponsor_id and value.get("numeric-id"):
            sponsor_id = f"Q{value['numeric-id']}"
        if not sponsor_id or sponsor_id in seen:
            continue
        seen.add(sponsor_id)

        brand = sponsor_labels.get(sponsor_id, sponsor_id)
        canonical = canonical_brand_name(brand)
        start_date = qualifier_date(claim, "P580")
        end_date = qualifier_date(claim, "P582", end=True)
        evidence_text = f"Wikidata sponsor claim P859: {canonical}"
        mention = mention_for_brand(
            brand=canonical,
            alias=brand,
            evidence_text=evidence_text,
            source_type="wikidata",
            source_url=source_url,
            confidence="medium",
            metadata={"wikidata_sponsor_id": sponsor_id},
        )
        mentions.append(
            SponsorshipMention(
                sponsor_brand=mention.sponsor_brand,
                normalized_brand=mention.normalized_brand,
                category=mention.category,
                source_type=mention.source_type,
                source_url=mention.source_url,
                evidence_text=mention.evidence_text,
                confidence=mention.confidence,
                status=status_for_evidence(evidence_text, end_date),
                start_date=start_date,
                end_date=end_date,
                linked_equipment_brand=mention.linked_equipment_brand,
                metadata=mention.metadata,
            )
        )
    return mentions


def canonical_brand_name(value: str) -> str:
    normalized = compare_text(value)
    for brand, aliases in BRAND_ALIASES.items():
        if normalized == compare_text(brand) or any(normalized == compare_text(alias) for alias in aliases):
            return brand
    return clean_text(value)


def deterministic_sponsorship_id(
    fencer_key: str,
    normalized_brand: str,
    source_url: str,
    source_type: str,
) -> str:
    raw_key = "|".join([fencer_key, normalized_brand, source_url, source_type])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace:sponsorship:{raw_key}"))


def fencer_identity_key(fencer: dict[str, Any]) -> str:
    for key in ("id", "fie_id", "name"):
        value = clean_text(fencer.get(key))
        if value:
            return f"{key}:{value}"
    return "unknown"


def build_sponsorship_rows(
    fencer: dict[str, Any],
    mentions: list[SponsorshipMention],
    *,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    fencer_name = clean_text(fencer.get("name"))
    if not fencer_name:
        return []
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    fencer_key = fencer_identity_key(fencer)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for mention in mentions:
        key = (mention.normalized_brand, mention.source_url, mention.source_type)
        if key in seen:
            continue
        seen.add(key)
        row = {
            "id": deterministic_sponsorship_id(
                fencer_key,
                mention.normalized_brand,
                mention.source_url,
                mention.source_type,
            ),
            "fencer_id": fencer.get("id"),
            "fencer_name": fencer_name,
            "fie_id": clean_text(fencer.get("fie_id")) or None,
            "country": clean_text(fencer.get("country")) or None,
            "sponsor_brand": mention.sponsor_brand,
            "normalized_brand": mention.normalized_brand,
            "category": mention.category,
            "start_date": mention.start_date,
            "end_date": mention.end_date,
            "status": mention.status,
            "evidence_text": mention.evidence_text,
            "source_url": mention.source_url,
            "source_type": mention.source_type,
            "linked_equipment_brand": mention.linked_equipment_brand,
            "confidence": mention.confidence,
            "metadata": dict(mention.metadata or {}),
            "scraped_at": scraped_at,
            "updated_at": scraped_at,
        }
        rows.append({key: value for key, value in row.items() if value is not None})
    return rows


def fetch_url(session: requests.Session, url: str) -> str | None:
    try:
        response = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"  Sponsorship fetch failed for {url}: {exc}")
        return None
    if response.status_code != 200:
        print(f"  Sponsorship HTTP {response.status_code} for {url}")
        return None
    return response.text


def load_fencers(client, limit: int = MAX_FENCERS) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in SELECT_COLUMN_CANDIDATES:
        try:
            return client.table("fs_fencers").select(columns).limit(limit).execute().data or []
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def iter_url_values(value: Any) -> Iterable[str]:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_url_values(item)


def metadata_urls(row: dict[str, Any], keys: Iterable[str]) -> list[str]:
    metadata = metadata_dict(row)
    urls: list[str] = []
    for key in keys:
        urls.extend(iter_url_values(row.get(key)))
        urls.extend(iter_url_values(metadata.get(key)))
    return sorted(set(urls))


def wikipedia_source_url(row: dict[str, Any]) -> str | None:
    metadata = metadata_dict(row)
    for source in (row, metadata):
        value = source.get("wikipedia_url") or source.get("wiki_url")
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def wikidata_id_for_fencer(row: dict[str, Any]) -> str | None:
    metadata = metadata_dict(row)
    for source in (row, metadata):
        value = source.get("wikidata_id") or source.get("wikidata")
        if isinstance(value, str) and re.fullmatch(r"Q\d+", value):
            return value
    return None


def source_texts_for_fencer(
    fencer: dict[str, Any],
    session: requests.Session,
    *,
    fetch_fie: bool = True,
    fetch_external: bool = True,
) -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    bio_text = clean_text(fencer.get("bio_text") or metadata_dict(fencer).get("bio_text"))
    wiki_url = wikipedia_source_url(fencer)
    if bio_text and wiki_url:
        sources.append(("fencer_bio", wiki_url, bio_text))

    fie_id = clean_text(fencer.get("fie_id"))
    if fetch_fie and fie_id:
        url = f"{FIE_BASE_URL}/{fie_id}"
        text = fetch_url(session, url)
        if text:
            sources.append(("official_athlete_page", url, text))

    if not fetch_external:
        return sources

    for url in metadata_urls(
        fencer,
        [
            "federation_profile_url",
            "national_federation_profile_url",
            "federation_url",
            "profile_url",
            "federation_profile_urls",
            "profile_urls",
        ],
    ):
        text = fetch_url(session, url)
        if text:
            sources.append(("federation_profile", url, text))

    for url in metadata_urls(fencer, ["sponsor_page", "sponsor_pages", "sponsor_profile_url", "sponsor_profile_urls"]):
        text = fetch_url(session, url)
        if text:
            sources.append(("sponsor_page", url, text))

    for url in metadata_urls(
        fencer,
        ["sponsorship_url", "sponsorship_urls", "announcement_url", "announcement_urls", "public_announcement_urls"],
    ):
        text = fetch_url(session, url)
        if text:
            sources.append(("public_announcement", url, text))

    return sources


def fetch_wikidata_sponsor_claims(session: requests.Session, entity_id: str) -> list[SponsorshipMention]:
    source_url = f"https://www.wikidata.org/wiki/{entity_id}"
    entity_url = WIKIDATA_ENTITY_URL.format(entity_id=entity_id)
    try:
        response = session.get(entity_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"  Wikidata sponsorship fetch failed for {entity_id}: {exc}")
        return []

    sponsor_ids: set[str] = set()
    entity = payload.get("entities", {}).get(entity_id, {})
    for claim in entity.get("claims", {}).get("P859", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict):
            sponsor_id = value.get("id") or (f"Q{value['numeric-id']}" if value.get("numeric-id") else None)
            if sponsor_id:
                sponsor_ids.add(sponsor_id)

    labels: dict[str, str] = {}
    if sponsor_ids:
        try:
            label_response = session.get(
                WIKIDATA_API_URL,
                headers=HEADERS,
                params={
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(sorted(sponsor_ids)),
                    "props": "labels",
                    "languages": "en",
                },
                timeout=20,
            )
            label_response.raise_for_status()
            label_payload = label_response.json()
            for sponsor_id, item in label_payload.get("entities", {}).items():
                label = item.get("labels", {}).get("en", {}).get("value")
                if label:
                    labels[sponsor_id] = label
        except Exception as exc:
            print(f"  Wikidata sponsor label fetch failed for {entity_id}: {exc}")

    return extract_wikidata_sponsorships(
        payload,
        entity_id=entity_id,
        sponsor_labels=labels,
        source_url=source_url,
    )


def scrape_fencer_sponsorships(
    fencers: list[dict[str, Any]],
    session: requests.Session,
    *,
    fetch_fie: bool = True,
    fetch_external: bool = True,
    fetch_wikidata: bool = True,
    sleeper=time.sleep,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0

    for fencer in fencers:
        fencer_name = clean_text(fencer.get("name"))
        if not fencer_name:
            skipped += 1
            continue

        mentions: list[SponsorshipMention] = []
        for source_type, source_url, text in source_texts_for_fencer(
            fencer,
            session,
            fetch_fie=fetch_fie,
            fetch_external=fetch_external,
        ):
            mentions.extend(
                extract_sponsorship_mentions(
                    text,
                    fencer_name=fencer_name,
                    source_type=source_type,
                    source_url=source_url,
                )
            )

        wikidata_id = wikidata_id_for_fencer(fencer)
        if fetch_wikidata and wikidata_id:
            mentions.extend(fetch_wikidata_sponsor_claims(session, wikidata_id))

        source_rows = build_sponsorship_rows(fencer, mentions)
        if source_rows:
            rows.extend(source_rows)
        else:
            skipped += 1
        sleeper(REQUEST_DELAY_SECONDS)

    return rows, skipped


def upsert_sponsorship_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_sponsorships").upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Sponsorship upsert batch {index // batch_size} failed: {exc}")
            for row in batch:
                try:
                    client.table("fs_sponsorships").upsert([row], on_conflict="id").execute()
                    written += 1
                except Exception as row_exc:
                    failed += 1
                    print(f"    Sponsorship upsert failed for {row.get('id')}: {row_exc}")
    return written, failed


def run(
    client=None,
    session: requests.Session | None = None,
    *,
    limit: int = MAX_FENCERS,
    fetch_fie: bool = True,
    fetch_external: bool = True,
    fetch_wikidata: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase()
    session = session or requests.Session()
    session.headers.update(HEADERS)
    run_log = ScraperRunLogger(SOURCE).start()

    try:
        previous_state = get_state(SOURCE, "last_run")
        fencers = load_fencers(client, limit=limit)
        rows, skipped = scrape_fencer_sponsorships(
            fencers,
            session,
            fetch_fie=fetch_fie,
            fetch_external=fetch_external,
            fetch_wikidata=fetch_wikidata,
        )
        written, failed = upsert_sponsorship_rows(client, rows) if rows else (0, 0)
        summary = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "previous_run": previous_state,
            "fencers_scanned": len(fencers),
            "sponsorship_rows_found": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main() -> None:
    summary = run()
    print(
        "Sponsorship scrape complete: scanned={fencers_scanned}, found={sponsorship_rows_found}, "
        "written={written}, failed={failed}, skipped={skipped}".format(**summary)
    )


if __name__ == "__main__":
    main()
