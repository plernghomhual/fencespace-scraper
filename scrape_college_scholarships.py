import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_college_scholarships"
TOP_50_LIMIT = 50
REQUEST_DELAY = 0.35
REQUEST_TIMEOUT = 20
UPSERT_BATCH_SIZE = 100

SCHOLARSHIPSTATS_URL = "https://scholarshipstats.com/fencing"
COLLEGE_SCHOLARSHIPS_URL = (
    "https://www.collegescholarships.org/scholarships/sports/fencing.htm"
)
SCHOLARSHIP_DIRECTORY_URLS = [SCHOLARSHIPSTATS_URL, COLLEGE_SCHOLARSHIPS_URL]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
ROSTER_PROFILE_RE = re.compile(r"/roster/[^/?#]+(?:/\d+)?(?:$|[?#])")
WEAPON_PATTERNS = [
    ("Epee", re.compile(r"\b(?:epee|epée)\b", re.IGNORECASE)),
    ("Foil", re.compile(r"\bfoil\b", re.IGNORECASE)),
    ("Sabre", re.compile(r"\b(?:sabre|saber)\b", re.IGNORECASE)),
]


@dataclass
class CollegeProgramSeed:
    college_name: str
    division: str | None = None
    conference: str | None = None
    gender_teams: list[str] = field(default_factory=list)
    website: str | None = None
    scholarship_slots: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_url(value: Any, base_url: str | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if base_url:
        text = urljoin(base_url, text)
    if text.startswith("//"):
        text = f"https:{text}"
    if "://" not in text:
        text = f"https://{text}"

    parsed = urlparse(text)
    if not parsed.netloc:
        return None
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    path = parsed.path or "/"
    return urlunparse((scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def cell_texts(row) -> list[str]:
    return [clean_text(cell.get_text(" ", strip=True)) or "" for cell in row.find_all(["th", "td"])]


def parse_limit_value(value: str | None) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    if text in {"-", "—", "N/A"}:
        return 0.0
    try:
        return float(text.replace(",", "").replace("$", ""))
    except ValueError:
        return None


def parse_scholarship_limits(soup: BeautifulSoup) -> dict[str, dict[str, float]]:
    limits: dict[str, dict[str, float]] = {}
    for row in soup.find_all("tr"):
        cells = cell_texts(row)
        if not cells:
            continue
        division = cells[0]
        if not division.startswith("NCAA"):
            continue
        men_limit = parse_limit_value(cells[11] if len(cells) > 11 else None)
        women_limit = parse_limit_value(cells[12] if len(cells) > 12 else None)
        limits[division] = {
            "Men": men_limit if men_limit is not None else 0.0,
            "Women": women_limit if women_limit is not None else 0.0,
        }
    return limits


def team_labels(cells: list[str]) -> list[str]:
    labels = {cell.upper() for cell in cells}
    teams = []
    if "M" in labels:
        teams.append("Men")
    if "W" in labels:
        teams.append("Women")
    return teams


def scholarship_slots_for(
    division: str | None,
    gender_teams: list[str],
    limits: dict[str, dict[str, float]],
) -> tuple[int | None, float | None]:
    if not division or not gender_teams:
        return None, None
    division_limits = limits.get(division)
    if not division_limits:
        if division == "NCAA III":
            return 0, 0.0
        return None, None
    exact = sum(division_limits.get(team, 0.0) for team in gender_teams)
    return int(math.ceil(exact)), exact


def parse_scholarshipstats_programs(
    html: str,
    limit: int = TOP_50_LIMIT,
    source_url: str = SCHOLARSHIPSTATS_URL,
) -> list[CollegeProgramSeed]:
    soup = BeautifulSoup(html, "html.parser")
    scholarship_limits = parse_scholarship_limits(soup)
    programs = []

    for table in soup.find_all("table"):
        header = clean_text(table.get_text(" ", strip=True)) or ""
        if "varsity Fencing teams" not in header and "varsity fencing teams" not in header:
            continue

        for row in table.find_all("tr"):
            cells = cell_texts(row)
            if not cells:
                continue
            link = row.find("a", href=True)
            if not link:
                continue
            name = clean_text(link.get_text(" ", strip=True))
            division = next((cell for cell in cells if cell.startswith("NCAA") or cell == "NAIA"), None)
            if not name or not division or not division.startswith("NCAA"):
                continue

            gender_teams = team_labels(cells)
            scholarship_slots, exact_slots = scholarship_slots_for(
                division, gender_teams, scholarship_limits
            )
            programs.append(
                CollegeProgramSeed(
                    college_name=name,
                    division=division,
                    conference=None,
                    gender_teams=gender_teams,
                    website=normalize_url(link.get("href")),
                    scholarship_slots=scholarship_slots,
                    metadata={
                        "directory_source": source_url,
                        "directory_name": "ScholarshipStats",
                        "source_rank": len(programs) + 1,
                        "city": cells[1] or None if len(cells) > 1 else None,
                        "state": cells[2] or None if len(cells) > 2 else None,
                        "scholarship_slots_exact": exact_slots,
                    },
                )
            )
            if len(programs) >= limit:
                return programs
    return programs[:limit]


def extract_roster_profile_links(html: str | None) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href") or ""
        href_lower = href.lower()
        text = clean_text(anchor.get_text(" ", strip=True)) or ""
        if "/coaches/" in href_lower or "coach" in href_lower:
            continue
        if not ROSTER_PROFILE_RE.search(href_lower):
            continue
        if text.casefold().startswith("full bio for"):
            continue
        links.append(href_lower.split("#", 1)[0])
    return dedupe(links)


def extract_roster_size(html: str | None) -> int | None:
    links = extract_roster_profile_links(html)
    return len(links) if links else None


def extract_weapons(html: str | None) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return [weapon for weapon, pattern in WEAPON_PATTERNS if pattern.search(text)]


def visible_lines(html: str | None) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return [
        line
        for line in (clean_text(part) for part in soup.get_text("\n").split("\n"))
        if line
    ]


def is_head_coach_title(line: str, allow_associate: bool = False) -> bool:
    lowered = line.casefold()
    if "head" not in lowered or "coach" not in lowered:
        return False
    if not allow_associate and "associate" in lowered:
        return False
    return True


def name_before_title(line: str) -> str | None:
    lowered = line.casefold()
    head_index = lowered.find("head")
    if head_index <= 0:
        return None
    return normalize_person_name(line[:head_index])


def normalize_person_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.casefold()
    labels = {
        "name",
        "title",
        "phone",
        "email",
        "email address",
        "location",
        "staff",
        "support staff",
        "coaching staff",
        "footer",
    }
    if lowered in labels or "@" in text:
        return None
    if "hide/show" in lowered or "additional information" in lowered or "full bio" in lowered:
        return None
    if "family" in lowered:
        return None
    if re.fullmatch(r"[\d\s().+-]+", text):
        return None
    if "coach" in lowered or "roster" in lowered or "fencing" in lowered:
        return None
    if not re.search(r"[A-Za-z]", text):
        return None
    if len(text.split()) < 2:
        return None
    return text


def find_nearby_email(lines: list[str], index: int) -> str | None:
    for offset in range(0, 6):
        for candidate_index in (index + offset, index - offset):
            if candidate_index < 0 or candidate_index >= len(lines):
                continue
            match = EMAIL_RE.search(lines[candidate_index])
            if match:
                return match.group(0)
    return None


def find_previous_name(lines: list[str], index: int) -> str | None:
    for candidate in reversed(lines[max(0, index - 5) : index]):
        name = normalize_person_name(candidate)
        if name:
            return name
    return None


def extract_head_coach(html: str | None) -> dict[str, str | None]:
    lines = visible_lines(html)
    for allow_associate in (False, True):
        for index, line in enumerate(lines):
            if not is_head_coach_title(line, allow_associate=allow_associate):
                continue
            name = name_before_title(line) or find_previous_name(lines, index)
            email = EMAIL_RE.search(line)
            return {
                "head_coach": name,
                "coach_email": email.group(0) if email else find_nearby_email(lines, index),
            }
    return {"head_coach": None, "coach_email": None}


def base_site_url(value: str | None) -> str | None:
    normalized = normalize_url(value)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def candidate_urls(base_url: str | None, gender_teams: list[str]) -> list[str]:
    root = base_site_url(base_url)
    if not root:
        return []
    if gender_teams == ["Men"]:
        slugs = ["mens-fencing", "fencing"]
    elif gender_teams == ["Women"]:
        slugs = ["womens-fencing", "fencing"]
    else:
        slugs = ["fencing", "mens-fencing", "womens-fencing"]

    candidates = [normalize_url(base_url)]
    for slug in slugs:
        candidates.extend(
            [
                urljoin(root, f"/sports/{slug}/roster"),
                urljoin(root, f"/sports/{slug}/coaches"),
                urljoin(root, f"/sports/{slug}"),
            ]
        )
    candidates.extend(
        [
            urljoin(root, "/roster.aspx?path=fencing"),
            urljoin(root, "/coaches.aspx?path=fencing"),
            urljoin(root, "/staff-directory"),
        ]
    )
    return dedupe([url for url in (normalize_url(url) for url in candidates) if url])


def fetch_html(session: requests.Session, url: str) -> tuple[str | None, str | None, int | None]:
    try:
        response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None, None, None
    if response.status_code >= 400:
        return None, response.url, response.status_code
    html = response.text or ""
    if "fenc" not in html.casefold() and "coach" not in html.casefold():
        return None, response.url, response.status_code
    return html, response.url, response.status_code


def final_url_is_fencing_page(url: str | None) -> bool:
    if not url:
        return True
    path = urlparse(url).path.casefold()
    return not ("/sports/" in path and "fenc" not in path)


def discover_program_pages(
    session: requests.Session,
    seed: CollegeProgramSeed,
    delay: float = REQUEST_DELAY,
) -> dict[str, Any]:
    pages: dict[str, Any] = {
        "roster_html": None,
        "coach_html": None,
        "roster_url": None,
        "coach_url": None,
        "attempted_urls": [],
    }
    for url in candidate_urls(seed.website, seed.gender_teams):
        html, final_url, status = fetch_html(session, url)
        pages["attempted_urls"].append({"url": url, "status": status, "final_url": final_url})
        if not final_url_is_fencing_page(final_url):
            continue
        lowered_url = url.casefold()
        is_coach_candidate = "coach" in lowered_url or "staff" in lowered_url
        if html:
            if pages["roster_html"] is None and extract_roster_size(html):
                pages["roster_html"] = html
                pages["roster_url"] = final_url or url
            coach = extract_head_coach(html)
            if (
                pages["coach_html"] is None
                and (coach["head_coach"] or coach["coach_email"])
                and (is_coach_candidate or coach["coach_email"])
            ):
                pages["coach_html"] = html
                pages["coach_url"] = final_url or url
        if pages["roster_html"] and pages["coach_html"]:
            break
        time.sleep(delay)
    return pages


def extract_directory_overview(html: str | None, url: str) -> dict[str, Any] | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else None
    text = soup.get_text(" ", strip=True)
    snippets = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lowered = sentence.casefold()
        if "fencing" in lowered and ("scholarship" in lowered or "ncaa" in lowered):
            snippets.append(sentence[:300])
        if len(snippets) >= 3:
            break
    return {"url": url, "title": title, "snippets": snippets}


def fetch_directory_overviews(session: requests.Session) -> list[dict[str, Any]]:
    overviews = []
    for url in SCHOLARSHIP_DIRECTORY_URLS:
        html, final_url, status = fetch_html(session, url)
        overview = extract_directory_overview(html, final_url or url)
        if overview:
            overview["status"] = status
            overviews.append(overview)
    return overviews


def load_program_seeds(
    session: requests.Session,
    limit: int = TOP_50_LIMIT,
) -> list[CollegeProgramSeed]:
    html, final_url, _status = fetch_html(session, SCHOLARSHIPSTATS_URL)
    if not html:
        raise RuntimeError(f"Could not fetch scholarship directory: {SCHOLARSHIPSTATS_URL}")
    programs = parse_scholarshipstats_programs(html, limit=limit, source_url=final_url or SCHOLARSHIPSTATS_URL)
    if not programs:
        raise RuntimeError("No NCAA fencing programs found in ScholarshipStats directory")
    return programs


def build_scholarship_row(
    seed: CollegeProgramSeed,
    roster_html: str | None = None,
    coach_html: str | None = None,
    roster_url: str | None = None,
    coach_url: str | None = None,
    scraped_at: str | None = None,
    directory_overviews: list[dict[str, Any]] | None = None,
    attempted_urls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    roster_size = extract_roster_size(roster_html)
    weapons = extract_weapons(roster_html) or extract_weapons(coach_html)
    weapons_inferred = False
    if not weapons and roster_size is not None:
        weapons = ["Epee", "Foil", "Sabre"]
        weapons_inferred = True

    coach = extract_head_coach(coach_html) if coach_html else {"head_coach": None, "coach_email": None}
    if not coach["head_coach"] and not coach["coach_email"]:
        coach = extract_head_coach(roster_html)

    metadata = dict(seed.metadata)
    metadata.update(
        {
            "source": SOURCE,
            "source_urls": {"roster": roster_url, "coach": coach_url},
            "roster_profile_count": roster_size,
            "weapons_inferred": weapons_inferred,
        }
    )
    if directory_overviews:
        metadata["scholarship_directory_overviews"] = directory_overviews
    if attempted_urls:
        metadata["attempted_urls"] = attempted_urls[:12]

    return {
        "college_name": seed.college_name,
        "division": seed.division,
        "conference": seed.conference,
        "weapons": weapons or None,
        "gender_teams": seed.gender_teams or None,
        "roster_size": roster_size,
        "scholarship_slots": seed.scholarship_slots,
        "head_coach": coach["head_coach"],
        "coach_email": coach["coach_email"],
        "website": seed.website,
        "metadata": metadata,
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
    }


def upsert_scholarship_rows(
    supabase,
    rows: list[dict[str, Any]],
    batch_size: int = UPSERT_BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        supabase.table("fs_college_scholarships").upsert(
            batch, on_conflict="college_name"
        ).execute()
        written += len(batch)
    return written


def scrape_college_scholarships(
    supabase,
    session: requests.Session | None = None,
    limit: int = TOP_50_LIMIT,
) -> dict[str, int]:
    session = session or requests.Session()
    scraped_at = datetime.now(timezone.utc).isoformat()
    programs = load_program_seeds(session, limit=limit)
    directory_overviews = fetch_directory_overviews(session)
    rows = []
    missing_official_data = 0

    for seed in programs:
        pages = discover_program_pages(session, seed)
        if not pages["roster_html"] and not pages["coach_html"]:
            missing_official_data += 1
        rows.append(
            build_scholarship_row(
                seed,
                roster_html=pages["roster_html"],
                coach_html=pages["coach_html"],
                roster_url=pages["roster_url"],
                coach_url=pages["coach_url"],
                scraped_at=scraped_at,
                directory_overviews=directory_overviews,
                attempted_urls=pages["attempted_urls"],
            )
        )

    written = upsert_scholarship_rows(supabase, rows)
    return {
        "programs_loaded": len(programs),
        "rows_written": written,
        "missing_official_data": missing_official_data,
    }


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous college scholarship state: {previous_state}")

        supabase = get_supabase_client()
        summary = scrape_college_scholarships(supabase)
        set_state(
            SOURCE,
            "last_run",
            {
                **summary,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        run_log.complete(
            written=summary["rows_written"],
            failed=0,
            skipped=summary["missing_official_data"],
            metadata=summary,
        )
        print(
            "College scholarship scraper complete: "
            f"{summary['rows_written']} rows written, "
            f"{summary['missing_official_data']} programs missing official page data"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
