# 3x5 proportional font: '#' = lit, '.' = off (parsed at load).
from pixelbadge.matrix import px


def _glyph(a):
    return a.strip("\n").split("\n")


# 3x5 font
FONT = {
    ch: _glyph(a)
    for ch, a in {
        "0": """
###
#.#
#.#
#.#
###""",
        "1": """
.#.
##.
.#.
.#.
###""",
        "2": """
###
..#
###
#..
###""",
        "3": """
###
..#
###
..#
###""",
        "4": """
#.#
#.#
###
..#
..#""",
        "5": """
###
#..
###
..#
###""",
        "6": """
###
#..
###
#.#
###""",
        "7": """
###
..#
..#
..#
..#""",
        "8": """
###
#.#
###
#.#
###""",
        "9": """
###
#.#
###
..#
###""",
        "A": """
###
#.#
###
#.#
#.#""",
        "B": """
##.
#.#
##.
#.#
##.""",
        "C": """
###
#..
#..
#..
###""",
        "D": """
##.
#.#
#.#
#.#
##.""",
        "E": """
###
#..
###
#..
###""",
        "F": """
###
#..
###
#..
#..""",
        "G": """
###
#..
#.#
#.#
###""",
        "H": """
#.#
#.#
###
#.#
#.#""",
        "I": """
###
.#.
.#.
.#.
###""",
        "K": """
#.#
#.#
##.
#.#
#.#""",
        "L": """
#..
#..
#..
#..
###""",
        "N": """
#.#
###
###
###
#.#""",
        "O": """
###
#.#
#.#
#.#
###""",
        "P": """
###
#.#
###
#..
#..""",
        "R": """
##.
#.#
##.
#.#
#.#""",
        "S": """
###
#..
###
..#
###""",
        "T": """
###
.#.
.#.
.#.
.#.""",
        "U": """
#.#
#.#
#.#
#.#
###""",
        "W": """
#.#
#.#
###
###
#.#""",
        "Z": """
###
..#
.#.
#..
###""",
        ".": """
...
...
...
...
#..""",
        "-": """
...
...
###
...
...""",
        "+": """
...
.#.
###
.#.
...""",
        "%": """
#..
..#
.#.
#..
..#""",
        " ": """
...
...
...
...
...""",
    }.items()
}


def ink_bounds(g):
    lo, hi = 3, -1
    for r in range(5):
        row = g[r]
        for c in range(3):
            if row[c] == "#":
                if c < lo:
                    lo = c
                if c > hi:
                    hi = c
    if hi < 0:
        return (0, -1, 2)  # space -> 2px
    return (lo, hi, hi - lo + 1)


def draw_text(x, y, s, color):
    cx = x
    for ch in str(s).upper():
        g = FONT.get(ch, FONT[" "])
        lo, hi, w = ink_bounds(g)
        for r in range(5):
            row = g[r]
            c = lo
            while c <= hi:
                if row[c] == "#":
                    px(cx + (c - lo), y + r, color)
                c += 1
        cx += w + 1
    return cx


def text_width(s):
    w = 0
    for ch in str(s).upper():
        w += ink_bounds(FONT.get(ch, FONT[" "]))[2] + 1
    return w - 1


def draw_icon(x, y, rows, color):
    if not rows:
        return
    for r in range(len(rows)):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == "#":
                px(x + c, y + r, color)
