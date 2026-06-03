from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - surfaced when a live client is required.
    create_client = None


SOURCE = "compute_career_milestones"
PAGE_SIZE = 1000
BATCH_SIZE = 100
MILESTONE_CONFLICT_COLUMNS = "person_key,milestone_type,tournament_key,milestone_date"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

RESULT_SELECTS = [
    "id,fencer_id,fie_fencer_id,tournament_id,rank,placement,medal,weapon,gender,category,season,country,nationality,name,metadata,date,created_at,updated_at",
    "fencer_id,fie_fencer_id,tournament_id,rank,placement,medal,weapon,gender,category,season,country,nationality,name,metadata,date",
    "fencer_id,fie_fencer_id,tournament_id,rank,placement,medal,name",
]
RANKING_SELECTS = [
    "fencer_id,fie_fencer_id,season,weapon,gender,category,rank,points,country,name,scraped_at",
    "fie_fencer_id,season,weapon,gender,category,rank,points,country,name,scraped_at",
    "fie_fencer_id,season,weapon,category,rank,points,country,name",
]
FENCER_SELECTS = [
    "id,fie_id,name,country,nationality,weapon,category,metadata",
    "id,fie_id,name,country,nationality,metadata",
    "id,fie_id,name",
]
IDENTITY_SELECTS = [
    "id,canonical_id,canonical_name,country,fie_ids,fs_fencer_row_ids,metadata",
    "id,canonical_name,country,fie_ids,fs_fencer_row_ids,metadata",
    "id,fs_fencer_row_ids,fie_ids",
    "canonical_id,fencer_ids",
]
TOURNAMENT_SELECTS = [
    "id,name,season,weapon,gender,category,type,country,location,start_date,end_date,date,fie_id,source_id,source,metadata",
    "id,name,season,weapon,gender,category,type,country,start_date,end_date,fie_id,metadata",
    "id,name,season,weapon,gender,category,start_date,end_date",
]
FENCER_STATS_SELECTS = [
    "identity_id,weapon,category,total_bouts,wins,losses,touches_scored,touches_received,current_streak,longest_win_streak,last_bout_at,updated_at",
    "identity_id,weapon,category,total_bouts,wins,losses,last_bout_at,updated_at",
]
LONGEVITY_SELECTS = [
    "fencer_id,first_competition_date,last_competition_date,first_season,last_season,status,updated_at",
    "fencer_id,last_competition_date,status,updated_at",
]

COUNTRY_ALIASES = {
    "AIN": "Russia",
    "AIN_": "Russia",
    "_AIN": "Russia",
    "FIE": "FIE",
    "US": "United States",
    "USA": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "GB": "Great Britain",
    "GBR": "Great Britain",
    "GREAT BRITAIN": "Great Britain",
    "KOR": "South Korea",
    "KOREA": "South Korea",
    "HONG KONG, CHINA": "Hong Kong",
    "HONG KONG CHINA": "Hong Kong",
    "TURKIYE": "Turkey",
    "COTE D'IVOIRE": "Cote D'Ivoire",
    "COTE DIVOIRE": "Cote D'Ivoire",
}

INTERNATIONAL_SOURCE_TERMS = {
    "fie",
    "olympic",
    "olympics",
    "paralympic",
    "paralympics",
    "world",
    "continental",
    "commonwealth",
    "universiade",
    "maccabiah",
    "mediterranean",
    "pan american",
    "cac",
    "iwas",
    "cism",
}
INTERNATIONAL_TYPE_TERMS = {
    "world cup",
    "grand prix",
    "world championship",
    "world championships",
    "olympic games",
    "paralympic games",
    "continental championship",
    "continental championships",
    "zonal championship",
    "zonal championships",
    "satellite",
    "european championship",
    "european championships",
    "asian championship",
    "asian championships",
    "pan american championship",
    "pan american championships",
    "african championship",
    "african championships",
}


@dataclass(frozen=True)
class Person:
    identity_id: str | None = None
    fencer_id: str | None = None
    fie_id: str | None = None
    fencer_name: str | None = None

    @property
    def key(self) -> str:
        return (
            self.identity_id
            or self.fencer_id
            or self.fie_id
            or normalize_key(self.fencer_name)
        )

    def fields(self) -> dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "fencer_id": self.fencer_id,
            "fie_id": self.fie_id,
            "fencer_name": self.fencer_name,
        }


class IdentityResolver:
    def __init__(self, fencers: list[dict[str, Any]], identities: list[dict[str, Any]]):
        self.fencer_to_person: dict[str, Person] = {}
        self.fie_to_person: dict[str, Person] = {}
        self.identity_to_person: dict[str, Person] = {}
        self._build(fencers, identities)

    def _build(self, fencers: list[dict[str, Any]], identities: list[dict[str, Any]]) -> None:
        fencer_by_id = {
            clean_text(row.get("id")): row
            for row in fencers
            if clean_text(row.get("id"))
        }

        for row in sorted(identities, key=lambda item: clean_text(item.get("id") or item.get("canonical_id")) or ""):
            identity_id = valid_uuid(row.get("id")) or valid_uuid(row.get("canonical_id"))
            members = parse_array(row.get("fs_fencer_row_ids") or row.get("fencer_ids"))
            member_ids = [member for member in members if valid_uuid(member)]
            canonical_fencer_id = (
                valid_uuid(row.get("canonical_id"))
                or next((member for member in sorted(member_ids) if member in fencer_by_id), None)
                or (sorted(member_ids)[0] if member_ids else None)
            )
            fie_ids = parse_array(row.get("fie_ids"))
            fencer_name = clean_text(row.get("canonical_name"))
            if not fencer_name:
                for member in sorted(member_ids):
                    fencer_name = clean_text((fencer_by_id.get(member) or {}).get("name"))
                    if fencer_name:
                        break

            if not identity_id and not canonical_fencer_id and not fie_ids:
                continue

            person = Person(
                identity_id=identity_id,
                fencer_id=canonical_fencer_id,
                fie_id=clean_text(sorted(fie_ids)[0]) if fie_ids else None,
                fencer_name=fencer_name,
            )
            if identity_id:
                self.identity_to_person[identity_id] = person
            for member in member_ids:
                self.fencer_to_person[member] = person
            for fie_id in fie_ids:
                text = clean_text(fie_id)
                if text:
                    self.fie_to_person[text] = person

        fie_counts = Counter(
            clean_text(row.get("fie_id"))
            for row in fencers
            if clean_text(row.get("fie_id"))
        )
        fallback_by_fie: dict[str, Person] = {}
        for row in sorted(fencers, key=lambda item: clean_text(item.get("id")) or ""):
            row_id = valid_uuid(row.get("id"))
            if not row_id:
                continue
            existing = self.fencer_to_person.get(row_id)
            fie_id = clean_text(row.get("fie_id"))
            if existing:
                if fie_id:
                    self.fie_to_person.setdefault(fie_id, existing)
                continue

            name = clean_text(row.get("name"))
            if fie_id and fie_counts[fie_id] > 1:
                person = fallback_by_fie.setdefault(
                    fie_id,
                    Person(fie_id=fie_id, fencer_name=name),
                )
            else:
                person = Person(fencer_id=row_id, fie_id=fie_id, fencer_name=name)
            self.fencer_to_person[row_id] = person
            if fie_id:
                self.fie_to_person.setdefault(fie_id, person)

    def from_result(self, row: dict[str, Any]) -> Person | None:
        fencer_id = valid_uuid(row.get("fencer_id"))
        if fencer_id and fencer_id in self.fencer_to_person:
            return self.fencer_to_person[fencer_id]

        fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
        if fie_id and fie_id in self.fie_to_person:
            return self.fie_to_person[fie_id]

        if fencer_id:
            return Person(fencer_id=fencer_id, fie_id=fie_id, fencer_name=clean_text(row.get("name")))
        if fie_id:
            return Person(fie_id=fie_id, fencer_name=clean_text(row.get("name")))
        return None

    def from_ranking(self, row: dict[str, Any]) -> Person | None:
        return self.from_result(row)

    def from_identity_id(self, identity_id: Any) -> Person | None:
        text = valid_uuid(identity_id)
        return self.identity_to_person.get(text) if text else None


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).casefold()


def valid_uuid(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError):
        return None


def parse_array(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        result = int(float(value))
        return result if result > 0 else None
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    key = re.sub(r"\s+", " ", key.upper().replace(".", ""))
    return COUNTRY_ALIASES.get(key, text.title())


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in {"e", "epee", "épée"}:
        return "Epee"
    if key in {"f", "foil", "fleuret"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).replace(".", "")
    if key in {"f", "female", "women", "woman", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "men", "man", "mens", "men's"}:
        return "Men's"
    return text.title()


def normalize_category(category: Any, gender: Any = None) -> str | None:
    category_text = clean_text(category)
    if not category_text:
        return None
    category_label = category_text if "'" in category_text else category_text.title()
    gender_label = normalize_gender(gender)
    if not gender_label:
        return category_label
    if category_label.casefold().startswith(gender_label.casefold()):
        return category_label
    return f"{gender_label} {category_label}"


def category_level(category: Any) -> str | None:
    key = normalize_key(category)
    if not key:
        return None
    if "junior" in key or re.search(r"\bu20\b", key):
        return "Junior"
    if "senior" in key:
        return "Senior"
    return None


def season_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = clean_text(value)
    if not text:
        return None
    years = re.findall(r"\d{4}", text)
    if years:
        return int(years[-1])
    short = re.match(r"^(\d{4})\s*[-/]\s*(\d{2})$", text)
    if short:
        start = int(short.group(1))
        end_two = int(short.group(2))
        end = (start // 100) * 100 + end_two
        return end + 100 if end < start else end
    return to_int(text)


def season_label(value: Any) -> str | None:
    text = clean_text(value)
    if text:
        return text
    season = season_to_int(value)
    return str(season) if season is not None else None


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def date_from_season(value: Any) -> date | None:
    season = season_to_int(value)
    return date(season, 7, 1) if season is not None else None


def result_event_date(result: dict[str, Any], tournament: dict[str, Any] | None) -> tuple[date | None, str | None]:
    for source in (tournament or {}, result):
        for key in ("start_date", "end_date", "date", "event_date"):
            parsed = parse_date(source.get(key))
            if parsed:
                return parsed, key
    season_date = date_from_season(result.get("season") or (tournament or {}).get("season"))
    return (season_date, "season") if season_date else (None, None)


def ranking_event_date(row: dict[str, Any]) -> tuple[date | None, str | None]:
    season_date = date_from_season(row.get("season"))
    if season_date:
        return season_date, "season"
    parsed = parse_date(row.get("scraped_at"))
    return (parsed, "scraped_at") if parsed else (None, None)


def normalize_medal(medal: Any, rank: int | None = None) -> str | None:
    text = normalize_key(medal)
    if text in {"gold", "g"}:
        return "gold"
    if text in {"silver", "s"}:
        return "silver"
    if text in {"bronze", "b"}:
        return "bronze"
    if rank == 1:
        return "gold"
    if rank == 2:
        return "silver"
    if rank == 3:
        return "bronze"
    return None


def is_international_tournament(tournament: dict[str, Any] | None) -> bool:
    if not tournament:
        return False
    if tournament.get("is_international") is True:
        return True
    if clean_text(tournament.get("fie_id")):
        return True

    metadata = tournament.get("metadata")
    metadata_values: list[str] = []
    if isinstance(metadata, dict):
        metadata_values = [
            str(value)
            for key, value in metadata.items()
            if key in {"source", "scraped_by", "event_source", "provider"} and value is not None
        ]

    source_text = " ".join(
        str(value)
        for value in [
            tournament.get("source"),
            tournament.get("source_id"),
            tournament.get("scope"),
            tournament.get("level"),
            *metadata_values,
        ]
        if value is not None
    )
    source_key = normalize_key(source_text)
    if any(term in source_key for term in INTERNATIONAL_SOURCE_TERMS):
        return True

    type_key = normalize_key(tournament.get("type"))
    return any(term in type_key for term in INTERNATIONAL_TYPE_TERMS)


def tournament_lookup(tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        values = tournaments.values()
    else:
        values = tournaments
    return {str(row["id"]): row for row in values if row.get("id") is not None}


def person_sort_key(person: Person) -> str:
    return person.key or ""


def clean_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def result_evidence(observation: dict[str, Any]) -> dict[str, Any]:
    tournament = observation.get("tournament") or {}
    result = observation.get("raw") or {}
    return clean_metadata(
        {
            "source_table": "fs_results",
            "result_id": clean_text(result.get("id")),
            "tournament_id": observation.get("tournament_id"),
            "tournament_name": clean_text(tournament.get("name")),
            "tournament_type": clean_text(tournament.get("type")),
            "date_precision": observation.get("date_precision"),
            "rank": observation.get("rank"),
            "medal": observation.get("medal"),
            "weapon": observation.get("weapon"),
            "category": observation.get("category"),
            "season": observation.get("season"),
            "fie_fencer_id": clean_text(result.get("fie_fencer_id") or result.get("fie_id")),
        }
    )


def ranking_evidence(observation: dict[str, Any]) -> dict[str, Any]:
    raw = observation.get("raw") or {}
    return clean_metadata(
        {
            "source_table": "fs_rankings_history",
            "fie_fencer_id": clean_text(raw.get("fie_fencer_id") or raw.get("fie_id")),
            "season": observation.get("season"),
            "weapon": observation.get("weapon"),
            "category": observation.get("category"),
            "rank": observation.get("rank"),
            "points": observation.get("points"),
            "country": observation.get("country"),
            "date_precision": observation.get("date_precision"),
        }
    )


def make_milestone(
    person: Person,
    *,
    milestone_type: str,
    milestone_date: date,
    title: str,
    description: str,
    source: str,
    tournament_id: str | None = None,
    weapon: str | None = None,
    season: str | None = None,
    rank: int | None = None,
    medal: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        **person.fields(),
        "milestone_type": milestone_type,
        "milestone_date": milestone_date.isoformat(),
        "tournament_id": tournament_id,
        "weapon": weapon,
        "season": season,
        "title": title,
        "description": description,
        "rank": rank,
        "medal": medal,
        "source": source,
        "metadata": metadata or {},
    }
    return row


def result_description(prefix: str, observation: dict[str, Any]) -> str:
    tournament_name = clean_text((observation.get("tournament") or {}).get("name"))
    rank = observation.get("rank")
    if tournament_name and rank:
        return f"{prefix} #{rank} at {tournament_name}."
    if tournament_name:
        return f"{prefix} at {tournament_name}."
    if rank:
        return f"{prefix} #{rank}."
    return prefix.rstrip(".") + "."


def event_sort_key(observation: dict[str, Any]) -> tuple[str, int, str]:
    rank = observation.get("rank")
    return (
        observation["event_date"].isoformat(),
        rank if isinstance(rank, int) else 999999,
        clean_text(observation.get("tournament_id") or observation.get("source_id")) or "",
    )


def choose_best_duplicate(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    current_rank = current.get("rank")
    candidate_rank = candidate.get("rank")
    if candidate_rank is not None and (current_rank is None or candidate_rank < current_rank):
        return candidate
    if candidate_rank == current_rank and event_sort_key(candidate) < event_sort_key(current):
        return candidate
    return current


def build_result_observations(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    resolver: IdentityResolver,
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    tournaments_by_id = tournament_lookup(tournaments)
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    skipped = 0
    duplicate_count = 0

    for index, result in enumerate(results):
        person = resolver.from_result(result)
        if not person:
            skipped += 1
            continue

        tournament_id = clean_text(result.get("tournament_id") or result.get("competition_id"))
        tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id else None
        event_dt, date_precision = result_event_date(result, tournament)
        if not event_dt:
            skipped += 1
            continue

        rank = to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        weapon = normalize_weapon(result.get("weapon") or (tournament or {}).get("weapon"))
        category = normalize_category(
            result.get("category") or (tournament or {}).get("category"),
            result.get("gender") or (tournament or {}).get("gender"),
        )
        season = season_label(result.get("season") or (tournament or {}).get("season"))
        source_id = clean_text(result.get("id")) or f"result:{index}"
        observation = {
            "person": person,
            "source_id": source_id,
            "raw": result,
            "tournament": tournament,
            "tournament_id": tournament_id,
            "event_date": event_dt,
            "date_precision": date_precision,
            "rank": rank,
            "medal": normalize_medal(result.get("medal"), rank),
            "weapon": weapon,
            "category": category,
            "category_level": category_level(category),
            "season": season,
            "season_sort": season_to_int(season),
        }
        key = (person.key, tournament_id or source_id)
        if key in deduped:
            duplicate_count += 1
        deduped[key] = choose_best_duplicate(deduped.get(key), observation)

    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in deduped.values():
        by_person[observation["person"].key].append(observation)
    for person_key in by_person:
        by_person[person_key].sort(key=event_sort_key)
    return dict(by_person), skipped, duplicate_count


def build_ranking_observations(
    rankings: list[dict[str, Any]],
    resolver: IdentityResolver,
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    skipped = 0
    duplicate_count = 0

    for index, row in enumerate(rankings):
        person = resolver.from_ranking(row)
        rank = to_int(row.get("rank"))
        event_dt, date_precision = ranking_event_date(row)
        if not person or rank is None or not event_dt:
            skipped += 1
            continue
        weapon = normalize_weapon(row.get("weapon"))
        category = normalize_category(row.get("category"), row.get("gender"))
        season = season_label(row.get("season"))
        observation = {
            "person": person,
            "source_id": f"ranking:{index}",
            "raw": row,
            "event_date": event_dt,
            "date_precision": date_precision,
            "rank": rank,
            "points": to_float(row.get("points")),
            "weapon": weapon,
            "category": category,
            "season": season,
            "season_sort": season_to_int(season),
            "country": normalize_country(row.get("country") or row.get("nationality")),
        }
        key = (
            person.key,
            season or "",
            weapon or "",
            category or "",
            observation.get("country") or "",
        )
        if key in deduped:
            duplicate_count += 1
        deduped[key] = choose_best_ranking_duplicate(deduped.get(key), observation)

    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in deduped.values():
        by_person[observation["person"].key].append(observation)
    for person_key in by_person:
        by_person[person_key].sort(key=lambda item: (item["event_date"].isoformat(), item["rank"], item.get("weapon") or ""))
    return dict(by_person), skipped, duplicate_count


def choose_best_ranking_duplicate(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    if candidate["rank"] < current["rank"]:
        return candidate
    if candidate["rank"] == current["rank"]:
        candidate_points = candidate.get("points")
        current_points = current.get("points")
        if candidate_points is not None and (current_points is None or candidate_points > current_points):
            return candidate
    return current


def add_first_result_milestones(rows: list[dict[str, Any]], observations_by_person: dict[str, list[dict[str, Any]]]) -> None:
    for observations in observations_by_person.values():
        person = observations[0]["person"]
        international = [obs for obs in observations if is_international_tournament(obs.get("tournament"))]
        if international:
            obs = international[0]
            rows.append(
                make_milestone(
                    person,
                    milestone_type="first_international_result",
                    milestone_date=obs["event_date"],
                    tournament_id=obs.get("tournament_id"),
                    weapon=obs.get("weapon"),
                    season=obs.get("season"),
                    rank=obs.get("rank"),
                    medal=obs.get("medal"),
                    title="First international result",
                    description=result_description("First recorded international result", obs),
                    source="fs_results",
                    metadata={"evidence": result_evidence(obs)},
                )
            )

        supported_result_milestones = international or [
            obs for obs in observations if not obs.get("tournament_id")
        ]
        ranked = [obs for obs in supported_result_milestones if obs.get("rank") is not None]
        for milestone_type, title, predicate in (
            ("first_top16", "First top-16 finish", lambda rank: rank <= 16),
            ("first_top8", "First top-8 finish", lambda rank: rank <= 8),
        ):
            candidates = [obs for obs in ranked if predicate(obs["rank"])]
            if candidates:
                obs = candidates[0]
                rows.append(
                    make_milestone(
                        person,
                        milestone_type=milestone_type,
                        milestone_date=obs["event_date"],
                        tournament_id=obs.get("tournament_id"),
                        weapon=obs.get("weapon"),
                        season=obs.get("season"),
                        rank=obs.get("rank"),
                        medal=obs.get("medal"),
                        title=title,
                        description=result_description("Finished", obs),
                        source="fs_results",
                        metadata={"evidence": result_evidence(obs)},
                    )
                )

        medals = [obs for obs in supported_result_milestones if obs.get("medal")]
        if medals:
            obs = medals[0]
            rows.append(
                make_milestone(
                    person,
                    milestone_type="first_medal",
                    milestone_date=obs["event_date"],
                    tournament_id=obs.get("tournament_id"),
                    weapon=obs.get("weapon"),
                    season=obs.get("season"),
                    rank=obs.get("rank"),
                    medal=obs.get("medal"),
                    title="First medal",
                    description=result_description(f"Won first {obs['medal']} medal", obs),
                    source="fs_results",
                    metadata={"evidence": result_evidence(obs)},
                )
            )
        golds = [obs for obs in supported_result_milestones if obs.get("medal") == "gold"]
        if golds:
            obs = golds[0]
            rows.append(
                make_milestone(
                    person,
                    milestone_type="first_gold",
                    milestone_date=obs["event_date"],
                    tournament_id=obs.get("tournament_id"),
                    weapon=obs.get("weapon"),
                    season=obs.get("season"),
                    rank=obs.get("rank"),
                    medal="gold",
                    title="First gold medal",
                    description=result_description("Won first gold medal", obs),
                    source="fs_results",
                    metadata={"evidence": result_evidence(obs)},
                )
            )


def add_personal_best_milestones(rows: list[dict[str, Any]], rankings_by_person: dict[str, list[dict[str, Any]]]) -> None:
    for observations in rankings_by_person.values():
        best = sorted(
            observations,
            key=lambda item: (
                item["rank"],
                item["event_date"].isoformat(),
                item.get("weapon") or "",
                item.get("category") or "",
            ),
        )[0]
        category_weapon = " ".join(
            part for part in [best.get("category"), best.get("weapon")] if part
        )
        if category_weapon and best.get("season"):
            description = f"Reached #{best['rank']} in {category_weapon} rankings for {best['season']}."
        elif category_weapon:
            description = f"Reached #{best['rank']} in {category_weapon} rankings."
        else:
            description = f"Reached personal best ranking #{best['rank']}."
        rows.append(
            make_milestone(
                best["person"],
                milestone_type="personal_best_ranking",
                milestone_date=best["event_date"],
                weapon=best.get("weapon"),
                season=best.get("season"),
                rank=best.get("rank"),
                title=f"Personal best ranking #{best['rank']}",
                description=description,
                source="fs_rankings_history",
                metadata={"evidence": ranking_evidence(best)},
            )
        )


def add_country_change_milestones(
    rows: list[dict[str, Any]],
    rankings_by_person: dict[str, list[dict[str, Any]]],
) -> int:
    skipped = 0
    for observations in rankings_by_person.values():
        by_season: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for obs in observations:
            if obs.get("country") and obs.get("season_sort") is not None:
                by_season[obs["season_sort"]].append(obs)

        summaries: list[dict[str, Any]] = []
        for season in sorted(by_season):
            countries = {obs["country"] for obs in by_season[season] if obs.get("country")}
            if len(countries) != 1:
                skipped += 1
                continue
            country = sorted(countries)[0]
            evidence = sorted(by_season[season], key=lambda item: (item["rank"], item.get("weapon") or ""))[0]
            summaries.append({"season": season, "country": country, "evidence": evidence})

        for previous, current in zip(summaries, summaries[1:]):
            if current["season"] != previous["season"] + 1:
                continue
            if normalize_key(previous["country"]) == normalize_key(current["country"]):
                continue
            current_obs = current["evidence"]
            rows.append(
                make_milestone(
                    current_obs["person"],
                    milestone_type="country_change",
                    milestone_date=current_obs["event_date"],
                    weapon=current_obs.get("weapon"),
                    season=current_obs.get("season"),
                    rank=current_obs.get("rank"),
                    title=f"Country change to {current['country']}",
                    description=(
                        f"Changed representation from {previous['country']} "
                        f"to {current['country']} in {current_obs.get('season')} rankings."
                    ),
                    source="fs_rankings_history",
                    metadata={
                        "previous_country": previous["country"],
                        "new_country": current["country"],
                        "previous_evidence": ranking_evidence(previous["evidence"]),
                        "evidence": ranking_evidence(current_obs),
                    },
                )
            )
    return skipped


def primary_weapon_for_season(observations: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None, bool]:
    counts = Counter(obs.get("weapon") for obs in observations if obs.get("weapon"))
    if not counts:
        return None, None, False
    most_common = counts.most_common()
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        return None, None, True
    weapon = most_common[0][0]
    weapon_obs = [obs for obs in observations if obs.get("weapon") == weapon]
    return weapon, sorted(weapon_obs, key=event_sort_key)[0], False


def add_weapon_transition_milestones(rows: list[dict[str, Any]], observations_by_person: dict[str, list[dict[str, Any]]]) -> int:
    skipped = 0
    for observations in observations_by_person.values():
        by_season: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for obs in observations:
            if obs.get("season_sort") is not None:
                by_season[obs["season_sort"]].append(obs)

        season_rows = []
        for season in sorted(by_season):
            weapon, evidence, ambiguous = primary_weapon_for_season(by_season[season])
            if ambiguous:
                skipped += 1
                continue
            if weapon and evidence:
                season_rows.append({"season": season, "weapon": weapon, "evidence": evidence})

        for previous, current in zip(season_rows, season_rows[1:]):
            if current["weapon"] == previous["weapon"]:
                continue
            obs = current["evidence"]
            rows.append(
                make_milestone(
                    obs["person"],
                    milestone_type="weapon_transition",
                    milestone_date=obs["event_date"],
                    tournament_id=obs.get("tournament_id"),
                    weapon=obs.get("weapon"),
                    season=obs.get("season"),
                    rank=obs.get("rank"),
                    medal=obs.get("medal"),
                    title=f"Weapon transition to {current['weapon']}",
                    description=f"Primary weapon changed from {previous['weapon']} to {current['weapon']} in {obs.get('season')}.",
                    source="fs_results",
                    metadata={
                        "from_weapon": previous["weapon"],
                        "to_weapon": current["weapon"],
                        "previous_evidence": result_evidence(previous["evidence"]),
                        "evidence": result_evidence(obs),
                    },
                )
            )
    return skipped


def add_category_transition_milestones(rows: list[dict[str, Any]], observations_by_person: dict[str, list[dict[str, Any]]]) -> None:
    for observations in observations_by_person.values():
        juniors = [obs for obs in observations if obs.get("category_level") == "Junior"]
        seniors = [obs for obs in observations if obs.get("category_level") == "Senior"]
        if not juniors or not seniors:
            continue
        first_junior = juniors[0]
        senior_candidates = [
            obs
            for obs in seniors
            if obs["event_date"] >= first_junior["event_date"]
        ]
        if not senior_candidates:
            continue
        first_senior = senior_candidates[0]
        rows.append(
            make_milestone(
                first_senior["person"],
                milestone_type="category_transition",
                milestone_date=first_senior["event_date"],
                tournament_id=first_senior.get("tournament_id"),
                weapon=first_senior.get("weapon"),
                season=first_senior.get("season"),
                rank=first_senior.get("rank"),
                medal=first_senior.get("medal"),
                title=f"Category transition to {first_senior['category_level']}",
                description=(
                    f"Moved from {first_junior['category_level']} to "
                    f"{first_senior['category_level']} competition."
                ),
                source="fs_results",
                metadata={
                    "from_category": first_junior["category_level"],
                    "to_category": first_senior["category_level"],
                    "previous_evidence": result_evidence(first_junior),
                    "evidence": result_evidence(first_senior),
                },
            )
        )


def add_status_signal_milestones(
    rows: list[dict[str, Any]],
    *,
    longevity: list[dict[str, Any]],
    fencer_stats: list[dict[str, Any]],
    resolver: IdentityResolver,
    previous_state: dict[str, Any] | None,
) -> dict[str, str]:
    status_by_person: dict[str, str] = {}
    previous_status = {}
    if isinstance(previous_state, dict) and isinstance(previous_state.get("status_by_person"), dict):
        previous_status = previous_state["status_by_person"]

    for row in longevity:
        person = resolver.from_result(row)
        if not person:
            continue
        status = clean_text(row.get("status"))
        if status:
            status_by_person[person.key] = status
        last_date = parse_date(row.get("last_competition_date") or row.get("updated_at"))
        if not status or not last_date:
            continue
        if status == "likely_retired":
            rows.append(
                make_milestone(
                    person,
                    milestone_type="retirement_signal",
                    milestone_date=last_date,
                    title="Likely retirement signal",
                    description=f"No recorded competition after {last_date.isoformat()}.",
                    source="fs_fencer_longevity",
                    metadata={"evidence": clean_metadata({"source_table": "fs_fencer_longevity", **row})},
                )
            )
        elif status == "active" and previous_status.get(person.key) == "likely_retired":
            rows.append(
                make_milestone(
                    person,
                    milestone_type="reactivation_signal",
                    milestone_date=last_date,
                    title="Reactivation signal",
                    description=f"Recorded new activity on {last_date.isoformat()} after a likely-retired signal.",
                    source="fs_fencer_longevity",
                    metadata={"evidence": clean_metadata({"source_table": "fs_fencer_longevity", **row})},
                )
            )

    for row in fencer_stats:
        person = resolver.from_identity_id(row.get("identity_id"))
        last_bout = parse_date(row.get("last_bout_at"))
        if not person or not last_bout or previous_status.get(person.key) != "likely_retired":
            continue
        status_by_person.setdefault(person.key, "active")
        rows.append(
            make_milestone(
                person,
                milestone_type="reactivation_signal",
                milestone_date=last_bout,
                weapon=normalize_weapon(row.get("weapon")),
                title="Reactivation signal",
                description=f"Recorded bout activity on {last_bout.isoformat()} after a likely-retired signal.",
                source="fs_fencer_stats",
                metadata={"evidence": clean_metadata({"source_table": "fs_fencer_stats", **row})},
            )
        )
    return status_by_person


def milestone_person_key(row: dict[str, Any]) -> str:
    return (
        clean_text(row.get("identity_id"))
        or clean_text(row.get("fencer_id"))
        or clean_text(row.get("fie_id"))
        or normalize_key(row.get("fencer_name"))
    )


def dedupe_and_sort_milestones(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    deduped = 0
    for row in rows:
        key = (
            milestone_person_key(row),
            row["milestone_type"],
            clean_text(row.get("tournament_id")) or "__no_tournament__",
            row["milestone_date"],
        )
        if key in by_key:
            deduped += 1
            continue
        by_key[key] = row
    return (
        sorted(
            by_key.values(),
            key=lambda item: (
                milestone_person_key(item),
                item["milestone_date"],
                item["milestone_type"],
                clean_text(item.get("tournament_id")) or "",
            ),
        ),
        deduped,
    )


def build_career_milestones(
    *,
    results: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    fencer_stats: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
    tournaments: list[dict[str, Any]] | dict[Any, dict[str, Any]],
    longevity: list[dict[str, Any]] | None = None,
    previous_state: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolver = IdentityResolver(fencers, identities)
    result_observations, skipped_results, deduped_results = build_result_observations(results, tournaments, resolver)
    ranking_observations, skipped_rankings, deduped_rankings = build_ranking_observations(rankings, resolver)

    rows: list[dict[str, Any]] = []
    add_first_result_milestones(rows, result_observations)
    add_personal_best_milestones(rows, ranking_observations)
    country_skips = add_country_change_milestones(rows, ranking_observations)
    weapon_skips = add_weapon_transition_milestones(rows, result_observations)
    add_category_transition_milestones(rows, result_observations)
    status_by_person = add_status_signal_milestones(
        rows,
        longevity=longevity or [],
        fencer_stats=fencer_stats,
        resolver=resolver,
        previous_state=previous_state,
    )
    rows, deduped_milestones = dedupe_and_sort_milestones(rows)

    summary = {
        "milestone_rows": len(rows),
        "skipped": skipped_results + skipped_rankings + country_skips + weapon_skips,
        "deduped": deduped_results + deduped_rankings + deduped_milestones,
        "status_by_person": status_by_person,
    }
    return rows, summary


def fetch_all(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def fetch_with_fallbacks(
    client,
    table: str,
    select_options: list[str],
    *,
    page_size: int,
    required: bool,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
            print(f"  Select fallback for {table}: {exc}")
    if required and last_error:
        raise last_error
    return []


def load_inputs(client, *, page_size: int) -> dict[str, list[dict[str, Any]]]:
    return {
        "results": fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size, required=False),
        "rankings": fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size, required=False),
        "fencer_stats": fetch_with_fallbacks(client, "fs_fencer_stats", FENCER_STATS_SELECTS, page_size=page_size, required=False),
        "fencers": fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size, required=False),
        "identities": fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size, required=False),
        "tournaments": fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size, required=False),
        "longevity": fetch_with_fallbacks(client, "fs_fencer_longevity", LONGEVITY_SELECTS, page_size=page_size, required=False),
    }


def upsert_milestones(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_career_milestones").upsert(
                batch,
                on_conflict=MILESTONE_CONFLICT_COLUMNS,
            ).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  fs_career_milestones upsert batch {index // batch_size} failed: {exc}")
            failed += len(batch)
    return written, failed


def compute_career_milestones(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    previous_state = get_state(SOURCE, "last_run") if update_state else None

    try:
        inputs = load_inputs(client, page_size=page_size)
        rows, build_summary = build_career_milestones(
            results=inputs["results"],
            rankings=inputs["rankings"],
            fencer_stats=inputs["fencer_stats"],
            fencers=inputs["fencers"],
            identities=inputs["identities"],
            tournaments=inputs["tournaments"],
            longevity=inputs["longevity"],
            previous_state=previous_state if isinstance(previous_state, dict) else None,
        )
        written, failed = upsert_milestones(client, rows, batch_size=batch_size) if rows else (0, 0)
        summary = {
            "results_read": len(inputs["results"]),
            "rankings_read": len(inputs["rankings"]),
            "fencer_stats_read": len(inputs["fencer_stats"]),
            "fencers_read": len(inputs["fencers"]),
            "identity_rows": len(inputs["identities"]),
            "tournaments_read": len(inputs["tournaments"]),
            "longevity_rows": len(inputs["longevity"]),
            "milestone_rows": len(rows),
            "written": written,
            "failed": failed,
            "skipped": build_summary["skipped"],
            "deduped": build_summary["deduped"],
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "status_by_person": build_summary["status_by_person"],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=summary["skipped"], metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Career milestone computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_career_milestones()
    print(
        "Career milestone computation complete - "
        f"{summary['milestone_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} rows skipped, "
        f"{summary['failed']} rows failed"
    )


if __name__ == "__main__":
    main()
