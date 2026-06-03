import hashlib
import os
import re
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_trivia"

FENCER_COLUMNS = "id,name,country,weapon,category,date_of_birth"
CAREER_COLUMNS = (
    "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals,"
    "best_rank,weapons_used,categories_competed,first_season,last_season"
)

SENSITIVE_BIO_FIELDS = {
    "address",
    "age",
    "birth_date",
    "birth_place",
    "biography",
    "bio",
    "club",
    "date",
    "date_of_birth",
    "dob",
    "email",
    "family",
    "hand",
    "height",
    "home",
    "instagram",
    "parent",
    "phone",
    "school",
    "weight",
}
YOUTH_CATEGORY_MARKERS = ("cadet", "junior", "youth", "u17", "u20", "under")
ADULT_CATEGORY_MARKERS = ("senior", "veteran", "masters")


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if clean_text(value) else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := clean_text(item))]
    return [str(value)] if clean_text(value) else []


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if key in {"e", "epee", "épée"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def age_on(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def category_texts(fencer: dict[str, Any], career: dict[str, Any] | None) -> list[str]:
    values = text_list(fencer.get("category"))
    if career:
        values.extend(text_list(career.get("categories_competed")))
    return values


def has_adult_category(categories: list[str]) -> bool:
    return any(marker in category.casefold() for category in categories for marker in ADULT_CATEGORY_MARKERS)


def has_youth_category(categories: list[str]) -> bool:
    return any(marker in category.casefold() for category in categories for marker in YOUTH_CATEGORY_MARKERS)


def is_minor_or_youth_profile(
    fencer: dict[str, Any],
    career: dict[str, Any] | None,
    today: date,
) -> bool:
    born = parse_date(fencer.get("date_of_birth") or fencer.get("dob") or fencer.get("birth_date"))
    if born and age_on(born, today) < 18:
        return True

    categories = category_texts(fencer, career)
    if has_adult_category(categories):
        return False
    return has_youth_category(categories)


def option_sort_key(value: str) -> tuple[int, int | str, str]:
    text = clean_text(value) or ""
    number_match = re.fullmatch(r"#?(-?\d+)", text)
    if number_match:
        return (0, int(number_match.group(1)), text)
    return (1, text.casefold(), text)


def make_options(answer: Any, values: list[Any], *, min_options: int = 3, max_options: int = 4) -> list[str] | None:
    answer_text = clean_text(answer)
    if not answer_text:
        return None
    distractors = sorted(
        {text for value in values if (text := clean_text(value)) and text != answer_text},
        key=option_sort_key,
    )
    if len(distractors) + 1 < min_options:
        return None
    selected = distractors[: max_options - 1] + [answer_text]
    return sorted(selected, key=option_sort_key)


def source_metadata(table: str, row_id: Any, columns: list[str]) -> dict[str, list[dict[str, Any]]]:
    return {
        "sources": [
            {
                "table": table,
                "row_id": clean_text(row_id),
                "columns": columns,
            }
        ]
    }


def source_columns_are_safe(metadata: dict[str, Any]) -> bool:
    for source in metadata.get("sources") or []:
        for column in source.get("columns") or []:
            if str(column).casefold() in SENSITIVE_BIO_FIELDS:
                return False
    return True


def deterministic_id(question_type: str, fencer_id: str, answer: str) -> str:
    digest = hashlib.sha256(f"{question_type}|{fencer_id}|{answer}".encode("utf-8")).hexdigest()[:16]
    return f"trivia:{question_type}:{digest}"


def question_row(
    *,
    fencer_id: str,
    question_type: str,
    question: str,
    answer: str,
    options: list[str],
    metadata: dict[str, Any],
    generated_at: str,
) -> dict[str, Any] | None:
    if not source_columns_are_safe(metadata):
        return None
    return {
        "id": deterministic_id(question_type, fencer_id, answer),
        "fencer_id": fencer_id,
        "question_type": question_type,
        "question": question,
        "answer": answer,
        "options": options,
        "source_metadata": metadata,
        "safety_flags": {"minor": False, "sensitive_bio": False},
        "generated_at": generated_at,
    }


def career_by_fencer(career_stats: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["fencer_id"]): row
        for row in career_stats
        if clean_text(row.get("fencer_id"))
    }


def eligible_fact_rows(
    fencers: list[dict[str, Any]],
    career_stats: list[dict[str, Any]],
    today: date,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    careers = career_by_fencer(career_stats)
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for fencer in sorted(fencers, key=lambda row: (clean_text(row.get("name")) or "", clean_text(row.get("id")) or "")):
        fencer_id = clean_text(fencer.get("id"))
        name = clean_text(fencer.get("name"))
        if not fencer_id or not name:
            continue
        career = careers.get(fencer_id)
        if not career:
            continue
        if is_minor_or_youth_profile(fencer, career, today):
            continue
        rows.append((fencer, career))
    return rows


def primary_weapon(fencer: dict[str, Any], career: dict[str, Any]) -> str | None:
    career_weapons = sorted({weapon for value in text_list(career.get("weapons_used")) if (weapon := normalize_weapon(value))})
    if len(career_weapons) == 1:
        return career_weapons[0]
    return normalize_weapon(fencer.get("weapon"))


def medal_total(career: dict[str, Any]) -> int:
    return sum(
        to_int(career.get(column)) or 0
        for column in ("gold_medals", "silver_medals", "bronze_medals")
    )


def build_trivia_questions(
    fencers: list[dict[str, Any]],
    career_stats: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    today = today or datetime.now(timezone.utc).date()
    eligible = eligible_fact_rows(fencers, career_stats, today)

    country_values = [clean_text(fencer.get("country")) for fencer, _career in eligible]
    weapon_values = [primary_weapon(fencer, career) for fencer, career in eligible]
    medal_values = [str(total) for _fencer, career in eligible if (total := medal_total(career)) > 0]
    best_rank_values = [f"#{rank}" for _fencer, career in eligible if (rank := to_int(career.get("best_rank")))]
    first_season_values = [clean_text(career.get("first_season")) for _fencer, career in eligible]

    questions: list[dict[str, Any]] = []

    for fencer, career in eligible:
        fencer_id = clean_text(fencer.get("id"))
        name = clean_text(fencer.get("name"))
        if not fencer_id or not name:
            continue

        country = clean_text(fencer.get("country"))
        if country and (options := make_options(country, country_values, min_options=3)):
            row = question_row(
                fencer_id=fencer_id,
                question_type="country",
                question=f"Which country is {name} listed as representing?",
                answer=country,
                options=options,
                metadata=source_metadata("fs_fencers", fencer_id, ["id", "name", "country"]),
                generated_at=generated_at,
            )
            if row:
                questions.append(row)

        weapon = primary_weapon(fencer, career)
        if weapon and (options := make_options(weapon, weapon_values, min_options=3)):
            row = question_row(
                fencer_id=fencer_id,
                question_type="weapon",
                question=f"Which weapon appears in {name}'s verified career data?",
                answer=weapon,
                options=options,
                metadata=source_metadata("fs_fencer_career_stats", fencer_id, ["fencer_id", "weapons_used"]),
                generated_at=generated_at,
            )
            if row:
                questions.append(row)

        total_medals = medal_total(career)
        if total_medals > 0 and (options := make_options(str(total_medals), medal_values, min_options=3)):
            row = question_row(
                fencer_id=fencer_id,
                question_type="career_medal_total",
                question=f"How many career medals are recorded for {name}?",
                answer=str(total_medals),
                options=options,
                metadata=source_metadata(
                    "fs_fencer_career_stats",
                    fencer_id,
                    ["fencer_id", "gold_medals", "silver_medals", "bronze_medals"],
                ),
                generated_at=generated_at,
            )
            if row:
                questions.append(row)

        best_rank = to_int(career.get("best_rank"))
        if best_rank and (options := make_options(f"#{best_rank}", best_rank_values, min_options=3)):
            row = question_row(
                fencer_id=fencer_id,
                question_type="best_rank",
                question=f"What is {name}'s best recorded career placement?",
                answer=f"#{best_rank}",
                options=options,
                metadata=source_metadata("fs_fencer_career_stats", fencer_id, ["fencer_id", "best_rank"]),
                generated_at=generated_at,
            )
            if row:
                questions.append(row)

        first_season = clean_text(career.get("first_season"))
        if first_season and (options := make_options(first_season, first_season_values, min_options=3)):
            row = question_row(
                fencer_id=fencer_id,
                question_type="first_season",
                question=f"Which season is {name}'s first recorded career season?",
                answer=first_season,
                options=options,
                metadata=source_metadata("fs_fencer_career_stats", fencer_id, ["fencer_id", "first_season"]),
                generated_at=generated_at,
            )
            if row:
                questions.append(row)

    return sorted(questions, key=lambda row: (row["question_type"], row["fencer_id"], row["id"]))


def count_skipped_fencers(
    fencers: list[dict[str, Any]],
    career_stats: list[dict[str, Any]],
    today: date,
) -> int:
    eligible_ids = {fencer["id"] for fencer, _career in eligible_fact_rows(fencers, career_stats, today)}
    career_ids = set(career_by_fencer(career_stats))
    return sum(
        1
        for fencer in fencers
        if clean_text(fencer.get("id")) in career_ids and clean_text(fencer.get("id")) not in eligible_ids
    )


def fetch_all(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
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
            break
        offset += page_size
    return rows


def batch_upsert(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_trivia_questions").upsert(batch, on_conflict="id").execute()
        written += len(batch)
    return written


def compute_trivia_questions(
    client=None,
    *,
    generated_at: str | None = None,
    today: date | None = None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    today = today or datetime.now(timezone.utc).date()
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    try:
        client = client or get_supabase_client()
        fencers = fetch_all(client, "fs_fencers", FENCER_COLUMNS, page_size=page_size)
        career_stats = fetch_all(client, "fs_fencer_career_stats", CAREER_COLUMNS, page_size=page_size)
        questions = build_trivia_questions(
            fencers,
            career_stats,
            generated_at=generated_at,
            today=today,
        )
        written = batch_upsert(client, questions, batch_size=batch_size) if questions else 0
        skipped = count_skipped_fencers(fencers, career_stats, today)

        summary = {
            "fencers_read": len(fencers),
            "career_stats_read": len(career_stats),
            "questions_generated": len(questions),
            "written": written,
            "skipped_fencers": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(timezone.utc).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Trivia computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_trivia_questions()
    print(
        "Trivia computation complete - "
        f"{summary['questions_generated']} questions built, {summary['written']} rows upserted"
    )


if __name__ == "__main__":
    main()
