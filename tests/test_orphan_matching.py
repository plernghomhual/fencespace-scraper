import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.match_orphan_results import (
    apply_updates,
    build_fencer_index,
    match_orphan_row,
    match_orphan_rows,
    write_unmatched_log,
)

FENCERS = [
    {"id": "fie-priority", "fie_id": "111", "name": "Wrong Name", "country": "France", "metadata": {}},
    {"id": "exact", "fie_id": "222", "name": "Lee Kiefer", "country": "United States", "metadata": {}},
    {"id": "normalized", "fie_id": "333", "name": "Ａｎｎａ Márton", "country": "Hungary", "metadata": {}},
    {"id": "fuzzy", "fie_id": "444", "name": "Miles Chamley Watson", "country": "United States", "metadata": {}},
    {"id": "ncaa", "fie_id": None, "name": "Alex Chen", "country": "Canada", "metadata": {"school": "Princeton"}},
    {"id": "olympedia", "fie_id": None, "name": "Different Name", "country": "France", "metadata": {"olympedia_athlete_id": "99"}},
    {"id": "jordan-us", "fie_id": "555", "name": "Jordan Lee", "country": "United States", "metadata": {}},
    {"id": "jordan-can", "fie_id": "556", "name": "Jordan Lee", "country": "Canada", "metadata": {}},
]


def _index():
    return build_fencer_index(FENCERS)


def test_tier_1_fie_id_match_takes_priority_over_name_match():
    row = {"id": "r1", "fie_fencer_id": "111", "name": "Lee Kiefer", "nationality": "United States", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "fie-priority"
    assert match.tier == "tier_1_fie_id"


def test_tier_2_exact_name_and_country_match():
    row = {"id": "r2", "name": "Lee Kiefer", "nationality": "United States", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "exact"
    assert match.tier == "tier_2_exact_name_country"


def test_tier_3_nfkc_lower_name_and_country_match():
    row = {"id": "r3", "name": "anna márton", "nationality": "Hungary", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "normalized"
    assert match.tier == "tier_3_normalized_name_country"


def test_tier_4_fuzzy_name_and_country_match():
    row = {"id": "r4", "name": "Miles Chamley Watsn", "nationality": "United States", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "fuzzy"
    assert match.tier == "tier_4_fuzzy_name_country"


def test_tier_5_ncaa_school_match_uses_metadata_school():
    row = {"id": "r5", "name": "Alex Chen", "nationality": "United States", "metadata": {"school": "Princeton"}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "ncaa"
    assert match.tier == "tier_5_ncaa_school"


def test_tier_6_olympedia_athlete_id_match_uses_metadata_id():
    row = {"id": "r6", "name": "Wrong Name", "nationality": "Brazil", "metadata": {"olympedia_athlete_id": 99}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert match.matched
    assert match.fencer_id == "olympedia"
    assert match.tier == "tier_6_olympedia_athlete_id"


def test_national_fed_ranking_orphan_uses_fie_id_column():
    row = {"id": "n1", "fie_id": "222", "name": "Unrelated Name", "country": "United States", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_national_fed_rankings")

    assert match.matched
    assert match.fencer_id == "exact"
    assert match.tier == "tier_1_fie_id"


def test_same_name_different_country_without_country_is_ambiguous_not_matched():
    row = {"id": "r7", "name": "Jordan Lee", "metadata": {}}

    match = match_orphan_row(row, _index(), table_name="fs_results")

    assert not match.matched
    assert match.reason == "ambiguous_name_without_country"


def test_match_rate_exceeds_80_percent_on_realistic_rows():
    rows = [
        {"id": "r1", "fie_fencer_id": "111", "name": "Lee Kiefer", "nationality": "United States", "metadata": {}},
        {"id": "r2", "name": "Lee Kiefer", "nationality": "United States", "metadata": {}},
        {"id": "r3", "name": "anna márton", "nationality": "Hungary", "metadata": {}},
        {"id": "r4", "name": "Miles Chamley Watsn", "nationality": "United States", "metadata": {}},
        {"id": "r5", "name": "Alex Chen", "nationality": "United States", "metadata": {"school": "Princeton"}},
        {"id": "r6", "name": "Wrong Name", "nationality": "Brazil", "metadata": {"olympedia_athlete_id": 99}},
        {"id": "r8", "name": "Unmatched Fencer", "nationality": "Spain", "metadata": {}},
    ]

    matches, unmatched = match_orphan_rows(rows, _index(), table_name="fs_results")

    assert len(matches) == 6
    assert len(unmatched) == 1
    assert len(matches) / len(rows) >= 0.80


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.payload = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, column, value):
        self.client.updates.append((self.table_name, column, value, self.payload))
        return self

    def execute(self):
        return type("Result", (), {"data": []})()


class FakeRpc:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpcs.append((self.name, self.params))
        return type("Result", (), {"data": len(self.params["p_updates"])})()


class FakeClient:
    def __init__(self):
        self.updates = []
        self.rpcs = []

    def table(self, table_name):
        return FakeTable(self, table_name)

    def rpc(self, name, params):
        return FakeRpc(self, name, params)


def test_apply_updates_sets_fencer_id_by_row_id():
    client = FakeClient()
    matches, _ = match_orphan_rows(
        [{"id": "r2", "name": "Lee Kiefer", "nationality": "United States", "metadata": {}}],
        _index(),
        table_name="fs_results",
    )

    written = apply_updates(client, "fs_results", matches, batch_size=100)

    assert written == 1
    assert client.rpcs == [
        (
            "fs_bulk_update_fencer_matches",
            {"p_table_name": "fs_results", "p_updates": [{"id": "r2", "fencer_id": "exact"}]},
        )
    ]
    assert client.updates == []


def test_unmatched_orphans_are_written_to_log(tmp_path):
    _, unmatched = match_orphan_rows(
        [{"id": "r8", "name": "Unmatched Fencer", "nationality": "Spain", "metadata": {}}],
        _index(),
        table_name="fs_results",
    )
    log_path = tmp_path / "unmatched_orphans.log"

    write_unmatched_log(log_path, unmatched)

    text = log_path.read_text()
    assert "table\trow_id\tname\tcountry\tsource\treason" in text
    assert "fs_results\tr8\tUnmatched Fencer\tSpain\tfs_results\tno_match" in text
