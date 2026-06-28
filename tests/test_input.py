"""Button callbacks: nav stepping, pause latch/toggle, brightness clamps, exit.

Characterizes the current cb_* behavior before refactoring. Each `app` fixture is a
freshly-loaded module, so `state` starts at its defaults (bright=10, nav=0, etc.)."""


def test_left_steps_back_and_latches_pause(app):
    app.cb_left(True)
    assert app.state["nav"] == -1
    assert app.state["paused"] is True


def test_right_steps_forward_and_latches_pause(app):
    app.cb_right(True)
    assert app.state["nav"] == 1
    assert app.state["paused"] is True


def test_nav_ignores_button_release(app):
    app.cb_left(False)
    assert app.state["nav"] == 0
    assert app.state["paused"] is False


def test_up_raises_brightness_by_two(app):
    app.state["bright"] = 10
    app.cb_up(True)
    assert app.state["bright"] == 12


def test_up_clamps_at_thirty(app):
    app.state["bright"] = 29
    app.cb_up(True)
    assert app.state["bright"] == 30


def test_down_lowers_brightness_by_two(app):
    app.state["bright"] = 10
    app.cb_down(True)
    assert app.state["bright"] == 8


def test_down_clamps_at_one(app):
    app.state["bright"] = 2
    app.cb_down(True)
    assert app.state["bright"] == 1
    app.cb_down(True)
    assert app.state["bright"] == 1


def test_brightness_ignores_release(app):
    app.state["bright"] = 10
    app.cb_up(False)
    app.cb_down(False)
    assert app.state["bright"] == 10


def test_a_toggles_pause(app):
    assert app.state["paused"] is False
    app.cb_a(True)
    assert app.state["paused"] is True
    app.cb_a(True)
    assert app.state["paused"] is False


def test_b_requests_exit(app):
    assert app.state["exit"] is False
    app.cb_b(True)
    assert app.state["exit"] is True


def test_b_ignores_release(app):
    app.cb_b(False)
    assert app.state["exit"] is False
