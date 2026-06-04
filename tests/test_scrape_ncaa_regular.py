from datetime import date

import pytest

from scrape_ncaa_regular import (
    ParsedBout,
    build_bout_rows,
    build_result_rows,
    build_tournament_row,
    parse_score_sheet_texts,
    parse_source_year,
    recent_seasons,
    write_meet,
)


ACC_SABER_PAGE = """
2025 ACC Fencing Championships
Hosted by University of North Carolina
Event: Men's Saber
Date: Saturday, February 22, 2025
Round: 1 Match: 1
Strip(s): E1, F2, S3
Referees: Becker, Bill
.Hassanein / Stapleton
Duke University & UNC Chapel Hill
CUM V/D V/D CUM
V TS TS V
0 Video D V Video 1
3 Samir Travers T/O 2 5 T/O Nicky Wind 6
1 Video V D Video 1
1 William Holz T/O 5 2 T/O Elden Wood 5
1 Video D V Video 2
2 Lev Ermakov T/O 3 5 T/O Finn Buchmann 4
Representative from Duke University Representative from UNC Chapel Hill
Referee(s)
REF #2025- 10101
"""


ACC_FOIL_PAGE = """
2025 ACC Fencing Championships
Hosted by University of North Carolina
Event: Men's Foil
Date: Saturday, February 22, 2025
Round: 1 Match: 1
Strip(s): E1, F2, S3
Referees: Abashidze, Gia
.Simonov / Webster
Duke University & UNC Chapel Hill
CUM V/D V/D CUM
V TS TS V
0 Video D V Video 1
3 Joseph Glasson T/O 4 5 T/O Peter Bruk 6
0 Video D V Video 2
1 Dayaal Singh T/O 3 5 T/O Cristian Porras 5
Representative from Duke University Representative from UNC Chapel Hill
Referee(s)
REF #2025- 10102
"""


ACC_EPEE_PAGE = """
2025 ACC Fencing Championships
Hosted by University of North Carolina
Event: Men's Epée
Date: Saturday, February 22, 2025
Round: 1 Match: 1
Strip(s): E1, F2, S3
Referees: Torchia, Dan
.Belanich / Buechel
Duke University & UNC Chapel Hill
CUM V/D V/D CUM
V TS TS V
1 Video V D Video 0
3 Allen Marakov T/O 5 4 T/O Boris Muga 6
1 Video D V Video 1
1 Peyton Young T/O 2 5 T/O Maximo Zafft 5
Representative from Duke University Representative from UNC Chapel Hill
Referee(s)
REF #2025- 10103
"""


ACC_FORFEIT_EPEE_PAGE = """
2025 ACC Fencing Championships
Hosted by University of North Carolina
Event: Women's Epée
Date: Sunday, February 23, 2025
Round: 5 Match: 2
Strip(s): E4, F5, S6
Referees: Torchia, Dan
.Belanich / Buechel
Boston College & Stanford
CUM V/D V/D CUM
V TS TS V
1 Video FV Video 0
3 Junyao Lu T/O T/O BOUT FORFEITED 6
1 Video FV Video 1
3 BOUT FORFEITED T/O T/O Valeria Sourimto 6
2 Video V D Video 0
1 Anisha Kundu T/O 5 4 T/O Sofia Raso 5
Representative from Boston College Representative from Stanford
Referee(s)
REF #2025- 50206
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.on_conflict = None
        self.filters = []

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def select(self, columns):
        self.action = "select"
        self.columns = columns
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        if self.action == "upsert":
            self.client.upserts.append((self.name, self.payload, self.on_conflict))
            if self.name == "fs_tournaments":
                return FakeResult([{"id": "tournament-1"}])
            return FakeResult(self.payload if isinstance(self.payload, list) else [self.payload])
        if self.action == "select":
            return FakeResult(self.client.selects.get(self.name, []))
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.upserts = []
        self.selects = {
            "fs_fencers": [
                {"id": "fencer-samir", "name": "Samir Travers", "country": "USA"},
                {"id": "fencer-nicky", "name": "Nicky Wind", "country": "United States"},
            ]
        }

    def table(self, name):
        return FakeTable(self, name)


def test_recent_seasons_returns_five_years_and_skips_2020():
    assert recent_seasons(current_year=2026) == [2026, 2025, 2024, 2023, 2022]
    assert 2020 not in recent_seasons(current_year=2022)


def test_parse_source_year_uses_url_year():
    assert parse_source_year("https://acc.escrimeresults.com/2025/ACC2025Mscoresheets.pdf") == 2025
    assert parse_source_year("https://example.com/no-year.pdf") is None


def test_parse_score_sheet_texts_extracts_bout_decisions():
    meets = parse_score_sheet_texts([ACC_SABER_PAGE], "https://acc.example/ACC2025Mscoresheets.pdf")

    assert len(meets) == 1
    meet = meets[0]
    assert meet.date == date(2025, 2, 22)
    assert meet.year == 2025
    assert meet.gender == "Men"
    assert meet.team_a == "Duke University"
    assert meet.team_b == "UNC Chapel Hill"
    assert meet.source_id == "ncaa_regular:2025:acc-2025-men-duke-university-vs-unc-chapel-hill"

    first = meet.bouts[0]
    assert first.weapon == "Sabre"
    assert first.fencer_a_name == "Samir Travers"
    assert first.fencer_b_name == "Nicky Wind"
    assert first.score_a == 2
    assert first.score_b == 5
    assert first.decision_a == "loss"
    assert first.decision_b == "win"


def test_parse_score_sheet_texts_groups_three_weapons_into_one_dual_meet():
    meets = parse_score_sheet_texts(
        [ACC_SABER_PAGE, ACC_FOIL_PAGE, ACC_EPEE_PAGE],
        "https://acc.example/ACC2025Mscoresheets.pdf",
    )

    assert len(meets) == 1
    assert {bout.weapon for bout in meets[0].bouts} == {"Sabre", "Foil", "Epee"}
    assert len(meets[0].bouts) == 7


def test_parse_score_sheet_texts_groups_weapon_pages_when_one_date_is_wrong():
    typo_saber = ACC_SABER_PAGE.replace("Saturday, February 22, 2025", "Monday, February 24, 2025")

    meets = parse_score_sheet_texts(
        [typo_saber, ACC_FOIL_PAGE, ACC_EPEE_PAGE],
        "https://acc.example/ACC2025Mscoresheets.pdf",
    )

    assert len(meets) == 1
    assert meets[0].date == date(2025, 2, 22)
    assert {bout.weapon for bout in meets[0].bouts} == {"Sabre", "Foil", "Epee"}


def test_parse_score_sheet_texts_counts_forfeited_bouts():
    meets = parse_score_sheet_texts([ACC_FORFEIT_EPEE_PAGE], "https://acc.example/ACC2025Wscoresheets.pdf")

    assert len(meets) == 1
    assert len(meets[0].bouts) == 3
    forfeit = meets[0].bouts[0]
    assert forfeit.fencer_a_name == "Junyao Lu"
    assert forfeit.fencer_b_name == "BOUT FORFEITED"
    assert forfeit.score_a == 5
    assert forfeit.score_b == 0
    assert forfeit.decision_a == "win"
    assert forfeit.decision_b == "loss"

    left_forfeit = meets[0].bouts[1]
    assert left_forfeit.fencer_a_name == "BOUT FORFEITED"
    assert left_forfeit.fencer_b_name == "Valeria Sourimto"
    assert left_forfeit.score_a == 0
    assert left_forfeit.score_b == 5
    assert left_forfeit.decision_a == "loss"
    assert left_forfeit.decision_b == "win"


def test_build_tournament_row_has_required_ncaa_regular_source_id():
    meet = parse_score_sheet_texts([ACC_SABER_PAGE], "https://acc.example/ACC2025Mscoresheets.pdf")[0]

    row = build_tournament_row(meet)

    assert row["source_id"] == "ncaa_regular:2025:acc-2025-men-duke-university-vs-unc-chapel-hill"
    assert row["name"] == "NCAA Regular Season: Duke University vs UNC Chapel Hill"
    assert row["type"] == "ncaa_regular_season"
    assert row["weapon"] == "Three Weapon"
    assert row["gender"] == "Men"
    assert row["start_date"] == "2025-02-22"
    assert row["metadata"]["bout_count"] == 3


def test_build_result_rows_summarizes_fencers_with_usa_name_matching():
    bouts = [
        ParsedBout(
            year=2025,
            source_url="https://acc.example/ACC2025Mscoresheets.pdf",
            source_page=1,
            date=date(2025, 2, 22),
            gender="Men",
            event_name="Men's Saber",
            round_number=1,
            match_number=1,
            team_a="Duke University",
            team_b="UNC Chapel Hill",
            weapon="Sabre",
            bout_number=1,
            fencer_a_name="Samir Travers",
            fencer_b_name="Nicky Wind",
            score_a=2,
            score_b=5,
            decision_a="loss",
            decision_b="win",
        ),
        ParsedBout(
            year=2025,
            source_url="https://acc.example/ACC2025Mscoresheets.pdf",
            source_page=1,
            date=date(2025, 2, 22),
            gender="Men",
            event_name="Men's Saber",
            round_number=1,
            match_number=1,
            team_a="Duke University",
            team_b="UNC Chapel Hill",
            weapon="Sabre",
            bout_number=2,
            fencer_a_name="Samir Travers",
            fencer_b_name="Elden Wood",
            score_a=5,
            score_b=2,
            decision_a="win",
            decision_b="loss",
        ),
    ]

    rows = build_result_rows("tournament-1", bouts, {"samir travers|usa": "fencer-samir"})
    samir = next(row for row in rows if row["name"] == "Samir Travers")

    assert samir["fencer_id"] == "fencer-samir"
    assert samir["nationality"] == "USA"
    assert samir["victory"] == 1
    assert samir["matches"] == 2
    assert samir["td"] == 7
    assert samir["tr"] == 7
    assert samir["metadata"]["school"] == "Duke University"
    assert samir["metadata"]["weapon"] == "Sabre"


def test_build_result_rows_skips_forfeit_placeholders():
    meet = parse_score_sheet_texts([ACC_FORFEIT_EPEE_PAGE], "https://acc.example/ACC2025Wscoresheets.pdf")[0]

    rows = build_result_rows("tournament-1", meet.bouts, {})

    assert "BOUT FORFEITED" not in {row["name"] for row in rows}


def test_build_bout_rows_include_weapon_names_and_stable_ids():
    bouts = parse_score_sheet_texts([ACC_SABER_PAGE], "https://acc.example/ACC2025Mscoresheets.pdf")[0].bouts
    rows = build_bout_rows("tournament-1", bouts, {"samir travers|usa": "fencer-samir", "nicky wind|usa": "fencer-nicky"})

    assert rows[0]["id"] == rows[0]["id"]
    assert rows[0]["tournament_id"] == "tournament-1"
    assert rows[0]["fencer_a_id"] == "fencer-samir"
    assert rows[0]["fencer_b_id"] == "fencer-nicky"
    assert rows[0]["winner_id"] == "fencer-nicky"
    assert rows[0]["score_a"] == 2
    assert rows[0]["score_b"] == 5
    assert rows[0]["weapon"] == "Sabre"
    assert rows[0]["metadata"]["fencer_a_name"] == "Samir Travers"


def test_write_meet_upserts_tournament_results_and_bouts():
    client = FakeClient()
    meet = parse_score_sheet_texts([ACC_SABER_PAGE], "https://acc.example/ACC2025Mscoresheets.pdf")[0]

    summary = write_meet(client, meet)

    assert summary["results"] == 6
    assert summary["bouts"] == 3
    tournament_upsert, results_upsert, bouts_upsert = client.upserts
    assert tournament_upsert[0] == "fs_tournaments"
    assert tournament_upsert[2] == "source_id"
    assert results_upsert[0] == "fs_results"
    assert results_upsert[2] == "tournament_id,name"
    assert bouts_upsert[0] == "fs_bouts"
    assert bouts_upsert[2] == "id"


def test_parse_score_sheet_texts_skips_non_score_pages():
    assert parse_score_sheet_texts(["2025 ACC Fencing Championships\nPlace School W L"], "https://acc.example") == []
