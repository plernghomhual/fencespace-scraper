import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


IDENTITY_ALICE = "11111111-1111-1111-1111-111111111111"
IDENTITY_BOB = "22222222-2222-2222-2222-222222222222"
FENCER_ALICE_FOIL = "00000000-0000-0000-0000-0000000000a1"
FENCER_ALICE_EPEE = "00000000-0000-0000-0000-0000000000a2"
FENCER_BOB = "00000000-0000-0000-0000-0000000000b1"
T_LOCAL = "aaaaaaaa-0000-0000-0000-000000000001"
T_WC_2024 = "aaaaaaaa-0000-0000-0000-000000000002"
T_GP_2024 = "aaaaaaaa-0000-0000-0000-000000000003"
T_WC_2025 = "aaaaaaaa-0000-0000-0000-000000000004"


def milestone_by_type(rows):
    return {row["milestone_type"]: row for row in rows}


def base_identities():
    return [
        {
            "id": IDENTITY_ALICE,
            "canonical_name": "Alice Example",
            "fie_ids": ["1001"],
            "fs_fencer_row_ids": [FENCER_ALICE_FOIL, FENCER_ALICE_EPEE],
        },
        {
            "id": IDENTITY_BOB,
            "canonical_name": "Bob Example",
            "fie_ids": ["2002"],
            "fs_fencer_row_ids": [FENCER_BOB],
        },
    ]


def base_fencers():
    return [
        {"id": FENCER_ALICE_FOIL, "fie_id": "1001", "name": "Alice Example", "country": "USA"},
        {"id": FENCER_ALICE_EPEE, "fie_id": "1001", "name": "Alice Example", "country": "USA"},
        {"id": FENCER_BOB, "fie_id": "2002", "name": "Bob Example", "country": "Italy"},
    ]


def base_tournaments():
    return [
        {
            "id": T_LOCAL,
            "name": "Local Open",
            "season": "2024",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "start_date": "2023-09-01",
            "type": "Local",
        },
        {
            "id": T_WC_2024,
            "name": "Doha World Cup",
            "season": "2024",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "start_date": "2024-01-12",
            "type": "World Cup",
            "fie_id": "9001",
            "metadata": {"scraped_by": "scrape_fie_history"},
        },
        {
            "id": T_GP_2024,
            "name": "Seoul Grand Prix",
            "season": "2024",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "start_date": "2024-03-14",
            "type": "Grand Prix",
            "fie_id": "9002",
        },
        {
            "id": T_WC_2025,
            "name": "Paris World Cup",
            "season": "2025",
            "weapon": "Epee",
            "gender": "Women",
            "category": "Senior",
            "start_date": "2025-02-20",
            "type": "World Cup",
            "fie_id": "9003",
        },
    ]


def test_build_milestones_detects_first_medal_gold_and_top_placements():
    from compute_career_milestones import build_career_milestones

    results = [
        {"id": "r-local", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_LOCAL, "rank": 12},
        {"id": "r-top16", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_WC_2024, "rank": 16},
        {"id": "r-medal", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_GP_2024, "rank": 2, "medal": "silver"},
        {"id": "r-gold", "fencer_id": FENCER_ALICE_EPEE, "tournament_id": T_WC_2025, "rank": 1},
    ]

    rows, summary = build_career_milestones(
        results=results,
        rankings=[],
        fencer_stats=[],
        fencers=base_fencers(),
        identities=base_identities(),
        tournaments=base_tournaments(),
    )

    by_type = milestone_by_type(rows)
    assert summary["skipped"] == 0
    assert by_type["first_international_result"]["milestone_date"] == "2024-01-12"
    assert by_type["first_international_result"]["tournament_id"] == T_WC_2024
    assert by_type["first_international_result"]["source"] == "fs_results"
    assert by_type["first_international_result"]["metadata"]["evidence"]["result_id"] == "r-top16"

    assert by_type["first_top16"]["rank"] == 16
    assert by_type["first_top16"]["title"] == "First top-16 finish"

    assert by_type["first_top8"]["rank"] == 2
    assert by_type["first_top8"]["medal"] == "silver"
    assert by_type["first_top8"]["description"] == "Finished #2 at Seoul Grand Prix."

    assert by_type["first_medal"]["rank"] == 2
    assert by_type["first_medal"]["medal"] == "silver"
    assert by_type["first_medal"]["title"] == "First medal"

    assert by_type["first_gold"]["milestone_date"] == "2025-02-20"
    assert by_type["first_gold"]["rank"] == 1
    assert by_type["first_gold"]["medal"] == "gold"
    assert by_type["first_gold"]["title"] == "First gold medal"

    assert {row["identity_id"] for row in rows} == {IDENTITY_ALICE}
    assert all("person_key" not in row and "tournament_key" not in row for row in rows)


def test_personal_best_ranking_uses_best_rank_and_source_evidence():
    from compute_career_milestones import build_career_milestones

    rankings = [
        {
            "fie_fencer_id": "1001",
            "season": 2022,
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "rank": 9,
            "points": 98.5,
            "country": "USA",
        },
        {
            "fie_fencer_id": "1001",
            "season": 2023,
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "rank": 3,
            "points": 148.0,
            "country": "USA",
        },
        {
            "fie_fencer_id": "1001",
            "season": 2024,
            "weapon": "Epee",
            "gender": "Women",
            "category": "Senior",
            "rank": 5,
            "points": 120.0,
            "country": "USA",
        },
    ]

    rows, summary = build_career_milestones(
        results=[],
        rankings=rankings,
        fencer_stats=[],
        fencers=base_fencers(),
        identities=base_identities(),
        tournaments=[],
    )

    personal_best = milestone_by_type(rows)["personal_best_ranking"]
    assert summary["skipped"] == 0
    assert personal_best["milestone_date"] == "2023-07-01"
    assert personal_best["rank"] == 3
    assert personal_best["weapon"] == "Foil"
    assert personal_best["season"] == "2023"
    assert personal_best["title"] == "Personal best ranking #3"
    assert personal_best["description"] == "Reached #3 in Women's Senior Foil rankings for 2023."
    assert personal_best["metadata"]["evidence"]["points"] == 148.0
    assert personal_best["metadata"]["evidence"]["fie_fencer_id"] == "1001"


def test_duplicate_identity_rows_dedupe_to_one_person_milestone():
    from compute_career_milestones import build_career_milestones

    results = [
        {"id": "r-a1", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_GP_2024, "rank": 3},
        {"id": "r-a2", "fencer_id": FENCER_ALICE_EPEE, "tournament_id": T_GP_2024, "rank": 3},
    ]
    rankings = [
        {"fie_fencer_id": "1001", "season": 2024, "weapon": "Foil", "category": "Senior", "rank": 5, "country": "USA"},
        {"fie_fencer_id": "1001", "season": 2024, "weapon": "Foil", "category": "Senior", "rank": 5, "country": "USA"},
    ]

    rows, summary = build_career_milestones(
        results=results,
        rankings=rankings,
        fencer_stats=[],
        fencers=base_fencers(),
        identities=base_identities(),
        tournaments=base_tournaments(),
    )

    assert summary["deduped"] >= 1
    assert [row["milestone_type"] for row in rows].count("first_medal") == 1
    assert [row["milestone_type"] for row in rows].count("personal_best_ranking") == 1
    assert {row["identity_id"] for row in rows} == {IDENTITY_ALICE}
    assert {row["fencer_id"] for row in rows} == {FENCER_ALICE_FOIL}


def test_country_weapon_and_category_transitions_are_evidence_backed():
    from compute_career_milestones import build_career_milestones

    results = [
        {"id": "r-junior", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_WC_2024, "rank": 20, "category": "Junior"},
        {"id": "r-senior", "fencer_id": FENCER_ALICE_EPEE, "tournament_id": T_WC_2025, "rank": 10, "weapon": "Epee", "category": "Senior"},
    ]
    rankings = [
        {"fie_fencer_id": "1001", "season": 2024, "weapon": "Foil", "category": "Junior", "rank": 20, "country": "USA"},
        {"fie_fencer_id": "1001", "season": 2025, "weapon": "Epee", "category": "Senior", "rank": 10, "country": "France"},
    ]

    rows, summary = build_career_milestones(
        results=results,
        rankings=rankings,
        fencer_stats=[],
        fencers=base_fencers(),
        identities=base_identities(),
        tournaments=base_tournaments(),
    )

    by_type = milestone_by_type(rows)
    assert summary["skipped"] == 0
    assert by_type["country_change"]["milestone_date"] == "2025-07-01"
    assert by_type["country_change"]["title"] == "Country change to France"
    assert by_type["country_change"]["metadata"]["previous_country"] == "United States"

    assert by_type["weapon_transition"]["milestone_date"] == "2025-02-20"
    assert by_type["weapon_transition"]["title"] == "Weapon transition to Epee"
    assert by_type["weapon_transition"]["metadata"]["from_weapon"] == "Foil"

    assert by_type["category_transition"]["milestone_date"] == "2025-02-20"
    assert by_type["category_transition"]["title"] == "Category transition to Senior"
    assert by_type["category_transition"]["metadata"]["from_category"] == "Junior"


def test_ambiguous_rows_are_skipped_instead_of_guessed():
    from compute_career_milestones import build_career_milestones

    rows, summary = build_career_milestones(
        results=[
            {"id": "missing-person", "tournament_id": T_GP_2024, "rank": 1, "name": "Unlinked Name"},
            {"id": "missing-date", "fencer_id": FENCER_BOB, "rank": 1},
        ],
        rankings=[
            {"fie_fencer_id": "2002", "season": 2024, "weapon": "Epee", "category": "Senior", "rank": 8, "country": "Italy"},
            {"fie_fencer_id": "2002", "season": 2025, "weapon": "Epee", "category": "Senior", "rank": 6, "country": "France"},
            {"fie_fencer_id": "2002", "season": 2025, "weapon": "Epee", "category": "Senior", "rank": 7, "country": "Italy"},
        ],
        fencer_stats=[],
        fencers=base_fencers(),
        identities=base_identities(),
        tournaments=base_tournaments(),
    )

    assert summary["skipped"] >= 2
    assert "country_change" not in milestone_by_type(rows)
    assert all(row["fencer_name"] != "Unlinked Name" for row in rows)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def limit(self, _count):
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = list(rows)
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            if self.name not in self.client.tables:
                raise RuntimeError(f"missing table {self.name}")
            return FakeResult(self.client.tables[self.name][self.range_start : self.range_end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_career_milestones_fetches_sources_and_upserts_idempotently():
    from compute_career_milestones import MILESTONE_CONFLICT_COLUMNS, compute_career_milestones

    tables = {
        "fs_results": [
            {"id": "r-top16", "fencer_id": FENCER_ALICE_FOIL, "tournament_id": T_WC_2024, "rank": 16},
            {"id": "r-medal", "fencer_id": FENCER_ALICE_EPEE, "tournament_id": T_GP_2024, "rank": 2, "medal": "silver"},
        ],
        "fs_rankings_history": [
            {"fie_fencer_id": "1001", "season": 2024, "weapon": "Foil", "category": "Senior", "rank": 4, "country": "USA"},
        ],
        "fs_fencer_stats": [
            {"identity_id": IDENTITY_ALICE, "weapon": "Foil", "category": "Senior", "total_bouts": 20, "wins": 15},
        ],
        "fs_fencers": base_fencers(),
        "fs_fencer_identities": base_identities(),
        "fs_tournaments": base_tournaments(),
        "fs_fencer_longevity": [],
    }
    client = FakeSupabase(tables)

    first = compute_career_milestones(client=client, page_size=2, batch_size=10, log_run=False, update_state=False)
    first_rows = [row for call in client.upserts for row in call["rows"]]

    client.upserts.clear()
    second = compute_career_milestones(client=client, page_size=2, batch_size=10, log_run=False, update_state=False)
    second_rows = [row for call in client.upserts for row in call["rows"]]

    assert first == second
    assert first["written"] == first["milestone_rows"]
    assert first["failed"] == 0
    assert first_rows == second_rows
    assert {call["table"] for call in client.upserts} == {"fs_career_milestones"}
    assert {call["on_conflict"] for call in client.upserts} == {MILESTONE_CONFLICT_COLUMNS}
    assert all("id" not in row and "created_at" not in row for row in first_rows)
    assert ("fs_results", "id,fencer_id,fie_fencer_id,tournament_id,rank,placement,medal,weapon,gender,category,season,country,nationality,name,metadata,date,created_at,updated_at") in client.selects
    assert any(table == "fs_fencer_stats" for table, _columns in client.selects)


def test_compute_career_milestones_safe_empty_data_does_not_upsert():
    from compute_career_milestones import compute_career_milestones

    client = FakeSupabase(
        {
            "fs_results": [],
            "fs_rankings_history": [],
            "fs_fencer_stats": [],
            "fs_fencers": [],
            "fs_fencer_identities": [],
            "fs_tournaments": [],
            "fs_fencer_longevity": [],
        }
    )

    summary = compute_career_milestones(client=client, log_run=False, update_state=False)

    assert summary["milestone_rows"] == 0
    assert summary["written"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert client.upserts == []
