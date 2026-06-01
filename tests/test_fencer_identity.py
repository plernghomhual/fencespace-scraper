import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def fencer_row(row_id, name, country, fie_id=None, weapon="Foil", category="Senior"):
    return {
        "id": row_id,
        "fie_id": fie_id,
        "name": name,
        "country": country,
        "weapon": weapon,
        "category": category,
    }


def test_fie_id_grouping_merges_weapon_category_duplicates():
    from scripts.merge_fencer_identities import build_identity_groups

    result = build_identity_groups([
        fencer_row("00000000-0000-0000-0000-000000000001", "Alice Example", "USA", "12345", "Foil", "Senior"),
        fencer_row("00000000-0000-0000-0000-000000000002", "Alice Example", "USA", "12345", "Epee", "Junior"),
    ])

    assert result.total_fencers == 2
    assert result.ambiguous_cases_left == 0
    assert len(result.identities) == 1
    identity = result.identities[0]
    assert identity["canonical_name"] == "Alice Example"
    assert identity["country"] == "USA"
    assert identity["fie_ids"] == ["12345"]
    assert identity["fs_fencer_row_ids"] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    assert identity["metadata"]["match_type"] == "fie_id"
    assert identity["metadata"]["weapons"] == ["Epee", "Foil"]
    assert identity["metadata"]["categories"] == ["Junior", "Senior"]


def test_rows_without_fie_id_group_by_normalized_name_and_country():
    from scripts.merge_fencer_identities import build_identity_groups

    result = build_identity_groups([
        fencer_row("00000000-0000-0000-0000-000000000011", "Lee, Kiefer!", "USA.", None, "Foil", "Senior"),
        fencer_row("00000000-0000-0000-0000-000000000012", "lee kiefer", "usa", "", "Foil", "Junior"),
    ])

    assert result.ambiguous_cases_left == 0
    assert len(result.identities) == 1
    identity = result.identities[0]
    assert identity["fie_ids"] == []
    assert identity["fs_fencer_row_ids"] == [
        "00000000-0000-0000-0000-000000000011",
        "00000000-0000-0000-0000-000000000012",
    ]
    assert identity["metadata"]["match_type"] == "name_country"
    assert identity["metadata"]["normalized_name"] == "lee kiefer"
    assert identity["metadata"]["normalized_country"] == "usa"


def test_no_fie_rows_with_missing_name_or_country_are_ambiguous():
    from scripts.merge_fencer_identities import build_identity_groups

    result = build_identity_groups([
        fencer_row("00000000-0000-0000-0000-000000000021", "Unknown Fencer", None, None),
        fencer_row("00000000-0000-0000-0000-000000000022", "", "FRA", None),
    ])

    assert result.identities == []
    assert result.ambiguous_cases_left == 2
    assert [case["reason"] for case in result.ambiguous_cases] == [
        "missing_name_country_key",
        "missing_name_country_key",
    ]


def test_no_fie_row_matching_multiple_fie_identities_is_ambiguous():
    from scripts.merge_fencer_identities import build_identity_groups

    ambiguous_row_id = "00000000-0000-0000-0000-000000000033"
    result = build_identity_groups([
        fencer_row("00000000-0000-0000-0000-000000000031", "Alex Kim", "Korea", "111"),
        fencer_row("00000000-0000-0000-0000-000000000032", "Alex Kim", "Korea", "222"),
        fencer_row(ambiguous_row_id, "Alex Kim", "Korea", None),
    ])

    assert len(result.identities) == 2
    assert result.ambiguous_cases_left == 1
    assert result.ambiguous_cases[0]["reason"] == "matched_multiple_fie_identities"
    assert ambiguous_row_id not in {
        row_id
        for identity in result.identities
        for row_id in identity["fs_fencer_row_ids"]
    }


def test_normalization_handles_accented_and_decomposed_unicode():
    from scripts.merge_fencer_identities import build_identity_groups, normalize_identity_text

    assert normalize_identity_text(" E\u0301LODIE, Clément! ") == "élodie clément"

    result = build_identity_groups([
        fencer_row("00000000-0000-0000-0000-000000000041", "E\u0301lodie Clément", "FRA", None),
        fencer_row("00000000-0000-0000-0000-000000000042", "Élodie Clément", "fra", None),
    ])

    assert result.ambiguous_cases_left == 0
    assert len(result.identities) == 1
    assert result.identities[0]["metadata"]["normalized_name"] == "élodie clément"


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

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append({
            "table": self.name,
            "rows": rows,
            "on_conflict": on_conflict,
        })
        return self

    def execute(self):
        if self.operation == "select":
            return FakeResult(self.client.fencers[self.range_start:self.range_end + 1])
        if self.operation == "upsert":
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, fencers):
        self.fencers = fencers
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_merge_script_fetches_fencers_and_upserts_idempotently():
    from scripts.merge_fencer_identities import merge_fencer_identities

    client = FakeSupabase([
        fencer_row("00000000-0000-0000-0000-000000000051", "Arianna Errigo", "Italy", "991"),
        fencer_row("00000000-0000-0000-0000-000000000052", "Arianna Errigo", "Italy", "991", "Sabre"),
        fencer_row("00000000-0000-0000-0000-000000000053", "No Id", "Italy", None),
    ])

    first = merge_fencer_identities(client=client, page_size=2, log_run=False, update_state=False)
    first_payload_ids = [row["id"] for call in client.upserts for row in call["rows"]]

    client.upserts.clear()
    second = merge_fencer_identities(client=client, page_size=2, log_run=False, update_state=False)
    second_payload_ids = [row["id"] for call in client.upserts for row in call["rows"]]

    assert first == {
        "total_fencers": 3,
        "identities_found": 2,
        "ambiguous_cases_left": 0,
        "identity_groups_created": 2,
    }
    assert second == first
    assert first_payload_ids == second_payload_ids
    assert {call["table"] for call in client.upserts} == {"fs_fencer_identities"}
    assert {call["on_conflict"] for call in client.upserts} == {"id"}
