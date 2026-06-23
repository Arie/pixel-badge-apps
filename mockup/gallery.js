// gallery.js — contact sheet: every icon and every stat (static + gauge) at once,
// so alignment and icon issues are visible side by side.
(function () {
  const C = window.EnergyConfig, R = window.EnergyRender, PF = window.PixelFont;

  function tile(parent, label) {
    const wrap = document.createElement('div'); wrap.className = 'tile';
    const mx = document.createElement('div'); mx.className = 'matrix';
    const cap = document.createElement('div'); cap.className = 'cap'; cap.textContent = label;
    wrap.appendChild(mx); wrap.appendChild(cap); parent.appendChild(wrap);
    return new window.Matrix(mx);
  }
  // Render an icon + a short label the way the app draws icon+value (rows 1-5).
  function iconTile(parent, iconName, word, caption) {
    const m = tile(parent, caption);
    const b = window.Matrix.blank();
    m.icon(b, 0, 1, iconName, '#bfe3ff');
    PF.drawText(b, 9, 1, word, '#6f8295');
    m.paint(b);
  }

  // --- Main icons (final set) ---
  const icons = document.getElementById('icons');
  [['SUN', 'SOL'], ['HOME', 'USE'], ['SELF', 'SELF'], ['GRID', 'GRID'], ['BATT', 'HW1'], ['BOLT', 'HW1']]
    .forEach(([ic, w]) => iconTile(icons, ic, w, ic));

  // --- All stats (single gauge view) ---
  function caption(s) {
    const idle = C.isActive(s) ? '' : '  — idle (hidden)';
    if (s.kind === 'battery') return s.id + '  ·  ' + s.sampleSoc + '% / ' + C.fmtPower(s.samplePower, true) + idle;
    return s.id + '  ·  ' + C.fmt(s, C.value(s)) + idle;
  }
  const gaugeGrid = document.getElementById('gauge');
  C.STATS.forEach(s => R.renderInto(tile(gaugeGrid, caption(s)), s));
  // BAT summary screen (shown only when ALL batteries are idle): 0W + fleet SOC gauge
  R.renderInto(tile(gaugeGrid, 'BAT summary · all full'),  { kind: 'batsummary', avg: 100 });
  R.renderInto(tile(gaugeGrid, 'BAT summary · live weighted (ZEN×3)'), { kind: 'batsummary' });
  R.renderInto(tile(gaugeGrid, 'BAT summary · all empty'), { kind: 'batsummary', avg: 0 });

  // --- Edge cases ---
  const edgeGrid = document.getElementById('edges');
  [
    { cap: 'USE overflow 19kW', s: { label: 'USE', kind: 'power', icon: 'HOME', color: C.COLORS.consumption, max: C.MAX.USE, sample: 19000 } },
    { cap: 'SOL full 6kW',      s: { label: 'SOL', kind: 'power', icon: 'SUN', color: C.COLORS.solar, max: C.MAX.SOL, sample: 6000 } },
    { cap: 'GRID exp -8kW OVERFLOW', s: { label: 'GRID', kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, sample: -8000 } },
    { cap: 'GRID import +8kW',  s: { label: 'GRID', kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, sample: 8000 } },
    { cap: 'HW1 12% low, charging', s: { label: 'HW1', kind: 'battery', powerMax: C.MAX.HW_POWER, socMin: 0, sampleSoc: 12, samplePower: 600 } },
    { cap: 'ZEN 90% discharging',   s: { label: 'ZEN', kind: 'battery', powerMax: C.MAX.ZEN_POWER, socMin: 10, sampleSoc: 90, samplePower: -1800 } }
  ].forEach(c => R.renderInto(tile(edgeGrid, c.cap), c.s));
})();
