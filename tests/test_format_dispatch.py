"""Per-kind dispatch: is_signed (only grid), fmt (signs grid), color_of (grid by sign)."""


def test_is_signed_true_only_for_grid(app):
    assert app.is_signed({"kind": "grid"}) is True
    assert app.is_signed({"kind": "power"}) is False
    assert app.is_signed({"kind": "use"}) is False
    assert app.is_signed({"kind": "self"}) is False


def test_fmt_signs_grid_only(app):
    assert app.fmt({"kind": "grid"}, -1500) == "-1.50KW"
    assert app.fmt({"kind": "grid"}, 1500) == "+1.50KW"
    assert app.fmt({"kind": "power"}, 1500) == "1.50KW"
    assert app.fmt({"kind": "use"}, 500) == "500W"


def test_color_of_grid_green_on_export_purple_on_import(app):
    g = {"kind": "grid", "color": app.PURPLE}
    assert app.color_of(g, -100) == app.GREEN  # exporting
    assert app.color_of(g, 100) == app.PURPLE  # importing
    assert app.color_of(g, 0) == app.PURPLE  # zero counts as import


def test_color_of_nongrid_uses_stat_colour(app):
    s = {"kind": "power", "color": app.AMBER}
    assert app.color_of(s, 50) == app.AMBER
    assert app.color_of(s, -50) == app.AMBER
