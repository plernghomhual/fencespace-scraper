import os
import sys
from datetime import UTC, datetime, timezone

import pdfplumber
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TOURNAMENT_ID = "00000000-0000-0000-0000-000000000114"
GENERATED_AT = datetime(2026, 6, 2, 14, 30, tzinfo=UTC)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.start = 0
        self.end = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.client.filters.append((self.table_name, column, value))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        end = self.end + 1 if self.end is not None else None
        return FakeResult(rows[self.start:end])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.filters = []
        self.ranges = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def fake_client():
    return FakeSupabase(
        {
            "fs_tournaments": [
                {
                    "id": TOURNAMENT_ID,
                    "fie_id": 987,
                    "name": "Grand Prix Seoul",
                    "season": 2026,
                    "weapon": "Epee",
                    "gender": "Men",
                    "category": "Senior",
                    "type": "Grand Prix",
                    "start_date": "2026-05-30",
                    "end_date": "2026-06-01",
                    "city": "Seoul",
                    "country": "KOR",
                    "organizer": "Korea Fencing Federation",
                    "venue_details": "Olympic Gymnasium",
                    "format": "Individual",
                    "has_results": True,
                    "live_results_url": "https://fie.org/competitions/2026/987",
                }
            ],
            "fs_competition_details": [
                {
                    "tournament_id": TOURNAMENT_ID,
                    "participant_count": 64,
                    "countries_represented": 12,
                    "format_type": "pools + direct elimination",
                    "pool_size": 7,
                    "de_rounds": 6,
                    "entry_fee": 100.0,
                    "prize_pool": 9000.0,
                    "currency": "EUR",
                    "metadata": {"document_urls": ["https://static.fie.org/invitation.pdf"]},
                }
            ],
            "fs_results": [
                {"tournament_id": TOURNAMENT_ID, "rank": 3, "name": "CARL KIM", "country": "KOR", "fie_fencer_id": "103"},
                {"tournament_id": TOURNAMENT_ID, "rank": 1, "name": "ALICE LEE", "country": "USA", "fie_fencer_id": "101"},
                {"tournament_id": TOURNAMENT_ID, "rank": 8, "name": "EVE STONE", "country": "GBR", "fie_fencer_id": "105"},
                {"tournament_id": TOURNAMENT_ID, "rank": 2, "name": "BOB PARK", "country": "FRA", "fie_fencer_id": "102"},
                {"tournament_id": TOURNAMENT_ID, "rank": 3, "name": "DANA ROSSI", "country": "ITA", "fie_fencer_id": "104"},
            ],
            "fs_bouts": [
                {
                    "id": "bout-2",
                    "tournament_id": TOURNAMENT_ID,
                    "round": "Tableau of 4",
                    "fencer_a_name": "Bob Park",
                    "fencer_b_name": "Dana Rossi",
                    "score_a": 15,
                    "score_b": 12,
                    "winner_name": "Bob Park",
                },
                {
                    "id": "bout-1",
                    "tournament_id": TOURNAMENT_ID,
                    "round": "Final",
                    "fencer_a_name": "Alice Lee",
                    "fencer_b_name": "Bob Park",
                    "score_a": 15,
                    "score_b": 11,
                    "winner_name": "Alice Lee",
                },
            ],
        }
    )


def test_build_payload_assembles_metadata_medalists_standings_and_bouts():
    from generate_tournament_pdf import build_tournament_pdf_payload

    payload = build_tournament_pdf_payload(
        fake_client(),
        TOURNAMENT_ID,
        generated_at=GENERATED_AT,
        include_bouts=True,
        bout_limit=10,
    )

    assert payload["tournament"]["id"] == TOURNAMENT_ID
    assert payload["title"] == "Grand Prix Seoul"
    assert payload["generated_at"] == "2026-06-02 14:30 UTC"
    assert payload["event"]["entries"] == 64
    assert payload["event"]["countries"] == 12
    assert payload["event"]["format"] == "pools + direct elimination"
    assert payload["medalists"]["gold"] == [{"rank": 1, "name": "ALICE LEE", "country": "USA"}]
    assert payload["medalists"]["silver"] == [{"rank": 2, "name": "BOB PARK", "country": "FRA"}]
    assert payload["medalists"]["bronze"] == [
        {"rank": 3, "name": "CARL KIM", "country": "KOR"},
        {"rank": 3, "name": "DANA ROSSI", "country": "ITA"},
    ]
    assert [row["name"] for row in payload["standings"]] == [
        "ALICE LEE",
        "BOB PARK",
        "CARL KIM",
        "DANA ROSSI",
        "EVE STONE",
    ]
    assert payload["bouts"] == [
        {"round": "Final", "fencer_a": "Alice Lee", "fencer_b": "Bob Park", "score": "15-11", "winner": "Alice Lee"},
        {"round": "Tableau of 4", "fencer_a": "Bob Park", "fencer_b": "Dana Rossi", "score": "15-12", "winner": "Bob Park"},
    ]


def test_generated_pdf_has_pdf_header_and_extractable_key_text(tmp_path):
    from generate_tournament_pdf import (
        build_tournament_pdf_payload,
        render_tournament_pdf,
    )

    payload = build_tournament_pdf_payload(
        fake_client(),
        TOURNAMENT_ID,
        generated_at=GENERATED_AT,
        include_bouts=True,
    )
    pdf_bytes = render_tournament_pdf(payload)

    assert pdf_bytes.startswith(b"%PDF-")
    output = tmp_path / "grand-prix-seoul.pdf"
    output.write_bytes(pdf_bytes)

    with pdfplumber.open(output) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Grand Prix Seoul" in text
    assert "Medalists" in text
    assert "ALICE LEE" in text
    assert "Full Standings" in text
    assert "Bout Summary" in text
    assert "Final" in text


def test_missing_tournament_raises_clean_error():
    from generate_tournament_pdf import TournamentPDFError, build_tournament_pdf_payload

    client = FakeSupabase({"fs_tournaments": [], "fs_results": []})

    with pytest.raises(TournamentPDFError, match="Tournament .* not found"):
        build_tournament_pdf_payload(client, TOURNAMENT_ID, generated_at=GENERATED_AT)


def test_tournament_without_results_raises_clean_error():
    from generate_tournament_pdf import TournamentPDFError, build_tournament_pdf_payload

    client = fake_client()
    client.tables["fs_results"] = []

    with pytest.raises(TournamentPDFError, match="No result rows"):
        build_tournament_pdf_payload(client, TOURNAMENT_ID, generated_at=GENERATED_AT)


def test_invalid_tournament_id_is_rejected_before_querying():
    from generate_tournament_pdf import TournamentPDFError, build_tournament_pdf_payload

    client = fake_client()

    with pytest.raises(TournamentPDFError, match="Invalid tournament id"):
        build_tournament_pdf_payload(client, "../not-a-uuid", generated_at=GENERATED_AT)

    assert client.selects == []


def test_generate_pdf_writes_only_requested_existing_output_path(tmp_path):
    from generate_tournament_pdf import generate_tournament_pdf

    output = tmp_path / "result.pdf"

    written = generate_tournament_pdf(
        fake_client(),
        TOURNAMENT_ID,
        output,
        generated_at=GENERATED_AT,
        include_bouts=False,
    )

    assert written == output
    assert output.read_bytes().startswith(b"%PDF-")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["result.pdf"]


def test_generate_pdf_rejects_missing_output_parent(tmp_path):
    from generate_tournament_pdf import TournamentPDFError, generate_tournament_pdf

    missing_parent = tmp_path / "missing" / "result.pdf"

    with pytest.raises(TournamentPDFError, match="Output directory does not exist"):
        generate_tournament_pdf(fake_client(), TOURNAMENT_ID, missing_parent, generated_at=GENERATED_AT)

    assert not missing_parent.exists()
