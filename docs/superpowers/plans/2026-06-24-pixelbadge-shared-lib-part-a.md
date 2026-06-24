# pixelbadge Shared Library (Part A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `ha_energy`'s reusable rendering primitives into a shared, on-badge importable `pixelbadge` library without changing behavior.

**Architecture:** A package at `lib/pixelbadge/` (deployed to the badge's `/lib`, which is on `sys.path`) holds the framebuffer, font, bar drawing, and Carousel. `ha_energy` imports them via absolute imports (`import pixelbadge.matrix`). The hardware modules (`rgb`/`hub75`) sit behind an `ImportError` guard so the library imports on the host for tests. Each component moves in its own task; the full pytest suite stays green throughout, and the app is confirmed on the panel at the end.

**Tech Stack:** MicroPython (badge) / CPython (host tests), uv, pytest, ruff.

## Global Constraints

- MicroPython compatible: no f-strings (use `%`), no type hints in lib modules, absolute imports only (no `from . import`).
- The existing **42-test suite must stay green after every task** (it transitively exercises moved code via the `app` fixture's re-exported names).
- Host-importability: any lib module that touches `rgb`/`hub75`/`wifi`/`urequests` guards it with `try/except ImportError`.
- ruff gate must pass exactly as CI runs it: `uv run ruff check .` AND `uv run ruff format --check .` AND `uv run pytest`.
- Deploy via the proven path: free `/dev/ttyUSB1`, then `uv run tools/badge.py ...`.
- Scope: only `matrix`, `pixelfont`, `gauges` (`bar_left`), `carousel` move in this plan. `gauge()` (couples to stat schema + `blink_on`), the `Display` loop, `poll`, input handlers, and config/`netclient` stay in `app/ha_energy` — deferred to a Part A.2 plan once `net_traffic` defines the shared loop/gauge contract.

---

### Task 1: Prove `/lib` import on-device + wire host import path

**Files:**
- Create: `lib/pixelbadge/__init__.py`
- Modify: `pyproject.toml` (pytest config)

**Interfaces:**
- Produces: an importable `pixelbadge` package (host + badge); `pixelbadge.VERSION` (str).

- [ ] **Step 1: Create the package marker**

`lib/pixelbadge/__init__.py`:
```python
# pixelbadge — shared primitives for CampZone 2019 "Pixel" badge apps.
VERSION = "0.1.0"
```

- [ ] **Step 2: Put `lib/` on the pytest import path**

In `pyproject.toml`, under `[tool.pytest.ini_options]` add:
```toml
pythonpath = ["lib"]
```

- [ ] **Step 3: Verify host import works**

Run: `cd /home/arie/Projects/pixel-badge-apps && uv run python -c "import pixelbadge; print(pixelbadge.VERSION)"`
Expected: `0.1.0`

- [ ] **Step 4: Smoke-test the import on the badge**

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py put lib/pixelbadge/__init__.py lib/pixelbadge/__init__.py
uv run tools/badge.py exec "import pixelbadge; print('LIBVER', pixelbadge.VERSION)"
```
Expected: output contains `LIBVER 0.1.0` (proves `/lib/pixelbadge` is importable on-device).

- [ ] **Step 5: Commit**

```bash
git add lib/pixelbadge/__init__.py pyproject.toml
git commit -m "pixelbadge: package skeleton + pytest path; on-device import proven"
```

---

### Task 2: Characterization fb-tests (written against current app, before moving)

These pin `px`/`draw_text`/`bar_left` at the framebuffer level. They reference `app.px` etc.; after extraction the app re-exports those names via import, so the tests stay valid and prove the move preserved behavior.

**Files:**
- Create: `tests/test_matrix.py`

**Interfaces:**
- Consumes: `app.fb`, `app.fb_clear`, `app.px`, `app.draw_text`, `app.bar_left` (all currently defined in `app/ha_energy/__init__.py`).

- [ ] **Step 1: Write the tests**

`tests/test_matrix.py`:
```python
"""Framebuffer-level characterization: px / draw_text / bar_left.
Targets app.* names so it stays valid before and after extraction."""


def test_px_packs_color(app):
    app.fb_clear()
    app.px(0, 0, (255, 0, 0))
    assert app.fb[0] == (255 << 24) | (0 << 16) | (0 << 8) | 255


def test_px_clips_offscreen(app):
    app.fb_clear()
    for x, y in [(-1, 0), (32, 0), (0, -1), (0, 8)]:
        app.px(x, y, (255, 255, 255))
    assert all(v == 0 for v in app.fb)


def test_bar_left_half_lights_16(app):
    app.fb_clear()
    app.bar_left(7, 0.5, (1, 2, 3))
    row = [app.fb[7 * 32 + i] for i in range(32)]
    assert sum(1 for v in row if v) == 16
    assert row[0] and not row[16]            # grows from the left


def test_draw_text_one_lights_glyph_cells(app):
    app.fb_clear()
    app.draw_text(0, 0, "1", (255, 255, 255))
    assert sum(1 for v in app.fb if v) == 8   # '1' glyph has 8 lit pixels
```

- [ ] **Step 2: Run to verify they pass against current code**

Run: `uv run pytest tests/test_matrix.py -q`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_matrix.py
git commit -m "Characterization fb-tests for px/draw_text/bar_left"
```

---

### Task 3: Move the framebuffer into `pixelbadge.matrix`

**Files:**
- Create: `lib/pixelbadge/matrix.py`
- Modify: `app/ha_energy/__init__.py` (remove fb defs; import them)

**Interfaces:**
- Produces: `pixelbadge.matrix` exporting `W, H, fb, fb_clear, px, fb_blit`.
- Consumes (in app): `from pixelbadge.matrix import W, H, fb, fb_clear, px, fb_blit`.

- [ ] **Step 1: Create the module**

`lib/pixelbadge/matrix.py`:
```python
# 32x8 HUB75 framebuffer. Hardware (rgb/hub75) guarded for host imports.
try:
    import rgb, hub75
except ImportError:
    rgb = hub75 = None

W, H = 32, 8
fb = [0] * (W * H)


def fb_clear():
    for i in range(W * H):
        fb[i] = 0


def px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        r, g, b = color
        fb[y * W + x] = (r << 24) | (g << 16) | (b << 8) | 255


def fb_blit():
    rgb.clear()
    hub75.image(fb, 0, 0, W, H)
```

- [ ] **Step 2: Rewire the app**

In `app/ha_energy/__init__.py`: delete the inline `W, H = 32, 8` line in the config area AND the `fb = [0]*(W*H)`, `fb_clear`, `px`, `fb_blit` definitions. Immediately after the hardware-import guard block (after `ON_BADGE` is set), add:
```python
from pixelbadge.matrix import W, H, fb, fb_clear, px, fb_blit
```
(Keep `W, H` available for any later code that uses them — the import provides them.)

- [ ] **Step 3: Run the full suite + format**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: 46 passed (42 + 4 fb-tests), checks pass. `test_matrix.py` still green proves px is unchanged.

- [ ] **Step 4: Deploy lib + app, confirm on panel**

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py put lib/pixelbadge/matrix.py lib/pixelbadge/matrix.py
uv run tools/badge.py put app/ha_energy/__init__.py apps/ha_energy/__init__.py
uv run tools/badge.py launch ha_energy
```
Expected: `Starting app 'ha_energy'...`, no traceback; panel renders normally.

- [ ] **Step 5: Commit**

```bash
git add lib/pixelbadge/matrix.py app/ha_energy/__init__.py
git commit -m "pixelbadge.matrix: move framebuffer out of ha_energy"
```

---

### Task 4: Move the font into `pixelbadge.pixelfont`

**Files:**
- Create: `lib/pixelbadge/pixelfont.py`
- Modify: `app/ha_energy/__init__.py`

**Interfaces:**
- Produces: `pixelbadge.pixelfont` exporting `FONT, ink_bounds, draw_text, text_width, draw_icon`.
- Note: `draw_icon(x, y, rows, color)` now takes glyph **rows** (not a name). `ICONS` stays in the app; the app passes `ICONS.get(name)`.

- [ ] **Step 1: Create the module**

`lib/pixelbadge/pixelfont.py`:
```python
# 3x5 proportional font: '#' = lit, '.' = off (parsed at load).
from pixelbadge.matrix import px


def _glyph(a):
    return a.strip("\n").split("\n")
```
Then **move the entire `FONT = {ch: _glyph(a) for ch, a in { ... }.items()}` block verbatim** from `app/ha_energy/__init__.py` (the `# 3x5 font` section) into this module, followed by **verbatim moves** of `ink_bounds`, `draw_text`, and `text_width`. Finally add the generic icon drawer:
```python
def draw_icon(x, y, rows, color):
    if not rows:
        return
    for r in range(len(rows)):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == "#":
                px(x + c, y + r, color)
```

- [ ] **Step 2: Rewire the app**

In `app/ha_energy/__init__.py`:
- Delete the moved `_glyph`, `FONT`, `ink_bounds`, `draw_text`, `text_width`, and the old `draw_icon` definitions. **Keep the `ICONS = {ch: _glyph(a) ...}` block**, but since `_glyph` now lives in the lib, add `from pixelbadge.pixelfont import _glyph` (or inline a local `_glyph` above ICONS — prefer importing it).
- Add: `from pixelbadge.pixelfont import FONT, ink_bounds, draw_text, text_width, draw_icon`.
- Change the icon call in `draw_stat` from `draw_icon(0, 0, s['icon'], col)` to `draw_icon(0, 0, ICONS.get(s['icon']), col)`. (The batsummary/`'BATT'` and battery calls that pass a name likewise become `ICONS.get('BATT')` etc.)

- [ ] **Step 3: Run the full suite + format**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: 46 passed. `test_matrix.py::test_draw_text_one_lights_glyph_cells` and `test_formatting` (text_width/ink_bounds) green prove the font move is faithful.

- [ ] **Step 4: Deploy + confirm on panel** (icons + text must look identical)

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py put lib/pixelbadge/pixelfont.py lib/pixelbadge/pixelfont.py
uv run tools/badge.py put app/ha_energy/__init__.py apps/ha_energy/__init__.py
uv run tools/badge.py launch ha_energy
```
Expected: icons (SUN/HOME/etc.) and values render exactly as before.

- [ ] **Step 5: Commit**

```bash
git add lib/pixelbadge/pixelfont.py app/ha_energy/__init__.py
git commit -m "pixelbadge.pixelfont: move font + text/icon drawing"
```

---

### Task 5: Move `bar_left` into `pixelbadge.gauges`

**Files:**
- Create: `lib/pixelbadge/gauges.py`
- Modify: `app/ha_energy/__init__.py`

**Interfaces:**
- Produces: `pixelbadge.gauges` exporting `bar_left(y, frac, color)`.
- Note: `gauge()` (overflow/sign logic) stays in the app — it depends on the stat dict and the `blink_on` global.

- [ ] **Step 1: Create the module**

`lib/pixelbadge/gauges.py`:
```python
from pixelbadge.matrix import W, px


def bar_left(y, frac, color):
    n = int(min(1.0, frac) * W + 0.5)
    for i in range(n):
        px(i, y, color)
```

- [ ] **Step 2: Rewire the app**

In `app/ha_energy/__init__.py`: delete the `bar_left` definition; add `from pixelbadge.gauges import bar_left`. (`gauge`, `draw_use_bar`, `bar_left` calls are unchanged.)

- [ ] **Step 3: Run the full suite + format**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: 46 passed (`test_matrix.py::test_bar_left_half_lights_16` green).

- [ ] **Step 4: Deploy + confirm on panel** (gauges/bars identical)

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py put lib/pixelbadge/gauges.py lib/pixelbadge/gauges.py
uv run tools/badge.py put app/ha_energy/__init__.py apps/ha_energy/__init__.py
uv run tools/badge.py launch ha_energy
```

- [ ] **Step 5: Commit**

```bash
git add lib/pixelbadge/gauges.py app/ha_energy/__init__.py
git commit -m "pixelbadge.gauges: move bar_left"
```

---

### Task 6: Move `Carousel` into `pixelbadge.carousel`

**Files:**
- Create: `lib/pixelbadge/carousel.py`
- Modify: `app/ha_energy/__init__.py`
- Modify: `tests/test_carousel.py` (retarget to the lib)

**Interfaces:**
- Produces: `pixelbadge.carousel` exporting `Carousel` (`__init__(seq)`, `refresh(seq)`, `step(n)`, `current()`).

- [ ] **Step 1: Create the module**

`lib/pixelbadge/carousel.py`: **move the `Carousel` class verbatim** from `app/ha_energy/__init__.py` (no hardware deps — pure logic).

- [ ] **Step 2: Rewire the app**

In `app/ha_energy/__init__.py`: delete the `Carousel` class; add `from pixelbadge.carousel import Carousel`.

- [ ] **Step 3: Point the existing Carousel test at the lib**

In `tests/test_carousel.py`, replace `app.Carousel(...)` references with the lib import. At top add `from pixelbadge.carousel import Carousel`, and change calls `app.Carousel(` → `Carousel(`. (Keeps the test meaningful even though the app still re-exports it.)

- [ ] **Step 4: Run the full suite + format**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: 46 passed.

- [ ] **Step 5: Deploy + confirm on panel** (auto-rotate + nav unchanged)

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py put lib/pixelbadge/carousel.py lib/pixelbadge/carousel.py
uv run tools/badge.py put app/ha_energy/__init__.py apps/ha_energy/__init__.py
uv run tools/badge.py launch ha_energy
```

- [ ] **Step 6: Commit**

```bash
git add lib/pixelbadge/carousel.py app/ha_energy/__init__.py tests/test_carousel.py
git commit -m "pixelbadge.carousel: move Carousel"
```

---

### Task 7: Add a `deploy-lib` step to `tools/badge.py`

So the library deploys in one command instead of per-file `put`s.

**Files:**
- Modify: `tools/badge.py`

**Interfaces:**
- Consumes: existing `put(local, remote)` helper in `tools/badge.py`.
- Produces: a `deploy-lib` subcommand that pushes every `lib/pixelbadge/*.py` to `/lib/pixelbadge/`.

- [ ] **Step 1: Add the subcommand**

In `tools/badge.py`'s CLI dispatch, add a `deploy-lib` command that globs `lib/pixelbadge/*.py` and `put`s each to `lib/pixelbadge/<name>`:
```python
elif cmd == "deploy-lib":
    import glob, os
    for f in sorted(glob.glob("lib/pixelbadge/*.py")):
        put(s, f, "lib/pixelbadge/" + os.path.basename(f))
```
(Match the file's existing arg-parsing/`put` signature; ensure the remote dir is created if the badge needs it — `put` already writes nested paths.)

- [ ] **Step 2: Verify end-to-end**

```bash
P=$(fuser /dev/ttyUSB1 2>/dev/null); [ -n "$P" ] && { kill $P; sleep 1; }
uv run tools/badge.py deploy-lib
uv run tools/badge.py exec "import pixelbadge.matrix, pixelbadge.pixelfont, pixelbadge.gauges, pixelbadge.carousel; print('LIB-OK')"
uv run tools/badge.py launch ha_energy
```
Expected: `LIB-OK`, then app starts and renders normally.

- [ ] **Step 3: Update README + format + commit**

Add one line to README's deploy section documenting `deploy-lib`. Then:
```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
git add tools/badge.py README.md
git commit -m "tools/badge.py: deploy-lib to push pixelbadge to /lib"
```

---

## Deferred to Part A.2 (separate plan)

`gauge()` (overflow/sign, `blink_on`), the `Display` loop + `idle_ms`, `poll`/HTTP + config `DEFAULTS`-merge (`netclient`), and button/input handlers. These are more coupled to app state and will share cleanly once `net_traffic` defines the loop/gauge/poll contract. Extract them then, same test-guarded pattern.
