import io
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FIE_BASE = "https://fie.org"
SOURCE = "scrape_competition_details"
PAGE_SIZE = 1000
REQUEST_DELAY = float(os.environ.get("COMPETITION_DETAILS_DELAY", "0.3"))
DEFAULT_LIMIT = int(os.environ.get("COMPETITION_DETAILS_LIMIT", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fie.org/competitions",
}

MONEY_RE = re.compile(
    r"(?:(?P<code_before>EUR|USD|GBP|CHF|JPY|CAD|AUD|CNY|RMB)\s*)?"
    r"(?P<symbol>[€$£¥])?\s*"
    r"(?P<amount>\d[\d ,.]*\d|\d)"
    r"\s*(?P<code_after>EUR|USD|GBP|CHF|JPY|CAD|AUD|CNY|RMB)?",
    re.IGNORECASE,
)

SYMBOL_CURRENCY = {"€": "EUR", "$": "USD", "£": "GBP", "¥": "JPY"}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def extract_window_var(html: str, var_name: str) -> Any:
    """Extract a JSON window variable from FIE HTML."""
    match = re.search(rf"window\.{re.escape(var_name)}\s*=\s*", html)
    if not match:
        return None
    offset = match.end()
    while offset < len(html) and html[offset].isspace():
        offset += 1
    if offset >= len(html) or html[offset] not in "[{":
        return None
    try:
        result, _ = json.JSONDecoder().raw_decode(html[offset:])
        return result
    except json.JSONDecodeError:
        return None


def extract_window_blocks(html: str) -> dict[str, Any]:
    names = {
        "_competition",
        "_athletes",
        "_pools",
        "_poolsResults",
        "_tableau",
        "_downloadLinks",
    }
    return {name: extract_window_var(html, name) for name in names}


def parse_number(value: str) -> float | None:
    text = re.sub(r"[^\d,.\-]", "", value or "").strip(".,")
    if not text or text == "-":
        return None
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_currency(code_before: str | None, symbol: str | None, code_after: str | None) -> str | None:
    code = code_before or code_after
    if code:
        code = code.upper()
        return "CNY" if code == "RMB" else code
    return SYMBOL_CURRENCY.get(symbol or "")


def money_values(text: str) -> list[tuple[str | None, float]]:
    values: list[tuple[str | None, float]] = []
    for match in MONEY_RE.finditer(text or ""):
        amount = parse_number(match.group("amount"))
        if amount is None:
            continue
        currency = normalize_currency(
            match.group("code_before"),
            match.group("symbol"),
            match.group("code_after"),
        )
        if currency is None and amount < 10:
            continue
        values.append((currency, amount))
    return values


def first_currency(*groups: list[tuple[str | None, float]]) -> str | None:
    for group in groups:
        for currency, _amount in group:
            if currency:
                return currency
    return None


def extract_entry_fee(text: str, competition_type: str | None = None) -> tuple[str | None, float | None]:
    lines = [line.strip() for line in (text or "").splitlines()]
    candidates: list[tuple[str | None, float, int]] = []
    target = (competition_type or "").casefold()

    for line in lines:
        lower = line.casefold()
        if "prize" in lower:
            continue
        if not (
            "entry fee" in lower
            or "entry fees" in lower
            or "registration fee" in lower
            or "individual competition" in lower
            or "team competition" in lower
        ):
            continue
        amounts = money_values(line)
        for currency, amount in amounts:
            priority = 2
            if "individual" in target and "individual competition" in lower:
                priority = 0
            elif "team" in target and "team competition" in lower:
                priority = 0
            elif "entry" in lower or "registration" in lower:
                priority = 1
            candidates.append((currency, amount, priority))

    if not candidates:
        return None, None

    currency, amount, _priority = sorted(candidates, key=lambda item: (item[2], item[1]))[0]
    return currency, amount


def prize_text_blocks(text: str) -> list[str]:
    lines = [line.strip() for line in (text or "").splitlines()]
    blocks: list[str] = []
    stop_re = re.compile(
        r"\b(entry|registration|bank|account|accommodation|hotel|visa|schedule|weapon control|organizer|venue)\b",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):
        if not re.search(r"\b(prize|prizes|award money|prize money)\b", line, re.IGNORECASE):
            continue
        block = [line]
        for next_line in lines[index + 1 : index + 12]:
            if not next_line:
                if len(block) > 1:
                    break
                continue
            if stop_re.search(next_line):
                break
            block.append(next_line)
        blocks.append("\n".join(block))
    return blocks


def extract_prize_pool(text: str) -> tuple[str | None, float | None, list[float]]:
    amounts: list[tuple[str | None, float]] = []
    for block in prize_text_blocks(text):
        amounts.extend(money_values(block))
    if not amounts:
        return None, None, []
    currency = first_currency(amounts)
    values = [amount for _currency, amount in amounts]
    return currency, sum(values), values


def extract_money_from_documents(
    document_texts: list[str] | None,
    competition_type: str | None = None,
) -> tuple[str | None, float | None, float | None, dict[str, Any]]:
    combined = "\n".join(text for text in (document_texts or []) if text)
    entry_currency, entry_fee = extract_entry_fee(combined, competition_type)
    prize_currency, prize_pool, prize_amounts = extract_prize_pool(combined)
    currency = prize_currency or entry_currency
    metadata = {
        "prize_amounts": prize_amounts,
    }
    return currency, entry_fee, prize_pool, metadata


def pool_rows(pool: dict[str, Any]) -> list[Any]:
    for key in ("rows", "fencers", "athletes"):
        rows = pool.get(key)
        if isinstance(rows, list):
            return rows
    return []


def extract_pools(pools_block: Any) -> list[dict[str, Any]]:
    if isinstance(pools_block, dict):
        pools = pools_block.get("pools")
    else:
        pools = pools_block
    if not isinstance(pools, list):
        return []
    return [pool for pool in pools if isinstance(pool, dict)]


def infer_pool_size(pool_sizes: list[int]) -> int | None:
    usable = [size for size in pool_sizes if size > 0]
    if not usable:
        return None
    counts = Counter(usable)
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def round_sort_key(name: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", name)
    number = int(match.group(1)) if match else 0
    return (-number, name)


def extract_de_rounds(tableau_block: Any) -> list[str]:
    round_names: set[str] = set()
    suites = tableau_block if isinstance(tableau_block, list) else [tableau_block]
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        rounds = suite.get("rounds")
        if isinstance(rounds, dict):
            round_names.update(str(name) for name in rounds.keys())
    return sorted(round_names, key=round_sort_key)


def athlete_country(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    fencer = entry.get("fencer") if isinstance(entry.get("fencer"), dict) else {}
    return clean_text(
        entry.get("nationality")
        or entry.get("country")
        or fencer.get("nationality")
        or fencer.get("country")
    )


def count_countries(athletes_block: Any) -> int | None:
    if not isinstance(athletes_block, list) or not athletes_block:
        return None
    countries = {country for country in (athlete_country(entry) for entry in athletes_block) if country}
    return len(countries) or None


def extract_participant_count(competition: dict[str, Any], athletes_block: Any) -> int | None:
    for key in ("fencerCount", "teamCount", "athleteCount", "participantCount"):
        count = coerce_int(competition.get(key))
        if count is not None:
            return count
    if isinstance(athletes_block, list) and athletes_block:
        return len(athletes_block)
    return None


def infer_format_type(competition: dict[str, Any], pool_count: int, round_names: list[str]) -> str | None:
    for key in ("format", "formula", "competitionFormula"):
        value = clean_text(competition.get(key))
        if value:
            return value
    has_pools = pool_count > 0
    has_de = bool(round_names)
    if has_pools and has_de:
        return "pools + direct elimination"
    if has_pools:
        return "pools"
    if has_de:
        return "direct elimination"
    return None


def make_absolute_url(url: str) -> str:
    return urljoin(FIE_BASE, url)


def extract_document_urls(blocks: dict[str, Any]) -> list[str]:
    competition = blocks.get("_competition") if isinstance(blocks.get("_competition"), dict) else {}
    urls: list[str] = []
    for key, value in competition.items():
        if not isinstance(value, str) or not value.strip():
            continue
        key_lower = key.casefold()
        if not (
            "invitation" in key_lower
            or "regulation" in key_lower
            or "program" in key_lower
            or "document" in key_lower
            or "manual" in key_lower
        ):
            continue
        url = make_absolute_url(value.strip())
        if url.lower().split("?", 1)[0].endswith(".pdf") or "static.fie.org" in url:
            urls.append(url)
    return list(dict.fromkeys(urls))


def parse_competition_detail_page(
    html: str,
    tournament_id: str | None = None,
    source_url: str | None = None,
    document_texts: list[str] | None = None,
) -> dict[str, Any]:
    blocks = extract_window_blocks(html)
    competition = blocks.get("_competition") if isinstance(blocks.get("_competition"), dict) else {}
    athletes = blocks.get("_athletes")
    pools = extract_pools(blocks.get("_pools"))
    pool_sizes = [len(pool_rows(pool)) for pool in pools if pool_rows(pool)]
    round_names = extract_de_rounds(blocks.get("_tableau"))
    document_urls = extract_document_urls(blocks)

    competition_type = clean_text(competition.get("type"))
    currency, entry_fee, prize_pool, money_meta = extract_money_from_documents(
        document_texts,
        competition_type=competition_type,
    )

    metadata = {
        "scraped_by": SOURCE,
        "source_url": source_url,
        "competition_id": competition.get("competitionId") or competition.get("id"),
        "competition_name": competition.get("name"),
        "competition_type": competition_type,
        "pool_count": len(pools),
        "pool_sizes": pool_sizes,
        "de_round_names": round_names,
        "document_urls": document_urls,
        **money_meta,
    }

    return {
        "tournament_id": tournament_id,
        "format_type": infer_format_type(competition, len(pools), round_names),
        "pool_size": infer_pool_size(pool_sizes),
        "de_rounds": len(round_names) or None,
        "entry_fee": entry_fee,
        "prize_pool": prize_pool,
        "currency": currency,
        "participant_count": extract_participant_count(competition, athletes),
        "countries_represented": count_countries(athletes),
        "metadata": metadata,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_detail_html(season: int, competition_url_id: Any) -> str | None:
    url = f"{FIE_BASE}/competitions/{season}/{competition_url_id}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code != 200:
        print(f"  Detail fetch HTTP {response.status_code}: {url}")
        return None
    return response.text


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def fetch_document_texts(urls: list[str]) -> list[str]:
    texts: list[str] = []
    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code != 200:
                print(f"  Document fetch HTTP {response.status_code}: {url}")
                continue
            content_type = response.headers.get("content-type", "").casefold()
            if "pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf"):
                texts.append(extract_pdf_text(response.content))
            else:
                texts.append(response.text)
        except Exception as exc:
            print(f"  Document fetch failed: {url}: {exc}")
    return texts


def fetch_all(client, table: str, select_columns: str, configure: Callable[[Any], Any] | None = None) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = client.table(table).select(select_columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def find_tournaments_needing_details(client, limit: int | None = None) -> list[dict]:
    existing_rows = fetch_all(client, "fs_competition_details", "tournament_id")
    existing_ids = {str(row["tournament_id"]) for row in existing_rows if row.get("tournament_id")}

    tournaments = fetch_all(
        client,
        "fs_tournaments",
        "id,fie_id,competition_url_id,season,name",
        configure=lambda query: query.not_.is_("fie_id", "null"),
    )
    pending = [row for row in tournaments if row.get("id") and str(row["id"]) not in existing_ids]
    if limit:
        return pending[:limit]
    return pending


def normalize_season(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return datetime.now(timezone.utc).year
    try:
        return int(float(text))
    except ValueError:
        years = re.findall(r"\d{4}", text)
        if years:
            return int(years[-1])
    return datetime.now(timezone.utc).year


def detail_url(season: int, competition_url_id: Any) -> str:
    return f"{FIE_BASE}/competitions/{season}/{competition_url_id}"


def upsert_competition_detail(client, row: dict[str, Any]) -> int:
    client.table("fs_competition_details").upsert(row, on_conflict="tournament_id").execute()
    return 1


def scrape_competition_details(
    client=None,
    limit: int | None = None,
    fetch_html: Callable[[int, Any], str | None] | None = None,
    fetch_document_texts: Callable[[list[str]], list[str]] | None = None,
    log_run: bool = True,
    update_state: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    client = client or get_supabase_client()
    fetch_html = fetch_html or fetch_detail_html
    fetch_document_texts = fetch_document_texts or globals()["fetch_document_texts"]
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    failure_counts = get_state(SOURCE, "failure_counts") if update_state else {}
    if not isinstance(failure_counts, dict):
        failure_counts = {}

    written = failed = skipped = processed = 0
    try:
        tournaments = find_tournaments_needing_details(client, limit=limit)
        for tournament in tournaments:
            tournament_id = tournament.get("id")
            url_id = tournament.get("competition_url_id") or tournament.get("fie_id")
            if not tournament_id or not url_id:
                skipped += 1
                continue

            season = normalize_season(tournament.get("season"))
            source_url = detail_url(season, url_id)
            processed += 1
            try:
                html = fetch_html(season, url_id)
                if not html:
                    raise RuntimeError(f"No FIE detail HTML returned for {source_url}")
                blocks = extract_window_blocks(html)
                document_urls = extract_document_urls(blocks)
                documents = fetch_document_texts(document_urls) if document_urls else []
                row = parse_competition_detail_page(
                    html,
                    tournament_id=tournament_id,
                    source_url=source_url,
                    document_texts=documents,
                )
                upsert_competition_detail(client, row)
                written += 1
                failure_counts.pop(str(tournament_id), None)
            except Exception as exc:
                failed += 1
                key = str(tournament_id)
                failure_counts[key] = int(failure_counts.get(key, 0)) + 1
                print(f"  Failed {tournament.get('name') or tournament_id}: {exc}")
            sleep(REQUEST_DELAY)

        if update_state:
            set_state(SOURCE, "failure_counts", failure_counts)
            set_state(
                SOURCE,
                "last_summary",
                {
                    "processed": processed,
                    "written": written,
                    "failed": failed,
                    "skipped": skipped,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped)
        return {"processed": processed, "written": written, "failed": failed, "skipped": skipped}
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main(limit: int | None = None) -> None:
    effective_limit = DEFAULT_LIMIT if limit is None else limit
    summary = scrape_competition_details(limit=effective_limit or None)
    print(
        "Competition details complete - "
        f"processed={summary['processed']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()
