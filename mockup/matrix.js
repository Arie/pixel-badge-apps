// matrix.js — a 32x8 LED-matrix surface rendered as a DOM grid, plus icons.
(function (global) {
  const W = 32, H = 8, OFF = '#141414';

  const ICONS = {
    SUN:  ["   #    ","#  #  # "," #   #  ","  ###   ","### ####","  ###   "," #   #  ","#  #  # "],
    HOME: ["   #    ","  ###   "," ##### #","#######.","# ### # ","# ### # ","# ### # ","        "],
    BATT: ["        "," ###### ","##    ##","##    ##","##    ##"," ###### ","        ","        "],
    GRID: ["  ###   "," #   #  ","  ###   ","   #    ","  # #   "," #   #  ","#     # ","        "],
    SELF: ["   #    ","  ###   "," # # #  ","#######.","#  #  # ","#  #  # ","#######.","        "]
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
