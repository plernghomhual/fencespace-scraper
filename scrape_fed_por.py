"""
scrape_fed_por.py — Portugal federation rankings scraper.

Probe evidence, 2026-06-02:
  - Target source: fpesgrima.pt.
  - Non-escalated probe of fpesgrima.pt and common ranking paths failed with
    sandbox DNS NameResolutionError.
  - Required escalated network probe was rejected by the environment usage
    gate, so live public combo coverage could not be verified in this shell.
  - Scraper therefore attempts the official domain and linked public ranking
    pages defensively, with Ophardt-style GET HTML parsing because nearby
    federation sources commonly expose public national rankings that way.

Expected Portuguese headers:
  Posição | Nome | Clube | Pontos
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "por_fencing"
COUNTRY = "Portugal"
CC = "por"
BASE_URL = "https://fpesgrima.pt"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
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

OFFICIAL_PROBE_URLS = [
    BASE_URL,
    f"{BASE_URL}/ranking",
    f"{BASE_URL}/rankings",
    f"{BASE_URL}/classificacoes",
    f"{BASE_URL}/classificações",
    f"{BASE_URL}/competicao/rankings",
    f"{BASE_URL}/competição/rankings",
    "https://www.fpesgrima.pt",
    "https://www.fpesgrima.pt/ranking",
    "https://www.fpesgrima.pt/rankings",
    "https://www.fpesgrima.pt/classificacoes",
    "https://www.fpesgrima.pt/classificações",
]
OPHARDT_SEARCH_URLS = [
    "https://fencing.ophardt.online/pt/search/rankings",
    "https://fencing.ophardt.online/en/search/rankings",
]

_HEADER_ALIASES = {
    "rank": {
        "rank",
        "ranking",
        "pos",
        "posicao",
        "posicao",
        "classificacao",
        "classificacao",
        "lugar",
        "place",
    },
    "name": {"nome", "name", "atleta", "fencer", "tirador", "esgrimista"},
    "club": {"clube", "club", "clubes", "clubs", "associacao", "associacoes"},
    "points": {"pontos", "points", "point", "pts", "total", "totalpoints"},
}
_SKIP_TOKENS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "total",
    "totais",
    "resumo",
    "sumario",
    "summary",
    "desclassificado",
    "desclassificada",
    "ausente",
}
_RANKING_LINK_CACHE: dict[tuple[str, str, str], str] | None = None


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils if available."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        from season_utils import normalize_season

        return normalize_season(end_year)
    except Exception:
        return f"{end_year - 1:04d}-{end_year:04d}"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value).lower())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def _is_skip_text(value: str) -> bool:
    token = _normalize_token(value)
    return token in _SKIP_TOKENS or token.startswith("total")


def _cell_text(cell: Tag, *, prefer_name: bool = False) -> str:
    if prefer_name:
        dropdown = cell.find("a", class_=lambda value: value and "dropdown-toggle" in value)
        if dropdown:
            return _clean_text(dropdown.get_text(" ", strip=True))

    clone = BeautifulSoup(str(cell), "html.parser").find(cell.name)
    if clone is None:
        return _clean_text(cell.get_text(" ", strip=True))

    for unwanted in clone.select("table, ul, .modal, .dropdown-menu, script, style"):
        unwanted.decompose()

    text = _clean_text(clone.get_text(" ", strip=True))
    text = re.split(r"\s+(?:Detalhes?|Details?|Biografia|Biography)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return _clean_text(text)


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for index, header in enumerate(headers):
        token = _normalize_token(header)
        for field, aliases in _HEADER_ALIASES.items():
            if field not in indexes and token in aliases:
                indexes[field] = index
    return indexes


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None
    match = re.match(r"^\s*(\d{1,5})", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None

    number_match = re.search(r"[-+]?\d[\d\s\xa0\u202f'.,]*", text)
    if not number_match:
        return None

    number = number_match.group(0)
    number = number.replace("\xa0", "").replace("\u202f", "").replace(" ", "").replace("'", "")
    if number in {"", "-", ".", ","}:
        return None

    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        parts = number.split(",")
        if len(parts) == 2 and len(parts[1]) in {1, 2}:
            number = f"{parts[0]}.{parts[1]}"
        else:
            number = number.replace(",", "")
    elif "." in number and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", number):
        number = number.replace(".", "")

    try:
        return float(number)
    except ValueError:
        return None


def _top_level_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Portuguese/Ophardt ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        for header_index, header_row in enumerate(rows):
            header_cells = _row_cells(header_row)
            if not header_cells:
                continue

            headers = [_cell_text(cell) for cell in header_cells]
            indexes = _header_indexes(headers)
            if not {"rank", "name", "points"}.issubset(indexes):
                continue

            max_index = max(indexes["rank"], indexes["name"], indexes["points"], indexes.get("club", 0))
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) <= max_index:
                    continue

                rank = _parse_rank(_cell_text(cells[indexes["rank"]]))
                if rank is None:
                    continue

                name = _cell_text(cells[indexes["name"]], prefer_name=True)
                if not name or _is_skip_text(name):
                    continue

                club = None
                if "club" in indexes and indexes["club"] < len(cells):
                    club = _cell_text(cells[indexes["club"]]) or None

                results.append(
                    {
                        "rank": rank,
                        "name": name,
                        "club": club,
                        "points": _parse_points(_cell_text(cells[indexes["points"]])),
                    }
                )

    return results


def _weapon_from_text(value: str) -> str | None:
    token = _normalize_token(value)
    if "espada" in token or "epee" in token:
        return "Epee"
    if "florete" in token or "foil" in token:
        return "Foil"
    if "sabre" in token or "saber" in token:
        return "Sabre"
    return None


def _gender_from_text(value: str) -> str | None:
    token = _normalize_token(value)
    if any(part in token for part in ("feminino", "feminina", "women", "female", "dames")):
        return "Women"
    if any(part in token for part in ("masculino", "masculina", "mens", "men", "male", "homens")):
        return "Men"
    return None


def _category_from_text(value: str) -> str | None:
    token = _normalize_token(value)
    if "junior" in token or "juniores" in token or "u20" in token or "sub20" in token:
        return "Junior"
    if "senior" in token or "seniores" in token:
        return "Senior"
    return None


def _matrix_descriptors(rows: list[Tag]) -> tuple[int, list[tuple[str, str] | None]] | None:
    for index, row in enumerate(rows[:4]):
        cells = _row_cells(row)
        if len(cells) < 2:
            continue
        descriptors = [(_weapon_from_text(_cell_text(cell)), _gender_from_text(_cell_text(cell))) for cell in cells[1:]]
        if any(weapon and gender for weapon, gender in descriptors):
            return index, [(weapon, gender) if weapon and gender else None for weapon, gender in descriptors]

    if len(rows) < 2:
        return None

    first_cells = _row_cells(rows[0])
    second_cells = _row_cells(rows[1])
    if len(first_cells) < 2 or len(second_cells) < 2:
        return None

    genders: list[str | None] = []
    for cell in first_cells[1:]:
        colspan = int(cell.get("colspan", 1) or 1)
        genders.extend([_gender_from_text(_cell_text(cell))] * colspan)

    weapons = [_weapon_from_text(_cell_text(cell)) for cell in second_cells[1:]]
    descriptors = [
        (weapon, gender) if weapon and gender else None
        for weapon, gender in zip(weapons, genders, strict=False)
    ]
    if any(descriptors):
        return 1, descriptors
    return None


def _extract_ranking_links(html: str, *, base_url: str) -> dict[tuple[str, str, str], str]:
    """Extract combo-specific ranking links from Portuguese/Ophardt index HTML."""
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    links: dict[tuple[str, str, str], str] = {}

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        matrix = _matrix_descriptors(rows)
        if matrix:
            header_index, descriptors = matrix
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) < 2:
                    continue
                category = _category_from_text(_cell_text(cells[0]))
                if not category:
                    continue
                for descriptor, cell in zip(descriptors, cells[1:], strict=False):
                    if not descriptor:
                        continue
                    anchor = cell.find("a", href=True)
                    if anchor:
                        links[(descriptor[0], descriptor[1], category)] = urljoin(base_url, anchor["href"])

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "rank" not in href.lower():
            continue
        context = " ".join(
            [
                anchor.get_text(" ", strip=True),
                anchor.find_parent("tr").get_text(" ", strip=True) if anchor.find_parent("tr") else "",
                href,
            ]
        )
        weapon = _weapon_from_text(context)
        gender = _gender_from_text(context)
        category = _category_from_text(context)
        if weapon and gender and category:
            links[(weapon, gender, category)] = urljoin(base_url, href)

    return links


def _looks_like_portugal_link(anchor: Tag) -> bool:
    text = _normalize_token(anchor.get_text(" ", strip=True))
    href = _normalize_token(anchor.get("href", ""))
    combined = f"{text} {href}"
    return any(token in combined for token in ("portugal", "portuguesa", "fpesgrima", "esgrimapt"))


def _extract_index_links(html: str, *, base_url: str, require_portugal_hint: bool = False) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        lower = href.lower()
        if "/search/rankings" not in lower or "/show/" in lower:
            continue
        if require_portugal_hint and not _looks_like_portugal_link(anchor):
            continue
        url = urljoin(base_url, href)
        if url not in found:
            found.append(url)
    return found


def _is_login_or_blocked_page(html: str) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    text = _normalize_token(soup.get_text(" ", strip=True))
    has_table = bool(soup.find("table"))
    has_password = bool(soup.find("input", {"type": "password"}))
    if has_password or any(token in text for token in ("acessonegado", "accessdenied", "recaptcha")):
        return True
    if not has_table and any(token in text for token in ("iniciarsessao", "login", "autenticacao", "authentication")):
        return True
    has_script = bool(soup.find("script"))
    has_app_root = bool(soup.find(id=re.compile(r"^(root|app|__next)$")))
    if not has_table and has_script and (has_app_root or "enablejavascript" in text or "javascript" in text):
        return True
    return False


def _fetch_discovery_url(url: str):
    return federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)


def _discover_ranking_links() -> dict[tuple[str, str, str], str]:
    global _RANKING_LINK_CACHE
    if _RANKING_LINK_CACHE is not None:
        return _RANKING_LINK_CACHE

    links: dict[tuple[str, str, str], str] = {}
    index_urls: list[str] = []

    for url in OFFICIAL_PROBE_URLS:
        try:
            response = _fetch_discovery_url(url)
        except requests.RequestException as exc:
            print(f"    Probe request error for {url}: {exc}")
            continue

        if response.status_code != 200:
            print(f"    Probe HTTP {response.status_code} for {url}")
            continue
        if _is_login_or_blocked_page(response.text):
            print(f"    Probe blocked/login/JS-only page for {response.url}")
            continue

        links.update(_extract_ranking_links(response.text, base_url=response.url))
        for index_url in _extract_index_links(response.text, base_url=response.url):
            if index_url not in index_urls:
                index_urls.append(index_url)

    for search_url in OPHARDT_SEARCH_URLS:
        try:
            response = _fetch_discovery_url(search_url)
        except requests.RequestException as exc:
            print(f"    Ophardt search request error for {search_url}: {exc}")
            continue
        if response.status_code != 200 or _is_login_or_blocked_page(response.text):
            continue
        for index_url in _extract_index_links(response.text, base_url=response.url, require_portugal_hint=True):
            if index_url not in index_urls:
                index_urls.append(index_url)

    for index_url in index_urls:
        try:
            response = federation_request(
                "get",
                index_url,
                headers=HEADERS,
                params={"season": current_season().split("-")[-1]},
                timeout=20,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            print(f"    Ranking index request error for {index_url}: {exc}")
            continue

        if response.status_code != 200:
            print(f"    Ranking index HTTP {response.status_code} for {index_url}")
            continue
        if _is_login_or_blocked_page(response.text):
            print(f"    Ranking index blocked/login/JS-only page for {response.url}")
            continue
        links.update(_extract_ranking_links(response.text, base_url=response.url))

    _RANKING_LINK_CACHE = links
    return links


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return _discover_ranking_links().get((weapon, gender, category))


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Portugal ranking page. Return None on 404/network/blocked pages."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL} for {weapon} {gender} {category}")
        return None

    last_error = None
    for attempt in range(1, 4):
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=25, allow_redirects=True)
        except requests.RequestException as exc:
            last_error = exc
            print(f"    Request error for {url} (attempt {attempt}/3): {exc}")
            if attempt < 3:
                time.sleep(min(REQUEST_DELAY * attempt, 5))
            continue

        if response.status_code == 200:
            if _is_login_or_blocked_page(response.text):
                print(f"    Blocked/login/JS-only page for {response.url}")
                return None
            return response.text
        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            return None

        print(f"    HTTP {response.status_code} for {url} (attempt {attempt}/3)")
        if response.status_code in {403, 408, 425, 429} or response.status_code >= 500:
            if attempt < 3:
                time.sleep(min(REQUEST_DELAY * attempt, 5))
            continue
        return None

    if last_error:
        print(f"    Giving up after request errors for {url}: {last_error}")
    return None


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_por").start()
    season = current_season()
    print(f"Portugal federation rankings — season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    missing_combos: list[str] = []

    try:
        discovered_links = _discover_ranking_links()
        if not discovered_links:
            print(f"No scrapeable rankings at {BASE_URL}")

        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            url = discovered_links.get((weapon, gender, category))
            print(f"  {label}...")

            if not url:
                print(f"    No public ranking URL discovered")
                missing_combos.append(label)
                total_skipped += 1
                time.sleep(REQUEST_DELAY)
                continue

            html = fetch_rankings_page(weapon, gender, category)
            if html is None:
                failed_combos.append(label)
                total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                failed_combos.append(label)
                total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue

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
                        "cc": CC,
                        "source_url": url,
                        "probe_url": BASE_URL,
                        "request_method": "GET",
                        "response_format": "html",
                    },
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        metadata = {
            "season": season,
            "source": BASE_URL,
            "request_method": "GET",
            "response_format": "html",
            "combos_total": len(RANKING_COMBOS),
            "combos_working": len(working_combos),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "missing_public_combos": missing_combos,
            "probe_notes": (
                "Local live probe hit sandbox DNS failures and escalated probe was rejected by "
                "the environment usage-limit gate. Runtime discovery checks official FP Esgrima "
                "pages and linked public Ophardt ranking indexes."
            ),
        }
        set_state(SOURCE, "last_run", metadata)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=metadata,
        )
        print(
            f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}, "
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
