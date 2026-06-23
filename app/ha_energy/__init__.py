# HA Energy — Home Assistant energy display for the CampZone 2019 "Pixel" badge.
# Single auto-advancing gauge view; LEFT/RIGHT step, B exits.
# Ported from the mockup in pixel-badge-apps/mockup. See docs/ for the design.

import sys, time, ujson as json, gc
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
IDLE_W = 10                                       # |power| below this = idle

# ---- colours (tuned on the panel) -------------------------------------------
PURPLE = (0x55, 0x18, 0xcc)   # consumption / import / battery charging
GREEN  = (0x2e, 0xd6, 0x40)   # solar / export / battery discharging
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
 '.':["   ","   ","   ","   ","#  "],'-':["   ","   ","###","   ","   "],
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

# ---- stats (entities come from config) --------------------------------------
STATS = [
 {'id':'USE', 'label':'USE', 'icon':'HOME','kind':'use',   'color':PURPLE,'max':17250},
 {'id':'SOL', 'label':'SOL', 'icon':'SUN', 'kind':'power', 'color':GREEN, 'max':6000, 'hideIdle':True},
 {'id':'SELF','label':'SELF','icon':'SELF','kind':'self',  'color':LBLUE, 'max':6000},
 {'id':'GRID','label':'GRID','icon':'GRID','kind':'grid',  'maxPos':17250,'maxNeg':6000},
 {'id':'HW1', 'label':'HW1', 'kind':'battery','socId':'HW1','powerId':'HW1P','weight':1,'socMin':0},
 {'id':'HW2', 'label':'HW2', 'kind':'battery','socId':'HW2','powerId':'HW2P','weight':1,'socMin':0},
 {'id':'ZEN', 'label':'ZEN', 'kind':'battery','socId':'ZEN','powerId':'ZENP','weight':3,'socMin':10},
]
BATSUM = {'kind':'batsummary'}
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

# ---- proportional font ------------------------------------------------------
def ink_bounds(g):
    lo, hi = 3, -1
    for r in range(5):
        row = g[r]
        for c in range(3):
            if row[c] == '#':
                if c < lo: lo = c
                if c > hi: hi = c
    if hi < 0:
        return (0, -1, 2)        # space -> 2px
    return (lo, hi, hi - lo + 1)
def draw_text(x, y, s, color):
    cx = x
    for ch in str(s).upper():
        g = FONT.get(ch, FONT[' '])
        lo, hi, w = ink_bounds(g)
        for r in range(5):
            row = g[r]
            c = lo
            while c <= hi:
                if row[c] == '#':
                    px(cx + (c - lo), y + r, color)
                c += 1
        cx += w + 1
    return cx
def text_width(s):
    w = 0
    for ch in str(s).upper():
        w += ink_bounds(FONT.get(ch, FONT[' ']))[2] + 1
    return w - 1
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

# ---- values, colours, formatting --------------------------------------------
def value_of(s):
    k = s['kind']
    if k == 'use':
        # house load = solar + grid − battery power (battery +=charge draws, −=discharge supplies)
        return (VALUES.get('SOL', 0) + VALUES.get('GRID', 0) -
                VALUES.get('HW1P', 0) - VALUES.get('HW2P', 0) - VALUES.get('ZENP', 0))
    if k == 'self':
        g = VALUES.get('GRID', 0)
        return VALUES.get('SOL', 0) - (-g if g < 0 else 0)
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
    elif is_signed(s) and v < 0:
        bar_right(7, frac, col)
    else:
        bar_left(7, frac, col)

def draw_stat(s):
    k = s['kind']
    if k == 'batsummary':
        avg = fleet_soc()
        col = soc_color(avg)
        draw_icon(0, 0, 'BATT', col)
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
    draw_icon(0, 0, s['icon'], col)
    draw_text(9, 0, fit_value(fmt(s, v), W - 9), col)
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
state = {'nav': 0, 'exit': False}
def cb_left(d):
    if d: state['nav'] = -1
def cb_right(d):
    if d: state['nav'] = 1
def cb_b(d):
    if d: state['exit'] = True
buttons.register(defines.BTN_LEFT, cb_left)
buttons.register(defines.BTN_RIGHT, cb_right)
buttons.register(defines.BTN_B, cb_b)

def render(s):
    fb_clear()
    draw_stat(s)
    fb_blit()

# ---- main -------------------------------------------------------------------
def main():
    global blink_on
    rgb.background((0, 0, 0))
    rgb.brightness(int(CFG.get('brightness', 10)))
    if not wifi.status():
        wifi.connect(); wifi.wait()
    if wifi.status():
        poll()
    idx = 0
    last_poll = time.ticks_ms()
    last_adv = time.ticks_ms()
    paused_until = time.ticks_ms()
    while not state['exit']:
        now = time.ticks_ms()
        if wifi.status() and time.ticks_diff(now, last_poll) >= POLL_MS:
            poll(); last_poll = now
        active = active_stats()
        n = len(active)
        if state['nav'] != 0:
            idx = (idx + state['nav']) % n
            state['nav'] = 0
            paused_until = time.ticks_add(now, 6000)
            last_adv = now
        elif time.ticks_diff(now, last_adv) >= 2500 and time.ticks_diff(now, paused_until) >= 0:
            idx = (idx + 1) % n
            last_adv = now
        if idx >= n:
            idx = 0
        blink_on = (time.ticks_ms() // 450) % 2 == 0
        try:
            render(active[idx])
        except Exception as e:
            sys.print_exception(e)
        time.sleep_ms(66)
    rgb.clear()
    system.home()

main()
