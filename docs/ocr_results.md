# OCR Results Pipeline

`ocr_results.py` extracts fencing competition result candidates from PDF bytes or a PDF path. It is a review-first pipeline: the default mode parses and scores candidates without writing to Supabase.

## Safe Dry Run

Run a PDF in dry-run mode:

```bash
.venv/bin/python ocr_results.py path/to/results.pdf --source-name "event-source"
```

The command prints counts for extracted events, manual-review rows, errors, skipped rows, and writes. In dry-run mode `written` remains `0`.

To save low-confidence rows for review:

```bash
.venv/bin/python ocr_results.py path/to/results.pdf \
  --source-name "event-source" \
  --manual-review-output /tmp/ocr-review.json
```

Programmatic use:

```python
from ocr_results import PDFExtractionConfig, process_pdf_results

config = PDFExtractionConfig(source_name="event-source")
result = process_pdf_results(pdf_bytes_or_path, config)

for event in result.events:
    print(event.tournament_name, event.event_name, len(event.results))

for item in result.manual_review:
    print(item.reason, item.raw_text)
```

## Extraction Behavior

- `pdfplumber` is the primary extractor for text and tables.
- Multi-page PDFs are processed page by page.
- Rotated pages are detected and reconstructed from word coordinates when needed.
- Blank or scanned pages do not trigger OCR unless OCR is explicitly enabled.
- Malformed PDFs return an extraction error and no candidates.
- Exact duplicate rows within the same tournament/event/rank/name/country are suppressed.

## Confidence And Review

Each result row receives a confidence score. Rows are sent to `manual_review` when they are below `low_confidence_threshold` or have review reasons such as:

- `missing_country`
- `missing_rank`
- `missing_name`

Event candidates also receive confidence based on result confidence and whether weapon/gender/category could be inferred. Low-confidence candidates are safe to inspect in dry-run output before any import.

## Optional OCR

OCR is optional and intentionally off by default.

Python dependencies:

```bash
pip install pytesseract
```

System dependency:

```bash
brew install tesseract
```

Enable OCR only for PDFs that need it:

```bash
.venv/bin/python ocr_results.py path/to/scanned-results.pdf \
  --source-name "scanned-event" \
  --ocr \
  --manual-review-output /tmp/scanned-review.json
```

For tests or controlled jobs, pass `PDFExtractionConfig(ocr_enabled=True, ocr_func=...)` to inject an OCR function without requiring Tesseract.

## Writing To Supabase

Writes are opt-in:

```bash
.venv/bin/python ocr_results.py path/to/results.pdf --source-name "event-source" --write
```

When writing:

- `fs_tournaments` is upserted with `on_conflict="source_id"`.
- Existing `fs_results` rows for that tournament are deleted before inserting high-confidence replacements.
- Low-confidence rows are skipped, not inserted.
- `ScraperRunLogger` is used for write runs.
- `fs_scraper_state` records the last write summary.

Before using `--write`, inspect dry-run output and any manual-review JSON. Do not enable OCR or run large OCR jobs without confirming the job size and expected runtime.
