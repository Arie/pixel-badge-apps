"""poll(): fetch each configured entity into VALUES, resiliently — a single bad
entity (network error / non-numeric state) must not stop the rest. `requests` only
exists on-badge, so we inject a fake one (this is exactly how the badge wires it)."""


class _Resp:
    def __init__(self, payload):
        self._payload = payload  # dict -> json(); None -> raise (simulates a failure)

    def json(self):
        if self._payload is None:
            raise ValueError("bad response")
        return self._payload

    def close(self):
        pass


class _FakeRequests:
    def __init__(self, table):
        self.table = table  # entity_id -> payload (or None)
        self.calls = []

    def get(self, url, headers=None):
        entity = url.rsplit("/", 1)[-1]
        self.calls.append(entity)
        return _Resp(self.table.get(entity))


def test_poll_populates_every_value(app):
    table = {ent: {"state": str(i + 1)} for i, ent in enumerate(app.ENTITIES.values())}
    app.requests = _FakeRequests(table)
    app.poll()
    for sid, ent in app.ENTITIES.items():
        assert app.VALUES[sid] == float(table[ent]["state"])


def test_poll_skips_failing_entity_keeps_the_rest(app):
    items = list(app.ENTITIES.items())
    bad_sid, bad_ent = items[0]
    table = {ent: {"state": "42"} for _, ent in items}
    table[bad_ent] = None  # this one raises in .json()
    app.requests = _FakeRequests(table)
    app.poll()
    assert bad_sid not in app.VALUES  # failure isolated
    for sid, _ in items[1:]:
        assert app.VALUES[sid] == 42.0  # everyone else still updated


def test_poll_skips_non_numeric_state(app):
    items = list(app.ENTITIES.items())
    table = {ent: {"state": "12"} for _, ent in items}
    table[items[0][1]] = {"state": "unavailable"}  # float() raises
    app.requests = _FakeRequests(table)
    app.poll()
    assert items[0][0] not in app.VALUES
    assert app.VALUES[items[1][0]] == 12.0
