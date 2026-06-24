// render.js — shared rendering of a stat onto a Matrix framebuffer. Single
// "gauge" view: icon/label + value on rows 0-4, a bar on row 7.
(function (global) {
  const C = global.EnergyConfig;
  const PF = global.PixelFont;
  const Blink = global.Blink || (global.Blink = { on: true });

  // Shrink a value to fit `avail` px: drop the 'W' from KW, then a decimal.
  function fitValue(txt, avail) {
    if (PF.textWidth(txt) <= avail) return txt;
    txt = txt.replace('KW', 'K');
    if (PF.textWidth(txt) <= avail) return txt;
    return txt.replace(/(\.\d)\d/, '$1');           // 2.40K -> 2.4K
  }

  // Flow-stat gauge bar: always grows from the left, scaled to the stat max;
  // colour shows the sign (green export / purple import). Blinks red over max.
  function gauge(matrix, b, s, v, col) {
    const max = s.kind === 'grid' ? (v < 0 ? s.maxNeg : s.maxPos) : s.max;
    const frac = Math.abs(v) / max;
    if (frac > 1) {
      if (Blink.on) matrix.barLeft(b, 7, 1, C.COLORS.alert);   // overflow → blinking red
    } else {
      matrix.barLeft(b, 7, frac, col);
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
      const lx = PF.textWidth(s.label) + 2;
      PF.drawText(b, lx, 0, fitValue(C.fmtBat(pw), 32 - lx), pc);
      matrix.barLeft(b, 7, C.displaySoc(s) / 100, pc);   // usable SOC (ZEN floored at 10%)
      return;
    }
    const v = C.value(s), col = C.colorOf(s, v);
    matrix.icon(b, 0, 0, s.icon, col);
    PF.drawText(b, 9, 0, fitValue(C.fmt(s, v), 32 - 9), col);
    if (s.kind === 'use') useBar(matrix, b, v, C.solarW());  // green self / purple import / amber export
    else gauge(matrix, b, s, v, col);
  }

  // USE bar: 6kW full-scale, split green (solar→home) / purple (grid→home) / amber (export).
  function useBar(matrix, b, usage, solar) {
    if (usage > 17250) { if (Blink.on) matrix.barLeft(b, 7, 1, C.COLORS.alert); return; }
    const SCALE = 6000, self = Math.min(usage, solar);
    const es = Math.round(Math.min(1, self / SCALE) * 32);
    const ei = Math.round(Math.min(1, usage / SCALE) * 32);
    const ex = Math.round(Math.min(1, solar / SCALE) * 32);
    for (let i = 0; i < es; i++) PF.setPixel(b, i, 7, C.COLORS.solar);
    for (let i = es; i < ei; i++) PF.setPixel(b, i, 7, C.COLORS.consumption);
    for (let i = ei; i < ex; i++) PF.setPixel(b, i, 7, C.COLORS.surplus);
  }

  function renderInto(matrix, s) {
    const b = global.Matrix.blank();
    drawStat(matrix, b, s);
    matrix.paint(b);
  }

  global.EnergyRender = { gauge, drawStat, renderInto };
})(window);
