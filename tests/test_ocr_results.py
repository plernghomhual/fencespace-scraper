import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _escape_pdf_text(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_text_pdf(pages):
    """Build a tiny valid text PDF without adding a test-only dependency."""
    objects = []

    def add_object(data):
        objects.append(data)
        return len(objects)

    catalog_id = add_object(b"")
    pages_id = add_object(b"")
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    content_ids = []

    for page in pages:
        if isinstance(page, dict):
            lines = page.get("lines", [])
            rotation = page.get("rotation", 0)
        else:
            lines = page
            rotation = 0

        operations = ["BT", "/F1 12 Tf", "72 720 Td"]
        first_line = True
        for line in lines:
            if not first_line:
                operations.append("0 -18 Td")
            operations.append(f"({_escape_pdf_text(line)}) Tj")
            first_line = False
        operations.append("ET")
        stream = "\n".join(operations).encode("latin-1")
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_id = add_object(b"")
        content_ids.append(content_id)
        page_ids.append((page_id, rotation))

    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    kids = " ".join(f"{page_id} 0 R" for page_id, _ in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    for (page_id, rotation), content_id in zip(page_ids, content_ids):
        rotate = f" /Rotate {rotation}" if rotation else ""
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792]{rotate} "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")

    xref_pos = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def test_process_pdf_bytes_extracts_multi_page_candidates_with_confidence():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    pdf_bytes = make_text_pdf(
        [
            [
                "Tournament: Capitol Clash",
                "Event: Senior Men Epee",
                "Rank Name Country Club",
                "1 DOE John USA DCFC",
                "2 SMITH Jack CAN VFC",
            ],
            [
                "Tournament: Capitol Clash",
                "Event: Senior Women Foil",
                "Rank Name Country Club",
                "1 LEE Alice KOR Seoul",
                "2 GARCIA Maria ESP Madrid",
            ],
        ]
    )

    result = process_pdf_results(pdf_bytes, PDFExtractionConfig(source_name="capitol-clash"))

    assert result.errors == []
    assert result.dry_run is True
    assert result.written == 0
    assert len(result.pages) == 2
    assert len(result.events) == 2
    assert result.manual_review == []

    first = result.events[0]
    assert first.tournament_name == "Capitol Clash"
    assert first.event_name == "Senior Men Epee"
    assert first.weapon == "Epee"
    assert first.gender == "Men"
    assert first.category == "Senior"
    assert first.confidence >= 0.9
    assert first.results[0].rank == 1
    assert first.results[0].name == "DOE John"
    assert first.results[0].country == "USA"
    assert first.results[0].club == "DCFC"
    assert first.results[0].confidence >= 0.9


def test_path_input_rotated_page_and_duplicate_rows_are_handled(tmp_path):
    from ocr_results import PDFExtractionConfig, process_pdf_results

    pdf_path = tmp_path / "rotated-results.pdf"
    pdf_path.write_bytes(
        make_text_pdf(
            [
                {
                    "rotation": 90,
                    "lines": [
                        "Tournament: Rotation Open",
                        "Event: Junior Women Sabre",
                        "Rank Name Country",
                        "1 DUPONT Anne FRA",
                        "1 DUPONT Anne FRA",
                    ],
                }
            ]
        )
    )

    result = process_pdf_results(pdf_path, PDFExtractionConfig(source_name="rotation-open"))

    assert result.errors == []
    assert result.pages[0].rotation == 90
    assert "rotated" in " ".join(result.pages[0].warnings).lower()
    assert len(result.events) == 1
    assert len(result.events[0].results) == 1
    assert result.events[0].results[0].name == "DUPONT Anne"


def test_low_confidence_rows_are_reported_for_manual_review():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    pdf_bytes = make_text_pdf(
        [
            [
                "Tournament: Review Open",
                "Event: Senior Men Foil",
                "Rank Name Country",
                "1 CLEAN Person USA",
                "2 Missing Country",
            ]
        ]
    )

    result = process_pdf_results(pdf_bytes, PDFExtractionConfig(source_name="review-open", low_confidence_threshold=0.8))

    assert len(result.events) == 1
    assert len(result.events[0].results) == 2
    low = result.events[0].results[1]
    assert low.rank == 2
    assert low.country is None
    assert low.confidence < 0.8
    assert "missing_country" in low.review_reasons
    assert [item.reason for item in result.manual_review if item.kind == "result_row"] == ["missing_country"]


def test_malformed_pdf_returns_error_and_no_candidates():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    result = process_pdf_results(b"not a pdf", PDFExtractionConfig(source_name="bad-file"))

    assert result.events == []
    assert result.pages == []
    assert result.manual_review == []
    assert len(result.errors) == 1
    assert "malformed" in result.errors[0].reason.lower() or "pdf" in result.errors[0].reason.lower()


def test_dry_run_default_does_not_touch_supabase_client():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    class FailingClient:
        def table(self, name):
            raise AssertionError(f"unexpected write to {name}")

    pdf_bytes = make_text_pdf(
        [
            [
                "Tournament: Dry Run Open",
                "Event: Senior Men Sabre",
                "Rank Name Country",
                "1 SAFE Row USA",
            ]
        ]
    )

    result = process_pdf_results(pdf_bytes, PDFExtractionConfig(source_name="dry-run"), supabase_client=FailingClient())

    assert result.dry_run is True
    assert result.written == 0
    assert result.failed == 0
    assert len(result.events) == 1


def test_scanned_pdf_uses_ocr_only_when_configured():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    calls = []

    def fake_ocr(page, page_number):
        calls.append(page_number)
        return "\n".join(
            [
                "Tournament: OCR Open",
                "Event: Senior Women Epee",
                "Rank Name Country",
                "1 OCR Winner USA",
            ]
        )

    blank_pdf = make_text_pdf([[]])

    without_ocr = process_pdf_results(
        blank_pdf,
        PDFExtractionConfig(source_name="ocr-open", ocr_enabled=False, ocr_func=fake_ocr),
    )
    assert calls == []
    assert without_ocr.events == []
    assert without_ocr.pages[0].method == "pdfplumber"
    assert "ocr_disabled" in without_ocr.pages[0].warnings

    with_ocr = process_pdf_results(
        blank_pdf,
        PDFExtractionConfig(source_name="ocr-open", ocr_enabled=True, ocr_func=fake_ocr),
    )
    assert calls == [1]
    assert with_ocr.pages[0].method == "ocr"
    assert with_ocr.events[0].results[0].name == "OCR Winner"


def test_write_true_upserts_only_high_confidence_rows():
    from ocr_results import PDFExtractionConfig, process_pdf_results

    class FakeResult:
        def __init__(self, data=None):
            self.data = data or []

    class FakeTable:
        def __init__(self, client, name):
            self.client = client
            self.name = name

        def upsert(self, payload, on_conflict=None):
            self.client.calls.append((self.name, "upsert", payload, on_conflict))
            self._result = FakeResult([{"id": "tournament-1"}])
            return self

        def delete(self):
            self.client.calls.append((self.name, "delete", None, None))
            return self

        def eq(self, column, value):
            self.client.calls.append((self.name, "eq", column, value))
            return self

        def insert(self, payload):
            self.client.calls.append((self.name, "insert", payload, None))
            self._result = FakeResult(payload)
            return self

        def execute(self):
            return getattr(self, "_result", FakeResult())

    class FakeClient:
        def __init__(self):
            self.calls = []

        def table(self, name):
            return FakeTable(self, name)

    pdf_bytes = make_text_pdf(
        [
            [
                "Tournament: Write Open",
                "Event: Senior Men Epee",
                "Rank Name Country",
                "1 HIGH Confidence USA",
                "2 Needs Review",
            ]
        ]
    )
    client = FakeClient()

    result = process_pdf_results(
        pdf_bytes,
        PDFExtractionConfig(source_name="write-open", low_confidence_threshold=0.8),
        supabase_client=client,
        write=True,
    )

    inserts = [call for call in client.calls if call[0] == "fs_results" and call[1] == "insert"]
    assert result.dry_run is False
    assert result.written == 1
    assert result.skipped == 1
    assert len(inserts) == 1
    assert inserts[0][2][0]["name"] == "HIGH Confidence"
    assert all(row["name"] != "Needs Review" for row in inserts[0][2])
