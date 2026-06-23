"""USE / SELF derivations — the sign + clamp bugs we hit on hardware."""

from conftest import stat


def test_use_subtracts_battery_power(app):
    # House load = solar + grid − Σbattery. Zendure discharging (−589) supplies the house.
    app.VALUES.update({"SOL": 2, "GRID": 25, "HW1P": 0, "HW2P": 0, "ZENP": -589})
    assert app.value_of(stat(app, "USE")) == 2 + 25 + 589  # == 616, not −562


def test_use_with_charging_batteries(app):
    # Charging (+) draws from the house, so it adds to consumption.
    app.VALUES.update({"SOL": 3284, "GRID": -984, "HW1P": 250, "HW2P": 0, "ZENP": 600})
    assert app.value_of(stat(app, "USE")) == 3284 - 984 - 850  # 1450


def test_self_is_solar_minus_export(app):
    app.VALUES.update({"SOL": 3000, "GRID": -1200})  # exporting 1200 of the 3000 solar
    assert app.value_of(stat(app, "SELF")) == 1800


def test_self_never_negative_on_battery_export_at_night(app):
    # No solar, but the battery exports to the grid → must NOT show a bogus negative self-use.
    app.VALUES.update({"SOL": 0, "GRID": -500})
    assert app.value_of(stat(app, "SELF")) == 0


def test_self_import_no_export(app):
    app.VALUES.update({"SOL": 2, "GRID": 25})  # importing → nothing exported
    assert app.value_of(stat(app, "SELF")) == 2
