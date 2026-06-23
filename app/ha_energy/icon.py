# 8x8 launcher icon: a green energy bolt on black. Format: ([64x 0xRRGGBBAA], frames)
_b = ["   ##   ",
      "  ##    ",
      " #####  ",
      "   ##   ",
      "  ##    ",
      " ##     ",
      "        ",
      "        "]
_FG = 0x33d96fff   # green
_BG = 0x000000ff   # black
icon = ([_FG if _b[y][x] == '#' else _BG for y in range(8) for x in range(8)], 1)
