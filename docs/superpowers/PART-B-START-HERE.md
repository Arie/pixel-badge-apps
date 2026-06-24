# Part B — net_traffic app: start here

Spec: `docs/superpowers/specs/2026-06-24-net-traffic-and-shared-lib-design.md` (Part B).
Part A (shared `pixelbadge` lib) is **done + on-device** (commits `9608d78..6c765e9`).

Start a **fresh session** and work these in order:

## 1. Open design questions
- **Routers probed (both OpenWRT SNAPSHOT x86/64, uhttpd+cgi-bin, python3+lua+jsonfilter, apk):**
  - Dev `root@192.168.1.1`: WAN `pppoe-ppp0` (+`pppoe-ppp1`); **no conntrack** (proc absent); sysupgrade keeps `/root/`.
  - Party `root@192.168.1.157 -p 10022`: WAN `eth3` (plain ethernet); **`/proc/net/nf_conntrack` PRESENT** (conns feasible here); sysupgrade keeps `/root/`. (At the actual party the WAN may be `192.168.99.1`/different iface.)
  - **Implications:** WAN iface differs per router → the CGI WAN list **must be config-driven**, never hardcoded. conntrack differs → emit `conns` **conditionally** (only if `/proc/net/nf_conntrack` exists). python3 is on both, so a python CGI is viable; shell is still the most portable choice for embedded routers — decide in the CGI plan.
  - Neither keeps `/www` across sysupgrade → add the CGI's path to `/etc/sysupgrade.conf`.
- **Total-data source:** live `vnstat` (apk add) vs accumulate counters vs drop for v1.

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
