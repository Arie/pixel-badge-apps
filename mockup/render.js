// render.js — shared rendering of a stat onto a Matrix framebuffer. Single
// "gauge" view: icon/label + value on rows 0-4, a bar on row 7.
(function (global) {
  const C = global.EnergyConfig;
  const PF = global.PixelFont;
  const Blink = global.Blink || (global.Blink = { on: true });

  // Flow-stat gauge bar: anchored by sign, scaled to the stat max, blinks red over max.
  function gauge(matrix, b, s, v, col) {
    const max = s.kind === 'grid' ? (v < 0 ? s.maxNeg : s.maxPos) : s.max;
    const frac = Math.abs(v) / max;
    if (frac > 1) {
      if (Blink.on) matrix.barLeft(b, 7, 1, C.COLORS.alert);   // overflow → blinking red
    } else if (C.isSigned(s) && v < 0) {
      matrix.barRight(b, 7, frac, col);                        // export → from right
    } else {
      matrix.barLeft(b, 7, frac, col);                         // consume/import & unidir → from left
    }
  }

  function drawStat(matrix, b, s) {
    if (s.kind === 'batsummary') {
      // all batteries idle → one screen: icon + 0W + fleet-SOC gauge (weighted avg)
      const avg = (s.avg !== undefined) ? s.avg : C.fleetSoc();
      const col = C.socColor(avg);
      matrix.icon(b, 0, 0, 'BATT', col);
      PF.drawText(b, 9, 0, '0W', col);
      matrix.barLeft(b, 7, avg / 100, col);
      return;
    }
    if (s.kind === 'battery') {
      // identifier + signed power number (colour = charge/discharge); usable SOC as the bar.
      // 2px gap (not a full 4px space char) so "HW1 +250W" fits in 32px.
      const pw = s.samplePower, pc = C.powerColor(pw);   // charge=purple, discharge=green
      PF.drawText(b, 0, 0, s.label, pc);
      PF.drawText(b, PF.textWidth(s.label) + 2, 0, C.fmtBat(pw), pc);
      matrix.barLeft(b, 7, C.displaySoc(s) / 100, pc);   // usable SOC (ZEN floored at 10%)
      return;
    }
    const v = C.value(s), col = C.colorOf(s, v);
    matrix.icon(b, 0, 0, s.icon, col);
    PF.drawText(b, 9, 0, C.fmt(s, v), col);
    gauge(matrix, b, s, v, col);
  }

  function renderInto(matrix, s) {
    const b = global.Matrix.blank();
    drawStat(matrix, b, s);
    matrix.paint(b);
  }

  global.EnergyRender = { gauge, drawStat, renderInto };
})(window);
