# Pixel Badge — Home Assistant Energy Display

**Status:** Design / in progress
**Date:** 2026-06-23
**Target hardware:** CampZone 2019 "Pixel" badge (ESP32, badge.team firmware, MicroPython)

## 1. Purpose

A badge app that shows live energy data from the user's Home Assistant
(`http://192.168.1.9:8123`) on the badge's 32×8 RGB LED matrix: power flows
(consumption, solar, self-use, grid) and the state-of-charge **and power** of
three home batteries. The user navigates presentation styles and individual
stats with the badge's 4-way button.

## 2. Hardware & platform constraints

- **Display:** HUB75 RGB LED matrix, **32×8 pixels**. ~5 characters of static text.
- **Graphics API:** firmware `rgb` module — `clear()`, `text(text,(r,g,b),(x,y))`,
  `scrolltext(...)`, `pixel((r,g,b),(x,y))`, `image(...)`, `brightness(1..30)`,
  `framerate(1..30)`.
- **Input:** `buttons.register(defines.BTN_*, cb)` for `UP/DOWN/LEFT/RIGHT/A/B`.
- **Networking:** `wifi` + `urequests` (custom headers). HA is plain **HTTP** on
  the LAN → **no TLS cert problem** (unlike the badge's broken OTA).
- **App location:** `apps/ha_energy/` (`__init__.py`, `metadata.json`, `icon.py`, `version`).

## 3. Data source — Home Assistant REST API

- Base: `http://192.168.1.9:8123`, auth `Authorization: Bearer <long-lived-token>`.
- Read: `GET /api/states/<entity_id>` → `{"state":"...","attributes":{...}}`.
- **Poll** all configured entities every **10 s** (and once on launch),
  sequentially, short timeout. Last-known values shown between polls.
- Connectivity verified live 2026-06-23 (HTTP 200; values below are real samples).

## 4. Stats, entities, and derivation

Cycled with LEFT/RIGHT (10 stats). Short ≤4-char on-matrix tag.

| Tag    | Meaning                  | Kind     | HA entity / formula | Sample |
|--------|--------------------------|----------|---------------------|--------|
| `USE`  | House consumption        | use      | **derived** (below) | ~523 W |
| `SOL`  | Solar generation         | power    | `sensor.solaredge_se6k_ac_power` | 3284 W |
| `SELF` | Self-consumption         | self     | **derived** (below) | ~523 W |
| `GRID` | Grid power (signed)      | grid     | `sensor.homewizard_p1_vermogen`  | −2761 W |
| `HW1`  | HomeWizard battery 1 SOC | soc      | `sensor.plug_in_battery_state_of_charge`   | 100 % |
| `HW1`  | HomeWizard battery 1 power | batpower | `sensor.plug_in_battery_power`           | 0 W |
| `HW2`  | HomeWizard battery 2 SOC | soc      | `sensor.plug_in_battery_state_of_charge_2` | 100 % |
| `HW2`  | HomeWizard battery 2 power | batpower | `sensor.plug_in_battery_power_2`         | 0 W |
| `ZEN`  | Zendure AC2400+ SOC      | soc      | `sensor.zendure_2400_ac_laadpercentage`  | 100 % |
| `ZEN`  | Zendure AC2400+ power   | batpower | `sensor.zendure_signed_power`            | 0 W |

**Sign conventions (confirmed live where possible):**
- `GRID` (`homewizard_p1_vermogen`): **negative = export, positive = import**
  (was −2761 W while solar 3284 W → exporting). Matches the green/purple logic.
- `batpower`: **positive = charging, negative = discharging** — *assumed; validate
  against `plug_in_battery_power` / `zendure_signed_power` when a battery is active.*

**Derivations (on-badge, per the user's decision to derive rather than add HA
template sensors):**
- `USE`  = `SOL` + `GRID` + (`HW1p` + `HW2p` + `ZENp`)  — signed sum, "into-house".
- `SELF` = `SOL` − max(0, −`GRID`)  — solar not exported.

## 5. Colors (HomeWizard-inspired, brightened for LEDs)

| Role                         | Hex       |
|------------------------------|-----------|
| Consumption / grid import    | `#7b3ff2` purple |
| Solar / grid export / charging | `#33d96f` green |
| Self-use                     | `#4fc3ff` light blue |
| Battery discharging          | `#ff9d3a` amber |
| Overflow (value > rated max) | `#ffffff` white |
| Battery SOC ≥50 / 20–50 / <20 % | green / amber / red |

## 6. Gauges & maxima (constants)

Gauge mode draws a bottom bar scaled to a per-stat full-scale maximum.

| Stat            | Max (full-scale) | Bar style |
|-----------------|------------------|-----------|
| `USE`           | **17 250 W** (grid connection rating) | left→right; **>max ⇒ white overflow tip** (solar+battery boosting beyond the connection) |
| `SOL` / `SELF`  | **6 000 W** (solar inverter)          | left→right |
| `GRID`          | **17 250 W**                          | bidirectional centre-out: export ← / import → |
| `HW1`/`HW2` power | **±800 W** each way                 | bidirectional: charge → / discharge ← |
| `ZEN` power     | **±2 400 W** each way                 | bidirectional |
| any `soc`       | 100 %                                 | left→right, colour by level |

`GRID` max is assumed equal to the connection rating (17 250 W) — confirm.

## 7. Display modes (UP/DOWN)

1. **Rotate** — hands-free slideshow: icon + value, auto-advancing (~2.5 s).
2. **Ticker** — continuous scrolling marquee of all stats, each in its colour.
3. **Gauge** — icon + value + the scaled bar from §6. (User's favourite.)

## 8. Navigation

- **UP/DOWN** — prev/next mode (wraps). **LEFT/RIGHT** — prev/next stat (wraps).
- **B** — exit to launcher. **A** — reserved (future).

## 9. Configuration & secrets

- `~/Projects/pixel-badge-apps/.ha-token` holds the long-lived token (gitignored).
- On-badge: `apps/ha_energy/config.json` (gitignored) holds token + entity map +
  maxima + poll interval. Repo ships `app/config.example.json`.

## 10. Error handling

- No WiFi / connect fails: WiFi-then-error glyph, retry with backoff, **no reboot**.
- HA unreachable / HTTP error: keep last-known values, dim/`?` indicator.
- Missing entity / non-numeric: that stat shows `--`; others keep working.

## 11. App & project structure

```
apps/ha_energy/                  # on-badge
  __init__.py  metadata.json  icon.py  version  config.json(gitignored)

pixel-badge-apps/                # this repo (local git)
  docs/2026-06-23-ha-energy-app-design.md
  mockup/  pixelfont.js matrix.js stats.js sim.js sim.css energy-sim.html
  app/     # the MicroPython app
```

The mockup mirrors the device split: framebuffer + font/icon renderer
(`pixelfont`/`matrix`), config/maxima/derivation (`stats`), controller (`sim`).
`stats.js` is the single source of truth and tracks the on-device config.

## 12. Open questions / to provide

- Confirm **`batpower` sign** (charge vs discharge) once a battery is active.
- Confirm **`GRID` gauge max** (assumed 17 250 W).
- Default **mode** on launch (proposed Rotate) and **brightness** (proposed 10/30).
- Whether 10 stats is the right granularity, or batteries should be composite
  (SOC + power on one screen).
