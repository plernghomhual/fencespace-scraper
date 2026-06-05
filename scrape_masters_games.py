"""
Masters Games veteran fencing results scraper.

Probe notes (2026-06-01):
  IMGA public archive: /other-sports-results-a-h/ links fencing PDFs.
    - Fencing-Results-WMG-1998.pdf: image-only; skip with warning.
    - All-fencing-results-2019.pdf: extractable PDF text.
  Olympedia search: no World Masters Games fencing result tables found.
"""
from typing import Any
import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
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


def _db() -> Any:
    if supabase is None:
        raise RuntimeError("Supabase is not configured")
    return supabase

SOURCE = "masters_games"
IMGA_RESULTS_URL = "https://www.imga.ch/other-sports-results-a-h/"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

WEAPON_PATTERNS = [
    (re.compile(r"\b(epee|spada)\b", re.I), "Epee"),
    (re.compile(r"\b(foil|fioretto)\b", re.I), "Foil"),
    (re.compile(r"\b(sabre|saber|sciabola)\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\b(women|women's|female|femminile)\b", re.I), "Women"),
    (re.compile(r"\b(men|men's|male|maschile)\b", re.I), "Men"),
]

MEDALS_BY_RANK = {1: "Gold", 2: "Silver", 3: "Bronze"}


def _ascii(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def _squash_spaces(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_pdf_token(text):
    text = re.sub(r"\(cid:\d+\)", "", text or "")
    if text and text.isdigit() and len(set(text)) == 1:
        return text[0]

    chars = list(text)
    if len(chars) >= 4 and len(chars) % 2 == 0:
        pairs = [chars[i] == chars[i + 1] for i in range(0, len(chars), 2)]
        if all(pairs):
            return "".join(chars[i] for i in range(0, len(chars), 2))

    return text


def _clean_pdf_text(text):
    return _squash_spaces(" ".join(_clean_pdf_token(part) for part in (text or "").split()))


def _normalized(text):
    return _ascii(_clean_pdf_text(text)).lower()


def extract_age_category(event_name):
    """Extract veteran/masters age category while preserving the visible label."""
    text = _clean_pdf_text(event_name)

    m = re.search(r"\bcat\.?\s*([0-9]+[A-Z]?)\b", text, re.I)
    if m:
        return f"Cat.{m.group(1)}"

    m = re.search(r"\bV\s*-?\s*(\d{2})(?:\+)?\b", text, re.I)
    if m:
        return f"V{m.group(1)}"

    m = re.search(r"\bVeterans?\s+(V?\d{2}\+?|\d{2}\s*-\s*\d{2})(?=\s|$)", text, re.I)
    if m:
        value = re.sub(r"\s*-\s*", "-", m.group(1).upper())
        return f"Veteran {value}"

    m = re.search(r"\bMasters?\s+(V?\d{2}\+?|\d{2}\s*-\s*\d{2})(?=\s|$)", text, re.I)
    if m:
        value = re.sub(r"\s*-\s*", "-", m.group(1).upper())
        return f"Masters {value}"

    m = re.search(r"\b(\d{2}\s*-\s*\d{2}|\d{2}\+)\b", text)
    if m:
        return re.sub(r"\s*-\s*", "-", m.group(1))

    if re.search(r"\bVeterans?\b", text, re.I):
        return "Veteran"
    if re.search(r"\bMasters?\b", text, re.I):
        return "Masters"
    return None


def classify_event(event_name):
    normalized = _normalized(event_name)
    weapon = next((weapon for pat, weapon in WEAPON_PATTERNS if pat.search(normalized)), None)
    gender = next((gender for pat, gender in GENDER_PATTERNS if pat.search(normalized)), None)
    return {
        "weapon": weapon,
        "gender": gender,
        "age_category": extract_age_category(event_name),
        "team": bool(re.search(r"\bteam\b", normalized)),
    }


def event_code(event_name):
    slug = _normalized(event_name).replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "event"


def _source_id(edition_id, code):
    return f"masters:{edition_id}:{code}"


def _parse_rank(text):
    m = re.search(r"\d+", _clean_pdf_text(text or ""))
    return int(m.group(0)) if m else None


def _parse_medal(text, rank):
    medal = _clean_pdf_text(text or "").title()
    if medal in {"Gold", "Silver", "Bronze"}:
        return medal
    return MEDALS_BY_RANK.get(rank)


def _header_indexes(header_cells):
    indexes: dict[Any, Any] = {}
    for i, header in enumerate(header_cells):
        value = _normalized(header)
        if any(k in value for k in ("rank", "place", "pos", "position", "posto")):
            indexes.setdefault("rank", i)
        elif any(k in value for k in ("country", "nation", "nationality", "noc", "nazione")):
            indexes.setdefault("country", i)
        elif any(k in value for k in ("medal",)):
            indexes.setdefault("medal", i)
        elif any(k in value for k in ("name", "competitor", "athlete", "fencer", "nome")):
            indexes.setdefault("name", i)
    return indexes


def _parse_html_table_rows(table, classification):
    trs = table.find_all("tr")
    if not trs:
        return []

    header_cells = [cell.get_text(" ", strip=True) for cell in trs[0].find_all(["th", "td"])]
    indexes = _header_indexes(header_cells)
    if "rank" not in indexes or "name" not in indexes:
        indexes = {"rank": 0, "name": 2, "country": 3, "medal": 4}
        if len(header_cells) == 4:
            indexes = {"rank": 0, "name": 1, "country": 2, "medal": 3}

    rows = []
    for tr in trs[1:]:
        cells = [_squash_spaces(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        if len(cells) <= max(indexes.get("rank", 0), indexes.get("name", 0)):
            continue
        rank = _parse_rank(cells[indexes["rank"]])
        name = cells[indexes["name"]]
        if rank is None or not name:
            continue
        country = cells[indexes["country"]] if indexes.get("country", -1) < len(cells) else None
        medal_text = cells[indexes["medal"]] if indexes.get("medal", -1) < len(cells) else ""
        rows.append({
            "rank": rank,
            "name": name,
            "country": country or None,
            "medal": _parse_medal(medal_text, rank),
            "weapon": classification["weapon"],
            "gender": classification["gender"],
            "age_category": classification["age_category"],
        })
    return rows


def _event_from_parts(edition_id, edition_name, event_name, rows, source_url=None):
    code = event_code(event_name)
    classification = classify_event(event_name)
    return {
        "edition_id": str(edition_id),
        "edition_name": edition_name,
        "event_name": event_name,
        "event_code": code,
        "source_id": _source_id(edition_id, code),
        "source_url": source_url,
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "age_category": classification["age_category"],
        "team": classification["team"],
        "rows": rows,
    }


def parse_html_results_page(html, edition_id, edition_name=None, source_url=None):
    """Parse a Masters Games HTML results page into event dictionaries."""
    soup = BeautifulSoup(html or "", "html.parser")
    events = []
    for table in soup.find_all("table"):
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        caption = table.find("caption")
        event_name = _squash_spaces(
            caption.get_text(" ", strip=True) if caption else heading.get_text(" ", strip=True) if heading else ""
        )
        classification = classify_event(event_name)
        if not classification["weapon"] or not classification["gender"] or not classification["age_category"]:
            continue
        rows = _parse_html_table_rows(table, classification)
        if rows:
            events.append(_event_from_parts(edition_id, edition_name, event_name, rows, source_url))
    return events


def _group_words_by_top(words, tolerance=3.0):
    rows: list[tuple[float, list[Any]]] = []
    for word in sorted(words, key=lambda w: (float(w.get("top", 0)), float(w.get("x0", 0)))):
        top = float(word.get("top", 0))
        if not rows or abs(rows[-1][0] - top) > tolerance:
            rows.append((top, [word]))
        else:
            rows[-1][1].append(word)
    return [row_words for _, row_words in rows]


def _pdf_event_name(words):
    tokens = []
    for word in sorted(words, key=lambda w: (float(w.get("top", 0)), float(w.get("x0", 0)))):
        top = float(word.get("top", 0))
        if top > 35:
            continue
        token = _clean_pdf_token(word.get("text", ""))
        normalized = _normalized(token)
        if not token or token == "--" or normalized in {"emg", "wmg"}:
            continue
        if re.fullmatch(r"\d{4}", token) or re.fullmatch(r"\d{2}/\d{2}/\d{4}", token):
            continue
        tokens.append(token)

    if tokens and tokens[-1].isdigit() and not extract_age_category(" ".join(tokens)):
        tokens[-1] = f"Cat.{tokens[-1]}"
    return _squash_spaces(" ".join(tokens))


def _pdf_header_columns(row):
    columns = {}
    for word in row:
        label = _normalized(word.get("text", ""))
        x0 = float(word.get("x0", 0))
        if any(k in label for k in ("posto", "rank", "place", "pos")):
            columns["rank"] = x0
        elif "cognome" in label or "surname" in label or "last" in label:
            columns["surname"] = x0
        elif label in {"nome", "name", "first"} or "competitor" in label or "athlete" in label:
            columns["given"] = x0
        elif "nation" in label or "country" in label or "noc" in label or (
            label.startswith("na") and ("ione" in label or "one" in label)
        ):
            columns["country"] = x0
        elif "medal" in label:
            columns["medal"] = x0
    return columns


def _nearest_column(x0, columns):
    ordered = sorted((x, name) for name, x in columns.items())
    selected = None
    for x, name in ordered:
        if x0 + 3 >= x:
            selected = name
        else:
            break
    return selected


def _country_from_tokens(tokens):
    for token in tokens:
        value = _ascii(token).upper()
        if re.fullmatch(r"[A-Z]{2,3}", value):
            return value
    return None


def parse_pdf_page_words(words, edition_id, edition_name=None, source_url=None):
    """Parse one extractable PDF page represented by pdfplumber extract_words()."""
    if not words:
        return None

    event_name = _pdf_event_name(words)
    classification = classify_event(event_name)
    if not classification["weapon"] or not classification["gender"] or not classification["age_category"]:
        return None

    word_rows = _group_words_by_top(words)
    header_index = None
    columns = {}
    for i, row in enumerate(word_rows):
        maybe_columns = _pdf_header_columns(row)
        if "rank" in maybe_columns and ("surname" in maybe_columns or "given" in maybe_columns):
            header_index = i
            columns = maybe_columns
            break
    if header_index is None:
        return None

    rows = []
    for row in word_rows[header_index + 1:]:
        buckets: dict[str, list[str]] = {name: [] for name in columns}
        for word in row:
            token = _clean_pdf_token(word.get("text", ""))
            if not token:
                continue
            column = _nearest_column(float(word.get("x0", 0)), columns)
            if column:
                buckets.setdefault(column, []).append(token)

        rank_tokens = buckets.get("rank", [])
        rank = _parse_rank(rank_tokens[0]) if rank_tokens else None
        if rank is None:
            continue

        surname = _squash_spaces(" ".join(buckets.get("surname", [])))
        given = _squash_spaces(" ".join(buckets.get("given", [])))
        name = _squash_spaces(f"{surname} {given}") or _squash_spaces(" ".join(buckets.get("name", [])))
        if not name:
            continue

        country = _country_from_tokens(buckets.get("country", []))
        medal_text = " ".join(buckets.get("medal", []))
        rows.append({
            "rank": rank,
            "name": name,
            "country": country,
            "medal": _parse_medal(medal_text, rank),
            "weapon": classification["weapon"],
            "gender": classification["gender"],
            "age_category": classification["age_category"],
        })

    if not rows:
        return None
    return _event_from_parts(edition_id, edition_name, event_name, rows, source_url)


def parse_pdf_results(content, edition_id, edition_name=None, source_url=None):
    events = []
    pages_with_words = 0
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            words = page.extract_words() or []
            if words:
                pages_with_words += 1
            event = parse_pdf_page_words(words, edition_id, edition_name, source_url)
            if event:
                events.append(event)
    if not pages_with_words:
        print(f"  Warning: no extractable text in PDF {source_url or edition_id}; skipping image-only source")
    return events


def _get(url, retries=3, binary=False):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.content if binary else r.text
            if r.status_code == 404:
                return None
            print(f"  HTTP {r.status_code} for {url}")
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def infer_edition_id(url, text=""):
    filename = os.path.basename(urlparse(url).path)
    for raw in (f"{filename} {text}", f"{url} {text}"):
        m = re.search(r"\b(WMG|World-Masters-Games)[-_ ]*(\d{4})\b", raw, re.I)
        if m:
            return f"wmg-{m.group(2)}"
        m = re.search(r"\b(EMG|European-Masters-Games)[-_ ]*(\d{4})\b", raw, re.I)
        if m:
            return f"emg-{m.group(2)}"
        m = re.search(r"\b(19|20)\d{2}\b", raw)
        if m:
            return f"masters-{m.group(0)}"
    return "masters-unknown"


def discover_imga_sources():
    html = _get(IMGA_RESULTS_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    sources = []
    seen = set()
    for link in soup.find_all("a", href=True):
        href = urljoin(IMGA_RESULTS_URL, link["href"])
        label = _squash_spaces(link.get_text(" ", strip=True))
        if href in seen:
            continue
        if "fenc" not in f"{href} {label}".lower() or not href.lower().endswith(".pdf"):
            continue
        seen.add(href)
        edition_id = infer_edition_id(href, label)
        sources.append({
            "url": href,
            "format": "pdf",
            "edition_id": edition_id,
            "edition_name": edition_id.upper(),
        })
    return sources


def fetch_source_events(source):
    if source["format"] == "pdf":
        content = _get(source["url"], binary=True)
        if not content:
            return []
        return parse_pdf_results(
            content,
            edition_id=source["edition_id"],
            edition_name=source.get("edition_name"),
            source_url=source["url"],
        )
    html = _get(source["url"])
    if not html:
        return []
    return parse_html_results_page(
        html,
        edition_id=source["edition_id"],
        edition_name=source.get("edition_name"),
        source_url=source["url"],
    )


def _extract_year(edition_name):
    m = re.search(r"\b(19|20)\d{2}\b", edition_name or "")
    return m.group(0) if m else None


def upsert_tournament(event):
    row = {
        "source_id": event["source_id"],
        "name": f"{event.get('edition_name') or event['edition_id']} - {event['event_name']}",
        "season": _extract_year(event.get("edition_name")) or _extract_year(event["edition_id"]),
        "type": "masters_games",
        "weapon": event["weapon"],
        "gender": event["gender"],
        "category": event["age_category"],
        "country": None,
        "has_results": True,
        "metadata": {
            "edition_id": event["edition_id"],
            "edition_name": event.get("edition_name"),
            "event_name": event["event_name"],
            "event_code": event["event_code"],
            "age_category": event["age_category"],
            "team": event["team"],
            "source_url": event.get("source_url"),
        },
    }
    try:
        result = _db().table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def _match_fencer(name, country):
    if not name or not country:
        return None
    try:
        rows = _db().table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(2).execute().data
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_results(tournament_id, event):
    db_rows = []
    for row in event["rows"]:
        if row["rank"] is None:
            continue
        fencer_id = _match_fencer(row["name"], row["country"])
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row["name"],
            "nationality": row["country"],
            "rank": row["rank"],
            "medal": row["medal"],
            "fencer_id": fencer_id,
            "metadata": {
                "weapon": row["weapon"],
                "gender": row["gender"],
                "age_category": row["age_category"],
                "source_id": event["source_id"],
            },
        })
    if not db_rows:
        return 0

    _db().table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            _db().table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_masters_games").start()
    try:
        print(f"Masters Games scraper starting - {datetime.now(timezone.utc).isoformat()}")
        done_ids = set(get_state(SOURCE, "done_event_ids") or [])
        sources = discover_imga_sources()
        print(f"  {len(sources)} IMGA fencing sources found")

        written = failed = skipped = 0
        for source in sources:
            events = fetch_source_events(source)
            if not events:
                skipped += 1
                time.sleep(REQUEST_DELAY)
                continue

            for event in events:
                if event["source_id"] in done_ids:
                    skipped += 1
                    continue

                if not event["weapon"] or not event["gender"] or not event["age_category"]:
                    print(f"  Skipping unclassifiable event: {event['event_name']}")
                    skipped += 1
                    continue

                tournament_id = upsert_tournament(event)
                if not tournament_id:
                    failed += 1
                    continue

                count = upsert_results(tournament_id, event)
                if count == 0:
                    failed += 1
                    continue

                done_ids.add(event["source_id"])
                set_state(SOURCE, "done_event_ids", sorted(done_ids))
                written += 1
                print(f"  {event['event_name']}: {count} results inserted")
                time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
