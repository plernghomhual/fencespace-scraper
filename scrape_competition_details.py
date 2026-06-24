import io
import json
import os
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FIE_BASE = "https://fie.org"
SOURCE = "scrape_competition_details"
PAGE_SIZE = 1000
REQUEST_DELAY = float(os.environ.get("COMPETITION_DETAILS_DELAY", "0.3"))
DEFAULT_LIMIT = int(os.environ.get("COMPETITION_DETAILS_LIMIT", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fie.org/competitions",
}

MONEY_RE = re.compile(
    r"(?:(?P<code_before>EUR|USD|GBP|CHF|JPY|CAD|AUD|CNY|RMB)\s*)?"
    r"(?P<symbol>[€$£¥])?\s*"
    r"(?P<amount>\d[\d ,.]*\d|\d)"
    r"\s*(?P<code_after>EUR|USD|GBP|CHF|JPY|CAD|AUD|CNY|RMB)?",
    re.IGNORECASE,
)

SYMBOL_CURRENCY = {"€": "EUR", "$": "USD", "£": "GBP", "¥": "JPY"}

TOURNAMENT_DETAIL_COLUMNS = (
    "organizer",
    "entry_deadline",
    "format",
    "quota",
    "venue_details",
    "registration_url",
    "live_results_url",
)

PLACEHOLDER_VALUES = {
    "-",
    "n/a",
    "na",
    "none",
    "not set",
    "not available",
    "tba",
    "tbd",
    "to be determined",
}

DETAIL_LABEL_ALIASES = {
    "organizer": (
        "organizer",
        "organiser",
        "organizing federation",
        "organising federation",
        "host federation",
        "host organiser",
        "host organizer",
    ),
    "entry_deadline": (
        "entry deadline",
        "entries deadline",
        "deadline for entries",
        "entry closing date",
        "entries closing date",
        "registration deadline",
        "registration closing date",
        "closing date",
    ),
    "venue": (
        "venue",
        "competition venue",
        "competition venue address",
        "venue address",
        "address",
    ),
    "format": (
        "formula",
        "competition formula",
        "competition format",
        "format",
    ),
    "quota": (
        "quota",
        "participation quota",
        "entry quota",
        "entries quota",
        "maximum entries",
        "maximum number of entries",
        "competition format",
    ),
    "location": ("location", "city"),
    "country": ("country",),
}

ALL_DETAIL_LABELS = tuple(alias for aliases in DETAIL_LABEL_ALIASES.values() for alias in aliases)


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


def meaningful_text(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.casefold() in PLACEHOLDER_VALUES:
        return None
    return text


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def normalize_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip().casefold()
    text = text.rstrip(":")
    return text


def line_matches_label(line: str, aliases: tuple[str, ...] = ALL_DETAIL_LABELS) -> bool:
    normalized = normalize_label(line)
    before_colon = normalize_label(line.split(":", 1)[0]) if ":" in line else normalized
    return before_colon in aliases or normalized in aliases


def split_labeled_value(line: str, aliases: tuple[str, ...]) -> tuple[str, str | None] | None:
    text = clean_text(line) or ""
    normalized = normalize_label(text)
    for alias in aliases:
        if normalized == alias:
            return alias, None
        pattern = re.compile(rf"^{re.escape(alias)}\s*[:\-–]\s*(.+)$", re.IGNORECASE)
        match = pattern.match(text)
        if match:
            return alias, clean_text(match.group(1))
    return None


def text_lines_from_html(html: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return [line for line in (clean_text(part) for part in re.split(r"[\r\n]+", html or "")) if line]

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return [line for line in (clean_text(part) for part in soup.get_text("\n").splitlines()) if line]


def text_lines_from_documents(document_texts: list[str] | None) -> list[str]:
    lines: list[str] = []
    for text in document_texts or []:
        lines.extend(line for line in (clean_text(part) for part in str(text).splitlines()) if line)
    return lines


def first_labeled_value(lines: list[str], aliases: tuple[str, ...]) -> tuple[str | None, str | None]:
    for index, line in enumerate(lines):
        split = split_labeled_value(line, aliases)
        if not split:
            continue
        _alias, inline_value = split
        if inline_value is not None:
            return meaningful_text(inline_value), line
        for next_line in lines[index + 1 : index + 5]:
            if line_matches_label(next_line):
                break
            return meaningful_text(next_line), f"{line}: {next_line}"
    return None, None


def _get_dict(d: dict[str, Any], key: str) -> dict[str, Any]:
    val = d.get(key)
    return val if isinstance(val, dict) else {}


def labeled_block_value(
    lines: list[str],
    aliases: tuple[str, ...],
    max_lines: int = 3,
) -> tuple[str | None, str | None]:
    for index, line in enumerate(lines):
        split = split_labeled_value(line, aliases)
        if not split:
            continue
        _alias, inline_value = split
        values: list[str] = []
        if meaningful_text(inline_value):
            values.append(meaningful_text(inline_value) or "")
        for next_line in lines[index + 1 : index + 1 + max_lines]:
            if line_matches_label(next_line):
                break
            value = meaningful_text(next_line)
            if value:
                values.append(value)
        if values:
            result = ", ".join(dict.fromkeys(values))
            return result, f"{line}: {result}"
    return None, None


def normalize_detail_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    patterns = (
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b",
    )
    candidate = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(0)
            break
    if candidate is None:
        return None

    iso_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", candidate)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            return None

    numeric_match = re.fullmatch(r"(\d{1,2})([./-])(\d{1,2})\2(\d{4})", candidate)
    if numeric_match:
        first, separator, second, year_str = numeric_match.groups()
        first_int = int(first)
        second_int = int(second)
        if separator == "/" and first_int <= 12 and second_int <= 12:
            return None
        day, month = first_int, second_int
        if separator == "/" and second_int > 12:
            month, day = first_int, second_int
        try:
            return datetime(int(year_str), month, day).date().isoformat()
        except ValueError:
            return None

    normalized = candidate.replace(",", "")
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_quota(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    lower = text.casefold()
    if any(token in lower for token in ("no quota", "unlimited", "not limited", "as per fie rules")):
        return None
    if not any(
        token in lower
        for token in (
            "quota",
            "maximum",
            "limited",
            "entries",
            "fencers",
            "participants",
            "competition format",
        )
    ):
        return None

    without_dates = re.sub(r"\b\d{4}-\d{1,2}-\d{1,2}\b", " ", text)
    without_dates = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b", " ", without_dates)
    for match in re.finditer(r"\b\d{1,4}\b", without_dates):
        number = int(match.group(0))
        if number > 0:
            return number
    return None


def normalize_format_text(value: Any) -> str | None:
    text = meaningful_text(value)
    if not text:
        return None
    text = re.sub(r"^\d+\s*(?:fencers|entries|participants)\s*[:\-–]?\s*", "", text, flags=re.IGNORECASE)
    text = clean_text(text)
    if not text:
        return None
    lower = text.casefold()
    if any(token in lower for token in ("pool", "direct", "elimination", "tableau", "round", "formula")):
        return text
    return None


def extract_window_var(html: str, var_name: str) -> Any:
    """Extract a JSON window variable from FIE HTML."""
    match = re.search(rf"window\.{re.escape(var_name)}\s*=\s*", html)
    if not match:
        return None
    offset = match.end()
    while offset < len(html) and html[offset].isspace():
        offset += 1
    if offset >= len(html) or html[offset] not in "[{":
        return None
    try:
        result, _ = json.JSONDecoder().raw_decode(html[offset:])
        return result
    except json.JSONDecodeError:
        return None


def extract_window_blocks(html: str) -> dict[str, Any]:
    names = {
        "_competition",
        "_athletes",
        "_pools",
        "_poolsResults",
        "_tableau",
        "_downloadLinks",
    }
    return {name: extract_window_var(html, name) for name in names}


def parse_number(value: str) -> float | None:
    text = re.sub(r"[^\d,.\-]", "", value or "").strip(".,")
    if not text or text == "-":
        return None
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_currency(code_before: str | None, symbol: str | None, code_after: str | None) -> str | None:
    code = code_before or code_after
    if code:
        code = code.upper()
        return "CNY" if code == "RMB" else code
    return SYMBOL_CURRENCY.get(symbol or "")


def money_values(text: str) -> list[tuple[str | None, float]]:
    values: list[tuple[str | None, float]] = []
    for match in MONEY_RE.finditer(text or ""):
        amount = parse_number(match.group("amount"))
        if amount is None:
            continue
        currency = normalize_currency(
            match.group("code_before"),
            match.group("symbol"),
            match.group("code_after"),
        )
        if currency is None and amount < 10:
            continue
        values.append((currency, amount))
    return values


def first_currency(*groups: list[tuple[str | None, float]]) -> str | None:
    for group in groups:
        for currency, _amount in group:
            if currency:
                return currency
    return None


def extract_entry_fee(text: str, competition_type: str | None = None) -> tuple[str | None, float | None]:
    lines = [line.strip() for line in (text or "").splitlines()]
    candidates: list[tuple[str | None, float, int]] = []
    target = (competition_type or "").casefold()

    for line in lines:
        lower = line.casefold()
        if "prize" in lower:
            continue
        if not (
            "entry fee" in lower
            or "entry fees" in lower
            or "registration fee" in lower
            or "individual competition" in lower
            or "team competition" in lower
        ):
            continue
        amounts = money_values(line)
        for currency, amount in amounts:
            priority = 2
            if "individual" in target and "individual competition" in lower:
                priority = 0
            elif "team" in target and "team competition" in lower:
                priority = 0
            elif "entry" in lower or "registration" in lower:
                priority = 1
            candidates.append((currency, amount, priority))

    if not candidates:
        return None, None

    currency, amount, _priority = sorted(candidates, key=lambda item: (item[2], item[1]))[0]
    return currency, amount


def prize_text_blocks(text: str) -> list[str]:
    lines = [line.strip() for line in (text or "").splitlines()]
    blocks: list[str] = []
    stop_re = re.compile(
        r"\b(entry|registration|bank|account|accommodation|hotel|visa|schedule|weapon control|organizer|venue)\b",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):
        if not re.search(r"\b(prize|prizes|award money|prize money)\b", line, re.IGNORECASE):
            continue
        block = [line]
        for next_line in lines[index + 1 : index + 12]:
            if not next_line:
                if len(block) > 1:
                    break
                continue
            if stop_re.search(next_line):
                break
            block.append(next_line)
        blocks.append("\n".join(block))
    return blocks


def extract_prize_pool(text: str) -> tuple[str | None, float | None, list[float]]:
    amounts: list[tuple[str | None, float]] = []
    for block in prize_text_blocks(text):
        amounts.extend(money_values(block))
    if not amounts:
        return None, None, []
    currency = first_currency(amounts)
    values = [amount for _currency, amount in amounts]
    return currency, sum(values), values


def extract_money_from_documents(
    document_texts: list[str] | None,
    competition_type: str | None = None,
) -> tuple[str | None, float | None, float | None, dict[str, Any]]:
    combined = "\n".join(text for text in (document_texts or []) if text)
    entry_currency, entry_fee = extract_entry_fee(combined, competition_type)
    prize_currency, prize_pool, prize_amounts = extract_prize_pool(combined)
    currency = prize_currency or entry_currency
    metadata = {
        "prize_amounts": prize_amounts,
    }
    return currency, entry_fee, prize_pool, metadata


def pool_rows(pool: dict[str, Any]) -> list[Any]:
    for key in ("rows", "fencers", "athletes"):
        rows = pool.get(key)
        if isinstance(rows, list):
            return rows
    return []


def extract_pools(pools_block: Any) -> list[dict[str, Any]]:
    if isinstance(pools_block, dict):
        pools = pools_block.get("pools")
    else:
        pools = pools_block
    if not isinstance(pools, list):
        return []
    return [pool for pool in pools if isinstance(pool, dict)]


def infer_pool_size(pool_sizes: list[int]) -> int | None:
    usable = [size for size in pool_sizes if size > 0]
    if not usable:
        return None
    counts = Counter(usable)
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def round_sort_key(name: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", name)
    number = int(match.group(1)) if match else 0
    return (-number, name)


def extract_de_rounds(tableau_block: Any) -> list[str]:
    round_names: set[str] = set()
    suites = tableau_block if isinstance(tableau_block, list) else [tableau_block]
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        rounds = suite.get("rounds")
        if isinstance(rounds, dict):
            round_names.update(str(name) for name in rounds.keys())
    return sorted(round_names, key=round_sort_key)


def athlete_country(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    fencer = _get_dict(entry, "fencer")
    return clean_text(
        entry.get("nationality")
        or entry.get("country")
        or fencer.get("nationality")
        or fencer.get("country")
    )


def count_countries(athletes_block: Any) -> int | None:
    if not isinstance(athletes_block, list) or not athletes_block:
        return None
    countries = {country for country in (athlete_country(entry) for entry in athletes_block) if country}
    return len(countries) or None


def extract_participant_count(competition: dict[str, Any], athletes_block: Any) -> int | None:
    for key in ("fencerCount", "teamCount", "athleteCount", "participantCount"):
        count = coerce_int(competition.get(key))
        if count is not None:
            return count
    if isinstance(athletes_block, list) and athletes_block:
        return len(athletes_block)
    return None


def infer_format_type(competition: dict[str, Any], pool_count: int, round_names: list[str]) -> str | None:
    for key in ("format", "formula", "competitionFormula"):
        value = clean_text(competition.get(key))
        if value:
            return value
    has_pools = pool_count > 0
    has_de = bool(round_names)
    if has_pools and has_de:
        return "pools + direct elimination"
    if has_pools:
        return "pools"
    if has_de:
        return "direct elimination"
    return None


def make_absolute_url(url: str) -> str:
    return urljoin(FIE_BASE, url)


def extract_html_links(html: str) -> dict[str, Any]:
    links: dict[str, Any] = {
        "registration_url": None,
        "live_results_url": None,
        "document_urls": [],
        "raw": {},
    }
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return links

    soup = BeautifulSoup(html or "", "html.parser")
    document_urls: list[str] = []
    for anchor in soup.find_all("a"):
        href = clean_text(anchor.get("href"))
        if not href:
            continue
        url = make_absolute_url(href)
        label = clean_text(
            " ".join(
                part
                for part in (
                    anchor.get_text(" "),
                    anchor.get("title"),
                    anchor.get("aria-label"),
                    anchor.get("data-original-title"),
                )
                if part
            )
        ) or href
        label_lower = label.casefold()
        href_lower = href.casefold()

        if links["live_results_url"] is None and (
            "live result" in label_lower
            or "live-result" in href_lower
            or "fencingtimelive" in href_lower
        ):
            links["live_results_url"] = url
            links["raw"]["live_results_url"] = label

        if links["registration_url"] is None and any(
            token in label_lower for token in ("entries", "entry list", "registration", "register")
        ):
            links["registration_url"] = url
            links["raw"]["registration_url"] = label

        if any(
            token in label_lower or token in href_lower
            for token in ("invitation", "regulation", "program", "manual", "document")
        ):
            if url.lower().split("?", 1)[0].endswith(".pdf") or "static.fie.org" in url.casefold():
                document_urls.append(url)

    links["document_urls"] = list(dict.fromkeys(document_urls))
    return links


def extract_competition_link_fields(competition: dict[str, Any]) -> tuple[dict[str, str | None], dict[str, str]]:
    fields: dict[str, str | None] = {"registration_url": None, "live_results_url": None}
    raw: dict[str, str] = {}
    for key, value in competition.items():
        if not isinstance(value, str) or not value.strip():
            continue
        key_lower = key.casefold()
        url = make_absolute_url(value.strip())
        if fields["registration_url"] is None and any(
            token in key_lower for token in ("registration", "entryurl", "entriesurl", "inscription")
        ):
            fields["registration_url"] = url
            raw["registration_url"] = f"{key}: {value}"
        if fields["live_results_url"] is None and any(
            token in key_lower for token in ("liveresult", "live_result", "livetiming", "liveurl")
        ):
            fields["live_results_url"] = url
            raw["live_results_url"] = f"{key}: {value}"
    return fields, raw


def extract_document_urls(blocks: dict[str, Any]) -> list[str]:
    competition = _get_dict(blocks, "_competition")
    download_links = _get_dict(blocks, "_downloadLinks")
    urls: list[str] = []
    for source in (competition, download_links):
        for key, value in source.items():
            if not isinstance(value, str) or not value.strip():
                continue
            key_lower = key.casefold()
            if not (
                "invitation" in key_lower
                or "regulation" in key_lower
                or "program" in key_lower
                or "document" in key_lower
                or "manual" in key_lower
            ):
                continue
            url = make_absolute_url(value.strip())
            if url.lower().split("?", 1)[0].endswith(".pdf") or "static.fie.org" in url:
                urls.append(url)
    return list(dict.fromkeys(urls))


def competition_value(competition: dict[str, Any], *keys: str) -> str | None:
    wanted = {key.casefold() for key in keys}
    for key, value in competition.items():
        if key.casefold() in wanted:
            result = meaningful_text(value)
            if result:
                return result
    return None


def extract_rendered_detail_fields(html: str, competition: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    lines = text_lines_from_html(html)
    fields: dict[str, Any] = {
        "organizer": None,
        "entry_deadline": None,
        "format": None,
        "quota": None,
        "venue_details": None,
        "registration_url": None,
        "live_results_url": None,
    }
    raw: dict[str, str] = {}

    organizer, organizer_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["organizer"])
    fields["organizer"] = organizer or competition_value(
        competition,
        "organizer",
        "organiser",
        "hostFederation",
        "organizingFederation",
    )
    if organizer_raw:
        raw["organizer"] = organizer_raw

    deadline_raw_value, deadline_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["entry_deadline"])
    fields["entry_deadline"] = normalize_detail_date(
        deadline_raw_value
        or competition_value(competition, "entryDeadline", "registrationDeadline", "inscriptionDeadline")
    )
    if deadline_raw:
        raw["entry_deadline"] = deadline_raw

    format_value, format_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["format"])
    fields["format"] = normalize_format_text(
        format_value or competition_value(competition, "format", "formula", "competitionFormula")
    )
    if format_raw:
        raw["format"] = format_raw

    quota_value, quota_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["quota"])
    fields["quota"] = normalize_quota(
        quota_value
        or competition_value(competition, "quota", "entryQuota", "maxEntries", "maximumEntries")
        or format_value
    )
    if quota_raw:
        raw["quota"] = quota_raw

    venue_value, venue_raw = labeled_block_value(lines, DETAIL_LABEL_ALIASES["venue"], max_lines=3)
    location, location_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["location"])
    country, country_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["country"])
    if not location:
        location = competition_value(competition, "location", "city")
    if not country:
        country = competition_value(competition, "country")
    venue_parts = [part for part in (meaningful_text(venue_value), meaningful_text(location), meaningful_text(country)) if part]
    fields["venue_details"] = ", ".join(dict.fromkeys(venue_parts)) or None
    if venue_raw:
        raw["venue_details"] = venue_raw
    elif location_raw or country_raw:
        raw["venue_details"] = " | ".join(part for part in (location_raw, country_raw) if part)

    html_links = extract_html_links(html)
    link_fields, link_raw = extract_competition_link_fields(competition)
    fields["registration_url"] = html_links.get("registration_url") or link_fields.get("registration_url")
    fields["live_results_url"] = html_links.get("live_results_url") or link_fields.get("live_results_url")
    raw.update(link_raw)
    raw.update(html_links.get("raw") or {})
    return fields, raw


def extract_document_detail_fields(document_texts: list[str] | None) -> tuple[dict[str, Any], dict[str, str]]:
    lines = text_lines_from_documents(document_texts)
    fields: dict[str, Any] = {
        "organizer": None,
        "entry_deadline": None,
        "format": None,
        "quota": None,
        "venue_details": None,
        "registration_url": None,
        "live_results_url": None,
    }
    raw: dict[str, str] = {}
    if not lines:
        return fields, raw

    organizer, organizer_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["organizer"])
    fields["organizer"] = organizer
    if organizer_raw:
        raw["organizer"] = organizer_raw

    deadline_value, deadline_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["entry_deadline"])
    fields["entry_deadline"] = normalize_detail_date(deadline_value or deadline_raw)
    if deadline_raw:
        raw["entry_deadline"] = deadline_raw

    format_value, format_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["format"])
    fields["format"] = normalize_format_text(format_value)
    if format_raw:
        raw["format"] = format_raw

    quota_value, quota_raw = first_labeled_value(lines, DETAIL_LABEL_ALIASES["quota"])
    fields["quota"] = normalize_quota(quota_value or quota_raw or format_value)
    if quota_raw:
        raw["quota"] = quota_raw

    venue_value, venue_raw = labeled_block_value(lines, DETAIL_LABEL_ALIASES["venue"], max_lines=3)
    fields["venue_details"] = meaningful_text(venue_value)
    if venue_raw:
        raw["venue_details"] = venue_raw
    return fields, raw


def merge_detail_fields(
    rendered_fields: dict[str, Any],
    rendered_raw: dict[str, str],
    document_fields: dict[str, Any],
    document_raw: dict[str, str],
    fallback_format: str | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    fields: dict[str, Any] = {}
    raw: dict[str, str] = {}
    for key in TOURNAMENT_DETAIL_COLUMNS:
        value = document_fields.get(key) or rendered_fields.get(key)
        if key == "format" and value is None:
            value = fallback_format
        fields[key] = value
        if key in document_raw:
            raw[key] = document_raw[key]
        elif key in rendered_raw:
            raw[key] = rendered_raw[key]
    return fields, raw


def extract_detail_fields(
    html: str,
    blocks: dict[str, Any],
    document_texts: list[str] | None,
    fallback_format: str | None,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    competition = _get_dict(blocks, "_competition")
    rendered_fields, rendered_raw = extract_rendered_detail_fields(html, competition)
    document_fields, document_raw = extract_document_detail_fields(document_texts)
    fields, raw = merge_detail_fields(rendered_fields, rendered_raw, document_fields, document_raw, fallback_format)
    html_document_urls = extract_html_links(html).get("document_urls") or []
    return fields, raw, html_document_urls


def build_tournament_update(detail_row: dict[str, Any]) -> dict[str, Any]:
    metadata = _get_dict(detail_row, "metadata")
    fields = _get_dict(metadata, "detail_fields")
    update = {
        column: fields.get(column)
        for column in TOURNAMENT_DETAIL_COLUMNS
        if meaningful_text(fields.get(column)) is not None or isinstance(fields.get(column), int)
    }
    if update and metadata.get("source_url"):
        update["detail_source"] = metadata["source_url"]
    return update


def parse_competition_detail_page(
    html: str,
    tournament_id: str | None = None,
    source_url: str | None = None,
    document_texts: list[str] | None = None,
) -> dict[str, Any]:
    blocks = extract_window_blocks(html)
    competition = _get_dict(blocks, "_competition")
    athletes = blocks.get("_athletes")
    pools = extract_pools(blocks.get("_pools"))
    pool_sizes = [len(pool_rows(pool)) for pool in pools if pool_rows(pool)]
    round_names = extract_de_rounds(blocks.get("_tableau"))
    format_type = infer_format_type(competition, len(pools), round_names)
    detail_fields, detail_fields_raw, html_document_urls = extract_detail_fields(
        html,
        blocks,
        document_texts,
        fallback_format=format_type,
    )
    document_urls = list(dict.fromkeys(extract_document_urls(blocks) + html_document_urls))

    competition_type = clean_text(competition.get("type"))
    currency, entry_fee, prize_pool, money_meta = extract_money_from_documents(
        document_texts,
        competition_type=competition_type,
    )

    metadata = {
        "scraped_by": SOURCE,
        "source_url": source_url,
        "competition_id": competition.get("competitionId") or competition.get("id"),
        "competition_name": competition.get("name"),
        "competition_type": competition_type,
        "pool_count": len(pools),
        "pool_sizes": pool_sizes,
        "de_round_names": round_names,
        "document_urls": document_urls,
        "detail_fields": detail_fields,
        "detail_fields_raw": detail_fields_raw,
        **money_meta,
    }

    return {
        "tournament_id": tournament_id,
        "format_type": format_type,
        "pool_size": infer_pool_size(pool_sizes),
        "de_rounds": len(round_names) or None,
        "entry_fee": entry_fee,
        "prize_pool": prize_pool,
        "currency": currency,
        "participant_count": extract_participant_count(competition, athletes),
        "countries_represented": count_countries(athletes),
        "metadata": metadata,
        "scraped_at": datetime.now(UTC).isoformat(),
    }


def fetch_detail_html(season: int, competition_url_id: Any) -> str | None:
    url = f"{FIE_BASE}/competitions/{season}/{competition_url_id}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code != 200:
        print(f"  Detail fetch HTTP {response.status_code}: {url}")
        return None
    return response.text


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def fetch_document_texts(urls: list[str]) -> list[str]:
    texts: list[str] = []
    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code != 200:
                print(f"  Document fetch HTTP {response.status_code}: {url}")
                continue
            content_type = response.headers.get("content-type", "").casefold()
            if "pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf"):
                texts.append(extract_pdf_text(response.content))
            else:
                texts.append(response.text)
        except Exception as exc:
            print(f"  Document fetch failed: {url}: {exc}")
    return texts


def fetch_all(client, table: str, select_columns: str, configure: Callable[[Any], Any] | None = None) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = client.table(table).select(select_columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def find_tournaments_needing_details(client, limit: int | None = None) -> list[dict]:
    existing_rows = fetch_all(client, "fs_competition_details", "tournament_id")
    existing_ids = {str(row["tournament_id"]) for row in existing_rows if row.get("tournament_id")}

    select_columns = ",".join(
        [
            "id",
            "fie_id",
            "competition_url_id",
            "season",
            "name",
            *TOURNAMENT_DETAIL_COLUMNS,
            "detail_source",
        ]
    )
    tournaments = fetch_all(
        client,
        "fs_tournaments",
        select_columns,
        configure=lambda query: query.not_.is_("fie_id", "null"),
    )

    def missing_tournament_columns(row: dict[str, Any]) -> bool:
        present_columns = [column for column in (*TOURNAMENT_DETAIL_COLUMNS, "detail_source") if column in row]
        if not present_columns:
            return False
        return any(row.get(column) in (None, "") for column in present_columns)

    pending = [
        row
        for row in tournaments
        if row.get("id") and (str(row["id"]) not in existing_ids or missing_tournament_columns(row))
    ]
    if limit:
        return pending[:limit]
    return pending


def normalize_season(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return datetime.now(UTC).year
    try:
        return int(float(text))
    except ValueError:
        years = re.findall(r"\d{4}", text)
        if years:
            return int(years[-1])
    return datetime.now(UTC).year


def detail_url(season: int, competition_url_id: Any) -> str:
    return f"{FIE_BASE}/competitions/{season}/{competition_url_id}"


def upsert_competition_detail(client, row: dict[str, Any]) -> int:
    client.table("fs_competition_details").upsert(row, on_conflict="tournament_id").execute()
    return 1


def update_tournament_detail_fields(client, tournament_id: Any, detail_row: dict[str, Any]) -> int:
    update = build_tournament_update(detail_row)
    if not update:
        return 0
    table = client.table("fs_tournaments")
    if not hasattr(table, "update"):
        return 0
    table.update(update).eq("id", tournament_id).execute()
    return 1


def scrape_competition_details(
    client=None,
    limit: int | None = None,
    fetch_html: Callable[[int, Any], str | None] | None = None,
    fetch_document_texts: Callable[[list[str]], list[str]] | None = None,
    log_run: bool = True,
    update_state: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    client = client or get_supabase_client()
    fetch_html = fetch_html or fetch_detail_html
    fetch_document_texts = fetch_document_texts or globals()["fetch_document_texts"]
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    failure_counts = get_state(SOURCE, "failure_counts") if update_state else {}
    if not isinstance(failure_counts, dict):
        failure_counts = {}

    written = failed = skipped = processed = 0
    try:
        tournaments = find_tournaments_needing_details(client, limit=limit)
        for tournament in tournaments:
            tournament_id = tournament.get("id")
            url_id = tournament.get("competition_url_id") or tournament.get("fie_id")
            if not tournament_id or not url_id:
                skipped += 1
                continue

            season = normalize_season(tournament.get("season"))
            source_url = detail_url(season, url_id)
            processed += 1
            try:
                html = fetch_html(season, url_id)
                if not html:
                    raise RuntimeError(f"No FIE detail HTML returned for {source_url}")
                blocks = extract_window_blocks(html)
                document_urls = list(
                    dict.fromkeys(extract_document_urls(blocks) + (extract_html_links(html).get("document_urls") or []))
                )
                documents = fetch_document_texts(document_urls) if document_urls else []
                row = parse_competition_detail_page(
                    html,
                    tournament_id=tournament_id,
                    source_url=source_url,
                    document_texts=documents,
                )
                upsert_competition_detail(client, row)
                update_tournament_detail_fields(client, tournament_id, row)
                written += 1
                failure_counts.pop(str(tournament_id), None)
            except Exception as exc:
                failed += 1
                key = str(tournament_id)
                failure_counts[key] = int(failure_counts.get(key, 0)) + 1
                print(f"  Failed {tournament.get('name') or tournament_id}: {exc}")
            sleep(REQUEST_DELAY)

        if update_state:
            set_state(SOURCE, "failure_counts", failure_counts)
            set_state(
                SOURCE,
                "last_summary",
                {
                    "processed": processed,
                    "written": written,
                    "failed": failed,
                    "skipped": skipped,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped)
        return {"processed": processed, "written": written, "failed": failed, "skipped": skipped}
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main(limit: int | None = None) -> None:
    effective_limit = DEFAULT_LIMIT if limit is None else limit
    summary = scrape_competition_details(limit=effective_limit or None)
    print(
        "Competition details complete - "
        f"processed={summary['processed']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()
