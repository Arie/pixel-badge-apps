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
