import os
from datetime import UTC, datetime, timezone

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


class ScraperRunLogger:
    def __init__(self, module: str):
        self.module = module
        self.started_at = datetime.now(UTC).isoformat()
        self.run_id = None
        self._client = None

    def _get_client(self):
        if self._client is None and SUPABASE_URL and SUPABASE_KEY:
            self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return self._client

    def start(self) -> "ScraperRunLogger":
        try:
            client = self._get_client()
            if not client:
                return self
            result = client.table("fs_scraper_runs").insert({
                "module": self.module,
                "started_at": self.started_at,
                "status": "running",
            }).execute()
            if result.data:
                self.run_id = result.data[0].get("id")
        except Exception as exc:
            print(f"[run_logger] Could not start run log: {exc}")
        return self

    def complete(self, *, written: int = 0, failed: int = 0, skipped: int = 0, metadata: dict | None = None):
        if not self.run_id:
            return
        try:
            client = self._get_client()
            if not client:
                return
            status = "completed_with_errors" if failed > 0 else "completed"
            client.table("fs_scraper_runs").update({
                "completed_at": datetime.now(UTC).isoformat(),
                "status": status,
                "written": written,
                "failed": failed,
                "skipped": skipped,
                "metadata": metadata or {},
            }).eq("id", self.run_id).execute()
        except Exception as exc:
            print(f"[run_logger] Could not complete run log: {exc}")

    def error(self, exc_str: str):
        if not self.run_id:
            return
        try:
            client = self._get_client()
            if not client:
                return
            client.table("fs_scraper_runs").update({
                "completed_at": datetime.now(UTC).isoformat(),
                "status": "error",
                "metadata": {"error": str(exc_str)[:1000]},
            }).eq("id", self.run_id).execute()
        except Exception as exc:
            print(f"[run_logger] Could not write error log: {exc}")
