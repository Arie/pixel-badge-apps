// render.js — shared rendering of a stat onto a Matrix framebuffer. Used by both
// the interactive controller (sim.js) and the contact-sheet gallery.
(function (global) {
  const C = global.EnergyConfig;
  const PF = global.PixelFont;

  function gauge(matrix, b, s, v, col) {
    if (C.isBidir(s)) {
      matrix.barCenter(b, 7, Math.abs(v) / s.max, v >= 0 ? 1 : -1, col);
    } else {
      const frac = s.kind === 'soc' ? v / 100 : v / s.max;
      if (matrix.barLeft(b, 7, frac, col)) {           // overflow above rated max
        PF.setPixel(b, 30, 7, C.COLORS.overflow);
        PF.setPixel(b, 31, 7, C.COLORS.overflow);
      }
    }
  }

  // Draw one stat. big => gauge styling (icon lowered + scaled bar at row 7).
  function drawStat(matrix, b, s, big) {
    const v = C.value(s), col = C.colorOf(s, v);
    matrix.icon(b, 0, 0, s.icon, col);             // icons are 7px tall; row 7 free
    PF.drawText(b, 10, 1, C.fmt(s, v), col);        // text rows 1-5, centred on the icon

    if (big) gauge(matrix, b, s, v, col);          // bar lives on row 7
  }

  function renderInto(matrix, s, big) {
    const b = global.Matrix.blank();
    drawStat(matrix, b, s, big);
    matrix.paint(b);
  }

  function tickerSegment(s) { return s.label + ' ' + C.fmt(s, C.value(s)); }

  global.EnergyRender = { gauge, drawStat, renderInto, tickerSegment };
})(window);
