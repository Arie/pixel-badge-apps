# Startup helpers shared by the badge apps.

import time

from pixelbadge.matrix import fb_blit, fb_clear, px

WIFI_COL = (0x4F, 0xC3, 0xFF)  # light blue, like the launcher's connect indicator

# A small wifi glyph centred on the 32x8 panel: a base dot plus three arcs that
# open downward. Arcs are lit progressively (level 0..3) to read as "connecting".
_WIFI_DOT = ((15, 6),)
_WIFI_ARCS = (
    ((15, 4), (14, 5), (16, 5)),
    ((14, 3), (15, 3), (16, 3), (13, 4), (17, 4)),
    ((13, 2), (14, 2), (15, 2), (16, 2), (17, 2), (12, 3), (18, 3)),
)


def _draw_wifi(level, color):
    fb_clear()
    for x, y in _WIFI_DOT:
        px(x, y, color)
    for i, arc in enumerate(_WIFI_ARCS):
        if level > i:
            for x, y in arc:
                px(x, y, color)
    fb_blit()


def connect_wifi(wifi, timeout_ms=20000, color=WIFI_COL):
    """Connect to wifi, animating the wifi glyph until associated or timed out.

    Returns True once connected, False on timeout. No-op returning True if already up.
    Drawn on the badge only (uses the panel); not called on the host.
    """
    if wifi.status():
        return True
    wifi.connect()
    start = time.ticks_ms()
    level = 0
    while not wifi.status() and time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        _draw_wifi(level, color)
        level = (level + 1) % 4
        time.sleep_ms(300)
    return wifi.status()
