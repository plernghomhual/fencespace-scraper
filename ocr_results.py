from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from run_logger import ScraperRunLogger
from scraper_state import set_state


SOURCE = "ocr_results"
DEFAULT_BATCH_SIZE = 100

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


OcrFunction = Callable[[Any, int], str]


@dataclass
class PDFExtractionConfig:
    source_name: str = SOURCE
    ocr_enabled: bool = False
    ocr_func: OcrFunction | None = None
    low_confidence_threshold: float = 0.75
    min_text_chars: int = 5
    batch_size: int = DEFAULT_BATCH_SIZE


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    tables: list[list[list[Any]]] = field(default_factory=list)
    rotation: int = 0
    method: str = "pdfplumber"
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ResultCandidate:
    rank: int | None
    name: str
    country: str | None = None
    club: str | None = None
    medal: str | None = None
    page_number: int | None = None
    raw_text: str = ""
    confidence: float = 1.0
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class EventCandidate:
    tournament_name: str
    event_name: str
    source_id: str
    weapon: str | None = None
    gender: str | None = None
    category: str | None = None
    team: bool = False
    page_number: int | None = None
    results: list[ResultCandidate] = field(default_factory=list)
    confidence: float = 1.0
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class ManualReviewItem:
    kind: str
    reason: str
    page_number: int | None = None
    tournament_name: str | None = None
    event_name: str | None = None
    raw_text: str = ""
    confidence: float = 0.0


@dataclass
class ExtractionError:
    reason: str
    source_name: str


@dataclass
class PipelineResult:
    pages: list[ExtractedPage] = field(default_factory=list)
    events: list[EventCandidate] = field(default_factory=list)
    manual_review: list[ManualReviewItem] = field(default_factory=list)
    errors: list[ExtractionError] = field(default_factory=list)
    dry_run: bool = True
    written: int = 0
    failed: int = 0
    skipped: int = 0


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize_key(value)).strip("-")
    return slug or "unknown"


def _medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _read_pdf_bytes(source: bytes | bytearray | str | Path | Any) -> tuple[bytes, str]:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), "bytes"
    if isinstance(source, (str, Path)):
        path = Path(source)
        return path.read_bytes(), str(path)
    if hasattr(source, "read"):
        data = source.read()
        return bytes(data), getattr(source, "name", "file-like")
    raise TypeError("PDF source must be bytes, a path, or a binary file-like object.")


def _reconstruct_rotated_text(page: Any, rotation: int) -> str:
    try:
        words = page.extract_words() or []
    except Exception:
        return ""
    if not words:
        return ""

    groups: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: float(item.get("x0", 0.0))):
        x0 = float(word.get("x0", 0.0))
        for group in groups:
            group_x = sum(float(item.get("x0", 0.0)) for item in group) / len(group)
            if abs(group_x - x0) <= 3:
                group.append(word)
                break
        else:
            groups.append([word])

    reverse = rotation % 360 == 90
    lines = []
    for group in sorted(groups, key=lambda items: sum(float(item.get("x0", 0.0)) for item in items) / len(items), reverse=reverse):
        ordered = sorted(group, key=lambda item: float(item.get("top", 0.0)))
        line = " ".join(_clean_text(item.get("text")) for item in ordered if _clean_text(item.get("text")))
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_text_from_page(page: Any, rotation: int = 0) -> str:
    if rotation % 360 in {90, 270}:
        rotated_text = _reconstruct_rotated_text(page, rotation)
        if _clean_text(rotated_text):
            return rotated_text

    text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
    if _clean_text(text):
        return text
    try:
        return page.extract_text(layout=True) or ""
    except Exception:
        return ""


def _default_ocr_page(page: Any, page_number: int) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("pytesseract is required when OCR is enabled without an ocr_func.") from exc

    try:
        rendered = page.to_image(resolution=220).original
    except Exception as exc:
        raise RuntimeError(f"Could not render page {page_number} for OCR: {exc}") from exc
    return pytesseract.image_to_string(rendered) or ""


def extract_pdf_pages(source: bytes | bytearray | str | Path | Any, config: PDFExtractionConfig | None = None) -> list[ExtractedPage]:
    config = config or PDFExtractionConfig()
    pdf_bytes, _ = _read_pdf_bytes(source)
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to extract PDF text and tables.") from exc

    pages: list[ExtractedPage] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for index, page in enumerate(pdf.pages, 1):
            warnings: list[str] = []
            rotation = int(getattr(page, "rotation", 0) or 0)
            if rotation:
                warnings.append("rotated_page")

            try:
                text = _extract_text_from_page(page, rotation)
            except Exception as exc:
                text = ""
                warnings.append(f"text_extraction_failed:{exc}")

            try:
                tables = page.extract_tables() or []
            except Exception as exc:
                tables = []
                warnings.append(f"table_extraction_failed:{exc}")

            method = "pdfplumber"
            confidence = 0.95 if rotation else 1.0
            if len(_clean_text(text)) < config.min_text_chars and not tables:
                if config.ocr_enabled:
                    ocr_func = config.ocr_func or _default_ocr_page
                    try:
                        text = ocr_func(page, index) or ""
                        method = "ocr"
                        confidence = 0.72
                        warnings.append("ocr_fallback")
                        if len(_clean_text(text)) < config.min_text_chars:
                            warnings.append("ocr_no_text")
                    except Exception as exc:
                        warnings.append(f"ocr_failed:{exc}")
                        confidence = 0.1
                else:
                    warnings.append("ocr_disabled")
                    confidence = 0.2

            pages.append(
                ExtractedPage(
                    page_number=index,
                    text=text or "",
                    tables=tables,
                    rotation=rotation,
                    method=method,
                    confidence=confidence,
                    warnings=warnings,
                )
            )
    return pages


def classify_event(event_name: str) -> dict[str, Any]:
    key = _normalize_key(event_name)
    weapon = None
    if re.search(r"\b(epee|epée|espada)\b", key):
        weapon = "Epee"
    elif re.search(r"\b(foil|florete)\b", key):
        weapon = "Foil"
    elif re.search(r"\b(sabre|saber|sable)\b", key):
        weapon = "Sabre"

    gender = None
    if re.search(r"\b(women|womens|female|girls|femenino|femenil|damas)\b", key):
        gender = "Women"
    elif re.search(r"\b(men|mens|male|boys|masculino|varonil)\b", key):
        gender = "Men"

    category = None
    if re.search(r"\b(veteran|veterans|vet)\b", key):
        category = "Veteran"
    elif re.search(r"\b(cadet|cadets|u17)\b", key):
        category = "Cadet"
    elif re.search(r"\b(junior|juniors|u20)\b", key):
        category = "Junior"
    elif re.search(r"\b(senior|seniors|open)\b", key):
        category = "Senior"

    team = bool(re.search(r"\b(team|teams|equipo|equipe)\b", key))
    return {"weapon": weapon, "gender": gender, "category": category, "team": team}


def _event_confidence(classification: dict[str, Any], results: list[ResultCandidate], pages: list[ExtractedPage]) -> tuple[float, list[str]]:
    score = 1.0
    reasons: list[str] = []
    for field_name in ("weapon", "gender"):
        if not classification.get(field_name):
            score -= 0.2
            reasons.append(f"missing_{field_name}")
    if not classification.get("category"):
        score -= 0.05
    if not results:
        score -= 0.35
        reasons.append("no_results")
    if results:
        score = min(score, sum(row.confidence for row in results) / len(results))
    if any(page.method == "ocr" for page in pages):
        score -= 0.05
    return max(0.0, min(1.0, round(score, 3))), reasons


def _parse_tournament_line(line: str) -> str | None:
    match = re.match(r"^(?:tournament|competition|meet|championship)\s*:\s*(?P<name>.+)$", line, re.I)
    return _clean_text(match.group("name")) if match else None


def _parse_event_line(line: str) -> str | None:
    match = re.match(r"^(?:event|weapon)\s*:\s*(?P<name>.+)$", line, re.I)
    return _clean_text(match.group("name")) if match else None


def _looks_like_header(line: str) -> bool:
    key = _normalize_key(line)
    return bool(re.search(r"\b(rank|place|pos|position)\b", key) and re.search(r"\b(name|athlete|fencer|team)\b", key))


def _parse_rank(raw: str) -> int | None:
    match = re.search(r"\d+", raw or "")
    return int(match.group(0)) if match else None


def _parse_result_line(line: str, page: ExtractedPage) -> ResultCandidate | None:
    text = _clean_text(line)
    match = re.match(r"^(?P<rank>T?\d{1,3})(?:[.=])?\s+(?P<body>.+)$", text, re.I)
    if not match:
        return None

    rank = _parse_rank(match.group("rank"))
    body = _clean_text(match.group("body"))
    if not body:
        return None

    tokens = body.split()
    country_index = None
    for index, token in enumerate(tokens):
        cleaned = re.sub(r"[^A-Za-z]", "", token).upper()
        if index > 0 and re.fullmatch(r"[A-Z]{3}", cleaned):
            country_index = index
            break

    if country_index is None:
        name = body
        country = None
        club = None
    else:
        name = _clean_text(" ".join(tokens[:country_index]))
        country = re.sub(r"[^A-Za-z]", "", tokens[country_index]).upper()
        club = _clean_text(" ".join(tokens[country_index + 1 :])) or None

    review_reasons: list[str] = []
    confidence = 1.0
    if rank is None:
        confidence -= 0.35
        review_reasons.append("missing_rank")
    if not name:
        confidence -= 0.5
        review_reasons.append("missing_name")
    if not country:
        confidence -= 0.35
        review_reasons.append("missing_country")
    if page.method == "ocr":
        confidence -= 0.15
    if page.rotation:
        confidence -= 0.05
    confidence = max(0.0, min(1.0, round(confidence, 3)))

    return ResultCandidate(
        rank=rank,
        name=name,
        country=country,
        club=club,
        medal=_medal_for_rank(rank),
        page_number=page.page_number,
        raw_text=text,
        confidence=confidence,
        review_reasons=review_reasons,
    )


def _table_header_map(row: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, value in enumerate(row):
        key = _normalize_key(_clean_text(value))
        if key in {"rank", "place", "pos", "position"}:
            mapping["rank"] = index
        elif key in {"name", "athlete", "fencer", "competitor", "team"}:
            mapping["name"] = index
        elif key in {"country", "nation", "nationality", "noc", "nat"}:
            mapping["country"] = index
        elif key in {"club", "organization", "organisation"}:
            mapping["club"] = index
    return mapping


def _parse_table_rows(table: list[list[Any]], page: ExtractedPage) -> list[ResultCandidate]:
    if not table:
        return []
    header = _table_header_map(table[0])
    rows: list[ResultCandidate] = []
    if {"rank", "name"}.issubset(header):
        for raw_row in table[1:]:
            rank = _parse_rank(_clean_text(raw_row[header["rank"]] if len(raw_row) > header["rank"] else ""))
            name = _clean_text(raw_row[header["name"]] if len(raw_row) > header["name"] else "")
            country = None
            if "country" in header and len(raw_row) > header["country"]:
                raw_country = re.sub(r"[^A-Za-z]", "", _clean_text(raw_row[header["country"]])).upper()
                country = raw_country if re.fullmatch(r"[A-Z]{3}", raw_country) else None
            club = None
            if "club" in header and len(raw_row) > header["club"]:
                club = _clean_text(raw_row[header["club"]]) or None
            line = " ".join(_clean_text(cell) for cell in raw_row if _clean_text(cell))
            parsed = _parse_result_line(f"{rank or ''} {name} {country or ''} {club or ''}", page)
            if parsed:
                parsed.raw_text = line
                rows.append(parsed)
        return rows

    for raw_row in table:
        line = " ".join(_clean_text(cell) for cell in raw_row if _clean_text(cell))
        parsed = _parse_result_line(line, page)
        if parsed:
            rows.append(parsed)
    return rows


def _source_id(source_name: str, tournament_name: str, event_name: str) -> str:
    digest = hashlib.sha1(f"{source_name}|{tournament_name}|{event_name}".encode("utf-8")).hexdigest()[:12]
    return f"{SOURCE}:{_slug(source_name)}:{_slug(tournament_name)}:{_slug(event_name)}:{digest}"


def normalize_extracted_pages(pages: list[ExtractedPage], config: PDFExtractionConfig | None = None) -> tuple[list[EventCandidate], list[ManualReviewItem]]:
    config = config or PDFExtractionConfig()
    current_tournament = config.source_name or "PDF Results"
    current_event_name = "Unclassified Results"
    grouped: dict[tuple[str, str], list[ResultCandidate]] = {}
    event_pages: dict[tuple[str, str], list[ExtractedPage]] = {}
    seen_rows: set[tuple[str, str, int | None, str, str | None]] = set()

    for page in pages:
        pending_table_rows: list[ResultCandidate] = []
        for table in page.tables:
            pending_table_rows.extend(_parse_table_rows(table, page))

        for raw_line in page.text.splitlines():
            line = _clean_text(raw_line)
            if not line or _looks_like_header(line):
                continue
            tournament_name = _parse_tournament_line(line)
            if tournament_name:
                current_tournament = tournament_name
                continue
            event_name = _parse_event_line(line)
            if event_name:
                current_event_name = event_name
                continue
            parsed = _parse_result_line(line, page)
            if not parsed:
                continue
            key = (current_tournament, current_event_name)
            row_key = (current_tournament.lower(), current_event_name.lower(), parsed.rank, parsed.name.lower(), parsed.country)
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            grouped.setdefault(key, []).append(parsed)
            event_pages.setdefault(key, []).append(page)

        if pending_table_rows:
            key = (current_tournament, current_event_name)
            for parsed in pending_table_rows:
                row_key = (current_tournament.lower(), current_event_name.lower(), parsed.rank, parsed.name.lower(), parsed.country)
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                grouped.setdefault(key, []).append(parsed)
                event_pages.setdefault(key, []).append(page)

    events: list[EventCandidate] = []
    manual_review: list[ManualReviewItem] = []
    for (tournament_name, event_name), rows in grouped.items():
        classification = classify_event(event_name)
        confidence, event_reasons = _event_confidence(classification, rows, event_pages.get((tournament_name, event_name), []))
        event = EventCandidate(
            tournament_name=tournament_name,
            event_name=event_name,
            source_id=_source_id(config.source_name, tournament_name, event_name),
            weapon=classification["weapon"],
            gender=classification["gender"],
            category=classification["category"] or "Senior",
            team=classification["team"],
            page_number=rows[0].page_number if rows else None,
            results=rows,
            confidence=confidence,
            review_reasons=event_reasons,
        )
        events.append(event)

        if confidence < config.low_confidence_threshold and event_reasons:
            manual_review.append(
                ManualReviewItem(
                    kind="event",
                    reason=",".join(event_reasons),
                    page_number=event.page_number,
                    tournament_name=tournament_name,
                    event_name=event_name,
                    confidence=confidence,
                )
            )
        for row in rows:
            if row.confidence < config.low_confidence_threshold or row.review_reasons:
                manual_review.append(
                    ManualReviewItem(
                        kind="result_row",
                        reason=",".join(row.review_reasons) if row.review_reasons else "low_confidence",
                        page_number=row.page_number,
                        tournament_name=tournament_name,
                        event_name=event_name,
                        raw_text=row.raw_text,
                        confidence=row.confidence,
                    )
                )
    return events, manual_review


def _candidate_to_tournament_row(event: EventCandidate) -> dict[str, Any]:
    return {
        "source_id": event.source_id,
        "name": f"{event.tournament_name} - {event.event_name}",
        "season": None,
        "type": SOURCE,
        "weapon": event.weapon,
        "gender": event.gender,
        "category": event.category,
        "country": None,
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "tournament_name": event.tournament_name,
            "event_name": event.event_name,
            "team": event.team,
            "confidence": event.confidence,
            "review_reasons": event.review_reasons,
        },
    }


def _candidate_to_result_row(tournament_id: Any, event: EventCandidate, row: ResultCandidate) -> dict[str, Any]:
    return {
        "tournament_id": tournament_id,
        "name": row.name,
        "nationality": row.country,
        "rank": row.rank,
        "medal": row.medal,
        "fencer_id": None,
        "metadata": {
            "source": SOURCE,
            "source_id": event.source_id,
            "club": row.club,
            "page_number": row.page_number,
            "confidence": row.confidence,
            "raw_text": row.raw_text,
        },
    }


def write_candidates(
    events: list[EventCandidate],
    client: Any,
    config: PDFExtractionConfig | None = None,
) -> tuple[int, int, int]:
    config = config or PDFExtractionConfig()
    written = 0
    failed = 0
    skipped = 0

    for event in events:
        safe_rows = [
            row
            for row in event.results
            if row.confidence >= config.low_confidence_threshold and not row.review_reasons
        ]
        skipped += len(event.results) - len(safe_rows)
        if not safe_rows or event.confidence < config.low_confidence_threshold:
            skipped += len(safe_rows)
            continue

        try:
            tournament_result = client.table("fs_tournaments").upsert(
                _candidate_to_tournament_row(event),
                on_conflict="source_id",
            ).execute()
            tournament_id = tournament_result.data[0]["id"] if tournament_result.data else None
            if not tournament_id:
                failed += 1
                continue

            db_rows = [_candidate_to_result_row(tournament_id, event, row) for row in safe_rows]
            client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
            for index in range(0, len(db_rows), config.batch_size):
                batch = db_rows[index : index + config.batch_size]
                client.table("fs_results").insert(batch).execute()
                written += len(batch)
        except Exception:
            failed += 1
    return written, failed, skipped


def process_pdf_results(
    source: bytes | bytearray | str | Path | Any,
    config: PDFExtractionConfig | None = None,
    *,
    supabase_client: Any | None = None,
    write: bool = False,
    log_run: bool = False,
) -> PipelineResult:
    config = config or PDFExtractionConfig()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    result = PipelineResult(dry_run=not write)
    try:
        result.pages = extract_pdf_pages(source, config)
        result.events, result.manual_review = normalize_extracted_pages(result.pages, config)

        if write:
            client = supabase_client or supabase
            if not client:
                result.errors.append(ExtractionError("write requested but no Supabase client is configured", config.source_name))
                result.failed = 1
            else:
                result.written, result.failed, result.skipped = write_candidates(result.events, client, config)
                set_state(
                    SOURCE,
                    "last_run",
                    {
                        "source_name": config.source_name,
                        "written": result.written,
                        "failed": result.failed,
                        "skipped": result.skipped,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
        if run_log:
            run_log.complete(written=result.written, failed=result.failed, skipped=result.skipped)
        return result
    except Exception as exc:
        result.errors.append(ExtractionError(f"Malformed PDF or extraction failure: {exc}", config.source_name))
        result.pages = []
        result.events = []
        result.manual_review = []
        result.failed = 1 if write else 0
        if run_log:
            run_log.error(str(exc))
        return result


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    return asdict(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract fencing result candidates from a competition PDF.")
    parser.add_argument("pdf_path", help="PDF file to parse")
    parser.add_argument("--source-name", default=SOURCE)
    parser.add_argument("--ocr", action="store_true", help="Enable OCR fallback for scanned pages")
    parser.add_argument("--write", action="store_true", help="Write high-confidence rows to Supabase")
    parser.add_argument("--manual-review-output", help="Write low-confidence rows to this JSON file")
    args = parser.parse_args(argv)

    config = PDFExtractionConfig(source_name=args.source_name, ocr_enabled=args.ocr)
    result = process_pdf_results(args.pdf_path, config, write=args.write, log_run=args.write)
    if args.manual_review_output:
        Path(args.manual_review_output).write_text(
            json.dumps([asdict(item) for item in result.manual_review], indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "events": len(result.events),
                "manual_review": len(result.manual_review),
                "errors": [error.reason for error in result.errors],
                "dry_run": result.dry_run,
                "written": result.written,
                "failed": result.failed,
                "skipped": result.skipped,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if result.errors or result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
