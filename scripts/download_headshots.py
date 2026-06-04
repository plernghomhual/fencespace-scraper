from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "download_headshots"
BUCKET_NAME = "fencer-headshots"
PENDING_COLUMNS = "id,fie_id,name,country,headshot_url,local_image_path,metadata,world_rank"
YOUTUBE_COLUMNS = "id,name,country,metadata,world_rank"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

DEFAULT_OUTPUT_DIR = Path(os.environ.get("HEADSHOT_OUTPUT_DIR", "headshots"))
MAX_FENCERS = int(os.environ.get("HEADSHOT_LIMIT", "1000"))
YOUTUBE_FENCER_LIMIT = int(os.environ.get("YOUTUBE_FENCER_LIMIT", "100"))
YOUTUBE_MAX_RESULTS = int(os.environ.get("YOUTUBE_MAX_RESULTS", "5"))
YOUTUBE_QUERY_MULTIPLIER = 24
DOWNLOAD_TIMEOUT_SECONDS = float(os.environ.get("HEADSHOT_TIMEOUT_SECONDS", "30"))
DOWNLOAD_DELAY_SECONDS = 1.0
MAX_IMAGE_BYTES = int(os.environ.get("HEADSHOT_MAX_IMAGE_BYTES", str(12 * 1024 * 1024)))
OUTPUT_SIZE = (400, 400)

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


class DownloadFailure(Exception):
    def __init__(self, reason: str, status_code: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


@dataclass
class ProcessStats:
    processed: int = 0
    written: int = 0
    failed: int = 0
    skipped: int = 0
    storage_mode: str = "supabase"


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def load_pending_fencers(client: Any, limit: int = MAX_FENCERS) -> list[dict[str, Any]]:
    result = (
        client.table("fs_fencers")
        .select(PENDING_COLUMNS)
        .filter("headshot_url", "not.is", "null")
        .or_("local_image_path.is.null,local_image_path.eq.")
        .limit(limit)
        .execute()
    )
    return result.data or []


def load_youtube_fencers(client: Any, limit: int = YOUTUBE_FENCER_LIMIT) -> list[dict[str, Any]]:
    result = (
        client.table("fs_fencers")
        .select(YOUTUBE_COLUMNS)
        .filter("world_rank", "not.is", "null")
        .order("world_rank", desc=False)
        .limit(limit * YOUTUBE_QUERY_MULTIPLIER)
        .execute()
    )
    rows = result.data or []
    fencers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        name = clean_text(row.get("name"))
        if not name:
            continue
        country = clean_text(row.get("country")) or ""
        key = (name.lower(), country.lower())
        if key in seen:
            continue
        seen.add(key)
        fencers.append(row)
        if len(fencers) >= limit:
            break
    return fencers


def _lanczos_filter():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def resize_center_crop(image_bytes: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if getattr(image, "is_animated", False):
                image.seek(0)
            image = ImageOps.fit(
                image.convert("RGB"),
                OUTPUT_SIZE,
                method=_lanczos_filter(),
                centering=(0.5, 0.5),
            )
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise DownloadFailure(f"invalid_image:{exc}") from exc


def download_and_resize_image(session: requests.Session, url: str) -> bytes:
    try:
        response = session.get(url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise DownloadFailure(f"request_error:{exc}") from exc

    if response.status_code != 200:
        raise DownloadFailure(f"http_{response.status_code}", response.status_code)

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if not content_type.startswith("image/"):
        raise DownloadFailure(f"non_image_content_type:{content_type or 'missing'}", response.status_code)

    if not response.content:
        raise DownloadFailure("empty_image", response.status_code)
    if len(response.content) > MAX_IMAGE_BYTES:
        raise DownloadFailure("image_too_large", response.status_code)

    return resize_center_crop(response.content)


def safe_path_part(value: Any, fallback: str) -> str:
    text = clean_text(value) or fallback
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-._")
    return text or fallback


def storage_path_for(fencer: dict[str, Any]) -> str:
    identifier = fencer.get("id") or fencer.get("fie_id") or fencer.get("name")
    return f"fencers/{safe_path_part(identifier, 'unknown')}.jpg"


def public_url_from_response(bucket: Any, storage_path: str) -> str:
    response = bucket.get_public_url(storage_path)
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict) and data.get("publicUrl"):
            return str(data["publicUrl"])
        if response.get("publicUrl"):
            return str(response["publicUrl"])
    public_url = getattr(response, "public_url", None) or getattr(response, "publicUrl", None)
    if public_url:
        return str(public_url)
    return str(response)


def upload_to_storage(client: Any, storage_path: str, image_bytes: bytes) -> str:
    bucket = client.storage.from_(BUCKET_NAME)
    bucket.upload(
        path=storage_path,
        file=image_bytes,
        file_options={
            "content-type": "image/jpeg",
            "cache-control": "31536000",
            "upsert": "true",
        },
    )
    return public_url_from_response(bucket, storage_path)


def save_local_image(output_dir: Path, storage_path: str, image_bytes: bytes) -> str:
    local_path = output_dir / storage_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(image_bytes)
    return str(local_path)


def update_fencer_local_image_path(client: Any, fencer_id: str, image_path: str) -> None:
    client.table("fs_fencers").update({"local_image_path": image_path}).eq("id", fencer_id).execute()


def process_headshots(
    client: Any,
    session: requests.Session,
    fencers: list[dict[str, Any]],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sleeper: Callable[[float], None] = time.sleep,
    use_storage: bool = True,
) -> ProcessStats:
    stats = ProcessStats(storage_mode="supabase" if use_storage else "local")
    storage_enabled = use_storage
    download_count = 0
    image_cache: dict[str, bytes] = {}
    failure_cache: dict[str, DownloadFailure] = {}

    for fencer in fencers:
        stats.processed += 1
        fencer_id = clean_text(fencer.get("id"))
        url = clean_text(fencer.get("headshot_url"))
        if not fencer_id or not url:
            stats.skipped += 1
            continue

        if url in image_cache:
            image_bytes = image_cache[url]
        elif url in failure_cache:
            stats.failed += 1
            print(f"  {fencer_id} - skipped headshot: {failure_cache[url].reason}")
            continue
        else:
            if download_count > 0:
                sleeper(DOWNLOAD_DELAY_SECONDS)
            download_count += 1

            try:
                image_bytes = download_and_resize_image(session, url)
                image_cache[url] = image_bytes
            except DownloadFailure as exc:
                failure_cache[url] = exc
                stats.failed += 1
                print(f"  {fencer_id} - skipped headshot: {exc.reason}")
                continue

        storage_path = storage_path_for(fencer)
        try:
            if storage_enabled:
                try:
                    image_path = upload_to_storage(client, storage_path, image_bytes)
                    mode = "supabase"
                except Exception as exc:
                    print(f"  Storage unavailable, using local headshots/: {exc}")
                    storage_enabled = False
                    image_path = save_local_image(output_dir, storage_path, image_bytes)
                    mode = "local"
            else:
                image_path = save_local_image(output_dir, storage_path, image_bytes)
                mode = "local"

            update_fencer_local_image_path(client, fencer_id, image_path)
            stats.written += 1
            stats.storage_mode = mode if stats.storage_mode == "supabase" or mode == "local" else stats.storage_mode
        except Exception as exc:
            stats.failed += 1
            print(f"  {fencer_id} - failed to store/update headshot: {exc}")

    return stats


def search_youtube_videos(
    session: requests.Session,
    fencer_name: str,
    api_key: str,
    *,
    max_results: int = YOUTUBE_MAX_RESULTS,
) -> list[str]:
    response = session.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "q": f"fencing {fencer_name}",
            "type": "video",
            "maxResults": max_results,
            "key": api_key,
        },
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        print(f"  YouTube search failed for {fencer_name}: HTTP {response.status_code}")
        return []
    data = response.json()
    video_ids: list[str] = []
    for item in data.get("items", []):
        item_id = item.get("id") or {}
        if item_id.get("kind") == "youtube#video" and item_id.get("videoId"):
            video_ids.append(str(item_id["videoId"]))
    return video_ids


def update_youtube_metadata(client: Any, fencer: dict[str, Any], video_ids: list[str]) -> bool:
    fencer_id = clean_text(fencer.get("id"))
    if not fencer_id or not video_ids:
        return False
    metadata = ensure_metadata(fencer.get("metadata"))
    metadata["youtube_videos"] = video_ids
    metadata["youtube_videos_scraped_at"] = datetime.now(timezone.utc).isoformat()
    client.table("fs_fencers").update({"metadata": metadata}).eq("id", fencer_id).execute()
    return True


def discover_youtube_videos(
    client: Any,
    session: requests.Session,
    api_key: str | None,
    *,
    limit: int = YOUTUBE_FENCER_LIMIT,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, int, int]:
    if not api_key:
        # YouTube Data API search requires YOUTUBE_API_KEY; without it, offline
        # scraper runs cannot discover videos and should not burn unauthenticated requests.
        print("Skipping YouTube discovery: YOUTUBE_API_KEY is not set.")
        return 0, 0, 0

    written = failed = skipped = 0
    fencers = load_youtube_fencers(client, limit=limit)
    for index, fencer in enumerate(fencers):
        name = clean_text(fencer.get("name"))
        if not name:
            skipped += 1
            continue
        if index > 0:
            sleeper(0.1)
        try:
            videos = search_youtube_videos(session, name, api_key)
            if update_youtube_metadata(client, fencer, videos):
                written += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            print(f"  YouTube discovery failed for {name}: {exc}")
    return written, failed, skipped


def main() -> None:
    if not supabase:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger(SOURCE).start()
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        previous_run = get_state(SOURCE, "last_run")
        print(f"Fencer media pipeline starting - {datetime.now(timezone.utc).isoformat()}")
        if previous_run:
            print(f"Previous run: {previous_run}")

        fencers = load_pending_fencers(supabase, limit=MAX_FENCERS)
        print(f"Found {len(fencers)} fencers with remote headshots and no local image")
        headshot_stats = process_headshots(supabase, session, fencers)

        youtube_written, youtube_failed, youtube_skipped = discover_youtube_videos(
            supabase,
            session,
            os.environ.get("YOUTUBE_API_KEY"),
            limit=YOUTUBE_FENCER_LIMIT,
        )

        completed_at = datetime.now(timezone.utc).isoformat()
        set_state(
            SOURCE,
            "last_run",
            {
                "completed_at": completed_at,
                "headshots_written": headshot_stats.written,
                "headshots_failed": headshot_stats.failed,
                "youtube_written": youtube_written,
            },
        )
        run_log.complete(
            written=headshot_stats.written + youtube_written,
            failed=headshot_stats.failed + youtube_failed,
            skipped=headshot_stats.skipped + youtube_skipped,
            metadata={
                "headshots": headshot_stats.__dict__,
                "youtube_written": youtube_written,
                "youtube_failed": youtube_failed,
                "youtube_skipped": youtube_skipped,
            },
        )
        print(
            "Fencer media pipeline complete - "
            f"headshots_written={headshot_stats.written}, "
            f"headshots_failed={headshot_stats.failed}, "
            f"headshots_skipped={headshot_stats.skipped}, "
            f"storage_mode={headshot_stats.storage_mode}, "
            f"youtube_written={youtube_written}, youtube_failed={youtube_failed}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
