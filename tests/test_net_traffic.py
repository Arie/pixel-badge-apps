"""Unit tests for the net_traffic badge app — pure host-testable functions only."""


# ---- fmt_rate ----------------------------------------------------------------


def test_fmt_rate_k(net_app):
    assert net_app.fmt_rate(512000) == "512K"


def test_fmt_rate_k_small(net_app):
    assert net_app.fmt_rate(1000) == "1K"


def test_fmt_rate_m_boundary(net_app):
    # exactly 1 000 000 bps → 1M
    assert net_app.fmt_rate(1000000) == "1M"


def test_fmt_rate_m(net_app):
    assert net_app.fmt_rate(45000000) == "45M"


def test_fmt_rate_m_680(net_app):
    assert net_app.fmt_rate(680000000) == "680M"


def test_fmt_rate_g(net_app):
    assert net_app.fmt_rate(1000000000) == "1G"


def test_fmt_rate_g_large(net_app):
    assert net_app.fmt_rate(10000000000) == "10G"


# ---- fmt_bytes ---------------------------------------------------------------


def test_fmt_bytes_g(net_app):
    assert net_app.fmt_bytes(277000000000) == "277G"


def test_fmt_bytes_m(net_app):
    assert net_app.fmt_bytes(512000000) == "512M"


def test_fmt_bytes_k(net_app):
    assert net_app.fmt_bytes(800000) == "800K"


def test_fmt_bytes_g_boundary(net_app):
    assert net_app.fmt_bytes(1000000000) == "1G"


# ---- build_screens -----------------------------------------------------------

WAN1 = {
    "iface": "pppoe-ppp0",
    "name": "WAN1",
    "down_bps": 680000000,
    "up_bps": 210000000,
    "down_max": 1000000000,
    "up_max": 1000000000,
    "total_down": 277000000000,
    "total_up": 50000000000,
    "pings": [11, 13, 12],
    "rtt_ms": 12,
    "loss_pct": 0,
}

WAN2 = {
    "iface": "eth3",
    "name": "WAN2",
    "down_bps": 120000000,
    "up_bps": 30000000,
    "down_max": 500000000,
    "up_max": 500000000,
    "total_down": 50000000000,
    "total_up": 10000000000,
    "pings": [],
    "rtt_ms": -1,
    "loss_pct": 0,
}


def test_build_screens_single_wan_no_conns(net_app):
    screens = net_app.build_screens([WAN1], None)
    assert len(screens) == 4
    kinds = [s["kind"] for s in screens]
    assert kinds == ["down", "up", "total", "ping"]


def test_build_screens_single_wan_with_conns(net_app):
    screens = net_app.build_screens([WAN1], 1240)
    assert len(screens) == 5
    assert screens[-1]["kind"] == "conns"


def test_build_screens_multi_wan(net_app):
    screens = net_app.build_screens([WAN1, WAN2], None)
    assert len(screens) == 8  # 4 + 4


def test_build_screens_multi_wan_with_conns(net_app):
    screens = net_app.build_screens([WAN1, WAN2], 300)
    assert len(screens) == 9  # 4 + 4 + 1


def test_build_screens_stable_ids(net_app):
    screens = net_app.build_screens([WAN1], None)
    ids = [s["id"] for s in screens]
    assert ids == [
        "pppoe-ppp0:down",
        "pppoe-ppp0:up",
        "pppoe-ppp0:total",
        "pppoe-ppp0:ping",
    ]


def test_build_screens_conns_id(net_app):
    screens = net_app.build_screens([WAN1], 500)
    conns_screen = next(s for s in screens if s["kind"] == "conns")
    assert conns_screen["id"] == "conns"


def test_build_screens_values(net_app):
    screens = net_app.build_screens([WAN1], None)
    down = screens[0]
    assert down["kind"] == "down"
    assert down["iface"] == "pppoe-ppp0"
    assert down["bps"] == 680000000
    assert down["bps_max"] == 1000000000


# ---- ping_columns ------------------------------------------------------------


def test_ping_columns_loss_gives_purple_at_row0(net_app):
    cols = net_app.ping_columns([-1], 60)
    assert len(cols) == 1
    assert cols[0] == [(0, "purple")]


def test_ping_columns_loss_only_one_pixel(net_app):
    # loss: single purple dot at top, no other pixels in that column
    cols = net_app.ping_columns([-1], 60)
    assert len(cols[0]) == 1


def test_ping_columns_30ms_at_60_scale(net_app):
    # height = max(1, round(30/60*7)) = max(1, round(3.5)) = max(1,4) = 4
    # rows 7,6,5,4 (growing from bottom)
    cols = net_app.ping_columns([30], 60)
    assert len(cols) == 1
    rows = [r for (r, _) in cols[0]]
    assert 7 in rows  # bottom row always lit
    assert len(rows) == 4  # 4 pixels high
    colors = [c for (_, c) in cols[0]]
    assert all(c == "green" for c in colors)  # 30 < 40 → green


def test_ping_columns_50ms_amber(net_app):
    # 50ms at scale 60 → height = max(1, round(50/60*7)) = max(1, round(5.8)) = 6
    cols = net_app.ping_columns([50], 60)
    colors = [c for (_, c) in cols[0]]
    assert all(c == "amber" for c in colors)  # 40 <= 50 < 80 → amber


def test_ping_columns_80ms_red(net_app):
    # 80ms >= 80 → red
    cols = net_app.ping_columns([80], 60)
    colors = [c for (_, c) in cols[0]]
    assert all(c == "red" for c in colors)


def test_ping_columns_capped_at_7(net_app):
    # rtt > scale_ms → capped at height 7, row 0 stays the loss lane
    cols = net_app.ping_columns([200], 60)
    rows = [r for (r, _) in cols[0]]
    assert 0 not in rows  # row 0 reserved for loss
    assert max(rows) == 7
    assert min(rows) == 1  # can reach row 1 (height=7 → rows 7..1)


def test_ping_columns_min_height_1(net_app):
    # very low rtt → still at least 1 pixel
    cols = net_app.ping_columns([1], 60)
    assert len(cols[0]) >= 1


def test_ping_columns_left_pad_newest_right(net_app):
    # 2 entries → 2 columns, newest (index 1) is at position x=1
    cols = net_app.ping_columns([10, 20], 60)
    assert len(cols) == 2


def test_ping_columns_39ms_still_green(net_app):
    cols = net_app.ping_columns([39], 60)
    colors = [c for (_, c) in cols[0]]
    assert all(c == "green" for c in colors)


def test_ping_columns_40ms_amber(net_app):
    cols = net_app.ping_columns([40], 60)
    colors = [c for (_, c) in cols[0]]
    assert all(c == "amber" for c in colors)


# ---- alert_wan ---------------------------------------------------------------


def test_alert_wan_high_loss(net_app):
    wans = [{"iface": "eth0", "loss_pct": 10, "rtt_ms": 20}]
    assert net_app.alert_wan(wans, 100, 5) == "eth0"


def test_alert_wan_high_rtt(net_app):
    wans = [{"iface": "eth0", "loss_pct": 0, "rtt_ms": 120}]
    assert net_app.alert_wan(wans, 100, 5) == "eth0"


def test_alert_wan_healthy_returns_none(net_app):
    wans = [{"iface": "eth0", "loss_pct": 2, "rtt_ms": 20}]
    assert net_app.alert_wan(wans, 100, 5) is None


def test_alert_wan_negative_rtt_not_alert(net_app):
    # rtt_ms=-1 means no data, should not trigger rtt alert
    wans = [{"iface": "eth0", "loss_pct": 0, "rtt_ms": -1}]
    assert net_app.alert_wan(wans, 100, 5) is None


def test_alert_wan_picks_first_alerting(net_app):
    wans = [
        {"iface": "eth0", "loss_pct": 0, "rtt_ms": 20},
        {"iface": "eth1", "loss_pct": 20, "rtt_ms": 20},
    ]
    assert net_app.alert_wan(wans, 100, 5) == "eth1"


def test_alert_wan_exact_threshold_triggers(net_app):
    # >= threshold should trigger
    wans = [{"iface": "eth0", "loss_pct": 5, "rtt_ms": 20}]
    assert net_app.alert_wan(wans, 100, 5) == "eth0"


def test_alert_wan_rtt_exact_threshold(net_app):
    wans = [{"iface": "eth0", "loss_pct": 0, "rtt_ms": 100}]
    assert net_app.alert_wan(wans, 100, 5) == "eth0"
