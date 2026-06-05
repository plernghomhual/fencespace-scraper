from enrich_locations import link_tournaments_to_venue


class FakeRpc:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpcs.append((self.name, self.params))
        return type("Result", (), {"data": len(self.params["p_updates"])})()


class FakeClient:
    def __init__(self):
        self.rpcs = []
        self.updates = []

    def rpc(self, name, params):
        return FakeRpc(self, name, params)

    def table(self, table_name):
        self.table_name = table_name
        return self

    def update(self, values):
        self.values = values
        return self

    def eq(self, column, value):
        self.updates.append((self.table_name, column, value, self.values))
        return self

    def execute(self):
        return type("Result", (), {"data": []})()


def test_link_tournaments_to_venue_bulk_updates_metadata():
    client = FakeClient()
    tournaments = [
        {"id": "t-1", "metadata": {"source": "fie"}},
        {"id": "t-2", "metadata": {"venue_id": "venue-1"}},
        {"id": "t-3", "metadata": {}},
    ]

    linked = link_tournaments_to_venue(client, tournaments, "venue-1")

    assert linked == 2
    assert client.rpcs == [
        (
            "fs_bulk_update_tournament_metadata",
            {
                "p_updates": [
                    {"id": "t-1", "metadata": {"source": "fie", "venue_id": "venue-1"}},
                    {"id": "t-3", "metadata": {"venue_id": "venue-1"}},
                ]
            },
        )
    ]
    assert client.updates == []
    assert tournaments[0]["metadata"]["venue_id"] == "venue-1"
    assert tournaments[2]["metadata"]["venue_id"] == "venue-1"
