from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T00:00:00+00:00"
ALICE_CANONICAL = "00000000-0000-0000-0000-0000000000a1"
ALICE_DUPLICATE = "00000000-0000-0000-0000-0000000000a2"
BOB = "00000000-0000-0000-0000-0000000000b1"
CAROL = "00000000-0000-0000-0000-0000000000c1"
DANA = "00000000-0000-0000-0000-0000000000d1"
ERIN = "00000000-0000-0000-0000-0000000000e1"


def test_build_leaderboard_dedupes_platform_handles_and_excludes_private_missing_accounts():
    from compute_social_leaderboard import build_leaderboard_rows, build_identity_map

    identity_map = build_identity_map(
        [
            {
                "canonical_id": ALICE_CANONICAL,
                "fs_fencer_row_ids": [ALICE_CANONICAL, ALICE_DUPLICATE],
            }
        ]
    )
    social_rows = [
        {
            "fencer_id": ALICE_DUPLICATE,
            "platform": "Instagram",
            "handle": "@Lee_Kiefer",
            "url": "https://www.instagram.com/Lee_Kiefer/",
            "source": "wikidata",
            "verified": True,
            "metadata": {
                "follower_count": "120000",
                "mention_count": 4,
                "collected_at": "2026-06-01T12:00:00+00:00",
            },
        },
        {
            "fencer_id": ALICE_CANONICAL,
            "platform": "ig",
            "handle": "lee_kiefer",
            "url": "https://instagram.com/lee_kiefer/?utm_source=duplicate",
            "source": "wikidata",
            "verified": True,
            "metadata": {
                "follower_count": 119000,
                "mention_count": 999,
                "collected_at": "2026-05-01T12:00:00+00:00",
            },
        },
        {
            "fencer_id": BOB,
            "platform": "Twitter",
            "handle": "@private-bob",
            "url": "https://x.com/private-bob",
            "source": "profile_probe",
            "verified": False,
            "metadata": {"follower_count": 999999, "account_status": "private"},
        },
        {
            "fencer_id": CAROL,
            "platform": "X",
            "handle": "@verified_carol",
            "url": "https://twitter.com/verified_carol",
            "source": "profile_probe",
            "verified": False,
            "metadata": {
                "followers": 45000,
                "mentions": 12,
                "status": "private",
                "publicly_verified": True,
                "collected_at": "2026-06-01T00:00:00+00:00",
            },
        },
        {
            "fencer_id": DANA,
            "platform": "TikTok",
            "handle": None,
            "url": "https://www.tiktok.com/",
            "source": "profile_probe",
            "verified": True,
            "metadata": {"follower_count": 100, "status": "missing"},
        },
    ]

    rows, skipped = build_leaderboard_rows(
        social_rows,
        identity_map=identity_map,
        computed_at=NOW,
    )

    by_key = {(row["platform"], row["normalized_handle"]): row for row in rows}

    assert skipped == 2
    assert set(by_key) == {("instagram", "lee_kiefer"), ("twitter", "verified_carol")}

    alice = by_key[("instagram", "lee_kiefer")]
    assert alice["fencer_id"] == ALICE_CANONICAL
    assert alice["source_platform"] == "instagram"
    assert alice["handle"] == "Lee_Kiefer"
    assert alice["follower_count"] == 120000
    assert alice["mention_count"] == 4
    assert alice["sources"] == ["wikidata"]

    carol = by_key[("twitter", "verified_carol")]
    assert carol["fencer_id"] == CAROL
    assert carol["follower_count"] == 45000
    assert carol["mention_count"] == 12


def test_stale_indicators_label_old_and_missing_collection_dates():
    from compute_social_leaderboard import build_leaderboard_rows

    social_rows = [
        {
            "fencer_id": ALICE_CANONICAL,
            "platform": "instagram",
            "handle": "fresh_count",
            "url": "https://instagram.com/fresh_count",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 10, "collected_at": "2026-06-01"},
        },
        {
            "fencer_id": BOB,
            "platform": "instagram",
            "handle": "old_count",
            "url": "https://instagram.com/old_count",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 20, "collected_at": "2026-04-01T00:00:00+00:00"},
        },
        {
            "fencer_id": CAROL,
            "platform": "instagram",
            "handle": "undated_count",
            "url": "https://instagram.com/undated_count",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 30},
        },
    ]

    rows, skipped = build_leaderboard_rows(
        social_rows,
        computed_at=NOW,
        stale_after_days=30,
    )
    by_handle = {row["normalized_handle"]: row for row in rows}

    assert skipped == 0
    assert by_handle["fresh_count"]["is_stale"] is False
    assert by_handle["fresh_count"]["stale_reason"] is None
    assert by_handle["old_count"]["is_stale"] is True
    assert by_handle["old_count"]["days_since_collected"] == 62
    assert by_handle["old_count"]["stale_reason"] == "follower_count_older_than_30_days"
    assert by_handle["undated_count"]["is_stale"] is True
    assert by_handle["undated_count"]["stale_reason"] == "missing_collection_date"


def test_rankings_use_deterministic_tie_breaks():
    from compute_social_leaderboard import build_leaderboard_rows

    social_rows = [
        {
            "fencer_id": ALICE_CANONICAL,
            "platform": "instagram",
            "handle": "beta",
            "url": "https://instagram.com/beta",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 1000, "mention_count": 5, "collected_at": "2026-06-01"},
        },
        {
            "fencer_id": BOB,
            "platform": "instagram",
            "handle": "alpha",
            "url": "https://instagram.com/alpha",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 1000, "mention_count": 8, "collected_at": "2026-06-01"},
        },
        {
            "fencer_id": CAROL,
            "platform": "instagram",
            "handle": "charlie",
            "url": "https://instagram.com/charlie",
            "source": "metrics",
            "verified": True,
            "metadata": {"follower_count": 900, "mention_count": 20, "collected_at": "2026-06-01"},
        },
    ]

    rows, skipped = build_leaderboard_rows(social_rows, computed_at=NOW)
    by_handle = {row["normalized_handle"]: row for row in rows}

    assert skipped == 0
    assert by_handle["alpha"]["follower_rank"] == 1
    assert by_handle["beta"]["follower_rank"] == 2
    assert by_handle["charlie"]["follower_rank"] == 3
    assert by_handle["charlie"]["mention_rank"] == 1
    assert by_handle["alpha"]["mention_rank"] == 2
    assert by_handle["beta"]["mention_rank"] == 3


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def limit(self, _n):
        return self

    def upsert(self, rows, on_conflict):
        self.pending_upsert = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.pending_upsert,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult([])
        if self.name not in self.client.tables:
            raise RuntimeError(f"missing table {self.name}")
        end = self.range_end if self.range_end is not None else len(self.client.tables[self.name]) - 1
        return FakeResult(self.client.tables[self.name][self.range_start : end + 1])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_social_leaderboard_uses_stored_rows_when_provider_is_missing():
    from compute_social_leaderboard import compute_social_leaderboard

    client = FakeSupabase(
        {
            "fs_fencer_social_media": [
                {
                    "fencer_id": ERIN,
                    "platform": "Instagram",
                    "handle": "@erin_fencer",
                    "url": "https://instagram.com/erin_fencer",
                    "source": "public_snapshot",
                    "verified": True,
                    "metadata": {
                        "follower_count": 7000,
                        "mention_count": 9,
                        "collected_at": "2026-06-01T00:00:00+00:00",
                    },
                },
                {
                    "fencer_id": DANA,
                    "platform": "TikTok",
                    "handle": "@unmeasured_dana",
                    "url": "https://www.tiktok.com/@unmeasured_dana",
                    "source": "profile_probe",
                    "verified": True,
                    "metadata": {},
                },
            ],
            "fs_fencer_identities": [],
            "fs_fencer_social_leaderboard": [],
        }
    )

    summary = compute_social_leaderboard(
        client=client,
        providers={},
        computed_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "read": 2,
        "written": 1,
        "failed": 0,
        "skipped": 1,
        "identity_rows": 0,
        "missing_provider": 1,
    }
    assert ("fs_fencer_social_media", "id,fencer_id,platform,handle,url,source,verified,metadata,created_at") in client.selects
    assert ("fs_fencer_social_leaderboard", "platform") in client.selects
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_fencer_social_leaderboard"
    assert client.upserts[0]["on_conflict"] == "platform,normalized_handle"
    assert client.upserts[0]["rows"][0]["normalized_handle"] == "erin_fencer"


def test_social_leaderboard_migration_defines_rankings_and_stale_columns():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_social_leaderboard.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_social_leaderboard" in normalized
    assert "primary key (platform, normalized_handle)" in normalized
    assert "source_platform" in normalized
    assert "follower_rank" in normalized
    assert "mention_rank" in normalized
    assert "is_stale" in normalized
    assert "stale_reason" in normalized
    assert "alter table public.fs_fencer_social_leaderboard enable row level security" in normalized
