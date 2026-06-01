import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import download_headshots as dh


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, rows):
        self.client = client
        self.rows = rows
        self.operations = []
        self.payload = None

    def select(self, columns):
        self.operations.append(("select", columns))
        return self

    def filter(self, column, operator, criteria):
        self.operations.append(("filter", column, operator, criteria))
        return self

    def or_(self, filters):
        self.operations.append(("or", filters))
        return self

    def not_(self):
        return self

    def is_(self, column, value):
        self.operations.append(("is", column, value))
        return self

    def order(self, column, desc=False):
        self.operations.append(("order", column, desc))
        return self

    def limit(self, count):
        self.operations.append(("limit", count))
        return self

    def update(self, payload):
        self.payload = payload
        self.operations.append(("update", payload))
        return self

    def eq(self, column, value):
        self.operations.append(("eq", column, value))
        self.client.updates.append((self.client.current_table, column, value, self.payload))
        return self

    def execute(self):
        self.client.last_operations = list(self.operations)
        return FakeResult(self.rows)


class FakeBucket:
    def __init__(self, fail_upload=False):
        self.fail_upload = fail_upload
        self.uploads = []

    def upload(self, path, file, file_options=None):
        if self.fail_upload:
            raise RuntimeError("storage bucket unavailable")
        self.uploads.append((path, file, file_options or {}))
        return {"path": path}

    def get_public_url(self, path):
        return f"https://storage.example/{path}"


class FakeStorage:
    def __init__(self, fail_upload=False):
        self.bucket = FakeBucket(fail_upload=fail_upload)
        self.bucket_names = []

    def from_(self, bucket_name):
        self.bucket_names.append(bucket_name)
        return self.bucket


class FakeClient:
    def __init__(self, rows=None, fail_upload=False):
        self.rows = rows or []
        self.storage = FakeStorage(fail_upload=fail_upload)
        self.updates = []
        self.current_table = None
        self.last_operations = []

    def table(self, table_name):
        self.current_table = table_name
        return FakeTable(self, self.rows)


class FakeResponse:
    def __init__(self, status_code, content_type, content=b"", payload=None):
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.content = content
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def image_bytes(size=(800, 600), color=(20, 40, 200)):
    from PIL import Image

    image = Image.new("RGB", size, color)
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def uploaded_image_size(uploaded_bytes):
    from PIL import Image

    with Image.open(io.BytesIO(uploaded_bytes)) as image:
        return image.size


def test_load_pending_fencers_queries_headshots_missing_local_path():
    client = FakeClient(rows=[{"id": "f1"}])

    rows = dh.load_pending_fencers(client, limit=25)

    assert rows == [{"id": "f1"}]
    assert ("select", "id,fie_id,name,country,headshot_url,local_image_path,metadata,world_rank") in client.last_operations
    assert ("filter", "headshot_url", "not.is", "null") in client.last_operations
    assert ("or", "local_image_path.is.null,local_image_path.eq.") in client.last_operations
    assert ("limit", 25) in client.last_operations


def test_process_headshots_uploads_resized_image_and_updates_public_url(tmp_path):
    client = FakeClient()
    session = FakeSession([FakeResponse(200, "image/jpeg", image_bytes())])
    fencer = {
        "id": "fencer-1",
        "name": "Aldo Montano",
        "headshot_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Aldo_Montano.jpg",
        "metadata": {},
    }

    stats = dh.process_headshots(
        client,
        session,
        [fencer],
        output_dir=tmp_path / "headshots",
        sleeper=lambda _: None,
    )

    assert stats.written == 1
    assert stats.failed == 0
    assert stats.storage_mode == "supabase"
    assert client.storage.bucket_names == ["fencer-headshots"]
    upload_path, uploaded_bytes, options = client.storage.bucket.uploads[0]
    assert upload_path == "fencers/fencer-1.jpg"
    assert uploaded_image_size(uploaded_bytes) == (400, 400)
    assert options["content-type"] == "image/jpeg"
    assert options["upsert"] == "true"
    assert client.updates == [
        (
            "fs_fencers",
            "id",
            "fencer-1",
            {"local_image_path": "https://storage.example/fencers/fencer-1.jpg"},
        )
    ]


def test_process_headshots_falls_back_to_local_storage_when_upload_fails(tmp_path):
    client = FakeClient(fail_upload=True)
    session = FakeSession([FakeResponse(200, "image/png", image_bytes(size=(300, 800)))])
    fencer = {"id": "fencer-2", "name": "Lee Kiefer", "headshot_url": "https://example.test/lee.png"}

    stats = dh.process_headshots(
        client,
        session,
        [fencer],
        output_dir=tmp_path / "headshots",
        sleeper=lambda _: None,
    )

    local_path = tmp_path / "headshots" / "fencers" / "fencer-2.jpg"
    assert stats.written == 1
    assert stats.storage_mode == "local"
    assert local_path.exists()
    assert uploaded_image_size(local_path.read_bytes()) == (400, 400)
    assert client.updates == [
        ("fs_fencers", "id", "fencer-2", {"local_image_path": str(local_path)})
    ]


def test_process_headshots_skips_http_errors_and_non_images(tmp_path):
    client = FakeClient()
    session = FakeSession(
        [
            FakeResponse(404, "text/html", b"deleted commons file"),
            FakeResponse(200, "text/html", b"<html>not an image</html>"),
        ]
    )
    fencers = [
        {"id": "deleted", "name": "Deleted File", "headshot_url": "https://commons.example/deleted.jpg"},
        {"id": "html", "name": "HTML", "headshot_url": "https://example.test/not-image"},
    ]

    stats = dh.process_headshots(
        client,
        session,
        fencers,
        output_dir=tmp_path / "headshots",
        sleeper=lambda _: None,
    )

    assert stats.written == 0
    assert stats.failed == 2
    assert client.storage.bucket.uploads == []
    assert client.updates == []


def test_process_headshots_rate_limits_external_downloads(tmp_path):
    client = FakeClient()
    session = FakeSession(
        [
            FakeResponse(200, "image/jpeg", image_bytes()),
            FakeResponse(200, "image/jpeg", image_bytes()),
        ]
    )
    sleeps = []

    dh.process_headshots(
        client,
        session,
        [
            {"id": "f1", "name": "One", "headshot_url": "https://example.test/one.jpg"},
            {"id": "f2", "name": "Two", "headshot_url": "https://example.test/two.jpg"},
        ],
        output_dir=tmp_path / "headshots",
        sleeper=sleeps.append,
    )

    assert sleeps == [dh.DOWNLOAD_DELAY_SECONDS]
    assert len(session.calls) == 2


def test_duplicate_headshot_urls_are_downloaded_once_but_update_each_fencer(tmp_path):
    client = FakeClient()
    session = FakeSession([FakeResponse(200, "image/jpeg", image_bytes())])
    sleeps = []

    stats = dh.process_headshots(
        client,
        session,
        [
            {"id": "f1", "name": "Duplicate One", "headshot_url": "https://example.test/shared.jpg"},
            {"id": "f2", "name": "Duplicate Two", "headshot_url": "https://example.test/shared.jpg"},
        ],
        output_dir=tmp_path / "headshots",
        sleeper=sleeps.append,
    )

    assert stats.written == 2
    assert len(session.calls) == 1
    assert sleeps == []
    assert len(client.storage.bucket.uploads) == 2
    assert [update[2] for update in client.updates] == ["f1", "f2"]


def test_youtube_search_extracts_video_ids_and_metadata_update_merges_existing_metadata():
    client = FakeClient()
    session = FakeSession(
        [
            FakeResponse(
                200,
                "application/json",
                payload={
                    "items": [
                        {"id": {"kind": "youtube#video", "videoId": "abc123"}},
                        {"id": {"kind": "youtube#channel", "channelId": "ignored"}},
                        {"id": {"kind": "youtube#video", "videoId": "def456"}},
                    ]
                },
            )
        ]
    )

    videos = dh.search_youtube_videos(session, "Lee Kiefer", "test-key", max_results=5)
    dh.update_youtube_metadata(
        client,
        {"id": "fencer-3", "metadata": {"wikidata_id": "Q123"}},
        videos,
    )

    assert videos == ["abc123", "def456"]
    assert session.calls[0][0] == dh.YOUTUBE_SEARCH_URL
    assert session.calls[0][1]["params"]["q"] == "fencing Lee Kiefer"
    assert client.updates[0][3]["metadata"]["wikidata_id"] == "Q123"
    assert client.updates[0][3]["metadata"]["youtube_videos"] == ["abc123", "def456"]


def test_youtube_discovery_without_api_key_does_not_call_external_api():
    client = FakeClient(rows=[{"id": "fencer-4", "name": "Arianna Errigo", "metadata": {}}])
    session = FakeSession([])

    result = dh.discover_youtube_videos(client, session, api_key=None, sleeper=lambda _: None)

    assert result == (0, 0, 0)
    assert session.calls == []
    assert client.updates == []
