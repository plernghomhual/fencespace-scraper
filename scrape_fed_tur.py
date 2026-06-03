"""
scrape_fed_tur.py - Turkey national federation rankings scraper.

Probe findings, 2026-06-02:
  - Requested host `trfencing.gov.tr` did not resolve from the sandbox probe.
  - Current public federation host is https://www.eskrim.org.tr.
  - Public rankings index:
      GET https://www.eskrim.org.tr/klasmanlar-20.html
  - Response formats: index is server-rendered HTML; ranking details are public
    PDF files under `/resim/extra/Klasmanlar/...`.
  - The current public index lists all 12 requested Senior/Junior
    Foil/Epee/Sabre Men/Women combos.

Turkish labels:
  Büyükler -> Senior, Gençler -> Junior
  Erkek -> Men, Kız/Kadın -> Women
  Epe -> Epee, Flöre -> Foil, Kılıç -> Sabre
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "tur_fencing"
COUNTRY = "Turkey"
BASE_URL = "https://www.eskrim.org.tr"
RANKINGS_INDEX_URL = f"{BASE_URL}/klasmanlar-20.html"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": RANKINGS_INDEX_URL,
}

RANKING_COMBOS = [
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
]

_RANKING_LINK_CACHE: dict[tuple[str, str, str], str] | None = None
_DATE_RE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b")
_LEADING_RANK_RE = re.compile(r"^\s*(\d+)\s+(.+)$")
_NUMERIC_TOKEN_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_PDF_SLUG_RE = re.compile(r"([GB])_([EK])_([EFK])\.pdf$", re.IGNORECASE)

_CATEGORY_FROM_SLUG = {"G": "Junior", "B": "Senior"}
_GENDER_FROM_SLUG = {"E": "Men", "K": "Women"}
_WEAPON_FROM_SLUG = {"E": "Epee", "F": "Foil", "K": "Sabre"}

_RANK_HEADERS = {"sira", "sirano", "sno", "no", "rank", "derece"}
_NAME_HEADERS = {
    "isim",
    "isimadsoyad",
    "adsoyad",
    "adisoyadi",
    "adsoyadi",
    "sporcu",
    "sporcuadi",
}
_SURNAME_HEADERS = {"soyad", "soyadi"}
_GIVEN_HEADERS = {"ad", "adi"}
_CLUB_HEADERS = {"kulup", "kulubu", "kulubu", "club", "takim"}
_POINT_HEADERS = {"puan", "puani", "puanlar", "points", "total", "toplam"}
_SKIP_TOKENS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "ret",
    "wdr",
    "toplam",
    "summary",
    "ozet",
    "baslik",
    "sira",
    "sno",
    "rank",
}
_CLUB_MARKERS = {
    "sk",
    "esk",
    "eskrim",
    "spor",
    "kulubu",
    "ferdi",
    "gsm",
    "gsim",
    "genclik",
    "demirspor",
}
_CLUB_PREFIXES = {
    "ankara",
    "istanbul",
    "izmir",
    "antalya",
    "bursa",
    "konya",
    "kayseri",
    "kocaeli",
    "eskisehir",
    "cankaya",
    "edirne",
    "denizli",
    "samsun",
    "ordu",
    "adana",
    "mersin",
    "uludag",
}


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _strip_accents(value: str) -> str:
    value = value.replace("ı", "i").replace("İ", "I")
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _strip_accents(value).lower())


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    token = _key(text.split()[0])
    if token in _SKIP_TOKENS:
        return None
    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in {"", "-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, tail = text.rsplit(",", 1)
        text = f"{head.replace(',', '')}.{tail}" if tail else head
    elif "." in text:
        parts = text.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            text = "".join(parts)
        elif len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        header = _key(cell)
        if header in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif header in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif header in _SURNAME_HEADERS and "surname" not in mapping:
            mapping["surname"] = idx
        elif header in _GIVEN_HEADERS and "given" not in mapping:
            mapping["given"] = idx
        elif header in _CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif header in _POINT_HEADERS:
            mapping["points"] = idx
    return mapping


def _parse_row_from_cells(cells: list[str], mapping: dict[str, int] | None = None) -> dict | None:
    cells = [_clean_text(cell) for cell in cells]
    if not cells:
        return None
    mapping = mapping or {}
    rank_idx = mapping.get("rank", 0)
    if len(cells) <= rank_idx:
        return None

    rank = _parse_rank(cells[rank_idx])
    if rank is None:
        return None

    if "name" in mapping and len(cells) > mapping["name"]:
        name = cells[mapping["name"]]
    elif "surname" in mapping and "given" in mapping:
        max_idx = max(mapping["surname"], mapping["given"])
        if len(cells) <= max_idx:
            return None
        name = _clean_text(f"{cells[mapping['surname']]} {cells[mapping['given']]}")
    elif len(cells) >= 3:
        name = _clean_text(f"{cells[1]} {cells[2]}")
    elif len(cells) >= 2:
        name = cells[1]
    else:
        return None

    if not name or _key(name) in _SKIP_TOKENS:
        return None

    club = None
    if "club" in mapping and len(cells) > mapping["club"]:
        club = cells[mapping["club"]] or None
    elif len(cells) >= 4:
        club = cells[3] or None

    points = None
    if "points" in mapping and len(cells) > mapping["points"]:
        points = _parse_points(cells[mapping["points"]])
    if points is None:
        for cell in reversed(cells):
            points = _parse_points(cell)
            if points is not None:
                break

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        mapping: dict[str, int] | None = None
        for row in table_rows:
            cells = row.find_all(["td", "th"])
            texts = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if not texts:
                continue

            detected = _detect_columns(texts)
            if "rank" in detected and (
                "name" in detected or ("surname" in detected and "given" in detected)
            ):
                mapping = detected
                continue

            parsed = _parse_row_from_cells(texts, mapping)
            if parsed:
                rows.append(parsed)

    return _dedupe_rows(rows)


def _parse_pipe_tables(text: str) -> list[dict]:
    rows: list[dict] = []
    mapping: dict[str, int] | None = None

    for raw_line in text.splitlines():
        if "|" not in raw_line:
            continue
        cells = [part.strip() for part in raw_line.strip().strip("|").split("|")]
        cells = [_clean_text(cell) for cell in cells]
        if not any(cells):
            continue

        detected = _detect_columns(cells)
        if "rank" in detected and (
            "name" in detected or ("surname" in detected and "given" in detected)
        ):
            mapping = detected
            continue

        parsed = _parse_row_from_cells(cells, mapping)
        if parsed:
            rows.append(parsed)

    return _dedupe_rows(rows)


def _is_noise_line(line: str) -> bool:
    text = _clean_text(line)
    if not text:
        return True
    key = _key(text)
    if key in _SKIP_TOKENS:
        return True
    if key.startswith(("snosoyad", "sirasoyad", "snosoyadad", "gencler", "buyukler")):
        return True
    if "klasmani" in key or "klasmanı" in text.lower():
        return True
    return False


def _logical_pdf_lines(text: str) -> list[str]:
    text = re.sub(r"(?i)(klasmani|klasmanı)(\d+)", r"\1\n\2", text)
    logical: list[str] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if _is_noise_line(line):
            if current:
                logical.append(" ".join(current))
                current = []
            continue

        if _LEADING_RANK_RE.match(line):
            if current:
                logical.append(" ".join(current))
            current = [line]
        elif current:
            current.append(line)

    if current:
        logical.append(" ".join(current))
    return logical


def _find_club_start(parts: list[str]) -> int | None:
    for idx in range(2, len(parts)):
        token = _key(parts[idx])
        if token in _CLUB_MARKERS:
            start = idx
            if idx > 2:
                start = idx - 1
                if parts[start] == "-" and start > 2:
                    start -= 1
                while start > 2 and _key(parts[start - 1]) in _CLUB_PREFIXES:
                    start -= 1
            return start

    for idx in range(2, len(parts)):
        token = parts[idx]
        if any(ch.islower() for ch in token):
            return idx
    return None


def _split_identity(identity: str) -> tuple[str, str | None]:
    parts = identity.split()
    if len(parts) < 2:
        return identity, None

    club_start = _find_club_start(parts)
    if club_start is None:
        club_start = 2 if len(parts) > 2 else len(parts)

    name = _clean_text(" ".join(parts[:club_start]))
    club = _clean_text(" ".join(parts[club_start:])) or None
    return name, club


def _parse_plain_pdf_line(line: str) -> dict | None:
    match = _LEADING_RANK_RE.match(line)
    if not match:
        return None

    rank = _parse_rank(match.group(1))
    if rank is None:
        return None

    body = match.group(2)
    date_match = _DATE_RE.search(body)
    if not date_match:
        return None

    identity = body[: date_match.start()].strip()
    after_date = body[date_match.end():]
    point_values = _NUMERIC_TOKEN_RE.findall(after_date)
    if not point_values:
        return None

    points = _parse_points(point_values[-1])
    if points is None:
        return None

    name, club = _split_identity(identity)
    if not name or _key(name) in _SKIP_TOKENS:
        return None

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_plain_text(text: str) -> list[dict]:
    rows = []
    for line in _logical_pdf_lines(text):
        parsed = _parse_plain_pdf_line(line)
        if parsed:
            rows.append(parsed)
    return _dedupe_rows(rows)


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple[int, str, float | None]] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row["rank"], row["name"], row.get("points"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Turkey ranking HTML, pdfplumber table text, or extracted PDF text."""
    if not html_or_text or not html_or_text.strip():
        return []

    html_rows = _parse_html_table(html_or_text)
    if html_rows:
        return html_rows

    pipe_rows = _parse_pipe_tables(html_or_text)
    if pipe_rows:
        return pipe_rows

    text = BeautifulSoup(html_or_text, "html.parser").get_text("\n", strip=True)
    return _parse_plain_text(text)


def _extract_ranking_links(
    html: str,
    *,
    base_url: str = RANKINGS_INDEX_URL,
) -> dict[tuple[str, str, str], str]:
    """Extract public PDF links from the federation ranking index."""
    soup = BeautifulSoup(html, "html.parser")
    links: dict[tuple[str, str, str], str] = {}

    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        filename = href.rsplit("/", 1)[-1]
        match = _PDF_SLUG_RE.search(filename)
        if not match:
            continue

        category_code, gender_code, weapon_code = (group.upper() for group in match.groups())
        combo = (
            _WEAPON_FROM_SLUG[weapon_code],
            _GENDER_FROM_SLUG[gender_code],
            _CATEGORY_FROM_SLUG[category_code],
        )
        if combo in RANKING_COMBOS:
            links[combo] = href

    return links


def _looks_blocked_or_js_only(text: str) -> bool:
    key = _key(text)
    blocked_markers = (
        "accessdenied",
        "forbidden",
        "captcha",
        "recaptcha",
        "giris",
        "girisyap",
        "login",
        "oturumac",
        "enablejavascript",
        "pleaseenablejavascript",
        "javascriptrequired",
    )
    return any(marker in key for marker in blocked_markers)


def _discover_ranking_links() -> dict[tuple[str, str, str], str]:
    global _RANKING_LINK_CACHE
    if _RANKING_LINK_CACHE is not None:
        return _RANKING_LINK_CACHE

    try:
        response = federation_request(
            "get",
            RANKINGS_INDEX_URL,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Ranking index request error for {RANKINGS_INDEX_URL}: {exc}")
        _RANKING_LINK_CACHE = {}
        return _RANKING_LINK_CACHE

    if response.status_code != 200:
        print(f"    Ranking index HTTP {response.status_code} for {RANKINGS_INDEX_URL}")
        _RANKING_LINK_CACHE = {}
        return _RANKING_LINK_CACHE

    if _looks_blocked_or_js_only(response.text):
        print(f"    Ranking index is blocked/login/JS-only: {RANKINGS_INDEX_URL}")
        _RANKING_LINK_CACHE = {}
        return _RANKING_LINK_CACHE

    _RANKING_LINK_CACHE = _extract_ranking_links(response.text, base_url=response.url)
    return _RANKING_LINK_CACHE


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber is required to parse Turkey ranking PDFs")
        return None

    try:
        chunks: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        cells = [_clean_text(cell) for cell in row]
                        if any(cells):
                            chunks.append(" | ".join(cells))
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                if text.strip():
                    chunks.append(text)
        return "\n".join(chunks).strip() or None
    except Exception as exc:
        print(f"    PDF parse error: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and extract one Turkey ranking combo; return None for failures."""
    combo = (weapon, gender, category)
    links = _discover_ranking_links()
    url = links.get(combo)
    if not url:
        print(f"    No scrapeable rankings at {RANKINGS_INDEX_URL} for {weapon} {gender} {category}")
        return None

    for attempt in range(2):
        try:
            response = federation_request(
                "get",
                url,
                headers=HEADERS,
                timeout=30,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(REQUEST_DELAY)
                continue
            print(f"    Request error for {url}: {exc}")
            return None

        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            return None

        if response.status_code in {403, 409, 429} or response.status_code >= 500:
            if attempt == 0:
                time.sleep(REQUEST_DELAY)
                continue
            print(f"    HTTP {response.status_code} for {url}")
            return None

        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {url}")
            return None

        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
            return _extract_pdf_text(response.content)

        if _looks_blocked_or_js_only(response.text):
            print(f"    Blocked/login/JS-only page for {url}")
            return None

        return response.text

    return None


def current_season() -> str:
    """Return current fencing season as YYYY-YYYY, using season_utils if present."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        import season_utils

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except Exception:
        pass
    return f"{end_year - 1:04d}-{end_year:04d}"


def _combo_label(combo: tuple[str, str, str]) -> str:
    weapon, gender, category = combo
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_tur").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    missing_combos: list[str] = []

    print(f"Turkey federation rankings - season {season}")
    print(f"Ranking index: {RANKINGS_INDEX_URL}")

    try:
        links = _discover_ranking_links()
        print(f"Discovered public ranking links: {len(links)}/{len(RANKING_COMBOS)}")

        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo = (weapon, gender, category)
            label = _combo_label(combo)
            url = links.get(combo)
            print(f"  {label}...")

            if not url:
                print(f"    No scrapeable rankings at {RANKINGS_INDEX_URL}")
                missing_combos.append(label)
                total_skipped += 1
            else:
                content = fetch_rankings_page(weapon, gender, category)
                if content is None:
                    failed_combos.append(label)
                    total_failed += 1
                else:
                    parsed = parse_rankings_table(content)
                    if not parsed:
                        print("    No rows parsed")
                        failed_combos.append(label)
                        total_failed += 1
                    else:
                        rows = [
                            build_ranking_row(
                                source=SOURCE,
                                season=season,
                                weapon=weapon,
                                gender=gender,
                                category=category,
                                rank=row["rank"],
                                name=row["name"],
                                country=COUNTRY,
                                club=row.get("club"),
                                points=row.get("points"),
                                metadata={
                                    "source_url": url,
                                    "index_url": RANKINGS_INDEX_URL,
                                    "country_code": "tur",
                                },
                            )
                            for row in parsed
                        ]
                        written = write_rankings(rows, source=SOURCE, season=season)
                        print(f"    Parsed {len(parsed)} rows; written {written}")
                        total_written += written
                        working_combos.append(label)

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        metadata = {
            "season": season,
            "combos_working": len(working_combos),
            "combos_total": len(RANKING_COMBOS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "missing_public_combos": missing_combos,
            "index_url": RANKINGS_INDEX_URL,
            "data_format": "html index + pdf details",
        }
        set_state(SOURCE, "last_run", metadata)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=metadata,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if missing_combos:
            print(f"Missing public combos: {', '.join(missing_combos)}")
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
