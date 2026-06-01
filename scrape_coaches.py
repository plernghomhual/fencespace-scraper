import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "national_team_coaches"
REQUEST_DELAY_SECONDS = float(os.environ.get("COACHES_DELAY", "1.0"))
BATCH_SIZE = int(os.environ.get("COACHES_BATCH_SIZE", "100"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TOP_FEDERATION_SOURCES = [
    {"country": "USA", "federation": "USA Fencing", "urls": ["https://www.usafencing.org/national-team-staff"]},
    {"country": "FRA", "federation": "FF Escrime", "urls": ["https://www.ffescrime.fr/haut-niveau/structures-du-programme-dexcellence/insep/"]},
    {"country": "ITA", "federation": "Federazione Italiana Scherma", "urls": ["https://federscherma.it/scherma-olimpica/", "https://federscherma.it/alto-livello/"]},
    {"country": "KOR", "federation": "Korea Fencing Federation", "urls": ["https://koreafencing.org/"]},
    {"country": "JPN", "federation": "Japan Fencing Federation", "urls": ["https://fencing-jpn.jp/", "https://fencing-jpn.jp/national/"]},
    {"country": "CHN", "federation": "Chinese Fencing Association", "urls": ["https://www.fencing.org.cn/"]},
    {"country": "HUN", "federation": "Hungarian Fencing Federation", "urls": ["https://hunfencing.hu/valogatott/", "https://hunfencing.hu/"]},
    {"country": "GER", "federation": "Deutscher Fechter-Bund", "urls": ["https://www.fechten.org/nationalmannschaft", "https://www.fechten.org/"]},
    {"country": "POL", "federation": "Polski Zwiazek Szermierczy", "urls": ["https://pzszerm.pl/reprezentacja/", "https://pzszerm.pl/"]},
    {"country": "UKR", "federation": "Ukrainian Fencing Federation", "urls": ["https://www.nffu.org.ua/", "https://fencing.org.ua/"]},
    {"country": "ROU", "federation": "Federatia Romana de Scrima", "urls": ["https://frscrima.ro/", "https://www.frscrima.ro/"]},
    {"country": "ESP", "federation": "Real Federacion Espanola de Esgrima", "urls": ["https://www.esgrima.es/", "https://rfee.es/"]},
    {"country": "EGY", "federation": "Egyptian Fencing Federation", "urls": ["https://www.egfencing.com/"]},
    {"country": "HKG", "federation": "Fencing Association of Hong Kong, China", "urls": ["https://www.hkfa.org.hk/"]},
    {"country": "SUI", "federation": "Swiss Fencing", "urls": ["https://swiss-fencing.ch/", "https://swiss-fencing.ch/fr/"]},
    {"country": "EST", "federation": "Estonian Fencing Association", "urls": ["https://vehklemisliit.ee/"]},
    {"country": "GEO", "federation": "Georgian Fencing Federation", "urls": ["https://fencing.ge/"]},
    {"country": "BEL", "federation": "Belgian Fencing", "urls": ["https://www.fencing-belgium.be/"]},
    {"country": "CAN", "federation": "Canadian Fencing Federation", "urls": ["https://fencing.ca/staff/", "https://fencing.ca/senior-national-team-program-coaches/"]},
    {"country": "GBR", "federation": "British Fencing", "urls": ["https://www.britishfencing.com/25-26-gbr-coaches/", "https://www.britishfencing.com/gbr-fencing/gbr-senior/gbr-coaching-panel/"]},
]

COACH_KEYWORDS = [
    "coach",
    "coaching",
    "national team",
    "staff",
    "entraineur",
    "entraîneur",
    "manager",
    "allenatore",
    "trainer",
]

_supabase = None


WEAPON_ALIASES = {
    "foil": "Foil",
    "fleuret": "Foil",
    "fioretto": "Foil",
    "florett": "Foil",
    "epee": "Epee",
    "epée": "Epee",
    "épée": "Epee",
    "spada": "Epee",
    "degen": "Epee",
    "sabre": "Sabre",
    "saber": "Sabre",
    "sabel": "Sabre",
    "sciabola": "Sabre",
}


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


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _looks_like_person_name(value: str | None) -> bool:
    text = clean_text(value) or ""
    if not text or len(text) > 80:
        return False
    if any(token in text.lower() for token in ["national team", "staff", "program", "email", "@"]):
        return False
    words = [word for word in re.split(r"\s+", text) if word]
    return len(words) >= 2 and any(char.isalpha() for char in text)


def normalize_weapons(text: str | None) -> list[str]:
    source = (text or "").lower()
    weapons: list[str] = []
    for alias, weapon in WEAPON_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", source, flags=re.IGNORECASE) and weapon not in weapons:
            weapons.append(weapon)
    return weapons


def coach_id_for(row: dict) -> str:
    key = "|".join(
        [
            clean_text(row.get("country")) or "",
            clean_text(row.get("federation")) or "",
            clean_text(row.get("name")) or "",
            clean_text(row.get("national_team_role")) or "",
        ]
    ).lower()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace.coach:{key}"))


def build_coach_row(
    *,
    name: Any,
    country: str | None,
    federation: str | None,
    role: Any = None,
    weapons: list[str] | None = None,
    metadata: dict | None = None,
) -> dict | None:
    clean_name = clean_text(name)
    if not clean_name or not _looks_like_person_name(clean_name):
        return None

    role_text = clean_text(role)
    row = {
        "name": clean_name,
        "country": clean_text(country),
        "federation": clean_text(federation),
        "national_team_role": role_text,
        "weapons": weapons or normalize_weapons(role_text),
        "metadata": metadata or {},
    }
    row["id"] = coach_id_for(row)
    return row


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


def _append_unique(rows: list[dict], row: dict | None) -> None:
    if not row:
        return
    key = (
        row.get("name"),
        row.get("country"),
        row.get("federation"),
        row.get("national_team_role"),
    )
    for existing in rows:
        if (
            existing.get("name"),
            existing.get("country"),
            existing.get("federation"),
            existing.get("national_team_role"),
        ) == key:
            return
    rows.append(row)


def _parse_tables(soup: BeautifulSoup, country: str | None, federation: str | None, source_url: str | None) -> list[dict]:
    rows: list[dict] = []
    for table in soup.find_all("table"):
        headers = _table_headers(table)
        if not headers:
            continue
        body_rows = table.select("tbody tr") or table.find_all("tr")[1:]
        for tr in body_rows:
            cells = [clean_text(td.get_text(" ", strip=True)) or "" for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            name = _value_by_header(cells, headers, {"name", "nom", "coach", "entraineur", "entraîneur"})
            role = _value_by_header(cells, headers, {"title", "role", "function", "position", "poste"}) or ""
            email = _value_by_header(cells, headers, {"email", "mail", "courriel"})
            if not name and len(cells) >= 2:
                role, name = cells[0], cells[1]
            role_and_row = f"{role} {' '.join(cells)}"
            if not re.search(r"coach|co-coach|entraineur|entraîneur|trainer|manager|performance\s+lead", role or "", re.IGNORECASE):
                continue
            metadata = {"source": source_url} if source_url else {}
            if email:
                metadata["email"] = email
            _append_unique(
                rows,
                build_coach_row(
                    name=name,
                    country=country,
                    federation=federation,
                    role=role,
                    weapons=normalize_weapons(role_and_row),
                    metadata=metadata,
                ),
            )
    return rows


def _parse_heading_colon_rows(soup: BeautifulSoup, country: str | None, federation: str | None, source_url: str | None) -> list[dict]:
    rows: list[dict] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "li", "p"]):
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        match = re.match(
            r"^(.{0,100}?(?:coach|entraineur|entraîneur|manager|performance lead))\s*[:|-]\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        role, name = match.groups()
        name = re.split(r"\s{2,}|\. ", name, maxsplit=1)[0]
        _append_unique(
            rows,
            build_coach_row(
                name=name,
                country=country,
                federation=federation,
                role=role,
                weapons=normalize_weapons(role),
                metadata={"source": source_url} if source_url else {},
            ),
        )
    return rows


def _staff_segments(text: str) -> list[tuple[str, str | None]]:
    segments = []
    for match in re.finditer(
        r"([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+)+)\s*\(([^)]+)\)",
        text,
    ):
        segments.append((match.group(1).strip(), match.group(2).strip()))
    if segments:
        return segments

    for part in re.split(r",|;|\s+-\s+", text):
        candidate = clean_text(part)
        if candidate and _looks_like_person_name(candidate):
            segments.append((candidate, None))
    return segments


def _parse_weapon_heading_sections(soup: BeautifulSoup, country: str | None, federation: str | None, source_url: str | None) -> list[dict]:
    rows: list[dict] = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = clean_text(heading.get_text(" ", strip=True))
        weapons = normalize_weapons(heading_text)
        if not heading_text or not weapons:
            continue

        sibling_texts: list[str] = []
        for sibling in heading.find_next_siblings():
            if getattr(sibling, "name", None) in {"h1", "h2", "h3", "h4"}:
                break
            text = clean_text(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else sibling)
            if text:
                sibling_texts.append(text)
            if len(sibling_texts) >= 3:
                break

        for name, staff_role in _staff_segments(" ".join(sibling_texts)):
            role = f"{heading_text} {staff_role}".strip() if staff_role else heading_text
            _append_unique(
                rows,
                build_coach_row(
                    name=name,
                    country=country,
                    federation=federation,
                    role=role,
                    weapons=weapons,
                    metadata={"source": source_url} if source_url else {},
                ),
            )
    return rows


def _parse_name_dash_weapon_rows(soup: BeautifulSoup, country: str | None, federation: str | None, source_url: str | None) -> list[dict]:
    rows: list[dict] = []
    weapon_words = "|".join(sorted((re.escape(alias) for alias in WEAPON_ALIASES), key=len, reverse=True))
    for node in soup.find_all(["li", "p", "h2", "h3", "h4"]):
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        match = re.match(rf"^(.+?)\s*[-–]\s*({weapon_words})(?:\b|$)", text, flags=re.IGNORECASE)
        if not match:
            continue
        name, weapon_text = match.groups()
        _append_unique(
            rows,
            build_coach_row(
                name=name,
                country=country,
                federation=federation,
                role=f"National Coach - {weapon_text}",
                weapons=normalize_weapons(weapon_text),
                metadata={"source": source_url} if source_url else {},
            ),
        )
    return rows


def parse_coaches_html(
    html: str,
    *,
    country: str | None = None,
    federation: str | None = None,
    source_url: str | None = None,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    rows: list[dict] = []
    for parser in [_parse_tables, _parse_heading_colon_rows, _parse_weapon_heading_sections, _parse_name_dash_weapon_rows]:
        for row in parser(soup, country, federation, source_url):
            _append_unique(rows, row)
    return rows


def _split_names(value: str) -> list[str]:
    names = []
    for part in re.split(r",|\band\b|/|;", value):
        text = clean_text(part)
        if text and _looks_like_person_name(text):
            names.append(text)
    return names


def parse_fencer_coach_relationships(
    html: str,
    *,
    country: str | None = None,
    federation: str | None = None,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    relationships: list[dict] = []

    blocks = soup.find_all(["article", "section", "div"])
    if not blocks:
        blocks = [soup]

    for block in blocks:
        text = clean_text(block.get_text(" ", strip=True)) or ""
        if not text or "coach" not in text.lower():
            continue

        title_node = block.find(["h1", "h2", "h3"]) if hasattr(block, "find") else None
        fencer_name = clean_text(title_node.get_text(" ", strip=True)) if title_node else None
        coach_match = re.search(
            r"\bcoach\s*:\s*(.+?)(?:\bNational team\b|\bTeam\b|\bAthlete\b|$)",
            text,
            flags=re.IGNORECASE,
        )
        if fencer_name and coach_match:
            for coach_name in _split_names(coach_match.group(1)):
                relationships.append(
                    {
                        "coach_name": coach_name,
                        "fencer_name": fencer_name,
                        "country": country,
                        "metadata": {"federation": federation},
                    }
                )

        for match in re.finditer(r"\bcoach\s+([^:]{2,80}):\s*([^.;]+)", text, flags=re.IGNORECASE):
            coach_name = clean_text(match.group(1))
            if not coach_name or not _looks_like_person_name(coach_name):
                continue
            for athlete_name in _split_names(match.group(2)):
                relationships.append(
                    {
                        "coach_name": coach_name,
                        "fencer_name": athlete_name,
                        "country": country,
                        "metadata": {"federation": federation},
                    }
                )

    deduped = []
    seen = set()
    for rel in relationships:
        key = (rel["coach_name"], rel["fencer_name"], rel.get("country"))
        if key not in seen:
            seen.add(key)
            deduped.append(rel)
    return deduped


def load_federation_sources() -> list[dict]:
    override = os.environ.get("COACH_SOURCE_URLS")
    if not override:
        return TOP_FEDERATION_SOURCES
    data = json.loads(override)
    if not isinstance(data, list):
        raise ValueError("COACH_SOURCE_URLS must be a JSON list")
    return data


def _page_has_coach_signal(html: str) -> bool:
    text = (clean_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True)) or "").lower()
    return any(keyword in text for keyword in COACH_KEYWORDS)


def fetch_source_pages(source: dict, session: requests.Session | None = None) -> list[tuple[str, str]]:
    session = session or requests.Session()
    urls = source.get("urls") or []
    if not urls and source.get("base_url"):
        base_url = source["base_url"]
        paths = ["/national-team", "/national-team-staff", "/staff", "/coaches", "/coaching-staff"]
        urls = [urljoin(base_url, path) for path in paths]

    pages: list[tuple[str, str]] = []
    for url in urls:
        try:
            response = session.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200 or not response.text:
                print(f"  {url} returned HTTP {response.status_code}")
                continue
            if _page_has_coach_signal(response.text):
                pages.append((url, response.text))
        except Exception as exc:
            print(f"  Failed to fetch {url}: {exc}")
        time.sleep(REQUEST_DELAY_SECONDS)
    return pages


def _normalize_coach_for_upsert(row: dict) -> dict:
    normalized = dict(row)
    normalized["name"] = clean_text(normalized.get("name"))
    normalized["country"] = clean_text(normalized.get("country"))
    normalized["federation"] = clean_text(normalized.get("federation"))
    normalized["national_team_role"] = clean_text(normalized.get("national_team_role"))
    normalized["weapons"] = normalized.get("weapons") or None
    normalized["metadata"] = normalized.get("metadata") or {}
    normalized["id"] = normalized.get("id") or coach_id_for(normalized)
    return normalized


def match_fencer(client, name: str, country: str | None) -> str | None:
    try:
        query = client.table("fs_fencers").select("id").ilike("name", name)
        if country:
            query = query.eq("country", country)
        result = query.limit(1).execute()
        if result.data:
            return result.data[0].get("id")
    except Exception as exc:
        print(f"  Fencer match failed for {name}: {exc}")
    return None


def upsert_coaches_and_relationships(
    coaches: list[dict],
    relationships: list[dict] | None = None,
    *,
    client=None,
) -> dict[str, int]:
    client = client or get_supabase()
    if not client:
        return {"coaches_written": 0, "relationships_written": 0, "relationships_skipped": len(relationships or [])}

    relationships = relationships or []
    coach_rows: dict[tuple[str, str | None, str | None, str | None], dict] = {}
    for row in coaches:
        normalized = _normalize_coach_for_upsert(row)
        if not normalized.get("name"):
            continue
        key = (
            normalized["name"],
            normalized.get("country"),
            normalized.get("federation"),
            normalized.get("national_team_role"),
        )
        coach_rows[key] = normalized

    for rel in relationships:
        coach_name = clean_text(rel.get("coach_name"))
        if not coach_name:
            continue
        federation = clean_text((rel.get("metadata") or {}).get("federation"))
        if any(
            existing.get("name") == coach_name
            and existing.get("country") == rel.get("country")
            and existing.get("federation") == federation
            for existing in coach_rows.values()
        ):
            continue
        placeholder = _normalize_coach_for_upsert(
            {
                "name": coach_name,
                "country": rel.get("country"),
                "federation": federation,
                "national_team_role": "Coach",
                "weapons": None,
                "metadata": {"source": "relationship_statement"},
            }
        )
        coach_rows.setdefault((placeholder["name"], placeholder.get("country"), placeholder.get("federation"), placeholder.get("national_team_role")), placeholder)

    coach_values = list(coach_rows.values())
    coaches_written = 0
    for i in range(0, len(coach_values), BATCH_SIZE):
        batch = coach_values[i:i + BATCH_SIZE]
        client.table("fs_coaches").upsert(batch, on_conflict="id").execute()
        coaches_written += len(batch)

    coach_by_name = {}
    for row in coach_values:
        coach_by_name.setdefault((row["name"], row.get("country"), row.get("federation")), row["id"])

    relationship_rows = []
    skipped = 0
    for rel in relationships:
        coach_name = clean_text(rel.get("coach_name"))
        fencer_name = clean_text(rel.get("fencer_name"))
        country = clean_text(rel.get("country"))
        federation = clean_text((rel.get("metadata") or {}).get("federation"))
        if not coach_name or not fencer_name:
            skipped += 1
            continue
        coach_id = coach_by_name.get((coach_name, country, federation))
        fencer_id = match_fencer(client, fencer_name, country)
        if not coach_id or not fencer_id:
            skipped += 1
            continue
        relationship_rows.append(
            {
                "fencer_id": fencer_id,
                "coach_id": coach_id,
                "current": True,
                "metadata": rel.get("metadata") or {},
            }
        )

    relationships_written = 0
    for i in range(0, len(relationship_rows), BATCH_SIZE):
        batch = relationship_rows[i:i + BATCH_SIZE]
        client.table("fs_fencer_coach_relationship").upsert(batch, on_conflict="fencer_id,coach_id").execute()
        relationships_written += len(batch)

    return {
        "coaches_written": coaches_written,
        "relationships_written": relationships_written,
        "relationships_skipped": skipped,
    }


def scrape_coaches() -> dict[str, int]:
    session = requests.Session()
    all_coaches: list[dict] = []
    all_relationships: list[dict] = []
    failed = 0

    for source in load_federation_sources():
        country = source.get("country")
        federation = source.get("federation")
        pages = fetch_source_pages(source, session=session)
        if not pages:
            failed += 1
            continue
        for url, html in pages:
            coaches = parse_coaches_html(html, country=country, federation=federation, source_url=url)
            relationships = parse_fencer_coach_relationships(html, country=country, federation=federation)
            all_coaches.extend(coaches)
            all_relationships.extend(relationships)

    result = upsert_coaches_and_relationships(all_coaches, all_relationships)
    result["sources_failed"] = failed
    result["coaches_parsed"] = len(all_coaches)
    result["relationships_parsed"] = len(all_relationships)
    return result


def main() -> None:
    if not get_supabase():
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_coaches").start()
    try:
        print(f"National team coach scraper starting — {datetime.now(timezone.utc).isoformat()}")
        result = scrape_coaches()
        set_state(
            SOURCE,
            "last_run",
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                **result,
            },
        )
        run_log.complete(
            written=result.get("coaches_written", 0) + result.get("relationships_written", 0),
            failed=result.get("sources_failed", 0),
            skipped=result.get("relationships_skipped", 0),
            metadata=result,
        )
        print(f"Done — {result}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
