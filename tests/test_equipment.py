import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ROOT = Path(__file__).resolve().parents[1]


def test_extracts_fie_profile_equipment_mentions_with_types():
    from scrape_equipment import extract_equipment_mentions

    html = """
    <html><body>
      <h1>Lee Kiefer</h1>
      <section>
        <h2>Equipment</h2>
        <p>Lee Kiefer is sponsored by Absolute Fencing.</p>
        <p>She wears a Leon Paul mask and uses a PBT weapon.</p>
      </section>
    </body></html>
    """

    mentions = extract_equipment_mentions(html, fencer_name="Lee Kiefer", source="fie_profile")
    by_brand = {mention.brand: mention for mention in mentions}

    assert by_brand["Absolute Fencing"].sponsor_name == "Absolute Fencing"
    assert by_brand["Absolute Fencing"].equipment_type is None
    assert by_brand["Absolute Fencing"].confidence == "high"
    assert by_brand["Leon Paul"].equipment_type == "mask"
    assert by_brand["PBT"].equipment_type == "weapon"


def test_extracts_wikipedia_bio_mentions_near_fencer_name_only():
    from scrape_equipment import extract_equipment_mentions

    bio = (
        "Lee Kiefer is an American foil fencer. Lee Kiefer has been an "
        "Absolute Fencing sponsored athlete and uses a Blue Gauntlet jacket. "
        "Another athlete, far from this biography, is sponsored by Allstar."
    )

    mentions = extract_equipment_mentions(bio, fencer_name="Lee Kiefer", source="wikipedia_bio")

    assert [(mention.brand, mention.equipment_type) for mention in mentions] == [
        ("Absolute Fencing", None),
        ("Blue Gauntlet", "jacket"),
    ]


def test_short_brand_aliases_require_equipment_or_sponsor_context():
    from scrape_equipment import extract_equipment_mentions

    text = (
        "Lee Kiefer said OK after warmups. Lee Kiefer selected an LP mask, "
        "an AF weapon, and a Blaise Freres jacket for the final."
    )

    mentions = extract_equipment_mentions(text, fencer_name="Lee Kiefer", source="federation_profile")
    by_brand = {mention.brand: mention for mention in mentions}

    assert "OK" not in by_brand
    assert by_brand["Leon Paul"].equipment_type == "mask"
    assert by_brand["Absolute Fencing"].equipment_type == "weapon"
    assert by_brand["Blaise Frères"].equipment_type == "jacket"


def test_build_equipment_rows_deduplicates_and_uses_stable_ids():
    from scrape_equipment import build_equipment_rows, extract_equipment_mentions

    fencer = {"id": "fencer-1", "name": "Lee Kiefer"}
    text = "Lee Kiefer wears a Leon Paul mask. Lee Kiefer's LP mask is listed again."
    mentions = extract_equipment_mentions(
        text,
        fencer_name="Lee Kiefer",
        source="fie_profile",
        source_url="https://fie.org/athletes/123",
    )

    rows = build_equipment_rows(fencer, mentions)
    repeated_rows = build_equipment_rows(fencer, mentions)

    assert len(rows) == 1
    assert rows[0]["id"] == repeated_rows[0]["id"]
    assert rows[0]["fencer_id"] == "fencer-1"
    assert rows[0]["brand"] == "Leon Paul"
    assert rows[0]["equipment_type"] == "mask"
    assert rows[0]["source"] == "fie_profile"
    assert rows[0]["source_url"] == "https://fie.org/athletes/123"
    assert rows[0]["metadata"]["matched_alias"] in {"Leon Paul", "LP"}


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeSelectTable:
    def __init__(self, rows):
        self.rows = rows
        self.selects = []
        self.current_select = None

    def select(self, columns):
        self.current_select = columns
        self.selects.append(columns)
        if "bio_text" in columns and "wikipedia_url" in columns:
            raise RuntimeError("column fs_fencers.wikipedia_url does not exist")
        return self

    def limit(self, count):
        return self

    def execute(self):
        return FakeResult(self.rows)


class FakeUpsertTable:
    def __init__(self):
        self.calls = []

    def upsert(self, payload, on_conflict=None):
        self.calls.append((payload, on_conflict))
        return self

    def execute(self):
        return FakeResult([])


class FakeClient:
    def __init__(self, rows=None):
        self.select_table = FakeSelectTable(rows or [])
        self.upsert_table = FakeUpsertTable()

    def table(self, table_name):
        if table_name == "fs_fencers":
            return self.select_table
        if table_name == "fs_fencer_equipment":
            return self.upsert_table
        raise AssertionError(table_name)


def test_load_fencers_falls_back_when_optional_columns_are_missing():
    from scrape_equipment import load_fencers

    client = FakeClient(rows=[{"id": "f1", "name": "Lee Kiefer", "metadata": {}}])

    rows = load_fencers(client, limit=25)

    assert rows == [{"id": "f1", "name": "Lee Kiefer", "metadata": {}}]
    assert client.select_table.selects == [
        "id,name,fie_id,country,bio_text,wikipedia_url,federation_profile_url,metadata",
        "id,name,fie_id,country,bio_text,metadata",
    ]


def test_upsert_equipment_rows_uses_stable_id_conflict_key():
    from scrape_equipment import upsert_equipment_rows

    client = FakeClient()
    rows = [{"id": "row-1", "fencer_id": "fencer-1", "brand": "PBT"}]

    written, failed = upsert_equipment_rows(client, rows, batch_size=100)

    assert written == 1
    assert failed == 0
    assert client.upsert_table.calls == [([rows[0]], "id")]


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_source_texts_include_wikipedia_bio_fie_and_federation_profiles():
    from scrape_equipment import source_texts_for_fencer

    session = FakeSession(
        [
            FakeResponse(text="<html>FIE profile: Lee Kiefer uses a PBT weapon.</html>"),
            FakeResponse(text="<html>Sponsored by Absolute Fencing</html>"),
        ]
    )
    fencer = {
        "id": "f1",
        "name": "Lee Kiefer",
        "fie_id": "123",
        "bio_text": "Lee Kiefer wears a Leon Paul mask.",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
        "federation_profile_url": "https://www.usafencing.org/lee-kiefer",
        "metadata": {},
    }

    sources = source_texts_for_fencer(fencer, session)

    assert sources == [
        ("wikipedia_bio", "https://en.wikipedia.org/wiki/Lee_Kiefer", "Lee Kiefer wears a Leon Paul mask."),
        ("fie_profile", "https://fie.org/athletes/123", "<html>FIE profile: Lee Kiefer uses a PBT weapon.</html>"),
        ("federation_profile", "https://www.usafencing.org/lee-kiefer", "<html>Sponsored by Absolute Fencing</html>"),
    ]
    assert [call[0] for call in session.calls] == [
        "https://fie.org/athletes/123",
        "https://www.usafencing.org/lee-kiefer",
    ]


def test_equipment_migration_defines_requested_table():
    sql_path = ROOT / "supabase" / "migrations" / "20260601_equipment.sql"
    sql = sql_path.read_text().lower()

    assert "create table if not exists public.fs_fencer_equipment" in sql
    assert "fencer_id uuid references public.fs_fencers(id)" in " ".join(sql.split())
    assert "brand text not null" in sql
    assert "confidence text default 'medium'" in sql
    assert "check (confidence in ('high', 'medium', 'low'))" in " ".join(sql.split())
    assert "metadata jsonb default '{}'" in sql
