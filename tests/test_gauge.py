"""gauge(): the row-7 bar — fraction = |value| / applicable-max, grid scales by
sign (maxNeg/maxPos), over-max blinks a full ALERT bar. Reads the framebuffer."""


def _row7(app):
    return [app.fb[7 * app.W + x] for x in range(app.W)]


def _pack(c):
    r, g, b = c
    return (r << 24) | (g << 16) | (b << 8) | 255


def test_power_half_fills_half_in_colour(app):
    app.fb_clear()
    app.blink_on = True
    app.gauge({"kind": "power", "max": 1000}, 500, app.GREEN)
    lit = [c for c in _row7(app) if c]
    assert len(lit) == 16  # int(0.5*32+0.5)
    assert all(c == _pack(app.GREEN) for c in lit)


def test_grid_negative_scales_by_maxneg(app):
    app.fb_clear()
    app.blink_on = True
    # export 3000 against maxNeg 6000 -> half bar
    app.gauge({"kind": "grid", "maxPos": 17250, "maxNeg": 6000}, -3000, app.GREEN)
    assert len([c for c in _row7(app) if c]) == 16


def test_grid_positive_scales_by_maxpos(app):
    app.fb_clear()
    app.blink_on = True
    # import 3000 against maxPos 6000 -> half bar (would be < half against 17250)
    app.gauge({"kind": "grid", "maxPos": 6000, "maxNeg": 17250}, 3000, app.PURPLE)
    assert len([c for c in _row7(app) if c]) == 16


def test_overflow_blinks_full_alert(app):
    app.fb_clear()
    app.blink_on = True
    app.gauge({"kind": "power", "max": 1000}, 2000, app.GREEN)
    lit = [c for c in _row7(app) if c]
    assert len(lit) == app.W
    assert all(c == _pack(app.ALERT) for c in lit)


def test_overflow_draws_nothing_on_blink_off(app):
    app.fb_clear()
    app.blink_on = False
    app.gauge({"kind": "power", "max": 1000}, 2000, app.GREEN)
    assert not any(_row7(app))
