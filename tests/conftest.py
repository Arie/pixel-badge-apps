"""Load the MicroPython badge app on the host for unit testing.

The app guards its hardware imports (`rgb`, `hub75`, …) and its `main()` call
behind `ON_BADGE`, so importing it off-device exposes the pure logic without
touching hardware or starting the render loop.
"""

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ha_energy" / "__init__.py"


def _load():
    spec = importlib.util.spec_from_file_location("ha_energy", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ON_BADGE is False, "tests must run off-device"
    return module


@pytest.fixture
def app():
    """Fresh module-with-cleared-readings for each test."""
    module = _load()
    module.VALUES.clear()
    return module


def stat(app, stat_id):
    return next(s for s in app.STATS if s["id"] == stat_id)
