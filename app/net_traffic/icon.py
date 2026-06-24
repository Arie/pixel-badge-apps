# 8x8 launcher icon: a green download arrow on black.
_b = ["   ##   ",
      "   ##   ",
      " ###### ",
      "  ####  ",
      "   ##   ",
      "        ",
      "        ",
      "        "]
_FG = 0x2ed640ff   # green
_BG = 0x000000ff   # black
icon = ([_FG if _b[y][x] == '#' else _BG for y in range(8) for x in range(8)], 1)
