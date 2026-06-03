"""
scrape_fed_svk.py - Slovakia national federation rankings scraper.

Probe findings, 2026-06-02:
  - Requested hosts `slovakfencing.sk` and `www.slovakfencing.sk` do not resolve.
  - Public federation host is https://www.slovak-fencing.sk.
  - Working rankings page:
      GET https://www.slovak-fencing.sk/site/slovensky-pohar-aktual/
  - Response format is public HTML linking direct application/pdf standings:
      /Source/SSZ/Slov-pohar/SPYYYY-YY/*.pdf
  - Public required combo coverage on the current page is 8/12:
      Foil/Epee Senior/Junior Men/Women.
    No Sabre Senior/Junior Men/Women ranking links were exposed during probe.

PDF text headers observed from pdfplumber:
  Č. Meno r. Klub ... Spolu
  # MENO ROČNÍK KLUB BODY
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

SOURCE = "svk_fencing"
COUNTRY = "Slovakia"
BASE_URL = "https://www.slovak-fencing.sk/site/slovensky-pohar-aktual/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
    "Referer": "https://www.slovak-fencing.sk/",
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

_WEAPON_LABELS = {
    "fleuret": "Foil",
    "floret": "Foil",
    "kord": "Epee",
    "epée": "Epee",
    "epee": "Epee",
    "sabla": "Sabre",
    "sable": "Sabre",
    "sabre": "Sabre",
}
_GENDER_CATEGORY_LABELS = {
    "seniori": ("Men", "Senior"),
    "seniorky": ("Women", "Senior"),
    "juniori": ("Men", "Junior"),
    "juniorky": ("Women", "Junior"),
}
_RANK_HEADERS = {"poradie", "c", "cislo", "rank", "#"}
_NAME_HEADERS = {"meno", "name", "pretekár", "pretekar", "m"}
_CLUB_HEADERS = {"klub", "club", "oddiel"}
_POINT_HEADERS = {"body", "spolu", "points", "total"}
_SKIP_TOKENS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "ret",
    "wd",
    "wdr",
    "sucet",
    "suhrn",
    "spolu",
    "summary",
    "total",
    "ranking",
    "poradie",
}
_JS_ONLY_RE = re.compile(r"<script\b[^>]*>.*?</script>|<script\b[^>]*src=", re.IGNORECASE | re.DOTALL)
_LOGIN_RE = re.compile(r"(login|prihl[aá]s|password|heslo)", re.IGNORECASE)
_DISCOVERED_URLS: dict[tuple[str, str, str], str] | None = None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _header_key(value: str) -> str:
    value = _strip_accents(_clean_text(value)).lower()
    value = value.replace("č", "c").replace("Č", "c")
    return re.sub(r"[^a-z0-9#]+", "", value)


def _is_skip_text(value: str) -> bool:
    key = _header_key(value)
    return key in _SKIP_TOKENS or any(token in key for token in ("sucet", "summary", "total"))


def _parse_rank(raw: str) -> int | None:
    text = _clean_text(raw)
    if not text or _is_skip_text(text):
        return None
    match = re.match(r"^\s*(\d{1,5})(?:[.)])?\b", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(raw: str) -> float | None:
    value = _clean_text(raw)
    if not value or _is_skip_text(value):
        return None
    value = value.replace(" ", "")
    value = re.sub(r"(?i)(body|points|spolu|total|pts)", "", value)
    value = re.sub(r"[^0-9,.\-]", "", value)
    if not value or value in {"-", ".", ","}:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            value = f"{parts[0]}.{parts[1]}"
        else:
            value = value.replace(",", "")
    elif "." in value and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def _find_header_mapping(labels: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, label in enumerate(labels):
        key = _header_key(label)
        if key in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif key in _CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif key in _POINT_HEADERS and "points" not in mapping:
            mapping["points"] = idx

    return mapping if {"rank", "name", "points"}.issubset(mapping) else None


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        mapping: dict[str, int] | None = None
        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            texts = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            candidate = _find_header_mapping(texts)
            if candidate:
                mapping = candidate
                continue
            if not mapping:
                continue

            if len(texts) <= max(mapping.values()):
                continue
            rank = _parse_rank(texts[mapping["rank"]])
            if rank is None:
                continue
            name = texts[mapping["name"]]
            if not name or _is_skip_text(name):
                continue
            club = texts[mapping["club"]] if "club" in mapping else None
            points = _parse_points(texts[mapping["points"]])
            results.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return results


def _is_numeric_token(token: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:[.,]\d+)?", token))


def _is_year_token(token: str) -> bool:
    token = token.strip()
    return bool(re.fullmatch(r"\d{2}|\d{4}", token))


def _club_start_index(tokens: list[str]) -> int:
    if not tokens:
        return 0

    known_single = {"AŠ", "BŠK", "BB", "Ravens", "Willard", "Dunaj", "Snina", "STU"}
    for idx, token in enumerate(tokens):
        if token in {"KŠ", "STU"} and idx + 1 < len(tokens):
            return idx
        if token in known_single:
            return idx
        if token.isupper() and len(token) <= 4 and idx >= 2:
            return idx
    return max(len(tokens) - 1, 0)


def _parse_pdf_line(line: str, *, body_layout: bool) -> dict | None:
    rank_match = re.match(r"^(\d{1,5})(?:[.)])?\s+(.+)$", line)
    if not rank_match:
        return None

    rank = _parse_rank(rank_match.group(1))
    if rank is None:
        return None

    tokens = rank_match.group(2).split()
    if len(tokens) < 3:
        return None

    year_idx = None
    for idx, token in enumerate(tokens):
        if (
            _is_year_token(token)
            and idx + 1 < len(tokens)
            and not _is_numeric_token(tokens[idx + 1])
        ):
            year_idx = idx
            break

    if year_idx is not None:
        first_score_idx = len(tokens)
        for idx in range(year_idx + 1, len(tokens)):
            if _is_numeric_token(tokens[idx]):
                first_score_idx = idx
                break
        if first_score_idx == len(tokens):
            return None
        name_tokens = tokens[:year_idx]
        club_tokens = tokens[year_idx + 1:first_score_idx]
        score_tokens = tokens[first_score_idx:]
    else:
        first_score_idx = len(tokens)
        for idx, token in enumerate(tokens):
            if _is_numeric_token(token):
                first_score_idx = idx
                break
        if first_score_idx == len(tokens):
            return None
        identity_tokens = tokens[:first_score_idx]
        score_tokens = tokens[first_score_idx:]
        club_idx = _club_start_index(identity_tokens)
        name_tokens = identity_tokens[:club_idx]
        club_tokens = identity_tokens[club_idx:]

    name = " ".join(name_tokens).strip()
    club = " ".join(club_tokens).strip() or None
    if not name or _is_skip_text(name):
        return None

    points_token = score_tokens[0] if body_layout else score_tokens[-1]
    points = _parse_points(points_token)
    if points is None:
        return None

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_pdf_text(text: str) -> list[dict]:
    results: list[dict] = []
    body_layout = False
    in_rankings = False

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or _is_skip_text(line):
            continue

        header_key = _header_key(line)
        if "menorocnikklubbody" in header_key or "menorokklubbody" in header_key:
            body_layout = True
            in_rankings = True
            continue
        if ("menorklub" in header_key or "menorokklub" in header_key) and "spolu" in header_key:
            body_layout = False
            in_rankings = True
            continue

        if not in_rankings and _parse_rank(line.split(" ", 1)[0]) is None:
            continue

        parsed = _parse_pdf_line(line, body_layout=body_layout)
        if parsed:
            results.append(parsed)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Slovakia HTML or extracted PDF standings text into ranking rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    if re.search(r"<\s*(html|body|table|tr|td|th)\b", html_or_text, flags=re.IGNORECASE):
        html_rows = _parse_html_table(html_or_text)
        if html_rows:
            return html_rows

    return _parse_pdf_text(html_or_text)


def _label_to_combo(label: str) -> tuple[str, str, str] | None:
    key = _header_key(label)
    weapon = None
    for token, value in _WEAPON_LABELS.items():
        if token in key:
            weapon = value
            break
    if not weapon:
        return None

    for token, (gender, category) in _GENDER_CATEGORY_LABELS.items():
        if token in key:
            return (weapon, gender, category)
    return None


def _extract_ranking_links(html: str, *, base_url: str = BASE_URL) -> dict[tuple[str, str, str], str]:
    """Extract public Slovak cup PDF links from the federation rankings page."""
    soup = BeautifulSoup(html or "", "html.parser")
    links: dict[tuple[str, str, str], str] = {}

    for anchor in soup.find_all("a", href=True):
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = urljoin(base_url, anchor["href"])
        if not re.search(r"\.pdf(?:$|\?)", href, re.IGNORECASE):
            continue

        combo = _label_to_combo(label)
        if combo and combo in RANKING_COMBOS:
            links[combo] = href

    return links


def discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    """Discover current public ranking PDF URLs from the Slovakia standings page."""
    global _DISCOVERED_URLS
    if _DISCOVERED_URLS is not None:
        return dict(_DISCOVERED_URLS)

    try:
        response = federation_request("get", BASE_URL, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"  Ranking index request failed: {exc}")
        _DISCOVERED_URLS = {}
        return {}

    if response.status_code != 200:
        print(f"  Ranking index HTTP {response.status_code}: {BASE_URL}")
        _DISCOVERED_URLS = {}
        return {}

    _DISCOVERED_URLS = _extract_ranking_links(response.text, base_url=response.url)
    return dict(_DISCOVERED_URLS)


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber is required to parse Slovakia ranking PDFs")
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(
                page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages
            )
    except Exception as exc:
        print(f"    PDF parse error: {exc}")
        return None


def _looks_unscrapeable_html(text: str) -> bool:
    soup = BeautifulSoup(text or "", "html.parser")
    visible = _clean_text(soup.get_text(" ", strip=True))
    if soup.find("input", {"type": "password"}) or soup.find("form") and _LOGIN_RE.search(visible):
        return True
    if soup.find("table"):
        return False
    if soup.find(id="app") and _JS_ONLY_RE.search(text):
        return True
    if _JS_ONLY_RE.search(text) and not visible:
        return True
    return False


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Slovakia ranking page/PDF, returning None for failures."""
    links = discover_ranking_urls()
    url = links.get((weapon, gender, category))
    if not url:
        print(f"    No public ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        return _extract_pdf_text(response.content)

    if "html" in content_type and _looks_unscrapeable_html(response.text):
        print(f"    No scrapeable rankings at {url}")
        return None

    return response.text


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils if present."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        from season_utils import normalize_season

        return normalize_season(end_year)
    except Exception:
        return f"{end_year - 1:04d}-{end_year:04d}"


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_svk").start()
    season = current_season()
    print(f"Slovakia federation rankings - season {season}")
    print(f"Ranking index: {BASE_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    public_urls = discover_ranking_urls()

    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            text = fetch_rankings_page(weapon, gender, category)
            if not text:
                total_failed += 1
                failed_combos.append(f"{label}: no public scrapeable ranking")
            else:
                parsed = parse_rankings_table(text)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(f"{label}: no rows parsed")
                else:
                    source_url = public_urls.get((weapon, gender, category))
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
                            metadata={"source_url": source_url} if source_url else {},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Written {written} rows ({len(parsed)} parsed)")
                    total_written += written

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "working_url": BASE_URL,
            "request_method": "GET",
            "response_format": "html index with application/pdf rankings",
            "public_combos": [
                _combo_label(*combo) for combo in RANKING_COMBOS if combo in public_urls
            ],
            "failed_combos": failed_combos,
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=summary,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
