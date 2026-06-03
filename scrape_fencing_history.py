import copy
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "scrape_fencing_history"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
REQUEST_TIMEOUT = 25
BATCH_SIZE = 100

FIE_HISTORY_URL = "https://fie.org/fie/history"
BRITANNICA_HISTORY_URL = "https://www.britannica.com/sports/fencing/Organized-sport"
USAF_NONCOMBATIVITY_URL = (
    "https://www.usafencing.org/news/2022/december/19/"
    "updated-unwillingness-to-fight-noncombativity-rules-take-effect-jan-1-2023"
)
AUSTRALIAN_NONCOMBATIVITY_URL = (
    "https://www.ausfencing.org/unwillingness-to-fight-non-combativity-rules/"
)
FIE_SABRE_TIMING_URL = (
    "https://static.fie.org/uploads/28/"
    "141008-123895-new%20rules%20for%20sabre_cover_ang.pdf"
)
CANADIAN_SABRE_TIMING_URL = "https://fencing.ca/rule-changes-2016/"
FENCING_MASTER_HISTORY_URL = "https://www.fencingmaster.com/history/history.htm"
KENT_HISTORY_URL = "https://www.kent-fencing.org.uk/fencing.html"
FIE_TOKYO_2020_URL = "https://fie.org/articles/1114"
OLYMPEDIA_FENCING_URL = "https://www.olympedia.org/sports/FEN"

CATEGORIES = {"governance", "rule_change", "equipment", "scoring_timing"}
WEAPON_ORDER = ("epee", "foil", "sabre")


@dataclass(frozen=True)
class HistorySource:
    url: str
    parser: Callable[[str, str], list[dict]]
    source_kind: str


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text


def page_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))


def normalize_title(value: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ordered_weapons(values: Iterable[str] | None) -> list[str]:
    seen = {clean_text(value).lower() for value in values or [] if clean_text(value)}
    return [weapon for weapon in WEAPON_ORDER if weapon in seen]


def validate_event(event: dict) -> dict:
    row = dict(event)
    row["event_date"] = row.get("event_date") or None
    if row["event_date"]:
        try:
            parsed = date.fromisoformat(str(row["event_date"]))
        except ValueError as exc:
            raise ValueError(f"invalid event_date: {row['event_date']}") from exc
        row["event_year"] = int(row.get("event_year") or parsed.year)

    if not row.get("event_year"):
        raise ValueError("event_year is required")
    row["event_year"] = int(row["event_year"])
    if not 1200 <= row["event_year"] <= 2100:
        raise ValueError("event_year must be between 1200 and 2100")

    row["category"] = clean_text(row.get("category"))
    if row["category"] not in CATEGORIES:
        raise ValueError(f"invalid category: {row['category']}")

    row["title"] = clean_text(row.get("title"))
    if not row["title"]:
        raise ValueError("title is required")

    row["description"] = clean_text(row.get("description"))
    if not row["description"]:
        raise ValueError("description is required")

    row["source_url"] = clean_text(row.get("source_url"))
    if not row["source_url"] or not row["source_url"].startswith(("http://", "https://")):
        raise ValueError("source_url is required")

    row["affected_weapons"] = ordered_weapons(row.get("affected_weapons"))
    if not row["affected_weapons"]:
        raise ValueError("affected_weapons is required")

    row["confidence"] = float(row.get("confidence", 0.75))
    if not 0 <= row["confidence"] <= 1:
        raise ValueError("confidence must be between 0 and 1")

    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")
    row["metadata"] = dict(metadata)
    return row


def make_event(
    *,
    event_year: int,
    category: str,
    title: str,
    description: str,
    affected_weapons: list[str],
    source_url: str,
    confidence: float,
    event_date: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return validate_event(
        {
            "event_date": event_date,
            "event_year": event_year,
            "category": category,
            "title": title,
            "description": description,
            "affected_weapons": affected_weapons,
            "source_url": source_url,
            "confidence": confidence,
            "metadata": metadata or {},
        }
    )


def parse_fie_history_page(html: str, source_url: str = FIE_HISTORY_URL) -> list[dict]:
    text = page_text(html)
    lower = text.lower()
    events: list[dict] = []

    if "29 november 1913" in lower and "fie was created" in lower:
        events.append(
            make_event(
                event_date="1913-11-29",
                event_year=1913,
                category="governance",
                title="FIE founded and first epee rules adopted",
                description=(
                    "The FIE was created in Paris and adopted its first epee "
                    "rules after disputes around the 1908 and 1912 Olympic Games."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.95,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                    "related_olympic_disputes": [1908, 1912],
                },
            )
        )
        events.append(
            make_event(
                event_date="1913-11-29",
                event_year=1913,
                category="rule_change",
                title="First FIE epee rules adopted",
                description=(
                    "At its creation, the FIE adopted its first epee rules, "
                    "creating an international rules baseline after Olympic disputes."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.9,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                    "related_olympic_disputes": [1908, 1912],
                },
            )
        )

    if "1924" in lower and "women" in lower and "foil" in lower:
        events.append(
            make_event(
                event_year=1924,
                category="governance",
                title="Women's foil introduced at the Olympic Games",
                description=(
                    "Women's foil entered the Olympic fencing programme, "
                    "opening the first women's Olympic fencing event."
                ),
                affected_weapons=["foil"],
                source_url=source_url,
                confidence=0.9,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                },
            )
        )

    if "1931" in lower and "first electric control apparatus" in lower:
        events.append(
            make_event(
                event_year=1931,
                category="equipment",
                title="First electric control apparatus experimented",
                description=(
                    "FIE history records experimentation with the first "
                    "electric control apparatus for fencing hits."
                ),
                affected_weapons=["epee", "foil", "sabre"],
                source_url=source_url,
                confidence=0.9,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                },
            )
        )

    if "1936" in lower and "electric apparatus" in lower and "adopted" in lower:
        events.append(
            make_event(
                event_year=1936,
                category="scoring_timing",
                title="Electric epee adopted for competition",
                description=(
                    "The FIE adopted electric hit-signalling apparatus for "
                    "competition, moving epee judging away from side judges."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.9,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                },
            )
        )
        events.append(
            make_event(
                event_year=1936,
                category="equipment",
                title="Electric hit-signalling apparatus adopted by FIE",
                description=(
                    "Electric apparatus for signalling hits became part of "
                    "international fencing governance."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.88,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                },
            )
        )

    if "1996" in lower and "women" in lower and "epee" in lower:
        events.append(
            make_event(
                event_year=1996,
                category="governance",
                title="Women's epee added to the Olympic programme",
                description=(
                    "Women's epee joined the Olympic fencing programme after "
                    "women's foil had been the sole women's Olympic weapon."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.9,
                metadata={
                    "source_name": "FIE history",
                    "source_kind": "official_history",
                    "manual_curation": False,
                },
            )
        )

    return events


def parse_britannica_history_page(
    html: str,
    source_url: str = BRITANNICA_HISTORY_URL,
) -> list[dict]:
    text = page_text(html)
    lower = text.lower()
    events: list[dict] = []

    if "1913" in lower and "federation internationale" in lower and "founded" in lower:
        events.append(
            make_event(
                event_year=1913,
                category="governance",
                title="FIE founded and first epee rules adopted",
                description=(
                    "A public history source corroborates 1913 as the year "
                    "the FIE became the governing body for international fencing."
                ),
                affected_weapons=["epee", "foil", "sabre"],
                source_url=source_url,
                confidence=0.8,
                metadata={
                    "source_name": "Britannica",
                    "source_kind": "public_history",
                    "manual_curation": False,
                },
            )
        )

    if "1936" in lower and "electrical epee" in lower:
        events.append(
            make_event(
                event_year=1936,
                category="scoring_timing",
                title="Electric epee adopted for competition",
                description=(
                    "Britannica dates the adoption of electrical epee "
                    "competition to 1936."
                ),
                affected_weapons=["epee"],
                source_url=source_url,
                confidence=0.85,
                metadata={
                    "source_name": "Britannica",
                    "source_kind": "public_history",
                    "manual_curation": False,
                },
            )
        )

    if "1955" in lower and "electrical scoring" in lower and "foil" in lower:
        events.append(
            make_event(
                event_year=1955,
                category="scoring_timing",
                title="Electrical scoring introduced for foil",
                description=(
                    "Electrical scoring was introduced for foil competitions "
                    "before its Olympic debut at the 1956 Games."
                ),
                affected_weapons=["foil"],
                source_url=source_url,
                confidence=0.85,
                metadata={
                    "source_name": "Britannica",
                    "source_kind": "public_history",
                    "manual_curation": False,
                    "olympic_debut_year": 1956,
                },
            )
        )

    return events


def parse_usaf_noncombativity_page(
    html: str,
    source_url: str = USAF_NONCOMBATIVITY_URL,
) -> list[dict]:
    text = page_text(html)
    lower = text.lower()
    if (
        "jan. 1, 2023" not in lower
        and "january 1, 2023" not in lower
        and "jan 1, 2023" not in lower
    ):
        return []
    if "non-combativity" not in lower and "unwillingness to fight" not in lower:
        return []
    if "2022 fie congress" not in lower:
        return []

    return [
        make_event(
            event_date="2023-01-01",
            event_year=2023,
            category="rule_change",
            title="Updated non-combativity P-Card rules take effect",
            description=(
                "FIE Congress-approved unwillingness-to-fight changes took "
                "effect domestically in USA Fencing events, changing how "
                "P-Cards are awarded."
            ),
            affected_weapons=["epee", "foil", "sabre"],
            source_url=source_url,
            confidence=0.88,
            metadata={
                "source_name": "USA Fencing",
                "source_kind": "federation_rule_summary",
                "manual_curation": False,
                "fie_congress_date": "2022-11-26",
            },
        )
    ]


def parse_sabre_timing_text(
    text: str,
    source_url: str = FIE_SABRE_TIMING_URL,
) -> list[dict]:
    normalized = clean_text(text).lower()
    combined = f"{normalized} {source_url.lower()}"
    if "2016" not in normalized or "120" not in normalized or "170" not in normalized:
        return []
    if "sabre" not in combined and "saber" not in combined:
        return []
    if "double" not in normalized and "timing" not in normalized:
        return []

    return [
        make_event(
            event_year=2016,
            category="scoring_timing",
            title="Sabre double-hit timing changed to 170 ms",
            description=(
                "FIE sabre apparatus timing guidance changed the double-hit "
                "registration window from 120 ms to 170 ms for the 2016-17 season."
            ),
            affected_weapons=["sabre"],
            source_url=source_url,
            confidence=0.86,
            metadata={
                "source_name": "FIE new rules for sabre",
                "source_kind": "official_rule_pdf",
                "manual_curation": False,
                "former_timing_ms": 120,
                "new_timing_ms": 170,
                "season": "2016-17",
            },
        )
    ]


def curated_event(
    *,
    event_year: int,
    category: str,
    title: str,
    description: str,
    affected_weapons: list[str],
    source_url: str,
    confidence: float,
    event_date: str | None = None,
    metadata: dict | None = None,
) -> dict:
    data = dict(metadata or {})
    data.setdefault("manual_curation", True)
    data.setdefault("curation_reason", "Public source is prose or PDF, not a stable feed.")
    return make_event(
        event_date=event_date,
        event_year=event_year,
        category=category,
        title=title,
        description=description,
        affected_weapons=affected_weapons,
        source_url=source_url,
        confidence=confidence,
        metadata=data,
    )


CURATED_TIMELINE_EVENTS = [
    curated_event(
        event_year=1896,
        category="governance",
        title="Fencing included in the first modern Olympic Games",
        description=(
            "Fencing was contested at the first modern Summer Olympic Games, "
            "establishing the sport as a continuous Olympic programme member."
        ),
        affected_weapons=["epee", "foil", "sabre"],
        source_url=OLYMPEDIA_FENCING_URL,
        confidence=0.82,
        metadata={"source_name": "Olympedia", "source_kind": "olympic_history"},
    ),
    curated_event(
        event_date="1913-11-29",
        event_year=1913,
        category="governance",
        title="FIE founded and first epee rules adopted",
        description=(
            "The FIE was created in Paris and adopted its first epee rules "
            "after Olympic rules disputes."
        ),
        affected_weapons=["epee"],
        source_url=FIE_HISTORY_URL,
        confidence=0.95,
        metadata={
            "source_name": "FIE history",
            "source_kind": "official_history",
            "related_olympic_disputes": [1908, 1912],
        },
    ),
    curated_event(
        event_year=1924,
        category="governance",
        title="Women's foil introduced at the Olympic Games",
        description=(
            "Women's foil became the first women's Olympic fencing event."
        ),
        affected_weapons=["foil"],
        source_url=FIE_HISTORY_URL,
        confidence=0.9,
        metadata={"source_name": "FIE history", "source_kind": "official_history"},
    ),
    curated_event(
        event_year=1931,
        category="equipment",
        title="First electric control apparatus experimented",
        description=(
            "FIE history records experiments with the first electric control "
            "apparatus for registering fencing hits."
        ),
        affected_weapons=["epee", "foil", "sabre"],
        source_url=FIE_HISTORY_URL,
        confidence=0.9,
        metadata={"source_name": "FIE history", "source_kind": "official_history"},
    ),
    curated_event(
        event_year=1936,
        category="scoring_timing",
        title="Electric epee adopted for competition",
        description=(
            "Electric hit signalling was adopted for epee competition, "
            "reducing reliance on side judges for hit arrival."
        ),
        affected_weapons=["epee"],
        source_url=FIE_HISTORY_URL,
        confidence=0.9,
        metadata={"source_name": "FIE history", "source_kind": "official_history"},
    ),
    curated_event(
        event_year=1933,
        category="scoring_timing",
        title="Electric epee adopted for competition",
        description=(
            "A fencing history source dates official epee use of the "
            "Laurent-Pagan electric scoring apparatus to 1933."
        ),
        affected_weapons=["epee"],
        source_url=FENCING_MASTER_HISTORY_URL,
        confidence=0.68,
        metadata={
            "source_name": "FencingMaster history",
            "source_kind": "public_history",
            "date_conflict_note": "FIE/Britannica sources use 1936.",
        },
    ),
    curated_event(
        event_year=1955,
        category="scoring_timing",
        title="Electrical scoring introduced for foil",
        description=(
            "Electrical scoring entered foil competitions ahead of its "
            "Olympic debut at the 1956 Games."
        ),
        affected_weapons=["foil"],
        source_url=BRITANNICA_HISTORY_URL,
        confidence=0.85,
        metadata={
            "source_name": "Britannica",
            "source_kind": "public_history",
            "olympic_debut_year": 1956,
        },
    ),
    curated_event(
        event_year=1988,
        category="scoring_timing",
        title="Electric sabre scoring introduced",
        description=(
            "Public fencing history sources date the introduction of "
            "electric sabre scoring to 1988."
        ),
        affected_weapons=["sabre"],
        source_url=KENT_HISTORY_URL,
        confidence=0.68,
        metadata={"source_name": "Kent Fencing history", "source_kind": "public_history"},
    ),
    curated_event(
        event_year=1996,
        category="governance",
        title="Women's epee added to the Olympic programme",
        description=(
            "Women's epee joined the Olympic fencing programme after women's "
            "foil had been the only women's Olympic fencing weapon."
        ),
        affected_weapons=["epee"],
        source_url=FIE_HISTORY_URL,
        confidence=0.9,
        metadata={"source_name": "FIE history", "source_kind": "official_history"},
    ),
    curated_event(
        event_year=1999,
        category="governance",
        title="Women's sabre added to the World Championships",
        description=(
            "Women's sabre individual and team events were added to the World "
            "Championships before later Olympic inclusion."
        ),
        affected_weapons=["sabre"],
        source_url="https://www.the-sports.org/fencing-world-championships-events-statistics-all-time-s22-c2-b0-g122-t1959-u0.html",
        confidence=0.65,
        metadata={
            "source_name": "World Championship event statistics",
            "source_kind": "public_history",
        },
    ),
    curated_event(
        event_year=2004,
        category="governance",
        title="Women's sabre added to the Olympic programme",
        description=(
            "Women's sabre entered the Olympic fencing programme at Athens "
            "2004, expanding Olympic weapon parity."
        ),
        affected_weapons=["sabre"],
        source_url=OLYMPEDIA_FENCING_URL,
        confidence=0.78,
        metadata={"source_name": "Olympedia", "source_kind": "olympic_history"},
    ),
    curated_event(
        event_year=2016,
        category="scoring_timing",
        title="Sabre double-hit timing changed to 170 ms",
        description=(
            "FIE sabre apparatus timing guidance changed the double-hit "
            "registration window from 120 ms to 170 ms for the 2016-17 season."
        ),
        affected_weapons=["sabre"],
        source_url=FIE_SABRE_TIMING_URL,
        confidence=0.86,
        metadata={
            "source_name": "FIE new rules for sabre",
            "source_kind": "official_rule_pdf",
            "former_timing_ms": 120,
            "new_timing_ms": 170,
            "season": "2016-17",
        },
    ),
    curated_event(
        event_year=2016,
        category="scoring_timing",
        title="Sabre double-hit timing changed to 170 ms",
        description=(
            "The Canadian Fencing Federation summarized the FIE sabre timing "
            "change as a move to 170 ms +/- 10."
        ),
        affected_weapons=["sabre"],
        source_url=CANADIAN_SABRE_TIMING_URL,
        confidence=0.72,
        metadata={
            "source_name": "Canadian Fencing Federation",
            "source_kind": "federation_rule_summary",
        },
    ),
    curated_event(
        event_date="2021-08-04",
        event_year=2021,
        category="governance",
        title="All 12 Olympic fencing events contested",
        description=(
            "At Tokyo 2020, fencing held gold-medal events for all six "
            "individual and six team events across epee, foil, and sabre."
        ),
        affected_weapons=["epee", "foil", "sabre"],
        source_url=FIE_TOKYO_2020_URL,
        confidence=0.9,
        metadata={"source_name": "FIE Tokyo 2020 report", "source_kind": "official_news"},
    ),
    curated_event(
        event_date="2023-01-01",
        event_year=2023,
        category="rule_change",
        title="Updated non-combativity P-Card rules take effect",
        description=(
            "FIE Congress-approved unwillingness-to-fight changes took "
            "effect in USA Fencing domestic events, changing how P-Cards "
            "are awarded."
        ),
        affected_weapons=["epee", "foil", "sabre"],
        source_url=USAF_NONCOMBATIVITY_URL,
        confidence=0.88,
        metadata={
            "source_name": "USA Fencing",
            "source_kind": "federation_rule_summary",
            "fie_congress_date": "2022-11-26",
        },
    ),
    curated_event(
        event_date="2023-02-01",
        event_year=2023,
        category="rule_change",
        title="Updated non-combativity P-Card rules take effect",
        description=(
            "The Australian Fencing Federation reported adoption of the same "
            "FIE non-combativity rule updates from February 2023."
        ),
        affected_weapons=["epee", "foil", "sabre"],
        source_url=AUSTRALIAN_NONCOMBATIVITY_URL,
        confidence=0.75,
        metadata={
            "source_name": "Australian Fencing Federation",
            "source_kind": "federation_rule_summary",
            "fie_congress_date": "2022-11-26",
            "domestic_effective_scope": "Australia",
        },
    ),
]


DEFAULT_SOURCES = [
    HistorySource(FIE_HISTORY_URL, parse_fie_history_page, "official_history"),
    HistorySource(BRITANNICA_HISTORY_URL, parse_britannica_history_page, "public_history"),
    HistorySource(USAF_NONCOMBATIVITY_URL, parse_usaf_noncombativity_page, "rule_summary"),
    HistorySource(FIE_SABRE_TIMING_URL, parse_sabre_timing_text, "official_rule_pdf"),
]


def event_key(event: dict) -> tuple[str, str]:
    return (event["category"], normalize_title(event["title"]))


def append_unique(items: list, value) -> None:
    if value not in items:
        items.append(value)


def merge_event(existing: dict, incoming: dict) -> None:
    metadata = existing.setdefault("metadata", {})
    metadata.setdefault("source_urls", [existing["source_url"]])
    append_unique(metadata["source_urls"], incoming["source_url"])

    evidence = metadata.setdefault("evidence", [])
    incoming_evidence = {
        "event_date": incoming.get("event_date"),
        "event_year": incoming.get("event_year"),
        "source_url": incoming["source_url"],
        "confidence": incoming["confidence"],
    }
    append_unique(evidence, incoming_evidence)

    current_date = (existing.get("event_date"), existing.get("event_year"))
    incoming_date = (incoming.get("event_date"), incoming.get("event_year"))
    if incoming_date != current_date:
        conflicting_dates = metadata.setdefault("conflicting_dates", [])
        conflict = {
            "event_date": incoming.get("event_date"),
            "event_year": incoming.get("event_year"),
            "source_url": incoming["source_url"],
        }
        append_unique(conflicting_dates, conflict)

    for weapon in incoming.get("affected_weapons") or []:
        if weapon not in existing["affected_weapons"]:
            existing["affected_weapons"].append(weapon)
    existing["affected_weapons"] = ordered_weapons(existing["affected_weapons"])
    existing["confidence"] = max(existing["confidence"], incoming["confidence"])


def dedupe_events(events: Iterable[dict]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}
    for raw_event in events:
        event = validate_event(raw_event)
        key = event_key(event)
        if key not in deduped:
            row = copy.deepcopy(event)
            row["metadata"] = dict(row.get("metadata") or {})
            row["metadata"].setdefault("source_urls", [row["source_url"]])
            row["metadata"].setdefault("evidence", [])
            deduped[key] = row
            continue
        merge_event(deduped[key], event)

    return sorted(
        deduped.values(),
        key=lambda row: (row["event_year"], row["event_date"] or "", row["title"]),
    )


def fetch_source_text(source: HistorySource) -> str:
    response = requests.get(
        source.url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    if source.source_kind.endswith("pdf"):
        return response.content.decode(response.encoding or "utf-8", errors="ignore")
    return response.text


def collect_history_events(
    *,
    include_remote: bool = True,
    include_curated: bool = True,
    fetcher: Callable[[HistorySource], str] = fetch_source_text,
    sources: Iterable[HistorySource] | None = None,
) -> list[dict]:
    events: list[dict] = []
    if include_curated:
        events.extend(copy.deepcopy(CURATED_TIMELINE_EVENTS))

    if include_remote:
        for source in sources or DEFAULT_SOURCES:
            try:
                source_text = fetcher(source)
                events.extend(source.parser(source_text, source.url))
                time.sleep(0.2)
            except Exception as exc:
                print(f"[{SOURCE}] source skipped {source.url}: {exc}")

    return dedupe_events(events)


def batch_upsert_history_events(client, rows: list[dict], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fencing_history_events").upsert(
            batch,
            on_conflict="category,event_year,title",
        ).execute()
        written += len(batch)
    return written


def scrape_fencing_history(
    *,
    supabase=None,
    include_remote: bool = True,
    fetcher: Callable[[HistorySource], str] = fetch_source_text,
    log_run: bool = True,
    update_state: bool = True,
) -> int:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        rows = collect_history_events(include_remote=include_remote, fetcher=fetcher)
        client = supabase or get_supabase_client()
        written = batch_upsert_history_events(client, rows) if client else 0
        summary = {
            "prepared": len(rows),
            "written": written,
            "skipped": 0 if client else len(rows),
            "include_remote": include_remote,
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
            run_log.complete(
                written=written,
                failed=0,
                skipped=summary["skipped"],
                metadata=summary,
            )
        return written
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    written = scrape_fencing_history()
    print(f"fencing history events: {written} rows written")


if __name__ == "__main__":
    main()
