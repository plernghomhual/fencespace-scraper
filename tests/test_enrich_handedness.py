import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"

FIE_PROFILE_HTML = """
<html><body>
<h1>SCRUGGS Lauren</h1>
<section>
  <div>Rank 7</div>
  <div>Hand</div><div>L</div>
</section>
<div class="ProfileInfo-item">
  <span>Club / Team</span><span>Fencers Club: United States</span>
</div>
<div class="ProfileInfo-item">
  <span>Handedness</span><span>Left</span>
</div>
</body></html>
"""

WIKIPEDIA_INFOBOX_HTML = """
<html><body>
<table class="infobox">
  <tr><th scope="row">Hand</th><td>Left-handed</td></tr>
  <tr><th scope="row">Weapon</th><td>Foil</td></tr>
</table>
</body></html>
"""

FEDERATION_BIO_HTML = """
<html><body>
<dl>
  <dt>Main dominante</dt>
  <dd>Droite</dd>
</dl>
<table>
  <tr><th>Mano dominante</th><td>Izquierda</td></tr>
</table>
</body></html>
"""

MEDIA_ONLY_HTML = """
<html><body>
<img alt="left-handed fencer attacking with foil" src="photo.jpg">
<p>She recovered from a left hand injury and later changed her guard.</p>
<video title="right hand slow motion replay"></video>
</body></html>
"""


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.pending_rows = None
        self.pending_conflict = None

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            (self.table_name, self.pending_rows, self.pending_conflict)
        )
        return FakeResponse(self.pending_rows)


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def normalized_sql() -> str:
    migration = Path("supabase/migrations/20260602_handedness.sql")
    return re.sub(r"\s+", " ", migration.read_text(encoding="utf-8").lower())


def test_handedness_migration_defines_storage_shape_and_constraints():
    sql = normalized_sql()

    assert "create table if not exists public.fs_fencer_handedness" in sql
    assert "fencer_id uuid not null references public.fs_fencers(id)" in sql
    assert "handedness text not null" in sql
    assert "source_url text not null" in sql
    assert "confidence numeric" in sql
    assert "collected_at timestamptz not null default now()" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql
    assert "unique (fencer_id, source_url)" in sql
    assert "handedness in ('left', 'right', 'ambidextrous', 'unknown')" in sql
    assert "confidence >= 0" in sql
    assert "confidence <= 1" in sql
    assert "drop table" not in sql
    assert "truncate table" not in sql


def test_normalize_handedness_supports_multilingual_values_and_unknowns():
    from enrich_handedness import normalize_handedness

    left_values = ["L", "Left", "left-handed", "Gaucher", "gauche", "main gauche", "zurdo", "izquierda", "mano izquierda", "linkshandig"]
    right_values = ["R", "Right", "right handed", "Droitier", "droite", "main droite", "diestro", "derecha", "mano destra", "rechtshandig"]
    ambi_values = ["Ambidextrous", "ambidextre", "ambidiestro", "beidhandig"]
    unknown_values = ["Unknown", "inconnu", "desconocido", "n/a", "not specified"]

    assert {normalize_handedness(value) for value in left_values} == {"left"}
    assert {normalize_handedness(value) for value in right_values} == {"right"}
    assert {normalize_handedness(value) for value in ambi_values} == {"ambidextrous"}
    assert {normalize_handedness(value) for value in unknown_values} == {"unknown"}
    assert normalize_handedness("left hand injury") is None


def test_parse_fie_profile_reads_explicit_handedness_fields():
    from enrich_handedness import parse_profile_handedness

    observation = parse_profile_handedness(
        FIE_PROFILE_HTML,
        source_url="https://fie.org/athletes/42855",
        source_type="fie_profile",
    )

    assert observation is not None
    assert observation.handedness == "left"
    assert observation.source_url == "https://fie.org/athletes/42855"
    assert observation.source_type == "fie_profile"
    assert observation.confidence >= 0.9
    assert observation.metadata["label"] == "Handedness"
    assert observation.metadata["raw_value"] == "Left"


def test_parse_public_and_federation_profiles_use_structured_labels_only():
    from enrich_handedness import parse_profile_handedness

    public_observation = parse_profile_handedness(
        WIKIPEDIA_INFOBOX_HTML,
        source_url="https://en.wikipedia.org/wiki/Lauren_Scruggs_(fencer)",
        source_type="public_athlete_page",
    )
    federation_observation = parse_profile_handedness(
        FEDERATION_BIO_HTML,
        source_url="https://federation.example/athletes/123",
        source_type="federation_profile",
    )

    assert public_observation is not None
    assert public_observation.handedness == "left"
    assert public_observation.metadata["label"] == "Hand"
    assert federation_observation is not None
    assert federation_observation.handedness == "right"
    assert federation_observation.metadata["label"] == "Main dominante"


def test_parse_profile_ignores_media_and_unstructured_narrative_mentions():
    from enrich_handedness import parse_profile_handedness

    assert (
        parse_profile_handedness(
            MEDIA_ONLY_HTML,
            source_url="https://example.org/media-only",
            source_type="public_athlete_page",
        )
        is None
    )


def test_parse_wikidata_binding_normalizes_p552_handedness_statement():
    from enrich_handedness import parse_wikidata_binding

    binding = {
        "athlete": {"value": "http://www.wikidata.org/entity/Q113042497"},
        "athleteLabel": {"value": "Lauren Scruggs"},
        "fie_id": {"value": "42855"},
        "countryLabel": {"value": "United States of America"},
        "hand": {"value": "http://www.wikidata.org/entity/Q789447"},
        "handLabel": {"value": "left-handedness"},
    }

    observation = parse_wikidata_binding(binding)

    assert observation is not None
    assert observation.wikidata_id == "Q113042497"
    assert observation.fie_id == "42855"
    assert observation.name == "Lauren Scruggs"
    assert observation.country == "United States of America"
    assert observation.source_type == "wikidata"
    assert observation.source_url == "https://www.wikidata.org/wiki/Q113042497"
    assert observation.handedness == "left"
    assert observation.confidence >= 0.95
    assert observation.metadata["wikidata_property"] == "P552"
    assert observation.metadata["hand_id"] == "Q789447"


def test_match_observation_prefers_wikidata_and_fie_ids_then_logs_ambiguous_name_only():
    from enrich_handedness import (
        HandednessObservation,
        build_fencer_indexes,
        build_identity_maps,
        match_observation_to_fencers,
    )

    fencers = [
        {
            "id": "row-a",
            "fie_id": "42855",
            "name": "SCRUGGS Lauren",
            "country": "USA",
            "metadata": {"wikidata_id": "Q113042497"},
        },
        {
            "id": "row-b",
            "fie_id": "42855",
            "name": "SCRUGGS Lauren",
            "country": "USA",
            "metadata": {},
        },
        {"id": "amb-1", "name": "Alex Kim", "country": "USA", "metadata": {}},
        {"id": "amb-2", "name": "Alex Kim", "country": "USA", "metadata": {}},
    ]
    identities = [{"fs_fencer_row_ids": ["row-a", "row-b"], "fie_ids": ["42855"]}]
    row_groups, fie_groups = build_identity_maps(identities)
    indexes = build_fencer_indexes(fencers)
    logs: list[Any] = []

    id_observation = HandednessObservation(
        handedness="left",
        source_url="https://www.wikidata.org/wiki/Q113042497",
        source_type="wikidata",
        confidence=0.98,
        metadata={},
        wikidata_id="Q113042497",
        fie_id="42855",
        name="Lauren Scruggs",
        country="USA",
    )
    name_only_observation = HandednessObservation(
        handedness="right",
        source_url="https://federation.example/alex-kim",
        source_type="federation_profile",
        confidence=0.8,
        metadata={},
        name="Alex Kim",
        country="USA",
    )

    assert match_observation_to_fencers(
        id_observation,
        indexes=indexes,
        row_groups=row_groups,
        fie_groups=fie_groups,
        ambiguous_log=logs,
    ) == {"row-a", "row-b"}
    assert match_observation_to_fencers(
        name_only_observation,
        indexes=indexes,
        row_groups=row_groups,
        fie_groups=fie_groups,
        ambiguous_log=logs,
    ) == set()
    assert logs == [
        {
            "name": "Alex Kim",
            "country": "USA",
            "source_url": "https://federation.example/alex-kim",
            "candidate_fencer_ids": ["amb-1", "amb-2"],
            "reason": "ambiguous_name_country_match",
        }
    ]


def test_build_rows_and_upsert_respect_dry_run_and_conflict_key():
    from enrich_handedness import (
        HandednessObservation,
        build_handedness_rows,
        upsert_handedness_rows,
    )

    observation = HandednessObservation(
        handedness="ambidextrous",
        source_url="https://www.wikidata.org/wiki/Q1",
        source_type="wikidata",
        confidence=0.97,
        metadata={"wikidata_property": "P552"},
        wikidata_id="Q1",
        fie_id="123",
        name="Ambi Fencer",
        country="France",
    )
    rows = build_handedness_rows(observation, {"row-1"}, collected_at=NOW)

    assert rows == [
        {
            "fencer_id": "row-1",
            "handedness": "ambidextrous",
            "source_url": "https://www.wikidata.org/wiki/Q1",
            "confidence": 0.97,
            "collected_at": NOW,
            "metadata": {
                "wikidata_property": "P552",
                "source_type": "wikidata",
                "wikidata_id": "Q1",
                "fie_id": "123",
                "source_name": "Ambi Fencer",
                "source_country": "France",
            },
        }
    ]

    dry_run_client = FakeSupabase()
    assert upsert_handedness_rows(dry_run_client, rows, dry_run=True) == 0
    assert dry_run_client.upserts == []

    write_client = FakeSupabase()
    assert upsert_handedness_rows(write_client, rows, dry_run=False) == 1
    assert write_client.upserts == [
        ("fs_fencer_handedness", rows, "fencer_id,source_url")
    ]
