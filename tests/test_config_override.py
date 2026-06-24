"""Step 3 (feature): config.json overrides DEFAULTS, so STATS / entities / maxima
reflect a different install. Drives _build_stats directly with crafted configs."""


def cfg_with(app, **over):
    c = dict(app.DEFAULTS)
    c.update(over)
    return c


def test_two_battery_config(app):
    cfg = cfg_with(
        app,
        batteries=[
            {
                "label": "A",
                "soc": "sensor.a_soc",
                "power": "sensor.a_pw",
                "power_max": 1000,
                "weight": 2,
                "soc_min": 5,
            },
            {"label": "B", "soc": "sensor.b_soc", "power": "sensor.b_pw"},
        ],
    )
    stats, ents, pids = app._build_stats(cfg)
    bats = [s for s in stats if s["kind"] == "battery"]
    assert [b["id"] for b in bats] == ["A", "B"]
    assert pids == ["AP", "BP"]
    assert ents["A"] == "sensor.a_soc" and ents["AP"] == "sensor.a_pw"
    assert (bats[0]["powerMax"], bats[0]["weight"], bats[0]["socMin"]) == (1000, 2, 5)
    # missing battery fields fall back to defaults
    assert (bats[1]["powerMax"], bats[1]["weight"], bats[1]["socMin"]) == (800, 1, 0)


def test_custom_maxima(app):
    stats, _, _ = app._build_stats(cfg_with(app, grid_connection_w=10000, solar_max_w=4000))
    g = {s["id"]: s for s in stats}
    assert g["USE"]["max"] == 10000
    assert g["SOL"]["max"] == 4000 and g["SELF"]["max"] == 4000
    assert (g["GRID"]["maxPos"], g["GRID"]["maxNeg"]) == (10000, 4000)


def test_flow_entities_mapped(app):
    _, ents, _ = app._build_stats(cfg_with(app, solar_entity="sensor.pv", grid_entity="sensor.p1"))
    assert ents["SOL"] == "sensor.pv" and ents["GRID"] == "sensor.p1"


def test_malformed_batteries_skipped(app):
    cfg = cfg_with(
        app,
        batteries=[
            {"label": "OK", "soc": "sensor.s", "power": "sensor.p"},
            {"label": "BAD"},  # no soc/power
            {"soc": "x", "power": "y"},  # no label
            {},  # empty
        ],
    )
    stats, ents, pids = app._build_stats(cfg)
    assert [s["id"] for s in stats if s["kind"] == "battery"] == ["OK"]
    assert pids == ["OKP"]


def test_no_batteries(app):
    stats, ents, pids = app._build_stats(cfg_with(app, batteries=[]))
    assert [s["id"] for s in stats] == ["USE", "SOL", "SELF", "GRID", "EV"]
    assert pids == []


def test_ev_charger_optional(app):
    # present by default (this install has a Peblar): hide-when-idle power stat, 11kW gauge
    g = {s["id"]: s for s in app._build_stats(dict(app.DEFAULTS))[0]}
    assert g["EV"]["kind"] == "power" and g["EV"]["max"] == 11000 and g["EV"]["hideIdle"]
    # absent when no ev_entity configured
    cfg = dict(app.DEFAULTS)
    cfg["ev_entity"] = ""
    assert "EV" not in [s["id"] for s in app._build_stats(cfg)[0]]
