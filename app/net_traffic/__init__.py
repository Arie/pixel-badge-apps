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
    'ping_dwell_seconds': 12,
    'ping_scale_ms': 50,    # ping-graph full-height RTT in ms (fixed scale)
    'rtt_alert_ms': 100,    # RTT at or above this -> alert
    'loss_alert_pct': 1,    # loss% at or above this -> alert
    'ping_only': False,     # dev: show ONLY the ping screen(s), no rotation
    'ping_animate': True,   # smooth left-scroll on ping screen
    'ping_rate': 5.0,       # samples/sec the producer emits
    'ping_lag': 10,         # jitter-buffer depth in samples
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
PING_DWELL_MS = int(cfg['ping_dwell_seconds'] * 1000)
PING_SCALE = int(cfg['ping_scale_ms'])
RTT_ALERT = int(cfg['rtt_alert_ms'])
LOSS_ALERT = int(cfg['loss_alert_pct'])
# Maximum history depth kept per iface (oldest→newest ring)
HIST_MAX = 96

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
    """Format byte count → compact string: e.g. 277000000000 → '277GB'."""
    if n >= 1000000000:
        return str(n // 1000000000) + 'GB'
    if n >= 1000000:
        return str(n // 1000000) + 'MB'
    return str(n // 1000) + 'KB'

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
        screens.append({'id': '%s:total_down' % iface, 'kind': 'total', 'iface': iface,
                        'total': wan['total_down'], 'dir': 'down',
                        'prefix': prefix, 'wan': wan})
        screens.append({'id': '%s:total_up' % iface, 'kind': 'total', 'iface': iface,
                        'total': wan['total_up'], 'dir': 'up',
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
    return total / count           # float; avg_label rounds for display

def avg_label(a):
    """Return display label for average ping value a.

    a < 0   -> "" (no data; caller should skip drawing)
    a < 100 -> "%dMS" % a  (e.g. 4 -> "4MS", 14 -> "14MS", 99 -> "99MS")
    else    -> "%d" % a    (e.g. 120 -> "120")
    """
    if a < 0:
        return ""
    if a < 10:
        return "%.1fMS" % a              # sub-10ms: one decimal (e.g. 4.2MS)
    if a < 100:
        return "%dMS" % int(round(a))
    return "%d" % int(round(a))

def bar_height(v, scale):
    """Return filled-bar height in pixels for a ping RTT value v.

    Height 1..6 growing up from the bottom (row 7 is the base row, row 2 is max).
    v=0 → h=1 (minimum visible bar), v>=scale → h=6.
    Does NOT handle loss (v<0); caller should check that first.
    """
    return max(1, int(round(min(v, scale) / scale * 6)))

def scroll_sample(combined, src):
    """Sample the combined ping buffer at fractional index src for smooth scrolling.

    Interpolates between adjacent integer samples. Loss handling:
      - If the nearest sample (by fractional distance) is a loss (-1), return -1.
      - If only one neighbour is a loss, return the non-loss neighbour (no interp).
      - Otherwise linearly interpolate and round.
    Past-end indices clamp to the last element.
    """
    i = int(src)
    if i < 0: i = 0
    frac = src - i
    a = combined[i] if i < len(combined) else combined[-1]
    b = combined[i + 1] if i + 1 < len(combined) else a
    near = a if frac < 0.5 else b
    if near < 0:            # nearest sample is a loss -> loss column
        return -1
    if a < 0:
        return b
    if b < 0:
        return a
    return int(round(a * (1.0 - frac) + b * frac))

def advance_play(play_pos, newest, hist_base, rate, dt, lag):
    """Advance the playhead at constant rate, clamped to the jitter buffer.

    play_pos  - current float absolute-index of the rightmost displayed sample
    newest    - absolute index of the latest sample in hist (= total - 1)
    hist_base - absolute index of the oldest sample in hist (= total - len(hist))
    rate      - samples/sec the producer emits (e.g. 5.0)
    dt        - elapsed seconds since last call
    lag       - jitter-buffer depth in samples (e.g. 4)

    Returns the new play_pos (float).
    """
    play_pos = play_pos + rate * dt
    if play_pos > newest:                 # caught up / data late -> hold at newest
        play_pos = newest
    if newest - play_pos > 2 * lag:       # fell too far behind (after a stall) -> snap
        play_pos = newest - lag
    floor = hist_base + 31                # need a full 32-wide window
    if play_pos < floor:
        play_pos = floor
    return play_pos

def draw_text_outline(x, y, s, color):
    """Draw text s at (x, y) with a 1px black outline for readability.

    Draws s in BLACK at the 8 surrounding pixel offsets, then draws s in
    color at (x, y) on top. Off-screen pixels (e.g. x=-1) are clipped by px.
    """
    BLACK = (0, 0, 0)
    for dx, dy in ((-1, 0), (1, 0), (0, -1),     # left, right, top
                   (-1, -1), (1, -1)):           # top corners (no bottom border)
        draw_text(x + dx, y + dy, s, BLACK)
    draw_text(x, y, s, color)

# ---- poll data storage ------------------------------------------------------
_data = {'wans': [], 'conns': None, 'stale': True}

# Per-iface jitter-buffer state (dicts keyed by iface string):
#   hist[iface]     - list of samples oldest→newest, max HIST_MAX entries
#   total[iface]    - count of samples ever appended (absolute index of next sample)
#                     so hist[j] has absolute index  total - len(hist) + j
#   cgi_seq[iface]  - last seen wan['seq'] from the CGI (or None)
#   play_pos[iface] - float absolute index of the rightmost DISPLAYED sample
# last_frame_ms     - ticks_ms() at the last rendered frame (for dt computation)
# last_poll_ms      - kept for compat (not used by scroll any more)
hist = {}
total = {}
cgi_seq = {}
play_pos = {}
last_frame_ms = 0
last_poll_ms = 0

def poll():
    """Fetch /cgi-bin/traffic and update _data. On any error: keep last-good, set stale."""
    global _data, hist, total, cgi_seq, play_pos, last_poll_ms
    try:
        r = requests.get(cfg['base_url'] + '/cgi-bin/traffic')
        d = r.json(); r.close()
        new_wans = d.get('wans', [])
        for wan in new_wans:
            iface = wan['iface']
            newer = wan.get('pings', [])
            s = wan.get('seq')
            if iface not in hist:
                # First poll for this iface: seed the buffer
                hist[iface] = list(newer)
                total[iface] = s if s is not None else len(newer)
                cgi_seq[iface] = s
                lag = cfg['ping_lag']
                play_pos[iface] = float(total[iface] - 1 - lag)
            else:
                # Subsequent polls: determine how many new samples arrived
                if s is not None and cgi_seq[iface] is not None:
                    n_new = s - cgi_seq[iface]
                else:
                    n_new = int(round(cfg['ping_rate'] * cfg['poll_seconds']))
                # Clamp to valid range
                if n_new < 0: n_new = 0
                if n_new > len(newer): n_new = len(newer)
                if n_new > 0:
                    hist[iface].extend(newer[-n_new:])
                    total[iface] += n_new
                    if len(hist[iface]) > HIST_MAX:
                        del hist[iface][:len(hist[iface]) - HIST_MAX]
                cgi_seq[iface] = s
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
    if cfg.get('ping_only'):                  # dev: keep only ping screens
        only = [s for s in screens if s.get('kind') == 'ping']
        if only:
            screens = only
    al = alert_wan(wans, RTT_ALERT, LOSS_ALERT)
    if al:
        # Move alerting wan's ping screen to front
        ping_id = '%s:ping' % al
        front = [s for s in screens if s['id'] == ping_id]
        rest  = [s for s in screens if s['id'] != ping_id]
        screens = front + rest
    return screens

# ---- render -----------------------------------------------------------------

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
        draw_icon(0, 0, ICONS['DOWN'], RED)
        px_off = 9
        txt = fmt_rate(s['bps'])
        draw_text(px_off, 0, txt, RED)
        if s['bps_max'] > 0:
            bar_left(7, s['bps'] / s['bps_max'], RED)
        return
    if k == 'up':
        draw_icon(0, 0, ICONS['UP'], GREEN)
        px_off = 9
        txt = fmt_rate(s['bps'])
        draw_text(px_off, 0, txt, GREEN)
        if s['bps_max'] > 0:
            bar_left(7, s['bps'] / s['bps_max'], GREEN)
        return
    if k == 'total':
        down = s.get('dir') == 'down'
        col = RED if down else GREEN                     # match the rate colours
        draw_icon(0, 0, ICONS['DOWN'] if down else ICONS['UP'], col)  # arrow = direction
        draw_text(9, 0, fmt_bytes(s['total']), col)
        return
    if k == 'conns':
        draw_icon(0, 0, ICONS['CONNS'], PURPLE)
        draw_text(9, 0, str(s['conns']), PURPLE)
        return
    if k == 'ping':
        # full-width sparkline: 32 columns, jitter-buffer constant-rate scroll
        pings = s['pings']
        n = len(pings)
        if n == 0:
            draw_text(0, 1, 'PING', GREY)
            draw_text(0, 4, '---', GREY)
            return
        iface = s.get('iface', '')
        scale = cfg['ping_scale_ms']
        if cfg.get('ping_animate') and iface in hist:
            # play_pos is advanced in Display._advance_ping; here we just read it.
            # Snap the window to integer sample positions: exact bars, no morph.
            buf = hist[iface]
            hist_base = total[iface] - len(hist[iface])
            ipp = int(round(play_pos[iface]))
            for c in range(W):
                idx = ipp - (31 - c) - hist_base
                if idx < 0 or idx >= len(buf):
                    continue
                v = buf[idx]
                if v < 0:
                    px(c, 0, PURPLE)              # steady loss dot
                else:
                    color = GREEN if v < 40 else (AMBER if v < 80 else RED)
                    h = bar_height(v, scale)
                    for r in range(h):
                        px(c, 7 - r, color)
        else:
            # Static path: draw the last 32 of hist (or raw pings) at integer positions
            buf = hist[iface] if iface in hist else pings
            start = max(0, len(buf) - W)
            for c in range(W):
                idx = start + c
                if idx >= len(buf):
                    break
                v = buf[idx]
                if v < 0:
                    px(c, 0, PURPLE)              # steady loss dot (no blink)
                else:
                    color = GREEN if v < 40 else (AMBER if v < 80 else RED)
                    h = bar_height(v, scale)
                    for r in range(h):
                        px(c, 7 - r, color)
        # avg overlay always uses real current pings
        a = avg_ping(pings)
        lbl = avg_label(a)
        if lbl:
            draw_text_outline(0, 0, lbl, WHITE)
        return

def render(s):
    fb_clear()
    draw_screen(s)
    gc.collect()        # clean heap BEFORE the blit: rgb.clear() blanks the panel, so a
    fb_blit()           # GC pause between clear and hub75.image() = a visible flicker

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
        self.alerting = False
        self.last_ipp = -1          # last integer scroll position rendered (dirty-gate)

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
            al = alert_wan(_data['wans'], RTT_ALERT, LOSS_ALERT)
            was = self.alerting
            self.alerting = al is not None
            if al and not was:                    # surface the alerting wan once...
                ping_id = '%s:ping' % al
                if self.car.cur_id != ping_id:    # ...unless it's already at the front
                    self.car.cur_id = ping_id
                    self.last_adv = now
            self.dirty = True

    def _select(self, now):
        if state['nav']:
            self.car.step(state['nav']); state['nav'] = 0
            self.last_adv = self.touched = now
            self.dirty = True
        elif not state['paused']:
            # Use longer dwell on ping screens
            dwell = PING_DWELL_MS if self._is_ping_screen() else ADV_MS
            if time.ticks_diff(now, self.last_adv) >= dwell:
                self.car.step(1); self.last_adv = now
                self.dirty = True

    def _is_ping_screen(self):
        """True if the current screen is a ping screen."""
        s = self.car.current()
        return s.get('kind') == 'ping'

    def _advance_ping(self, now):
        """Advance the ping play-head every tick; return its integer scroll position
        (or None if no data). Decoupled from rendering so we can redraw only when the
        integer position changes (nearest-sample bars are identical between steps)."""
        global last_frame_ms
        iface = self.car.current().get('iface', '')
        if iface not in hist:
            return None
        if last_frame_ms == 0:
            last_frame_ms = now
        dt = time.ticks_diff(now, last_frame_ms) / 1000.0
        if dt > 0.3:
            dt = 0.3                 # avoid a jump after the screen was off
        last_frame_ms = now
        newest = total[iface] - 1
        hist_base = total[iface] - len(hist[iface])
        play_pos[iface] = advance_play(
            play_pos[iface], newest, hist_base, cfg['ping_rate'], dt, cfg['ping_lag'])
        return int(round(play_pos[iface]))

    def _draw(self, now):
        # Ping screen: advance the play-head every tick but redraw (and blit, which
        # blanks the panel via rgb.clear) ONLY when the integer scroll position
        # changes -> ~5 redraws/sec instead of 14, killing the residual flicker.
        if cfg.get('ping_animate') and self._is_ping_screen():
            ipp = self._advance_ping(now)
            if ipp != self.last_ipp or self.dirty:
                try:
                    render(self.car.current())
                except Exception as e:
                    sys.print_exception(e)
                self.last_ipp = ipp
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
