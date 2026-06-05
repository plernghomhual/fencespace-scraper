#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_logger import ScraperRunLogger


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
PAGE_SIZE = 1000
PDF_PAGE_WIDTH = 595
PDF_PAGE_HEIGHT = 842
PDF_MARGIN = 54


class TournamentPDFError(RuntimeError):
    """Raised when tournament result PDF generation cannot continue safely."""


@dataclass(frozen=True)
class PDFLine:
    text: str
    font: str = "F1"
    size: int = 10
    gap_after: int = 3


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def validate_tournament_id(tournament_id: str) -> str:
    try:
        return str(uuid.UUID(str(tournament_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TournamentPDFError(f"Invalid tournament id: {tournament_id!r}") from exc


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def display_value(value: Any, default: str = "-") -> str:
    text = clean_text(value)
    return text if text is not None else default


def format_generated_at(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, str):
        parsed = parse_datetime(value)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TournamentPDFError(f"Invalid generated timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_money(amount: Any, currency: Any) -> str | None:
    number = coerce_float(amount)
    if number is None:
        return None
    prefix = clean_text(currency)
    formatted = f"{number:,.2f}"
    return f"{prefix} {formatted}" if prefix else formatted


def _query_rows(
    client: Any,
    table_name: str,
    filters: dict[str, Any],
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table_name).select("*")
        for column, value in filters.items():
            query = query.eq(column, value)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _query_one(client: Any, table_name: str, filters: dict[str, Any]) -> dict[str, Any] | None:
    rows = _query_rows(client, table_name, filters, page_size=1)
    return rows[0] if rows else None


def result_rank(row: dict[str, Any]) -> int:
    return coerce_int(row.get("rank") or row.get("placement")) or 999999


def result_sort_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        result_rank(row),
        display_value(row.get("name"), "").casefold(),
        display_value(row.get("country") or row.get("nationality"), "").casefold(),
        display_value(row.get("fie_fencer_id"), ""),
    )


def standing_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": result_rank(row),
        "name": display_value(row.get("name")),
        "country": display_value(row.get("country") or row.get("nationality")),
        "fie_fencer_id": display_value(row.get("fie_fencer_id")),
        "victory": coerce_int(row.get("victory")),
        "matches": coerce_int(row.get("matches")),
        "td": coerce_int(row.get("td")),
        "tr": coerce_int(row.get("tr")),
        "diff": coerce_int(row.get("diff")),
    }


def medalist_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": result_rank(row),
        "name": display_value(row.get("name")),
        "country": display_value(row.get("country") or row.get("nationality")),
    }


def build_medalists(sorted_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    medalists: dict[str, list[dict[str, Any]]] = {"gold": [], "silver": [], "bronze": []}
    for row in sorted_results:
        rank = result_rank(row)
        if rank == 1:
            medalists["gold"].append(medalist_row(row))
        elif rank == 2:
            medalists["silver"].append(medalist_row(row))
        elif rank == 3:
            medalists["bronze"].append(medalist_row(row))
    return medalists


def location_text(tournament: dict[str, Any]) -> str:
    direct = clean_text(tournament.get("location"))
    if direct:
        return direct
    parts = [
        clean_text(tournament.get("city")),
        clean_text(tournament.get("country")),
    ]
    return ", ".join(part for part in parts if part) or "-"


def build_event_payload(
    tournament: dict[str, Any],
    details: dict[str, Any] | None,
) -> dict[str, Any]:
    details = details or {}
    currency = details.get("currency")
    return {
        "season": tournament.get("season"),
        "weapon": display_value(tournament.get("weapon")),
        "gender": display_value(tournament.get("gender")),
        "category": display_value(tournament.get("category")),
        "type": display_value(tournament.get("type")),
        "start_date": display_value(tournament.get("start_date")),
        "end_date": display_value(tournament.get("end_date")),
        "location": location_text(tournament),
        "organizer": display_value(tournament.get("organizer")),
        "venue": display_value(tournament.get("venue_details") or tournament.get("venue")),
        "format": display_value(details.get("format_type") or tournament.get("format")),
        "entries": coerce_int(details.get("participant_count") or tournament.get("quota")),
        "countries": coerce_int(details.get("countries_represented")),
        "pool_size": coerce_int(details.get("pool_size")),
        "de_rounds": coerce_int(details.get("de_rounds")),
        "entry_fee": format_money(details.get("entry_fee"), currency),
        "prize_pool": format_money(details.get("prize_pool"), currency),
        "live_results_url": display_value(tournament.get("live_results_url")),
        "registration_url": display_value(tournament.get("registration_url")),
    }


def round_sort_value(round_name: Any) -> tuple[int, int, str]:
    text = display_value(round_name, "").casefold()
    if "final" in text and "semi" not in text and "tableau" not in text:
        return (0, 0, text)
    if "semifinal" in text or "semi-final" in text or "tableau of 4" in text:
        return (1, 4, text)
    if "tableau" in text or "round of" in text:
        numbers = [coerce_int(part) for part in text.replace("/", " ").split()]
        numeric = [number for number in numbers if number is not None]
        return (2, min(numeric) if numeric else 999999, text)
    if "pool" in text or "poule" in text:
        return (3, 999999, text)
    return (4, 999999, text)


def bout_sort_key(row: dict[str, Any]) -> tuple[int, int, str, str]:
    _raw_meta = row.get("metadata")
    metadata: dict[str, Any] = _raw_meta if isinstance(_raw_meta, dict) else {}
    order = coerce_int(metadata.get("bout_order") or row.get("bout_order"))
    round_group, round_number, round_name = round_sort_value(row.get("round"))
    return (round_group, order or round_number, round_name, display_value(row.get("id"), ""))


def participant_name(row: dict[str, Any], side: str) -> str:
    return display_value(
        row.get(f"fencer_{side}_name")
        or row.get(f"fencer_{side}")
        or row.get(f"fencer_{side}_id")
        or row.get(f"fie_fencer_id_{side}")
    )


def bout_summary_row(row: dict[str, Any]) -> dict[str, str]:
    score_a = coerce_int(row.get("score_a"))
    score_b = coerce_int(row.get("score_b"))
    score = "-" if score_a is None and score_b is None else f"{display_value(score_a)}-{display_value(score_b)}"
    return {
        "round": display_value(row.get("round")),
        "fencer_a": participant_name(row, "a"),
        "fencer_b": participant_name(row, "b"),
        "score": score,
        "winner": display_value(row.get("winner_name") or row.get("winner") or row.get("winner_id")),
    }


def build_tournament_pdf_payload(
    client: Any,
    tournament_id: str,
    *,
    generated_at: datetime | str | None = None,
    include_bouts: bool = False,
    bout_limit: int | None = 50,
) -> dict[str, Any]:
    tournament_uuid = validate_tournament_id(tournament_id)
    tournament = _query_one(client, "fs_tournaments", {"id": tournament_uuid})
    if not tournament:
        raise TournamentPDFError(f"Tournament {tournament_uuid} not found")

    results = _query_rows(client, "fs_results", {"tournament_id": tournament_uuid})
    if not results:
        raise TournamentPDFError(f"No result rows found for tournament {tournament_uuid}")

    details = _query_one(client, "fs_competition_details", {"tournament_id": tournament_uuid})
    sorted_results = sorted(results, key=result_sort_key)
    standings = [standing_row(row) for row in sorted_results]

    bouts: list[dict[str, str]] = []
    if include_bouts:
        raw_bouts = sorted(
            _query_rows(client, "fs_bouts", {"tournament_id": tournament_uuid}),
            key=bout_sort_key,
        )
        if bout_limit is not None:
            raw_bouts = raw_bouts[: max(0, bout_limit)]
        bouts = [bout_summary_row(row) for row in raw_bouts]

    return {
        "title": display_value(tournament.get("name"), tournament_uuid),
        "generated_at": format_generated_at(generated_at),
        "tournament": {
            "id": tournament_uuid,
            "fie_id": tournament.get("fie_id"),
            "name": display_value(tournament.get("name")),
            "season": tournament.get("season"),
            "has_results": bool(tournament.get("has_results")),
        },
        "event": build_event_payload(tournament, details),
        "medalists": build_medalists(sorted_results),
        "standings": standings,
        "bouts": bouts,
        "include_bouts": include_bouts,
    }


def _clip(text: Any, width: int) -> str:
    value = display_value(text)
    if len(value) <= width:
        return value
    return value[: max(0, width - 1)] + "..."


def _table_row(values: list[Any], widths: list[int]) -> str:
    return "  ".join(_clip(value, width).ljust(width) for value, width in zip(values, widths))


def _wrapped_lines(text: str, *, font: str = "F1", size: int = 10, width: int = 92) -> list[PDFLine]:
    wrapped = textwrap.wrap(text, width=width, replace_whitespace=False) or [""]
    return [PDFLine(line, font=font, size=size) for line in wrapped]


def payload_to_pdf_lines(payload: dict[str, Any]) -> list[PDFLine]:
    lines: list[PDFLine] = [
        PDFLine(payload["title"], font="F2", size=18, gap_after=8),
        PDFLine(f"Generated: {payload['generated_at']}", size=9, gap_after=8),
        PDFLine("Tournament Metadata", font="F2", size=13, gap_after=5),
    ]

    tournament = payload["tournament"]
    event = payload["event"]
    metadata_rows = [
        ("Tournament ID", tournament["id"]),
        ("FIE ID", tournament.get("fie_id")),
        ("Season", event.get("season")),
        ("Weapon", event.get("weapon")),
        ("Gender", event.get("gender")),
        ("Category", event.get("category")),
        ("Type", event.get("type")),
        ("Dates", f"{event.get('start_date')} to {event.get('end_date')}"),
        ("Location", event.get("location")),
        ("Organizer", event.get("organizer")),
        ("Venue", event.get("venue")),
        ("Live Results", event.get("live_results_url")),
    ]
    for label, value in metadata_rows:
        lines.extend(_wrapped_lines(f"{label}: {display_value(value)}", width=98))

    lines.extend(
        [
            PDFLine("", gap_after=6),
            PDFLine("Event Table", font="F2", size=13, gap_after=5),
            PDFLine(
                _table_row(
                    ["Format", "Entries", "Countries", "Pool", "DE", "Entry Fee", "Prize Pool"],
                    [26, 8, 9, 6, 4, 14, 14],
                ),
                font="F3",
                size=8,
            ),
            PDFLine(
                _table_row(
                    [
                        event.get("format"),
                        event.get("entries"),
                        event.get("countries"),
                        event.get("pool_size"),
                        event.get("de_rounds"),
                        event.get("entry_fee"),
                        event.get("prize_pool"),
                    ],
                    [26, 8, 9, 6, 4, 14, 14],
                ),
                font="F3",
                size=8,
            ),
            PDFLine("", gap_after=6),
            PDFLine("Medalists", font="F2", size=13, gap_after=5),
        ]
    )

    medal_labels = [("Gold", "gold"), ("Silver", "silver"), ("Bronze", "bronze")]
    for label, key in medal_labels:
        rows = payload["medalists"][key]
        names = ", ".join(f"{row['name']} ({row['country']})" for row in rows) if rows else "-"
        lines.extend(_wrapped_lines(f"{label}: {names}", width=98))

    lines.extend(
        [
            PDFLine("", gap_after=6),
            PDFLine("Full Standings", font="F2", size=13, gap_after=5),
            PDFLine(
                _table_row(["Rank", "Name", "Country", "FIE ID", "V", "M", "TD", "TR", "Diff"], [5, 27, 10, 10, 4, 4, 5, 5, 5]),
                font="F3",
                size=8,
            ),
        ]
    )
    for row in payload["standings"]:
        lines.append(
            PDFLine(
                _table_row(
                    [
                        row.get("rank"),
                        row.get("name"),
                        row.get("country"),
                        row.get("fie_fencer_id"),
                        row.get("victory"),
                        row.get("matches"),
                        row.get("td"),
                        row.get("tr"),
                        row.get("diff"),
                    ],
                    [5, 27, 10, 10, 4, 4, 5, 5, 5],
                ),
                font="F3",
                size=8,
            )
        )

    if payload.get("include_bouts"):
        lines.extend(
            [
                PDFLine("", gap_after=6),
                PDFLine("Bout Summary", font="F2", size=13, gap_after=5),
            ]
        )
        if not payload["bouts"]:
            lines.append(PDFLine("No bout data available."))
        else:
            lines.append(
                PDFLine(
                    _table_row(["Round", "Fencer A", "Fencer B", "Score", "Winner"], [18, 22, 22, 8, 18]),
                    font="F3",
                    size=8,
                )
            )
            for row in payload["bouts"]:
                lines.append(
                    PDFLine(
                        _table_row(
                            [
                                row.get("round"),
                                row.get("fencer_a"),
                                row.get("fencer_b"),
                                row.get("score"),
                                row.get("winner"),
                            ],
                            [18, 22, 22, 8, 18],
                        ),
                        font="F3",
                        size=8,
                    )
                )

    return lines


def paginate_lines(lines: list[PDFLine]) -> list[list[tuple[PDFLine, int]]]:
    pages: list[list[tuple[PDFLine, int]]] = [[]]
    y = PDF_PAGE_HEIGHT - PDF_MARGIN
    min_y = PDF_MARGIN
    for line in lines:
        line_height = line.size + line.gap_after
        if y - line_height < min_y and pages[-1]:
            pages.append([])
            y = PDF_PAGE_HEIGHT - PDF_MARGIN
        if line.text:
            pages[-1].append((line, y))
        y -= line_height
    return pages


def _pdf_escape(text: str) -> bytes:
    raw = str(text).encode("cp1252", errors="replace")
    raw = raw.replace(b"\\", b"\\\\")
    raw = raw.replace(b"(", b"\\(").replace(b")", b"\\)")
    raw = raw.replace(b"\r", b" ").replace(b"\n", b" ")
    return raw


def _content_stream(lines: list[tuple[PDFLine, int]]) -> bytes:
    chunks: list[bytes] = []
    for line, y in lines:
        chunks.append(
            b"BT /"
            + line.font.encode("ascii")
            + f" {line.size} Tf {PDF_MARGIN} {y} Td (".encode("ascii")
            + _pdf_escape(line.text)
            + b") Tj ET\n"
        )
    return b"".join(chunks)


def _pdf_stream(payload: bytes) -> bytes:
    return f"<< /Length {len(payload)} >>\nstream\n".encode("ascii") + payload + b"endstream"


def render_tournament_pdf(payload: dict[str, Any]) -> bytes:
    pages = paginate_lines(payload_to_pdf_lines(payload))
    objects: list[bytes | None] = [None]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(None)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids: list[int] = []
    for page in pages:
        stream = _pdf_stream(_content_stream(page))
        content_id = len(objects)
        objects.append(stream)
        page_id = len(objects)
        page_ids.append(page_id)
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PDF_PAGE_WIDTH} {PDF_PAGE_HEIGHT}] "
                f"/Contents {content_id} 0 R "
                "/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>"
            ).encode("ascii")
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for obj_id in range(1, len(objects)):
        body = objects[obj_id]
        if body is None:
            raise AssertionError(f"PDF object {obj_id} was not initialized")
        offsets.append(len(pdf))
        pdf += f"{obj_id} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def validate_output_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.exists() and path.is_dir():
        raise TournamentPDFError(f"Output path is a directory: {path}")
    if not path.parent.exists():
        raise TournamentPDFError(f"Output directory does not exist: {path.parent}")
    return path


def generate_tournament_pdf(
    client: Any,
    tournament_id: str,
    output_path: str | Path,
    *,
    generated_at: datetime | str | None = None,
    include_bouts: bool = False,
    bout_limit: int | None = 50,
) -> Path:
    path = validate_output_path(output_path)
    payload = build_tournament_pdf_payload(
        client,
        tournament_id,
        generated_at=generated_at,
        include_bouts=include_bouts,
        bout_limit=bout_limit,
    )
    path.write_bytes(render_tournament_pdf(payload))
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a tournament results PDF.")
    parser.add_argument("tournament_id", help="fs_tournaments.id UUID to export.")
    parser.add_argument("--output", required=True, help="PDF output path.")
    parser.add_argument("--include-bouts", action="store_true", help="Include a bout summary when fs_bouts rows exist.")
    parser.add_argument("--bout-limit", type=int, default=50, help="Maximum bouts to include when --include-bouts is set.")
    parser.add_argument("--generated-at", help="Override generated timestamp, e.g. 2026-06-02T14:30:00Z.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.bout_limit < 0:
        parser.error("--bout-limit must be non-negative")

    run_log = ScraperRunLogger("generate_tournament_pdf").start()
    try:
        written = generate_tournament_pdf(
            get_supabase_client(),
            args.tournament_id,
            args.output,
            generated_at=args.generated_at,
            include_bouts=args.include_bouts,
            bout_limit=args.bout_limit,
        )
    except TournamentPDFError as exc:
        run_log.error(str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        run_log.error(str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    run_log.complete(written=1, failed=0, skipped=0, metadata={"output": str(written)})
    print(str(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
