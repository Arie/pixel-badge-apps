# Router endpoint — `traffic` CGI

`cgi-bin/traffic` is a POSIX-sh CGI for OpenWRT (uhttpd) that serves per-WAN
internet stats as JSON for the badge `net_traffic` app to poll. No extra packages
(uses `/proc/net/dev`); rate is computed from the delta between calls, with state
in `/tmp`.

## JSON contract (v1)

```json
{"wans":[
  {"name":"WAN1","iface":"pppoe-ppp0","up":true,
   "down_bps":0,"up_bps":0,"down_max":1000000000,"up_max":1000000000,
   "total_down":0,"total_up":0}
]}
```

`down_bps`/`up_bps` are bits/sec since the previous call (poll at a steady
interval, e.g. 5 s). `down_max`/`up_max` are link rates in bits/sec (for gauge
full-scale). `total_*` are lifetime bytes from the kernel (reset on reboot/PPPoE
reconnect). **Planned next:** `rtt_ms`, `loss_pct` (per-WAN ping) and `conns`
(active conntrack flows, where `/proc/net/nf_conntrack` exists).

## Configure the WAN list

Create `/etc/traffic.conf`, one WAN per line — `<iface> <name> <down_mbps> <up_mbps>`:

```
pppoe-ppp0 WAN1 1000 1000
eth3       WAN2 500  500
```

If absent, the default-route interface is auto-detected as a single `WAN`.
(WAN ifaces differ per router — dev `pppoe-ppp0`, party `eth3` — so always set this
on multi-WAN boxes.)

## Install (survives sysupgrade)

```sh
# on the router:
cp traffic /www/cgi-bin/traffic && chmod +x /www/cgi-bin/traffic
grep -q '/www/cgi-bin/traffic' /etc/sysupgrade.conf || echo '/www/cgi-bin/traffic' >> /etc/sysupgrade.conf
# test:
curl -s http://127.0.0.1/cgi-bin/traffic
```

The badge polls `http://<router>/cgi-bin/traffic` (dev `192.168.1.1`, party
`192.168.99.1`). Tested non-invasively from `/tmp` against `root@192.168.1.1`.
