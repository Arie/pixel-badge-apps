// matrix.js — a 32x8 LED-matrix surface rendered as a DOM grid, plus icons.
(function (global) {
  const W = 32, H = 8, OFF = '#141414';

  // Icons are 8 wide x 5 tall — the same height as the 3x5 value font, drawn on
  // rows 1-5 beside the value. Row 7 is left for the gauge bar.
  const ICONS = {
    SUN:  [" # ## # ","  ####  ","########","  ####  "," # ## # "],
    HOME: ["   ##   ","  ####  "," ###### "," #    # "," # ## # "],
    SELF: ["   ##   ","  ####  "," ###### "," ###### "," ###### "],
    GRID: ["   ##   "," ###### ","   ##   "," ###### ","   ##   "],
    BATT: ["#####   ","#   #   ","#   ##  ","#   #   ","#####   "],
    BOLT: ["    ### ","   ##   ","  ####  ","    ##  ","  ##    "],

    // ---- alternatives for comparison ----
    GRID_TOWER: ["   ##   "," ###### ","  #  #  "," ###### ","#      #"],
    SELF_CORE:  ["   ##   ","  ####  "," ###### "," # ## # "," #    # "],
    SELF_LOOP:  ["  ####  "," #    # "," #    # "," #    # ","  ####  "],
    SELF_IN:    ["   ##   ","########"," #    # "," #    # "," #    # "]
  };

  class Matrix {
    constructor(el) {
      this.el = el;
      el.style.display = 'grid';
      el.style.gridTemplateColumns = `repeat(${W},1fr)`;
      el.style.gridTemplateRows = `repeat(${H},1fr)`;
      el.style.gap = '2px';                 // dark space between LEDs (real panel)
      el.style.background = '#050505';
      el.style.padding = '6px';
      el.style.borderRadius = '6px';
      this.cells = [];
      for (let i = 0; i < W * H; i++) {
        const d = document.createElement('div');
        d.className = 'cell';
        el.appendChild(d);
        this.cells.push(d);
      }
    }
    static blank() { return Array.from({ length: H }, () => Array(W).fill(null)); }

    icon(buf, x, y, name, color) {
      const rows = ICONS[name];
      if (!rows) return;
      for (let r = 0; r < rows.length; r++)
        for (let c = 0; c < rows[r].length; c++)
          if (rows[r][c] === '#') window.PixelFont.setPixel(buf, x + c, y + r, color);
    }
    bar(buf, x, y, len, color) {
      for (let i = 0; i < len; i++) window.PixelFont.setPixel(buf, x + i, y, color);
    }
    // Full-width bar (all 32 columns) anchored at the LEFT edge (x0), growing right.
    barLeft(buf, y, frac, color) {
      const n = Math.min(W, Math.round(Math.min(1, frac) * W));
      for (let i = 0; i < n; i++) window.PixelFont.setPixel(buf, i, y, color);
    }
    // Full-width bar anchored at the RIGHT edge (x31), growing left. Used for
    // negative (discharge/export) values so the anchor side encodes direction.
    barRight(buf, y, frac, color) {
      const n = Math.min(W, Math.round(Math.min(1, frac) * W));
      for (let i = 0; i < n; i++) window.PixelFont.setPixel(buf, W - 1 - i, y, color);
    }
    paint(buf) {
      for (let y = 0; y < H; y++)
        for (let x = 0; x < W; x++)
          this.cells[y * W + x].style.background = buf[y][x] || OFF;
    }
  }

  global.Matrix = Matrix;
  global.MATRIX_W = W;
  global.MATRIX_H = H;
})(window);
