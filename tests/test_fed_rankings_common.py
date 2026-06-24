import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_build_ranking_row_minimal():
    from fed_rankings_common import build_ranking_row
    row = build_ranking_row(
        source="british_fencing",
        season="2025-2026",
        weapon="Foil",
        gender="Men",
        category="Senior",
        rank=1,
        name="James Davis",
        country="GBR",
    )
    assert row["source"] == "british_fencing"
    assert row["season"] == "2025-2026"
    assert row["weapon"] == "Foil"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior"
    assert row["rank"] == 1
    assert row["name"] == "James Davis"
    assert row["country"] == "GBR"
    assert row["club"] is None
    assert row["points"] is None
    assert row["fencer_id"] is None
    assert row["fie_id"] is None
    assert isinstance(row["metadata"], dict)


def test_build_ranking_row_with_optionals():
    from fed_rankings_common import build_ranking_row
    row = build_ranking_row(
        source="fff",
        season="2025-2026",
        weapon="Epee",
        gender="Women",
        category="Junior",
        rank=3,
        name="Marie Dupont",
        country="FRA",
        club="Paris FC",
        points=1250.5,
        fie_id="98765",
    )
    assert row["club"] == "Paris FC"
    assert row["points"] == 1250.5
    assert row["fie_id"] == "98765"


def test_normalize_weapon():
    from fed_rankings_common import normalize_weapon
    assert normalize_weapon("foil") == "Foil"
    assert normalize_weapon("EPÉE") == "Epee"
    assert normalize_weapon("épée") == "Epee"
    assert normalize_weapon("sabre") == "Sabre"
    assert normalize_weapon("saber") == "Sabre"
    assert normalize_weapon("fleuret") == "Foil"
    assert normalize_weapon("degen") == "Epee"


def test_normalize_gender():
    from fed_rankings_common import normalize_gender
    assert normalize_gender("men") == "Men"
    assert normalize_gender("M") == "Men"
    assert normalize_gender("women") == "Women"
    assert normalize_gender("F") == "Women"
    assert normalize_gender("dames") == "Women"
    assert normalize_gender("hommes") == "Men"
    assert normalize_gender("herren") == "Men"
    assert normalize_gender("damen") == "Women"


def test_normalize_category():
    from fed_rankings_common import normalize_category
    assert normalize_category("senior") == "Senior"
    assert normalize_category("junior") == "Junior"
    assert normalize_category("cadet") == "Cadet"
    assert normalize_category("veteran") == "Veteran"
    assert normalize_category("u20") == "Junior"
    assert normalize_category("u17") == "Cadet"
