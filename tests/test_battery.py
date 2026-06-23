"""Battery logic: usable-SOC remap, weighted fleet SOC, idle filter, colours."""

from conftest import stat


def test_display_soc_remaps_zen_floor(app):
    # ZEN is empty at 10% → 10 maps to 0, 100 stays 100, 55 → 50.
    app.VALUES.update({"ZEN": 10})
    assert app.display_soc(stat(app, "ZEN")) == 0
    app.VALUES.update({"ZEN": 55})
    assert app.display_soc(stat(app, "ZEN")) == 50
    app.VALUES.update({"ZEN": 100})
    assert app.display_soc(stat(app, "ZEN")) == 100


def test_display_soc_hw_is_identity(app):
    app.VALUES.update({"HW1": 78})
    assert app.display_soc(stat(app, "HW1")) == 78


def test_fleet_soc_weights_zen_triple(app):
    # usable: HW1=80, HW2=40, ZEN raw 100 → 100. Weighted (1,1,3): (80+40+300)/5 = 84.
    app.VALUES.update({"HW1": 80, "HW2": 40, "ZEN": 100})
    assert app.fleet_soc() == 84


def test_idle_battery_hidden(app):
    app.VALUES.update({"HW1P": 0, "HW2P": 0, "ZENP": 5})  # all under the 10W idle threshold
    assert app.is_active(stat(app, "HW1")) is False
    assert app.is_active(stat(app, "ZEN")) is False


def test_active_battery_shown(app):
    app.VALUES.update({"HW1P": 250})
    assert app.is_active(stat(app, "HW1")) is True


def test_all_idle_batteries_collapse_to_summary(app):
    app.VALUES.update({"SOL": 0, "HW1P": 0, "HW2P": 0, "ZENP": 0})
    seq = app.active_stats()
    ids = [s["id"] for s in seq]
    assert "BAT" in ids  # the summary stands in
    assert not any(i in ids for i in ("HW1", "HW2", "ZEN"))


def test_some_active_batteries_no_summary(app):
    app.VALUES.update({"HW1P": 250, "HW2P": 0, "ZENP": -600})
    ids = [s["id"] for s in app.active_stats()]
    assert "BAT" not in ids
    assert "HW1" in ids and "ZEN" in ids
    assert "HW2" not in ids  # idle one stays hidden


def test_solar_hidden_at_night(app):
    app.VALUES.update({"SOL": 2})
    assert app.is_active(stat(app, "SOL")) is False
    app.VALUES.update({"SOL": 1200})
    assert app.is_active(stat(app, "SOL")) is True


def test_power_colour_charge_vs_discharge(app):
    assert app.power_color(250) == app.PURPLE  # charging
    assert app.power_color(-180) == app.GREEN  # discharging


def test_soc_colour_bands(app):
    assert app.soc_color(80) == app.GREEN
    assert app.soc_color(35) == app.AMBER
    assert app.soc_color(10) == app.RED
