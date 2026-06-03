"""
National championship result scraper for top fencing nations.

Probe summary (2026-06-02):
  Shell probe was blocked by sandbox DNS; approval retry was blocked by the
  environment usage-limit gate. Public web probes confirmed current source
  shapes for 4Fence Italy, Engarde France, FencingWorldwide/Ophardt events,
  Canadian/British Fencing Time Live login redirects, and HKFA PDFs.
"""
from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from season_utils import current_fie_season, normalize_season

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "national_champs"
REQUEST_DELAY = 1.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
}

COUNTRY_CONFIGS = [
    {
        "country": "ITA",
        "name": "Italy",
        "federation_url": "https://federscherma.it/",
        "source_url": "https://www.4fence.it/FIS/Risultati/2026-06-04-30_Italia_-_Campionati_Italiani_Assoluti_Frecciarossa/",
        "language": "it",
        "result_page_types": ["html", "pdf", "4fence"],
        "parser": "4fence_html",
        "status": "parsable",
        "fallback_notes": "Use older Federscherma PDFs or 4Fence weapon/gender pages if current event menu changes.",
        "probe_evidence": "4Fence/FIS lists 2026 Campionati Italiani Assoluti Frecciarossa with weapon/gender result pages; 2025 pages expose CLASSIFICA FINALE tables and PDFs.",
    },
    {
        "country": "FRA",
        "name": "France",
        "federation_url": "https://www.escrime-ffe.fr/",
        "source_url": "https://engarde-service.com/tournament/life/antony2026",
        "language": "fr",
        "result_page_types": ["html", "engarde"],
        "parser": "engarde_html",
        "status": "parsable",
        "fallback_notes": "Use public Engarde competition pages under the tournament shell; skip login/account-only pages.",
        "probe_evidence": "Engarde public pages expose Classement general tables with Rg/Nom/Prenom/Club columns.",
    },
    {
        "country": "GER",
        "name": "Germany",
        "federation_url": "https://www.fechten.org/",
        "source_url": "https://www.fencingworldwide.com/de/32780-2025/tournament/",
        "language": "de",
        "result_page_types": ["html", "fencingworldwide", "ophardt"],
        "parser": "fencingworldwide_html",
        "status": "parsable",
        "fallback_notes": "Follow event links from the FencingWorldwide tournament page; skip when only article podium prose is available.",
        "probe_evidence": "DFB links Deutsche Meisterschaft results to FencingWorldwide; tournament page lists six Senior event links.",
    },
    {
        "country": "HKG",
        "name": "Hong Kong, China",
        "federation_url": "https://www.hkfa.org.hk/",
        "source_url": "https://www.hkfa.org.hk/EN/results.html?mID=7",
        "language": "en/zh",
        "result_page_types": ["pdf", "html-index"],
        "parser": "pdf_text",
        "status": "parsable",
        "fallback_notes": "Use HKFA results PDFs linked from the results index; skip PDFs without final classification rows.",
        "probe_evidence": "HKFA results index links public 2025 Hong Kong Open result PDFs; PDF text includes Name, Club, Country, and ranking fields.",
    },
    {
        "country": "POL",
        "name": "Poland",
        "federation_url": "https://pzszerm.pl/",
        "source_url": "https://pzszerm.pl/zawody/kalendarium-zawodow/",
        "language": "pl",
        "result_page_types": ["html"],
        "parser": "fencingworldwide_html",
        "status": "parsable",
        "fallback_notes": "Use PZSzerm tournament detail pages with Klasyfikacja koncowa tables; old pages can be historic only.",
        "probe_evidence": "PZSzerm tournament pages expose Mistrzostwa Polski metadata and tabular classifications.",
    },
    {
        "country": "BRA",
        "name": "Brazil",
        "federation_url": "https://cbesgrima.org.br/",
        "source_url": "https://www.fencingworldwide.com/en/",
        "language": "pt",
        "result_page_types": ["html", "fencingworldwide"],
        "parser": "fencingworldwide_html",
        "status": "parsable",
        "fallback_notes": "Use FencingWorldwide/Ophardt Campeonato Brasileiro event links; discover current IDs from index.",
        "probe_evidence": "FencingWorldwide current list includes Campeonato Brasileiro in Curitiba with Senior Foil/Epee/Sabre events.",
    },
    {
        "country": "CAN",
        "name": "Canada",
        "federation_url": "https://fencing.ca/",
        "source_url": "https://fencing.ca/results-2/",
        "language": "en/fr",
        "result_page_types": ["html-index", "fencingtimelive-login"],
        "parser": None,
        "status": "blocked",
        "fallback_notes": "Wait for public export or authenticated Fencing Time Live handoff; do not fabricate rows.",
        "probe_evidence": "CFF results page links 2025-26 nationals to Fencing Time Live; probed eventSchedule redirected to /account/login.",
    },
    {
        "country": "GBR",
        "name": "Great Britain",
        "federation_url": "https://www.britishfencing.com/",
        "source_url": "https://www.britishfencing.com/2026-british-national-championships-gb-cup-round-up/",
        "language": "en",
        "result_page_types": ["html-podium", "fencingtimelive-login"],
        "parser": None,
        "status": "blocked",
        "fallback_notes": "Article podium lists are not full standings; Fencing Time Live requires login for full results.",
        "probe_evidence": "British Fencing 2026 round-up links full results to Fencing Time Live and notes tournament info requires login.",
    },
    {
        "country": "USA",
        "name": "United States",
        "federation_url": "https://www.usafencing.org/",
        "source_url": "https://www.usafencing.org/natresults",
        "language": "en",
        "result_page_types": ["fencingtimelive-login"],
        "parser": None,
        "status": "blocked",
        "fallback_notes": "National results currently point users to Fencing Time advanced search; requires public export or credentials.",
        "probe_evidence": "USA Fencing national results page directs previous-season result lookup through Fencing Time.",
    },
    {
        "country": "JPN",
        "name": "Japan",
        "federation_url": "https://fencing-jpn.jp/",
        "source_url": "https://championship.fencing-jpn.jp/catalog/",
        "language": "ja",
        "result_page_types": ["html-booklet"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Static championship booklet has historic winners/profiles, not full current standings.",
        "probe_evidence": "All Japan championship catalog pages are public but expose booklet/prose and historical winner lists rather than complete rank tables.",
    },
    {
        "country": "KOR",
        "name": "Korea",
        "federation_url": "https://fencing.sports.or.kr/",
        "source_url": "https://fencing.sports.or.kr/",
        "language": "ko",
        "result_page_types": ["portal"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Needs a follow-up authenticated/dynamic portal probe before parser work.",
        "probe_evidence": "No stable static public national championship rank table was identified in current public probes.",
    },
    {
        "country": "CHN",
        "name": "China",
        "federation_url": "https://www.chnfencing.org.cn/",
        "source_url": "https://www.chnfencing.org.cn/",
        "language": "zh",
        "result_page_types": ["portal"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Needs official result-page discovery; skip until public table/PDF/XLS is confirmed.",
        "probe_evidence": "No stable static public national championship rank table was identified in current public probes.",
    },
    {
        "country": "HUN",
        "name": "Hungary",
        "federation_url": "https://hunfencing.hu/",
        "source_url": "https://hunfencing.hu/",
        "language": "hu",
        "result_page_types": ["html", "pdf"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Use only after a public championship final classification source is confirmed.",
        "probe_evidence": "No current stable public full-standings source confirmed during this scoped probe.",
    },
    {
        "country": "UKR",
        "name": "Ukraine",
        "federation_url": "https://nffu.org.ua/",
        "source_url": "https://nffu.org.ua/",
        "language": "uk",
        "result_page_types": ["html", "pdf"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Skip unless official public PDF/HTML standings are available.",
        "probe_evidence": "No current stable public full-standings source confirmed during this scoped probe.",
    },
    {
        "country": "ROU",
        "name": "Romania",
        "federation_url": "https://frscrima.ro/",
        "source_url": "https://www.fencingtimelive.com/",
        "language": "ro",
        "result_page_types": ["fencingtimelive"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "FencingWorldwide showed Romanian championship events via Fencing Time; skip if login-gated.",
        "probe_evidence": "FencingWorldwide current list included Campionatele din Romania, but public full result rows were not confirmed.",
    },
    {
        "country": "ESP",
        "name": "Spain",
        "federation_url": "https://esgrima.es/",
        "source_url": "https://esgrima.es/category/competiciones/",
        "language": "es",
        "result_page_types": ["html", "pdf"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Use only public RFEE result PDFs/memoria tables when complete rank rows are present.",
        "probe_evidence": "RFEE public pages expose competition news and annual memoria PDFs; current full live standings were not confirmed.",
    },
    {
        "country": "EGY",
        "name": "Egypt",
        "federation_url": "https://egyptfencing.com/",
        "source_url": "https://egyptfencing.com/",
        "language": "ar/en",
        "result_page_types": ["portal"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Needs official source discovery before parser work.",
        "probe_evidence": "No current stable public full-standings source confirmed during this scoped probe.",
    },
    {
        "country": "SUI",
        "name": "Switzerland",
        "federation_url": "https://swiss-fencing.ch/",
        "source_url": "https://www.fencingworldwide.com/de/",
        "language": "de/fr",
        "result_page_types": ["html", "fencingworldwide"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "FencingWorldwide lists Schweizermeisterschaften; enable parser once event result links expose full tables.",
        "probe_evidence": "FencingWorldwide current list included Schweizermeisterschaften in Zug.",
    },
    {
        "country": "NED",
        "name": "Netherlands",
        "federation_url": "https://www.knas.nl/",
        "source_url": "https://www.knas.nl/",
        "language": "nl",
        "result_page_types": ["html", "pdf"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Needs KNAS national championship result discovery before parser work.",
        "probe_evidence": "No current stable public full-standings source confirmed during this scoped probe.",
    },
    {
        "country": "TUR",
        "name": "Turkey",
        "federation_url": "https://www.eskrim.org.tr/",
        "source_url": "https://www.eskrim.org.tr/",
        "language": "tr",
        "result_page_types": ["portal", "pdf"],
        "parser": None,
        "status": "stub",
        "fallback_notes": "Needs official public result page/PDF confirmation before parser work.",
        "probe_evidence": "No current stable public full-standings source confirmed during this scoped probe.",
    },
]


_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def _clean_text(value) -> str:
    text = str(value or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn"
    )


def _key(value) -> str:
    text = _strip_accents(_clean_text(value).lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _title_name(value) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return " ".join(part.capitalize() if part.isupper() else part for part in text.split())


def _rank_to_int(value) -> int | None:
    match = re.match(r"\s*(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def _to_float(value) -> float | None:
    text = _clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _identifier(value) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return text


def _medal_for_rank(rank: int | None) -> str | None:
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _normalized_season(value=None) -> str:
    raw = value or current_fie_season()
    return normalize_season(raw)


def _canonical_header(header: str) -> str | None:
    key = _key(header)
    if key in {"rank", "rg", "rang", "place", "pos", "posizione", "classifica", "l p"}:
        return "rank"
    if key in {"name", "nom", "nome", "imie i nazwisko", "athlete", "fencer"}:
        return "name"
    if key in {"cognome", "surname", "family name", "last name", "nazwisko"}:
        return "last_name"
    if key in {"prenom", "prénom", "given name", "first name", "nome atleta", "imie"}:
        return "first_name"
    if key in {"country", "pays", "nazione", "nationality", "nat"}:
        return "country"
    if key in {"club", "societa", "societa sportiva", "societe", "society", "klub"}:
        return "club"
    if key in {"points", "point", "punt", "punti", "score"}:
        return "points"
    if key in {"fie id", "fie", "n fis", "num fis", "id fie", "licence", "license"}:
        return "fie_id"
    return None


def _first_index(headers: list[str | None], name: str) -> int | None:
    try:
        return headers.index(name)
    except ValueError:
        return None


def _cell(cells: list[str], index: int | None) -> str | None:
    if index is None or index >= len(cells):
        return None
    return _clean_text(cells[index]) or None


def build_result_row(
    metadata: dict,
    *,
    rank,
    name,
    country=None,
    club=None,
    points=None,
    fie_id=None,
) -> dict | None:
    parsed_rank = _rank_to_int(rank)
    fencer_name = _title_name(name)
    if parsed_rank is None or not fencer_name:
        return None
    return {
        "tournament": metadata.get("tournament") or metadata.get("name"),
        "event": metadata.get("event"),
        "rank": parsed_rank,
        "fencer_name": fencer_name,
        "country": _clean_text(country) or metadata.get("country"),
        "club": _clean_text(club) or None,
        "points": _to_float(points),
        "medal": _medal_for_rank(parsed_rank),
        "weapon": metadata.get("weapon"),
        "gender": metadata.get("gender"),
        "category": metadata.get("category") or "Senior",
        "season": _normalized_season(metadata.get("season")),
        "source_url": metadata.get("source_url"),
        "fie_id": _identifier(fie_id),
    }


def _parse_table_rows(table, metadata: dict) -> list[dict]:
    trs = table.find_all("tr")
    if not trs:
        return []
    header_cells = trs[0].find_all(["th", "td"])
    headers = [_canonical_header(cell.get_text(" ", strip=True)) for cell in header_cells]
    rank_i = _first_index(headers, "rank")
    name_i = _first_index(headers, "name")
    first_i = _first_index(headers, "first_name")
    last_i = _first_index(headers, "last_name")
    if rank_i is None or (name_i is None and first_i is None and last_i is None):
        return []

    country_i = _first_index(headers, "country")
    club_i = _first_index(headers, "club")
    points_i = _first_index(headers, "points")
    fie_i = _first_index(headers, "fie_id")

    parsed = []
    for tr in trs[1:]:
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if last_i is not None and (first_i is not None or name_i is not None):
            first = _cell(cells, first_i)
            if first is None and name_i is not None:
                first = _cell(cells, name_i)
            last = _cell(cells, last_i)
            name = f"{first or ''} {last or ''}".strip()
        elif first_i is not None and name_i is not None:
            first = _cell(cells, first_i)
            last = _cell(cells, name_i)
            name = f"{first or ''} {last or ''}".strip()
        elif name_i is not None:
            name = _cell(cells, name_i)
        else:
            name = _cell(cells, first_i) or _cell(cells, last_i)
        row = build_result_row(
            metadata,
            rank=_cell(cells, rank_i),
            name=name,
            country=_cell(cells, country_i),
            club=_cell(cells, club_i),
            points=_cell(cells, points_i),
            fie_id=_cell(cells, fie_i),
        )
        if row:
            parsed.append(row)
    return parsed


def parse_html_table_results(html: str, metadata: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows = []
    for table in soup.find_all("table"):
        rows.extend(_parse_table_rows(table, metadata))
    return rows


def parse_4fence_html(html: str, metadata: dict) -> list[dict]:
    return parse_html_table_results(html, metadata)


def parse_engarde_html(html: str, metadata: dict) -> list[dict]:
    return parse_html_table_results(html, metadata)


def parse_fencingworldwide_html(html: str, metadata: dict) -> list[dict]:
    return parse_html_table_results(html, metadata)


def parse_pdf_text_results(text: str, metadata: dict) -> list[dict]:
    parsed = []
    current_headers = None
    for raw_line in (text or "").splitlines():
        line = _clean_text(raw_line)
        if not line or "|" not in line:
            continue
        parts = [_clean_text(part) for part in line.split("|")]
        headers = [_canonical_header(part) for part in parts]
        if "rank" in headers and ("name" in headers or "last_name" in headers):
            current_headers = headers
            continue
        if not current_headers or len(parts) != len(current_headers):
            continue
        data = {header: parts[i] for i, header in enumerate(current_headers) if header}
        row = build_result_row(
            metadata,
            rank=data.get("rank"),
            name=data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}",
            country=data.get("country"),
            club=data.get("club"),
            points=data.get("points"),
            fie_id=data.get("fie_id"),
        )
        if row:
            parsed.append(row)
    return parsed


def _spreadsheet_rows_xls(content: bytes) -> list[list]:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=content)
    sheet = workbook.sheet_by_index(0)
    return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]


def _spreadsheet_rows_xlsx(content: bytes) -> list[list]:
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    sheet = workbook.worksheets[0]
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def parse_spreadsheet_results(content: bytes, metadata: dict, file_ext: str = ".xlsx") -> list[dict]:
    rows = _spreadsheet_rows_xls(content) if file_ext.lower() == ".xls" else _spreadsheet_rows_xlsx(content)
    header_index = None
    headers = []
    for i, row in enumerate(rows):
        candidate = [_canonical_header(cell) for cell in row]
        if "rank" in candidate and "name" in candidate:
            header_index = i
            headers = candidate
            break
    if header_index is None:
        return []

    parsed = []
    rank_i = _first_index(headers, "rank")
    name_i = _first_index(headers, "name")
    country_i = _first_index(headers, "country")
    club_i = _first_index(headers, "club")
    points_i = _first_index(headers, "points")
    fie_i = _first_index(headers, "fie_id")
    for row in rows[header_index + 1 :]:
        cells = [_clean_text(cell) for cell in row]
        result = build_result_row(
            metadata,
            rank=_cell(cells, rank_i),
            name=_cell(cells, name_i),
            country=_cell(cells, country_i),
            club=_cell(cells, club_i),
            points=_cell(cells, points_i),
            fie_id=_cell(cells, fie_i),
        )
        if result:
            parsed.append(result)
    return parsed


PARSERS = {
    "4fence_html": parse_4fence_html,
    "engarde_html": parse_engarde_html,
    "fencingworldwide_html": parse_fencingworldwide_html,
    "pdf_text": parse_pdf_text_results,
    "spreadsheet": parse_spreadsheet_results,
}


def match_fencer(client, *, fie_id=None, name=None, country=None) -> str | None:
    if not client:
        return None
    if fie_id:
        try:
            rows = (
                client.table("fs_fencers")
                .select("id")
                .eq("fie_id", str(fie_id))
                .limit(2)
                .execute()
                .data
            )
            if rows:
                return rows[0]["id"]
        except Exception:
            pass
    if name and country:
        try:
            rows = (
                client.table("fs_fencers")
                .select("id")
                .ilike("name", name)
                .eq("country", country)
                .limit(2)
                .execute()
                .data
            )
            if len(rows) == 1:
                return rows[0]["id"]
        except Exception:
            pass
    return None


def build_result_db_rows(client, tournament_id: str, parsed_rows: list[dict], unmatched_logger=print) -> list[dict]:
    db_rows = []
    for row in parsed_rows:
        if row.get("rank") is None:
            continue
        name = row.get("fencer_name") or row.get("name")
        country = row.get("country")
        fie_id = row.get("fie_id")
        fencer_id = match_fencer(client, fie_id=fie_id, name=name, country=country)
        if not fencer_id:
            unmatched_logger(
                f"Unmatched fencer for tournament {tournament_id}: {name} ({country or 'unknown country'}) fie_id={fie_id or '-'} source={row.get('source_url') or '-'}"
            )
        db_row = {
            "tournament_id": tournament_id,
            "name": name,
            "nationality": country,
            "rank": row["rank"],
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": {
                "source": SOURCE,
                "event": row.get("event"),
                "club": row.get("club"),
                "points": row.get("points"),
                "weapon": row.get("weapon"),
                "gender": row.get("gender"),
                "category": row.get("category"),
                "season": row.get("season"),
                "source_url": row.get("source_url"),
                "fie_id": fie_id,
            },
        }
        if fie_id:
            db_row["fie_fencer_id"] = str(fie_id)
        db_rows.append(db_row)
    return db_rows


def _source_id(config: dict, row: dict) -> str:
    seed = "|".join(
        [
            SOURCE,
            config.get("country", ""),
            row.get("season") or "",
            row.get("tournament") or "",
            row.get("event") or "",
        ]
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", seed).strip("-").lower()
    return slug[:180]


def upsert_tournament(client, config: dict, row: dict) -> str | None:
    source_id = _source_id(config, row)
    tournament = {
        "source_id": source_id,
        "name": f"{row.get('tournament') or config.get('name')} - {row.get('event') or 'National Championship'}",
        "season": row.get("season"),
        "type": "national_championship",
        "weapon": row.get("weapon"),
        "gender": row.get("gender"),
        "category": row.get("category"),
        "country": config.get("country"),
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "country": config.get("country"),
            "source_url": row.get("source_url") or config.get("source_url"),
            "probe_evidence": config.get("probe_evidence"),
        },
    }
    try:
        result = client.table("fs_tournaments").upsert(tournament, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def write_results(client, tournament_id: str, parsed_rows: list[dict], unmatched_logger=print) -> int:
    db_rows = build_result_db_rows(client, tournament_id, parsed_rows, unmatched_logger=unmatched_logger)
    if not db_rows:
        return 0
    client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i : i + 100]
        try:
            client.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def _metadata_for_config(config: dict) -> dict:
    return {
        "country": config.get("country"),
        "tournament": config.get("tournament") or config.get("name"),
        "event": config.get("event"),
        "weapon": config.get("weapon"),
        "gender": config.get("gender"),
        "category": config.get("category") or "Senior",
        "season": config.get("season") or current_fie_season(),
        "source_url": config.get("source_url"),
    }


def fetch_config_payload(config: dict):
    url = config.get("source_url")
    if not url:
        raise ValueError(f"{config.get('country')} has no source_url")
    response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    if "account/login" in response.url:
        raise RuntimeError(f"login redirect for {url}")
    parser = config.get("parser")
    if parser == "pdf_text":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            return "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)
    if parser == "spreadsheet":
        return response.content
    return response.text


def parse_config_payload(config: dict, payload) -> list[dict]:
    parser_name = config.get("parser")
    parser = PARSERS.get(parser_name)
    if not parser:
        return []
    metadata = _metadata_for_config(config)
    if parser_name == "spreadsheet":
        ext = os.path.splitext(urlparse(config.get("source_url", "")).path)[1] or ".xlsx"
        return parser(payload, metadata, file_ext=ext)
    return parser(payload, metadata)


def run_country_config(config: dict, client=None, payload=None) -> dict:
    country = config.get("country", "unknown")
    if config.get("status") != "parsable" or not config.get("parser"):
        print(f"{country} blocked/stub: {config.get('probe_evidence')}")
        print(f"  Fallback: {config.get('fallback_notes')}")
        return {"written": 0, "failed": 0, "skipped": 1}

    try:
        payload = payload if payload is not None else fetch_config_payload(config)
        rows = parse_config_payload(config, payload)
    except Exception as exc:
        print(f"{country} skipped: fetch/parse failed: {exc}")
        print(f"  Probe evidence: {config.get('probe_evidence')}")
        return {"written": 0, "failed": 0, "skipped": 1}

    if not rows:
        print(f"{country} skipped: no parseable result rows")
        return {"written": 0, "failed": 0, "skipped": 1}

    if not client:
        print(f"{country} parsed {len(rows)} rows; no Supabase credentials, skipping writes")
        return {"written": 0, "failed": 0, "skipped": len(rows)}

    tournament_id = upsert_tournament(client, config, rows[0])
    if not tournament_id:
        return {"written": 0, "failed": 1, "skipped": 0}
    written = write_results(client, tournament_id, rows)
    return {"written": written, "failed": 0 if written else 1, "skipped": 0}


def main():
    from run_logger import ScraperRunLogger
    from scraper_state import get_state, set_state

    run_log = ScraperRunLogger("scrape_national_champs").start()
    client = get_supabase()
    try:
        print(f"National championships scraper starting - {datetime.now(timezone.utc).isoformat()}")
        done = set(get_state(SOURCE, "done_countries") or [])
        total = {"written": 0, "failed": 0, "skipped": 0}
        for config in COUNTRY_CONFIGS:
            country = config["country"]
            if country in done:
                total["skipped"] += 1
                continue
            summary = run_country_config(config, client=client)
            for key in total:
                total[key] += summary[key]
            if summary["written"] > 0 or config.get("status") != "parsable":
                done.add(country)
                set_state(SOURCE, "done_countries", sorted(done))
            time.sleep(REQUEST_DELAY)
        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=total["written"], failed=total["failed"], skipped=total["skipped"])
        print(f"Done - written={total['written']}, failed={total['failed']}, skipped={total['skipped']}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
