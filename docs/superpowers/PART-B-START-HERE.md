# Part B — net_traffic app: start here

Spec: `docs/superpowers/specs/2026-06-24-net-traffic-and-shared-lib-design.md` (Part B).
Part A (shared `pixelbadge` lib) is **done + on-device** (commits `9608d78..6c765e9`).

Start a **fresh session** and work these in order:

## 1. Resolve open design questions (decisions block the plan)
- **Re-probe the party router** when online: `ssh -p 10022 root@192.168.1.159 ...`
  (or the real `192.168.99.1:22`). Confirm: python3? conntrack? `/proc/net/dev`
  WAN iface name(s)? package manager (apk vs opkg)? The dev router
  (`root@192.168.1.1`) is SNAPSHOT x86/64 with uhttpd + cgi-bin, python3, jsonfilter,
  WAN `pppoe-ppp0` (+`pppoe-ppp1`), no conntrack, `/etc/sysupgrade.conf` persistence.
- **Total-data source:** live `vnstat` (apk add) vs accumulate counters vs drop for v1.
- **Active connections:** install conntrack (apk add) vs defer.

## 2. Display mockup pass (like the energy app)
Multi-WAN layout on 32x8 + the latency/loss **alert-override** (bad WAN jumps to
front + blinks, reusing the overflow-blink idea). Decide screens, gauge full-scales
(per-WAN link speed), and alert thresholds (RTT ms, loss %). Use the `mockup/`
browser harness + Playwright, same workflow as `ha_energy`.

## 3. Build order (each its own plan → SDD execution)
1. **On-router shell CGI** `/www/cgi-bin/traffic`: read `/proc/net/dev` per WAN,
   `/tmp` state for rate deltas, ping for rtt/loss, emit the JSON contract (see spec).
   Persist via `/etc/sysupgrade.conf`. Test against `root@192.168.1.1` first
   (write to `/tmp` to test non-invasively before installing to `/www`).
2. **`net_traffic` badge app** `app/net_traffic/__init__.py`: HTTP-poll the CGI,
   render per the mockup, config-driven `base_url` (dev `192.168.1.1` / party
   `192.168.99.1`), alert-override. Reuse `import pixelbadge.*`.
3. **Part A.2 (optional, do alongside):** extract the now-shared loop/poll/input —
   `Display`, `netclient` (config DEFAULTS-merge + HTTP-GET-JSON), `input`, and a
   shared `gauge()` — into `pixelbadge`, refactoring BOTH apps onto them,
   test-guarded. Pull these out as the two apps reveal the common contract.

## Reusable now
`import pixelbadge.matrix` (fb/px/fb_blit), `.pixelfont` (FONT/draw_text/draw_icon),
`.gauges` (bar_left), `.carousel` (Carousel). Deploy lib with
`uv run tools/badge.py deploy-lib`. Badge serial: CH340 `/dev/ttyUSB1`.
