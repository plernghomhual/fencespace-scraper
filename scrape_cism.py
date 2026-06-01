"""
CISM World Military Games fencing results scraper.

Probe notes (verified 2026-06-01):
  Source page: https://www.milsport.one/sports/cism-disciplines-world-level-sport/fencing
  Structured World Summer Games download:
    "CISM WSG Wuhan 2019 - 47th WMC Fencing" -> /medias/fichiers/8__Fencing.pdf

The CISM site mixes HTML event pages and PDF downloads. This scraper imports only
World Games fencing PDFs whose standings text can be extracted reliably.
"""
import os
import re
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

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

CISM_BASE = "https://www.milsport.one"
CISM_FENCING_PAGE = f"{CISM_BASE}/sports/cism-disciplines-world-level-sport/fencing"
SOURCE = "cism"
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}


def _normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("´", "'").replace("’", "'").replace("`", "'")
    value = re.sub(r"[^a-zA-Z0-9']+", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _slug(value):
    value = _normalize_text(value).replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _clean_line(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_year(value):
    match = re.search(r"\b((?:19|20)\d{2})\b", value or "")
    return match.group(1) if match else None


def classify_event(event_name):
    """Return {weapon, gender, team} for English or French CISM event names."""
    normalized = _normalize_text(event_name)

    weapon = None
    if re.search(r"\b(epee|épée)\b", normalized):
        weapon = "Epee"
    elif re.search(r"\b(foil|fleuret)\b", normalized):
        weapon = "Foil"
    elif re.search(r"\b(sabre|saber)\b", normalized):
        weapon = "Sabre"

    gender = None
    if re.search(r"\b(women|woman|dames?|female|ladies)\b", normalized):
        gender = "Women"
    elif re.search(r"\b(men|man|hommes?|male|messieurs)\b", normalized):
        gender = "Men"

    team = bool(re.search(r"\b(team|teams|equipe|equipes)\b", normalized))
    return {"weapon": weapon, "gender": gender, "team": team}


def _event_code(classification):
    weapon = (classification["weapon"] or "unknown").lower()
    gender = (classification["gender"] or "unknown").lower()
    format_name = "team" if classification["team"] else "individual"
    return f"{gender}_{format_name}_{weapon}"


def _is_event_title(line):
    classification = classify_event(line)
    if not classification["weapon"] or not classification["gender"]:
        return False
    normalized = _normalize_text(line)
    return bool(re.search(r"\b(individual|individuel|individuelle|team|teams|equipe|equipes)\b", normalized))


def parse_source_page(html):
    """Discover structured CISM World Summer Games fencing result PDF editions."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    editions = []
    seen_urls = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href:
            continue
        title = _clean_line(link.get_text(" ", strip=True))
        absolute_url = urljoin(CISM_BASE, href)
        haystack = f"{title} {absolute_url}".lower()
        if not absolute_url.lower().split("?", 1)[0].endswith(".pdf"):
            continue
        if "fencing" not in haystack:
            continue
        if not any(marker in haystack for marker in ("wsg", "world summer games", "military world games")):
            continue
        if absolute_url in seen_urls:
            continue

        year = _extract_year(title) or _extract_year(absolute_url)
        city_match = re.search(r"\b(?:wsg|games)\s+(.+?)\s+((?:19|20)\d{2})\b", title, re.I)
        city = city_match.group(1) if city_match else "cism"
        edition_id = f"{_slug(city)}-{year}" if year else _slug(title or absolute_url)
        editions.append({
            "edition_id": edition_id,
            "edition_name": title or f"CISM World Military Games {year or edition_id}",
            "url": absolute_url,
            "format": "pdf",
        })
        seen_urls.add(absolute_url)
    return editions


def _parse_rank(value):
    value = _clean_line(value)
    if not re.fullmatch(r"\d{1,3}", value):
        return None
    return int(value)


def _parse_country_code(value):
    value = _clean_line(value)
    match = re.match(r"([A-Z]{3})\b", value)
    return match.group(1) if match else None


def _is_noise_line(value):
    normalized = _normalize_text(value)
    return (
        not normalized
        or normalized in {"final standings", "name", "nation", "country", "medal", "dnf", "dns", "dsq"}
        or normalized.startswith("as of ")
        or normalized.startswith("report created")
        or bool(re.search(r"^FEN[A-Z-]+_", _clean_line(value)))
    )


def _title_word(value):
    if value.isupper():
        return value.title()
    return value


def _combine_split_name(surname, first_name):
    parts = [_title_word(part) for part in f"{first_name} {surname}".split()]
    return " ".join(parts).strip()


def _medal_for_rank(rank):
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _next_event_index(lines, start):
    for idx in range(start + 1, len(lines)):
        if _is_event_title(lines[idx]):
            return idx
    return len(lines)


def _find_rank_run(segment):
    for idx, line in enumerate(segment):
        if _normalize_text(line) != "rank":
            continue
        start = None
        ranks = []
        for j in range(idx + 1, len(segment)):
            rank = _parse_rank(segment[j])
            if rank is None:
                if start is not None:
                    break
                continue
            if start is None:
                start = j
            ranks.append(rank)
        if ranks:
            return idx, start, start + len(ranks), ranks
    return None, None, None, []


def _parse_individual_standings(segment):
    normalized_segment = [_normalize_text(line) for line in segment]
    if "final standings" not in normalized_segment and any("seed" in line for line in normalized_segment):
        return []

    rank_header, rank_start, rank_end, ranks = _find_rank_run(segment)
    if not ranks:
        return []
    count = len(ranks)
    header_region = normalized_segment[rank_header:rank_start]

    rows = []
    if "first name" in header_region and "country" in header_region:
        surname_start = rank_end
        first_name_start = surname_start + count
        country_start = first_name_start + count
        if len(segment) < country_start + count:
            return []
        surnames = segment[surname_start:first_name_start]
        first_names = segment[first_name_start:country_start]
        countries = segment[country_start:country_start + count]
        for rank, surname, first_name, country_raw in zip(ranks, surnames, first_names, countries):
            country = _parse_country_code(country_raw)
            name = _combine_split_name(surname, first_name)
            if name and country:
                rows.append({"rank": rank, "name": name, "country": country, "medal": _medal_for_rank(rank)})
        return rows

    names_start = rank_end
    country_header = None
    for idx in range(names_start, len(segment)):
        if _normalize_text(segment[idx]) in {"nation", "country"}:
            country_header = idx
            break
    if country_header is None or country_header < names_start + count:
        return []

    names = [
        line
        for line in segment[names_start:country_header]
        if not _is_noise_line(line) and _parse_rank(line) is None
    ][:count]
    countries = [
        line
        for line in segment[country_header + 1:]
        if _parse_country_code(line)
    ][:count]
    if len(countries) < count:
        return []
    for rank, name, country_raw in zip(ranks, names, countries):
        country = _parse_country_code(country_raw)
        name = _clean_line(name)
        if name and country:
            rows.append({"rank": rank, "name": name, "country": country, "medal": _medal_for_rank(rank)})
    return rows


def _parse_team_medallists(segment):
    normalized_segment = [_normalize_text(line) for line in segment]
    if "medallists" not in normalized_segment and "medalists" not in normalized_segment:
        return []

    medal_rank = {"gold": 1, "silver": 2, "bronze": 3}
    rows = []
    idx = 0
    while idx < len(segment):
        medal_key = _normalize_text(segment[idx])
        if medal_key not in medal_rank:
            idx += 1
            continue
        country_line = segment[idx + 1] if idx + 1 < len(segment) else ""
        country = _parse_country_code(country_line)
        if not country:
            idx += 1
            continue
        country_name = re.sub(r"^[A-Z]{3}\s*-\s*", "", _clean_line(country_line))
        members = []
        idx += 2
        while idx < len(segment) and _normalize_text(segment[idx]) not in medal_rank:
            if re.search(r"^FEN[A-Z-]+_", segment[idx]) or _normalize_text(segment[idx]).startswith("report created"):
                break
            value = _clean_line(segment[idx])
            if value and _normalize_text(value) not in {"name", "nation", "medal"}:
                members.append(value)
            idx += 1
        rank = medal_rank[medal_key]
        rows.append({
            "rank": rank,
            "name": country_name or country,
            "country": country,
            "medal": medal_key.capitalize(),
            "team_members": members,
        })
    return rows


def parse_pdf_text(text, edition_id, edition_name):
    """Parse CISM PDF-extracted text into event dicts with placement rows."""
    lines = [_clean_line(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    events_by_code = {}

    for idx, title in enumerate(lines):
        if not _is_event_title(title):
            continue
        classification = classify_event(title)
        if not classification["weapon"] or not classification["gender"]:
            continue
        end = _next_event_index(lines, idx)
        segment = lines[idx:end]
        rows = _parse_team_medallists(segment) if classification["team"] else []
        if not rows:
            rows = _parse_individual_standings(segment)
        if not rows:
            continue

        event_code = _event_code(classification)
        event = {
            "edition_id": edition_id,
            "edition_name": edition_name,
            "event_code": event_code,
            "event_name": title,
            "classification": classification,
            "rows": rows,
            "metadata": {"event_title": title},
        }
        current = events_by_code.get(event_code)
        if current is None or len(rows) > len(current["rows"]):
            events_by_code[event_code] = event

    return list(events_by_code.values())


def _extract_pdf_text(pdf_bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        try:
            import pdfplumber

            parts = []
            with pdfplumber.open(tmp.name) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            return "\n".join(parts)
        except ModuleNotFoundError:
            from pdfminer.high_level import extract_text

            return extract_text(tmp.name)


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                if url.lower().split("?", 1)[0].endswith(".pdf"):
                    return response.content
                return response.text
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def discover_editions():
    html = _get(CISM_FENCING_PAGE)
    return parse_source_page(html)


def fetch_edition_events(edition):
    content = _get(edition["url"])
    if not content:
        return []
    if edition.get("format") == "pdf":
        text = _extract_pdf_text(content if isinstance(content, bytes) else content.encode("utf-8"))
        events = parse_pdf_text(text, edition["edition_id"], edition["edition_name"])
    else:
        events = []
    for event in events:
        event["source_url"] = edition["url"]
        event["data_format"] = edition.get("format")
        event["metadata"]["source_url"] = edition["url"]
        event["metadata"]["data_format"] = edition.get("format")
    return events


def upsert_tournament(event):
    classification = event["classification"]
    source_id = f"cism:{event['edition_id']}:{event['event_code']}"
    year = _extract_year(event["edition_name"]) or _extract_year(event["edition_id"])
    row = {
        "source_id": source_id,
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": year,
        "type": "military_games",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "cism_edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_code": event["event_code"],
            "event_title": event["metadata"]["event_title"],
            "team": classification["team"],
            "source_url": event.get("source_url"),
            "data_format": event.get("data_format"),
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(name, country):
    try:
        rows = supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(2).execute().data
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_results(tournament_id, result_rows):
    db_rows = []
    for row in result_rows:
        if row["rank"] is None:
            continue
        fencer_id = None
        if not row.get("team_members") and row.get("name") and row.get("country"):
            fencer_id = _match_fencer(row["name"], row["country"])
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row["name"],
            "nationality": row["country"],
            "rank": row["rank"],
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": {"team_members": row.get("team_members")},
        })
    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for idx in range(0, len(db_rows), 100):
        batch = db_rows[idx:idx + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_cism").start()
    try:
        print(f"CISM scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        editions = discover_editions()
        print(f"  {len(editions)} CISM World Games fencing editions found")

        written = failed = skipped = 0
        for edition in editions:
            print(f"\n  Edition: {edition['edition_name']} ({edition['edition_id']})")
            events = fetch_edition_events(edition)
            if not events:
                print("    No extractable fencing events found")
                skipped += 1
                continue

            print(f"    {len(events)} events found")
            for event in events:
                source_id = f"cism:{event['edition_id']}:{event['event_code']}"
                if source_id in done_source_ids:
                    skipped += 1
                    continue
                print(f"    {event['event_name']} ({len(event['rows'])} rows)")
                tournament_id = upsert_tournament(event)
                if not tournament_id:
                    failed += 1
                    continue
                inserted = upsert_results(tournament_id, event["rows"])
                if inserted == 0:
                    failed += 1
                    continue
                done_source_ids.add(source_id)
                set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
                written += 1
                time.sleep(REQUEST_DELAY)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
