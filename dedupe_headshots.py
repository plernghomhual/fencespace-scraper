from __future__ import annotations

import hashlib
import io
import math
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "dedupe_headshots"
REVIEW_TABLE = "fs_headshot_duplicate_reviews"
FENCER_COLUMNS = "id,fie_id,name,country,image_url,metadata,world_rank"
DEFAULT_LIMIT = int(os.environ.get("HEADSHOT_DEDUPE_LIMIT", "5000"))
DEFAULT_HASH_DISTANCE_THRESHOLD = int(os.environ.get("HEADSHOT_DEDUPE_HASH_DISTANCE", "5"))
DEFAULT_COLOR_DISTANCE_THRESHOLD = float(os.environ.get("HEADSHOT_DEDUPE_COLOR_DISTANCE", "18"))
DEFAULT_EMBEDDING_DISTANCE_THRESHOLD = float(os.environ.get("HEADSHOT_DEDUPE_EMBEDDING_DISTANCE", "0.6"))
REMOTE_IMAGE_TIMEOUT_SECONDS = float(os.environ.get("HEADSHOT_DEDUPE_REMOTE_TIMEOUT_SECONDS", "15"))
PRIVACY_NOTES = (
    "Manual review candidate only. Hashes and optional face embeddings can create false positives "
    "and biometric privacy risk; do not auto-merge identities or delete images. "
    "A human reviewer must inspect the source images and evidence before action."
)

EmbeddingProvider = Callable[[dict[str, Any], bytes], Sequence[float] | None]


@dataclass
class DedupeStats:
    processed: int = 0
    images_loaded: int = 0
    skipped: int = 0
    candidates: int = 0
    upserted: int = 0
    embedding_skipped: int = 0
    image_errors: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ImageFingerprint:
    row: dict[str, Any]
    fencer_id: str
    source_image_id: str
    image_bytes: bytes
    byte_sha256: str
    normalized_sha256: str
    average_hash: int
    mean_rgb: tuple[float, float, float]
    width: int
    height: int


@dataclass
class DuplicateCandidate:
    candidate_key: str
    source_fencer_a_id: str
    source_fencer_b_id: str
    source_image_a_id: str
    source_image_b_id: str
    image_a_url: str | None
    image_b_url: str | None
    match_type: str
    confidence: float
    evidence: dict[str, Any]
    status: str = "pending"
    privacy_notes: str = PRIVACY_NOTES

    def to_review_row(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_key,
            "source_fencer_a_id": self.source_fencer_a_id,
            "source_fencer_b_id": self.source_fencer_b_id,
            "source_image_a_id": self.source_image_a_id,
            "source_image_b_id": self.source_image_b_id,
            "image_a_url": self.image_a_url,
            "image_b_url": self.image_b_url,
            "match_type": self.match_type,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "status": self.status,
            "privacy_notes": self.privacy_notes,
            "updated_at": datetime.now(UTC).isoformat(),
        }


@dataclass
class DedupeResult:
    candidates: list[DuplicateCandidate]
    stats: DedupeStats


def clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_url(value: Any) -> str | None:
    url = clean_text(value)
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            query,
            "",
        )
    )


def is_http_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def source_image_id_for(row: dict[str, Any], fingerprint: ImageFingerprint | None = None) -> str:
    if fingerprint:
        return f"content:{fingerprint.normalized_sha256[:32]}"
    source = (
        normalize_url(row.get("local_image_path"))
        or normalize_url(row.get("image_url"))
        or clean_text(row.get("id"))
        or "unknown"
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]
    return f"source:{digest}"


def display_image_url(row: dict[str, Any]) -> str | None:
    return normalize_url(row.get("local_image_path")) or normalize_url(row.get("image_url"))


def pair_key(row_a: dict[str, Any], row_b: dict[str, Any]) -> tuple[str, str]:
    first = clean_text(row_a.get("id")) or source_image_id_for(row_a)
    second = clean_text(row_b.get("id")) or source_image_id_for(row_b)
    a, b = sorted((first, second))
    return a, b


def candidate_key_for(row_a: dict[str, Any], row_b: dict[str, Any]) -> str:
    first, second = pair_key(row_a, row_b)
    raw = f"{first}|{second}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"headshot:{digest}"


def _lanczos_filter():
    return getattr(Image, "Resampling", Image).LANCZOS


def average_hash(image: Image.Image) -> int:
    gray = image.convert("L").resize((8, 8), _lanczos_filter())
    pixels = list(gray.tobytes())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | int(pixel >= avg)
    return bits


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def rgb_distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=False)))


def embedding_distance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return float("inf")
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=False)))


def fingerprint_image(row: dict[str, Any], image_bytes: bytes) -> ImageFingerprint:
    fencer_id = clean_text(row.get("id")) or source_image_id_for(row)
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if getattr(image, "is_animated", False):
                image.seek(0)
            rgb = image.convert("RGB")
            width, height = rgb.size
            normalized = rgb.resize((64, 64), _lanczos_filter())
            mean_pixel = normalized.resize((1, 1), _lanczos_filter()).getpixel((0, 0))
            normalized_sha256 = hashlib.sha256(normalized.tobytes()).hexdigest()
            byte_sha256 = hashlib.sha256(image_bytes).hexdigest()
            fingerprint = ImageFingerprint(
                row=row,
                fencer_id=fencer_id,
                source_image_id="",
                image_bytes=image_bytes,
                byte_sha256=byte_sha256,
                normalized_sha256=normalized_sha256,
                average_hash=average_hash(rgb),
                mean_rgb=(float(mean_pixel[0]), float(mean_pixel[1]), float(mean_pixel[2])),
                width=width,
                height=height,
            )
            fingerprint.source_image_id = source_image_id_for(row, fingerprint)
            return fingerprint
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"invalid_image:{exc}") from exc


def read_local_image_bytes(path_value: str) -> bytes:
    path = Path(path_value).expanduser()
    if not path.exists():
        raise FileNotFoundError(path_value)
    return path.read_bytes()


def fetch_remote_image_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=REMOTE_IMAGE_TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"non_image_content_type:{content_type}")
    return response.content


def load_image_fingerprints(
    rows: Iterable[dict[str, Any]],
    stats: DedupeStats,
    *,
    allow_remote_images: bool = False,
    remote_fetcher: Callable[[str], bytes] = fetch_remote_image_bytes,
) -> list[ImageFingerprint]:
    fingerprints: list[ImageFingerprint] = []
    for row in rows:
        path_value = clean_text(row.get("local_image_path"))
        if not path_value:
            continue
        try:
            if is_http_url(path_value):
                if not allow_remote_images:
                    continue
                image_bytes = remote_fetcher(path_value)
            else:
                image_bytes = read_local_image_bytes(path_value)
            fingerprints.append(fingerprint_image(row, image_bytes))
            stats.images_loaded += 1
        except FileNotFoundError:
            stats.skipped += 1
            stats.image_errors.append({"fencer_id": str(row.get("id")), "reason": "missing_image"})
        except ValueError as exc:
            reason = str(exc).split(":", 1)[0] or "invalid_image"
            stats.skipped += 1
            stats.image_errors.append({"fencer_id": str(row.get("id")), "reason": reason})
        except Exception as exc:
            stats.skipped += 1
            stats.image_errors.append({"fencer_id": str(row.get("id")), "reason": f"image_error:{exc}"})
    return fingerprints


def evidence_source(row: dict[str, Any], source_image_id: str) -> dict[str, Any]:
    return {
        "fencer_id": clean_text(row.get("id")),
        "fie_id": clean_text(row.get("fie_id")),
        "name": clean_text(row.get("name")),
        "country": clean_text(row.get("country")),
        "source_image_id": source_image_id,
        "image_url": normalize_url(row.get("image_url")),
        "local_image_path": normalize_url(row.get("local_image_path")) or clean_text(row.get("local_image_path")),
    }


def confidence_for_perceptual(hash_distance: int, color_distance: float) -> float:
    confidence = 0.94 - (hash_distance * 0.018) - (color_distance / 400)
    return max(0.70, min(0.98, confidence))


def confidence_for_embedding(distance: float, threshold: float) -> float:
    if threshold <= 0:
        return 0.0
    confidence = 0.95 - (distance / threshold) * 0.15
    return max(0.80, min(0.98, confidence))


MATCH_TYPE_PRIORITY = {
    "content_hash": 50,
    "identical_url": 45,
    "identical_local_path": 44,
    "face_embedding": 40,
    "perceptual_hash": 30,
}


def add_candidate(
    candidates: dict[tuple[str, str], DuplicateCandidate],
    row_a: dict[str, Any],
    row_b: dict[str, Any],
    *,
    match_type: str,
    confidence: float,
    evidence_update: dict[str, Any],
    fingerprint_a: ImageFingerprint | None = None,
    fingerprint_b: ImageFingerprint | None = None,
) -> None:
    first_id, second_id = pair_key(row_a, row_b)
    if first_id == second_id:
        return

    if first_id == (clean_text(row_a.get("id")) or source_image_id_for(row_a)):
        left_row, right_row = row_a, row_b
        left_fp, right_fp = fingerprint_a, fingerprint_b
    else:
        left_row, right_row = row_b, row_a
        left_fp, right_fp = fingerprint_b, fingerprint_a

    key = (first_id, second_id)
    image_a_id = source_image_id_for(left_row, left_fp)
    image_b_id = source_image_id_for(right_row, right_fp)

    if key not in candidates:
        evidence = {
            "match_types": [],
            "source_a": evidence_source(left_row, image_a_id),
            "source_b": evidence_source(right_row, image_b_id),
        }
        evidence.update(evidence_update)
        candidates[key] = DuplicateCandidate(
            candidate_key=candidate_key_for(left_row, right_row),
            source_fencer_a_id=str(first_id),
            source_fencer_b_id=str(second_id),
            source_image_a_id=image_a_id,
            source_image_b_id=image_b_id,
            image_a_url=display_image_url(left_row),
            image_b_url=display_image_url(right_row),
            match_type=match_type,
            confidence=confidence,
            evidence=evidence,
        )

    candidate = candidates[key]
    if match_type not in candidate.evidence["match_types"]:
        candidate.evidence["match_types"].append(match_type)
    candidate.confidence = max(candidate.confidence, confidence)
    if MATCH_TYPE_PRIORITY.get(match_type, 0) > MATCH_TYPE_PRIORITY.get(candidate.match_type, 0):
        candidate.match_type = match_type
    for evidence_key, evidence_value in evidence_update.items():
        candidate.evidence[evidence_key] = evidence_value


def grouped_pairs(rows: list[dict[str, Any]], key_func: Callable[[dict[str, Any]], str | None]):
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = key_func(row)
        if key:
            groups.setdefault(key, []).append(row)
    for key, group in groups.items():
        if len(group) < 2:
            continue
        for index, row_a in enumerate(group):
            for row_b in group[index + 1 :]:
                yield key, row_a, row_b


def load_default_embedding_provider() -> EmbeddingProvider | None:
    try:
        import face_recognition  # type: ignore
    except Exception:
        return None

    def provider(_record: dict[str, Any], image_bytes: bytes) -> Sequence[float] | None:
        image = face_recognition.load_image_file(io.BytesIO(image_bytes))
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            return None
        return [float(value) for value in encodings[0]]

    return provider


def find_duplicate_candidates(
    rows: list[dict[str, Any]],
    *,
    hash_distance_threshold: int = DEFAULT_HASH_DISTANCE_THRESHOLD,
    color_distance_threshold: float = DEFAULT_COLOR_DISTANCE_THRESHOLD,
    enable_face_embeddings: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_distance_threshold: float = DEFAULT_EMBEDDING_DISTANCE_THRESHOLD,
    allow_remote_images: bool = False,
    remote_fetcher: Callable[[str], bytes] = fetch_remote_image_bytes,
) -> DedupeResult:
    stats = DedupeStats(processed=len(rows))
    candidates: dict[tuple[str, str], DuplicateCandidate] = {}

    for url, row_a, row_b in grouped_pairs(rows, lambda row: normalize_url(row.get("image_url"))):
        add_candidate(
            candidates,
            row_a,
            row_b,
            match_type="identical_url",
            confidence=0.99,
            evidence_update={"identical_url": url},
        )

    for path, row_a, row_b in grouped_pairs(rows, lambda row: normalize_url(row.get("local_image_path"))):
        add_candidate(
            candidates,
            row_a,
            row_b,
            match_type="identical_local_path",
            confidence=0.98,
            evidence_update={"identical_local_image_path": path},
        )

    fingerprints = load_image_fingerprints(
        rows,
        stats,
        allow_remote_images=allow_remote_images,
        remote_fetcher=remote_fetcher,
    )
    by_normalized_hash: dict[str, list[ImageFingerprint]] = {}
    for fingerprint in fingerprints:
        by_normalized_hash.setdefault(fingerprint.normalized_sha256, []).append(fingerprint)

    for normalized_hash, group in by_normalized_hash.items():
        if len(group) < 2:
            continue
        for index, fp_a in enumerate(group):
            for fp_b in group[index + 1 :]:
                add_candidate(
                    candidates,
                    fp_a.row,
                    fp_b.row,
                    match_type="content_hash",
                    confidence=1.0,
                    evidence_update={
                        "normalized_sha256": normalized_hash,
                        "byte_sha256_a": fp_a.byte_sha256,
                        "byte_sha256_b": fp_b.byte_sha256,
                        "dimensions_a": [fp_a.width, fp_a.height],
                        "dimensions_b": [fp_b.width, fp_b.height],
                    },
                    fingerprint_a=fp_a,
                    fingerprint_b=fp_b,
                )

    for index, fp_a in enumerate(fingerprints):
        for fp_b in fingerprints[index + 1 :]:
            if fp_a.normalized_sha256 == fp_b.normalized_sha256:
                hash_distance = 0
                color_distance = 0.0
            else:
                hash_distance = hamming_distance(fp_a.average_hash, fp_b.average_hash)
                color_distance = rgb_distance(fp_a.mean_rgb, fp_b.mean_rgb)
            if hash_distance <= hash_distance_threshold and color_distance <= color_distance_threshold:
                add_candidate(
                    candidates,
                    fp_a.row,
                    fp_b.row,
                    match_type="perceptual_hash",
                    confidence=confidence_for_perceptual(hash_distance, color_distance),
                    evidence_update={
                        "hash_distance": hash_distance,
                        "color_distance": round(color_distance, 4),
                        "average_hash_a": f"{fp_a.average_hash:016x}",
                        "average_hash_b": f"{fp_b.average_hash:016x}",
                    },
                    fingerprint_a=fp_a,
                    fingerprint_b=fp_b,
                )

    if enable_face_embeddings:
        provider = embedding_provider or load_default_embedding_provider()
        if provider is None:
            stats.embedding_skipped = len(fingerprints)
        else:
            embeddings: list[tuple[ImageFingerprint, Sequence[float]]] = []
            for fingerprint in fingerprints:
                try:
                    embedding = provider(fingerprint.row, fingerprint.image_bytes)
                except Exception as exc:
                    stats.image_errors.append(
                        {"fencer_id": fingerprint.fencer_id, "reason": f"embedding_error:{exc}"}
                    )
                    continue
                if embedding is None:
                    stats.embedding_skipped += 1
                    continue
                embeddings.append((fingerprint, embedding))
            for index, (fp_a, emb_a) in enumerate(embeddings):
                for fp_b, emb_b in embeddings[index + 1 :]:
                    distance = embedding_distance(emb_a, emb_b)
                    if distance <= embedding_distance_threshold:
                        add_candidate(
                            candidates,
                            fp_a.row,
                            fp_b.row,
                            match_type="face_embedding",
                            confidence=confidence_for_embedding(distance, embedding_distance_threshold),
                            evidence_update={"embedding_distance": round(distance, 6)},
                            fingerprint_a=fp_a,
                            fingerprint_b=fp_b,
                        )

    result_candidates = sorted(candidates.values(), key=lambda item: item.candidate_key)
    for candidate in result_candidates:
        candidate.evidence["match_types"] = sorted(
            candidate.evidence["match_types"],
            key=lambda item: MATCH_TYPE_PRIORITY.get(item, 0),
            reverse=True,
        )
    stats.candidates = len(result_candidates)
    return DedupeResult(candidates=result_candidates, stats=stats)


def load_headshot_rows(client: Any, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    result = client.table("fs_fencers").select(FENCER_COLUMNS).limit(limit).execute()
    return result.data or []


def upsert_review_candidates(client: Any, candidates: Iterable[DuplicateCandidate]) -> int:
    written = 0
    for candidate in candidates:
        client.table(REVIEW_TABLE).upsert(
            candidate.to_review_row(),
            on_conflict="candidate_key",
        ).execute()
        written += 1
    return written


def run_dedupe(
    client: Any,
    *,
    limit: int = DEFAULT_LIMIT,
    enable_face_embeddings: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    allow_remote_images: bool = False,
) -> DedupeResult:
    rows = load_headshot_rows(client, limit=limit)
    result = find_duplicate_candidates(
        rows,
        enable_face_embeddings=enable_face_embeddings,
        embedding_provider=embedding_provider,
        allow_remote_images=allow_remote_images,
    )
    result.stats.upserted = upsert_review_candidates(client, result.candidates)
    return result


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    if not supabase:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_run = get_state(SOURCE, "last_run")
        if previous_run:
            print(f"Previous headshot dedupe run: {previous_run}")

        result = run_dedupe(
            supabase,
            limit=DEFAULT_LIMIT,
            enable_face_embeddings=env_flag("HEADSHOT_DEDUPE_ENABLE_FACE_EMBEDDINGS"),
            allow_remote_images=env_flag("HEADSHOT_DEDUPE_ALLOW_REMOTE_IMAGES"),
        )
        completed_at = datetime.now(UTC).isoformat()
        set_state(
            SOURCE,
            "last_run",
            {
                "completed_at": completed_at,
                "processed": result.stats.processed,
                "candidates": result.stats.candidates,
                "upserted": result.stats.upserted,
                "skipped": result.stats.skipped,
            },
        )
        run_log.complete(
            written=result.stats.upserted,
            failed=len(result.stats.image_errors),
            skipped=result.stats.skipped + result.stats.embedding_skipped,
            metadata={
                "processed": result.stats.processed,
                "images_loaded": result.stats.images_loaded,
                "candidates": result.stats.candidates,
                "image_errors": result.stats.image_errors[:50],
                "embedding_skipped": result.stats.embedding_skipped,
                "privacy": PRIVACY_NOTES,
            },
        )
        print(
            "Headshot dedupe complete - "
            f"processed={result.stats.processed}, "
            f"candidates={result.stats.candidates}, "
            f"upserted={result.stats.upserted}, "
            f"skipped={result.stats.skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
