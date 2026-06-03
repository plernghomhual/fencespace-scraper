import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML_RESULTS = """
<!doctype html>
<html>
<body>
  <h1>2025年度 全日本学生フェンシング選手権大会 女子個人戦 結果</h1>
  <time>2025.10.12</time>
  <table>
    <thead>
      <tr>
        <th>順位</th><th>選手名</th><th>大学</th><th>種目</th><th>区分</th><th>得点</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>竹山 柚葉</td><td>日本大学</td><td>女子フルーレ</td><td>個人</td><td>128.5</td></tr>
      <tr><td>2</td><td>岸本 鈴</td><td>明治大学</td><td>女子エペ</td><td>個人</td><td></td></tr>
      <tr><td>合計</td><td>2名</td><td></td><td></td><td></td><td>128.5</td></tr>
      <tr><td>DNS</td><td>棄権選手</td><td>東京大学</td><td>女子サーブル</td><td>個人</td><td>0</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_SEED_PDF_TEXT = """
2025年 全日本学生フェンシング選手権大会個人戦シード表 女子
順位 | フルーレ |  | エペ |  | サーブル |
 | 氏名 | 所属 | 氏名 | 所属 | 氏名 | 所属
1 | 竹山 柚葉 | 日本大学 | 岸本 鈴 | 明治大学 | 板橋 香菜子 | 早稲田大学
2 | 永井 未寿稀 | 朝日大学 | 柳生 紗来 | 立命館大学 | 金髙 生幸 | 愛知工業大学
合計 | 2名 |  | 2名 |  | 2名 |
"""


FIXTURE_PIPE_RESULTS = """
２０２５年度 関東学生フェンシング選手権大会 男子サーブル個人戦
順位 | 氏名 | 所属 | 得点 | メダル
１ | 山田 太郎 | 早稲田大学 | 45 | 金
２ | 𠮷田 隼人 | 慶応義塾大学 | - | 銀
DQ | 失格 選手 | 日本大学 | 0 |
"""


FIXTURE_TEAM_LEAGUE_TEXT = """
2025年度 関東学生フェンシング連盟リーグ戦 男子エペ団体 結果
種目 | 校名 | 得点
男子エペ | 日本大学 | 45
男子エペ | 早稲田大学 | 38
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", content=b"", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = content or text.encode("utf-8")
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.action = None
        self.payload = None
        self.kwargs = {}
        self.filters = []
        self.columns = None

    def select(self, columns):
        self.action = "select"
        self.columns = columns
        return self

    def upsert(self, payload, **kwargs):
        self.action = "upsert"
        self.payload = payload
        self.kwargs = kwargs
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    def execute(self):
        self.client.operations.append(
            {
                "table": self.table,
                "action": self.action,
                "payload": self.payload,
                "kwargs": self.kwargs,
                "filters": self.filters,
                "columns": self.columns,
            }
        )
        if self.action == "select":
            return FakeResult(self.client.select_data.get(self.table, []))
        return FakeResult(self.payload if isinstance(self.payload, list) else [self.payload])


class FakeSupabase:
    def __init__(self):
        self.operations = []
        self.select_data = {}

    def table(self, name):
        return FakeQuery(self, name)


class FakeRunLogger:
    def __init__(self, module):
        self.module = module
        self.started = False
        self.completed = None
        self.errors = []

    def start(self):
        self.started = True
        return self

    def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
        self.completed = {
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "metadata": metadata or {},
        }

    def error(self, exc_str):
        self.errors.append(exc_str)


def test_parse_japanese_html_result_rows_preserves_cjk_and_missing_points():
    from scrape_japanese_univ import parse_results_document

    rows = parse_results_document(
        FIXTURE_HTML_RESULTS,
        source_url="https://f-gakuren.com/results.html",
    )

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "竹山 柚葉"
    assert rows[0]["university"] == "日本大学"
    assert rows[0]["weapon"] == "Foil"
    assert rows[0]["gender"] == "Women"
    assert rows[0]["category"] == "Individual"
    assert rows[0]["points"] == 128.5
    assert rows[0]["medal"] == "Gold"
    assert rows[0]["season"] == "2025-2026"
    assert rows[0]["date"] == "2025-10-12"
    assert rows[0]["source_url"] == "https://f-gakuren.com/results.html"
    assert rows[1]["name"] == "岸本 鈴"
    assert rows[1]["points"] is None
    assert rows[1]["medal"] == "Silver"


def test_parse_side_by_side_pdf_seed_table_expands_weapon_columns():
    from scrape_japanese_univ import parse_results_document

    rows = parse_results_document(
        FIXTURE_SEED_PDF_TEXT,
        source_url="https://f-kantogakuren.com/wp-content/uploads/2025/10/seeds.pdf",
    )

    assert len(rows) == 6
    sabre_second = next(row for row in rows if row["name"] == "金髙 生幸")
    assert sabre_second["rank"] == 2
    assert sabre_second["university"] == "愛知工業大学"
    assert sabre_second["weapon"] == "Sabre"
    assert sabre_second["gender"] == "Women"
    assert sabre_second["category"] == "Individual"
    assert sabre_second["points"] is None
    assert rows[0]["name"] == "竹山 柚葉"
    assert rows[0]["university"] == "日本大学"


def test_pipe_fixture_skips_summary_and_dq_rows_and_parses_fullwidth_rank():
    from scrape_japanese_univ import parse_results_document

    rows = parse_results_document(
        FIXTURE_PIPE_RESULTS,
        source_url="https://f-kantogakuren.com/results.pdf",
    )

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "山田 太郎"
    assert rows[0]["university"] == "早稲田大学"
    assert rows[0]["weapon"] == "Sabre"
    assert rows[0]["gender"] == "Men"
    assert rows[0]["points"] == 45.0
    assert rows[0]["medal"] == "Gold"
    assert rows[1]["name"] == "𠮷田 隼人"
    assert rows[1]["points"] is None
    assert rows[1]["medal"] == "Silver"


def test_normalize_name_preserves_unicode_without_ascii_folding():
    from scrape_japanese_univ import normalize_name

    assert normalize_name("  金髙　生幸  ") == "金髙 生幸"
    assert normalize_name("バーナード洋人") == "バーナード洋人"
    assert normalize_name("𠮷田　隼人") == "𠮷田 隼人"


def test_blocked_source_returns_deterministic_stub():
    from scrape_japanese_univ import SourceConfig, fetch_source_document

    source = SourceConfig(
        name="blocked",
        url="https://blocked.example/results.pdf",
        competition_name="Blocked Source",
    )
    session = FakeSession([FakeResponse(status_code=403, text="Forbidden")])

    document = fetch_source_document(source, session=session)

    assert document.status == "blocked"
    assert document.rows == []
    assert "HTTP 403" in document.reason
    assert session.calls[0][0] == "https://blocked.example/results.pdf"


def test_result_rows_match_fencers_best_effort_and_log_unmatched():
    from scrape_japanese_univ import build_fencer_index, build_result_rows, build_tournament_rows

    parsed = parse_fixture_rows()
    tournaments = build_tournament_rows(parsed)
    tournament_ids = {row["source_id"]: 101 + index for index, row in enumerate(tournaments)}
    fencer_index = build_fencer_index(
        [
            {"id": "fencer-1", "name": "竹山 柚葉", "country": "Japan"},
            {"id": "wrong-country", "name": "岸本 鈴", "country": "Korea"},
        ]
    )

    rows, unmatched = build_result_rows(parsed, tournament_ids, fencer_index)

    takeyama = next(row for row in rows if row["name"] == "竹山 柚葉")
    kishimoto = next(row for row in rows if row["name"] == "岸本 鈴")
    assert takeyama["fencer_id"] == "fencer-1"
    assert takeyama["metadata"]["match_method"] == "exact_name_country"
    assert takeyama["metadata"]["university"] == "日本大学"
    assert kishimoto["fencer_id"] is None
    assert kishimoto["metadata"]["match_method"] == "unmatched"
    assert unmatched == ["岸本 鈴 | 明治大学 | Women Epee Individual"]


def test_team_rows_do_not_match_school_names_to_fencers():
    from scrape_japanese_univ import (
        build_fencer_index,
        build_result_rows,
        build_tournament_rows,
        parse_results_document,
    )

    parsed = parse_results_document(
        FIXTURE_TEAM_LEAGUE_TEXT,
        source_url="https://f-kantogakuren.com/league.pdf",
    )
    tournament_ids = {row["source_id"]: 201 + index for index, row in enumerate(build_tournament_rows(parsed))}
    fencer_index = build_fencer_index([{"id": "school-named-fencer", "name": "日本大学", "country": "Japan"}])

    rows, unmatched = build_result_rows(parsed, tournament_ids, fencer_index)

    assert len(rows) == 2
    assert rows[0]["name"] == "日本大学"
    assert rows[0]["metadata"]["university"] == "日本大学"
    assert rows[0]["metadata"]["category"] == "Team"
    assert rows[0]["metadata"]["rank_source"] == "row_order"
    assert rows[0]["fencer_id"] is None
    assert rows[0]["metadata"]["match_method"] == "team_row"
    assert unmatched == []


def test_upserts_use_expected_conflict_keys():
    from scrape_japanese_univ import upsert_results, upsert_tournaments

    fake = FakeSupabase()
    fake.select_data["fs_tournaments"] = [{"id": 101, "source_id": "jpn_univ:one"}]

    ids = upsert_tournaments(fake, [{"source_id": "jpn_univ:one", "name": "All Japan Students"}])
    upsert_results(
        fake,
        [
            {
                "tournament_id": 101,
                "name": "竹山 柚葉",
                "rank": 1,
                "metadata": {"source_result_id": "jpn_univ:one:1"},
            }
        ],
    )

    assert ids == {"jpn_univ:one": 101}
    assert fake.operations[0]["table"] == "fs_tournaments"
    assert fake.operations[0]["action"] == "upsert"
    assert fake.operations[0]["kwargs"] == {"on_conflict": "source_id"}
    assert fake.operations[-1]["table"] == "fs_results"
    assert fake.operations[-1]["action"] == "upsert"
    assert fake.operations[-1]["kwargs"] == {"on_conflict": "tournament_id,name"}


def test_scrape_sources_logs_state_and_skips_blocked_source(monkeypatch):
    import scrape_japanese_univ
    from scrape_japanese_univ import SourceConfig, scrape_sources

    source = SourceConfig(
        name="blocked",
        url="https://blocked.example/results.pdf",
        competition_name="Blocked Source",
    )
    fake_client = FakeSupabase()
    fake_logger = FakeRunLogger("scrape_japanese_univ")
    state_updates = []
    monkeypatch.setattr(scrape_japanese_univ, "get_state", lambda source, key: [])
    monkeypatch.setattr(
        scrape_japanese_univ,
        "set_state",
        lambda source, key, value: state_updates.append((source, key, value)),
    )

    summary = scrape_sources(
        [source],
        client=fake_client,
        session=FakeSession([FakeResponse(status_code=403, text="Forbidden")]),
        logger_factory=lambda module: fake_logger,
        sleep_fn=lambda seconds: None,
    )

    assert summary == {
        "sources_checked": 1,
        "tournaments_written": 0,
        "results_written": 0,
        "failed": 0,
        "skipped": 1,
        "unmatched": 0,
    }
    assert fake_logger.started is True
    assert fake_logger.completed["written"] == 0
    assert fake_logger.completed["failed"] == 0
    assert fake_logger.completed["skipped"] == 1
    assert fake_logger.completed["metadata"]["blocked_sources"] == ["https://blocked.example/results.pdf"]
    assert state_updates[-1][0] == "scrape_japanese_univ"
    assert state_updates[-1][1] == "last_run"
    assert state_updates[-1][2]["skipped"] == 1
    assert fake_client.operations == []


def parse_fixture_rows():
    from scrape_japanese_univ import parse_results_document

    return parse_results_document(
        FIXTURE_HTML_RESULTS,
        source_url="https://f-gakuren.com/results.html",
    )
