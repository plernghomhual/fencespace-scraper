import io
import os
import re
import time
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import pdfplumber
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


SOURCE = "ncaa_regular"
BATCH_SIZE = 100
REQUEST_DELAY = float(os.environ.get("NCAA_REGULAR_REQUEST_DELAY", "1.0"))
MAX_PDF_BYTES = int(os.environ.get("NCAA_REGULAR_MAX_PDF_BYTES", str(25 * 1024 * 1024)))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

SOURCE_PAGES = [
    # These pages were probed. They frequently link to scanned PDFs, so the scraper
    # discovers them but skips image-only or oversized files without failing the run.
    "https://redstormsports.com/news/2026/1/17/fencing-hosts-st-johns-super-cup-on-saturday",
    "https://goduke.com/news/2025/11/9/fencing-duke-men-women-post-two-wins-apiece-at-elite-invitational",
    "https://gopsusports.com/sports/fencing/schedule",
]

@dataclass(frozen=True)
class SourceDocument:
    url: str
    label: str
    year: int | None = None


@dataclass(frozen=True)
class ParsedBout:
    year: int
    source_url: str
    source_page: int
    date: date
    gender: str
    event_name: str
    round_number: int | None
    match_number: int | None
    team_a: str
    team_b: str
    weapon: str
    bout_number: int
    fencer_a_name: str
    fencer_b_name: str
    score_a: int
    score_b: int
    decision_a: str
    decision_b: str

    @property
    def source_key(self) -> str:
        return (
            f"p{self.source_page}:r{self.round_number or 0}:m{self.match_number or 0}:"
            f"{slugify(self.weapon)}:{self.bout_number}:"
            f"{slugify(self.fencer_a_name)}:{slugify(self.fencer_b_name)}"
        )


@dataclass
class ParsedMeet:
    year: int
    source_url: str
    date: date
    gender: str
    team_a: str
    team_b: str
    bouts: list[ParsedBout] = field(default_factory=list)

    @property
    def meet_id(self) -> str:
        return make_meet_id(self.year, self.source_url, self.gender, self.team_a, self.team_b)

    @property
    def source_id(self) -> str:
        return f"ncaa_regular:{self.year}:{self.meet_id}"


def clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def strip_accents(value):
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(ch) != "Mn"
    )


def normalize_key(value):
    text = strip_accents(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fencer_lookup_key(name, country="USA"):
    return f"{normalize_key(name)}|{normalize_key(country)}"


def slugify(value):
    text = normalize_key(value)
    return re.sub(r"\s+", "-", text).strip("-")


def recent_seasons(current_year=None, count=5):
    year = current_year or datetime.now(UTC).year
    seasons: list[Any] = []
    while len(seasons) < count:
        if year != 2020:
            seasons.append(year)
        year -= 1
    return seasons


def parse_source_year(url):
    parsed = urlparse(url)
    matches = re.findall(r"(20\d{2})", parsed.path)
    if not matches:
        return None
    year = int(matches[0])
    return year if year != 2020 else None


def source_slug_for_url(url, year=None):
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    source_year = year or parse_source_year(url)

    if "acc.escrimeresults.com" in host or re.search(r"acc20\d{2}", path):
        return f"acc-{source_year}" if source_year else "acc"
    if "ivy.escrimeresults.com" in host or "/ivy/" in path:
        return f"ivy-{source_year}" if source_year else "ivy"
    if "redstormsports.com" in host:
        return f"st-johns-{source_year}" if source_year else "st-johns"
    if "goduke.com" in host:
        return f"duke-{source_year}" if source_year else "duke"
    if "gopsusports.com" in host:
        return f"penn-state-{source_year}" if source_year else "penn-state"

    host_slug = slugify(host.replace("www.", ""))
    return f"{host_slug}-{source_year}" if source_year else host_slug


def make_meet_id(year, source_url, gender, team_a, team_b):
    return (
        f"{source_slug_for_url(source_url, year)}-"
        f"{slugify(gender)}-{slugify(team_a)}-vs-{slugify(team_b)}"
    )


def normalize_weapon(event_name):
    text = strip_accents(event_name or "").lower()
    if "saber" in text or "sabre" in text:
        return "Sabre"
    if "foil" in text:
        return "Foil"
    if "epee" in text or "epée" in text:
        return "Epee"
    return clean_text(event_name) or "Unknown"


def normalize_gender(event_name):
    text = (event_name or "").lower()
    if "women" in text:
        return "Women"
    if "men" in text:
        return "Men"
    return "Mixed"


def parse_page_date(text):
    match = re.search(
        r"Date:\s*(?:[A-Za-z]+,\s*)?([A-Za-z]+ \d{1,2}, \d{4})",
        text,
    )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def parse_round_match(text):
    match = re.search(r"Round:\s*(\d+)\s+Match:\s*(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_event_name(text):
    match = re.search(r"Event:\s*([^\n\r]+)", text)
    return clean_text(match.group(1)) if match else None


def parse_teams(lines):
    for line in lines:
        if " & " not in line:
            continue
        left, right = line.split(" & ", 1)
        left = clean_text(left)
        right = clean_text(right)
        if left and right and "Referee" not in left and "Referee" not in right:
            return left, right
    return None, None


def parse_score_sheet_page(text, source_url, source_page=1):
    event_name = parse_event_name(text)
    if not event_name:
        return []

    event_date = parse_page_date(text)
    if not event_date:
        return []

    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    team_a, team_b = parse_teams(lines)
    if not team_a or not team_b:
        return []

    round_number, match_number = parse_round_match(text)
    year = event_date.year
    weapon = normalize_weapon(event_name)
    gender = normalize_gender(event_name)

    bouts = []
    bout_number = 0
    pending_decision = None
    bout_re = re.compile(r"^\d+\s+(.+?)\s+T/O\s+(\d+)\s+(\d+)\s+T/O\s+(.+?)\s+\d+$")
    right_forfeit_re = re.compile(r"^\d+\s+(.+?)\s+T/O\s+T/O\s+BOUT FORFEITED\s+\d+$")
    left_forfeit_re = re.compile(r"^\d+\s+BOUT FORFEITED\s+T/O\s+T/O\s+(.+?)\s+\d+$")

    for line in lines:
        if "Substitutions may be made" in line:
            break

        tokens = line.split()
        if "FV" in tokens:
            fv_index = tokens.index("FV")
            d_index = tokens.index("D") if "D" in tokens else None
            pending_decision = ("loss", "win") if d_index is not None and d_index < fv_index else ("win", "loss")
            continue

        vd_tokens = [token for token in line.split() if token in {"V", "D"}]
        if len(vd_tokens) >= 2 and "Video" in line:
            pending_decision = (
                "win" if vd_tokens[-2] == "V" else "loss",
                "win" if vd_tokens[-1] == "V" else "loss",
            )
            continue

        right_forfeit_match = right_forfeit_re.match(line)
        if right_forfeit_match:
            fencer_a = clean_text(right_forfeit_match.group(1))
            if not fencer_a:
                continue
            bout_number += 1
            bouts.append(
                ParsedBout(
                    year=year,
                    source_url=source_url,
                    source_page=source_page,
                    date=event_date,
                    gender=gender,
                    event_name=event_name,
                    round_number=round_number,
                    match_number=match_number,
                    team_a=team_a,
                    team_b=team_b,
                    weapon=weapon,
                    bout_number=bout_number,
                    fencer_a_name=fencer_a,
                    fencer_b_name="BOUT FORFEITED",
                    score_a=5,
                    score_b=0,
                    decision_a="win",
                    decision_b="loss",
                )
            )
            pending_decision = None
            continue

        left_forfeit_match = left_forfeit_re.match(line)
        if left_forfeit_match:
            fencer_b = clean_text(left_forfeit_match.group(1))
            if not fencer_b:
                continue
            bout_number += 1
            bouts.append(
                ParsedBout(
                    year=year,
                    source_url=source_url,
                    source_page=source_page,
                    date=event_date,
                    gender=gender,
                    event_name=event_name,
                    round_number=round_number,
                    match_number=match_number,
                    team_a=team_a,
                    team_b=team_b,
                    weapon=weapon,
                    bout_number=bout_number,
                    fencer_a_name="BOUT FORFEITED",
                    fencer_b_name=fencer_b,
                    score_a=0,
                    score_b=5,
                    decision_a="loss",
                    decision_b="win",
                )
            )
            pending_decision = None
            continue

        match = bout_re.match(line)
        if not match:
            continue

        fencer_a = clean_text(match.group(1))
        score_a = int(match.group(2))
        score_b = int(match.group(3))
        fencer_b = clean_text(match.group(4))
        if not fencer_a or not fencer_b:
            continue

        if score_a > score_b:
            decision_a, decision_b = "win", "loss"
        elif score_b > score_a:
            decision_a, decision_b = "loss", "win"
        elif pending_decision:
            decision_a, decision_b = pending_decision
        else:
            decision_a = decision_b = "unknown"

        bout_number += 1
        bouts.append(
            ParsedBout(
                year=year,
                source_url=source_url,
                source_page=source_page,
                date=event_date,
                gender=gender,
                event_name=event_name,
                round_number=round_number,
                match_number=match_number,
                team_a=team_a,
                team_b=team_b,
                weapon=weapon,
                bout_number=bout_number,
                fencer_a_name=fencer_a,
                fencer_b_name=fencer_b,
                score_a=score_a,
                score_b=score_b,
                decision_a=decision_a,
                decision_b=decision_b,
            )
        )
        pending_decision = None

    return bouts


def parse_score_sheet_texts(page_texts, source_url):
    grouped = {}
    for index, text in enumerate(page_texts, start=1):
        for bout in parse_score_sheet_page(text or "", source_url, source_page=index):
            key = (
                bout.gender,
                normalize_key(bout.team_a),
                normalize_key(bout.team_b),
                bout.round_number,
                bout.match_number,
            )
            if key not in grouped:
                grouped[key] = ParsedMeet(
                    year=bout.year,
                    source_url=source_url,
                    date=bout.date,
                    gender=bout.gender,
                    team_a=bout.team_a,
                    team_b=bout.team_b,
                )
            grouped[key].bouts.append(bout)

    for meet in grouped.values():
        dates = Counter(bout.date for bout in meet.bouts)
        if dates:
            meet.date = sorted(dates.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return sorted(grouped.values(), key=lambda meet: (meet.date, meet.gender, meet.team_a, meet.team_b))


def acc_source_documents(seasons=None):
    docs = []
    for year in seasons or recent_seasons():
        if year == 2020:
            continue
        for gender_code, gender in (("M", "Men"), ("W", "Women")):
            docs.append(
                SourceDocument(
                    url=f"https://acc.escrimeresults.com/{year}/ACC{year}{gender_code}scoresheets.pdf",
                    label=f"ACC {year} {gender} score sheets",
                    year=year,
                )
            )
    return docs


def canonical_document_url(base_url, href):
    url = urljoin(base_url, href)
    if "/documents/" in url and "/documents/download/" not in url:
        url = url.replace("/documents/", "/documents/download/", 1)
    return url


def discover_pdf_links_from_page(page_url):
    response = requests.get(page_url, headers=HEADERS, timeout=25)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    docs = []
    seen = set()
    for link in soup.find_all("a", href=True):
        text = clean_text(link.get_text(" ", strip=True)) or ""
        href = link["href"]
        combined = f"{href} {text}".lower()
        if ".pdf" not in combined:
            continue
        if not any(token in combined for token in ("fenc", "result", "scor", "super", "elite")):
            continue
        url = canonical_document_url(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        docs.append(SourceDocument(url=url, label=text or page_url, year=parse_source_year(url)))
    return docs


def discover_source_documents(seasons=None, include_school_pages=True):
    docs = acc_source_documents(seasons)
    if include_school_pages:
        for page_url in SOURCE_PAGES:
            try:
                docs.extend(discover_pdf_links_from_page(page_url))
            except Exception as exc:
                print(f"  Source page probe failed for {page_url}: {exc}")

    seen = set()
    unique_docs = []
    for doc in docs:
        if doc.url in seen:
            continue
        seen.add(doc.url)
        unique_docs.append(doc)
    return unique_docs


def response_content_length(response):
    try:
        return int(response.headers.get("content-length") or 0)
    except ValueError:
        return 0


def fetch_pdf_text_pages(url, max_bytes=MAX_PDF_BYTES):
    try:
        head = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if head.status_code == 404:
            return [], "not_found"
        size = response_content_length(head)
        if size and size > max_bytes:
            return [], "too_large"
    except Exception:
        pass

    response = requests.get(url, headers=HEADERS, timeout=60)
    if response.status_code == 404:
        return [], "not_found"
    if response.status_code != 200:
        return [], f"http_{response.status_code}"
    if len(response.content) > max_bytes:
        return [], "too_large"
    if not response.content.startswith(b"%PDF"):
        return [], "not_pdf"

    pages = []
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            pages.append(text)

    if not any(clean_text(page) for page in pages):
        return [], "no_text"
    return pages, "ok"


def country_is_usa(row):
    values = [row.get("country"), row.get("nationality")]
    return any(normalize_key(value) in {"usa", "us", "united states", "united states of america"} for value in values)


def load_fencer_index(client):
    rows: list[Any] = []
    offset = 0
    while True:
        query = client.table("fs_fencers").select("id,name,country")
        if hasattr(query, "range"):
            query = query.range(offset, offset + 999)
        page = query.execute().data or []
        rows.extend(page)
        if not hasattr(query, "range") or len(page) < 1000:
            break
        offset += 1000

    fencer_index: dict[Any, Any] = {}
    for row in rows:
        if not row.get("id") or not row.get("name") or not country_is_usa(row):
            continue
        fencer_index.setdefault(fencer_lookup_key(row["name"]), row["id"])
    return fencer_index


def utc_now():
    return datetime.now(UTC).isoformat()


def build_tournament_row(meet):
    return {
        "source_id": meet.source_id,
        "name": f"NCAA Regular Season: {meet.team_a} vs {meet.team_b}",
        "season": str(meet.year),
        "start_date": meet.date.isoformat(),
        "end_date": meet.date.isoformat(),
        "type": "ncaa_regular_season",
        "weapon": "Three Weapon",
        "gender": meet.gender,
        "category": "College",
        "country": "USA",
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": meet.source_url,
            "source_meet_id": meet.meet_id,
            "team_a": meet.team_a,
            "team_b": meet.team_b,
            "bout_count": len(meet.bouts),
            "weapons": sorted({bout.weapon for bout in meet.bouts}),
        },
        "updated_at": utc_now(),
    }


def iter_bout_sides(bout):
    yield {
        "name": bout.fencer_a_name,
        "opponent": bout.fencer_b_name,
        "team": bout.team_a,
        "opponent_team": bout.team_b,
        "weapon": bout.weapon,
        "touches_scored": bout.score_a,
        "touches_received": bout.score_b,
        "decision": bout.decision_a,
    }
    yield {
        "name": bout.fencer_b_name,
        "opponent": bout.fencer_a_name,
        "team": bout.team_b,
        "opponent_team": bout.team_a,
        "weapon": bout.weapon,
        "touches_scored": bout.score_b,
        "touches_received": bout.score_a,
        "decision": bout.decision_b,
    }


def build_result_rows(tournament_id, bouts, fencer_index):
    summaries: dict[Any, Any] = {}
    for bout in bouts:
        for side in iter_bout_sides(bout):
            if normalize_key(side["name"]) == "bout forfeited":
                continue
            key = normalize_key(side["name"])
            row = summaries.setdefault(
                key,
                {
                    "name": side["name"],
                    "team": side["team"],
                    "weapons": set(),
                    "opponents": set(),
                    "matches": 0,
                    "victory": 0,
                    "td": 0,
                    "tr": 0,
                },
            )
            row["weapons"].add(side["weapon"])
            row["opponents"].add(side["opponent_team"])
            row["matches"] += 1
            row["victory"] += 1 if side["decision"] == "win" else 0
            row["td"] += side["touches_scored"]
            row["tr"] += side["touches_received"]

    result_rows = []
    for row in sorted(summaries.values(), key=lambda item: (item["team"], item["name"])):
        weapons = sorted(row["weapons"])
        result_rows.append(
            {
                "tournament_id": tournament_id,
                "fencer_id": fencer_index.get(fencer_lookup_key(row["name"])),
                "fie_fencer_id": None,
                "rank": None,
                "placement": None,
                "name": row["name"],
                "country": "USA",
                "nationality": "USA",
                "victory": row["victory"],
                "matches": row["matches"],
                "td": row["td"],
                "tr": row["tr"],
                "diff": row["td"] - row["tr"],
                "metadata": {
                    "source": SOURCE,
                    "school": row["team"],
                    "weapon": weapons[0] if len(weapons) == 1 else "Mixed",
                    "weapons": weapons,
                    "opponent_teams": sorted(row["opponents"]),
                    "match_method": "name_country_usa"
                    if fencer_index.get(fencer_lookup_key(row["name"]))
                    else "unmatched",
                },
                "updated_at": utc_now(),
            }
        )
    return result_rows


def make_bout_id(tournament_id, source_key):
    seed = f"fencespace:ncaa-regular-bout:{tournament_id}:{source_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def build_bout_rows(tournament_id, bouts, fencer_index):
    rows = []
    for bout in bouts:
        fencer_a_id = fencer_index.get(fencer_lookup_key(bout.fencer_a_name))
        fencer_b_id = fencer_index.get(fencer_lookup_key(bout.fencer_b_name))
        winner = None
        if bout.decision_a == "win":
            winner = fencer_a_id
        elif bout.decision_b == "win":
            winner = fencer_b_id

        rows.append(
            {
                "id": make_bout_id(tournament_id, bout.source_key),
                "tournament_id": tournament_id,
                "fencer_a_id": fencer_a_id,
                "fencer_b_id": fencer_b_id,
                "score_a": bout.score_a,
                "score_b": bout.score_b,
                "winner_id": winner,
                "round": f"Round {bout.round_number or '?'} Match {bout.match_number or '?'}",
                "weapon": bout.weapon,
                "metadata": {
                    "source": SOURCE,
                    "source_url": bout.source_url,
                    "source_page": bout.source_page,
                    "source_key": bout.source_key,
                    "gender": bout.gender,
                    "team_a": bout.team_a,
                    "team_b": bout.team_b,
                    "fencer_a_name": bout.fencer_a_name,
                    "fencer_b_name": bout.fencer_b_name,
                    "decision_a": bout.decision_a,
                    "decision_b": bout.decision_b,
                    "bout_date": bout.date.isoformat(),
                },
                "updated_at": utc_now(),
            }
        )
    return rows


def batch_upsert(client, table, rows, on_conflict=None):
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        query = client.table(table)
        if on_conflict:
            query.upsert(batch, on_conflict=on_conflict).execute()
        else:
            query.upsert(batch).execute()


def missing_column_error(exc, columns):
    message = str(exc).lower()
    return any(column.lower() in message for column in columns) and (
        "column" in message or "schema cache" in message or "could not find" in message
    )


def constraint_error(exc):
    message = str(exc).lower()
    return "unique" in message or "constraint" in message or "42p10" in message


def id_type_error(exc):
    message = str(exc).lower()
    return "id" in message and (
        "invalid input syntax" in message or "type integer" in message or "type bigint" in message
    )


def strip_keys(rows, keys):
    return [{key: value for key, value in row.items() if key not in keys} for row in rows]


def upsert_results(client, rows):
    if not rows:
        return
    try:
        batch_upsert(client, "fs_results", rows, on_conflict="tournament_id,name")
        return
    except Exception as exc:
        if not constraint_error(exc):
            raise

    tournament_ids = sorted({row["tournament_id"] for row in rows})
    for tournament_id in tournament_ids:
        client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    for index in range(0, len(rows), BATCH_SIZE):
        client.table("fs_results").insert(rows[index : index + BATCH_SIZE]).execute()


def upsert_bouts(client, rows):
    if not rows:
        return
    try:
        batch_upsert(client, "fs_bouts", rows, on_conflict="id")
        return
    except Exception as exc:
        if id_type_error(exc):
            batch_upsert(client, "fs_bouts", strip_keys(rows, {"id"}))
            return
        if not missing_column_error(exc, {"weapon", "metadata", "updated_at"}):
            raise

    fallback = strip_keys(rows, {"weapon", "metadata", "updated_at"})
    try:
        batch_upsert(client, "fs_bouts", fallback, on_conflict="id")
    except Exception as exc:
        if not id_type_error(exc):
            raise
        batch_upsert(client, "fs_bouts", strip_keys(fallback, {"id"}))


def upsert_tournament(client, meet):
    row = build_tournament_row(meet)
    result = client.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
    if result.data:
        return result.data[0].get("id")

    data = (
        client.table("fs_tournaments")
        .select("id")
        .eq("source_id", row["source_id"])
        .execute()
        .data
        or []
    )
    return data[0].get("id") if data else None


def write_meet(client, meet):
    tournament_id = upsert_tournament(client, meet)
    if not tournament_id:
        raise RuntimeError(f"upserted tournament not found: {meet.source_id}")

    fencer_index = load_fencer_index(client)
    result_rows = build_result_rows(tournament_id, meet.bouts, fencer_index)
    bout_rows = build_bout_rows(tournament_id, meet.bouts, fencer_index)

    upsert_results(client, result_rows)
    upsert_bouts(client, bout_rows)

    return {"tournament_id": tournament_id, "results": len(result_rows), "bouts": len(bout_rows)}


def scrape_document(client, doc):
    page_texts, status = fetch_pdf_text_pages(doc.url)
    if status != "ok":
        print(f"  Skipping {doc.label}: {status}")
        return {"meets": 0, "results": 0, "bouts": 0, "skipped": 1}

    meets = parse_score_sheet_texts(page_texts, doc.url)
    if not meets:
        print(f"  Skipping {doc.label}: no parseable score sheets")
        return {"meets": 0, "results": 0, "bouts": 0, "skipped": 1}

    summary = {"meets": 0, "results": 0, "bouts": 0, "skipped": 0}
    for meet in meets:
        written = write_meet(client, meet)
        summary["meets"] += 1
        summary["results"] += written["results"]
        summary["bouts"] += written["bouts"]
        print(
            f"  {meet.gender} {meet.team_a} vs {meet.team_b}: "
            f"{written['results']} results, {written['bouts']} bouts"
        )
    return summary


def scrape_ncaa_regular(seasons=None, include_school_pages=True):
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger(SOURCE).start()
    try:
        docs = discover_source_documents(seasons=seasons, include_school_pages=include_school_pages)
        done_urls = set(get_state(SOURCE, "done_source_urls") or [])
        written = failed = skipped = 0
        results_written = bouts_written = 0

        for doc in docs:
            if doc.url in done_urls:
                skipped += 1
                continue
            print(f"\nSource: {doc.label} — {doc.url}")
            try:
                summary = scrape_document(supabase, doc)
                written += summary["meets"]
                results_written += summary["results"]
                bouts_written += summary["bouts"]
                skipped += summary["skipped"]
                done_urls.add(doc.url)
                set_state(SOURCE, "done_source_urls", sorted(done_urls))
            except Exception as exc:
                print(f"  Failed {doc.url}: {exc}")
                failed += 1
            finally:
                time.sleep(REQUEST_DELAY)

        set_state(
            SOURCE,
            "last_run_summary",
            {
                "updated_at": utc_now(),
                "tournaments": written,
                "results": results_written,
                "bouts": bouts_written,
                "failed": failed,
                "skipped": skipped,
            },
        )
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(
            "\nDone — "
            f"tournaments={written}, results={results_written}, "
            f"bouts={bouts_written}, failed={failed}, skipped={skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main():
    scrape_ncaa_regular()


if __name__ == "__main__":
    main()
