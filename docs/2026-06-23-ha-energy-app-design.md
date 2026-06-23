# Pixel Badge — Home Assistant Energy Display

**Status:** Design / in progress
**Date:** 2026-06-23
**Target hardware:** CampZone 2019 "Pixel" badge (ESP32, badge.team firmware, MicroPython)

## 1. Purpose

A badge app that shows live energy data from the user's Home Assistant
(`http://192.168.1.9:8123`) on the badge's 32×8 RGB LED matrix: power flows
(consumption, solar, self-use, grid) and the state-of-charge of three home
batteries. The user navigates between presentation styles and individual stats
with the badge's 4-way button.

## 2. Hardware & platform constraints

- **Display:** HUB75 RGB LED matrix, **32×8 pixels** (`CONFIG_HUB75_WIDTH=32`,
  `CONFIG_HUB75_HEIGHT=8`). ~5 characters of static text in the small font.
- **Graphics API:** firmware `rgb` module — `rgb.clear()`, `rgb.text(text,(r,g,b),(x,y))`,
  `rgb.scrolltext(text,(r,g,b))`, `rgb.pixel((r,g,b),(x,y))`, `rgb.image(data,(x,y),(w,h))`,
  `rgb.brightness(1..30)`, `rgb.framerate(1..30)`.
- **Input:** `buttons` module — `buttons.register(defines.BTN_*, cb)` for
  `BTN_UP/DOWN/LEFT/RIGHT/A/B`.
- **Networking:** `wifi` module + `urequests` (supports custom headers). HA is
  plain **HTTP** on the LAN, so there is **no TLS cert problem** (unlike the
  badge's OTA — see the firmware notes).
- **App install location:** `apps/<slug>/` on the badge FAT filesystem, with
  `__init__.py`, `metadata.json`, `icon.py`, `version`.

## 3. Data source — Home Assistant REST API

- Base URL: `http://192.168.1.9:8123`
- Auth: **long-lived access token** sent as `Authorization: Bearer <token>`.
- Per-entity read: `GET /api/states/<entity_id>` →
  `{"state":"850","attributes":{...}}`. `state` parsed as float.
- **Polling:** refresh all configured entities every **10 s** (and once on
  launch), sequentially, with a short timeout. Last-known values are shown
  between polls. A failed read marks that stat stale (see error handling).

## 4. Stats (short tags) and entity mapping

Stats are cycled with LEFT/RIGHT. Each has a short ≤4-char on-matrix tag.

| Tag    | Meaning                         | Kind   | HA entity_id (TO PROVIDE) |
|--------|---------------------------------|--------|---------------------------|
| `USE`  | House power consumption         | power  | _tbd_                     |
| `SOL`  | Solar generation                | power  | _tbd_                     |
| `SELF` | Self-consumption (solar used)   | power  | _tbd_ (may be derived)    |
| `GRID` | Grid power, signed              | grid   | _tbd_                     |
| `HW1`  | HomeWizard Plug-In Battery 1 SOC| soc    | _tbd_                     |
| `HW2`  | HomeWizard Plug-In Battery 2 SOC| soc    | _tbd_                     |
| `ZEN`  | Zendure AC2400+ SOC             | soc    | _tbd_                     |

**Kinds:**
- `power` — value in W; `>=1000` shown as `x.xK`. Single fixed color.
- `grid` — signed W; **negative = export**, **positive = import**. `-`/`+` prefix.
- `soc` — integer %; color by level.

## 5. Color scheme (HomeWizard-inspired)

Brightened so it reads on LEDs (dark purple renders dim on a raw matrix).

| Role                         | Color        | Hex       |
|------------------------------|--------------|-----------|
| Consumption (`USE`)          | purple       | `#7b3ff2` |
| Solar (`SOL`) / grid export  | green        | `#33d96f` |
| Self-use (`SELF`)            | light blue   | `#4fc3ff` |
| Grid import (`GRID` +)       | purple       | `#7b3ff2` |
| Grid export (`GRID` −)       | green        | `#33d96f` |
| Battery SOC ≥ 50%            | green        | `#33d96f` |
| Battery SOC 20–50%           | amber        | `#ff9d3a` |
| Battery SOC < 20%            | red          | `#ff4d4d` |

## 6. Display modes (UP/DOWN to switch)

1. **Rotate** — hands-free slideshow: icon + value for one stat, auto-advancing
   through the stat list (~2.5 s each). LEFT/RIGHT steps manually.
2. **Ticker** — continuous left-scrolling marquee of all stats in one pass
   (`USE 850W  SOL 2.1K  …`), each segment in its stat color. Matches the
   countdown app's scroll feel.
3. **Gauge** — focused single stat: icon + value + a bottom bar whose length
   encodes magnitude (% for SOC, scaled W for power). Grid uses signed color.

## 7. Navigation

- **UP / DOWN** — previous / next **mode** (wraps).
- **LEFT / RIGHT** — previous / next **stat** (wraps).
- **B** — exit app (back to launcher), matching other apps.
- **A** — reserved (future: toggle brightness or pin a stat).

## 8. Configuration & secrets

- Token + entity IDs live in `apps/ha_energy/config.json` on the badge,
  **never committed**. Repo ships `app/config.example.json`.
- Shape:
  ```json
  {
    "base_url": "http://192.168.1.9:8123",
    "token": "<long-lived-access-token>",
    "poll_seconds": 10,
    "stats": [
      {"id":"USE","entity":"sensor.house_power"},
      {"id":"SOL","entity":"sensor.solar_power"},
      {"id":"SELF","entity":"sensor.self_consumption"},
      {"id":"GRID","entity":"sensor.grid_power"},
      {"id":"HW1","entity":"sensor.homewizard_battery_1_soc"},
      {"id":"HW2","entity":"sensor.homewizard_battery_2_soc"},
      {"id":"ZEN","entity":"sensor.zendure_ac2400_soc"}
    ]
  }
  ```

## 9. Error handling

- **No WiFi / connect fails:** show a WiFi icon then an error glyph; retry on a
  backoff. Do not hard-reboot the badge for transient failures.
- **HA unreachable / HTTP error:** keep last-known values; show a small stale
  indicator (e.g., dimmed value) and a `?` when never fetched.
- **Entity missing / non-numeric state:** that stat shows `--`; others keep working.

## 10. App structure (on-badge)

```
apps/ha_energy/
  __init__.py     # app entry: setup, button handlers, poll loop, render loop
  metadata.json   # name "HA Energy", category "event_related"/"system", revision
  icon.py         # launcher icon (8x8)
  version
  config.json     # user secrets (gitignored, created from example)
```

Internally the app mirrors the mockup's separation: a small framebuffer +
font/icon renderer, a stats/config layer, and a controller that maps buttons to
mode/stat and renders. The firmware `rgb` calls replace the browser DOM matrix.

## 11. Project structure (this repo: `pixel-badge-apps`)

```
pixel-badge-apps/
  docs/2026-06-23-ha-energy-app-design.md   # this doc
  mockup/         # browser simulator (design tool): pixelfont/matrix/stats/sim + html/css
  app/            # the MicroPython badge app (ha_energy)
```

The **mockup** is the design surface: `stats.js` is the single source of truth
for tags/colors/kinds and is kept in sync with the on-device config.

## 12. Open questions / to provide

- HA **long-lived access token**.
- Exact **entity IDs** for the 7 stats (and whether SELF and GRID exist as
  sensors or must be derived from others).
- Confirm **battery SOC color-by-level** thresholds (50 / 20%) vs. a fixed color.
- Confirm whether **GRID** (signed import/export) and **SELF** stay in the list.
- Default **mode** on launch (proposed: Rotate) and default **brightness**
  (proposed: 10/30).
