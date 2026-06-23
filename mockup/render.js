// render.js — shared rendering of a stat onto a Matrix framebuffer. Used by both
// the interactive controller (sim.js) and the contact-sheet gallery.
(function (global) {
  const C = global.EnergyConfig;
  const PF = global.PixelFont;
  // Shared blink phase (toggled by the controller); gallery leaves it on.
  const Blink = global.Blink || (global.Blink = { on: true });

  // All gauges are anchored at the far left; sign/direction is shown by colour
  // and the ± in the value. Above the rated max the whole bar blinks red.
  function gauge(matrix, b, s, v, col) {
    // signed stats may have an asymmetric max (e.g. GRID: export 6kW / import 17.25kW)
    const max = s.kind === 'grid' ? (v < 0 ? s.maxNeg : s.maxPos) : s.max;
    const frac = s.kind === 'soc' ? v / 100 : Math.abs(v) / max;
    if (frac > 1) {
      if (Blink.on) matrix.barLeft(b, 7, 1, C.COLORS.alert);   // blinking-red overflow
    } else if (C.isSigned(s) && v < 0) {
      matrix.barRight(b, 7, frac, col);                        // discharge/export → from right
    } else {
      matrix.barLeft(b, 7, frac, col);                         // charge/import & unidir → from left
    }
  }

  // Draw one stat. big => gauge styling (icon lowered + scaled bar at row 7).
  function drawStat(matrix, b, s, big) {
    const v = C.value(s), col = C.colorOf(s, v);
    const y = big ? 0 : 1;                          // gauge: top (bar on row 7); else centred
    matrix.icon(b, 0, y, s.icon, col);             // icon: 8x5, cols 0-7
    PF.drawText(b, 9, y, C.fmt(s, v), col);         // value aligned to the icon
    if (big) gauge(matrix, b, s, v, col);          // gauge bar: very bottom row 7
  }

  function renderInto(matrix, s, big) {
    const b = global.Matrix.blank();
    drawStat(matrix, b, s, big);
    matrix.paint(b);
  }

  function tickerSegment(s) { return s.label + ' ' + C.fmt(s, C.value(s)); }

  global.EnergyRender = { gauge, drawStat, renderInto, tickerSegment };
})(window);
