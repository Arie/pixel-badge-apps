# Router endpoint — `traffic` CGI

`cgi-bin/traffic` is a POSIX-sh CGI for OpenWRT (uhttpd) that serves per-WAN
internet stats as JSON for the badge `net_traffic` app to poll. No extra packages
(uses `/proc/net/dev`); rate is computed from the delta between calls, with state
in `/tmp`.

## JSON contract (v2)

```json
{"wans":[
  {"name":"WAN1","iface":"pppoe-ppp0","up":true,
   "down_bps":0,"up_bps":0,"down_max":1000000000,"up_max":1000000000,
   "total_down":0,"total_up":0,
   "pings":[12,11,13,-1,12,11],"rtt_ms":11,"loss_pct":16}
],"conns":423}
```

### Per-WAN fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human label from `traffic.conf` |
| `iface` | string | Kernel interface name |
| `up` | bool | Interface present in `/proc/net/dev` |
| `down_bps` / `up_bps` | int | Bits/sec since previous call |
| `down_max` / `up_max` | int | Link rate in bits/sec (gauge full-scale) |
| `total_down` / `total_up` | int | Lifetime bytes (resets on reboot/reconnect) |
| `pings` | int array | Up to 32 RTT samples in ms, `-1` = loss; newest last. Empty array `[]` if pinger not running. |
| `rtt_ms` | int | Most recent non-`-1` RTT in the buffer, or `-1` if all lost / buffer empty |
| `loss_pct` | int | Percentage of `-1` entries in the buffer (0 if buffer empty) |

### Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `conns` | int | Active conntrack flows (`wc -l /proc/net/nf_conntrack`). **Only present** when `/proc/net/nf_conntrack` exists on the router. Omitted otherwise. |

`down_bps`/`up_bps` are bits/sec since the previous call (poll at a steady
interval, e.g. 5 s). `down_max`/`up_max` are link rates in bits/sec (for gauge
full-scale). `total_*` are lifetime bytes from the kernel (reset on reboot/PPPoE
reconnect).

The `pings` array drives a 32-wide sparkline on the badge display; `-1` entries
are rendered as a gap/loss indicator.

## Configure the WAN list

Create `/etc/traffic.conf`, one WAN per line —
`<iface> <name> <down_mbps> <up_mbps> [ping_target]`:

```
pppoe-ppp0 WAN1 1000 1000 185.93.175.46
pppoe-ppp1 WAN2 1000 1000 185.93.175.46
```

The optional 5th field is a per-WAN **ping target** (default `8.8.8.8`, pinged with
`-4`). Pointing both WANs at a provider-homed IP makes their graphs diverge by the
peering distance — e.g. `freedom.nl` (185.93.175.46) is on-net for the Freedom WAN
(~4.2 ms) but a peering hop away via KPN (~5.9 ms), so each WAN's avg-ping overlay
reads a different number. Use a neutral anchor like `8.8.8.8` for pure link-health.

If absent, the default-route interface is auto-detected as a single `WAN`.
(WAN ifaces differ per router — dev `pppoe-ppp0`, party `eth3` — so always set this
on multi-WAN boxes.)

## Install (survives sysupgrade)

### 1. CGI (v2)

```sh
cp cgi-bin/traffic /www/cgi-bin/traffic
chmod +x /www/cgi-bin/traffic
grep -q '/www/cgi-bin/traffic' /etc/sysupgrade.conf || \
    echo '/www/cgi-bin/traffic' >> /etc/sysupgrade.conf
```

### 2. Ping daemon

```sh
cp traffic-pinger /usr/bin/traffic-pinger
chmod +x /usr/bin/traffic-pinger
grep -q '/usr/bin/traffic-pinger' /etc/sysupgrade.conf || \
    echo '/usr/bin/traffic-pinger' >> /etc/sysupgrade.conf
```

### 3. Init script (procd — auto-start + respawn)

```sh
cp etc/init.d/traffic-pinger /etc/init.d/traffic-pinger
chmod +x /etc/init.d/traffic-pinger
grep -q '/etc/init.d/traffic-pinger' /etc/sysupgrade.conf || \
    echo '/etc/init.d/traffic-pinger' >> /etc/sysupgrade.conf
/etc/init.d/traffic-pinger enable
/etc/init.d/traffic-pinger start
```

### 4. Test

```sh
# After ~8 s of pinger running:
curl -s http://127.0.0.1/cgi-bin/traffic | python3 -m json.tool
```

### Minimal `/etc/sysupgrade.conf` additions

```
/www/cgi-bin/traffic
/usr/bin/traffic-pinger
/etc/init.d/traffic-pinger
/etc/traffic.conf
```

## Non-invasive dev test (from workstation)

Note: busybox ash does not have `nohup` or `disown`. Use `start-stop-daemon -S -b`
(always present on OpenWRT) to daemonize properly so the pinger survives SSH disconnect.

```sh
# Copy files to /tmp on router
ssh root@192.168.1.1 'cat > /tmp/traffic-pinger' < router/traffic-pinger
ssh root@192.168.1.1 'cat > /tmp/traffic'        < router/cgi-bin/traffic
ssh root@192.168.1.1 'chmod +x /tmp/traffic-pinger /tmp/traffic'

# Start pinger as a proper background daemon
ssh root@192.168.1.1 'start-stop-daemon -S -b -m -p /tmp/pinger.pid -x /bin/sh -- /tmp/traffic-pinger && echo started'

# Wait ~8s, then run CGI
sleep 8
ssh root@192.168.1.1 'sh /tmp/traffic'

# Cleanup
ssh root@192.168.1.1 'start-stop-daemon -K -p /tmp/pinger.pid; pkill -f "ping -I" 2>/dev/null; rm -f /tmp/traffic_ping_* /tmp/pinger.pid /tmp/traffic /tmp/traffic-pinger'
```

The badge polls `http://<router>/cgi-bin/traffic` (dev `192.168.1.1`, party
`192.168.99.1`). Tested non-invasively from `/tmp` against `root@192.168.1.1`.

## Dev data faker (`traffic-faker`)

A flat real connection (e.g. a steady 4 ms) makes the ping graph dull to develop
against. `traffic-faker` writes synthetic samples (baseline jitter + ~10% spikes +
~4% loss) to the ring buffer the CGI reads, so the badge graph shows lively motion.
**Dev only** — run it INSTEAD of the real pinger:

```sh
ssh root@192.168.1.1 'cat > /tmp/traffic-faker' < router/traffic-faker
ssh root@192.168.1.1 'chmod +x /tmp/traffic-faker;
  /etc/init.d/traffic-pinger stop; /etc/init.d/traffic-pinger disable;
  start-stop-daemon -S -b -m -p /tmp/faker.pid -x /bin/sh -- /tmp/traffic-faker pppoe-ppp0'
```

To restore real pings (kill any faker awk + start the service):
`for p in $(pgrep -f traffic_ping_); do grep -qa awk /proc/$p/cmdline && kill -9 $p; done; /etc/init.d/traffic-pinger enable; /etc/init.d/traffic-pinger start`

The real `traffic-pinger` is the default; the faker is only for graph development.
The pinger emits ~5 samples/sec (5 pings then `sleep 1`, since busybox lacks
sub-second sleep) to match the badge's `ping_rate`.
