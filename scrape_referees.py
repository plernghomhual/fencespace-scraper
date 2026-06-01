import io
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FIE_BASE_URL = "https://fie.org"
FIE_REFEREES_URL = f"{FIE_BASE_URL}/referees"
FIE_REFEREES_SEARCH_URL = f"{FIE_BASE_URL}/referees/search"
FIE_REFEREE_COMMISSION_URL = f"{FIE_BASE_URL}/fie/structure/council/CA"
SOURCE = "fie_referees"
REQUEST_DELAY_SECONDS = float(os.environ.get("FIE_REFEREES_DELAY", "1.0"))
BATCH_SIZE = int(os.environ.get("FIE_REFEREES_BATCH_SIZE", "100"))
MAX_SEARCH_PAGES = int(os.environ.get("FIE_REFEREES_MAX_SEARCH_PAGES", "50"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "application/json,text/html,application/pdf,*/*",
    "Referer": FIE_REFEREES_URL,
}

_supabase = None


WEAPON_CODES = {
    "E": "Epee",
    "F": "Foil",
    "S": "Sabre",
}

WEAPON_ALIASES = {
    "epee": "Epee",
    "epée": "Epee",
    "épée": "Epee",
    "degen": "Epee",
    "spada": "Epee",
    "foil": "Foil",
    "fleuret": "Foil",
    "fioretto": "Foil",
    "florett": "Foil",
    "sabre": "Sabre",
    "saber": "Sabre",
    "sabel": "Sabre",
    "sciabola": "Sabre",
}

CATEGORY_ORDER = {"A": 0, "B": 1, "C": 2}


def get_supabase():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def clean_text(value: Any) -> str | None:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    upper = text.upper()
    if re.fullmatch(r"[A-Z]{3}", upper):
        return upper
    return text


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _highest_category(categories: list[str]) -> str | None:
    valid = [cat.upper() for cat in categories if cat and cat.upper() in CATEGORY_ORDER]
    if not valid:
        return None
    return sorted(valid, key=lambda cat: CATEGORY_ORDER[cat])[0]


def parse_weapon_category(value: Any) -> tuple[list[str], str | None, dict[str, str]]:
    text = clean_text(value) or ""
    weapons: list[str] = []
    categories: list[str] = []
    weapon_categories: dict[str, str] = {}

    for code, category in re.findall(r"\b([EFS])\s*[=:]?\s*([ABC])\b", text, flags=re.IGNORECASE):
        weapon = WEAPON_CODES.get(code.upper())
        if not weapon:
            continue
        if weapon not in weapons:
            weapons.append(weapon)
        category = category.upper()
        categories.append(category)
        weapon_categories[weapon] = category

    alias_pattern = "|".join(sorted((re.escape(k) for k in WEAPON_ALIASES), key=len, reverse=True))
    for match in re.finditer(rf"\b({alias_pattern})\b\s*[=: -]*\s*([ABC])?", text, flags=re.IGNORECASE):
        weapon = WEAPON_ALIASES.get(match.group(1).lower())
        if not weapon:
            continue
        if weapon not in weapons:
            weapons.append(weapon)
        category = (match.group(2) or "").upper()
        if category:
            categories.append(category)
            weapon_categories.setdefault(weapon, category)

    if not categories:
        categories.extend(cat.upper() for cat in re.findall(r"\b([ABC])\b", text, flags=re.IGNORECASE))

    return weapons, _highest_category(categories), weapon_categories


def build_referee_row(
    *,
    name: Any,
    country: Any = None,
    fie_license_id: Any = None,
    category_text: Any = None,
    metadata: dict | None = None,
) -> dict | None:
    clean_name = clean_text(name)
    if not clean_name:
        return None

    certification_level = clean_text(category_text)
    weapons, category, weapon_categories = parse_weapon_category(certification_level)
    row_metadata = dict(metadata or {})
    if weapon_categories:
        row_metadata["weapon_categories"] = weapon_categories

    return {
        "name": clean_name,
        "country": normalize_country(country),
        "fie_license_id": clean_text(fie_license_id),
        "category": category,
        "certification_level": certification_level,
        "weapons": weapons or None,
        "metadata": row_metadata,
    }


def parse_referees_json(payload: str | list[dict] | dict) -> list[dict]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or data.get("referees") or []
    else:
        items = data

    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        country = item.get("countryCode") or item.get("country")
        metadata = {
            "source": FIE_REFEREES_SEARCH_URL,
            "source_country": item.get("country"),
        }
        for key in ["flag", "gender", "age", "date"]:
            if item.get(key) is not None:
                metadata[key] = item.get(key)
        row = build_referee_row(
            name=item.get("name"),
            country=country,
            fie_license_id=item.get("id") or item.get("license") or item.get("licenseId"),
            category_text=item.get("weaponCategory") or item.get("category"),
            metadata=metadata,
        )
        if row:
            rows.append(row)
    return rows


def _table_headers(table) -> list[str]:
    header_cells = table.select("thead th")
    if not header_cells:
        first_row = table.find("tr")
        header_cells = first_row.find_all(["th", "td"]) if first_row else []
    return [_norm_key(cell.get_text(" ", strip=True)) for cell in header_cells]


def _value_by_header(cells: list[str], headers: list[str], wanted: set[str]) -> str | None:
    for index, header in enumerate(headers):
        if index < len(cells) and header in wanted:
            return cells[index]
    return None


def parse_referees_html(html: str, source_url: str | None = None) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for table in soup.find_all("table"):
        headers = _table_headers(table)
        if not headers:
            continue
        joined_headers = " ".join(headers)
        if "name" not in joined_headers and "nom" not in joined_headers:
            continue

        body_rows = table.select("tbody tr") or table.find_all("tr")[1:]
        for tr in body_rows:
            cells = [clean_text(td.get_text(" ", strip=True)) or "" for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            name = _value_by_header(cells, headers, {"name", "nom", "referee", "arbitre"}) or cells[1]
            country = _value_by_header(cells, headers, {"country", "countrycode", "nation", "nationality", "pays"})
            license_id = _value_by_header(cells, headers, {"licenseid", "licenceid", "license", "licence", "fielicenseid", "id"})
            category = _value_by_header(cells, headers, {"category", "weaponcategory", "certification", "level", "categorie"})
            row = build_referee_row(
                name=name,
                country=country,
                fie_license_id=license_id,
                category_text=category,
                metadata={"source": source_url or FIE_REFEREES_URL},
            )
            if row:
                rows.append(row)

    if rows:
        return rows

    for card in soup.select("li, article, .card, .person, .member"):
        text = clean_text(card.get_text(" ", strip=True))
        if not text or not re.search(r"\b[A-Z][A-Za-z' -]+ [A-Z][A-Za-z' -]+\b", text):
            continue
        category_match = re.search(r"\b(?:[EFS]\s*[=:]\s*[ABC]|Epee|Épée|Foil|Fleuret|Sabre|Saber)\b.*", text, re.IGNORECASE)
        country_match = re.search(r"\b[A-Z]{3}\b", text)
        name = text
        if country_match:
            name = text[:country_match.start()].strip(" -|,")
        row = build_referee_row(
            name=name,
            country=country_match.group(0) if country_match else None,
            category_text=category_match.group(0) if category_match else None,
            metadata={"source": source_url or FIE_REFEREES_URL, "raw_text": text[:500]},
        )
        if row:
            rows.append(row)
    return rows


def parse_referee_pdf_text(text: str, source_url: str | None = None) -> list[dict]:
    rows: list[dict] = []
    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if not line or re.search(r"license\s+name\s+country", line, re.IGNORECASE):
            continue
        match = re.match(r"^(\d{2,})\s+(.+?)\s+([A-Z]{3})\s+(.+)$", line)
        if not match:
            continue
        license_id, name, country, category = match.groups()
        row = build_referee_row(
            name=name,
            country=country,
            fie_license_id=license_id,
            category_text=category,
            metadata={"source": source_url or "pdf_text"},
        )
        if row:
            rows.append(row)
    return rows


def parse_referee_pdf_bytes(pdf_bytes: bytes, source_url: str | None = None) -> list[dict]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse PDF referee lists") from exc

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return parse_referee_pdf_text("\n".join(text_parts), source_url=source_url)


def parse_referee_response(content: bytes, content_type: str, source_url: str) -> list[dict]:
    if "pdf" in content_type.lower() or source_url.lower().endswith(".pdf"):
        return parse_referee_pdf_bytes(content, source_url=source_url)

    text = content.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped.startswith("[") or stripped.startswith("{"):
        return parse_referees_json(text)
    return parse_referees_html(text, source_url=source_url)


def fetch_referee_search_pages(session: requests.Session) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, MAX_SEARCH_PAGES + 1):
        response = session.get(
            FIE_REFEREES_SEARCH_URL,
            headers=HEADERS,
            params={"fetchPage": page},
            timeout=20,
        )
        if response.status_code != 200 or not response.content:
            print(f"  {FIE_REFEREES_SEARCH_URL} page {page} returned HTTP {response.status_code}")
            break
        page_rows = parse_referee_response(
            response.content,
            response.headers.get("content-type", ""),
            FIE_REFEREES_SEARCH_URL,
        )
        if not page_rows:
            break
        rows.extend(page_rows)
        time.sleep(REQUEST_DELAY_SECONDS)
    return rows


def fetch_referees(session: requests.Session | None = None) -> list[dict]:
    session = session or requests.Session()
    try:
        rows = fetch_referee_search_pages(session)
        if rows:
            return rows
    except Exception as exc:
        print(f"  Failed to fetch {FIE_REFEREES_SEARCH_URL}: {exc}")

    urls = [FIE_REFEREES_URL, FIE_REFEREE_COMMISSION_URL]
    for index, url in enumerate(urls):
        try:
            response = session.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200 or not response.content:
                print(f"  {url} returned HTTP {response.status_code}")
                continue
            rows = parse_referee_response(response.content, response.headers.get("content-type", ""), url)
            if rows:
                return rows
        except Exception as exc:
            print(f"  Failed to fetch {url}: {exc}")
        if index < len(urls) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)
    return []


def upsert_referees(rows: list[dict], client=None) -> int:
    client = client or get_supabase()
    if not client or not rows:
        return 0

    deduped: dict[tuple[str, str], dict] = {}
    for row in rows:
        name = clean_text(row.get("name"))
        if not name:
            continue
        normalized = dict(row)
        normalized["name"] = name
        key = ("license", normalized.get("fie_license_id")) if normalized.get("fie_license_id") else (
            "name_country",
            f"{name}|{normalized.get('country') or ''}",
        )
        deduped[key] = normalized

    written = 0
    values = list(deduped.values())
    for i in range(0, len(values), BATCH_SIZE):
        batch = values[i:i + BATCH_SIZE]
        client.table("fs_referees").upsert(batch, on_conflict="fie_license_id").execute()
        written += len(batch)
    return written


def main() -> None:
    client = get_supabase()
    if not client:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_referees").start()
    total_written = 0
    total_failed = 0
    try:
        print(f"FIE referee scraper starting — {datetime.now(timezone.utc).isoformat()}")
        rows = fetch_referees()
        total_written = upsert_referees(rows, client=client)
        skipped = max(len(rows) - total_written, 0)
        set_state(
            SOURCE,
            "last_run",
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "rows_fetched": len(rows),
                "rows_written": total_written,
            },
        )
        run_log.complete(written=total_written, failed=total_failed, skipped=skipped)
        print(f"Done — fetched={len(rows)}, written={total_written}, skipped={skipped}")
    except Exception as exc:
        total_failed += 1
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
