from scrape_fie_career import extract_window_var, parse_tab_ranking

# Minimal page with _tabRanking embedded as a window variable
PAGE_WITH_RANKING = """
<html><head>
<script>
window.__translations__ = {};
window._tabRanking = [
  {"weapon": "E", "category": "S", "season": 2024, "rank": 5, "point": 312.0},
  {"weapon": "E", "category": "S", "season": 2023, "rank": 8, "point": 240.5},
  {"weapon": "E", "category": "J", "season": 2020, "rank": 12, "point": 180.0},
  {"weapon": "F", "category": "S", "season": 2024, "rank": 3, "point": 400.0}
];
window._tabResults = [];
</script>
</head><body></body></html>
"""

PAGE_NO_RANKING = """
<html><head>
<script>
window.__translations__ = {};
</script>
</head><body></body></html>
"""

PAGE_EMPTY_RANKING = """
<html><head>
<script>
window._tabRanking = [];
</script>
</head><body></body></html>
"""

PAGE_LOWERCASE_CODES = """
<html><head>
<script>
window._tabRanking = [
  {"weapon": "epee", "category": "senior", "season": 2023, "rank": 10, "point": 200.0},
  {"weapon": "sabre", "category": "junior", "season": 2022, "rank": 4, "point": 150.0}
];
</script>
</head><body></body></html>
"""

PAGE_SABRE_M_CODE = """
<html><head>
<script>
window._tabRanking = [
  {"weapon": "M", "category": "S", "season": 2023, "rank": 2, "point": 500.0}
];
</script>
</head><body></body></html>
"""

PAGE_UNKNOWN_WEAPON = """
<html><head>
<script>
window._tabRanking = [
  {"weapon": "X", "category": "S", "season": 2023, "rank": 1, "point": 100.0},
  {"weapon": "E", "category": "S", "season": 2023, "rank": 5, "point": 250.0}
];
</script>
</head><body></body></html>
"""


def test_extract_window_var_returns_list():
    result = extract_window_var(PAGE_WITH_RANKING, "_tabRanking")
    assert isinstance(result, list)
    assert len(result) == 4


def test_extract_window_var_missing_returns_none():
    result = extract_window_var(PAGE_NO_RANKING, "_tabRanking")
    assert result is None


def test_extract_window_var_empty_list():
    result = extract_window_var(PAGE_EMPTY_RANKING, "_tabRanking")
    assert result == []


def test_parse_tab_ranking_returns_rows():
    rows = parse_tab_ranking(PAGE_WITH_RANKING)
    assert len(rows) == 4


def test_parse_tab_ranking_fields():
    rows = parse_tab_ranking(PAGE_WITH_RANKING)
    first = rows[0]
    assert first["weapon"] == "Epee"
    assert first["category"] == "Senior"
    assert first["season"] == 2024
    assert first["rank"] == 5
    assert first["points"] == 312.0


def test_parse_tab_ranking_junior_category():
    rows = parse_tab_ranking(PAGE_WITH_RANKING)
    junior = [r for r in rows if r["category"] == "Junior"]
    assert len(junior) == 1
    assert junior[0]["rank"] == 12


def test_parse_tab_ranking_multiple_weapons():
    rows = parse_tab_ranking(PAGE_WITH_RANKING)
    foil = [r for r in rows if r["weapon"] == "Foil"]
    assert len(foil) == 1
    assert foil[0]["rank"] == 3


def test_parse_tab_ranking_lowercase_codes():
    rows = parse_tab_ranking(PAGE_LOWERCASE_CODES)
    assert len(rows) == 2
    assert rows[0]["weapon"] == "Epee"
    assert rows[0]["category"] == "Senior"
    assert rows[1]["weapon"] == "Sabre"
    assert rows[1]["category"] == "Junior"


def test_parse_tab_ranking_m_code_is_sabre():
    rows = parse_tab_ranking(PAGE_SABRE_M_CODE)
    assert len(rows) == 1
    assert rows[0]["weapon"] == "Sabre"


def test_parse_tab_ranking_skips_unknown_weapon():
    rows = parse_tab_ranking(PAGE_UNKNOWN_WEAPON)
    # Unknown weapon "X" skipped; valid "E" entry kept
    assert len(rows) == 1
    assert rows[0]["weapon"] == "Epee"


def test_parse_tab_ranking_empty_page_returns_empty():
    rows = parse_tab_ranking(PAGE_NO_RANKING)
    assert rows == []


def test_parse_tab_ranking_empty_array_returns_empty():
    rows = parse_tab_ranking(PAGE_EMPTY_RANKING)
    assert rows == []
