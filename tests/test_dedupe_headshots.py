import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dedupe_headshots as dhd


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.payload = None
        self.operation = None

    def select(self, columns):
        self.operation = "select"
        self.client.operations.append((self.table_name, "select", columns))
        return self

    def limit(self, count):
        self.client.operations.append((self.table_name, "limit", count))
        return self

    def upsert(self, row, on_conflict):
        self.operation = "upsert"
        self.payload = row
        self.client.upserts.append(
            {
                "table": self.table_name,
                "row": dict(row),
                "on_conflict": on_conflict,
            }
        )
        return self

    def update(self, payload):
        self.client.destructive_operations.append((self.table_name, "update", payload))
        raise AssertionError("dedupe must not update fencers or identities")

    def delete(self):
        self.client.destructive_operations.append((self.table_name, "delete"))
        raise AssertionError("dedupe must not delete images or rows")

    def execute(self):
        if self.operation == "select":
            return FakeResult(self.client.rows)
        if self.operation == "upsert":
            return FakeResult([self.payload])
        return FakeResult([])


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []
        self.upserts = []
        self.destructive_operations = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def image_file(tmp_path, name, *, color=(40, 80, 200), accent=(240, 240, 240), shift=0):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (96, 96), color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((28 + shift, 16, 68 + shift, 56), fill=accent)
    draw.rectangle((40 + shift, 56, 56 + shift, 82), fill=(90, 90, 120))
    path = tmp_path / name
    image.save(path, format="JPEG", quality=92)
    return path


def fencer_row(fencer_id, path, *, url=None, name=None, country="USA"):
    return {
        "id": fencer_id,
        "fie_id": f"FIE-{fencer_id}",
        "name": name or f"Fencer {fencer_id}",
        "country": country,
        "image_url": url,
        "local_image_path": str(path) if path else None,
        "metadata": {"source": "test-fixture"},
    }


def test_identical_urls_and_content_hashes_are_flagged_for_review(tmp_path):
    shared_bytes_path = image_file(tmp_path, "lee-a.jpg")
    duplicate_path = tmp_path / "lee-b.jpg"
    duplicate_path.write_bytes(shared_bytes_path.read_bytes())
    rows = [
        fencer_row("fencer-a", shared_bytes_path, url="https://images.example/lee.jpg", name="Lee Kiefer"),
        fencer_row("fencer-b", duplicate_path, url="https://images.example/lee.jpg", name="Lee Kiefer"),
    ]

    result = dhd.find_duplicate_candidates(rows)

    assert result.stats.processed == 2
    assert result.stats.skipped == 0
    assert len(result.candidates) == 1
    review_row = result.candidates[0].to_review_row()
    assert review_row["status"] == "pending"
    assert review_row["source_fencer_a_id"] == "fencer-a"
    assert review_row["source_fencer_b_id"] == "fencer-b"
    assert review_row["source_image_a_id"]
    assert review_row["source_image_b_id"]
    assert review_row["confidence"] == pytest.approx(1.0)
    assert set(review_row["evidence"]["match_types"]) == {"identical_url", "content_hash", "perceptual_hash"}
    assert "manual review" in review_row["privacy_notes"].lower()


def test_perceptual_hash_flags_visually_similar_images_without_exact_match(tmp_path):
    first = image_file(tmp_path, "similar-a.jpg", color=(45, 80, 190), shift=0)
    second = image_file(tmp_path, "similar-b.jpg", color=(46, 82, 193), shift=1)
    rows = [
        fencer_row("fencer-a", first, url="https://images.example/a.jpg", name="Arianna Errigo"),
        fencer_row("fencer-b", second, url="https://images.example/b.jpg", name="Arianna Errigo"),
    ]

    result = dhd.find_duplicate_candidates(rows)

    assert len(result.candidates) == 1
    review_row = result.candidates[0].to_review_row()
    assert review_row["match_type"] == "perceptual_hash"
    assert 0.7 <= review_row["confidence"] < 1.0
    assert review_row["evidence"]["hash_distance"] <= dhd.DEFAULT_HASH_DISTANCE_THRESHOLD
    assert review_row["evidence"]["color_distance"] <= dhd.DEFAULT_COLOR_DISTANCE_THRESHOLD


def test_corrupt_and_missing_images_are_skipped_without_candidates(tmp_path):
    valid = image_file(tmp_path, "valid.jpg")
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"not a real image")
    missing = tmp_path / "missing.jpg"
    rows = [
        fencer_row("valid", valid, url="https://images.example/valid.jpg"),
        fencer_row("corrupt", corrupt, url="https://images.example/corrupt.jpg"),
        fencer_row("missing", missing, url="https://images.example/missing.jpg"),
    ]

    result = dhd.find_duplicate_candidates(rows)

    assert result.candidates == []
    assert result.stats.processed == 3
    assert result.stats.skipped == 2
    reasons = {error["reason"] for error in result.stats.image_errors}
    assert reasons == {"invalid_image", "missing_image"}


def test_review_upserts_do_not_delete_images_or_merge_identities(tmp_path):
    client = FakeClient(
        [
            fencer_row("fencer-a", None, url="https://images.example/shared.jpg"),
            fencer_row("fencer-b", None, url="https://images.example/shared.jpg"),
        ]
    )

    result = dhd.run_dedupe(client, limit=10)

    assert result.stats.candidates == 1
    assert client.destructive_operations == []
    assert [item["table"] for item in client.upserts] == ["fs_headshot_duplicate_reviews"]
    assert client.upserts[0]["on_conflict"] == "candidate_key"
    assert client.upserts[0]["row"]["status"] == "pending"
    assert "fs_fencer_identities" not in [operation[0] for operation in client.operations]


def test_optional_embedding_provider_can_flag_mocked_face_candidate(tmp_path):
    first = image_file(tmp_path, "face-a.jpg", color=(20, 20, 220), accent=(240, 230, 210))
    second = image_file(tmp_path, "face-b.jpg", color=(220, 30, 30), accent=(245, 235, 215))
    rows = [
        fencer_row("fencer-a", first, url="https://images.example/face-a.jpg"),
        fencer_row("fencer-b", second, url="https://images.example/face-b.jpg"),
    ]
    calls = []

    def embedding_provider(record, image_bytes):
        calls.append(record["id"])
        if record["id"] == "fencer-a":
            return [0.10, 0.20, 0.30]
        return [0.11, 0.19, 0.31]

    result = dhd.find_duplicate_candidates(
        rows,
        enable_face_embeddings=True,
        embedding_provider=embedding_provider,
    )

    assert calls == ["fencer-a", "fencer-b"]
    assert len(result.candidates) == 1
    review_row = result.candidates[0].to_review_row()
    assert review_row["match_type"] == "face_embedding"
    assert review_row["confidence"] >= 0.85
    assert review_row["evidence"]["embedding_distance"] < dhd.DEFAULT_EMBEDDING_DISTANCE_THRESHOLD


def test_migration_defines_private_manual_review_table():
    migration = Path("supabase/migrations/20260602_headshot_dedup.sql").read_text(encoding="utf-8")
    normalized = " ".join(migration.lower().split())

    assert "create table if not exists public.fs_headshot_duplicate_reviews" in normalized
    assert "source_fencer_a_id" in normalized
    assert "source_fencer_b_id" in normalized
    assert "source_image_a_id" in normalized
    assert "source_image_b_id" in normalized
    assert "confidence" in normalized
    assert "status" in normalized
    assert "manual review" in normalized
    assert "privacy" in normalized
    assert "alter table public.fs_headshot_duplicate_reviews enable row level security" in normalized
    assert "revoke all on public.fs_headshot_duplicate_reviews from anon, authenticated" in normalized
