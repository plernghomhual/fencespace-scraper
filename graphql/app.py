import json
import re
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

import api as rest_api


SCHEMA_SDL = """
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
""".strip()


FIELD_MAPS: dict[str, dict[str, str]] = {
    "Pagination": {"limit": "limit", "offset": "offset", "count": "count"},
    "Fencer": {
        "id": "id",
        "fieId": "fie_id",
        "name": "name",
        "country": "country",
        "weapon": "weapon",
        "category": "category",
        "gender": "gender",
        "worldRank": "world_rank",
        "fiePoints": "fie_points",
    },
    "CareerStats": {
        "fencerId": "fencer_id",
        "totalCompetitions": "total_competitions",
        "goldMedals": "gold_medals",
        "silverMedals": "silver_medals",
        "bronzeMedals": "bronze_medals",
    },
    "SocialLink": {"fencerId": "fencer_id", "platform": "platform", "url": "url", "handle": "handle"},
    "FencerEquipment": {
        "fencerId": "fencer_id",
        "brand": "brand",
        "equipmentType": "equipment_type",
        "sponsorName": "sponsor_name",
        "source": "source",
        "sourceUrl": "source_url",
        "confidence": "confidence",
    },
    "Tournament": {
        "id": "id",
        "fieId": "fie_id",
        "season": "season",
        "name": "name",
        "country": "country",
        "type": "type",
        "startDate": "start_date",
        "endDate": "end_date",
    },
    "Result": {
        "id": "id",
        "tournamentId": "tournament_id",
        "fencerId": "fencer_id",
        "rank": "rank",
        "name": "name",
        "nationality": "nationality",
        "points": "points",
    },
    "Ranking": {
        "id": "id",
        "season": "season",
        "weapon": "weapon",
        "gender": "gender",
        "category": "category",
        "rank": "rank",
        "name": "name",
        "country": "country",
        "points": "points",
    },
    "HeadToHead": {
        "id": "id",
        "fencerAId": "fencer_a_id",
        "fencerBId": "fencer_b_id",
        "weapon": "weapon",
        "aWins": "a_wins",
        "bWins": "b_wins",
        "aTouches": "a_touches",
        "bTouches": "b_touches",
        "boutsTotal": "bouts_total",
        "lastMeetingDate": "last_meeting_date",
        "lastWinnerId": "last_winner_id",
    },
    "CountryDepth": {
        "country": "country",
        "weapon": "weapon",
        "category": "category",
        "fencersInTop16": "fencers_in_top16",
        "fencersInTop32": "fencers_in_top32",
        "fencersInTop64": "fencers_in_top64",
        "totalRanked": "total_ranked",
        "avgWorldRank": "avg_world_rank",
    },
    "NewsItem": {
        "id": "id",
        "platform": "platform",
        "postId": "post_id",
        "author": "author",
        "url": "url",
        "textExcerpt": "text_excerpt",
        "hashtags": "hashtags",
        "language": "language",
        "tournamentId": "tournament_id",
        "postedAt": "posted_at",
        "source": "source",
    },
    "Product": {
        "id": "id",
        "productName": "product_name",
        "brand": "brand",
        "category": "category",
        "rating": "rating",
        "reviewCount": "review_count",
        "price": "price",
        "currency": "currency",
        "source": "source",
        "url": "url",
        "scrapedAt": "scraped_at",
    },
}


PAGE_FIELDS = {"data", "pagination"}
H2H_PAGE_FIELDS = {"fencerA", "fencerB", "data", "pagination"}


@dataclass
class Selection:
    name: str
    alias: str | None
    args: dict[str, Any]
    children: list["Selection"]

    @property
    def response_key(self) -> str:
        return self.alias or self.name


class GraphQLError(ValueError):
    pass


class GraphQLParser:
    def __init__(self, query: str, variables: dict[str, Any] | None = None):
        self.tokens = self._tokenize(query)
        self.variables = variables or {}
        self.index = 0

    def parse(self) -> list[Selection]:
        if not self.tokens:
            raise GraphQLError("GraphQL query is required")
        token = self._peek()
        if token in {"mutation", "subscription"}:
            raise GraphQLError("GraphQL endpoint is read-only")
        if token == "query":
            self._consume()
            if self._peek_is_name():
                self._consume()
            if self._peek() == "(":
                self._skip_balanced("(", ")")
        selections = self._parse_selection_set()
        if self._peek() is not None:
            raise GraphQLError(f"Unexpected token '{self._peek()}'")
        return selections

    def _tokenize(self, query: str) -> list[str]:
        tokens: list[str] = []
        index = 0
        while index < len(query):
            char = query[index]
            if char.isspace():
                index += 1
                continue
            if char == "#":
                newline = query.find("\n", index)
                index = len(query) if newline == -1 else newline + 1
                continue
            if char in "{}():,[]":
                tokens.append(char)
                index += 1
                continue
            if char == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*", query[index:])
                if not match:
                    raise GraphQLError("Invalid variable token")
                tokens.append(match.group(0))
                index += len(match.group(0))
                continue
            if char == '"':
                end = index + 1
                escaped = False
                while end < len(query):
                    current = query[end]
                    if current == '"' and not escaped:
                        break
                    escaped = current == "\\" and not escaped
                    if current != "\\":
                        escaped = False
                    end += 1
                if end >= len(query):
                    raise GraphQLError("Unterminated string literal")
                tokens.append(query[index : end + 1])
                index = end + 1
                continue
            number = re.match(r"-?\d+(?:\.\d+)?", query[index:])
            if number:
                tokens.append(number.group(0))
                index += len(number.group(0))
                continue
            name = re.match(r"[A-Za-z_][A-Za-z0-9_]*", query[index:])
            if name:
                tokens.append(name.group(0))
                index += len(name.group(0))
                continue
            raise GraphQLError(f"Unexpected character '{char}'")
        return tokens

    def _parse_selection_set(self) -> list[Selection]:
        self._expect("{")
        selections: list[Selection] = []
        while self._peek() != "}":
            if self._peek() is None:
                raise GraphQLError("Unterminated selection set")
            selections.append(self._parse_field())
        self._expect("}")
        return selections

    def _parse_field(self) -> Selection:
        first = self._parse_name()
        alias = None
        name = first
        if self._peek() == ":":
            self._consume()
            alias = first
            name = self._parse_name()
        args = self._parse_arguments() if self._peek() == "(" else {}
        children = self._parse_selection_set() if self._peek() == "{" else []
        return Selection(name=name, alias=alias, args=args, children=children)

    def _parse_arguments(self) -> dict[str, Any]:
        args: dict[str, Any] = {}
        self._expect("(")
        while self._peek() != ")":
            name = self._parse_name()
            self._expect(":")
            args[name] = self._parse_value()
            if self._peek() == ",":
                self._consume()
        self._expect(")")
        return args

    def _parse_value(self) -> Any:
        token = self._consume()
        if token is None:
            raise GraphQLError("Expected value")
        if token.startswith("$"):
            name = token[1:]
            if name not in self.variables:
                raise GraphQLError(f"Variable '${name}' was not provided")
            return self.variables[name]
        if token.startswith('"'):
            return json.loads(token)
        if token == "true":
            return True
        if token == "false":
            return False
        if token == "null":
            return None
        if re.fullmatch(r"-?\d+", token):
            return int(token)
        if re.fullmatch(r"-?\d+\.\d+", token):
            return float(token)
        return token

    def _skip_balanced(self, opener: str, closer: str) -> None:
        depth = 0
        while self._peek() is not None:
            token = self._consume()
            if token == opener:
                depth += 1
            elif token == closer:
                depth -= 1
                if depth == 0:
                    return
        raise GraphQLError(f"Unterminated {opener}{closer} block")

    def _parse_name(self) -> str:
        token = self._consume()
        if token is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            raise GraphQLError("Expected field or argument name")
        return token

    def _peek_is_name(self) -> bool:
        token = self._peek()
        return bool(token and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token))

    def _expect(self, expected: str) -> None:
        token = self._consume()
        if token != expected:
            raise GraphQLError(f"Expected '{expected}'")

    def _consume(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]


app = FastAPI(title="FenceSpace GraphQL API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)


def reset_rate_limits() -> None:
    rest_api.reset_rate_limits()


def get_supabase_client():
    if hasattr(app.state, "supabase_client"):
        return app.state.supabase_client
    return rest_api.get_supabase_client()


def is_valid_api_key(api_key: str) -> bool:
    return rest_api.is_valid_api_key_for_client(get_supabase_client(), api_key)


@app.middleware("http")
async def graphql_auth_and_readonly_guard(request: Request, call_next):
    path = request.url.path
    if path in {"/docs", "/openapi.json", "/redoc", "/graphql/schema"} or path.startswith("/docs/"):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if path == "/graphql":
        if request.method not in {"GET", "POST", "HEAD"}:
            return JSONResponse(status_code=405, content={"detail": "Method not allowed"})
    elif request.method not in {"GET", "HEAD"}:
        return JSONResponse(status_code=405, content={"detail": "Method not allowed"})

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"detail": "Missing API key"})
    if not is_valid_api_key(api_key):
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})

    allowed, retry_after = rest_api.check_rate_limit(api_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


@app.get("/graphql/schema", response_class=PlainTextResponse)
def graphql_schema() -> str:
    return SCHEMA_SDL


@app.get("/graphql")
def graphql_get(query: str = Query(...), variables: str | None = None):
    parsed_variables: dict[str, Any] = {}
    if variables:
        try:
            parsed = json.loads(variables)
        except json.JSONDecodeError as exc:
            return _error_response(f"Invalid variables JSON: {exc.msg}", status_code=400)
        if not isinstance(parsed, dict):
            return _error_response("variables must be a JSON object", status_code=400)
        parsed_variables = parsed
    return _execute_response(query, parsed_variables)


@app.post("/graphql")
async def graphql_post(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        return _error_response(f"Invalid JSON body: {exc.msg}", status_code=400)
    if not isinstance(payload, dict):
        return _error_response("GraphQL request body must be a JSON object", status_code=400)
    query = payload.get("query")
    variables = payload.get("variables") or {}
    if not isinstance(query, str):
        return _error_response("query must be a string", status_code=400)
    if not isinstance(variables, dict):
        return _error_response("variables must be an object", status_code=400)
    return _execute_response(query, variables)


def _execute_response(query: str, variables: dict[str, Any]):
    try:
        data = execute_graphql(query, variables)
    except GraphQLError as exc:
        return _error_response(str(exc), status_code=400)
    except HTTPException as exc:
        return _error_response(str(exc.detail), status_code=exc.status_code)
    return {"data": data}


def _error_response(message: str, *, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"errors": [{"message": message}]})


def execute_graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    selections = GraphQLParser(query, variables).parse()
    data: dict[str, Any] = {}
    for selection in selections:
        data[selection.response_key] = _resolve_root(selection)
    return data


def _resolve_root(selection: Selection) -> Any:
    resolvers = {
        "fencers": _resolve_fencers,
        "fencer": _resolve_fencer,
        "tournaments": _resolve_tournaments,
        "results": _resolve_results,
        "rankings": _resolve_rankings,
        "h2h": _resolve_h2h,
        "countries": _resolve_countries,
        "news": _resolve_news,
        "products": _resolve_products,
    }
    resolver = resolvers.get(selection.name)
    if not resolver:
        raise GraphQLError(f"Unknown root field '{selection.name}'")
    return resolver(selection)


def _resolve_fencers(selection: Selection) -> dict[str, Any]:
    return _resolve_page(
        selection,
        table_name="fs_fencers",
        type_name="Fencer",
        allowed_args={"name", "country", "weapon", "limit", "offset"},
        configure=lambda query, args: _apply_filters(
            query,
            args,
            ilike={"name": "name"},
            eq={"country": "country", "weapon": "weapon"},
        ),
    )


def _resolve_tournaments(selection: Selection) -> dict[str, Any]:
    return _resolve_page(
        selection,
        table_name="fs_tournaments",
        type_name="Tournament",
        allowed_args={"season", "type", "country", "limit", "offset"},
        configure=lambda query, args: _apply_filters(
            query,
            args,
            eq={"season": "season", "type": "type", "country": "country"},
        ),
    )


def _resolve_results(selection: Selection) -> dict[str, Any]:
    _require_args(selection, {"tournamentId"})
    return _resolve_page(
        selection,
        table_name="fs_results",
        type_name="Result",
        allowed_args={"tournamentId", "limit", "offset"},
        configure=lambda query, args: _apply_filters(query, args, eq={"tournamentId": "tournament_id"}),
    )


def _resolve_rankings(selection: Selection) -> dict[str, Any]:
    return _resolve_page(
        selection,
        table_name="fs_rankings_history",
        type_name="Ranking",
        allowed_args={"season", "weapon", "gender", "category", "limit", "offset"},
        configure=lambda query, args: _apply_filters(
            query,
            args,
            eq={"season": "season", "weapon": "weapon", "gender": "gender", "category": "category"},
        ),
    )


def _resolve_h2h(selection: Selection) -> dict[str, Any]:
    _require_args(selection, {"fencerA", "fencerB"})
    _validate_args(selection, {"fencerA", "fencerB", "limit", "offset"})
    limit, offset = _pagination(selection.args)
    left, right = sorted([selection.args["fencerA"], selection.args["fencerB"]])
    children = _children_by_name(selection.children)
    _validate_h2h_page_children(selection, children)
    data_selection = children.get("data")
    rows: list[dict[str, Any]] = []
    if data_selection:
        row_fields = _requested_leaf_fields(data_selection, "HeadToHead")
        query = (
            get_supabase_client()
            .table("fs_head_to_head")
            .select(_select_columns("HeadToHead", row_fields))
            .eq("fencer_a_id", left)
            .eq("fencer_b_id", right)
            .range(offset, offset + limit - 1)
        )
        rows = _execute_rows(query, "fs_head_to_head")
    return _build_h2h_page(selection.args["fencerA"], selection.args["fencerB"], rows, limit, offset, children)


def _resolve_countries(selection: Selection) -> dict[str, Any]:
    _require_args(selection, {"code"})
    return _resolve_page(
        selection,
        table_name="fs_country_depth",
        type_name="CountryDepth",
        allowed_args={"code", "limit", "offset"},
        configure=lambda query, args: query.eq("country", str(args["code"]).upper()),
    )


def _resolve_news(selection: Selection) -> dict[str, Any]:
    return _resolve_page(
        selection,
        table_name="fs_social_feed",
        type_name="NewsItem",
        allowed_args={"platform", "limit", "offset"},
        configure=lambda query, args: _apply_filters(query, args, eq={"platform": "platform"}),
    )


def _resolve_products(selection: Selection) -> dict[str, Any]:
    return _resolve_page(
        selection,
        table_name="fs_equipment_reviews",
        type_name="Product",
        allowed_args={"brand", "category", "limit", "offset"},
        configure=lambda query, args: _apply_filters(query, args, eq={"brand": "brand", "category": "category"}),
    )


def _resolve_fencer(selection: Selection) -> dict[str, Any] | None:
    _require_args(selection, {"id"})
    _validate_args(selection, {"id"})
    if not selection.children:
        raise GraphQLError("Field 'fencer' requires a selection set")
    children = _children_by_name(selection.children)
    allowed_children = {"profile", "careerStats", "social", "equipment"}
    for child_name in children:
        if child_name not in allowed_children:
            raise GraphQLError(f"Unknown field '{child_name}' for FencerProfile")

    fencer_id = selection.args["id"]
    result: dict[str, Any] = {}
    if "profile" in children:
        child = children["profile"]
        fields = _requested_leaf_fields(child, "Fencer")
        rows = _execute_rows(
            get_supabase_client()
            .table("fs_fencers")
            .select(_select_columns("Fencer", fields))
            .eq("id", fencer_id)
            .limit(1),
            "fs_fencers",
        )
        if not rows:
            return None
        result[child.response_key] = _project_row(rows[0], "Fencer", fields)
    if "careerStats" in children:
        child = children["careerStats"]
        fields = _requested_leaf_fields(child, "CareerStats")
        rows = _execute_optional_rows(
            get_supabase_client()
            .table("fs_fencer_career_stats")
            .select(_select_columns("CareerStats", fields))
            .eq("fencer_id", fencer_id)
            .limit(1)
        )
        result[child.response_key] = _project_row(rows[0], "CareerStats", fields) if rows else None
    if "social" in children:
        child = children["social"]
        fields = _requested_leaf_fields(child, "SocialLink")
        rows = _execute_optional_rows(
            get_supabase_client()
            .table("fs_fencer_social_media")
            .select(_select_columns("SocialLink", fields))
            .eq("fencer_id", fencer_id)
        )
        result[child.response_key] = [_project_row(row, "SocialLink", fields) for row in rows]
    if "equipment" in children:
        child = children["equipment"]
        fields = _requested_leaf_fields(child, "FencerEquipment")
        rows = _execute_optional_rows(
            get_supabase_client()
            .table("fs_fencer_equipment")
            .select(_select_columns("FencerEquipment", fields))
            .eq("fencer_id", fencer_id)
        )
        result[child.response_key] = [_project_row(row, "FencerEquipment", fields) for row in rows]
    return result


def _resolve_page(
    selection: Selection,
    *,
    table_name: str,
    type_name: str,
    allowed_args: set[str],
    configure,
) -> dict[str, Any]:
    _validate_args(selection, allowed_args)
    limit, offset = _pagination(selection.args)
    children = _children_by_name(selection.children)
    _validate_page_children(selection, children)

    data_selection = children.get("data")
    rows: list[dict[str, Any]] = []
    row_fields: list[str] = []
    if data_selection:
        row_fields = _requested_leaf_fields(data_selection, type_name)
        query = get_supabase_client().table(table_name).select(_select_columns(type_name, row_fields))
        query = configure(query, selection.args)
        rows = _execute_rows(query.range(offset, offset + limit - 1), table_name)

    return _build_page(rows, type_name, row_fields, limit, offset, children)


def _apply_filters(query, args: dict[str, Any], *, eq: dict[str, str] | None = None, ilike: dict[str, str] | None = None):
    for arg_name, column in (eq or {}).items():
        value = args.get(arg_name)
        if value is not None and value != "":
            query = query.eq(column, value)
    for arg_name, column in (ilike or {}).items():
        value = args.get(arg_name)
        if value:
            query = query.ilike(column, f"%{value}%")
    return query


def _children_by_name(children: list[Selection]) -> dict[str, Selection]:
    return {child.name: child for child in children}


def _validate_page_children(selection: Selection, children: dict[str, Selection]) -> None:
    if not children:
        raise GraphQLError(f"Field '{selection.name}' requires a selection set")
    for child_name in children:
        if child_name not in PAGE_FIELDS:
            raise GraphQLError(f"Unknown field '{child_name}' for {selection.name} page")
    if "pagination" in children:
        _requested_leaf_fields(children["pagination"], "Pagination")


def _validate_h2h_page_children(selection: Selection, children: dict[str, Selection]) -> None:
    if not children:
        raise GraphQLError(f"Field '{selection.name}' requires a selection set")
    for child_name in children:
        if child_name not in H2H_PAGE_FIELDS:
            raise GraphQLError(f"Unknown field '{child_name}' for h2h page")
    if "pagination" in children:
        _requested_leaf_fields(children["pagination"], "Pagination")
    for scalar_name in ("fencerA", "fencerB"):
        child = children.get(scalar_name)
        if child and child.children:
            raise GraphQLError(f"Field '{scalar_name}' does not accept a nested selection")


def _requested_leaf_fields(selection: Selection, type_name: str) -> list[str]:
    if not selection.children:
        raise GraphQLError(f"Field '{selection.name}' requires a nested selection")
    allowed = FIELD_MAPS[type_name]
    fields: list[str] = []
    for child in selection.children:
        if child.children:
            raise GraphQLError(f"Field '{child.name}' for {type_name} does not accept a nested selection")
        if child.name not in allowed:
            raise GraphQLError(f"Unknown field '{child.name}' for {type_name}")
        fields.append(child.name)
    return fields


def _validate_args(selection: Selection, allowed_args: set[str]) -> None:
    for name in selection.args:
        if name not in allowed_args:
            raise GraphQLError(f"Unknown argument '{name}' for {selection.name}")


def _require_args(selection: Selection, required_args: set[str]) -> None:
    missing = [name for name in sorted(required_args) if selection.args.get(name) in {None, ""}]
    if missing:
        raise GraphQLError(f"Missing required argument(s) for {selection.name}: {', '.join(missing)}")


def _pagination(args: dict[str, Any]) -> tuple[int, int]:
    limit = _coerce_int(args.get("limit", rest_api.DEFAULT_LIMIT), "limit")
    offset = _coerce_int(args.get("offset", 0), "offset")
    if limit < 1 or limit > rest_api.MAX_LIMIT:
        raise GraphQLError(f"limit must be between 1 and {rest_api.MAX_LIMIT}")
    if offset < 0:
        raise GraphQLError("offset must be greater than or equal to 0")
    return limit, offset


def _coerce_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GraphQLError(f"{name} must be an integer")
    return value


def _select_columns(type_name: str, fields: list[str]) -> str:
    columns = []
    for field in fields:
        column = FIELD_MAPS[type_name][field]
        if column not in columns:
            columns.append(column)
    if not columns:
        columns.append(next(iter(FIELD_MAPS[type_name].values())))
    return ",".join(columns)


def _build_page(
    rows: list[dict[str, Any]],
    type_name: str,
    row_fields: list[str],
    limit: int,
    offset: int,
    children: dict[str, Selection],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if "data" in children:
        result[children["data"].response_key] = [_project_row(row, type_name, row_fields) for row in rows]
    if "pagination" in children:
        result[children["pagination"].response_key] = _project_pagination(limit, offset, len(rows), children["pagination"])
    return result


def _build_h2h_page(
    fencer_a: str,
    fencer_b: str,
    rows: list[dict[str, Any]],
    limit: int,
    offset: int,
    children: dict[str, Selection],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if "fencerA" in children:
        result[children["fencerA"].response_key] = fencer_a
    if "fencerB" in children:
        result[children["fencerB"].response_key] = fencer_b
    if "data" in children:
        row_fields = _requested_leaf_fields(children["data"], "HeadToHead")
        result[children["data"].response_key] = [_project_row(row, "HeadToHead", row_fields) for row in rows]
    if "pagination" in children:
        result[children["pagination"].response_key] = _project_pagination(limit, offset, len(rows), children["pagination"])
    return result


def _project_pagination(limit: int, offset: int, count: int, selection: Selection) -> dict[str, int]:
    source = {"limit": limit, "offset": offset, "count": count}
    return {child.response_key: source[child.name] for child in selection.children}


def _project_row(row: dict[str, Any], type_name: str, fields: list[str]) -> dict[str, Any]:
    mapping = FIELD_MAPS[type_name]
    return {field: row.get(mapping[field]) for field in fields}


def _execute_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def _execute_optional_rows(query) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except Exception:
        return []
