"""Value formatting, adaptive width fit, proportional font, overflow."""

from conftest import stat


def test_fmt_power_watts_and_kw(app):
    assert app.fmt_power(523, False) == "523W"
    assert app.fmt_power(1190, False) == "1.19KW"  # 2 decimals below 10kW
    assert app.fmt_power(17250, False) == "17.2KW"  # 1 decimal at/above 10kW
    assert app.fmt_power(-2761, True) == "-2.76KW"  # signed
    assert app.fmt_power(8000, True) == "+8.00KW"


def test_fmt_bat_is_signed(app):
    assert app.fmt_bat(250) == "+250W"
    assert app.fmt_bat(-589) == "-589W"
    assert app.fmt_bat(2400) == "+2.40KW"


def test_fit_value_drops_w_then_decimal(app):
    # plenty of room: keep KW
    assert app.fit_value("1.19KW", 32) == "1.19KW"
    # tight: drop the W
    wide = app.text_width("-2.76KW")
    assert app.fit_value("-2.76KW", wide - 1) == "-2.76K"
    # tighter still: drop a decimal too
    k = app.fit_value("-2.76KW", app.text_width("-2.76K") - 1)
    assert k == "-2.7K"


def test_proportional_font_dot_is_narrow(app):
    # '.' should be ~half the width of a digit (its empty columns are trimmed)
    dot = app.text_width(".")
    digit = app.text_width("8")
    assert dot < digit


def test_text_width_matches_drawn_pixels(app):
    # draw into a fresh framebuffer; lit pixels must stay within the reported width
    app.fb_clear()
    end = app.draw_text(0, 0, "1.19KW", app.GREEN)
    lit_cols = [i % app.W for i, v in enumerate(app.fb) if v]
    assert end == app.text_width("1.19KW") + 1  # next-x = width + trailing gap
    assert max(lit_cols) <= app.text_width("1.19KW") - 1


def test_is_overflow_use_above_connection(app):
    app.VALUES.update({"SOL": 6000, "GRID": 6000, "HW1P": 0, "HW2P": 0, "ZENP": -8000})
    use = stat(app, "USE")
    assert app.value_of(use) > use["max"]
    assert app.is_overflow(use) is True


def test_is_overflow_grid_export_beyond_solar(app):
    app.VALUES["GRID"] = -8000  # exporting 8kW > 6kW solar max
    assert app.is_overflow(stat(app, "GRID")) is True
    app.VALUES["GRID"] = -3000
    assert app.is_overflow(stat(app, "GRID")) is False
