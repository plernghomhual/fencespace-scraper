import os
from datetime import datetime, timezone
from typing import Any

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

_client = None


def _get_client():
    global _client
    if _client is None and SUPABASE_URL and SUPABASE_KEY:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def get_state(source: str, key: str) -> Any:
    client = _get_client()
    if not client:
        return None
    try:
        result = (
            client.table("fs_scraper_state")
            .select("value")
            .eq("source", source)
            .eq("key", key)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("value")
    except Exception as exc:
        print(f"[scraper_state] get_state({source!r}, {key!r}) failed: {exc}")
    return None


def set_state(source: str, key: str, value: Any) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.table("fs_scraper_state").upsert(
            {
                "source": source,
                "key": key,
                "value": value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="source,key",
        ).execute()
    except Exception as exc:
        print(f"[scraper_state] set_state({source!r}, {key!r}) failed: {exc}")


def get_cursor(source: str, default: int = 1) -> int:
    state = get_state(source, "cursor")
    if isinstance(state, dict):
        try:
            return int(state.get("page", default))
        except (TypeError, ValueError):
            pass
    return default


def set_cursor(source: str, page: int, extra: dict | None = None) -> None:
    value: dict = {"page": page, "updated_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        value.update(extra)
    set_state(source, "cursor", value)


def reset_cursor(source: str) -> None:
    set_cursor(source, 1)
