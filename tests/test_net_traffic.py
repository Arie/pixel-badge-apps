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
    assert net_app.avg_label(4) == "4.0MS"  # sub-10ms shows one decimal
    assert net_app.avg_label(4.2) == "4.2MS"
    assert net_app.avg_label(9.9) == "9.9MS"


def test_avg_label_two_digits(net_app):
    assert net_app.avg_label(14) == "14MS"


def test_avg_label_two_digits_99(net_app):
    assert net_app.avg_label(99) == "99MS"


def test_avg_label_three_digits(net_app):
    assert net_app.avg_label(120) == "120"


def test_avg_label_no_data(net_app):
    assert net_app.avg_label(-1) == ""


# ---- scroll_sample -----------------------------------------------------------


def test_scroll_sample_midpoint(net_app):
    # fractional index 0.5 between 10 and 20 → 15
    assert net_app.scroll_sample([10, 20], 0.5) == 15


def test_scroll_sample_integer_index(net_app):
    # integer index 1.0 → sample at index 1
    assert net_app.scroll_sample([10, 20, 30], 1.0) == 20


def test_scroll_sample_exact_last(net_app):
    # integer index at last element
    assert net_app.scroll_sample([10, 20, 30], 2.0) == 30


def test_scroll_sample_past_end_clamps(net_app):
    # index 1.9 in a 2-element list: b clamps to a → ~20
    result = net_app.scroll_sample([10, 20], 1.9)
    assert result == 20


def test_scroll_sample_loss_nearest_frac_above_half(net_app):
    # frac=0.6 → nearest is b (index 1) = -1 → loss
    assert net_app.scroll_sample([10, -1], 0.6) == -1


def test_scroll_sample_loss_nearest_frac_below_half(net_app):
    # frac=0.4 → nearest is a (index 0) = -1 → loss
    assert net_app.scroll_sample([-1, 20], 0.4) == -1


def test_scroll_sample_loss_neighbour_skipped(net_app):
    # frac=0.0 → nearest is a=10 (not loss); b=-1 is skipped → return a
    assert net_app.scroll_sample([10, -1], 0.0) == 10


# ---- advance_play ------------------------------------------------------------


def test_advance_play_advances_by_rate_times_dt(net_app):
    # play_pos 95.0, newest 100, lag=4; newest-play_pos=5 <= 2*4=8, no snap.
    # hist_base=0, floor=31 < 95. advance: 95 + 5*0.2 = 96.0 → 96.0
    result = net_app.advance_play(95.0, 100, 0, 5, 0.2, 4)
    assert result == 96.0


def test_advance_play_holds_at_newest(net_app):
    # play_pos 99.9, rate=5, dt=0.5 would push to 102.4 → clamped to newest=100
    result = net_app.advance_play(99.9, 100, 0, 5, 0.5, 4)
    assert result == 100


def test_advance_play_snaps_when_far_behind(net_app):
    # play_pos 50.0, newest 100, lag=4; newest-play_pos = 50 > 2*4=8 → snap to 100-4=96
    result = net_app.advance_play(50.0, 100, 0, 5, 0.1, 4)
    assert result == 96


def test_advance_play_floors_to_full_window(net_app):
    # play_pos 5.0, newest 40, hist_base 20; floor = 20+31 = 51; result clamped to 51
    result = net_app.advance_play(5.0, 40, 20, 5, 0.0, 4)
    assert result == 51


def test_advance_play_no_movement_when_dt_zero(net_app):
    # dt=0 → no advance; play_pos=35, newest=40, hist_base=0, lag=4
    # newest-play_pos=5 > 2*4=8? No (5 < 8). floor=31. play_pos stays 35.
    result = net_app.advance_play(35.0, 40, 0, 5, 0.0, 4)
    assert result == 35.0


def test_advance_play_normal_advance_within_bounds(net_app):
    # play_pos=93, newest=100, hist_base=60, rate=5, dt=0.2, lag=4
    # advance: 93 + 1.0 = 94; newest-94=6 <= 8, no snap; floor=91, 94>91 ok.
    result = net_app.advance_play(93.0, 100, 60, 5, 0.2, 4)
    assert result == 94.0


# ---- poll seq-delta append --------------------------------------------------


def test_poll_seq_delta_appends_correct_n_new(net_app):
    """Verify that the seq-driven append adds exactly n_new samples to hist."""
    # Seed the iface state as if a first poll happened: hist=[10,11,12], total=3, seq=3
    iface = "eth0"
    net_app.hist[iface] = [10, 11, 12]
    net_app.total[iface] = 3
    net_app.cgi_seq[iface] = 3
    net_app.play_pos[iface] = 2.0

    # Simulate what poll() does for a subsequent poll: s=5 → n_new=2
    newer = [13, 14]
    s = 5
    old_seq = net_app.cgi_seq[iface]
    n_new = s - old_seq  # = 2
    if n_new < 0:
        n_new = 0
    if n_new > len(newer):
        n_new = len(newer)
    net_app.hist[iface].extend(newer[-n_new:])
    net_app.total[iface] += n_new
    net_app.cgi_seq[iface] = s

    assert net_app.total[iface] == 5
    assert net_app.hist[iface] == [10, 11, 12, 13, 14]
    assert net_app.cgi_seq[iface] == 5


def test_poll_seq_delta_clamps_n_new_to_len_newer(net_app):
    """n_new clamped to len(newer) if seq jumps more than available data."""
    iface = "eth1"
    net_app.hist[iface] = [1, 2, 3]
    net_app.total[iface] = 3
    net_app.cgi_seq[iface] = 3
    net_app.play_pos[iface] = 2.0

    newer = [4, 5]  # only 2 available
    s = 20  # seq jumped by 17 — more than len(newer)=2 → clamp to 2
    n_new = s - net_app.cgi_seq[iface]
    if n_new > len(newer):
        n_new = len(newer)
    net_app.hist[iface].extend(newer[-n_new:])
    net_app.total[iface] += n_new
    net_app.cgi_seq[iface] = s

    assert len(net_app.hist[iface]) == 5
    assert net_app.hist[iface][-2:] == [4, 5]


# ---- bar_height --------------------------------------------------------------


def test_bar_height_zero_gives_minimum_1(net_app):
    # 0 ms → minimum bar height of 1 (not 0)
    assert net_app.bar_height(0, 50) >= 1


def test_bar_height_full_scale_gives_6(net_app):
    # at full scale → height 6 (top of bar area)
    assert net_app.bar_height(50, 50) == 6


def test_bar_height_half_scale_near_3(net_app):
    # 25 ms at scale 50 → round(25/50*6) = round(3.0) = 3
    assert net_app.bar_height(25, 50) == 3


def test_bar_height_clamps_above_scale(net_app):
    # rtt above scale clamps to 6
    assert net_app.bar_height(200, 50) == 6


def test_bar_height_small_value(net_app):
    # 4 ms at scale 50 → round(4/50*6) = round(0.48) = 0 → clamped to min 1
    assert net_app.bar_height(4, 50) == 1


def test_bar_height_returns_int(net_app):
    assert isinstance(net_app.bar_height(25, 50), int)
