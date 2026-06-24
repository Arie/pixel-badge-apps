# HA Energy — Home Assistant energy display for the CampZone 2019 "Pixel" badge.
# Single auto-advancing gauge view; LEFT/RIGHT step, B exits.
# Ported from the mockup in pixel-badge-apps/mockup. See docs/ for the design.

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
# DEFAULTS are this install's values; config.json (gitignored) overrides them.
DEFAULTS = {
    'base_url': '', 'token': '',
    'poll_seconds': 5, 'brightness': 10, 'idle_watts': 10, 'auto_advance_seconds': 2.5,
    'grid_connection_w': 17250,   # USE overflow + GRID import full-scale
    'solar_max_w': 6000,          # SOL max, USE-bar scale, GRID export full-scale
    'solar_entity': 'sensor.solaredge_se6k_ac_power',
    'grid_entity': 'sensor.homewizard_p1_vermogen',
    'ev_entity': 'sensor.peblar_ev_charger_power',   # EV charger power (W); shown only when active
    'ev_max_w': 11000,                                # 3x16A
    'batteries': [
        {'label': 'HW1', 'soc': 'sensor.plug_in_battery_state_of_charge',   'power': 'sensor.plug_in_battery_power',   'power_max': 800,  'weight': 1, 'soc_min': 0},
        {'label': 'HW2', 'soc': 'sensor.plug_in_battery_state_of_charge_2', 'power': 'sensor.plug_in_battery_power_2', 'power_max': 800,  'weight': 1, 'soc_min': 0},
        {'label': 'ZEN', 'soc': 'sensor.zendure_2400_ac_laadpercentage',   'power': 'sensor.zendure_signed_power',    'power_max': 2400, 'weight': 3, 'soc_min': 10},
    ],
}
try:
    with open('apps/ha_energy/config.json') as f:
        CFG = json.load(f)
except OSError:                                  # absent off-device; defaults stand in
    CFG = {}
cfg = dict(DEFAULTS)
cfg.update(CFG)                                  # config.json wins, key by key

BASE = cfg['base_url']
HEADERS = {'Authorization': 'Bearer ' + cfg['token']}
POLL_MS = int(cfg['poll_seconds']) * 1000
ADV_MS = int(cfg['auto_advance_seconds'] * 1000)
IDLE_W = cfg['idle_watts']                        # |power| below this = idle
USE_SCALE = cfg['solar_max_w']                    # USE bar full-scale
GRID_MAX = cfg['grid_connection_w']               # USE boost-overflow threshold

# ---- colours (tuned on the panel) -------------------------------------------
PURPLE = (0x55, 0x18, 0xcc)   # consumption / import / battery charging
GREEN  = (0x2e, 0xd6, 0x40)   # solar / export / battery discharging
LBLUE  = (0x4f, 0xc3, 0xff)   # self-use
AMBER  = (0xff, 0x9d, 0x3a)   # SOC mid
RED    = (0xff, 0x4d, 0x4d)   # SOC low
ALERT  = (0xff, 0x2a, 0x2a)   # overflow (blinking)

# ---- pixel-art tables ------------------------------------------------------
# Glyphs/icons are drawn as art: '#' = lit pixel, '.' = off. Parsed to rows at
# load. (Dots, not spaces, so trailing-whitespace tooling can't corrupt them.)

# 8x5 icons (SUN=SOL, HOME=USE, SELF, GRID=tower, BATT=SOC, BOLT=battery power)
ICONS = {ch: _glyph(a) for ch, a in {
'SUN': """
.#.##.#.
..####..
########
..####..
.#.##.#.""",
'HOME': """
...##...
..####..
.######.
.#....#.
.#.##.#.""",
'SELF': """
...##...
..####..
.######.
.######.
.######.""",
'GRID': """
...##...
.######.
..#..#..
.######.
#......#""",
'BATT': """
#####...
#...#...
#...##..
#...#...
#####...""",
'BOLT': """
...###..
..##....
.#####..
....##..
...##...""",
'EV': """
..####..
.#....#.
########
########
.##..##.""",
}.items()}

# ---- stats (built from config; DEFAULTS reproduce this install exactly) ------
def _build_stats(c):
    bats, entities, pids = [], {'SOL': c['solar_entity'], 'GRID': c['grid_entity']}, []
    for bc in c['batteries']:
        label = bc.get('label'); soc = bc.get('soc'); power = bc.get('power')
        if not (label and soc and power):
            continue                                  # skip malformed battery entries
        pid = label + 'P'
        bats.append({'id':label, 'label':label, 'kind':'battery',
                     'socId':label, 'powerId':pid, 'powerMax':bc.get('power_max', 800),
                     'weight':bc.get('weight', 1), 'socMin':bc.get('soc_min', 0)})
        entities[label] = soc; entities[pid] = power; pids.append(pid)
    flow = [
     {'id':'USE', 'label':'USE', 'icon':'HOME','kind':'use',   'color':PURPLE,'max':c['grid_connection_w']},
     {'id':'SOL', 'label':'SOL', 'icon':'SUN', 'kind':'power', 'color':GREEN, 'max':c['solar_max_w'], 'hideIdle':True},
     {'id':'SELF','label':'SELF','icon':'SELF','kind':'self',  'color':LBLUE, 'max':c['solar_max_w'], 'hideIdle':True},
     {'id':'GRID','label':'GRID','icon':'GRID','kind':'grid',  'maxPos':c['grid_connection_w'],'maxNeg':c['solar_max_w']},
    ]
    if c.get('ev_entity'):                            # EV charger: a hide-when-idle load
        flow.append({'id':'EV', 'label':'EV', 'icon':'EV', 'kind':'power',
                     'color':PURPLE, 'max':c['ev_max_w'], 'hideIdle':True})
        entities['EV'] = c['ev_entity']
    return flow + bats, entities, pids

STATS, ENTITIES, BAT_POWER_IDS = _build_stats(cfg)
BATSUM = {'kind':'batsummary', 'id':'BAT'}
VALUES = {}     # id -> float (raw HA readings)

# ---- values, colours, formatting --------------------------------------------
def value_of(s):
    k = s['kind']
    if k == 'use':
        # house load = solar + grid − Σ battery power (+ charge draws, − discharge supplies)
        total = VALUES.get('SOL', 0) + VALUES.get('GRID', 0)
        for p in BAT_POWER_IDS:
            total -= VALUES.get(p, 0)
        return total
    if k == 'self':
        g = VALUES.get('GRID', 0)
        sv = VALUES.get('SOL', 0) - (-g if g < 0 else 0)   # solar minus solar-exported
        return sv if sv > 0 else 0                          # never negative (battery export ≠ neg self-use)
    return VALUES.get(s['id'], 0)
def is_signed(s):
    return s['kind'] == 'grid'
def color_of(s, v):
    if s['kind'] == 'grid':
        return GREEN if v < 0 else PURPLE
    return s['color']
def soc_color(soc):
    return GREEN if soc >= 50 else (AMBER if soc >= 20 else RED)
def power_color(w):
    return PURPLE if w >= 0 else GREEN
def display_soc(s):
    mn = s.get('socMin', 0)
    raw = VALUES.get(s['socId'], 0)
    d = int(round((raw - mn) / (100 - mn) * 100))
    return 0 if d < 0 else (100 if d > 100 else d)
def fleet_soc():
    bats = [s for s in STATS if s['kind'] == 'battery']
    tot = 0; ws = 0
    for bb in bats:
        w = bb.get('weight', 1)
        tot += display_soc(bb) * w; ws += w
    return int(round(tot / ws)) if ws else 0

def fmt_power(v, signed):
    a = abs(v)
    sign = ('-' if v < 0 else '+') if signed else ''
    if a < 1000:
        return sign + str(int(round(a))) + 'W'
    k = a / 1000.0
    return sign + (('%.1f' % k) if k >= 10 else ('%.2f' % k)) + 'KW'
def fmt_bat(v):
    return fmt_power(v, True)
def fmt(s, v):
    return fmt_power(v, is_signed(s))
def fit_value(txt, avail):
    if text_width(txt) <= avail:
        return txt
    txt = txt.replace('KW', 'K')
    if text_width(txt) <= avail:
        return txt
    i = txt.find('.')
    if i >= 0 and i + 2 < len(txt) and txt[i + 2] in '0123456789':
        txt = txt[:i + 2] + txt[i + 3:]
    return txt

blink_on = True
def gauge(s, v, col):
    if s['kind'] == 'grid':
        mx = s['maxNeg'] if v < 0 else s['maxPos']
    else:
        mx = s['max']
    frac = abs(v) / mx
    if frac > 1:
        if blink_on:
            bar_left(7, 1.0, ALERT)
    else:
        bar_left(7, frac, col)      # always from the left; colour shows the sign

def use_segments(usage, solar):
    """Split into (self-use, grid-import, export) watts: solar used at home,
    the rest of usage drawn from the grid, and any solar beyond usage exported."""
    self_w = solar if solar < usage else usage
    return (self_w, usage - self_w, solar - self_w)

def draw_use_bar(usage):
    if usage > GRID_MAX:                        # boost beyond the grid connection
        if blink_on:
            bar_left(7, 1.0, ALERT)
        return
    solar = VALUES.get('SOL', 0)
    self_w, _imp, _exp = use_segments(usage, solar)
    end_self = int(min(1.0, self_w / USE_SCALE) * W + 0.5)   # solar used at home (green)
    end_imp  = int(min(1.0, usage  / USE_SCALE) * W + 0.5)   # ...then grid import (purple)
    end_exp  = int(min(1.0, solar  / USE_SCALE) * W + 0.5)   # ...or solar export (amber)
    for i in range(end_self):
        px(i, 7, GREEN)
    for i in range(end_self, end_imp):
        px(i, 7, PURPLE)
    for i in range(end_imp, end_exp):
        px(i, 7, AMBER)

def draw_stat(s):
    k = s['kind']
    if k == 'batsummary':
        avg = fleet_soc()
        col = soc_color(avg)
        draw_icon(0, 0, ICONS.get('BATT'), col)
        draw_text(9, 0, '0W', col)
        bar_left(7, avg / 100.0, col)
        return
    if k == 'battery':
        pw = VALUES.get(s['powerId'], 0)
        pc = power_color(pw)
        draw_text(0, 0, s['label'], pc)
        lx = text_width(s['label']) + 2
        draw_text(lx, 0, fit_value(fmt_bat(pw), W - lx), pc)
        bar_left(7, display_soc(s) / 100.0, pc)
        return
    v = value_of(s)
    col = color_of(s, v)
    draw_icon(0, 0, ICONS.get(s['icon']), col)
    draw_text(9, 0, fit_value(fmt(s, v), W - 9), col)
    if k == 'use':
        draw_use_bar(v)         # two-tone: green self-use / purple import / amber export
    else:
        gauge(s, v, col)

# ---- active list (idle filter + BAT summary) --------------------------------
def is_active(s):
    if s['kind'] == 'battery':
        return abs(VALUES.get(s['powerId'], 0)) >= IDLE_W
    if s.get('hideIdle'):
        return abs(value_of(s)) >= IDLE_W
    return True
def active_stats():
    out = [s for s in STATS if s['kind'] != 'battery' and is_active(s)]
    bats = [s for s in STATS if s['kind'] == 'battery' and is_active(s)]
    if bats:
        out.extend(bats)
    else:
        out.append(BATSUM)
    return out

# ---- HA polling -------------------------------------------------------------
def poll():
    for sid in ENTITIES:
        try:
            r = requests.get(BASE + '/api/states/' + ENTITIES[sid], headers=HEADERS)
            d = r.json(); r.close()
            VALUES[sid] = float(d['state'])
        except Exception:
            pass
    gc.collect()

# ---- input ------------------------------------------------------------------
state = {'nav': 0, 'exit': False, 'paused': False,
         'bright': int(CFG.get('brightness', 10))}      # 1..30
def cb_left(d):
    if d:
        state['nav'] = -1
        state['paused'] = True          # manual step latches auto-rotate off
def cb_right(d):
    if d:
        state['nav'] = 1
        state['paused'] = True
def cb_up(d):
    if d:
        state['bright'] = min(30, state['bright'] + 2)
def cb_down(d):
    if d:
        state['bright'] = max(1, state['bright'] - 2)
def cb_a(d):
    if d:
        state['paused'] = not state['paused']   # toggle auto-rotate
def cb_b(d):
    if d:
        state['exit'] = True
if ON_BADGE:
    buttons.register(defines.BTN_LEFT, cb_left)
    buttons.register(defines.BTN_RIGHT, cb_right)
    buttons.register(defines.BTN_UP, cb_up)
    buttons.register(defines.BTN_DOWN, cb_down)
    buttons.register(defines.BTN_A, cb_a)
    buttons.register(defines.BTN_B, cb_b)

def render(s):
    fb_clear()
    draw_stat(s)
    fb_blit()

def is_overflow(s):                       # does this stat blink (value over its max)?
    k = s['kind']
    if k == 'grid':
        v = value_of(s)
        return abs(v) > (s['maxNeg'] if v < 0 else s['maxPos'])
    if k == 'use' or k == 'self' or k == 'power':
        return abs(value_of(s)) > s['max']
    return False

# ---- main -------------------------------------------------------------------
class Display:
    """One screen-tick = five small phases. main() just calls step() in a loop."""
    def __init__(self):
        self.car = Carousel(active_stats())
        self.bright = state['bright']
        self.last_poll = self.last_adv = self.touched = time.ticks_ms()
        self.dirty = True            # something to (re)draw this tick
        self.prev_blink = False
        self.overflow = False

    def _brightness(self, now):      # UP/DOWN — applies live, no redraw needed
        if state['bright'] != self.bright:
            self.bright = state['bright']
            rgb.brightness(self.bright)
            self.touched = now

    def _poll(self, now):            # refresh HA readings on the poll interval
        if wifi.status() and time.ticks_diff(now, self.last_poll) >= POLL_MS:
            poll()
            self.last_poll = now
            self.car.refresh(active_stats())   # the active set can change with new data
            self.dirty = True

    def _select(self, now):          # which stat to show (LEFT/RIGHT or auto-advance)
        if state['nav']:
            self.car.step(state['nav']); state['nav'] = 0
            self.last_adv = self.touched = now
            self.dirty = True
        elif not state['paused'] and time.ticks_diff(now, self.last_adv) >= ADV_MS:
            self.car.step(1); self.last_adv = now
            self.dirty = True

    def _draw(self, now):            # redraw only when the picture changes
        global blink_on
        cur = self.car.current()
        self.overflow = is_overflow(cur)
        blink_on = (now // 450) % 2 == 0
        if self.overflow and blink_on != self.prev_blink:
            self.dirty = True        # animate the overflow blink
        self.prev_blink = blink_on
        if self.dirty:
            try:
                render(cur)
            except Exception as e:
                sys.print_exception(e)
            self.dirty = False

    def _idle_ms(self, now):         # snappy after a press, quicker while blinking
        if time.ticks_diff(now, self.touched) < 1200:
            return 50
        return 120 if self.overflow else 220

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
