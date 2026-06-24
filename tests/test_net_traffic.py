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


# ---- ping_columns (line/trace mode, fixed 50 ms scale) ----------------------


def test_ping_columns_loss_gives_purple_at_row0(net_app):
    cols = net_app.ping_columns([-1], 50)
    assert len(cols) == 1
    assert cols[0] == [(0, "purple")]


def test_ping_columns_loss_only_one_pixel(net_app):
    # loss: single purple dot at row 0, no other pixels
    cols = net_app.ping_columns([-1], 50)
    assert len(cols[0]) == 1


def test_ping_columns_0ms_at_bottom(net_app):
    # 0 ms → level=0 → row 7 (bottom)
    cols = net_app.ping_columns([0], 50)
    assert len(cols[0]) == 1
    assert cols[0][0][0] == 7


def test_ping_columns_50ms_at_top(net_app):
    # 50 ms (== scale) → level=6 → row 1
    cols = net_app.ping_columns([50], 50)
    assert len(cols[0]) == 1
    assert cols[0][0][0] == 1


def test_ping_columns_over_scale_capped_at_row1(net_app):
    # rtt > scale → clamped to scale → row 1, row 0 stays loss lane
    cols = net_app.ping_columns([200], 50)
    row = cols[0][0][0]
    assert row == 1
    assert row != 0


def test_ping_columns_25ms_near_mid(net_app):
    # 25 ms at scale 50 → level = round(25/50*6) = round(3.0) = 3 → row 4
    cols = net_app.ping_columns([25], 50)
    row = cols[0][0][0]
    assert row == 4


def test_ping_columns_one_pixel_per_column(net_app):
    # line mode: exactly one pixel per column for normal rtt
    cols = net_app.ping_columns([10, 20, 30], 50)
    for col in cols:
        assert len(col) == 1


def test_ping_columns_multiple_columns_count(net_app):
    # 2 entries → 2 columns
    cols = net_app.ping_columns([10, 20], 50)
    assert len(cols) == 2


def test_ping_columns_30ms_green(net_app):
    # 30 ms < 40 → green
    cols = net_app.ping_columns([30], 50)
    assert cols[0][0][1] == "green"


def test_ping_columns_39ms_still_green(net_app):
    cols = net_app.ping_columns([39], 50)
    assert cols[0][0][1] == "green"


def test_ping_columns_40ms_amber(net_app):
    cols = net_app.ping_columns([40], 50)
    assert cols[0][0][1] == "amber"


def test_ping_columns_60ms_amber(net_app):
    # 60 ms: 40 <= 60 < 80 → amber
    cols = net_app.ping_columns([60], 50)
    assert cols[0][0][1] == "amber"


def test_ping_columns_80ms_red(net_app):
    # 80 ms >= 80 → red
    cols = net_app.ping_columns([80], 50)
    assert cols[0][0][1] == "red"


def test_ping_columns_100ms_red(net_app):
    # 100 ms >= 80 → red
    cols = net_app.ping_columns([100], 50)
    assert cols[0][0][1] == "red"


def test_ping_columns_fixed_scale_4ms_near_bottom(net_app):
    # With fixed 50 ms scale, a 4 ms ping should be near the bottom (row 6 or 7)
    # level = round(4/50*6) = round(0.48) = 0 → row 7
    cols = net_app.ping_columns([4], 50)
    row = cols[0][0][0]
    assert row >= 6, "4 ms should be near the bottom with 50 ms fixed scale, got row %d" % row


def test_ping_columns_loss_row0_not_used_by_normal(net_app):
    # normal rtt never occupies row 0 (reserved for loss)
    cols = net_app.ping_columns([1, 10, 50, 100], 50)
    for col in cols:
        assert col[0][0] != 0


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


# ---- avg_ping ----------------------------------------------------------------


def test_avg_ping_normal(net_app):
    assert net_app.avg_ping([10, 20, 30]) == 20


def test_avg_ping_excludes_losses(net_app):
    assert net_app.avg_ping([10, -1, 20, -1]) == 15


def test_avg_ping_all_loss(net_app):
    assert net_app.avg_ping([-1, -1]) == -1


def test_avg_ping_empty(net_app):
    assert net_app.avg_ping([]) == -1


# ---- avg_label ---------------------------------------------------------------


def test_avg_label_single_digit(net_app):
    assert net_app.avg_label(4) == "4MS"


def test_avg_label_two_digits(net_app):
    assert net_app.avg_label(14) == "14MS"


def test_avg_label_two_digits_99(net_app):
    assert net_app.avg_label(99) == "99MS"


def test_avg_label_three_digits(net_app):
    assert net_app.avg_label(120) == "120"


def test_avg_label_no_data(net_app):
    assert net_app.avg_label(-1) == ""
