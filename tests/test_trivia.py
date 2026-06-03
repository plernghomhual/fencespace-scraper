import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ALICE = "00000000-0000-0000-0000-000000000001"
FENCER_BOB = "00000000-0000-0000-0000-000000000002"
FENCER_CAROL = "00000000-0000-0000-0000-000000000003"
FENCER_DAN = "00000000-0000-0000-0000-000000000004"
FENCER_MINOR = "00000000-0000-0000-0000-000000000005"
FENCER_EVE = "00000000-0000-0000-0000-000000000006"
NOW = "2026-06-02T12:00:00+00:00"


def adult_fencer_rows():
    return [
        {
            "id": FENCER_ALICE,
            "name": "Alice Example",
            "country": "USA",
            "weapon": "Foil",
            "category": "Senior",
            "date_of_birth": "1995-03-11",
            "height": "170",
        },
        {
            "id": FENCER_BOB,
            "name": "Bob Example",
            "country": "FRA",
            "weapon": "Epee",
            "category": "Senior",
        },
        {
            "id": FENCER_CAROL,
            "name": "Carol Example",
            "country": "ITA",
            "weapon": "Sabre",
            "category": "Senior",
        },
        {
            "id": FENCER_DAN,
            "name": "Dan Example",
            "country": "JPN",
            "weapon": "Epee",
            "category": "Senior",
        },
    ]


def career_rows():
    return [
        {
            "fencer_id": FENCER_ALICE,
            "total_competitions": 24,
            "gold_medals": 3,
            "silver_medals": 1,
            "bronze_medals": 0,
            "best_rank": 1,
            "weapons_used": ["Foil"],
            "categories_competed": ["Women's Senior"],
            "first_season": "2018",
            "last_season": "2026",
        },
        {
            "fencer_id": FENCER_BOB,
            "total_competitions": 18,
            "gold_medals": 1,
            "silver_medals": 2,
            "bronze_medals": 1,
            "best_rank": 2,
            "weapons_used": ["Epee"],
            "categories_competed": ["Men's Senior"],
            "first_season": "2019",
            "last_season": "2025",
        },
        {
            "fencer_id": FENCER_CAROL,
            "total_competitions": 15,
            "gold_medals": 0,
            "silver_medals": 1,
            "bronze_medals": 2,
            "best_rank": 3,
            "weapons_used": ["Sabre"],
            "categories_competed": ["Women's Senior"],
            "first_season": "2020",
            "last_season": "2026",
        },
        {
            "fencer_id": FENCER_DAN,
            "total_competitions": 12,
            "gold_medals": 0,
            "silver_medals": 0,
            "bronze_medals": 1,
            "best_rank": 8,
            "weapons_used": ["Epee"],
            "categories_competed": ["Men's Senior"],
            "first_season": "2021",
            "last_season": "2024",
        },
    ]


def test_build_trivia_questions_is_deterministic_and_fact_backed():
    from compute_trivia import build_trivia_questions

    first = build_trivia_questions(
        adult_fencer_rows(),
        career_rows(),
        generated_at=NOW,
        today=date(2026, 6, 2),
    )
    second = build_trivia_questions(
        list(reversed(adult_fencer_rows())),
        list(reversed(career_rows())),
        generated_at=NOW,
        today=date(2026, 6, 2),
    )

    assert first == second
    assert len(first) >= 12
    assert len({question["id"] for question in first}) == len(first)

    by_key = {(question["question_type"], question["fencer_id"]): question for question in first}

    country = by_key[("country", FENCER_ALICE)]
    assert country["question"] == "Which country is Alice Example listed as representing?"
    assert country["answer"] == "USA"
    assert country["options"] == ["FRA", "ITA", "JPN", "USA"]
    assert country["source_metadata"] == {
        "sources": [
            {
                "table": "fs_fencers",
                "row_id": FENCER_ALICE,
                "columns": ["id", "name", "country"],
            }
        ]
    }

    weapon = by_key[("weapon", FENCER_ALICE)]
    assert weapon["answer"] == "Foil"
    assert weapon["options"] == ["Epee", "Foil", "Sabre"]
    assert weapon["source_metadata"]["sources"] == [
        {
            "table": "fs_fencer_career_stats",
            "row_id": FENCER_ALICE,
            "columns": ["fencer_id", "weapons_used"],
        }
    ]

    medals = by_key[("career_medal_total", FENCER_ALICE)]
    assert medals["answer"] == "4"
    assert medals["options"] == ["1", "3", "4"]

    assert "date_of_birth" not in repr(first)
    assert "height" not in repr(first)
    assert all(question["safety_flags"] == {"minor": False, "sensitive_bio": False} for question in first)


def test_build_trivia_questions_filters_minors_and_sensitive_question_types():
    from compute_trivia import build_trivia_questions

    fencers = adult_fencer_rows() + [
        {
            "id": FENCER_MINOR,
            "name": "Young Example",
            "country": "CAN",
            "weapon": "Foil",
            "category": "Cadet",
            "date_of_birth": "2010-09-15",
            "birth_place": "Private City",
        }
    ]
    careers = career_rows() + [
        {
            "fencer_id": FENCER_MINOR,
            "total_competitions": 4,
            "gold_medals": 1,
            "silver_medals": 0,
            "bronze_medals": 0,
            "best_rank": 1,
            "weapons_used": ["Foil"],
            "categories_competed": ["Women's Cadet"],
            "first_season": "2025",
            "last_season": "2026",
        }
    ]

    questions = build_trivia_questions(fencers, careers, generated_at=NOW, today=date(2026, 6, 2))

    assert FENCER_MINOR not in {question["fencer_id"] for question in questions}
    assert "Young Example" not in repr(questions)
    assert "birth_place" not in repr(questions)
    assert "Private City" not in repr(questions)


def test_options_keep_answer_when_distractor_pool_exceeds_max_options():
    from compute_trivia import build_trivia_questions

    fencers = adult_fencer_rows() + [
        {
            "id": FENCER_EVE,
            "name": "Eve Example",
            "country": "AUS",
            "weapon": "Sabre",
            "category": "Senior",
        }
    ]
    careers = career_rows() + [
        {
            "fencer_id": FENCER_EVE,
            "total_competitions": 9,
            "gold_medals": 0,
            "silver_medals": 0,
            "bronze_medals": 0,
            "best_rank": 16,
            "weapons_used": ["Sabre"],
            "categories_competed": ["Women's Senior"],
            "first_season": "2022",
            "last_season": "2026",
        }
    ]

    questions = build_trivia_questions(fencers, careers, generated_at=NOW, today=date(2026, 6, 2))
    country = {
        (question["question_type"], question["fencer_id"]): question
        for question in questions
    }[("country", FENCER_ALICE)]

    assert country["answer"] == "USA"
    assert country["answer"] in country["options"]
    assert country["options"] == ["AUS", "FRA", "ITA", "USA"]


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.tables[self.table_name]
            return FakeResult(rows[self.range_start : self.range_end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation for {self.table_name}")


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_fencers": adult_fencer_rows(),
            "fs_fencer_career_stats": career_rows(),
        }
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_trivia_questions_fetches_sources_and_upserts_questions():
    from compute_trivia import compute_trivia_questions

    client = FakeSupabase()

    summary = compute_trivia_questions(
        client=client,
        generated_at=NOW,
        today=date(2026, 6, 2),
        page_size=2,
        log_run=False,
        update_state=False,
    )

    assert summary["fencers_read"] == 4
    assert summary["career_stats_read"] == 4
    assert summary["questions_generated"] == summary["written"]
    assert summary["skipped_fencers"] == 0

    assert ("fs_fencers", "id,name,country,weapon,category,date_of_birth") in client.selects
    assert (
        "fs_fencer_career_stats",
        "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals,best_rank,weapons_used,categories_competed,first_season,last_season",
    ) in client.selects

    upsert = client.upserts[0]
    assert upsert["table"] == "fs_trivia_questions"
    assert upsert["on_conflict"] == "id"
    assert len(upsert["rows"]) == summary["questions_generated"]
    assert all(row["generated_at"] == NOW for row in upsert["rows"])


def test_trivia_questions_migration_defines_fact_checked_storage():
    migration = Path("supabase/migrations/20260602_trivia_questions.sql")

    sql = migration.read_text(encoding="utf-8").casefold()

    assert "create table if not exists public.fs_trivia_questions" in sql
    assert "question_type text not null" in sql
    assert "options jsonb not null" in sql
    assert "source_metadata jsonb not null" in sql
    assert "safety_flags jsonb not null" in sql
    assert "alter table public.fs_trivia_questions enable row level security" in sql
    assert "idx_fs_trivia_questions_fencer_id" in sql
