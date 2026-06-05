"""
scrape_japanese_univ.py - Japanese university fencing results scraper.

Probe findings (2026-06-02):
  - Public student-fencing result material is exposed through Kanto Gakuren pages:
    https://f-gakuren.com/f-kantougakuren/tournament_information.html
  - Linked public PDFs are hosted on f-kantogakuren.com/wp-content/uploads/.
  - Observed result shapes include Japanese HTML/PDF tables, side-by-side weapon
    seed tables, and league/team PDFs. Some pages can be unavailable or blocked.

The parser preserves Japanese names and university labels as source Unicode text.
It converts only numeric fields, such as rank and points, for database storage.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "scrape_japanese_univ"
COUNTRY = "Japan"
REQUEST_DELAY = float(os.environ.get("JAPANESE_UNIV_REQUEST_DELAY", "1.5"))
BATCH_SIZE = int(os.environ.get("JAPANESE_UNIV_BATCH_SIZE", "500"))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

DEFAULT_SOURCES: list[SourceConfig | dict[str, Any]] = [
    # Tournament information page. It may only list result links; direct parsing
    # is allowed to skip deterministically when no public result table is found.
    {
        "name": "kanto_gakuren_tournament_information",
        "url": "https://f-gakuren.com/f-kantougakuren/tournament_information.html",
        "competition_name": "関東学生フェンシング連盟 大会情報",
    },
    # Public PDFs observed on Kanto Gakuren result pages.
    {
        "name": "kanto_league_relegation_2025",
        "url": "https://f-kantogakuren.com/wp-content/uploads/2025/05/65edab69fcd95ab96a8069691d760430.pdf",
        "competition_name": "2025年度 関東学生フェンシング連盟リーグ戦入替戦結果",
        "season": "2025-2026",
        "category": "Team",
    },
    {
        "name": "all_japan_student_individual_seeds_2025",
        "url": "https://f-kantogakuren.com/wp-content/uploads/2025/10/7610c0e7cacfd41456794edbbf9873c3.pdf",
        "competition_name": "2025年 全日本学生フェンシング選手権大会個人戦シード表",
        "season": "2025-2026",
        "category": "Individual",
    },
]

RANK_HEADERS = {"順位", "rank", "#"}
NAME_HEADERS = {"氏名", "選手名", "選手", "名前", "name", "athlete"}
UNIVERSITY_HEADERS = {"所属", "所属先", "大学", "学校", "校名", "校名大学", "チーム", "team", "school", "university"}
POINTS_HEADERS = {"得点", "ポイント", "獲得総得点", "総得点", "点", "score", "points", "pts"}
MEDAL_HEADERS = {"メダル", "賞", "medal"}
WEAPON_HEADERS = {"種目", "weapon"}
CATEGORY_HEADERS = {"区分", "カテゴリ", "カテゴリー", "部門", "category"}
GENDER_HEADERS = {"性別", "gender"}
SKIP_MARKERS = {"dns", "dq", "棄権", "失格", "合計", "総合", "順位", "氏名", "選手名"}


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url: str
    competition_name: str
    season: str | None = None
    date: str | None = None
    weapon: str | None = None
    gender: str | None = None
    category: str | None = None


@dataclass
class SourceDocument:
    source: SourceConfig
    status: str
    reason: str
    rows: list[dict[str, Any]]
    content: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(value: Any) -> str:
    """Normalize spacing only; do not ASCII-fold or decompose Japanese text."""
    return _clean_text(value)


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _clean_text(value)).lower()


def _digits_for_number(value: Any) -> str:
    chars: list[str] = []
    for char in str(value):
        if char in {"，", ","}:
            chars.append(",")
            continue
        if char in {"．", "。", "."}:
            chars.append(".")
            continue
        if char in {"－", "ー", "―", "—"}:
            chars.append("-")
            continue
        try:
            chars.append(str(unicodedata.digit(char)))
            continue
        except (TypeError, ValueError):
            pass
        chars.append(char)
    return "".join(chars)


def _parse_rank(value: Any) -> int | None:
    text = _digits_for_number(_clean_text(value))
    compact = _compact(text)
    if not compact or compact in SKIP_MARKERS:
        return None
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def _parse_points(value: Any) -> float | None:
    text = _digits_for_number(_clean_text(value)).replace(" ", "")
    if not text or _compact(text) in {"-", "dns", "dq", "棄権", "失格"}:
        return None
    if re.fullmatch(r"\d{1,3}(,\d{3})+(?:\.\d+)?", text):
        text = text.replace(",", "")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> str | None:
    text = _digits_for_number(_clean_text(value))
    patterns = (
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
        r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _season_from_text(value: Any) -> str | None:
    text = _digits_for_number(str(value))
    match = re.search(r"(20\d{2})\s*年度", text)
    if not match:
        match = re.search(r"(20\d{2})\s*年", text)
    if not match:
        return None
    year = int(match.group(1))
    return f"{year}-{year + 1}"


def _infer_weapon(*values: Any) -> str | None:
    text = _compact(" ".join(str(value or "") for value in values))
    if any(token in text for token in ("フルーレ", "foil")):
        return "Foil"
    if any(token in text for token in ("エペ", "epee", "épée")):
        return "Epee"
    if any(token in text for token in ("サーブル", "sabre", "saber")):
        return "Sabre"
    return None


def _infer_gender(*values: Any) -> str | None:
    text = _compact(" ".join(str(value or "") for value in values))
    if "女子" in text or "women" in text or "female" in text:
        return "Women"
    if "男子" in text or "men" in text or "male" in text:
        return "Men"
    return None


def _infer_category(*values: Any) -> str | None:
    text = _compact(" ".join(str(value or "") for value in values))
    if any(token in text for token in ("団体", "大学対抗", "リーグ", "team")):
        return "Team"
    if any(token in text for token in ("個人", "シード", "individual")):
        return "Individual"
    return None


def _normalize_medal(value: Any, rank: int | None, *, infer_from_rank: bool) -> str | None:
    text = _compact(value)
    if text in {"gold", "金"}:
        return "Gold"
    if text in {"silver", "銀"}:
        return "Silver"
    if text in {"bronze", "銅"}:
        return "Bronze"
    if not infer_from_rank or rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _header_key(value: Any) -> str | None:
    key = _compact(value)
    if key in RANK_HEADERS:
        return "rank"
    if key in NAME_HEADERS:
        return "name"
    if key in UNIVERSITY_HEADERS:
        return "university"
    if key in POINTS_HEADERS:
        return "points"
    if key in MEDAL_HEADERS:
        return "medal"
    if key in WEAPON_HEADERS:
        return "weapon"
    if key in CATEGORY_HEADERS:
        return "category"
    if key in GENDER_HEADERS:
        return "gender"
    return None


def _detect_header(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(cells):
        key = _header_key(cell)
        if key and key not in mapping:
            mapping[key] = index
    return mapping


def _is_summary_or_blocked_rank(value: Any) -> bool:
    compact = _compact(value)
    return not compact or compact in SKIP_MARKERS or compact.startswith(("※", "注"))


def _document_context(content: str, source_url: str, defaults: SourceConfig | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(content or "", "html.parser")
    headings = [tag.get_text(" ", strip=True) for tag in soup.find_all(["h1", "h2", "title"])]
    visible_text = soup.get_text("\n", strip=True) if soup.find() else content
    first_line = next((_clean_text(line) for line in visible_text.splitlines() if _clean_text(line)), "")
    title = _clean_text(" ".join(headings)) or first_line
    date_text = " ".join(tag.get_text(" ", strip=True) for tag in soup.find_all("time")) + " " + visible_text[:500]
    season = (defaults.season if defaults else None) or _season_from_text(title) or _season_from_text(visible_text)
    return {
        "competition_name": (defaults.competition_name if defaults else None) or title or "Japanese University Fencing",
        "title": title,
        "season": season,
        "date": (defaults.date if defaults else None) or _parse_date(date_text),
        "weapon": defaults.weapon if defaults else None,
        "gender": defaults.gender if defaults else None,
        "category": defaults.category if defaults else None,
        "source_url": source_url,
        "infer_rank_medals": "シード" not in title,
    }


def _source_id(parts: list[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"jpn_univ:{digest}"


def _append_parsed_row(
    rows: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    rank: int | None,
    name: Any,
    university: Any,
    weapon: Any = None,
    gender: Any = None,
    category: Any = None,
    points: Any = None,
    medal: Any = None,
    rank_source: str = "explicit",
) -> None:
    athlete_or_team = normalize_name(name)
    university_name = normalize_name(university)
    if rank is None or not athlete_or_team:
        return

    weapon_value = _infer_weapon(weapon, context.get("weapon"), context.get("title")) or context.get("weapon")
    gender_value = _infer_gender(gender, weapon, context.get("gender"), context.get("title")) or context.get("gender")
    category_value = (
        _infer_category(category, context.get("category"), context.get("title")) or context.get("category") or "Individual"
    )
    season = context.get("season")
    date = context.get("date")
    tournament_source_id = _source_id(
        [
            context.get("source_url"),
            context.get("competition_name"),
            season,
            weapon_value,
            gender_value,
            category_value,
        ]
    )
    row = {
        "rank": rank,
        "name": athlete_or_team,
        "university": university_name or None,
        "weapon": weapon_value,
        "gender": gender_value,
        "category": category_value,
        "points": _parse_points(points),
        "medal": _normalize_medal(medal, rank, infer_from_rank=bool(context.get("infer_rank_medals"))),
        "season": season,
        "date": date,
        "source_url": context.get("source_url"),
        "competition_name": context.get("competition_name"),
        "tournament_source_id": tournament_source_id,
        "rank_source": rank_source,
    }
    rows.append(row)


def _parse_html_tables(content: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(content or "", "html.parser")
    parsed: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        mapping: dict[str, int] = {}
        synthetic_rank = 1
        for tr in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if not cells:
                continue
            detected = _detect_header(cells)
            if "name" in detected or "university" in detected:
                mapping = detected
                synthetic_rank = 1
                continue
            if not mapping:
                continue

            rank = _parse_rank(cells[mapping["rank"]]) if "rank" in mapping and len(cells) > mapping["rank"] else None
            rank_source = "explicit"
            if rank is None and "rank" not in mapping and "points" in mapping:
                rank = synthetic_rank
                rank_source = "row_order"
            if rank is None:
                continue

            name_idx = mapping.get("name", mapping.get("university"))
            univ_idx = mapping.get("university")
            if name_idx is None or len(cells) <= name_idx:
                continue
            if _is_summary_or_blocked_rank(cells[mapping["rank"]]) if "rank" in mapping else False:
                continue

            _append_parsed_row(
                parsed,
                context=context,
                rank=rank,
                name=cells[name_idx],
                university=cells[univ_idx] if univ_idx is not None and len(cells) > univ_idx else cells[name_idx],
                weapon=cells[mapping["weapon"]] if "weapon" in mapping and len(cells) > mapping["weapon"] else None,
                gender=cells[mapping["gender"]] if "gender" in mapping and len(cells) > mapping["gender"] else None,
                category=cells[mapping["category"]] if "category" in mapping and len(cells) > mapping["category"] else None,
                points=cells[mapping["points"]] if "points" in mapping and len(cells) > mapping["points"] else None,
                medal=cells[mapping["medal"]] if "medal" in mapping and len(cells) > mapping["medal"] else None,
                rank_source=rank_source,
            )
            synthetic_rank += 1
    return parsed


def _split_pipe_cells(line: str) -> list[str]:
    cells = [part.strip() for part in re.split(r"\s*\|\s*", line.strip())]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _parse_side_by_side_weapon_table(lines: list[str], context: dict[str, Any]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    groups: list[tuple[str, int, int]] = []
    active = False

    for line in lines:
        if "|" not in line:
            continue
        cells = _split_pipe_cells(line)
        if not cells:
            continue

        weapon_indexes = [(index, _infer_weapon(cell)) for index, cell in enumerate(cells)]
        weapon_indexes = [(index, weapon) for index, weapon in weapon_indexes if weapon]
        if _header_key(cells[0]) == "rank" and len(weapon_indexes) >= 2:
            groups = [(weapon or "", index, index + 1) for index, weapon in weapon_indexes if index + 1 < len(cells) + 1]
            active = True
            continue

        if not active or not groups:
            continue
        if any(_header_key(cell) in {"name", "university"} for cell in cells):
            continue

        rank = _parse_rank(cells[0])
        if rank is None:
            continue

        for weapon, name_index, university_index in groups:
            if len(cells) <= name_index:
                continue
            name = cells[name_index]
            university = cells[university_index] if len(cells) > university_index else None
            _append_parsed_row(
                parsed,
                context=context,
                rank=rank,
                name=name,
                university=university,
                weapon=weapon,
                gender=context.get("gender") or _infer_gender(context.get("title")),
                category=context.get("category") or "Individual",
                points=None,
                medal=None,
            )
    return parsed


def _parse_pipe_tables(content: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [line.strip() for line in BeautifulSoup(content, "html.parser").get_text("\n").splitlines()]
    side_by_side = _parse_side_by_side_weapon_table(lines, context)
    if side_by_side:
        return side_by_side

    parsed: list[dict[str, Any]] = []
    mapping: dict[str, int] = {}
    synthetic_rank = 1
    for line in lines:
        if "|" not in line:
            continue
        cells = _split_pipe_cells(line)
        if len(cells) < 2:
            continue
        detected = _detect_header(cells)
        if "name" in detected or "university" in detected:
            mapping = detected
            synthetic_rank = 1
            continue
        if not mapping:
            continue

        rank = _parse_rank(cells[mapping["rank"]]) if "rank" in mapping and len(cells) > mapping["rank"] else None
        rank_source = "explicit"
        if rank is None and "rank" not in mapping and "points" in mapping:
            rank = synthetic_rank
            rank_source = "row_order"
        if rank is None:
            continue

        name_idx = mapping.get("name", mapping.get("university"))
        univ_idx = mapping.get("university")
        if name_idx is None or len(cells) <= name_idx:
            continue

        _append_parsed_row(
            parsed,
            context=context,
            rank=rank,
            name=cells[name_idx],
            university=cells[univ_idx] if univ_idx is not None and len(cells) > univ_idx else cells[name_idx],
            weapon=cells[mapping["weapon"]] if "weapon" in mapping and len(cells) > mapping["weapon"] else None,
            gender=cells[mapping["gender"]] if "gender" in mapping and len(cells) > mapping["gender"] else None,
            category=cells[mapping["category"]] if "category" in mapping and len(cells) > mapping["category"] else None,
            points=cells[mapping["points"]] if "points" in mapping and len(cells) > mapping["points"] else None,
            medal=cells[mapping["medal"]] if "medal" in mapping and len(cells) > mapping["medal"] else None,
            rank_source=rank_source,
        )
        synthetic_rank += 1
    return parsed


def parse_results_document(
    content: str,
    *,
    source_url: str,
    defaults: SourceConfig | None = None,
) -> list[dict[str, Any]]:
    if not content or not content.strip():
        return []
    context = _document_context(content, source_url, defaults)
    html_rows = _parse_html_tables(content, context)
    if html_rows:
        return _dedupe_rows(html_rows)
    return _dedupe_rows(_parse_pipe_tables(content, context))


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("tournament_source_id"), row.get("rank"), row.get("name"), row.get("university"), row.get("weapon"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber is required to parse Japanese university fencing PDFs")
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        print(f"PDF parse error: {exc}")
        return None


def fetch_source_document(source: SourceConfig, *, session: Any | None = None) -> SourceDocument:
    session = session or requests.Session()
    try:
        response = session.get(source.url, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        return SourceDocument(source=source, status="blocked", reason=f"request error: {exc}", rows=[])

    if response.status_code in {401, 403, 429}:
        return SourceDocument(source=source, status="blocked", reason=f"HTTP {response.status_code}", rows=[])
    if response.status_code == 404:
        return SourceDocument(source=source, status="missing", reason="HTTP 404", rows=[])
    if response.status_code != 200:
        return SourceDocument(source=source, status="error", reason=f"HTTP {response.status_code}", rows=[])

    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        text = _extract_pdf_text(response.content)
        if not text:
            return SourceDocument(source=source, status="skipped", reason="PDF text unavailable", rows=[])
        rows = parse_results_document(text, source_url=source.url, defaults=source)
        return SourceDocument(source=source, status="ok" if rows else "skipped", reason="" if rows else "no parseable rows", rows=rows, content=text)

    rows = parse_results_document(response.text, source_url=source.url, defaults=source)
    return SourceDocument(
        source=source,
        status="ok" if rows else "skipped",
        reason="" if rows else "no public result table found",
        rows=rows,
        content=response.text,
    )


def discover_result_sources(index_html: str, base_url: str) -> list[SourceConfig]:
    soup = BeautifulSoup(index_html or "", "html.parser")
    sources: list[SourceConfig] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        label = _clean_text(link.get_text(" ", strip=True))
        href = urljoin(base_url, link["href"])
        if href in seen:
            continue
        if not any(token in label for token in ("結果", "リーグ", "関カレ", "インカレ", "王座", "シード")):
            continue
        if not (href.lower().endswith(".pdf") or "result" in href.lower() or "tournament" in href.lower()):
            continue
        seen.add(href)
        sources.append(SourceConfig(name=f"discovered_{len(sources) + 1}", url=href, competition_name=label or "Japanese University Fencing"))
    return sources


def build_tournament_rows(parsed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in parsed_rows:
        source_id = row["tournament_source_id"]
        if source_id in grouped:
            continue
        label_parts = [row.get("competition_name"), row.get("gender"), row.get("weapon"), row.get("category")]
        name = " - ".join(str(part) for part in label_parts if part)
        grouped[source_id] = {
            "source_id": source_id,
            "name": name or row.get("competition_name") or "Japanese University Fencing",
            "season": row.get("season"),
            "start_date": row.get("date"),
            "end_date": row.get("date"),
            "type": "university",
            "weapon": row.get("weapon"),
            "gender": row.get("gender"),
            "category": row.get("category"),
            "country": COUNTRY,
            "has_results": True,
            "metadata": {
                "source": SOURCE,
                "source_url": row.get("source_url"),
                "competition_name": row.get("competition_name"),
                "university_league": True,
            },
        }
    return list(grouped.values())


def _name_key(value: Any) -> str:
    return _compact(normalize_name(value))


def build_fencer_index(fencers: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for fencer in fencers:
        name = fencer.get("name")
        fencer_id = fencer.get("id")
        if not name or fencer_id is None:
            continue
        country = _compact(fencer.get("country") or fencer.get("nationality") or COUNTRY)
        index[(_name_key(name), country)] = str(fencer_id)
    return index


def _match_fencer_id(row: dict[str, Any], fencer_index: dict[tuple[str, str], str]) -> tuple[str | None, str]:
    key = (_name_key(row.get("name")), _compact(COUNTRY))
    if key in fencer_index:
        return fencer_index[key], "exact_name_country"
    return None, "unmatched"


def build_result_rows(
    parsed_rows: list[dict[str, Any]],
    tournament_ids: dict[str, Any],
    fencer_index: dict[tuple[str, str], str],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for row in parsed_rows:
        _tsid = row.get("tournament_source_id")
        tournament_id = tournament_ids.get(_tsid) if _tsid is not None else None
        if tournament_id is None:
            unmatched.append(f"{row.get('name')} | {row.get('university')} | missing_tournament")
            continue
        if row.get("category") == "Team":
            fencer_id, match_method = None, "team_row"
        else:
            fencer_id, match_method = _match_fencer_id(row, fencer_index)
        if fencer_id is None and row.get("category") != "Team":
            unmatched.append(
                f"{row.get('name')} | {row.get('university')} | "
                f"{row.get('gender')} {row.get('weapon')} {row.get('category')}"
            )

        rows.append(
            {
                "tournament_id": tournament_id,
                "fencer_id": fencer_id,
                "fie_fencer_id": None,
                "rank": row.get("rank"),
                "placement": row.get("rank"),
                "name": row.get("name"),
                "country": COUNTRY,
                "nationality": COUNTRY,
                "medal": row.get("medal"),
                "points": row.get("points"),
                "metadata": {
                    "source": SOURCE,
                    "source_url": row.get("source_url"),
                    "source_result_id": _source_id(
                        [row.get("tournament_source_id"), row.get("rank"), row.get("name"), row.get("university")]
                    ),
                    "university": row.get("university"),
                    "weapon": row.get("weapon"),
                    "gender": row.get("gender"),
                    "category": row.get("category"),
                    "rank_source": row.get("rank_source"),
                    "match_method": match_method,
                },
                "updated_at": utc_now(),
            }
        )
    return rows, unmatched


def require_supabase(client: Any | None = None) -> Any:
    resolved = client or supabase
    if resolved is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return resolved


def upsert_tournaments(client: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    for start in range(0, len(rows), BATCH_SIZE):
        client.table("fs_tournaments").upsert(rows[start : start + BATCH_SIZE], on_conflict="source_id").execute()

    source_ids = [row["source_id"] for row in rows]
    ids: dict[str, Any] = {}
    for start in range(0, len(source_ids), BATCH_SIZE):
        chunk = source_ids[start : start + BATCH_SIZE]
        result = client.table("fs_tournaments").select("id,source_id").in_("source_id", chunk).execute()
        for row in result.data or []:
            ids[row["source_id"]] = row["id"]
    return ids


def upsert_results(client: Any, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    written = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        client.table("fs_results").upsert(batch, on_conflict="tournament_id,name").execute()
        written += len(batch)
    return written


def fetch_fencers(client: Any) -> list[dict[str, Any]]:
    result = client.table("fs_fencers").select("id,name,country,nationality").execute()
    return result.data or []


def _coerce_source(source: SourceConfig | dict[str, Any]) -> SourceConfig:
    if isinstance(source, SourceConfig):
        return source
    return SourceConfig(**source)


def scrape_sources(
    sources: list[SourceConfig | dict[str, Any]],
    *,
    client: Any | None = None,
    session: Any | None = None,
    logger_factory: Any = ScraperRunLogger,
    sleep_fn: Any = time.sleep,
) -> dict[str, int]:
    db = require_supabase(client) if client is not None else client
    if db is None and client is None:
        db = require_supabase(None)

    run_log = logger_factory(SOURCE).start()
    summary = {
        "sources_checked": 0,
        "tournaments_written": 0,
        "results_written": 0,
        "failed": 0,
        "skipped": 0,
        "unmatched": 0,
    }
    blocked_sources: list[str] = []
    unmatched_rows: list[str] = []

    try:
        done_urls = set(get_state(SOURCE, "done_source_urls") or [])
        fencer_index: dict[tuple[str, str], str] | None = None
        parsed_sources = [_coerce_source(source) for source in sources]

        for index, source in enumerate(parsed_sources):
            summary["sources_checked"] += 1
            if source.url in done_urls:
                summary["skipped"] += 1
                continue

            document = fetch_source_document(source, session=session)
            if document.status in {"blocked", "missing", "skipped"}:
                summary["skipped"] += 1
                if document.status == "blocked":
                    blocked_sources.append(source.url)
                continue
            if document.status != "ok":
                summary["failed"] += 1
                continue

            if fencer_index is None:
                fencer_index = build_fencer_index(fetch_fencers(db)) if db is not None else {}
            tournament_rows = build_tournament_rows(document.rows)
            tournament_ids = upsert_tournaments(db, tournament_rows)
            result_rows, unmatched = build_result_rows(document.rows, tournament_ids, fencer_index or {})
            written = upsert_results(db, result_rows)
            summary["tournaments_written"] += len(tournament_ids)
            summary["results_written"] += written
            summary["unmatched"] += len(unmatched)
            unmatched_rows.extend(unmatched)
            done_urls.add(source.url)
            set_state(SOURCE, "done_source_urls", sorted(done_urls))

            if index < len(parsed_sources) - 1:
                sleep_fn(REQUEST_DELAY)

        set_state(SOURCE, "last_run", {"updated_at": utc_now(), **summary})
        run_log.complete(
            written=summary["results_written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata={
                "blocked_sources": blocked_sources,
                "unmatched": summary["unmatched"],
                "unmatched_rows": unmatched_rows[:50],
            },
        )
        return summary
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_sources(DEFAULT_SOURCES)
    print(
        "Japanese university scraper complete - "
        f"sources={summary['sources_checked']}, tournaments={summary['tournaments_written']}, "
        f"results={summary['results_written']}, skipped={summary['skipped']}, "
        f"failed={summary['failed']}, unmatched={summary['unmatched']}"
    )


if __name__ == "__main__":
    main()
