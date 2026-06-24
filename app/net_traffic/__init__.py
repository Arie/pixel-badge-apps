# net_traffic — per-WAN internet traffic monitor for the CampZone 2019 "Pixel" badge.
# Polls the router CGI (/cgi-bin/traffic) and shows per-WAN down/up/total/ping screens.
# Mirrors ha_energy exactly: ON_BADGE guard, Carousel, 5-phase tick, LEFT/RIGHT nav, B exit.

import sys, time, gc
try:
    import ujson as json
except ImportError:                              # host (tests/lint) uses stdlib json
    import json

try:                                             # badge-only hardware modules
    import rgb, hub75, wifi, buttons, defines, system
    import urequests as requests
    ON_BADGE = True
except ImportError:                              # host: the pure logic still imports fine
    ON_BADGE = False

from pixelbadge.matrix import W, H, fb, fb_clear, px, fb_blit
from pixelbadge.pixelfont import _glyph, FONT, ink_bounds, draw_text, text_width, draw_icon
from pixelbadge.gauges import bar_left
from pixelbadge.carousel import Carousel

# ---- config ----------------------------------------------------------------
DEFAULTS = {
    'base_url': 'http://192.168.1.1',
    'poll_seconds': 1,
    'brightness': 10,
    'auto_advance_seconds': 2.5,
    'ping_scale_ms': 50,    # ping-graph full-height RTT in ms (fixed scale)
    'rtt_alert_ms': 100,    # RTT at or above this -> alert
    'loss_alert_pct': 5,    # loss% at or above this -> alert
    'ping_animate': True,   # smooth height-tween between polls on ping screen
}
try:
    with open('apps/net_traffic/config.json') as f:
        CFG = json.load(f)
except OSError:
    CFG = {}
cfg = dict(DEFAULTS)
cfg.update(CFG)

POLL_MS = int(cfg['poll_seconds']) * 1000
ADV_MS = int(cfg['auto_advance_seconds'] * 1000)
PING_SCALE = int(cfg['ping_scale_ms'])
RTT_ALERT = int(cfg['rtt_alert_ms'])
LOSS_ALERT = int(cfg['loss_alert_pct'])

# ---- colours ----------------------------------------------------------------
GREEN  = (0x2e, 0xd6, 0x40)   # download
BLUE   = (0x4f, 0xc3, 0xff)   # upload
GREY   = (0x9a, 0xa7, 0xb3)   # total
PURPLE = (0x55, 0x18, 0xcc)   # conns / ping-loss
AMBER  = (0xff, 0x9d, 0x3a)   # ping medium latency
RED    = (0xff, 0x2a, 0x2a)   # ping high latency / alert
WHITE  = (0xdf, 0xe7, 0xee)   # avg-ping overlay text

# ---- icon bitmaps (LOCKED from net-options.html ★ FINAL choices) ----------
# '#' = lit pixel, '.' = off. Parsed to row strings by _glyph at load.
ICONS = {k: _glyph(a) for k, a in {
'DOWN': """
...##...
...##...
.######.
..####..
...##...""",
'UP': """
...##...
..####..
.######.
...##...
...##...""",
'SIGMA': """
######..
.#......
..#.....
.#......
######..""",
'CONNS': """
..#..#..
.##..##.
########
.##..##.
..#..#..""",
}.items()}

# ---- pure, host-testable functions -----------------------------------------

def fmt_rate(bps):
    """Format bits/sec → compact string: e.g. 680000000 → '680M'."""
    if bps >= 1000000000:
        return str(bps // 1000000000) + 'G'
    if bps >= 1000000:
        return str(bps // 1000000) + 'M'
    return str(bps // 1000) + 'K'

def fmt_bytes(n):
    """Format byte count → compact string: e.g. 277000000000 → '277G'."""
    if n >= 1000000000:
        return str(n // 1000000000) + 'G'
    if n >= 1000000:
        return str(n // 1000000) + 'M'
    return str(n // 1000) + 'K'

def build_screens(wans, conns):
    """Build the ordered list of screen dicts from parsed poll data.

    For each wan: down, up, total, ping screens (4 each).
    Then one conns screen if conns is not None.
    Screen ids are stable: '<iface>:<kind>' for wan screens, 'conns' for the flow count.
    """
    multi = len(wans) > 1
    screens = []
    for i, wan in enumerate(wans):
        iface = wan['iface']
        prefix = wan.get('name', str(i + 1)) if multi else ''
        screens.append({'id': '%s:down' % iface, 'kind': 'down', 'iface': iface,
                        'bps': wan['down_bps'], 'bps_max': wan['down_max'],
                        'prefix': prefix, 'wan': wan})
        screens.append({'id': '%s:up' % iface, 'kind': 'up', 'iface': iface,
                        'bps': wan['up_bps'], 'bps_max': wan['up_max'],
                        'prefix': prefix, 'wan': wan})
        screens.append({'id': '%s:total' % iface, 'kind': 'total', 'iface': iface,
                        'total': wan['total_down'],
                        'prefix': prefix, 'wan': wan})
        screens.append({'id': '%s:ping' % iface, 'kind': 'ping', 'iface': iface,
                        'pings': wan.get('pings', []),
                        'prefix': prefix, 'wan': wan})
    if conns is not None:
        screens.append({'id': 'conns', 'kind': 'conns', 'conns': conns})
    return screens

def ping_columns(pings, scale_ms):
    """Return a list of column ops for the ping sparkline (line/trace mode).

    Each entry is a list with ONE (row, color_key) tuple for one x column.
    Columns align so newest ping is rightmost (matching the 32-wide display).
    color_key is 'purple', 'green', 'amber', or 'red' — strings for testability.

    Loss (-1): single purple pixel at row 0 (top).
    Normal rtt: level = round(min(rtt, scale_ms) / scale_ms * 6), 0..6.
                pixel row = 7 - level  (0 ms -> row 7, >=scale_ms -> row 1).
                Row 0 is reserved for loss only.
    Colors: green if rtt<40, amber if rtt<80, else red.
    """
    result = []
    for v in pings:
        if v < 0:
            result.append([(0, 'purple')])
        else:
            rtt = v
            color = 'green' if rtt < 40 else ('amber' if rtt < 80 else 'red')
            level = round(min(rtt, scale_ms) / scale_ms * 6)
            row = 7 - level
            result.append([(row, color)])
    return result

def alert_wan(wans, rtt_alert, loss_alert):
    """Return the iface of the first WAN in alert state, or None.

    Alert if loss_pct >= loss_alert OR (rtt_ms >= 0 AND rtt_ms >= rtt_alert).
    """
    for wan in wans:
        if wan.get('loss_pct', 0) >= loss_alert:
            return wan['iface']
        rtt = wan.get('rtt_ms', -1)
        if rtt >= 0 and rtt >= rtt_alert:
            return wan['iface']
    return None

def avg_ping(pings):
    """Return integer average (rounded) of non-loss entries (>= 0), or -1 if none.

    Loss sentinels are -1 and are excluded from the average.
    """
    total = 0
    count = 0
    for v in pings:
        if v >= 0:
            total += v
            count += 1
    if count == 0:
        return -1
    return int(round(total / count))

def avg_label(a):
    """Return display label for average ping value a.

    a < 0   -> "" (no data; caller should skip drawing)
    a < 100 -> "%dMS" % a  (e.g. 4 -> "4MS", 14 -> "14MS", 99 -> "99MS")
    else    -> "%d" % a    (e.g. 120 -> "120")
    """
    if a < 0:
        return ""
    if a < 100:
        return "%dMS" % a
    return "%d" % a

def interp_pings(prev, new, t):
    """Interpolate ping values for smooth animation (pure, host-testable).

    Returns a new list same length as new.
    For each index i:
      - if prev[i] >= 0 and new[i] >= 0: tween (int round)
      - else: return new[i] directly (loss/value transitions pop)
    If prev is shorter than new, missing entries are treated as equal to new
    (no tween for those columns).
    t is clamped by the caller to [0,1].
    """
    result = []
    for i in range(len(new)):
        n = new[i]
        if i < len(prev):
            p = prev[i]
        else:
            p = n          # no prev -> no tween
        if p >= 0 and n >= 0:
            result.append(int(round(p + (n - p) * t)))
        else:
            result.append(n)
    return result

def draw_text_outline(x, y, s, color):
    """Draw text s at (x, y) with a 1px black outline for readability.

    Draws s in BLACK at the 8 surrounding pixel offsets, then draws s in
    color at (x, y) on top. Off-screen pixels (e.g. x=-1) are clipped by px.
    """
    BLACK = (0, 0, 0)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw_text(x + dx, y + dy, s, BLACK)
    draw_text(x, y, s, color)

# ---- poll data storage ------------------------------------------------------
_data = {'wans': [], 'conns': None, 'stale': True}

# Per-iface ping history for animation tweening.
# prev_pings[iface] = pings list from the poll before last
# cur_pings[iface]  = pings list from the most recent poll
# last_poll_ms      = time.ticks_ms() at the moment of the last successful poll
prev_pings = {}
cur_pings  = {}
last_poll_ms = 0

def poll():
    """Fetch /cgi-bin/traffic and update _data. On any error: keep last-good, set stale."""
    global _data, prev_pings, cur_pings, last_poll_ms
    try:
        r = requests.get(cfg['base_url'] + '/cgi-bin/traffic')
        d = r.json(); r.close()
        new_wans = d.get('wans', [])
        # Rotate ping history before overwriting
        for wan in new_wans:
            iface = wan['iface']
            new_p = wan.get('pings', [])
            if iface in cur_pings:
                prev_pings[iface] = cur_pings[iface]
            else:
                prev_pings[iface] = new_p   # first poll: prev == new, t irrelevant
            cur_pings[iface] = new_p
        last_poll_ms = time.ticks_ms()
        _data['wans'] = new_wans
        _data['conns'] = d.get('conns', None)
        _data['stale'] = False
    except Exception:
        _data['stale'] = True
    gc.collect()

def _screens_from_data():
    """Build screen list from current _data, with alert wan first if alerting."""
    wans = _data['wans']
    conns = _data['conns']
    if not wans:
        # Graceful no-data placeholder: one conns-style screen
        return [{'id': 'loading', 'kind': 'loading', 'stale': _data['stale']}]
    screens = build_screens(wans, conns)
    al = alert_wan(wans, RTT_ALERT, LOSS_ALERT)
    if al:
        # Move alerting wan's ping screen to front
        ping_id = '%s:ping' % al
        front = [s for s in screens if s['id'] == ping_id]
        rest  = [s for s in screens if s['id'] != ping_id]
        screens = front + rest
    return screens

# ---- render -----------------------------------------------------------------
blink_on = True

_COLOR_MAP = {'green': GREEN, 'amber': AMBER, 'red': RED, 'purple': PURPLE}

def _draw_prefix(prefix):
    """Draw a small prefix label (WAN name) at x=0; returns x offset after prefix."""
    if not prefix:
        return 0
    x = draw_text(0, 0, prefix[:3], GREY)
    return x + 1

def draw_screen(s):
    """Render one screen into the framebuffer."""
    k = s['kind']
    if k == 'loading':
        draw_text(0, 1, 'NET', GREY)
        draw_text(0, 4, '---' if s.get('stale') else 'WAIT', GREY)
        return
    if k == 'down':
        draw_icon(0, 0, ICONS['DOWN'], GREEN)
        px_off = 9
        txt = fmt_rate(s['bps'])
        draw_text(px_off, 0, txt, GREEN)
        if s['bps_max'] > 0:
            bar_left(7, s['bps'] / s['bps_max'], GREEN)
        return
    if k == 'up':
        draw_icon(0, 0, ICONS['UP'], BLUE)
        px_off = 9
        txt = fmt_rate(s['bps'])
        draw_text(px_off, 0, txt, BLUE)
        if s['bps_max'] > 0:
            bar_left(7, s['bps'] / s['bps_max'], BLUE)
        return
    if k == 'total':
        draw_icon(0, 0, ICONS['SIGMA'], GREY)
        txt = fmt_bytes(s['total'])
        draw_text(9, 0, txt, GREY)
        return
    if k == 'conns':
        draw_icon(0, 0, ICONS['CONNS'], PURPLE)
        draw_text(9, 0, str(s['conns']), PURPLE)
        return
    if k == 'ping':
        # full-width sparkline: 32 columns, newest entry at rightmost column
        pings = s['pings']
        n = len(pings)
        if n == 0:
            draw_text(0, 1, 'PING', GREY)
            draw_text(0, 4, '---', GREY)
            return
        # Compute tween fraction t in [0, 1]
        iface = s.get('iface', '')
        if cfg.get('ping_animate') and iface in cur_pings and iface in prev_pings:
            now_ms = time.ticks_ms()
            elapsed = time.ticks_diff(now_ms, last_poll_ms)
            t = min(1.0, elapsed / float(POLL_MS))
            draw_pings = interp_pings(prev_pings[iface], cur_pings[iface], t)
        else:
            draw_pings = pings
        # pad so newest is at x=31
        start_x = max(0, W - n)
        visible = draw_pings[max(0, n - W):]
        scale = cfg['ping_scale_ms']
        cols = ping_columns(visible, scale)
        for i, ops in enumerate(cols):
            x = start_x + i
            for (row, color_key) in ops:
                c = _COLOR_MAP.get(color_key, GREY)
                if color_key == 'purple' and not blink_on:
                    c = (0, 0, 0)    # blink the loss dot
                px(x, row, c)
        # avg overlay always uses real (cur) pings
        a = avg_ping(pings)
        lbl = avg_label(a)
        if lbl:
            draw_text_outline(0, 0, lbl, WHITE)
        return

def render(s):
    fb_clear()
    draw_screen(s)
    fb_blit()

def _is_alerting():
    """True if any current WAN is in alert state."""
    return alert_wan(_data['wans'], RTT_ALERT, LOSS_ALERT) is not None

# ---- input ------------------------------------------------------------------
state = {'nav': 0, 'exit': False, 'paused': False,
         'bright': int(CFG.get('brightness', cfg['brightness']))}

def cb_left(d):
    if d: state['nav'] = -1; state['paused'] = True
def cb_right(d):
    if d: state['nav'] = 1; state['paused'] = True
def cb_up(d):
    if d: state['bright'] = min(30, state['bright'] + 2)
def cb_down(d):
    if d: state['bright'] = max(1, state['bright'] - 2)
def cb_a(d):
    if d: state['paused'] = not state['paused']
def cb_b(d):
    if d: state['exit'] = True

if ON_BADGE:
    buttons.register(defines.BTN_LEFT,  cb_left)
    buttons.register(defines.BTN_RIGHT, cb_right)
    buttons.register(defines.BTN_UP,    cb_up)
    buttons.register(defines.BTN_DOWN,  cb_down)
    buttons.register(defines.BTN_A,     cb_a)
    buttons.register(defines.BTN_B,     cb_b)

# ---- main loop --------------------------------------------------------------
class Display:
    """One screen-tick = five small phases. main() just calls step() in a loop."""
    def __init__(self):
        screens = _screens_from_data()
        self.car = Carousel(screens)
        self.bright = state['bright']
        self.last_poll = self.last_adv = self.touched = time.ticks_ms()
        self.dirty = True
        self.prev_blink = False
        self.alerting = False

    def _brightness(self, now):
        if state['bright'] != self.bright:
            self.bright = state['bright']
            rgb.brightness(self.bright)
            self.touched = now

    def _poll(self, now):
        if wifi.status() and time.ticks_diff(now, self.last_poll) >= POLL_MS:
            poll()
            self.last_poll = now
            new_screens = _screens_from_data()
            self.car.refresh(new_screens)
            self.alerting = _is_alerting()
            self.dirty = True

    def _select(self, now):
        if state['nav']:
            self.car.step(state['nav']); state['nav'] = 0
            self.last_adv = self.touched = now
            self.dirty = True
        elif not state['paused'] and time.ticks_diff(now, self.last_adv) >= ADV_MS:
            self.car.step(1); self.last_adv = now
            self.dirty = True

    def _is_ping_screen(self):
        """True if the current screen is a ping screen."""
        s = self.car.current()
        return s.get('kind') == 'ping'

    def _draw(self, now):
        global blink_on
        blink_on = (now // 450) % 2 == 0
        if self.alerting and blink_on != self.prev_blink:
            self.dirty = True         # animate the alert blink
        self.prev_blink = blink_on
        # Ping-animate: bypass dirty gate; always render at ~14fps
        if cfg.get('ping_animate') and self._is_ping_screen():
            try:
                render(self.car.current())
            except Exception as e:
                sys.print_exception(e)
            self.dirty = False
        elif self.dirty:
            try:
                render(self.car.current())
            except Exception as e:
                sys.print_exception(e)
            self.dirty = False

    def _idle_ms(self, now):
        # Ping screen with animation: spin at ~14fps (70ms sleep per tick)
        if cfg.get('ping_animate') and self._is_ping_screen():
            return 70
        if time.ticks_diff(now, self.touched) < 1200:
            return 50
        return 120 if self.alerting else 220

    def step(self):
        now = time.ticks_ms()
        self._brightness(now)
        self._poll(now)
        self._select(now)
        self._draw(now)
        time.sleep_ms(self._idle_ms(now))

def main():
    rgb.background((0, 0, 0))
    rgb.brightness(state['bright'])
    if not wifi.status():
        wifi.connect(); wifi.wait()
    if wifi.status():
        poll()
    display = Display()
    while not state['exit']:
        display.step()
    rgb.clear()
    system.home()

if ON_BADGE:        # the badge launches the app by importing it; host import stays inert
    main()
