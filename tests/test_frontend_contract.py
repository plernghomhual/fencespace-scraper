import re
from pathlib import Path

import frontend_api_contract as contract


ROOT = Path(__file__).resolve().parents[1]
API_YAML = ROOT / "docs" / "api.yaml"
RLS_SQL = ROOT / "supabase" / "migrations" / "20260601_rls_policies.sql"


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _view_select_columns(sql: str, view_name: str) -> set[str]:
    match = re.search(
        rf"create\s+or\s+replace\s+view\s+(?:public\.)?{view_name}\s+"
        rf"(?:with\s*\([^)]*\)\s+)?as\s+select\s+(.*?)\s+from\s+",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing public view {view_name}"
    return {part.strip().split()[-1].lower() for part in match.group(1).split(",")}


def test_frontend_routes_are_mapped_to_existing_api_contract_paths():
    yaml_text = API_YAML.read_text()

    assert set(contract.FRONTEND_ROUTE_CONTRACT) == {
        "/",
        "/fencers",
        "/fencers/[id]",
        "/tournaments",
        "/tournaments/[id]",
        "/rankings",
        "/countries/[code]",
        "/head-to-head",
    }
    for route, spec in contract.FRONTEND_ROUTE_CONTRACT.items():
        for api_path in spec["api_paths"]:
            assert api_path in yaml_text, f"{route} maps to undocumented API path {api_path}"


def test_required_api_fields_are_backed_by_documented_schemas_or_public_views():
    yaml_text = _normalized(API_YAML.read_text())
    sql = RLS_SQL.read_text()

    assert _view_select_columns(sql, "v_fencer_public") == contract.PUBLIC_VIEW_FIELDS["v_fencer_public"]
    assert _view_select_columns(sql, "v_tournament_public") == contract.PUBLIC_VIEW_FIELDS["v_tournament_public"]

    for schema_name, fields in contract.REQUIRED_SCHEMA_FIELDS.items():
        schema_marker = f"{schema_name.lower()}:"
        assert schema_marker in yaml_text, f"missing schema {schema_name}"
        for field in fields:
            assert f"{field.lower()}:" in yaml_text, f"missing {schema_name}.{field}"


def test_mock_fixtures_cover_required_frontend_fields():
    for fixture_name, rows in contract.MOCK_FRONTEND_FIXTURES.items():
        assert rows, f"{fixture_name} fixture must not be empty"
        required = contract.MOCK_FIXTURE_REQUIRED_FIELDS[fixture_name]
        for row in rows:
            assert required.issubset(row), f"{fixture_name} missing fields: {required - set(row)}"


def test_frontend_server_env_contract_excludes_private_supabase_and_scraper_secrets():
    forbidden = set(contract.FORBIDDEN_BROWSER_ENV_VARS)

    assert "SUPABASE_SERVICE_KEY" in forbidden
    assert "SUPABASE_KEY" in forbidden
    assert forbidden.isdisjoint(contract.FRONTEND_SERVER_ENV_VARS)
    assert forbidden.isdisjoint(contract.FRONTEND_PUBLIC_ENV_VARS)
    assert all(name.startswith("NEXT_PUBLIC_") for name in contract.FRONTEND_PUBLIC_ENV_VARS)
