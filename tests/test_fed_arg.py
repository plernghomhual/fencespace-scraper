"""
Tests for scrape_fed_arg.py.

Fixtures reflect the public FAE ranking PDFs probed from:
  https://www.esgrima-fae.com.ar/assets/pdf/ranking/mayores/mayores-espadafem.pdf
  https://www.esgrima-fae.com.ar/assets/pdf/ranking/juveniles/juveniles-sablemasc.pdf

PDF text columns:
  Nº | TIRADOR/A | SALA/CLUB | FECHA NAC. | event point columns | DESC. | TOTAL
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
RANKING NACIONAL DE MAYORES 2026 - ESPADA FEMENINA
Nº TIRADORA SALA FECHA NAC CN 2025 1ª 2026 2ª 2026 3ª 2026 DESC TOTAL
1 MÉNDEZ BELLO Josefina María ASTU 19/04/1996 38,40 32,00 32,00 0,00 0,00 102,40
2 EGLEZ Victoria CH 29/11/2008 26,40 26,00 8,00 26,00 8,00 78,40
3 MUSCI CONCEPCIÓN Margarita Inés FLA 31/03/2004 19,20 0,00 26,00 32,00 0,00 77,20
"""


FIXTURE_JUNIOR_TEXT = """
RANKING NACIONAL JUVENIL 2026 - SABLE MASCULINO
Nº TIRADOR CLUB FECHA NAC. 2ª 2025 3ª 2025 CN 2025 1ª 2026 DESC. TOTAL
1 ARPÓN SIMETO Matías RAC 12/03/2006 14,00 22,00 31,20 22,00 14,00 75,20
2 SOLER Bastian HG&CH 25/02/2011 16,00 16,00 26,40 32,00 16,00 74,40
3 BÖETTE Juan Bautista CHYP 05/02/2007 26,00 22,00 19,20 8,00 8,00 67,20
"""


FIXTURE_HTML_TABLE = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr>
        <th>Posición</th>
        <th>Nombre</th>
        <th>Club</th>
        <th>Puntos</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>1</td>
        <td>DE LA FUENTE LUNADEI Matiniano</td>
        <td>RAC</td>
        <td>1.234,50</td>
      </tr>
      <tr>
        <td>2</td>
        <td>FERNÁNDEZ RIVAS Paula</td>
        <td>GEBA</td>
        <td>39,60</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
RANKING NACIONAL DE MAYORES 2026 - FLORETE MASCULINO
N° TIRADOR SALA FECHA NAC CN 2025 1ª 2026 DESC TOTAL
TOTAL RANKING NACIONAL DE MAYORES 2026 - FLORETE MASCULINO
DNS APELLIDO Nombre CLUB 01/01/2000 0,00 0,00 0,00
DQ OTRO Nombre CLUB 01/01/2000 0,00 0,00 0,00
1 CERQUETTI Dante Leonel GEBA 26/04/2002 26,40 0,00 26,00 32,00 0,00 84,40
Resumen 1 prueba nacional
2 MARCHETTI Franco GER 15/05/2007 31,20 22,00 32,00 26,00 22,00 89,20
"""


FIXTURE_MALFORMED_DATES = """
RANKING NACIONAL DE MAYORES 2026 - SABLE MASCULINO
Nº TIRADOR SALA FECHA NAC CN 2025 1ª 2026 2ª 2026 3ª 2026 DESC TOTAL
27 CLERICI Gastón APE 25/061976 2,40 0,00 0,00 0,00 0,00 2,40
10 ZEMBORAIN NAVAJAS José Alejandro JCA 26//12/2005 8,00 26,00 0,00 0,00 0,00 34,00
"""


FIXTURE_EMPTY_HTML = ""


FIXTURE_NO_DATA_HTML = """
<!doctype html>
<html>
<body>
  <h1>Clasificaciones</h1>
  <p>No hay datos disponibles para esta categoría.</p>
</body>
</html>
"""


def test_parse_arg_pdf_text_returns_ranked_rows():
    from scrape_fed_arg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "MÉNDEZ BELLO Josefina María",
        "club": "ASTU",
        "points": 102.4,
    }
    assert rows[2]["rank"] == 3
    assert rows[2]["name"] == "MUSCI CONCEPCIÓN Margarita Inés"
    assert rows[2]["points"] == 77.2


def test_parse_arg_pdf_text_preserves_accents_and_club_symbols():
    from scrape_fed_arg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_JUNIOR_TEXT)

    assert len(rows) == 3
    assert rows[0]["name"] == "ARPÓN SIMETO Matías"
    assert rows[1]["club"] == "HG&CH"
    assert rows[2]["name"] == "BÖETTE Juan Bautista"


def test_parse_arg_html_table_with_spanish_headers_and_decimal_comma():
    from scrape_fed_arg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_TABLE)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "DE LA FUENTE LUNADEI Matiniano"
    assert rows[0]["club"] == "RAC"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "FERNÁNDEZ RIVAS Paula"


def test_parse_arg_empty_html_returns_empty_list():
    from scrape_fed_arg import parse_rankings_table

    assert parse_rankings_table(FIXTURE_EMPTY_HTML) == []


def test_parse_arg_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_arg import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA_HTML) == []


def test_parse_arg_skips_dns_dq_and_summary_rows():
    from scrape_fed_arg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert [row["rank"] for row in rows] == [1, 2]
    assert rows[0]["name"] == "CERQUETTI Dante Leonel"
    assert rows[1]["name"] == "MARCHETTI Franco"


def test_parse_arg_handles_malformed_pdf_dates_from_source():
    from scrape_fed_arg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_MALFORMED_DATES)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 27,
        "name": "CLERICI Gastón",
        "club": "APE",
        "points": 2.4,
    }
    assert rows[1]["rank"] == 10
    assert rows[1]["name"] == "ZEMBORAIN NAVAJAS José Alejandro"
    assert rows[1]["points"] == 34.0


def test_arg_url_and_category_mappings():
    from scrape_fed_arg import CATEGORY_SLUGS, build_rankings_url

    assert CATEGORY_SLUGS == {
        "Senior": "mayores",
        "Junior": "juveniles",
        "Cadet": "cadetes",
    }
    assert build_rankings_url("Epee", "Women", "Senior").endswith(
        "/assets/pdf/ranking/mayores/mayores-espadafem.pdf"
    )
    assert build_rankings_url("Sabre", "Men", "Junior").endswith(
        "/assets/pdf/ranking/juveniles/juveniles-sablemasc.pdf"
    )
