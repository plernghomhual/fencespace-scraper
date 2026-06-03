"""Frontend-facing API contract metadata for tests and documentation."""

FRONTEND_ROUTE_CONTRACT = {
    "/": {"api_paths": ["/fencer/search", "/tournaments", "/rankings"]},
    "/fencers": {"api_paths": ["/fencer/search"]},
    "/fencers/[id]": {"api_paths": ["/fencer/{id}"]},
    "/tournaments": {"api_paths": ["/tournaments"]},
    "/tournaments/[id]": {"api_paths": ["/tournaments/{id}/results"]},
    "/rankings": {"api_paths": ["/rankings"]},
    "/countries/[code]": {"api_paths": ["/countries/{code}/depth"]},
    "/head-to-head": {"api_paths": ["/h2h/{fencer_a}/{fencer_b}"]},
}

PUBLIC_VIEW_FIELDS = {
    "v_fencer_public": {
        "id",
        "name",
        "country",
        "weapon",
        "category",
        "world_rank",
        "fie_points",
        "image_url",
    },
    "v_tournament_public": {
        "id",
        "name",
        "season",
        "start_date",
        "end_date",
        "country",
        "weapon",
        "category",
        "type",
    },
}

REQUIRED_SCHEMA_FIELDS = {
    "Fencer": {"id", "name", "country", "weapon", "category", "world_rank", "fie_points"},
    "Tournament": {"id", "name", "season", "country", "type", "start_date", "end_date"},
    "Result": {"tournament_id", "fencer_id", "rank", "name", "nationality"},
    "Ranking": {"season", "weapon", "gender", "category", "rank", "name", "points"},
    "HeadToHead": {"fencer_a_id", "fencer_b_id", "weapon", "a_wins", "b_wins", "bouts_total"},
    "CountryDepth": {
        "country",
        "weapon",
        "category",
        "fencers_in_top16",
        "fencers_in_top32",
        "fencers_in_top64",
        "total_ranked",
        "avg_world_rank",
    },
}

MOCK_FRONTEND_FIXTURES = {
    "fencers": [
        {
            "id": "f1",
            "name": "Alex Lee",
            "country": "KOR",
            "weapon": "Epee",
            "category": "Senior",
            "world_rank": 1,
            "fie_points": 210.5,
        }
    ],
    "tournaments": [
        {
            "id": "t1",
            "name": "Seoul Grand Prix",
            "season": 2026,
            "country": "KOR",
            "type": "GP",
            "start_date": "2026-05-02",
            "end_date": "2026-05-04",
        }
    ],
    "rankings": [
        {
            "season": 2026,
            "weapon": "Epee",
            "gender": "Men",
            "category": "Senior",
            "rank": 1,
            "name": "Alex Lee",
            "points": 210.5,
        }
    ],
    "country_depth": [
        {
            "country": "KOR",
            "weapon": "Epee",
            "category": "Senior",
            "fencers_in_top16": 3,
            "fencers_in_top32": 7,
            "fencers_in_top64": 12,
            "total_ranked": 25,
            "avg_world_rank": 22.4,
        }
    ],
    "head_to_head": [
        {
            "fencer_a_id": "f1",
            "fencer_b_id": "f2",
            "weapon": "Epee",
            "a_wins": 3,
            "b_wins": 1,
            "bouts_total": 4,
        }
    ],
}

MOCK_FIXTURE_REQUIRED_FIELDS = {
    "fencers": REQUIRED_SCHEMA_FIELDS["Fencer"],
    "tournaments": REQUIRED_SCHEMA_FIELDS["Tournament"],
    "rankings": REQUIRED_SCHEMA_FIELDS["Ranking"],
    "country_depth": REQUIRED_SCHEMA_FIELDS["CountryDepth"],
    "head_to_head": REQUIRED_SCHEMA_FIELDS["HeadToHead"],
}

FORBIDDEN_BROWSER_ENV_VARS = (
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_KEY",
    "SCRAPER_TOKEN",
    "SCRAPER_PASSWORD",
)
FRONTEND_SERVER_ENV_VARS = ("FENCESPACE_API_BASE_URL", "FENCESPACE_API_KEY", "FS_API_KEY", "API_KEY")
FRONTEND_PUBLIC_ENV_VARS = ()
