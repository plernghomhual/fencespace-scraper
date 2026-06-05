"""
BUCS UK university fencing results scraper.

Probe summary (verified 2026-06-02):
  BUCS sport page: current and prior league fixtures/results require BUCS Play
    registration/login; keep those as explicit skipped stubs.
  BUCS 2025-26 individuals page: public page links to Fencing Time Live schedule
    E7C0C362F7884325A3D5437B81CBF8E3. FTL schedule exposes event names, dates,
    statuses, and event result links, but notes account requirements for results
    after 2026-04-14.
  BUCS regional event pages can expose winner tables with Weapon, Student,
    Institution columns.
  BUCS Big Wednesday 2025 PDF is public and exposes team match result rows such
    as "Fencing Men Trophy Nottingham 2 128 - 118 Exeter".

Local read-only network probing from this sandbox hit DNS restrictions; the
escalated probe was blocked by the approval usage limit. The parser fixtures use
the public web-probed structures above and deterministic blocked-path handling.
"""
from __future__ import annotations

from typing import Any
import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "bucs"
REQUEST_DELAY = float(os.environ.get("BUCS_REQUEST_DELAY", "1.0"))

BUCS_FENCING_URL = "https://www.bucs.org.uk/sports-page/fencing.html"
BUCS_INDIVIDUALS_2025_26_URL = (
    "https://www.bucs.org.uk/events-page/"
    "fencing-individual-championships-2025-26-part-of-bucs-nationals-1.html"
)
FTL_2025_26_SCHEDULE_URL = (
    "https://www.fencingtimelive.com/tournaments/eventSchedule/"
    "E7C0C362F7884325A3D5437B81CBF8E3"
)
BIG_WEDNESDAY_2025_PDF_URL = (
    "https://www.bucs.org.uk/static/82f4656f-0a53-4491-8a596b7c12e68e48/"
    "BBW-2025-Results-Final.pdf"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

WEAPON_ALIASES = [
    (re.compile(r"\bepee\b|\bep[eé]e\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]

UNIVERSITY_ALIASES = {
    "anglia ruskin": "Anglia Ruskin University",
    "bath": "University of Bath",
    "birmingham": "University of Birmingham",
    "bournemouth": "Bournemouth University",
    "bradford": "University of Bradford",
    "brunel": "Brunel University London",
    "durham": "Durham University",
    "edinburgh": "University of Edinburgh",
    "east london": "University of East London",
    "essex": "University of Essex",
    "exeter": "University of Exeter",
    "glasgow": "University of Glasgow",
    "hartpury": "Hartpury University",
    "imperial": "Imperial College London",
    "lancaster": "Lancaster University",
    "leeds beckett": "Leeds Beckett University",
    "liverpool john moores": "Liverpool John Moores University",
    "loughborough": "Loughborough University",
    "manchester": "University of Manchester",
    "manchester met": "Manchester Metropolitan University",
    "newcastle": "Newcastle University",
    "northumbria": "Northumbria University",
    "nottingham": "University of Nottingham",
    "nottingham trent": "Nottingham Trent University",
    "oxford": "University of Oxford",
    "salford": "University of Salford",
    "sgs": "South Gloucestershire and Stroud College",
    "sheffield hallam": "Sheffield Hallam University",
    "st andrews": "University of St Andrews",
    "st andrew's": "University of St Andrews",
    "stirling": "University of Stirling",
    "strathclyde": "University of Strathclyde",
    "surrey": "University of Surrey",
    "uwe": "University of the West of England",
    "warwick": "University of Warwick",
}


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_accents(value):
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(char) != "Mn"
    )


def normalize_key(value):
    text = strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", normalize_key(value)).strip("-")


def title_name(value):
    text = clean_text(value)
    if not text:
        return None
    return " ".join(part[:1].upper() + part[1:] if part.islower() else part for part in text.split())


def rank_to_int(value):
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def medal_for_rank(rank):
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def normalize_season(value):
    text = clean_text(value)
    match = re.search(r"\b(20\d{2})\s*[-/]\s*(\d{2,4})\b", text)
    if match:
        start = int(match.group(1))
        end_raw = match.group(2)
        end = int(end_raw) if len(end_raw) == 4 else (start // 100) * 100 + int(end_raw)
        if end < start:
            end += 100
        return f"{start}-{end}"

    match = re.search(r"\b(\d{2})\s*[-/]\s*(\d{2})\b", text)
    if match:
        start = 2000 + int(match.group(1))
        end = 2000 + int(match.group(2))
        if end < start:
            end += 100
        return f"{start}-{end}"
    return None


def season_ending_in(year):
    year = int(year)
    return f"{year - 1}-{year}"


def split_team_suffix(value):
    text = clean_text(value)
    match = re.match(r"^(?P<base>.+?)\s+(?P<number>\d+)$", text)
    if not match:
        return text, None
    return clean_text(match.group("base")), int(match.group("number"))


def normalize_university_name(value):
    base, _team_number = split_team_suffix(value)
    key = normalize_key(base).replace("'", "")
    if key in UNIVERSITY_ALIASES:
        return UNIVERSITY_ALIASES[key]
    if re.search(r"\buniversity\b|\bcollege\b", base, re.I):
        return clean_text(base)
    return f"University of {clean_text(base)}" if clean_text(base) else None


def table_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    return rows


def header_key(value):
    return normalize_key(value).replace("'", "")


def _weapon_from_label(label):
    text = strip_accents(label or "")
    for pattern, weapon in WEAPON_ALIASES:
        if pattern.search(text):
            return weapon
    return None


def _gender_from_label(label):
    text = normalize_key(label)
    if re.search(r"\bwomen\b|\bwoman\b|female", text):
        return "Women"
    if re.search(r"\bmen\b|\bman\b|male", text):
        return "Men"
    if "mixed" in text or "open" in text:
        return "Mixed"
    return None


def _category_from_label(label):
    text = normalize_key(label)
    for category in ("Beginner", "Novice", "Senior", "Open", "Plate", "Trophy", "Champ", "Championship"):
        if normalize_key(category) in text:
            return category
    return None


def _event_code(gender, weapon, category, team):
    kind = "team" if team else "individual"
    parts = []
    if category == "Senior":
        parts.append("senior")
    if gender:
        parts.append(gender.lower())
    if weapon and weapon != "Mixed":
        parts.append(weapon.lower())
    if category and category != "Senior":
        parts.append(category.lower())
    parts.append(kind)
    return "-".join(slugify(part) for part in parts if part)


def classify_event_label(label, team=False, default_weapon=None):
    weapon = _weapon_from_label(label) or default_weapon
    gender = _gender_from_label(label)
    category = _category_from_label(label)
    if team and not weapon:
        weapon = "Mixed"
    return {
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "team": team,
        "event_code": _event_code(gender, weapon, category, team),
    }


def _result_row(rank, name, university, source_url, team=False, fie_id=None, country="GBR", **metadata):
    raw_university = clean_text(university)
    row = {
        "placement": rank,
        "rank": rank,
        "name": clean_text(name),
        "university": normalize_university_name(raw_university),
        "raw_university": raw_university,
        "team": team,
        "source_url": source_url,
    }
    if team:
        _base, team_number = split_team_suffix(raw_university)
        row["team_number"] = team_number
    else:
        row["fie_id"] = clean_text(fie_id) or None
        row["country"] = country
    row.update(metadata)
    return row


def _event_source_id(season, event_code, source_url):
    parsed = urlparse(source_url or "")
    path_slug = slugify(parsed.path.rsplit("/", 1)[-1].replace(".html", "")) or "source"
    return f"bucs:{season}:{path_slug}:{event_code}"


def _add_bucs_individual_result(events_by_code, season, title, source_url, event_label, student, institution):
    classification = classify_event_label(event_label, team=False)
    if not classification["weapon"] or not classification["gender"]:
        return
    event_code = classification["event_code"]
    event = events_by_code.setdefault(
        event_code,
        {
            "source_id": _event_source_id(season, event_code, source_url),
            "season": season,
            "tournament_name": title or "BUCS Fencing",
            "event_name": f"{title} - {event_label}" if title else event_label,
            "event_code": event_code,
            "weapon": classification["weapon"],
            "gender": classification["gender"],
            "category": classification["category"],
            "team": False,
            "source_url": source_url,
            "source_kind": "bucs_event_html_winner_table",
            "results": [],
        },
    )
    rank = len(event["results"]) + 1
    event["results"].append(_result_row(rank, student, institution, source_url, team=False))


def _parse_flattened_bucs_result_lines(soup):
    lines = [clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    for index in range(0, max(0, len(lines) - 2)):
        header = [header_key(line) for line in lines[index : index + 3]]
        if header == ["weapon", "student", "institution"]:
            rows = []
            cursor = index + 3
            stop_pattern = re.compile(r"^(return to events|bucs partners|share this|rules and regulations)$", re.I)
            while cursor + 2 < len(lines):
                if stop_pattern.search(lines[cursor]):
                    break
                rows.append(lines[cursor : cursor + 3])
                cursor += 3
            return rows
    return []


def parse_bucs_event_results_page(html, source_url):
    """Parse public BUCS event pages with Weapon/Student/Institution winner tables."""
    soup = BeautifulSoup(html or "", "html.parser")
    heading = soup.find("h1") or soup.title
    title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    season = normalize_season(title) or normalize_season(source_url)
    events_by_code: dict[Any, Any] = {}

    for table in soup.find_all("table"):
        rows = table_rows(table)
        if len(rows) < 2:
            continue
        headers = [header_key(cell) for cell in rows[0]]
        if not {"weapon", "student", "institution"}.issubset(set(headers)):
            continue
        weapon_col = headers.index("weapon")
        student_col = headers.index("student")
        institution_col = headers.index("institution")
        for row in rows[1:]:
            if len(row) <= max(weapon_col, student_col, institution_col):
                continue
            event_label = clean_text(row[weapon_col])
            student = title_name(row[student_col])
            institution = clean_text(row[institution_col])
            if not event_label or not student or not institution:
                continue
            _add_bucs_individual_result(events_by_code, season, title, source_url, event_label, student, institution)

    if not events_by_code:
        for event_label, student, institution in _parse_flattened_bucs_result_lines(soup):
            if event_label and student and institution:
                _add_bucs_individual_result(
                    events_by_code,
                    season,
                    title,
                    source_url,
                    event_label,
                    title_name(student),
                    institution,
                )
    return list(events_by_code.values())


def _find_ranked_table(soup):
    for table in soup.find_all("table"):
        rows = table_rows(table)
        if len(rows) < 2:
            continue
        headers = [header_key(cell) for cell in rows[0]]
        has_rank = any(label in {"place", "placement", "rank", "pos", "position"} for label in headers)
        has_name = any(label in {"name", "fencer", "student", "competitor"} for label in headers)
        if has_rank and has_name:
            return rows
    return []


def _column(headers, candidates):
    for candidate in candidates:
        if candidate in headers:
            return headers.index(candidate)
    for idx, header in enumerate(headers):
        if any(candidate in header for candidate in candidates):
            return idx
    return None


def parse_fencingtimelive_results_page(html, source_url, season, tournament_name):
    """Parse a public Fencing Time Live individual final standings table."""
    soup = BeautifulSoup(html or "", "html.parser")
    heading = soup.find("h1") or soup.find("h2") or soup.title
    event_name = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    classification = classify_event_label(event_name, team=False)
    rows = _find_ranked_table(soup)
    if not event_name or not rows or not classification["weapon"] or not classification["gender"]:
        return None

    headers = [header_key(cell) for cell in rows[0]]
    rank_col = _column(headers, ["place", "placement", "rank", "pos", "position"])
    name_col = _column(headers, ["name", "fencer", "student", "competitor"])
    university_col = _column(headers, ["club", "school", "university", "institution", "affiliation", "team"])
    fie_col = _column(headers, ["fie id", "fieid", "fie"])
    if rank_col is None or name_col is None or university_col is None:
        return None

    result_rows = []
    for row in rows[1:]:
        if len(row) <= max(rank_col, name_col, university_col):
            continue
        rank = rank_to_int(row[rank_col])
        name = title_name(row[name_col])
        university = clean_text(row[university_col])
        if rank is None or not name or not university:
            continue
        fie_id = row[fie_col] if fie_col is not None and len(row) > fie_col else None
        result_rows.append(_result_row(rank, name, university, source_url, team=False, fie_id=fie_id))
    if not result_rows:
        return None

    event_code = classification["event_code"]
    return {
        "source_id": f"bucs:{season}:{event_code}",
        "season": season,
        "tournament_name": tournament_name,
        "event_name": event_name,
        "event_code": event_code,
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "team": False,
        "source_url": source_url,
        "source_kind": "fencingtimelive_html",
        "results": result_rows,
    }


def _parse_bucs_team_match(line, source_url, season):
    match = re.match(
        r"^Fencing\s+(?P<gender>Men|Women|Mixed|Open)\s+"
        r"(?P<level>Trophy|Champ|Championship|Vase)\s+"
        r"(?P<home>.+?)\s+(?P<home_score>\d+)\s*-\s*"
        r"(?P<away_score>\d+)\s+(?P<away>.+?)\s*$",
        clean_text(line),
        re.I,
    )
    if not match:
        return None
    gender = match.group("gender").title()
    level = "Champ" if match.group("level").lower().startswith("champ") else match.group("level").title()
    home_score = int(match.group("home_score"))
    away_score = int(match.group("away_score"))
    home = clean_text(match.group("home"))
    away = clean_text(match.group("away"))
    event_label = f"{gender} {level}"
    classification = classify_event_label(event_label, team=True, default_weapon="Mixed")
    event_code = classification["event_code"]

    home_rank, away_rank = (1, 2) if home_score >= away_score else (2, 1)
    return {
        "source_id": f"bucs:{season}:big-wednesday-2025:{event_code}",
        "season": season,
        "tournament_name": "BUCS Big Wednesday 2025",
        "event_name": f"BUCS Big Wednesday 2025 - {gender} {level} Fencing Final",
        "event_code": event_code,
        "weapon": "Mixed",
        "gender": gender,
        "category": level,
        "team": True,
        "source_url": source_url,
        "source_kind": "bucs_big_wednesday_pdf",
        "results": [
            _result_row(
                home_rank,
                home,
                home,
                source_url,
                team=True,
                score_for=home_score,
                score_against=away_score,
            ),
            _result_row(
                away_rank,
                away,
                away,
                source_url,
                team=True,
                score_for=away_score,
                score_against=home_score,
            ),
        ],
    }


def parse_big_wednesday_pdf_text(text, source_url):
    year_match = re.search(r"BUCS\s+BIG\s+WEDNESDAY\s+((?:19|20)\d{2})", text or "", re.I)
    year = int(year_match.group(1)) if year_match else datetime.now(timezone.utc).year
    season = season_ending_in(year)
    events = []
    for raw_line in (text or "").splitlines():
        event = _parse_bucs_team_match(raw_line, source_url, season)
        if event:
            events.append(event)
    return events


def blocked_public_results_stub(html, source_url):
    text = clean_text(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))
    key = normalize_key(text)
    if "bucs play" in key and "fixtures and results" in key and ("register" in key or "login" in key):
        return {
            "source_url": source_url,
            "status": "blocked",
            "reason": "BUCS Play registration/login required for fixtures and results",
            "skipped": True,
        }
    return None


def parse_fencingtimelive_schedule(html, base_url, season, tournament_name):
    soup = BeautifulSoup(html or "", "html.parser")
    events = []
    for link in soup.find_all("a", href=True):
        label = clean_text(link.get_text(" ", strip=True))
        href = link.get("href")
        if not label or not href or "/events/" not in href:
            continue
        classification = classify_event_label(label, team=False)
        if not classification["weapon"] or not classification["gender"]:
            continue
        events.append(
            {
                "event_name": label,
                "event_code": classification["event_code"],
                "season": season,
                "tournament_name": tournament_name,
                "source_url": urljoin(base_url, href),
            }
        )
    return events


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                return response
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep((2 ** attempt) * (5 if response.status_code == 429 else 1))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_pdf_text(url):
    response = _get(url)
    if not response:
        return None
    import pdfplumber

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)


def discover_events():
    """Discover public BUCS individual and team result events."""
    events = []
    skipped_stubs = []

    response = _get(BUCS_FENCING_URL, retries=1)
    if response:
        stub = blocked_public_results_stub(response.text, BUCS_FENCING_URL)
        if stub:
            skipped_stubs.append(stub)
            print(f"  Skipping login-only BUCS Play results: {BUCS_FENCING_URL}")
        time.sleep(REQUEST_DELAY)

    response = _get(BUCS_INDIVIDUALS_2025_26_URL, retries=1)
    if response:
        events.extend(parse_bucs_event_results_page(response.text, BUCS_INDIVIDUALS_2025_26_URL))
        time.sleep(REQUEST_DELAY)

    response = _get(FTL_2025_26_SCHEDULE_URL, retries=1)
    if response:
        schedule = parse_fencingtimelive_schedule(
            response.text,
            FTL_2025_26_SCHEDULE_URL,
            "2025-2026",
            "BUCS Fencing: Individual Championships 2025-26",
        )
        for item in schedule:
            result_response = _get(item["source_url"], retries=1)
            if result_response:
                event = parse_fencingtimelive_results_page(
                    result_response.text,
                    item["source_url"],
                    season=item["season"],
                    tournament_name=item["tournament_name"],
                )
                if event:
                    events.append(event)
                else:
                    print(f"  No public result table found for {item['source_url']}")
            time.sleep(REQUEST_DELAY)

    pdf_text = fetch_pdf_text(BIG_WEDNESDAY_2025_PDF_URL)
    if pdf_text:
        events.extend(parse_big_wednesday_pdf_text(pdf_text, BIG_WEDNESDAY_2025_PDF_URL))

    return events, skipped_stubs


def _match_fencer(fie_id=None, name=None, country=None):
    if not supabase:
        return None, None
    if fie_id:
        try:
            rows = (
                supabase.table("fs_fencers")
                .select("id,fie_id")
                .eq("fie_id", str(fie_id))
                .limit(2)
                .execute()
                .data
            )
            if rows:
                return rows[0].get("id"), "fie_id"
        except Exception as exc:
            print(f"  FIE ID match failed for {fie_id}: {exc}")

    if name and country:
        try:
            rows = (
                supabase.table("fs_fencer_identities")
                .select("fs_fencer_row_ids,fie_ids")
                .ilike("canonical_name", name)
                .eq("country", country)
                .limit(2)
                .execute()
                .data
            )
            if len(rows or []) == 1 and rows[0].get("fs_fencer_row_ids"):
                return rows[0]["fs_fencer_row_ids"][0], "canonical_identity_name_country"
        except Exception as exc:
            print(f"  Identity match failed for {name}/{country}: {exc}")

        try:
            rows = (
                supabase.table("fs_fencers")
                .select("id,fie_id")
                .ilike("name", name)
                .eq("country", country)
                .limit(2)
                .execute()
                .data
            )
            if len(rows or []) == 1:
                return rows[0].get("id"), "name_country"
        except Exception as exc:
            print(f"  Name/country match failed for {name}/{country}: {exc}")
    return None, None


def tournament_row(event):
    return {
        "source_id": event["source_id"],
        "name": f"{event['tournament_name']} - {event['event_name']}",
        "season": event["season"],
        "type": "bucs_university",
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("category") or "Senior",
        "country": "GBR",
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_kind": event.get("source_kind"),
            "event_code": event.get("event_code"),
            "team": event.get("team"),
            "tournament_name": event.get("tournament_name"),
        },
    }


def upsert_tournament(event):
    try:
        result = supabase.table("fs_tournaments").upsert(tournament_row(event), on_conflict="source_id").execute()  # type: ignore[union-attr]
        if result.data:
            return result.data[0].get("id")
        rows = (
            supabase.table("fs_tournaments")  # type: ignore[union-attr]
            .select("id")
            .eq("source_id", event["source_id"])
            .limit(1)
            .execute()
            .data
        )
        return rows[0]["id"] if rows else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def result_row_for_db(tournament_id, event, result, fencer_id, match_method):
    team = bool(result.get("team"))
    metadata = {
        "source": SOURCE,
        "source_id": event["source_id"],
        "source_url": result.get("source_url") or event.get("source_url"),
        "team": team,
        "university": result.get("university"),
        "raw_university": result.get("raw_university"),
        "match_method": match_method,
    }
    if team:
        metadata.update(
            {
                "team_number": result.get("team_number"),
                "score_for": result.get("score_for"),
                "score_against": result.get("score_against"),
            }
        )
    else:
        metadata["fie_id"] = result.get("fie_id")

    row = {
        "tournament_id": tournament_id,
        "name": result.get("name"),
        "nationality": result.get("country") if not team else "GBR",
        "rank": result.get("rank"),
        "placement": result.get("placement"),
        "medal": medal_for_rank(result.get("rank")),
        "fencer_id": fencer_id,
        "metadata": metadata,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("fie_id"):
        row["fie_fencer_id"] = str(result["fie_id"])
    return row


def upsert_results(tournament_id, event):
    """Delete and reinsert BUCS results, skipping unmatched individual fencers."""
    db_rows = []
    skipped = failed = 0
    for result in event.get("results", []):
        if result.get("rank") is None or not result.get("name"):
            skipped += 1
            continue
        if result.get("team"):
            print(f"  university-only team row: {result.get('name')} ({result.get('university')})")
            db_rows.append(result_row_for_db(tournament_id, event, result, None, "team_university_row"))
            continue

        fencer_id, match_method = _match_fencer(result.get("fie_id"), result.get("name"), result.get("country"))
        if not fencer_id:
            print(
                "  unmatched fencer: "
                f"{result.get('name')} / {result.get('country')} / {result.get('university')}"
            )
            skipped += 1
            continue
        db_rows.append(result_row_for_db(tournament_id, event, result, fencer_id, match_method))

    if not db_rows:
        return {"written": 0, "skipped": skipped, "failed": failed}

    try:
        supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    except Exception as exc:
        print(f"  Results delete failed for {event['source_id']}: {exc}")
        return {"written": 0, "skipped": skipped, "failed": 1}

    written = 0
    for index in range(0, len(db_rows), 100):
        batch = db_rows[index : index + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed for {event['source_id']}: {exc}")
            failed += len(batch)
    return {"written": written, "skipped": skipped, "failed": failed}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_bucs").start()
    try:
        print(f"BUCS scraper starting - {datetime.now(timezone.utc).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        events, blocked_stubs = discover_events()
        print(f"  {len(events)} public events found; {len(blocked_stubs)} blocked sources")

        written = failed = len(blocked_stubs)
        skipped = len(blocked_stubs)
        for event in events:
            if event["source_id"] in done_source_ids:
                skipped += 1
                continue
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue
            counts = upsert_results(tournament_id, event)
            written += counts["written"]
            skipped += counts["skipped"]
            failed += counts["failed"]
            if counts["written"] > 0:
                done_source_ids.add(event["source_id"])
                set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            time.sleep(REQUEST_DELAY)

        set_state(
            SOURCE,
            "last_run",
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "events": len(events),
                "blocked_sources": blocked_stubs,
            },
        )
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
