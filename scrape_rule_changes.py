"""
Historical fencing rule-change scraper.

The table produced by this module stores sourced rule-change facts. It does not
claim causal impact on competition results unless a caller supplies a tested
aggregate analysis with caveats.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime, timezone
from typing import Any, TypedDict


class RuleChangeSeed(TypedDict, total=False):
    summary: str
    effective_date: str
    effective_season: str
    weapons_affected: list[str]
    categories_affected: list[str]
    rule_area: str
    source_url: str
    source_type: str
    source_title: str
    evidence_quote: str
    affected_competition_ids: list[str]
    affected_seasons: list[str]
    impact_analysis_status: str
    impact_summary: str
    metadata: dict[str, Any]
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

STATE_SOURCE = "scrape_rule_changes"
REQUEST_TIMEOUT = int(os.environ.get("RULE_CHANGES_REQUEST_TIMEOUT", "20"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIE_RULES_URL = "https://fie.org/fie/documents/rules"
FENCING_ARCHIVE_FIE_URL = "https://www.fencingarchive.com/index.php/fie/"

CHANGELOG_SOURCES = [
    {
        "url": "https://www.britishfencing.com/updates-from-fie-congress-november-2023/",
        "source_type": "federation_summary",
    },
    {
        "url": "https://www.britishfencing.com/2025-fie-congress-summary-decisions/",
        "source_type": "federation_summary",
    },
    {
        "url": "https://www.usafencing.org/news/2022/december/19/updated-unwillingness-to-fight-noncombativity-rules-take-effect-jan-1-2023",
        "source_type": "federation_summary",
    },
]

DEFAULT_MANUAL_SEEDS: list[RuleChangeSeed] = [
    {
        "summary": "Updated unwillingness-to-fight/non-combativity P-card rules took effect for USA Fencing events on Jan. 1, 2023.",
        "effective_date": "2023-01-01",
        "weapons_affected": ["epee"],
        "categories_affected": ["individual", "team"],
        "rule_area": "passivity",
        "source_url": "https://www.usafencing.org/news/2022/december/19/updated-unwillingness-to-fight-noncombativity-rules-take-effect-jan-1-2023",
        "source_type": "federation_summary",
        "evidence_quote": "The rule changes, enforced at all USA Fencing tournaments beginning Jan. 1, 2023, affect how P-Cards are awarded.",
    },
    {
        "summary": "Sabre lockout timing changed from 120ms to 170ms after the 2016 Olympics.",
        "effective_season": "2016-2017",
        "weapons_affected": ["sabre"],
        "categories_affected": ["senior", "junior"],
        "rule_area": "timing",
        "source_url": "https://fencing.net/15522/2015-fie-congress-summary/",
        "source_type": "historical_archive",
        "evidence_quote": "Blocking time on sabre goes from 120 to 170 milliseconds. Starts after Rio Olympics.",
    },
    {
        "summary": "A 2013 FIE Congress rules summary reported updates including foil blade-beat treatment, non-combativity criteria, visor masks, and spare mask wires.",
        "effective_season": "2013-2014",
        "weapons_affected": ["epee", "foil", "sabre"],
        "categories_affected": [],
        "rule_area": "general",
        "source_url": "https://www.swordfightersaustralia.com/blog/?cat=5",
        "source_type": "historical_archive",
        "evidence_quote": "In 2013 a number of rules were updated/created/amended at the FIE Congress.",
    },
]

ALL_WEAPONS = ["epee", "foil", "sabre"]
ALL_AGE_CATEGORIES = ["senior", "junior", "cadet", "veteran"]
EVENT_CATEGORIES = ["individual", "team"]
SOURCE_TYPES = {
    "fie_rulebook",
    "fie_congress_decision",
    "federation_summary",
    "historical_archive",
    "manual_seed",
}
IMPACT_STATUSES = {"not_analyzed", "tested_with_caveats"}

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


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\u00a0", " ").replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def _strip_size_suffix(title: str) -> str:
    return clean_text(re.sub(r"\s*\([^)]*\b[KM]b\)\s*$", "", title, flags=re.IGNORECASE))


def _absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def _document_area(title: str, section: str = "") -> str:
    text = f"{section} {title}".casefold()
    if "summary" in text and "congress" in text:
        return "congress_decision"
    if "congress" in text:
        return "congress"
    if "technical" in text:
        return "technical"
    if "material" in text:
        return "material"
    if "organis" in text or "organizat" in text:
        return "organization"
    if "rule" in text:
        return "rulebook"
    return "document"


def _published_label(title: str) -> str | None:
    month_match = re.search(
        r"\b("
        r"January|February|March|April|May|June|July|August|September|October|November|December"
        r")\s+(20\d{2})\b",
        title,
        flags=re.IGNORECASE,
    )
    if month_match:
        return f"{month_match.group(1).title()} {month_match.group(2)}"
    year_month = re.search(r"\b(20\d{2}-\d{2})\b", title)
    if year_month:
        return year_month.group(1)
    year = re.search(r"\b(19\d{2}|20\d{2})\b", title)
    if year:
        return year.group(1)
    return None


def parse_fie_rulebook_listing(html: str, base_url: str = FIE_RULES_URL) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        title = _strip_size_suffix(link.get_text(" ", strip=True))
        href = _absolute_url(base_url, link["href"])
        lower_title = title.casefold()
        if not title or ".pdf" not in href.casefold():
            continue
        if "rules" not in lower_title and "rule" not in lower_title:
            continue
        if href in seen:
            continue
        seen.add(href)
        docs.append(
            {
                "title": title,
                "source_url": href,
                "source_type": "fie_rulebook",
                "document_area": _document_area(title),
                "published_label": _published_label(title),
            }
        )
    return docs


def parse_fencing_archive_documents(html: str, base_url: str = FENCING_ARCHIVE_FIE_URL) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = _absolute_url(base_url, link["href"])
        if ".pdf" not in href.casefold():
            continue
        title = _strip_size_suffix(link.get_text(" ", strip=True))
        if not title or href in seen:
            continue
        seen.add(href)
        heading = ""
        for previous in link.find_all_previous(["h1", "h2", "h3"]):
            heading = clean_text(previous.get_text(" ", strip=True))
            if heading:
                break
        docs.append(
            {
                "title": title,
                "source_url": href,
                "source_type": "historical_archive",
                "document_area": _document_area(title, heading),
                "published_label": _published_label(title),
            }
        )
    return docs


def _normalize_date_text(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    text = text.replace(",", " ")
    text = re.sub(r"\bSept\.", "Sept", text, flags=re.IGNORECASE)
    text = re.sub(r"\bJan\.", "Jan", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_effective_date(value: str | None) -> str | None:
    text = _normalize_date_text(value or "")
    if not text:
        return None

    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        return _safe_date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    numeric_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text)
    if numeric_match:
        return _safe_date(int(numeric_match.group(3)), int(numeric_match.group(2)), int(numeric_match.group(1)))

    day_month_year = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b", text)
    if day_month_year:
        month = MONTHS.get(day_month_year.group(2).casefold())
        if month:
            return _safe_date(int(day_month_year.group(3)), month, int(day_month_year.group(1)))

    month_day_year = re.search(r"\b([A-Za-z]+)\s+(\d{1,2})\s+(20\d{2})\b", text)
    if month_day_year:
        month = MONTHS.get(month_day_year.group(1).casefold())
        if month:
            return _safe_date(int(month_day_year.group(3)), month, int(month_day_year.group(2)))

    return None


def _safe_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _extract_date_context(text: str) -> str | None:
    patterns = [
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+20\d{2}\b",
        r"\b[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+20\d{2}\b",
        r"\b20\d{2}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}/20\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def season_from_effective_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value).date()
    except ValueError:
        return None
    end_year = parsed.year if parsed.month < 7 else parsed.year + 1
    return f"{end_year - 1:04d}-{end_year:04d}"


def normalize_effective_season(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\b(20\d{2})\s*[-/]\s*(\d{2}|20\d{2})\b", text)
    if not match:
        return None
    start = int(match.group(1))
    end_raw = match.group(2)
    end = int(end_raw) if len(end_raw) == 4 else int(str(start)[:2] + end_raw)
    if end < start:
        end += 100
    return f"{start:04d}-{end:04d}"


def _extract_default_effective_date(text: str) -> str | None:
    markers = (
        "come into effect",
        "coming into effect",
        "take effect",
        "takes effect",
        "beginning",
        "enforced",
    )
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    for sentence in sentences:
        lowered = sentence.casefold()
        if any(marker in lowered for marker in markers):
            parsed = parse_effective_date(_extract_date_context(sentence) or sentence)
            if parsed:
                return parsed
    return None


def _published_date(published_at: str | None) -> str | None:
    if not published_at:
        return None
    parsed = parse_effective_date(published_at)
    if parsed:
        return parsed
    try:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _candidate_texts(soup: BeautifulSoup) -> list[str]:
    items = [clean_text(li.get_text(" ", strip=True)) for li in soup.find_all("li")]
    items = [item for item in items if _looks_like_rule_change(item)]
    if items:
        return items

    body = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in body.find_all("p")]
    article_text = clean_text(" ".join(p for p in paragraphs if p))
    if _looks_like_rule_change(article_text):
        return [article_text]
    return []


def _looks_like_rule_change(text: str) -> bool:
    lowered = text.casefold()
    keywords = (
        "rule",
        "rules",
        "passivity",
        "non-combativity",
        "unwillingness to fight",
        "p-card",
        "p-yellow",
        "p-red",
        "p-black",
        "t.",
        "o.",
        "foil",
        "epee",
        "sabre",
        "saber",
        "mask",
        "clothing",
        "category",
        "coaching",
        "lockout",
        "blocking time",
        "warm-up",
        "training",
        "effective",
        "come into effect",
    )
    return any(keyword in lowered for keyword in keywords)


def rule_area_from_text(text: str) -> str:
    lowered = text.casefold()
    if any(value in lowered for value in ("passivity", "non-combativity", "unwillingness to fight", "p-card")):
        return "passivity"
    if any(value in lowered for value in ("lockout", "blocking time", "millisecond", "timing")):
        return "timing"
    if any(value in lowered for value in ("women's category", "womens category", "eligibility", "female sex")):
        return "eligibility"
    if any(value in lowered for value in ("clothing", "mask", "equipment", "material", "breeches", "socks")):
        return "equipment"
    if "coaching" in lowered:
        return "coaching"
    if any(value in lowered for value in ("ranking", "points")):
        return "rankings"
    if any(value in lowered for value in ("sponsorship", "logo", "advertising")):
        return "publicity"
    if any(value in lowered for value in ("rest time", "format", "match")):
        return "competition_format"
    return "general"


def weapons_from_text(text: str, rule_area: str | None = None) -> list[str]:
    lowered = text.casefold()
    if "all weapons" in lowered:
        return ALL_WEAPONS.copy()
    weapons: list[str] = []
    if "epee" in lowered or "epée" in lowered:
        weapons.append("epee")
    if "foil" in lowered:
        weapons.append("foil")
    if "sabre" in lowered or "saber" in lowered:
        weapons.append("sabre")
    if weapons:
        return weapons
    if rule_area in {"passivity", "eligibility"}:
        return ALL_WEAPONS.copy()
    return []


def categories_from_text(text: str, rule_area: str | None = None) -> list[str]:
    lowered = text.casefold()
    categories: list[str] = []
    for category in ALL_AGE_CATEGORIES:
        if category in lowered:
            categories.append(category)
    for category in EVENT_CATEGORIES:
        if category in lowered:
            categories.append(category)
    if "women's category" in lowered or "womens category" in lowered or rule_area == "eligibility":
        return ALL_AGE_CATEGORIES.copy()
    if categories:
        return _dedupe(categories)
    if rule_area == "passivity":
        return EVENT_CATEGORIES.copy()
    return []


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _event_scope(text: str) -> str | None:
    lowered = text.casefold()
    if "direct elimination" in lowered or re.search(r"\bde\b", lowered):
        return "direct_elimination"
    if "pool" in lowered or "pools" in lowered:
        return "pools"
    return None


def _effective_values(text: str, *, default_date: str | None, published_at: str | None) -> tuple[str | None, str | None, str]:
    explicit_season = normalize_effective_season(text)
    lowered = text.casefold()
    if "effective immediately" in lowered:
        effective_date = _published_date(published_at) or default_date
    else:
        effective_date = parse_effective_date(_extract_date_context(text) or "")
    if effective_date is None and explicit_season is None:
        effective_date = default_date
    effective_season = explicit_season or season_from_effective_date(effective_date)
    if effective_date:
        date_status = "exact_date"
    elif effective_season:
        date_status = "season_only"
    else:
        date_status = "missing"
    return effective_date, effective_season, date_status


def parse_rule_change_changelog(
    html: str,
    *,
    source_url: str,
    source_type: str,
    published_at: str | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    source_title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")
    body = soup.find("article") or soup.find("main") or soup.body or soup
    body_text = clean_text(body.get_text(" ", strip=True))
    default_date = _extract_default_effective_date(body_text)

    rows: list[dict[str, Any]] = []
    for candidate in _candidate_texts(soup):
        rule_area = rule_area_from_text(candidate)
        effective_date, effective_season, date_status = _effective_values(
            candidate,
            default_date=default_date,
            published_at=published_at,
        )
        metadata = {
            "date_status": date_status,
            "parser": "rule_change_changelog",
        }
        scope = _event_scope(candidate)
        if scope:
            metadata["event_scope"] = scope
        row = build_rule_change_row(
            summary=candidate,
            effective_date=effective_date,
            effective_season=effective_season,
            weapons_affected=weapons_from_text(candidate, rule_area),
            categories_affected=categories_from_text(candidate, rule_area),
            rule_area=rule_area,
            source_url=source_url,
            source_type=source_type,
            source_title=source_title or None,
            evidence_quote=candidate[:500],
            affected_seasons=[effective_season] if effective_season else [],
            metadata=metadata,
            allow_missing_effective=True,
        )
        rows.append(row)
    return rows


def _validate_source(source_url: str | None, source_type: str | None) -> None:
    if not source_url or not clean_text(source_url):
        raise ValueError("source_url is required")
    if not str(source_url).startswith(("http://", "https://")):
        raise ValueError("source_url must be an http(s) URL")
    if not source_type or source_type not in SOURCE_TYPES:
        raise ValueError(f"source_type must be one of {sorted(SOURCE_TYPES)}")


def _validate_effective(
    effective_date: str | None,
    effective_season: str | None,
    *,
    allow_missing_effective: bool,
) -> None:
    if not effective_date and not effective_season and not allow_missing_effective:
        raise ValueError("effective_date or effective_season is required")
    if effective_date and parse_effective_date(effective_date) != effective_date:
        raise ValueError("effective_date must be YYYY-MM-DD")
    if effective_season and normalize_effective_season(effective_season) != effective_season:
        raise ValueError("effective_season must be YYYY-YYYY")


def _normalize_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    return _dedupe([clean_text(value).casefold() for value in values if clean_text(value)])


def _rule_key(
    *,
    source_url: str,
    summary: str,
    rule_area: str,
    effective_date: str | None,
    effective_season: str | None,
) -> str:
    payload = "\n".join(
        [
            clean_text(source_url),
            clean_text(rule_area),
            clean_text(effective_date),
            clean_text(effective_season),
            clean_text(summary).casefold(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_rule_change_row(
    *,
    summary: str,
    rule_area: str,
    source_url: str,
    source_type: str,
    effective_date: str | None = None,
    effective_season: str | None = None,
    weapons_affected: list[str] | None = None,
    categories_affected: list[str] | None = None,
    source_title: str | None = None,
    evidence_quote: str | None = None,
    affected_competition_ids: list[str] | None = None,
    affected_seasons: list[str] | None = None,
    impact_analysis_status: str = "not_analyzed",
    impact_summary: str | None = None,
    metadata: dict[str, Any] | None = None,
    allow_missing_effective: bool = False,
) -> dict[str, Any]:
    summary_text = clean_text(summary)
    area = clean_text(rule_area).casefold().replace(" ", "_")
    if not summary_text:
        raise ValueError("summary is required")
    if not area:
        raise ValueError("rule_area is required")
    _validate_source(source_url, source_type)
    effective_date = parse_effective_date(effective_date) if effective_date else None
    effective_season = normalize_effective_season(effective_season) if effective_season else None
    if effective_date and not effective_season:
        effective_season = season_from_effective_date(effective_date)
    _validate_effective(
        effective_date,
        effective_season,
        allow_missing_effective=allow_missing_effective,
    )
    if impact_analysis_status not in IMPACT_STATUSES:
        raise ValueError(f"impact_analysis_status must be one of {sorted(IMPACT_STATUSES)}")
    if impact_summary and impact_analysis_status != "tested_with_caveats":
        raise ValueError("impact_summary requires impact_analysis_status='tested_with_caveats'")

    affected_seasons_list = _normalize_list(affected_seasons)
    if not affected_seasons_list and effective_season:
        affected_seasons_list = [effective_season]

    metadata_value = dict(metadata or {})
    if impact_analysis_status == "not_analyzed":
        metadata_value.setdefault("impact_claim_policy", "historical_fact_only")

    return {
        "rule_key": _rule_key(
            source_url=source_url,
            summary=summary_text,
            rule_area=area,
            effective_date=effective_date,
            effective_season=effective_season,
        ),
        "effective_date": effective_date,
        "effective_season": effective_season,
        "weapons_affected": _normalize_list(weapons_affected),
        "categories_affected": _normalize_list(categories_affected),
        "rule_area": area,
        "summary": summary_text,
        "source_url": clean_text(source_url),
        "source_type": source_type,
        "source_title": clean_text(source_title) or None,
        "evidence_quote": clean_text(evidence_quote) or None,
        "affected_competition_ids": _normalize_list(affected_competition_ids),
        "affected_seasons": affected_seasons_list,
        "impact_analysis_status": impact_analysis_status,
        "impact_summary": clean_text(impact_summary) or None,
        "metadata": metadata_value,
    }


def valid_rule_change_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for candidate in candidates:
        if not candidate.get("effective_date") and not candidate.get("effective_season"):
            skipped += 1
            continue
        try:
            rows.append(
                build_rule_change_row(
                    summary=candidate.get("summary") or "",
                    effective_date=candidate.get("effective_date"),
                    effective_season=candidate.get("effective_season"),
                    weapons_affected=candidate.get("weapons_affected"),
                    categories_affected=candidate.get("categories_affected"),
                    rule_area=candidate.get("rule_area") or "",
                    source_url=candidate.get("source_url") or "",
                    source_type=candidate.get("source_type") or "",
                    source_title=candidate.get("source_title"),
                    evidence_quote=candidate.get("evidence_quote"),
                    affected_competition_ids=candidate.get("affected_competition_ids"),
                    affected_seasons=candidate.get("affected_seasons"),
                    impact_analysis_status=candidate.get("impact_analysis_status") or "not_analyzed",
                    impact_summary=candidate.get("impact_summary"),
                    metadata=candidate.get("metadata"),
                )
            )
        except ValueError:
            skipped += 1
    return rows, skipped


def load_manual_seed_fixtures(seeds: list[RuleChangeSeed] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in seeds if seeds is not None else DEFAULT_MANUAL_SEEDS:
        metadata = dict(seed.get("metadata") or {})
        metadata["manual_seed"] = True
        rows.append(
            build_rule_change_row(
                summary=seed.get("summary") or "",
                effective_date=seed.get("effective_date"),
                effective_season=seed.get("effective_season"),
                weapons_affected=seed.get("weapons_affected"),
                categories_affected=seed.get("categories_affected"),
                rule_area=seed.get("rule_area") or "",
                source_url=seed.get("source_url") or "",
                source_type=seed.get("source_type") or "manual_seed",
                source_title=seed.get("source_title"),
                evidence_quote=seed.get("evidence_quote"),
                affected_competition_ids=seed.get("affected_competition_ids"),
                affected_seasons=seed.get("affected_seasons"),
                impact_analysis_status=seed.get("impact_analysis_status") or "not_analyzed",
                impact_summary=seed.get("impact_summary"),
                metadata=metadata,
            )
        )
    return rows


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response.text


def upsert_rule_changes(client, rows: list[dict[str, Any]], batch_size: int = 100) -> int:
    if not rows:
        return 0
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        rule_key = row.get("rule_key")
        if rule_key:
            by_key[rule_key] = row
    deduped = list(by_key.values())
    written = 0
    for i in range(0, len(deduped), batch_size):
        batch = deduped[i : i + batch_size]
        client.table("fs_rule_changes").upsert(batch, on_conflict="rule_key").execute()
        written += len(batch)
    return written


def scrape_rule_changes() -> dict[str, Any]:
    client = get_supabase_client()
    session = requests.Session()
    previous_docs = get_state(STATE_SOURCE, "source_documents") or []

    source_documents: list[dict[str, Any]] = []
    failed = 0
    skipped = 0
    all_rows: list[dict[str, Any]] = []

    try:
        source_documents.extend(parse_fie_rulebook_listing(fetch_html(session, FIE_RULES_URL)))
    except Exception as exc:
        failed += 1
        print(f"  FIE rulebook listing failed: {exc}")

    try:
        source_documents.extend(parse_fencing_archive_documents(fetch_html(session, FENCING_ARCHIVE_FIE_URL)))
    except Exception as exc:
        failed += 1
        print(f"  Fencing Archive listing failed: {exc}")

    for source in CHANGELOG_SOURCES:
        try:
            candidates = parse_rule_change_changelog(
                fetch_html(session, source["url"]),
                source_url=source["url"],
                source_type=source["source_type"],
            )
            rows, source_skipped = valid_rule_change_rows(candidates)
            all_rows.extend(rows)
            skipped += source_skipped
        except Exception as exc:
            failed += 1
            print(f"  Rule-change source failed for {source['url']}: {exc}")

    try:
        all_rows.extend(load_manual_seed_fixtures())
    except Exception as exc:
        failed += 1
        print(f"  Manual seed load failed: {exc}")

    written = upsert_rule_changes(client, all_rows)
    if source_documents:
        set_state(STATE_SOURCE, "source_documents", source_documents[-1000:])
    elif previous_docs:
        set_state(STATE_SOURCE, "source_documents", previous_docs)
    set_state(
        STATE_SOURCE,
        "last_run",
        {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "source_documents": len(source_documents),
        },
    )
    return {
        "written": written,
        "failed": failed,
        "skipped": skipped,
        "fetched": len(all_rows),
        "source_documents": len(source_documents),
    }


def main() -> None:
    run_log = ScraperRunLogger("scrape_rule_changes").start()
    try:
        result = scrape_rule_changes()
        run_log.complete(
            written=result["written"],
            failed=result["failed"],
            skipped=result["skipped"],
            metadata={
                "fetched": result["fetched"],
                "source_documents": result["source_documents"],
            },
        )
        print(
            "Done - "
            f"fetched={result['fetched']}, written={result['written']}, "
            f"failed={result['failed']}, skipped={result['skipped']}, "
            f"source_documents={result['source_documents']}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
