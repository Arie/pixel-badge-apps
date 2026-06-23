// matrix.js — a 32x8 LED-matrix surface rendered as a DOM grid, plus icons.
(function (global) {
  const W = 32, H = 8, OFF = '#141414';

  // Icons are 8 wide x 7 tall: row 7 is ALWAYS blank so the gauge bar owns it.
  const ICONS = {
    SUN:  ["   ##   ","#  ##  #"," ###### ","########"," ###### ","#  ##  #","   ##   ","        "],
    HOME: ["   ##   ","  ####  "," ###### ","########"," #    # "," #  # # "," #  # # ","        "],
    SELF: ["   ##   ","  ####  "," ###### ","########"," ###### "," ###### "," ###### ","        "],
    GRID: ["   ##   ","  ####  "," ###### ","   ##   "," ###### ","  ####  ","   ##   ","        "],
    BATT: ["        ","######  ","#    #  ","#    ###","#    ###","#    #  ","######  ","        "],
    BOLT: ["    ##  ","   ##   ","  ###   "," #####  ","   ##   ","  ##    "," #      ","        "]
  };

  class Matrix {
    constructor(el) {
      this.el = el;
      el.style.display = 'grid';
      el.style.gridTemplateColumns = `repeat(${W},1fr)`;
      el.style.gridTemplateRows = `repeat(${H},1fr)`;
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
    // Unidirectional bar from the left; fills `frac` (0..1) of the 30px track.
    // Returns true if frac>1 (overflow).
    barLeft(buf, y, frac, color) {
      const n = Math.min(30, Math.round(frac * 30));
      for (let i = 0; i < n; i++) window.PixelFont.setPixel(buf, 1 + i, y, color);
      return frac > 1;
    }
    // Bidirectional bar growing from the centre. dir>0 to the right, dir<0 left.
    barCenter(buf, y, frac, dir, color) {
      const n = Math.round(Math.min(1, frac) * 15);
      window.PixelFont.setPixel(buf, dir >= 0 ? 16 : 15, y, color); // centre seed
      for (let i = 1; i <= n; i++)
        window.PixelFont.setPixel(buf, dir >= 0 ? 16 + i : 15 - i, y, color);
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
