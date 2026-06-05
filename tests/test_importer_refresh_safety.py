import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

AUDITED_IMPORTERS = [
    "scrape_results.py",
    "scrape_fred.py",
    "askfred_scraper.py",
    "scrape_fie_satellite.py",
    "scrape_youth_majors.py",
    "scrape_iwas_games.py",
    "scrape_engarde.py",
]


@pytest.mark.parametrize("filename", AUDITED_IMPORTERS)
def test_importer_does_not_delete_existing_tournament_rows_before_refresh(filename):
    source = (ROOT / filename).read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", source)

    destructive_refresh = re.compile(
        r"\.table\([\"']fs_(?:results|bouts)[\"']\)"
        r"\.delete\(\)"
        r"\.eq\([\"']tournament_id[\"'],"
    )
    assert not destructive_refresh.search(compact)
