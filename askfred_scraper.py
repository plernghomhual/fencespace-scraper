import csv
import hashlib
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://www.askfred.net"
BATCH_SIZE = int(os.environ.get("ASKFRED_BATCH_SIZE", "100"))
START_PAGE = int(os.environ.get("ASKFRED_START_PAGE", "1"))
MAX_RESULT_PAGES = int(os.environ.get("ASKFRED_MAX_RESULT_PAGES", "5"))
MAX_TOURNAMENTS = int(os.environ.get("ASKFRED_MAX_TOURNAMENTS", "0"))
REQUEST_DELAY_MIN = float(os.environ.get("ASKFRED_DELAY_MIN", "1.0"))
REQUEST_DELAY_MAX = float(os.environ.get("ASKFRED_DELAY_MAX", "2.0"))
RETRY_ATTEMPTS = int(os.environ.get("ASKFRED_RETRY_ATTEMPTS", "3"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/csv;q=0.8,*/*;q=0.7",
    "Referer": BASE_URL,
}


@dataclass(frozen=True)
class TournamentRef:
    askfred_id: str
    name: str
    results_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    return text or None


def title_case(value: Any) -> str | None:
    text = clean_text(value)
    return text.title() if text else None


def normalize_name_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_person_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        first = title_case(first)
        last = title_case(last)
        if first and last:
            return first if first.lower() == last.lower() else f"{first} {last}"
        return first or last

    return title_case(text)


def name_from_parts(first_name: Any, last_name: Any) -> str | None:
    first = title_case(first_name)
    last = title_case(last_name)
    if first and last:
        return first if first.lower() == last.lower() else f"{first} {last}"
    return first or last


def to_int(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def stable_negative_id(value: str) -> int:
    # Keeps AskFRED-only club ids away from positive USA Fencing ids.
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:15]
    return -int(digest, 16)


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower()
    if key in {"saber", "sabre"}:
        return "Sabre"
    if key == "epee":
        return "Epee"
    if key == "foil":
        return "Foil"
    return title_case(text)


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower()
    if key in {"men", "mens", "men's", "male"}:
        return "Men"
    if key in {"women", "womens", "women's", "female"}:
        return "Women"
    return title_case(text)


def normalize_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%b %d %Y", "%d %B %Y", "%B %d %Y"]:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


session = make_session()


def polite_sleep():
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def request_get(path_or_url: str, *, params: dict[str, Any] | None = None, accept: str | None = None) -> requests.Response | None:
    global session

    url = path_or_url if path_or_url.startswith("http") else urljoin(BASE_URL, path_or_url)
    headers = {}
    if accept:
        headers["Accept"] = accept

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            print(f"  Connection error fetching {url} (attempt {attempt}/{RETRY_ATTEMPTS}): {exc}")
            session = make_session()
        except requests.exceptions.RequestException as exc:
            print(f"  Request error fetching {url} (attempt {attempt}/{RETRY_ATTEMPTS}): {exc}")

        if attempt < RETRY_ATTEMPTS:
            time.sleep(min(2 * attempt, 8))
    return None


def parse_total_pages(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b\d+\s+of\s+(\d+)\s+pages\b", text)
    return int(match.group(1)) if match else None


def parse_results_index(html: str) -> tuple[list[TournamentRef], int | None]:
    soup = BeautifulSoup(html, "html.parser")
    refs: list[TournamentRef] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.match(r"^/tournaments/([0-9a-f-]+)/results$", href)
        if not match:
            continue

        askfred_id = match.group(1)
        if askfred_id in seen:
            continue

        name = clean_text(link.get_text(" ", strip=True))
        if not name:
            name = f"AskFRED Tournament {askfred_id}"

        refs.append(TournamentRef(askfred_id=askfred_id, name=name, results_path=href))
        seen.add(askfred_id)

    return refs, parse_total_pages(soup)


def discover_tournaments() -> list[TournamentRef]:
    print(
        "Discovering AskFRED result pages "
        f"from page {START_PAGE} for up to {MAX_RESULT_PAGES} page(s)"
    )

    refs: list[TournamentRef] = []
    seen: set[str] = set()
    last_page = START_PAGE + MAX_RESULT_PAGES - 1

    for page in range(START_PAGE, last_page + 1):
        response = request_get("/results", params={"has_results": "true", "page": page})
        polite_sleep()
        if response is None:
            print(f"  Page {page}: failed after retries")
            continue
        if response.status_code != 200:
            print(f"  Page {page}: HTTP {response.status_code}, skipping")
            continue

        page_refs, total_pages = parse_results_index(response.text)
        for ref in page_refs:
            if ref.askfred_id not in seen:
                refs.append(ref)
                seen.add(ref.askfred_id)

        total_label = f" of {total_pages}" if total_pages else ""
        print(f"  Page {page}{total_label}: {len(page_refs)} tournament result links")

        if total_pages and page >= total_pages:
            break
        if MAX_TOURNAMENTS and len(refs) >= MAX_TOURNAMENTS:
            refs = refs[:MAX_TOURNAMENTS]
            break

    print(f"Discovered {len(refs)} unique AskFRED tournaments with results")
    return refs


def csv_rows_for_tournament(ref: TournamentRef) -> list[dict[str, str]]:
    response = request_get(
        f"/tournaments/{ref.askfred_id}/results.csv",
        accept="text/csv, */*;q=0.5",
    )
    polite_sleep()
    if response is None:
        print(f"    CSV fetch failed for {ref.name}")
        return []
    if response.status_code != 200:
        print(f"    CSV fetch HTTP {response.status_code} for {ref.name}")
        return []

    reader = csv.DictReader(StringIO(response.text))
    rows = [
        {(key or "").strip(): value for key, value in row.items()}
        for row in reader
    ]
    print(f"    CSV rows: {len(rows)}")
    return rows


def parse_event_cards(ref: TournamentRef) -> dict[str, dict[str, Any]]:
    response = request_get(ref.results_path)
    polite_sleep()
    if response is None or response.status_code != 200:
        status = response.status_code if response is not None else "failed"
        print(f"    Result page fetch {status}; event ids will fall back to stable hashes")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    event_map: dict[str, dict[str, Any]] = {}

    for card in soup.select("div.card"):
        header = card.select_one(".card-header")
        if not header:
            continue

        spans = [clean_text(span.get_text(" ", strip=True)) for span in header.find_all("span")]
        event_name = next((span for span in spans if span), None)
        event_link = header.find("a", href=re.compile(r"^/events/[0-9a-f-]+"))
        if not event_name or not event_link:
            continue

        event_match = re.search(r"/events/([0-9a-f-]+)", event_link["href"])
        if not event_match:
            continue

        event_map[normalize_name_key(event_name)] = {
            "event_name": event_name,
            "event_uuid": event_match.group(1),
            "event_path": event_link["href"],
            "event_summary": spans[1] if len(spans) > 1 else None,
        }

    print(f"    Event cards: {len(event_map)}")
    return event_map


def split_competitor_cell(value: Any) -> tuple[str | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None
    match = re.match(r"^(.*?)\s*\((.*?)\)\s*$", text)
    if match:
        return normalize_person_name(match.group(1)), clean_text(match.group(2))
    return normalize_person_name(text), None


def parse_victory_cell(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None


def parse_bout_cell(value: Any) -> dict[str, Any] | None:
    text = clean_text(value)
    if not text or text == "-":
        return None
    match = re.match(r"([VD])\s*(\d+)?", text, re.IGNORECASE)
    if not match:
        return {"raw": text}
    return {
        "result": match.group(1).upper(),
        "score_for": int(match.group(2)) if match.group(2) else None,
        "raw": text,
    }


def parse_pool_stats(event_uuid: str) -> dict[str, dict[str, Any]]:
    response = request_get(f"/events/{event_uuid}")
    polite_sleep()
    if response is None or response.status_code != 200:
        status = response.status_code if response is not None else "failed"
        print(f"      Round page fetch {status}; pool stats unavailable")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    stats: dict[str, dict[str, Any]] = {}

    for pool_index, table in enumerate(soup.find_all("table"), start=1):
        header_cells = [clean_text(th.get_text(" ", strip=True)) or "" for th in table.find_all("th")]
        if not header_cells or "Competitor - Club" not in header_cells[0]:
            continue

        rows = table.find_all("tr")
        competitors: list[tuple[str | None, str | None]] = []
        parsed_rows: list[list[str]] = []

        for row in rows[1:]:
            cells = [clean_text(cell.get_text(" ", strip=True)) or "" for cell in row.find_all(["td", "th"])]
            if not cells:
                continue
            competitors.append(split_competitor_cell(cells[0]))
            parsed_rows.append(cells)

        stat_index = {name: idx for idx, name in enumerate(header_cells)}
        bout_columns = [
            idx
            for idx, header in enumerate(header_cells)
            if idx > 0 and re.fullmatch(r"\d+", header or "")
        ]

        for row_index, cells in enumerate(parsed_rows):
            name, club_abbrev = competitors[row_index]
            if not name:
                continue

            key = normalize_name_key(name)
            bouts = []
            for column in bout_columns:
                if column >= len(cells):
                    continue
                bout = parse_bout_cell(cells[column])
                if not bout:
                    continue
                opponent_index = int(header_cells[column]) - 1
                opponent_name = None
                if 0 <= opponent_index < len(competitors):
                    opponent_name = competitors[opponent_index][0]
                bout["opponent"] = opponent_name
                bout["pool"] = pool_index
                bouts.append(bout)

            entry = {
                "victory": parse_victory_cell(cells[stat_index["V(%)"]]) if "V(%)" in stat_index and stat_index["V(%)"] < len(cells) else None,
                "matches": len(bouts) or None,
                "td": to_int(cells[stat_index["TS"]]) if "TS" in stat_index and stat_index["TS"] < len(cells) else None,
                "tr": to_int(cells[stat_index["TR"]]) if "TR" in stat_index and stat_index["TR"] < len(cells) else None,
                "diff": to_int(cells[stat_index["Ind"]]) if "Ind" in stat_index and stat_index["Ind"] < len(cells) else None,
                "club_abbrev": club_abbrev,
                "pool": pool_index,
                "pool_bouts": bouts,
            }
            stats[key] = entry

    print(f"      Pool stats: {len(stats)} fencers")
    return stats


def group_csv_rows(rows: list[dict[str, str]], event_map: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        tournament_name = clean_text(row.get("Tournament"))
        event_name = clean_text(row.get("Event"))
        if not tournament_name or not event_name:
            continue

        event_info = event_map.get(normalize_name_key(event_name), {})
        event_uuid = event_info.get("event_uuid")
        fallback_key = stable_hash(f"{tournament_name}|{event_name}")
        source_key = f"askfred:event:{event_uuid or fallback_key}"

        if source_key not in grouped:
            grouped[source_key] = {
                "source_key": source_key,
                "tournament_name": tournament_name,
                "event_name": event_name,
                "event_uuid": event_uuid,
                "event_path": event_info.get("event_path"),
                "event_summary": event_info.get("event_summary"),
                "rows": [],
            }
        grouped[source_key]["rows"].append(row)

    return grouped


def build_tournament_rows(ref: TournamentRef, grouped_events: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source_key, event in grouped_events.items():
        first = event["rows"][0]
        event_date = normalize_date(first.get("Date"))
        season = event_date[:4] if event_date else None
        event_name = event["event_name"]
        tournament_name = event["tournament_name"]
        display_name = f"{tournament_name}: {event_name}"

        rows.append(
            {
                "fie_id": source_key,
                "season": season,
                "name": display_name[:180],
                "location": None,
                "country": "United States",
                "weapon": normalize_weapon(first.get("Weapon")),
                "gender": normalize_gender(first.get("Event Gender")),
                "category": clean_text(first.get("Age Resitrction") or first.get("Age Restriction")),
                "start_date": event_date,
                "end_date": event_date,
                "type": "AskFRED",
                "has_results": True,
                "is_sub_competition": False,
                "metadata": {
                    "source": "askfred",
                    "askfred_tournament_uuid": ref.askfred_id,
                    "askfred_event_uuid": event.get("event_uuid"),
                    "askfred_event_path": event.get("event_path"),
                    "askfred_event_name": event_name,
                    "askfred_tournament_name": tournament_name,
                    "askfred_event_summary": event.get("event_summary"),
                    "askfred_results_path": ref.results_path,
                    "askfred_event_rating": clean_text(first.get("Event Rating")),
                    "askfred_event_size": to_int(first.get("Event Size")),
                    "askfred_rating_restriction": clean_text(first.get("Rating Restriction")),
                },
                "updated_at": utc_now(),
            }
        )
    return rows


def batch_upsert(table: str, rows: list[dict[str, Any]], *, on_conflict: str, batch_size: int = BATCH_SIZE):
    for i in range(0, len(rows), batch_size):
        supabase.table(table).upsert(rows[i : i + batch_size], on_conflict=on_conflict).execute()


def upsert_tournaments(rows: list[dict[str, Any]]) -> dict[str, int]:
    if not rows:
        return {}

    batch_upsert("fs_tournaments", rows, on_conflict="fie_id")

    ids: dict[str, int] = {}
    source_keys = [row["fie_id"] for row in rows]
    for i in range(0, len(source_keys), BATCH_SIZE):
        chunk = source_keys[i : i + BATCH_SIZE]
        result = supabase.table("fs_tournaments").select("id,fie_id").in_("fie_id", chunk).execute()
        for row in result.data or []:
            ids[row["fie_id"]] = row["id"]

    return ids


def fetch_us_fencer_index() -> dict[str, list[dict[str, Any]]]:
    print("Loading existing United States fencers for name matching...")
    index: dict[str, list[dict[str, Any]]] = {}
    start = 0
    page_size = 1000

    while True:
        response = (
            supabase.table("fs_fencers")
            .select("id,name,country,club,metadata")
            .eq("country", "United States")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            key = normalize_name_key(row.get("name"))
            if key:
                index.setdefault(key, []).append(row)
        if len(rows) < page_size:
            break
        start += page_size

    print(f"Loaded {sum(len(v) for v in index.values())} United States fencer rows")
    return index


def fencer_key(usfa_number: Any, name: str | None, club: str | None) -> str:
    usfa = re.sub(r"\D", "", str(usfa_number or ""))
    if usfa:
        return f"askfred:usfa:{usfa}"
    fallback_source = f"{name or ''}|{club or ''}"
    return f"askfred:name:{stable_hash(normalize_name_key(fallback_source))}"


def merge_metadata(existing: Any, updates: dict[str, Any]) -> dict[str, Any]:
    metadata = existing if isinstance(existing, dict) else {}
    merged = dict(metadata)
    merged.update({key: value for key, value in updates.items() if value is not None})
    return merged


def collect_result_rows(
    ref: TournamentRef,
    grouped_events: dict[str, dict[str, Any]],
    tournament_ids: dict[str, int],
    fencer_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    result_rows: list[dict[str, Any]] = []
    fencer_updates_by_id: dict[int, dict[str, Any]] = {}
    clubs: dict[str, str] = {}

    for source_key, event in grouped_events.items():
        tournament_id = tournament_ids.get(source_key)
        if not tournament_id:
            print(f"    Missing fs_tournaments id for {source_key}; skipping event results")
            continue

        pool_stats: dict[str, dict[str, Any]] = {}
        event_uuid = event.get("event_uuid")
        if event_uuid:
            print(f"    Fetching round data for {event['event_name']}")
            pool_stats = parse_pool_stats(event_uuid)

        for row in event["rows"]:
            name = name_from_parts(row.get("Competitor First Name"), row.get("Competitor Last Name"))
            if not name:
                continue

            rank = to_int(row.get("Place"))
            if rank is None:
                continue

            club = clean_text(row.get("Club"))
            if club:
                clubs[normalize_name_key(club)] = club

            name_key = normalize_name_key(name)
            matched_fencers = fencer_index.get(name_key, [])
            fencer_id = matched_fencers[0]["id"] if matched_fencers else None

            rating_before = clean_text(row.get("Rating Before Event"))
            rating_earned = clean_text(row.get("Rating Earned"))
            current_rating = rating_earned or rating_before

            for fencer in matched_fencers:
                update: dict[str, Any] = {
                    "id": fencer["id"],
                    "name": fencer.get("name") or name,
                    "country": "United States",
                    "updated_at": utc_now(),
                }
                if club and clean_text(fencer.get("club")) != club:
                    update["club"] = club
                if current_rating:
                    update["metadata"] = merge_metadata(
                        fencer.get("metadata"),
                        {
                            "askfred_rating": current_rating,
                            "askfred_rating_before_event": rating_before,
                            "askfred_rating_earned": rating_earned,
                            "askfred_rating_source_tournament": ref.askfred_id,
                            "askfred_rating_updated_at": utc_now(),
                        },
                    )
                if "club" in update or "metadata" in update:
                    fencer_updates_by_id[fencer["id"]] = update

            stats = pool_stats.get(name_key, {})
            askfred_fencer_key = fencer_key(row.get("Usfa Number"), name, club)
            metadata = {
                "source": "askfred",
                "askfred_tournament_uuid": ref.askfred_id,
                "askfred_tournament_name": event["tournament_name"],
                "askfred_event_uuid": event.get("event_uuid"),
                "askfred_event_name": event["event_name"],
                "askfred_event_path": event.get("event_path"),
                "askfred_usfa_number": clean_text(row.get("Usfa Number")),
                "askfred_club": club,
                "askfred_rating_before_event": rating_before,
                "askfred_rating_earned": rating_earned,
                "askfred_event_rating": clean_text(row.get("Event Rating")),
                "askfred_event_size": to_int(row.get("Event Size")),
                "askfred_rating_restriction": clean_text(row.get("Rating Restriction")),
                "askfred_age_restriction": clean_text(row.get("Age Resitrction") or row.get("Age Restriction")),
                "askfred_pool": stats.get("pool"),
                "askfred_pool_bouts": stats.get("pool_bouts"),
                "askfred_pool_club_abbrev": stats.get("club_abbrev"),
            }

            result_rows.append(
                {
                    "tournament_id": tournament_id,
                    "fie_fencer_id": askfred_fencer_key,
                    "fencer_id": fencer_id,
                    "rank": rank,
                    "placement": rank,
                    "name": name,
                    "country": "United States",
                    "nationality": "United States",
                    "victory": stats.get("victory"),
                    "matches": stats.get("matches"),
                    "td": stats.get("td"),
                    "tr": stats.get("tr"),
                    "diff": stats.get("diff"),
                    "metadata": metadata,
                    "updated_at": utc_now(),
                }
            )

    return result_rows, list(fencer_updates_by_id.values()), clubs


def upsert_results(rows: list[dict[str, Any]]):
    if not rows:
        return

    try:
        batch_upsert("fs_results", rows, on_conflict="tournament_id,fie_fencer_id")
        return
    except Exception as exc:
        message = str(exc)
        if "unique" not in message.lower() and "constraint" not in message.lower() and "42P10" not in message:
            raise

        print(
            "    Results upsert conflict key is not available in this database; "
            "falling back to replacing AskFRED rows for affected events."
        )

    affected_tournament_ids = sorted({row["tournament_id"] for row in rows})
    for tournament_id in affected_tournament_ids:
        (
            supabase.table("fs_results")
            .delete()
            .eq("tournament_id", tournament_id)
            .like("fie_fencer_id", "askfred:%")
            .execute()
        )

    for i in range(0, len(rows), BATCH_SIZE):
        supabase.table("fs_results").insert(rows[i : i + BATCH_SIZE]).execute()


def upsert_fencer_updates(rows: list[dict[str, Any]]):
    if not rows:
        return
    batch_upsert("fs_fencers", rows, on_conflict="id")


def upsert_clubs(clubs: dict[str, str]):
    if not clubs:
        return

    rows = []
    for key, name in sorted(clubs.items()):
        rows.append(
            {
                "usafencing_id": stable_negative_id(f"askfred-club:{key}"),
                "name": name,
                "city": None,
                "state": None,
                "country": "USA",
                "is_active": True,
                "metadata": {
                    "source": "askfred",
                    "askfred_club_key": key,
                    "askfred_synthetic_usafencing_id": True,
                },
                "updated_at": utc_now(),
            }
        )

    batch_upsert("fs_clubs", rows, on_conflict="usafencing_id")


def scrape_tournament(ref: TournamentRef, fencer_index: dict[str, list[dict[str, Any]]]) -> tuple[int, int, int]:
    print(f"\n  Scraping {ref.name} ({ref.askfred_id})")
    csv_rows = csv_rows_for_tournament(ref)
    if not csv_rows:
        print("    No CSV result rows found")
        return 0, 0, 0

    event_map = parse_event_cards(ref)
    grouped_events = group_csv_rows(csv_rows, event_map)
    if not grouped_events:
        print("    No event groups found")
        return 0, 0, 0

    tournament_rows = build_tournament_rows(ref, grouped_events)
    tournament_ids = upsert_tournaments(tournament_rows)
    print(f"    Upserted {len(tournament_rows)} AskFRED event tournament rows")

    result_rows, fencer_updates, clubs = collect_result_rows(ref, grouped_events, tournament_ids, fencer_index)
    upsert_results(result_rows)
    upsert_fencer_updates(fencer_updates)
    upsert_clubs(clubs)

    print(
        f"    Upserted {len(result_rows)} results, "
        f"{len(fencer_updates)} fencer updates, {len(clubs)} clubs"
    )
    return len(result_rows), len(fencer_updates), len(clubs)


def main():
    print(f"AskFRED scraper starting - {utc_now()}")
    print(
        "Settings: "
        f"start_page={START_PAGE}, max_pages={MAX_RESULT_PAGES}, "
        f"max_tournaments={MAX_TOURNAMENTS or 'none'}, delay={REQUEST_DELAY_MIN}-{REQUEST_DELAY_MAX}s"
    )

    fencer_index = fetch_us_fencer_index()
    tournament_refs = discover_tournaments()

    total_results = 0
    total_fencer_updates = 0
    total_clubs = 0
    failed = 0

    for index, ref in enumerate(tournament_refs, start=1):
        print(f"\nTournament {index}/{len(tournament_refs)}")
        try:
            results_count, fencer_count, club_count = scrape_tournament(ref, fencer_index)
            total_results += results_count
            total_fencer_updates += fencer_count
            total_clubs += club_count
        except Exception as exc:
            failed += 1
            print(f"    Error scraping {ref.name}: {exc}")

    print(
        "\nAskFRED scraper complete - "
        f"results={total_results}, fencer_updates={total_fencer_updates}, "
        f"clubs={total_clubs}, failed_tournaments={failed}"
    )


if __name__ == "__main__":
    main()
