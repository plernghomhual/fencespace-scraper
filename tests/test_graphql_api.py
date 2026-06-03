import importlib
import os
import sys
from textwrap import dedent

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.ilike_filters = []
        self.start = None
        self.end = None
        self.limit_count = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selected.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def ilike(self, column, pattern):
        self.ilike_filters.append((column, pattern.replace("%", "").lower()))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, needle in self.ilike_filters:
            rows = [row for row in rows if needle in str(row.get(column, "")).lower()]
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        if self.selected and self.selected != "*":
            wanted = [column.strip() for column in self.selected.split(",") if column.strip()]
            rows = [{key: row.get(key) for key in wanted if key in row} for row in rows]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.ranges = []
        self.selected = []
        self.tables = {
            "fs_fencers": [
                {
                    "id": "f1",
                    "fie_id": "101",
                    "name": "Alex Lee",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "world_rank": 1,
                    "fie_points": 178.5,
                    "metadata": {"private": True},
                },
                {
                    "id": "f2",
                    "fie_id": "102",
                    "name": "Mina Park",
                    "country": "KOR",
                    "weapon": "Foil",
                    "category": "Senior",
                    "world_rank": 8,
                    "fie_points": 91.0,
                    "metadata": {"private": True},
                },
            ],
            "fs_fencer_career_stats": [
                {"fencer_id": "f1", "total_competitions": 12, "gold_medals": 2, "metadata": {"private": True}}
            ],
            "fs_fencer_social_media": [
                {"fencer_id": "f1", "platform": "instagram", "url": "https://example.test/alex"}
            ],
            "fs_fencer_equipment": [
                {"fencer_id": "f1", "brand": "Allstar", "equipment_type": "weapon", "source_url": "https://gear.test"}
            ],
            "fs_tournaments": [
                {
                    "id": "t1",
                    "fie_id": "9001",
                    "name": "Seoul GP",
                    "season": 2026,
                    "type": "GP",
                    "country": "KOR",
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-03",
                }
            ],
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "t1",
                    "fencer_id": "f1",
                    "rank": 1,
                    "name": "Alex Lee",
                    "nationality": "KOR",
                    "points": 48.0,
                }
            ],
            "fs_rankings_history": [
                {
                    "id": "rk1",
                    "season": 2026,
                    "weapon": "Epee",
                    "gender": "Men",
                    "category": "Senior",
                    "rank": 1,
                    "name": "Alex Lee",
                    "country": "KOR",
                    "points": 178.5,
                }
            ],
            "fs_head_to_head": [
                {
                    "id": "h1",
                    "fencer_a_id": "f1",
                    "fencer_b_id": "f2",
                    "weapon": "Epee",
                    "a_wins": 3,
                    "b_wins": 1,
                    "bouts_total": 4,
                    "last_meeting_date": "2026-03-02",
                }
            ],
            "fs_country_depth": [
                {
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "fencers_in_top16": 3,
                    "fencers_in_top32": 8,
                    "fencers_in_top64": 14,
                    "total_ranked": 25,
                    "avg_world_rank": 27.3,
                }
            ],
            "fs_social_feed": [
                {
                    "id": "n1",
                    "platform": "instagram",
                    "post_id": "post-1",
                    "author": "FenceSpace",
                    "url": "https://social.test/post-1",
                    "text_excerpt": "Seoul GP results posted",
                    "language": "en",
                    "tournament_id": "t1",
                    "posted_at": "2026-03-04T00:00:00Z",
                    "source": "social",
                    "metadata": {"private": True},
                }
            ],
            "fs_equipment_reviews": [
                {
                    "id": "p1",
                    "product_name": "FIE Epee Blade",
                    "brand": "Allstar",
                    "category": "blade",
                    "rating": 4.8,
                    "review_count": 42,
                    "price": 199.99,
                    "currency": "USD",
                    "source": "retailer",
                    "url": "https://gear.test/blade",
                    "metadata": {"private": True},
                }
            ],
            "fs_api_keys": [{"key": "db-secret", "active": True, "revoked": False}],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def graphql_module(monkeypatch):
    monkeypatch.setenv("FENCESPACE_API_KEY", "secret")
    for name in ["graphql.app", "graphql", "api"]:
        sys.modules.pop(name, None)
    module = importlib.import_module("graphql.app")
    fake = FakeSupabase()
    module.app.state.supabase_client = fake
    module.reset_rate_limits()
    yield module
    for name in ["graphql.app", "graphql", "api"]:
        sys.modules.pop(name, None)


@pytest.fixture
def client(graphql_module):
    return TestClient(graphql_module.app)


def auth_headers():
    return {"X-API-Key": "secret"}


def gql(client, query, variables=None, headers=None):
    return client.post(
        "/graphql",
        headers=auth_headers() if headers is None else headers,
        json={"query": dedent(query), "variables": variables or {}},
    )


def test_graphql_app_imports_and_serves_schema(client):
    response = client.get("/graphql/schema")

    assert response.status_code == 200
    assert "type Query" in response.text


def test_graphql_schema_snapshot(client):
    response = client.get("/graphql/schema")

    assert response.status_code == 200
    assert response.text.strip() == dedent(
        """
        type Query {
          fencers(name: String, country: String, weapon: String, limit: Int = 50, offset: Int = 0): FencerPage!
          fencer(id: ID!): FencerProfile
          tournaments(season: Int, type: String, country: String, limit: Int = 50, offset: Int = 0): TournamentPage!
          results(tournamentId: ID!, limit: Int = 50, offset: Int = 0): ResultPage!
          rankings(season: Int, weapon: String, gender: String, category: String, limit: Int = 50, offset: Int = 0): RankingPage!
          h2h(fencerA: ID!, fencerB: ID!, limit: Int = 50, offset: Int = 0): HeadToHeadPage!
          countries(code: String!, limit: Int = 50, offset: Int = 0): CountryDepthPage!
          news(platform: String, limit: Int = 50, offset: Int = 0): NewsPage!
          products(brand: String, category: String, limit: Int = 50, offset: Int = 0): ProductPage!
        }

        type Pagination {
          limit: Int!
          offset: Int!
          count: Int!
        }

        type Fencer {
          id: ID
          fieId: String
          name: String
          country: String
          weapon: String
          category: String
          gender: String
          worldRank: Int
          fiePoints: Float
        }

        type FencerProfile {
          profile: Fencer
          careerStats: CareerStats
          social: [SocialLink!]!
          equipment: [FencerEquipment!]!
        }

        type CareerStats {
          fencerId: ID
          totalCompetitions: Int
          goldMedals: Int
          silverMedals: Int
          bronzeMedals: Int
        }

        type SocialLink {
          fencerId: ID
          platform: String
          url: String
          handle: String
        }

        type FencerEquipment {
          fencerId: ID
          brand: String
          equipmentType: String
          sponsorName: String
          source: String
          sourceUrl: String
          confidence: String
        }

        type Tournament {
          id: ID
          fieId: String
          season: Int
          name: String
          country: String
          type: String
          startDate: String
          endDate: String
        }

        type Result {
          id: ID
          tournamentId: ID
          fencerId: ID
          rank: Int
          name: String
          nationality: String
          points: Float
        }

        type Ranking {
          id: ID
          season: Int
          weapon: String
          gender: String
          category: String
          rank: Int
          name: String
          country: String
          points: Float
        }

        type HeadToHead {
          id: ID
          fencerAId: ID
          fencerBId: ID
          weapon: String
          aWins: Int
          bWins: Int
          aTouches: Int
          bTouches: Int
          boutsTotal: Int
          lastMeetingDate: String
          lastWinnerId: ID
        }

        type CountryDepth {
          country: String
          weapon: String
          category: String
          fencersInTop16: Int
          fencersInTop32: Int
          fencersInTop64: Int
          totalRanked: Int
          avgWorldRank: Float
        }

        type NewsItem {
          id: ID
          platform: String
          postId: String
          author: String
          url: String
          textExcerpt: String
          hashtags: [String!]
          language: String
          tournamentId: ID
          postedAt: String
          source: String
        }

        type Product {
          id: ID
          productName: String
          brand: String
          category: String
          rating: Float
          reviewCount: Int
          price: Float
          currency: String
          source: String
          url: String
          scrapedAt: String
        }

        type FencerPage { data: [Fencer!]!, pagination: Pagination! }
        type TournamentPage { data: [Tournament!]!, pagination: Pagination! }
        type ResultPage { data: [Result!]!, pagination: Pagination! }
        type RankingPage { data: [Ranking!]!, pagination: Pagination! }
        type HeadToHeadPage { fencerA: ID!, fencerB: ID!, data: [HeadToHead!]!, pagination: Pagination! }
        type CountryDepthPage { data: [CountryDepth!]!, pagination: Pagination! }
        type NewsPage { data: [NewsItem!]!, pagination: Pagination! }
        type ProductPage { data: [Product!]!, pagination: Pagination! }
        """
    ).strip()


def test_graphql_rejects_missing_api_key(client):
    response = gql(client, "{ fencers { data { id } } }", headers={})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_graphql_rejects_mutations(client):
    response = gql(client, "mutation { fencers { data { id } } }")

    assert response.status_code == 400
    assert response.json()["errors"][0]["message"] == "GraphQL endpoint is read-only"


def test_graphql_rejects_invalid_filter_names(client):
    response = gql(client, "{ fencers(private: true) { data { id } } }")

    assert response.status_code == 400
    assert "Unknown argument 'private' for fencers" in response.json()["errors"][0]["message"]


def test_graphql_rejects_private_fields(client):
    response = gql(client, "{ fencers { data { id metadata } } }")

    assert response.status_code == 400
    assert "Unknown field 'metadata' for Fencer" in response.json()["errors"][0]["message"]


def test_graphql_rejects_fencer_without_selection_set(client):
    response = gql(client, '{ fencer(id: "f1") }')

    assert response.status_code == 400
    assert "Field 'fencer' requires a selection set" in response.json()["errors"][0]["message"]


def test_graphql_paginates_and_selects_only_requested_columns(client, graphql_module):
    response = gql(
        client,
        """
        {
          fencers(limit: 1, offset: 1) {
            pagination { limit offset count }
            data { id name }
          }
        }
        """,
    )

    assert response.status_code == 200
    payload = response.json()["data"]["fencers"]
    assert payload["pagination"] == {"limit": 1, "offset": 1, "count": 1}
    assert payload["data"] == [{"id": "f2", "name": "Mina Park"}]
    fake = graphql_module.app.state.supabase_client
    assert ("fs_fencers", 1, 1) in fake.ranges
    assert ("fs_fencers", "id,name") in fake.selected
    assert ("fs_fencers", "*") not in fake.selected


@pytest.mark.parametrize(
    ("query", "path", "expected"),
    [
        (
            '{ fencers(name: "alex", country: "KOR", weapon: "Epee") { data { id fieId name country weapon worldRank fiePoints } } }',
            ("fencers", "data", 0, "fieId"),
            "101",
        ),
        (
            '{ fencer(id: "f1") { profile { id name } careerStats { totalCompetitions goldMedals } social { platform url } equipment { brand equipmentType sourceUrl } } }',
            ("fencer", "equipment", 0, "equipmentType"),
            "weapon",
        ),
        (
            '{ tournaments(season: 2026, type: "GP", country: "KOR") { data { id fieId name startDate endDate } } }',
            ("tournaments", "data", 0, "name"),
            "Seoul GP",
        ),
        (
            '{ results(tournamentId: "t1") { data { id tournamentId fencerId rank name nationality points } } }',
            ("results", "data", 0, "rank"),
            1,
        ),
        (
            '{ rankings(season: 2026, weapon: "Epee", gender: "Men", category: "Senior") { data { id name country rank points } } }',
            ("rankings", "data", 0, "points"),
            178.5,
        ),
        (
            '{ h2h(fencerA: "f2", fencerB: "f1") { fencerA fencerB data { fencerAId fencerBId boutsTotal lastMeetingDate } } }',
            ("h2h", "data", 0, "boutsTotal"),
            4,
        ),
        (
            '{ countries(code: "kor") { data { country weapon fencersInTop16 totalRanked avgWorldRank } } }',
            ("countries", "data", 0, "country"),
            "KOR",
        ),
        (
            '{ news(platform: "instagram") { data { id platform postId textExcerpt postedAt } } }',
            ("news", "data", 0, "textExcerpt"),
            "Seoul GP results posted",
        ),
        (
            '{ products(brand: "Allstar", category: "blade") { data { id productName brand category rating reviewCount price currency url } } }',
            ("products", "data", 0, "productName"),
            "FIE Epee Blade",
        ),
    ],
)
def test_graphql_core_type_happy_paths(client, query, path, expected):
    response = gql(client, query)

    assert response.status_code == 200
    value = response.json()["data"]
    for segment in path:
        value = value[segment]
    assert value == expected


def test_graphql_rejects_invalid_pagination(client):
    response = gql(client, "{ fencers(limit: 501) { data { id } } }")

    assert response.status_code == 400
    assert "limit must be between 1 and 500" in response.json()["errors"][0]["message"]
