from io import BytesIO
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _xlsx_bytes(rows, sheet_name="Ranking"):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _xls_bytes(rows, sheet_name="Ranking"):
    import xlwt

    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name)
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            ws.write(r_idx, c_idx, value)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_parse_rankings_xls_reads_openpyxl_generated_xlsx():
    from scrape_fed_italy import parse_rankings_xls

    data = _xlsx_bytes(
        [
            ["Pos", "Atleta", "Societa", "Punti"],
            [1, "GAROZZO Daniele", "Fiamme Oro", 1250],
            [2, "VOLPI Alice", "Fiamme Oro", "1.234,5"],
        ]
    )

    rows = parse_rankings_xls(data)

    assert rows == [
        {
            "rank": 1,
            "name": "GAROZZO Daniele",
            "club": "Fiamme Oro",
            "points": 1250.0,
        },
        {
            "rank": 2,
            "name": "VOLPI Alice",
            "club": "Fiamme Oro",
            "points": 1234.5,
        },
    ]


def test_parse_rankings_xls_maps_shuffled_italian_columns_and_chars():
    from scrape_fed_italy import parse_rankings_xls

    data = _xlsx_bytes(
        [
            ["Società", "Punti", "Atleta", "Pos"],
            ["Club Scherma città d'Italia", "10,5", "CÈCÈ Lucia", "3"],
            ["Accademia d'armi", "1.250", "D'AMICÒ Zoé", "4"],
        ]
    )

    rows = parse_rankings_xls(data)

    assert rows == [
        {
            "rank": 3,
            "name": "CÈCÈ Lucia",
            "club": "Club Scherma città d'Italia",
            "points": 10.5,
        },
        {
            "rank": 4,
            "name": "D'AMICÒ Zoé",
            "club": "Accademia d'armi",
            "points": 1250.0,
        },
    ]


def test_parse_rankings_xls_accepts_real_federscherma_totale_header():
    from scrape_fed_italy import parse_rankings_xls

    data = _xlsx_bytes(
        [
            ["Rank", "NOME", "Codice", "Società", "TOTALE"],
            [1, "BATINI MARTINA", 147440, "RMCC", 59691.5],
        ],
        sheet_name="FF A",
    )

    rows = parse_rankings_xls(data)

    assert rows == [
        {
            "rank": 1,
            "name": "BATINI MARTINA",
            "club": "RMCC",
            "points": 59691.5,
        }
    ]


def test_parse_rankings_xls_returns_empty_for_empty_sheet():
    from scrape_fed_italy import parse_rankings_xls

    assert parse_rankings_xls(_xlsx_bytes([])) == []


def test_parse_rankings_xls_returns_empty_for_header_only_sheet():
    from scrape_fed_italy import parse_rankings_xls

    data = _xlsx_bytes([["Pos", "Atleta", "Società", "Punti"]])

    assert parse_rankings_xls(data) == []


def test_parse_rankings_xls_reads_biff_xls_with_xlrd_fallback():
    from scrape_fed_italy import parse_rankings_xls

    data = _xls_bytes(
        [
            ["Pos", "Atleta", "Società", "Punti"],
            [1, "ROSSI Èlia", "Roma Scherma", "2,75"],
        ]
    )

    rows = parse_rankings_xls(data)

    assert rows == [
        {
            "rank": 1,
            "name": "ROSSI Èlia",
            "club": "Roma Scherma",
            "points": 2.75,
        }
    ]


def test_old_html_parser_is_removed():
    import scrape_fed_italy

    assert not hasattr(scrape_fed_italy, "parse_rankings_table")


def test_ranking_combos_cover_all_senior_and_junior_olympic_weapons():
    from scrape_fed_italy import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert set(RANKING_COMBOS) == {
        ("Foil", "Men", "Senior"),
        ("Foil", "Women", "Senior"),
        ("Epee", "Men", "Senior"),
        ("Epee", "Women", "Senior"),
        ("Sabre", "Men", "Senior"),
        ("Sabre", "Women", "Senior"),
        ("Foil", "Men", "Junior"),
        ("Foil", "Women", "Junior"),
        ("Epee", "Men", "Junior"),
        ("Epee", "Women", "Junior"),
        ("Sabre", "Men", "Junior"),
        ("Sabre", "Women", "Junior"),
    }
