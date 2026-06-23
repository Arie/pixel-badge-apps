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
    if (s.kind === 'battery') return s.id + '  ·  ' + s.sampleSoc + '% / ' + C.fmtPower(s.samplePower, true);
    return s.id + '  ·  ' + C.fmt(s, C.value(s));
  }
  const gaugeGrid = document.getElementById('gauge');
  C.STATS.forEach(s => R.renderInto(tile(gaugeGrid, caption(s)), s));

  // --- Edge cases ---
  const edgeGrid = document.getElementById('edges');
  [
    { label: 'USE overflow 19kW', kind: 'power', icon: 'HOME', color: C.COLORS.consumption, max: C.MAX.USE, sample: 19000 },
    { label: 'SOL full 6kW',      kind: 'power', icon: 'SUN', color: C.COLORS.solar, max: C.MAX.SOL, sample: 6000 },
    { label: 'GRID exp -8kW OVERFLOW', kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, sample: -8000 },
    { label: 'GRID import +8kW',  kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, sample: 8000 },
    { label: 'HW1 12% low, charging', kind: 'battery', powerMax: C.MAX.HW_POWER, sampleSoc: 12, samplePower: 600 },
    { label: 'ZEN 90% discharging',   kind: 'battery', powerMax: C.MAX.ZEN_POWER, sampleSoc: 90, samplePower: -1800 }
  ].forEach(cs => R.renderInto(tile(edgeGrid, cs.label), cs, true));
})();
