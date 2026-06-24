# Shared `pixelbadge` library + `net_traffic` app — design

Date: 2026-06-24

## Goal

1. Extract the reusable, app-agnostic parts of `ha_energy` into a shared
   on-badge library (`pixelbadge`) so multiple apps share one implementation.
2. Build a second app, `net_traffic` — an internet/network-traffic dashboard for
   the 32×8 panel, fed by OpenWRT over HTTP.

Hard ordering (user directive): **ship the shared library first, proving the
existing app still works via tests + on-device, before any `net_traffic` code.**

## Part A — shared `pixelbadge` library

### Placement (verified)

The badge `sys.path` is `['', '/lib', '/apps', '/sd/lib', '/sd/apps', 'apps']`.
`/lib` is an import root, so a package at `/lib/pixelbadge/` is importable as
`import pixelbadge.matrix` from any app. Absolute imports from `/lib` are
reliable in MicroPython (the earlier risk was *relative* `from . import x` inside
a launched app, which we avoid). Fallback if on-device imports misbehave:
build-time bundling that inlines shared modules into each app's single file.

```
repo/
  lib/pixelbadge/            → deployed to badge /lib/pixelbadge/
    __init__.py
    matrix.py     W,H, fb, fb_clear, px, fb_blit          (hardware: rgb/hub75)
    pixelfont.py  FONT, draw_text, text_width, ink_bounds, draw_icon
    gauges.py     bar_left, gauge (signed/overflow)
    carousel.py   Carousel
    display.py    Display loop skeleton + idle_ms (callback-driven)
    netclient.py  config DEFAULTS-merge + HTTP-GET-JSON helper
    input.py      button registration + shared state dict
  app/ha_energy/__init__.py    app-specific only (STATS, poll map, render, icons, two-tone USE bar)
  app/net_traffic/__init__.py  new app
```

App-specific (stays in each app): the stat/data schema, `poll()` mapping,
`render()`, the icon set, and any bespoke gauge (e.g. energy's two-tone USE bar).

### `display.py` interface (callback-driven)

`Display` keeps the tick phases (brightness, poll, select, draw, idle) but takes
the app's hooks instead of calling app globals directly:

- `poll()` — refresh the app's values (returns nothing; updates app state)
- `active_stats()` — current visible stat list (drives the carousel)
- `render(stat)` — draw one stat into the framebuffer
- `is_overflow(stat)` / `alert(stats)` — whether to blink / force a screen front

This is the one component whose shape changes (parameterised); everything else is
a near-verbatim code move.

### Test-coverage requirement (the guardrail)

Well-covered today: `Carousel`, config merge/`_build_stats`, font metrics
(`ink_bounds`/`text_width`), derivations/formatting.

**Gaps to fill BEFORE extraction** (fb-level, no hardware — `px`/`draw_text`/
`bar_left` write the in-memory `fb` list; only `fb_blit` touches hardware):

- `test_matrix`: `px` clipping (off-panel writes ignored) + fb index/colour packing
- `test_pixelfont`: `draw_text` lights the expected fb cells for a known glyph
- `test_gauges`: `bar_left(frac)` lights the expected number of cells from the left

### Extraction sequence (each step keeps the full suite green)

1. Confirm a trivial `/lib` import works on-device (`import pixelbadge` smoke test).
2. Add the gap-filling fb-level tests above against current `ha_energy`.
3. Create `lib/pixelbadge/`, move components over module by module.
4. Refactor `ha_energy` to import from `pixelbadge`; **all characterization +
   logic + new fb tests stay green**; deploy and confirm on the panel.
5. Only then start `net_traffic`.

`tools/badge.py` gains a step to deploy `lib/pixelbadge/` → `/lib/pixelbadge/`.

## Part B — `net_traffic` app

### Data path (on-router endpoint)

A POSIX-shell CGI at `/www/cgi-bin/traffic` under `uhttpd` reads `/proc/net/dev`
per WAN, keeps last counters in `/tmp` to compute rates, measures ping/loss, and
emits one JSON blob. The badge polls it over HTTP exactly as `ha_energy` polls
HA. Shell (not python) for portability to embedded party routers.

**Persistence across sysupgrade:** add the CGI path to `/etc/sysupgrade.conf`
(the router already curates this file for custom scripts).

Dev router probed (`root@192.168.1.1`): OpenWRT SNAPSHOT x86/64, `uhttpd` +
`/www/cgi-bin`, `python3`/`lua`/`jsonfilter` present, `apk` (not opkg), WAN =
`pppoe-ppp0` (and `pppoe-ppp1` — dual WAN). `conntrack` NOT present. Party staging
box `root@192.168.1.159:10022` was offline at probe time — re-probe it (or the
actual `192.168.99.1`) before relying on its capabilities.

### JSON contract (badge ↔ endpoint)

Stable schema so an on-router CGI / a future collector are interchangeable:

```json
{
  "wans": [
    {"name": "WAN1", "iface": "pppoe-ppp0", "down_bps": 0, "up_bps": 0,
     "down_max": 1000000000, "up_max": 100000000,
     "total_down": 0, "total_up": 0, "rtt_ms": 0, "loss_pct": 0, "up": true}
  ],
  "conns": 0
}
```

### Stats (user-selected)

- **WAN down/up throughput** (Mbps) per WAN — core, from `/proc/net/dev`.
- **Total data used** per WAN — counters reset on reboot/PPPoE reconnect; accurate
  totals want `vnstat` (apk add) or accumulation. (Decision deferred.)
- **Active connections** — needs conntrack accounting + tool (`apk add`); absent now.
- **Latency + loss** per WAN — ping a public host on the router.

### Multi-WAN

The dev router and party setups have multiple WANs. The display is per-WAN; the
config lists the WAN interfaces. Layout (one screen per WAN×metric vs combined)
is a display-design question to settle with a **mockup pass** (as we did for
energy) before building the app.

### Alert override

A WAN with high latency or packet loss **overrides auto-scroll**: its screen jumps
to the front and blinks (reusing the `ha_energy` overflow-blink mechanism).
Thresholds (e.g. RTT > N ms, loss > M %) configurable; defaults TBD in the mockup
pass.

### Config (per environment)

Config-driven like `ha_energy`: `base_url` (dev `http://192.168.1.1`, party
`http://192.168.99.1`), poll interval, the WAN list, per-WAN max link speeds (for
gauge full-scale), and alert thresholds.

## Open questions (resolve during implementation)

- Re-probe the party router for python/conntrack/WAN names when it's online.
- Total-data source: live `vnstat` vs accumulate vs drop it for v1.
- Install conntrack for connection count, or defer.
- `net_traffic` on-badge layout + alert thresholds → mockup pass.

## Out of scope

Colors/font internals (shared as-is), the `ha_energy` mockup, unrelated refactors.
```
