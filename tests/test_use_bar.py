"""USE two-tone bar: split into self-use / grid-import / export."""


def test_importing(app):
    # solar < usage: solar all self-used, rest imported, nothing exported
    assert app.use_segments(2500, 1500) == (1500, 1000, 0)


def test_zero_metering(app):
    assert app.use_segments(2000, 2000) == (2000, 0, 0)


def test_exporting(app):
    # solar > usage: usage all from solar, surplus exported
    assert app.use_segments(1500, 3500) == (1500, 0, 2000)


def test_high_usage_above_scale(app):
    # >6kW usage still splits correctly (the bar just clamps when drawn)
    assert app.use_segments(8000, 2000) == (2000, 6000, 0)


def test_no_solar(app):
    assert app.use_segments(1200, 0) == (0, 1200, 0)


# ---- drawn bar: pixel boundaries + overflow (USE_SCALE=6000, W=32) -----------


def _row7(app):
    return [app.fb[7 * app.W + x] for x in range(app.W)]


def _pack(c):
    r, g, b = c
    return (r << 24) | (g << 16) | (b << 8) | 255


def test_bar_import_green_then_purple(app):
    app.fb_clear()
    app.blink_on = True
    app.VALUES["SOL"] = 3000
    app.draw_use_bar(4500)  # self 3000 (->16px), import 1500 (->24), no export
    row = _row7(app)
    assert [i for i, c in enumerate(row) if c == _pack(app.GREEN)] == list(range(16))
    assert [i for i, c in enumerate(row) if c == _pack(app.PURPLE)] == list(range(16, 24))
    assert not [c for c in row if c == _pack(app.AMBER)]


def test_bar_export_green_then_amber(app):
    app.fb_clear()
    app.blink_on = True
    app.VALUES["SOL"] = 4500
    app.draw_use_bar(3000)  # self 3000 (->16px), no import, export to solar 4500 (->24)
    row = _row7(app)
    assert [i for i, c in enumerate(row) if c == _pack(app.GREEN)] == list(range(16))
    assert [i for i, c in enumerate(row) if c == _pack(app.AMBER)] == list(range(16, 24))
    assert not [c for c in row if c == _pack(app.PURPLE)]


def test_bar_overflow_blinks_full_alert(app):
    app.fb_clear()
    app.blink_on = True
    app.VALUES["SOL"] = 0
    app.draw_use_bar(app.GRID_MAX + 1000)  # beyond the grid connection
    lit = [c for c in _row7(app) if c]
    assert len(lit) == app.W
    assert all(c == _pack(app.ALERT) for c in lit)
