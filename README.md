# Pixel Badge Apps

MicroPython apps for the CampZone 2019 "Pixel" badge (badge.team firmware).

## ha_energy — Home Assistant energy display

Shows live power flows and home-battery SOC/power from Home Assistant on the 32×8
LED matrix. Single auto-advancing gauge view; ◀▶ step (latches auto-rotate off),
**A** pause/resume, ▲▼ brightness, **B** exit. See
[docs/2026-06-23-ha-energy-app-design.md](docs/2026-06-23-ha-energy-app-design.md).

- `app/ha_energy/` — the on-badge MicroPython app (deployed to `apps/ha_energy/`).
- `mockup/` — browser simulator used to design the layout/colors/navigation.
  Serve with any static server: `python3 -m http.server -d mockup` then open
  `gallery.html` (contact sheet) or `energy-sim.html` (interactive).
- Copy `app/ha_energy/config.example.json` → `config.json` and fill in your HA
  token + entity IDs (gitignored).

## Layout

```
app/ha_energy/   on-badge MicroPython app (+ gitignored config.json)
mockup/          browser design mockup (plain JS)
tools/badge.py   serial deploy / REPL helper
tests/           pytest suite for the app's pure logic
docs/            design doc
```

## Development

Tooling is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # create .venv + install dev deps (pytest, ruff, pyserial)
uv run pytest                 # run the test suite
uv run ruff check .           # lint
uv run ruff format .          # format
uv run pre-commit install     # (optional) run lint+format on every commit
```

**Testing a MicroPython app on the host:** `app/ha_energy/__init__.py` guards its
hardware imports (`rgb`, `hub75`, …) and its `main()` call behind `ON_BADGE`, so it
imports cleanly off-device. The tests load it via `importlib` and exercise the pure
logic (derivations, formatting, font metrics, battery/idle rules) — no badge needed.

## Deploying to the badge

Badge on USB (CH340 → e.g. `/dev/ttyUSB1`; the default is the stable by-id path):

```bash
uv run tools/badge.py deploy            # push app/ha_energy/* -> apps/ha_energy/
uv run tools/badge.py launch ha_energy  # start it (badge reboots into the app)
```

Override the port with `--port` or `$BADGE_PORT`. The deploy drives the badge's
MicroPython "Python shell" over serial (it resets, selects the shell, and streams
the files in).
