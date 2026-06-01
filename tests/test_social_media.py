import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


WIKIDATA_BINDING = {
    "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
    "athleteLabel": {"value": "Aldo Montano"},
    "fie_id": {"value": "37049"},
    "instagram": {"value": "@aldo_montano"},
    "twitter": {"value": "AldoMontano"},
    "youtube": {"value": "UCabc123"},
    "tiktok": {"value": "@aldomontano"},
    "facebook": {"value": "aldo.montano.official"},
}


FEDERATION_PROFILE_HTML = """
<!doctype html>
<html>
  <body>
    <header>
      <ul class="socials">
        <li><a href="https://twitter.com/FIE_fencing"></a></li>
      </ul>
    </header>
    <main class="AthletePage">
      <section class="AthleteSocialLinks">
        <a href="https://www.instagram.com/lee_kiefer/">Instagram</a>
        <a href="https://x.com/leetothekiefer">X</a>
        <a href="https://www.youtube.com/@LeeKieferOfficial">YouTube</a>
        <a href="https://www.tiktok.com/@leekiefer">TikTok</a>
        <a href="https://www.facebook.com/LeeKieferUSA">Facebook</a>
        <a href="https://www.threads.net/@lee_kiefer">Threads</a>
        <a class="social-link" rel="me" href="https://mastodon.social/@lee">Mastodon</a>
      </section>
    </main>
    <div class="xs-menu">
      <div class="flex-parent social">
        <a href="https://www.instagram.com/fencing_fie/"></a>
        <a href="https://www.youtube.com/user/FIEvideo"></a>
      </div>
    </div>
  </body>
</html>
"""


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.filters = []
        self.range_bounds = None
        self.operation = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column):
        self.order_column = column
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": rows,
                "on_conflict": on_conflict,
            }
        )
        return self

    def execute(self):
        if self.operation == "upsert":
            return FakeResult([])
        if self.name == "fs_fencers":
            self.client.selects.append({"columns": self.columns, "filters": self.filters})
            if self.range_bounds is not None:
                start, end = self.range_bounds
                return FakeResult(self.client.profile_fencers[start : end + 1])
            if ("metadata->>wikidata_id", "Q312123") in self.filters:
                return FakeResult(self.client.wikidata_matches)
            if ("fie_id", "37049") in self.filters:
                return FakeResult(self.client.fie_matches)
        return FakeResult([])


class FakeSupabase:
    def __init__(self):
        self.wikidata_matches = [{"id": "fencer-a"}, {"id": "fencer-b"}]
        self.fie_matches = [{"id": "fencer-c"}]
        self.profile_fencers = [
            {
                "id": "fencer-profile",
                "fie_id": "12345",
                "metadata": {"fie_profile_scrape": {"profile_url": "https://fie.org/athletes/12345"}},
            }
        ]
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FakeSparqlResponse:
    def __init__(self, bindings):
        self.status_code = 200
        self._bindings = bindings

    def json(self):
        return {"results": {"bindings": self._bindings}}


class FakeHttpResponse:
    status_code = 200
    text = FEDERATION_PROFILE_HTML


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, timeout):
        self.urls.append((url, timeout))
        return FakeHttpResponse()


def test_fetch_wikidata_social_bindings_uses_social_properties_and_pages(monkeypatch):
    import scrape_social_media as sm

    calls = []
    pages = [[WIKIDATA_BINDING], []]

    def fake_get(url, params, headers, timeout):
        calls.append(params["query"])
        return FakeSparqlResponse(pages.pop(0))

    monkeypatch.setattr(sm.requests, "get", fake_get)
    monkeypatch.setattr(sm.time, "sleep", lambda delay: None)

    rows = sm.fetch_wikidata_social_bindings(page_size=1, delay=0)

    assert rows == [WIKIDATA_BINDING]
    assert "wdt:P2003" in calls[0]
    assert "wdt:P2002" in calls[0]
    assert "wdt:P2397" in calls[0]
    assert "wdt:P7085" in calls[0]
    assert "wdt:P2013" in calls[0]
    assert "OFFSET 1" in calls[1]


def test_wikidata_binding_builds_platform_rows_with_canonical_urls():
    import scrape_social_media as sm

    parsed = sm.parse_wikidata_social_binding(WIKIDATA_BINDING)
    rows = sm.build_social_rows_for_fencers(parsed, ["fencer-a"], source="wikidata")

    by_platform = {row["platform"]: row for row in rows}
    assert set(by_platform) == {"instagram", "twitter", "youtube", "tiktok", "facebook"}
    assert by_platform["instagram"]["handle"] == "aldo_montano"
    assert by_platform["instagram"]["url"] == "https://www.instagram.com/aldo_montano/"
    assert by_platform["twitter"]["url"] == "https://twitter.com/AldoMontano"
    assert by_platform["youtube"]["url"] == "https://www.youtube.com/channel/UCabc123"
    assert by_platform["tiktok"]["url"] == "https://www.tiktok.com/@aldomontano"
    assert by_platform["facebook"]["url"] == "https://www.facebook.com/aldo.montano.official"
    assert by_platform["facebook"]["metadata"]["wikidata_id"] == "Q312123"


def test_federation_profile_parser_ignores_header_footer_social_links():
    import scrape_social_media as sm

    links = sm.extract_social_links_from_html(
        FEDERATION_PROFILE_HTML,
        base_url="https://fie.org/athletes/12345",
    )

    by_platform = {link["platform"]: link for link in links}
    assert set(by_platform) == {
        "instagram",
        "twitter",
        "youtube",
        "tiktok",
        "facebook",
        "threads",
        "other",
    }
    assert by_platform["twitter"]["handle"] == "leetothekiefer"
    assert by_platform["threads"]["handle"] == "lee_kiefer"
    assert by_platform["other"]["url"] == "https://mastodon.social/@lee"
    assert all("FIE_fencing" not in link["url"] for link in links)
    assert all("fencing_fie" not in link["url"] for link in links)


def test_federation_profile_parser_reads_json_same_as_social_links():
    import scrape_social_media as sm

    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@type": "Person",
            "sameAs": [
              "https://www.instagram.com/alice_fencer/",
              "https://www.threads.net/@alice_fencer"
            ]
          }
        </script>
      </head>
      <body>
        <script>
          window.__athlete = {"social": {"tiktok": "https://www.tiktok.com/@aliceparry"}};
        </script>
      </body>
    </html>
    """

    links = sm.extract_social_links_from_html(html, base_url="https://fie.org/athletes/55")

    by_platform = {link["platform"]: link for link in links}
    assert by_platform["instagram"]["handle"] == "alice_fencer"
    assert by_platform["threads"]["handle"] == "alice_fencer"
    assert by_platform["tiktok"]["handle"] == "aliceparry"


def test_wikidata_pass_matches_by_metadata_and_upserts_for_each_fencer(monkeypatch):
    import scrape_social_media as sm

    client = FakeSupabase()
    monkeypatch.setattr(sm, "fetch_wikidata_social_bindings", lambda: [WIKIDATA_BINDING])

    stats = sm.scrape_wikidata_social_media(client)

    assert stats == {"bindings": 1, "matched": 2, "written": 10, "skipped": 0, "failed": 0}
    assert client.selects[0]["filters"] == [("metadata->>wikidata_id", "Q312123")]
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_fencer_social_media"
    assert client.upserts[0]["on_conflict"] == "fencer_id,platform"
    assert len(client.upserts[0]["rows"]) == 10


def test_federation_profile_pass_uses_state_cursor_and_profile_html(monkeypatch):
    import scrape_social_media as sm

    client = FakeSupabase()
    session = FakeSession()
    state_updates = []

    monkeypatch.setattr(sm, "get_state", lambda source, key: {"offset": 0})
    monkeypatch.setattr(sm, "set_state", lambda source, key, value: state_updates.append((source, key, value)))

    stats = sm.scrape_federation_profiles(client, session=session, limit=10, delay=0)

    assert stats == {"profiles": 1, "written": 7, "skipped": 0, "failed": 0}
    assert session.urls == [("https://fie.org/athletes/12345", 20)]
    assert client.upserts[0]["table"] == "fs_fencer_social_media"
    assert client.upserts[0]["on_conflict"] == "fencer_id,platform"
    assert {row["source"] for row in client.upserts[0]["rows"]} == {"federation_profile"}
    assert {row["verified"] for row in client.upserts[0]["rows"]} == {True}
    assert state_updates[-1][1] == "federation_cursor"
    assert state_updates[-1][2]["offset"] == 0
