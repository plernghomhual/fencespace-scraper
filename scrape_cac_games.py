"""
Central American & Caribbean Games fencing results scraper.

Probe summary (2026-06-01):
  * Olympedia has CAC Games references in athlete/list text, but no structured
    CAC fencing result pages under the probed results, organization, or sport pages.
  * 2018 Barranquilla official archive PDFs expose parseable individual final
    standings (C76) and team medalist lists (C92B).
  * 2014 Veracruz official PDFs are bracket-style only; 2023 official S3 PDFs
    returned AccessDenied during probe; earlier public archives are not structured
    enough for safe per-event import.
"""
import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "cac_games"
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "application/pdf,text/html,*/*;q=0.8",
}

MEDAL_MAP = {
    "gold": "Gold",
    "oro": "Gold",
    "silver": "Silver",
    "plata": "Silver",
    "bronze": "Bronze",
    "bronce": "Bronze",
}
MEDAL_RANK = {"Gold": 1, "Silver": 2, "Bronze": 3}

COUNTRY_NAMES = {
    "AHO": ("Netherlands Antilles", "Antillas Neerlandesas"),
    "BAR": ("Barbados",),
    "BAH": ("Bahamas",),
    "CCS": ("Centro Caribe Sports",),
    "COL": ("Colombia",),
    "CRC": ("Costa Rica",),
    "CUB": ("Cuba",),
    "DOM": ("Dominican Republic", "República Dominicana", "Republica Dominicana"),
    "ESA": ("El Salvador",),
    "GUA": ("Guatemala",),
    "JAM": ("Jamaica",),
    "MEX": ("Mexico", "México"),
    "NCA": ("Nicaragua",),
    "PAN": ("Panama", "Panamá"),
    "PUR": ("Puerto Rico",),
    "VEN": ("Venezuela",),
}


def _event(event_code, event_name, parser, url, skip_reason=None):
    return {
        "event_code": event_code,
        "event_name": event_name,
        "parser": parser,
        "result_url": url,
        **({"skip_reason": skip_reason} if skip_reason else {}),
    }


ARCHIVE_2018 = "https://web.archive.org/web"
BA2018 = "http://resultados.elheraldo.co/resBA2018/pdf/BA2018/FE"

CAC_GAMES_ARCHIVES = [
    {
        "edition_id": str(year),
        "edition_name": name,
        "skip_reason": "No structured public per-event fencing result archive found.",
    }
    for year, name in [
        (1938, "Panama City 1938"),
        (1946, "Barranquilla 1946"),
        (1950, "Guatemala City 1950"),
        (1954, "Mexico City 1954"),
        (1959, "Caracas 1959"),
        (1962, "Kingston 1962"),
        (1966, "San Juan 1966"),
        (1970, "Panama City 1970"),
        (1974, "Santo Domingo 1974"),
        (1978, "Medellin 1978"),
        (1982, "Havana 1982"),
        (1986, "Santiago de los Caballeros 1986"),
        (1990, "Mexico City 1990"),
        (1993, "Ponce 1993"),
        (1998, "Maracaibo 1998"),
        (2002, "San Salvador 2002"),
        (2006, "Cartagena de Indias 2006"),
        (2010, "Mayaguez 2010"),
    ]
] + [
    {
        "edition_id": "2014",
        "edition_name": "Veracruz 2014",
        "skip_reason": "Official PDFs are bracket-style and lack reliable final standings tables.",
    },
    {
        "edition_id": "2018",
        "edition_name": "Barranquilla 2018",
        "events": [
            _event(
                "FEM002000",
                "ESPADA INDIVIDUAL MASCULINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180730212832/{BA2018}/BA2018_FE_C76_FEM002000.pdf",
            ),
            _event(
                "FEM001000",
                "FLORETE INDIVIDUAL MASCULINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180805083208/{BA2018}/BA2018_FE_C76_FEM001000.pdf",
            ),
            _event(
                "FEM003000",
                "SABLE INDIVIDUAL MASCULINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180730212714/{BA2018}/BA2018_FE_C76_FEM003000.pdf",
            ),
            _event(
                "FEM402000",
                "ESPADA EQUIPO MASCULINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805083313/{BA2018}/BA2018_FE_C92B_FEM402000.pdf",
            ),
            _event(
                "FEM401000",
                "FLORETE EQUIPO MASCULINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805083042/{BA2018}/BA2018_FE_C92B_FEM401000.pdf",
            ),
            _event(
                "FEM403000",
                "SABLE EQUIPO MASCULINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805083201/{BA2018}/BA2018_FE_C92B_FEM403000.pdf",
            ),
            _event(
                "FEW002000",
                "ESPADA INDIVIDUAL FEMENINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180730212550/{BA2018}/BA2018_FE_C76_FEW002000.pdf",
            ),
            _event(
                "FEW001000",
                "FLORETE INDIVIDUAL FEMENINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180730212823/{BA2018}/BA2018_FE_C76_FEW001000.pdf",
            ),
            _event(
                "FEW003000",
                "SABLE INDIVIDUAL FEMENINO",
                "individual_standings_pdf",
                f"{ARCHIVE_2018}/20180805083300/{BA2018}/BA2018_FE_C76_FEW003000.pdf",
            ),
            _event(
                "FEW402000",
                "ESPADA EQUIPO FEMENINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805083029/{BA2018}/BA2018_FE_C92B_FEW402000.pdf",
            ),
            _event(
                "FEW401000",
                "FLORETE EQUIPO FEMENINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805083311/{BA2018}/BA2018_FE_C92B_FEW401000.pdf",
            ),
            _event(
                "FEW403000",
                "SABLE EQUIPO FEMENINO",
                "team_medalists_pdf",
                f"{ARCHIVE_2018}/20180805082938/{BA2018}/BA2018_FE_C92B_FEW403000.pdf",
            ),
        ],
    },
    {
        "edition_id": "2023",
        "edition_name": "San Salvador 2023",
        "skip_reason": "Official S3 result PDFs returned AccessDenied during probe.",
    },
]


def _normalize_text(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def classify_event(event_name):
    """Return {weapon, gender, team} for English or Spanish CAC event labels."""
    label = _normalize_text(event_name)
    weapon = None
    if re.search(r"\b(epee|epée|espada)\b", label):
        weapon = "Epee"
    elif re.search(r"\b(foil|florete)\b", label):
        weapon = "Foil"
    elif re.search(r"\b(sabre|saber|sable)\b", label):
        weapon = "Sabre"

    gender = None
    if re.search(r"\b(women|womens|female|femenino|femenil|mujeres|damas)\b", label):
        gender = "Women"
    elif re.search(r"\b(men|mens|male|masculino|varonil|hombres)\b", label):
        gender = "Men"

    team = bool(re.search(r"\b(team|equipo|equipos)\b", label))
    return {"weapon": weapon, "gender": gender, "team": team}


def _source_id(edition_id, event_code):
    return f"cac_games:{edition_id}:{event_code}"


def wayback_raw_url(url):
    """Convert a Wayback wrapper URL to the raw archived resource URL."""
    return re.sub(
        r"^(https://web\.archive\.org/web/\d+)(/https?://)",
        r"\1id_\2",
        url,
    )


def discover_events_from_manifest(manifest=None):
    """Return (events, skipped_editions) from the static probed archive manifest."""
    events = []
    skipped = []
    for edition in manifest or CAC_GAMES_ARCHIVES:
        if edition.get("skip_reason"):
            skipped.append({
                "edition_id": edition["edition_id"],
                "edition_name": edition["edition_name"],
                "reason": edition["skip_reason"],
            })
            continue
        for event in edition.get("events", []):
            item = {
                "edition_id": edition["edition_id"],
                "edition_name": edition["edition_name"],
                "event_code": event["event_code"],
                "event_name": event["event_name"],
                "result_url": event["result_url"],
                "parser": event["parser"],
                "source_id": _source_id(edition["edition_id"], event["event_code"]),
            }
            if event.get("skip_reason"):
                item["skip_reason"] = event["skip_reason"]
            events.append(item)
    return events, skipped


def _normalise_medal(raw):
    return MEDAL_MAP.get(_normalize_text(raw))


def parse_individual_standings_text(text):
    """Parse official C76 final standings text into placement rows."""
    rows = []
    line_re = re.compile(
        r"^(?P<rank>\d{1,2})\s+"
        r"(?P<name>.+?)\s+"
        r"(?P<country>[A-Z]{3})\s+-\s+"
        r"(?P<country_name>.+?)"
        r"(?:\s+(?P<medal>Gold|Silver|Bronze|GOLD|SILVER|BRONZE|Oro|Plata|Bronce))?$",
        re.I,
    )
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        match = line_re.match(line)
        if not match:
            continue
        medal = _normalise_medal(match.group("medal") or "")
        rows.append({
            "rank": int(match.group("rank")),
            "name": match.group("name").strip(),
            "country": match.group("country"),
            "medal": medal,
        })
    return rows


def _canonical_country_name(code, raw_name):
    aliases = COUNTRY_NAMES.get(code, ())
    if aliases:
        return aliases[0]
    return re.sub(r"\s+", " ", raw_name).strip()


def _split_country_and_roster(code, text):
    text = re.sub(r"\s+", " ", text).strip()
    for alias in sorted(COUNTRY_NAMES.get(code, ()), key=len, reverse=True):
        if _normalize_text(text).startswith(_normalize_text(alias)):
            first_roster = text[len(alias):].strip()
            return _canonical_country_name(code, alias), first_roster
    parts = text.split()
    if len(parts) >= 3:
        return parts[0], " ".join(parts[1:])
    return text, ""


def _is_team_footer_or_heading(line):
    normalized = _normalize_text(line)
    return (
        not normalized
        or normalized in {
            "esgrima",
            "fencing",
            "medallistas - equipos",
            "medallists",
            "medalla con nombre",
        }
        or "pagina" in normalized
        or "_c92" in normalized
        or normalized.startswith(("men's ", "women's "))
        or normalized.startswith(("espada equipo", "florete equipo", "sable equipo"))
        or re.match(r"^[a-z]{3}\s+\d+\s+[a-z]{3}\s+\d{4}$", normalized)
    )


def parse_team_medalists_text(text):
    """Parse official C92B team medalist text into one row per medal team."""
    rows = []
    current = None
    medal_re = re.compile(
        r"^(?P<medal>GOLD|SILVER|BRONZE|Gold|Silver|Bronze|ORO|PLATA|BRONCE|Oro|Plata|Bronce)\s+"
        r"(?P<country>[A-Z]{3})\s+-\s+(?P<rest>.+)$"
    )

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        match = medal_re.match(line)
        if match:
            medal = _normalise_medal(match.group("medal"))
            country = match.group("country")
            team_name, first_roster = _split_country_and_roster(country, match.group("rest"))
            current = {
                "rank": MEDAL_RANK[medal],
                "name": team_name,
                "country": country,
                "medal": medal,
                "metadata": {"roster": []},
            }
            if first_roster:
                current["metadata"]["roster"].append(first_roster)
            rows.append(current)
            continue

        if current and not _is_team_footer_or_heading(line):
            current["metadata"]["roster"].append(line)

    return rows


def _extract_pdf_text(content):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse CAC Games PDFs") from exc

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def fetch_pdf_text(url, retries=3):
    url = wayback_raw_url(url)
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200 and response.content.startswith(b"%PDF"):
                return _extract_pdf_text(response.content), None
            if response.status_code == 404:
                return None, "HTTP 404"
            reason = f"HTTP {response.status_code}"
            if b"AccessDenied" in response.content[:500]:
                reason = "HTTP 403 AccessDenied"
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            return None, reason
        except Exception as exc:
            if attempt == retries - 1:
                return None, str(exc)
            time.sleep(2 ** attempt)
    return None, "fetch retries exhausted"


def parse_event_results(event, text):
    if event["parser"] == "individual_standings_pdf":
        return parse_individual_standings_text(text)
    if event["parser"] == "team_medalists_pdf":
        return parse_team_medalists_text(text)
    return []


def upsert_tournament(event, classification):
    row = {
        "source_id": event["source_id"],
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": event["edition_id"],
        "type": "cac_games",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_code": event["event_code"],
            "event_name": event["event_name"],
            "team": classification["team"],
            "source_url": event["result_url"],
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def _match_fencer(name, country):
    try:
        rows = (
            supabase.table("fs_fencers")
            .select("id")
            .ilike("name", name)
            .eq("country", country)
            .limit(2)
            .execute()
            .data
        )
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_results(tournament_id, result_rows, team=False):
    db_rows = []
    for row in result_rows:
        if row.get("rank") is None:
            continue
        fencer_id = None if team else _match_fencer(row["name"], row["country"])
        metadata = dict(row.get("metadata") or {})
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row["name"],
            "nationality": row["country"],
            "rank": row["rank"],
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": metadata,
        })
    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_cac_games").start()
    try:
        print(f"CAC Games scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        events, skipped_editions = discover_events_from_manifest()

        for skipped in skipped_editions:
            print(f"  Skipping edition {skipped['edition_id']}: {skipped['reason']}")

        written = failed = skipped = 0
        for event in events:
            source_id = event["source_id"]
            if source_id in done_source_ids:
                skipped += 1
                continue
            if event.get("skip_reason"):
                print(f"  Skipping {source_id}: {event['skip_reason']}")
                skipped += 1
                continue

            classification = classify_event(event["event_name"])
            if not classification["weapon"] or not classification["gender"]:
                print(f"  Skipping {source_id}: unclassifiable label {event['event_name']!r}")
                skipped += 1
                continue

            print(f"  Fetching {event['edition_name']} — {event['event_name']}")
            text, fetch_error = fetch_pdf_text(event["result_url"])
            if not text:
                print(f"    Skipping {source_id}: {fetch_error or 'no PDF text'}")
                skipped += 1
                time.sleep(REQUEST_DELAY)
                continue

            result_rows = parse_event_results(event, text)
            if not result_rows:
                print(f"    Skipping {source_id}: no parseable result rows")
                skipped += 1
                time.sleep(REQUEST_DELAY)
                continue

            tournament_id = upsert_tournament(event, classification)
            if not tournament_id:
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            n = upsert_results(tournament_id, result_rows, team=classification["team"])
            if n == 0:
                print(f"    Insert failed or partial — skipping done mark")
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            print(f"    {n} results inserted")
            done_source_ids.add(source_id)
            set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            written += 1
            time.sleep(REQUEST_DELAY)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        set_state(SOURCE, "skipped_editions", skipped_editions)
        run_log.complete(written=written, failed=failed, skipped=skipped + len(skipped_editions))
        print(f"\nDone — written={written}, skipped={skipped + len(skipped_editions)}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
