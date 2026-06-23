# HA Energy — Home Assistant energy display for the CampZone 2019 "Pixel" badge.
# Shows power flows and home-battery SOC/power on the 32x8 LED matrix.
# See docs/2026-06-23-ha-energy-app-design.md for the full design.

import time, ujson as json, gc
import rgb, hub75, wifi, buttons, defines, system
import urequests as requests

W, H = 32, 8

# ---- config (token + entity map; gitignored) --------------------------------
with open('apps/ha_energy/config.json') as f:
    CFG = json.load(f)
BASE = CFG['base_url']
POLL_MS = int(CFG.get('poll_seconds', 10)) * 1000
ENTITIES = CFG['entities']                       # id -> HA entity_id
HEADERS = {'Authorization': 'Bearer ' + CFG['token']}

# ---- colours (HomeWizard-inspired, brightened) ------------------------------
PURPLE = (0x7b, 0x3f, 0xf2)   # consumption / import / battery charging
GREEN  = (0x33, 0xd9, 0x6f)   # solar / export / battery discharging
LBLUE  = (0x4f, 0xc3, 0xff)   # self-use
AMBER  = (0xff, 0x9d, 0x3a)   # SOC mid
RED    = (0xff, 0x4d, 0x4d)   # SOC low
ALERT  = (0xff, 0x2a, 0x2a)   # overflow (blinking)

# ---- 3x5 font ---------------------------------------------------------------
FONT = {
 '0':["###","# #","# #","# #","###"],'1':[" # ","## "," # "," # ","###"],
 '2':["###","  #","###","#  ","###"],'3':["###","  #","###","  #","###"],
 '4':["# #","# #","###","  #","  #"],'5':["###","#  ","###","  #","###"],
 '6':["###","#  ","###","# #","###"],'7':["###","  #","  #","  #","  #"],
 '8':["###","# #","###","# #","###"],'9':["###","# #","###","  #","###"],
 'A':["###","# #","###","# #","# #"],'B':["## ","# #","## ","# #","## "],
 'C':["###","#  ","#  ","#  ","###"],'D':["## ","# #","# #","# #","## "],
 'E':["###","#  ","###","#  ","###"],'F':["###","#  ","###","#  ","#  "],
 'G':["###","#  ","# #","# #","###"],'H':["# #","# #","###","# #","# #"],
 'I':["###"," # "," # "," # ","###"],'K':["# #","# #","## ","# #","# #"],
 'L':["#  ","#  ","#  ","#  ","###"],'N':["# #","###","###","###","# #"],
 'O':["###","# #","# #","# #","###"],'P':["###","# #","###","#  ","#  "],
 'R':["## ","# #","## ","# #","# #"],'S':["###","#  ","###","  #","###"],
 'T':["###"," # "," # "," # "," # "],'U':["# #","# #","# #","# #","###"],
 'W':["# #","# #","###","###","# #"],'Z':["###","  #"," # ","#  ","###"],
 '.':["   ","   ","   ","   "," # "],'-':["   ","   ","###","   ","   "],
 '+':["   "," # ","###"," # ","   "],'%':["#  ","  #"," # ","#  ","  #"],
 ' ':["   ","   ","   ","   ","   "],
}

# ---- 8x5 icons --------------------------------------------------------------
ICONS = {
 'SUN':  [" # ## # ","  ####  ","########","  ####  "," # ## # "],
 'HOME': ["   ##   ","  ####  "," ###### "," #    # "," # ## # "],
 'SELF': ["   ##   ","  ####  "," ###### "," ###### "," ###### "],
 'GRID': ["   ##   "," ###### ","  #  #  "," ###### ","#      #"],
 'BATT': ["#####   ","#   #   ","#   ##  ","#   #   ","#####   "],
 'BOLT': ["   ###  ","  ##    "," #####  ","    ##  ","   ##   "],
}

# ---- stats (single source of truth; entities come from config) --------------
STATS = [
 {'id':'USE', 'label':'USE', 'icon':'HOME','kind':'use',     'color':PURPLE,'max':17250},
 {'id':'SOL', 'label':'SOL', 'icon':'SUN', 'kind':'power',   'color':GREEN, 'max':6000},
 {'id':'SELF','label':'SELF','icon':'SELF','kind':'self',    'color':LBLUE, 'max':6000},
 {'id':'GRID','label':'GRID','icon':'GRID','kind':'grid',    'maxPos':17250,'maxNeg':6000},
 {'id':'HW1', 'label':'HW1', 'icon':'BATT','kind':'soc'},
 {'id':'HW1P','label':'HW1', 'icon':'BOLT','kind':'batpower','max':800},
 {'id':'HW2', 'label':'HW2', 'icon':'BATT','kind':'soc'},
 {'id':'HW2P','label':'HW2', 'icon':'BOLT','kind':'batpower','max':800},
 {'id':'ZEN', 'label':'ZEN', 'icon':'BATT','kind':'soc'},
 {'id':'ZENP','label':'ZEN', 'icon':'BOLT','kind':'batpower','max':2400},
]

VALUES = {}     # id -> float (raw HA readings)

# ---- framebuffer ------------------------------------------------------------
fb = [0] * (W * H)
def fb_clear():
    for i in range(W * H):
        fb[i] = 0
def px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        r, g, b = color
        fb[y * W + x] = (r << 24) | (g << 16) | (b << 8) | 255
def fb_blit():
    rgb.clear()
    hub75.image(fb, 0, 0, W, H)

def draw_text(x, y, s, color):
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[' '])
        for r in range(5):
            row = g[r]
            for c in range(3):
                if row[c] == '#':
                    px(cx + c, y + r, color)
        cx += 4
    return cx
def text_w(s):
    return len(s) * 4 - 1
def draw_icon(x, y, name, color):
    rows = ICONS.get(name)
    if not rows:
        return
    for r in range(len(rows)):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == '#':
                px(x + c, y + r, color)
def bar_left(y, frac, color):
    n = int(min(1.0, frac) * W + 0.5)
    for i in range(n):
        px(i, y, color)
def bar_right(y, frac, color):
    n = int(min(1.0, frac) * W + 0.5)
    for i in range(n):
        px(W - 1 - i, y, color)

# ---- values, derivation, colour, formatting ---------------------------------
def value_of(s):
    k = s['kind']
    if k == 'use':
        return (VALUES.get('SOL', 0) + VALUES.get('GRID', 0) +
                VALUES.get('HW1P', 0) + VALUES.get('HW2P', 0) + VALUES.get('ZENP', 0))
    if k == 'self':
        g = VALUES.get('GRID', 0)
        return VALUES.get('SOL', 0) - (-g if g < 0 else 0)
    return VALUES.get(s['id'], 0)

def is_signed(s):
    return s['kind'] in ('grid', 'batpower')

def color_of(s, v):
    k = s['kind']
    if k == 'grid':
        return GREEN if v < 0 else PURPLE
    if k == 'soc':
        return GREEN if v >= 50 else (AMBER if v >= 20 else RED)
    if k == 'batpower':
        return PURPLE if v >= 0 else GREEN
    return s['color']

def fmt(s, v):
    if s['kind'] == 'soc':
        return str(int(round(v))) + '%'
    a = abs(v)
    sign = ('-' if v < 0 else '+') if is_signed(s) else ''
    if a < 1000:
        return sign + str(int(round(a))) + 'W'
    k = a / 1000.0
    if k >= 10:
        return sign + str(int(round(k))) + 'KW'
    return sign + ('%.1f' % k) + 'KW'

blink_on = True
def gauge(s, v, col):
    k = s['kind']
    if k == 'grid':
        mx = s['maxNeg'] if v < 0 else s['maxPos']
    else:
        mx = s['max']
    frac = (v / 100.0) if k == 'soc' else (abs(v) / mx)
    if frac > 1:
        if blink_on:
            bar_left(7, 1.0, ALERT)
    elif is_signed(s) and v < 0:
        bar_right(7, frac, col)
    else:
        bar_left(7, frac, col)

def draw_stat(s, big):
    v = value_of(s)
    col = color_of(s, v)
    y = 0 if big else 1
    draw_icon(0, y, s['icon'], col)
    draw_text(9, y, fmt(s, v), col)
    if big:
        gauge(s, v, col)

def ticker_seg(s):
    return s['label'] + ' ' + fmt(s, value_of(s))

# ---- HA polling -------------------------------------------------------------
def poll():
    for sid, ent in ENTITIES.items():
        try:
            r = requests.get(BASE + '/api/states/' + ent, headers=HEADERS)
            d = r.json()
            r.close()
            st = d['state']
            VALUES[sid] = float(st)
        except Exception:
            pass        # keep last-known value on any error
    gc.collect()

# ---- controller -------------------------------------------------------------
MODES = ['Rotate', 'Ticker', 'Gauge']
state = {'mode': 0, 'stat': 0, 'exit': False, 'dirty': True}

def cb_up(d):
    if d: state['mode'] = (state['mode'] - 1) % len(MODES); state['dirty'] = True
def cb_down(d):
    if d: state['mode'] = (state['mode'] + 1) % len(MODES); state['dirty'] = True
def cb_left(d):
    if d: state['stat'] = (state['stat'] - 1) % len(STATS); state['dirty'] = True
def cb_right(d):
    if d: state['stat'] = (state['stat'] + 1) % len(STATS); state['dirty'] = True
def cb_b(d):
    if d: state['exit'] = True

buttons.register(defines.BTN_UP, cb_up)
buttons.register(defines.BTN_DOWN, cb_down)
buttons.register(defines.BTN_LEFT, cb_left)
buttons.register(defines.BTN_RIGHT, cb_right)
buttons.register(defines.BTN_B, cb_b)

def render():
    fb_clear()
    if MODES[state['mode']] == 'Ticker':
        x = state['tick']
        for s in STATS:
            v = value_of(s)
            x = draw_text(x, 1, ticker_seg(s), color_of(s, v)) + 6
    else:
        draw_stat(STATS[state['stat']], MODES[state['mode']] == 'Gauge')
    fb_blit()

# ---- main -------------------------------------------------------------------
def main():
    global blink_on
    rgb.background((0, 0, 0))
    rgb.brightness(int(CFG.get('brightness', 10)))

    # WiFi
    if not wifi.status():
        wifi.connect()
        wifi.wait()
    if wifi.status():
        poll()

    state['tick'] = W
    last_poll = time.ticks_ms()
    last_rot = time.ticks_ms()
    total = 0
    for s in STATS:
        total += text_w(ticker_seg(s)) + 6

    while not state['exit']:
        now = time.ticks_ms()
        if wifi.status() and time.ticks_diff(now, last_poll) >= POLL_MS:
            poll()
            last_poll = now
            state['dirty'] = True
            total = 0
            for s in STATS:
                total += text_w(ticker_seg(s)) + 6

        prev_blink = blink_on
        blink_on = (time.ticks_ms() // 450) % 2 == 0

        mode = MODES[state['mode']]
        if mode == 'Rotate' and time.ticks_diff(now, last_rot) >= 2500:
            state['stat'] = (state['stat'] + 1) % len(STATS)
            last_rot = now
            state['dirty'] = True
        if mode == 'Ticker':
            state['tick'] -= 1
            if state['tick'] < -total:
                state['tick'] = W
            render()
        elif state['dirty'] or prev_blink != blink_on:
            render()
            state['dirty'] = False

        time.sleep_ms(60)

    rgb.clear()
    system.home()

main()
