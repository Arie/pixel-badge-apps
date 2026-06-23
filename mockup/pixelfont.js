// pixelfont.js — a 3x5 pixel font and text helpers for the 32x8 matrix.
// Mirrors the spirit of the badge's small font; the on-device app uses the
// firmware's rgb.text(), this is only for the browser mockup.
(function (global) {
  const F = {
    '0':["###","# #","# #","# #","###"],'1':[" # ","## "," # "," # ","###"],
    '2':["###","  #","###","#  ","###"],'3':["###","  #","###","  #","###"],
    '4':["# #","# #","###","  #","  #"],'5':["###","#  ","###","  #","###"],
    '6':["###","#  ","###","# #","###"],'7':["###","  #","  #","  #","  #"],
    '8':["###","# #","###","# #","###"],'9':["###","# #","###","  #","###"],
    'A':["###","# #","###","# #","# #"],'B':["## ","# #","## ","# #","## "],
    'C':["###","#  ","#  ","#  ","###"],'D':["## ","# #","# #","# #","## "],
    'E':["###","#  ","###","#  ","###"],'F':["###","#  ","###","#  ","#  "],
    'G':["###","#  ","# #","# #","###"],'H':["# #","# #","###","# #","# #"],
    'I':["###"," # "," # "," # ","###"],'J':["  #","  #","  #","# #","###"],
    'K':["# #","# #","## ","# #","# #"],'L':["#  ","#  ","#  ","#  ","###"],
    'M':["# #","###","###","# #","# #"],'N':["# #","###","###","###","# #"],
    'O':["###","# #","# #","# #","###"],'P':["###","# #","###","#  ","#  "],
    'R':["## ","# #","## ","# #","# #"],'S':["###","#  ","###","  #","###"],
    'T':["###"," # "," # "," # "," # "],'U':["# #","# #","# #","# #","###"],
    'V':["# #","# #","# #","# #"," # "],'W':["# #","# #","###","###","# #"],
    'Y':["# #","# #"," # "," # "," # "],'Z':["###","  #"," # ","#  ","###"],
    '.':["   ","   ","   ","   "," # "],'-':["   ","   ","###","   ","   "],
    '+':["   "," # ","###"," # ","   "],'%':["#  ","  #"," # ","#  ","  #"],
    ':':["   "," # ","   "," # ","   "],' ':["   ","   ","   ","   ","   "]
  };
  const CHAR_W = 3, CHAR_H = 5, GAP = 1;

  // Proportional: trim each glyph to its lit columns so thin chars (.,:) close up.
  function inkBounds(g) {
    let lo = CHAR_W, hi = -1;
    for (let r = 0; r < CHAR_H; r++)
      for (let c = 0; c < CHAR_W; c++)
        if (g[r][c] === '#') { if (c < lo) lo = c; if (c > hi) hi = c; }
    if (hi < 0) return { lo: 0, hi: -1, w: 2 };   // space → 2px blank
    return { lo: lo, hi: hi, w: hi - lo + 1 };
  }
  // Draw text into buf (8 rows x 32 cols of color-or-null). Returns next x.
  function drawText(buf, x, y, txt, color) {
    let cx = x;
    for (const ch of String(txt).toUpperCase()) {
      const g = F[ch] || F[' '];
      const b = inkBounds(g);
      for (let r = 0; r < CHAR_H; r++)
        for (let c = b.lo; c <= b.hi; c++)
          if (g[r][c] === '#') setPixel(buf, cx + (c - b.lo), y + r, color);
      cx += b.w + GAP;
    }
    return cx;
  }
  function textWidth(txt) {
    let w = 0;
    for (const ch of String(txt).toUpperCase()) w += inkBounds(F[ch] || F[' ']).w + GAP;
    return w - GAP;
  }
  function setPixel(buf, x, y, color) {
    if (x >= 0 && x < 32 && y >= 0 && y < 8) buf[y][x] = color;
  }

  global.PixelFont = { drawText, textWidth, setPixel, CHAR_W, CHAR_H, GAP };
})(window);
