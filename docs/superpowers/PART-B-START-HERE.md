# Part B — net_traffic app: start here

Spec: `docs/superpowers/specs/2026-06-24-net-traffic-and-shared-lib-design.md` (Part B).
Part A (shared `pixelbadge` lib) is **done + on-device** (commits `9608d78..6c765e9`).

## Progress so far
- ✅ **Routers probed** (see §1), **design locked** (see §2), **CGI v1 built + verified** (§3.1).
- Remaining: **CGI v2** (pinger + rtt/loss/conns), then the **net_traffic app**.

Start a **fresh session** (this design work ran a long context) and continue at §3.2.

## 1. Routers (probed)
Both OpenWRT SNAPSHOT x86/64, uhttpd+cgi-bin, python3+lua+jsonfilter, **apk** (not opkg).
- Dev `root@192.168.1.1`: WAN `pppoe-ppp0` (+`pppoe-ppp1`); **no conntrack** (proc absent); sysupgrade keeps `/root/`.
- Party `root@192.168.1.157 -p 10022`: WAN `eth3`; **`/proc/net/nf_conntrack` PRESENT**; keeps `/root/`. (Real party WAN may be `192.168.99.1`/other iface.)
- **Implications:** WAN list **must be config-driven** (`/etc/traffic.conf`); emit `conns` **only if** `/proc/net/nf_conntrack` exists; add the CGI path to `/etc/sysupgrade.conf` (`/www` isn't kept).
- **Still open:** total-data source — live `vnstat` (apk add) vs accumulate vs drop for v1.

## 2. Display design (LOCKED)
Mockups: `mockup/net-gallery.html` (screens) and `mockup/net-options.html` (icon/loss options).
One stat per auto-rotating screen, like `ha_energy`. Per WAN:
- **Download / Upload:** direction-**arrow** icon (green / blue) + rate (`680M`) + utilisation gauge (rate ÷ link max).
- **Total down:** **sigma** Σ icon + lifetime bytes (`277G`), no gauge.
- **Ping graph** (the highlight): full 32-wide sparkline, one column per ping.
  Height ∝ RTT, colour **green→amber→red** by latency; a **lost packet = a single
  PURPLE dot on the top row with an empty column below** (latency bars cap at row 1
  so the top row is the loss lane). ~6.4 s of history at 0.2 s/ping.
- **Connections:** bold **↔ double-arrow** icon + count (`1240`).
- **Multi-WAN:** small WAN digit ("2") + arrow prefix; each WAN rotates its own screens.
- **Alert-override:** a WAN with loss / very-high ping **jumps to the front and blinks**
  (reuse the `ha_energy` overflow-blink mechanism). Thresholds → config.

Icon bitmaps live in `mockup/net-options.html` (copy the chosen `["...","..."]` arrays).

## 3. Build (each its own plan → SDD, test-guarded)

### 3.1 On-router CGI v1 — ✅ DONE
`router/cgi-bin/traffic` (committed `f76dbf7`): POSIX-sh, per-WAN down/up bit-rate
(from `/proc/net/dev` deltas, `/tmp` state) + totals + up-status; config-driven WAN
list (`/etc/traffic.conf`, default-route fallback). Verified vs `root@192.168.1.1`.
Contract + install in `router/README.md`.

### 3.2 On-router CGI v2 — NEXT
Extend `router/cgi-bin/traffic`:
- **Background pinger:** loop per WAN at 0.2 s, store last 32 RTTs (ms; sentinel for
  loss) in a `/tmp` ring buffer per iface. Decide: procd service vs cron vs
  self-respawning `&` loop (procd is the OpenWRT-idiomatic choice; survives via an
  `/etc/init.d/` script added to `sysupgrade.conf`).
- **JSON adds:** per WAN `pings:[...32 ints, -1=loss]`, `rtt_ms`, `loss_pct`; and
  top-level `conns` only when `/proc/net/nf_conntrack` exists.
- Test from `/tmp` against `root@192.168.1.1` before installing to `/www`.

### 3.3 net_traffic app
`app/net_traffic/__init__.py`: HTTP-poll the CGI, render the §2 screens with
`import pixelbadge.*` (matrix/pixelfont/gauges/carousel), per-WAN rotation, the ping
sparkline, and the loss/high-ping alert-override. Config-driven `base_url`
(dev `http://192.168.1.1` / party `http://192.168.99.1`), poll interval, per-WAN link
maxes, alert thresholds. Host-importable + tests like `ha_energy`; deploy via
`tools/badge.py` (and `deploy-lib` for the shared lib).

### 3.4 Part A.2 (alongside) — shared loop/poll/input
Once both apps reveal the common contract, extract `Display`, `netclient`
(DEFAULTS-merge + HTTP-GET-JSON), `input`, and a shared `gauge()` into `pixelbadge`,
refactoring BOTH apps onto them — test-guarded (characterization first).

## Reusable now
`import pixelbadge.matrix` (fb/px/fb_blit), `.pixelfont` (FONT/draw_text/draw_icon),
`.gauges` (bar_left), `.carousel` (Carousel). Deploy lib with
`uv run tools/badge.py deploy-lib`. Badge serial: CH340 `/dev/ttyUSB1`.
