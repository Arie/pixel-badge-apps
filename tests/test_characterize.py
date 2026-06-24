"""Characterization tests: pin the CURRENT hardcoded config so the upcoming
config-driven build (defaults == these values) is a provable refactor, not a
behaviour change. If a value here must change, that's a deliberate decision."""


def by_id(app):
    return {s["id"]: s for s in app.STATS}


def test_stats_order(app):
    assert [s["id"] for s in app.STATS] == ["USE", "SOL", "SELF", "GRID", "EV", "HW1", "HW2", "ZEN"]


def test_stat_kinds(app):
    assert {s["id"]: s["kind"] for s in app.STATS} == {
        "USE": "use",
        "SOL": "power",
        "SELF": "self",
        "GRID": "grid",
        "EV": "power",
        "HW1": "battery",
        "HW2": "battery",
        "ZEN": "battery",
    }


def test_flow_maxima(app):
    g = by_id(app)
    assert g["USE"]["max"] == 17250  # grid connection rating
    assert g["SOL"]["max"] == 6000  # solar inverter
    assert g["SELF"]["max"] == 6000
    assert g["GRID"]["maxPos"] == 17250  # import full-scale
    assert g["GRID"]["maxNeg"] == 6000  # export full-scale


def test_hide_idle_flags(app):
    g = by_id(app)
    assert g["SOL"].get("hideIdle") is True
    assert g["SELF"].get("hideIdle") is True
    assert not g["USE"].get("hideIdle")
    assert not g["GRID"].get("hideIdle")


def test_battery_params(app):
    def params(s):
        return (s["socId"], s["powerId"], s["weight"], s["socMin"])

    g = by_id(app)
    assert params(g["HW1"]) == ("HW1", "HW1P", 1, 0)
    assert params(g["HW2"]) == ("HW2", "HW2P", 1, 0)
    assert params(g["ZEN"]) == ("ZEN", "ZENP", 3, 10)


def test_constants(app):
    assert app.IDLE_W == 10
    assert app.USE_SCALE == 6000  # USE bar full-scale (= solar max)


def test_use_overflow_threshold_is_connection_rating(app):
    # the boost-overflow blink keys off 17250 in draw_use_bar / is_overflow
    g = by_id(app)
    app.VALUES.update({"SOL": 0, "GRID": 0, "HW1P": -18000, "HW2P": 0, "ZENP": 0})
    assert app.value_of(g["USE"]) == 18000  # >17250
    assert app.is_overflow(g["USE"]) is True
