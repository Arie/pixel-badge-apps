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

  // --- Static (centred) row ---
  const staticGrid = document.getElementById('static');
  C.STATS.forEach(s => R.renderInto(tile(staticGrid, s.id + '  ·  ' + C.fmt(s, C.value(s))), s, false));

  // --- Gauge row ---
  const gaugeGrid = document.getElementById('gauge');
  C.STATS.forEach(s => R.renderInto(tile(gaugeGrid, s.id + '  ·  ' + C.fmt(s, C.value(s))), s, true));

  // --- Gauge edge cases ---
  const edgeGrid = document.getElementById('edges');
  const cases = [
    { label: 'USE overflow 19kW', kind: 'power', icon: 'HOME', color: C.COLORS.consumption, max: C.MAX.USE, _v: 19000 },
    { label: 'SOL full 6kW',      kind: 'power', icon: 'SUN', color: C.COLORS.solar, max: C.MAX.SOL, _v: 6000 },
    { label: 'GRID export -5kW',     kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, _v: -5000 },
    { label: 'GRID exp -8kW OVERFLOW', kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, _v: -8000 },
    { label: 'GRID import +8kW',     kind: 'grid', icon: 'GRID', maxPos: C.MAX.GRID_IMPORT, maxNeg: C.MAX.GRID_EXPORT, _v: 8000 },
    { label: 'ZEN charge +2.4kW', kind: 'batpower', icon: 'BOLT', max: C.MAX.ZEN_POWER, _v: 2400 },
    { label: 'HW dischg -800W',   kind: 'batpower', icon: 'BOLT', max: C.MAX.HW_POWER, _v: -800 },
    { label: 'SOC low 12%',       kind: 'soc', icon: 'BATT', _v: 12 }
  ];
  cases.forEach(cs => {
    const s = Object.assign({}, cs, { sample: cs._v, id: cs.label, label: cs.label.slice(0, 4) });
    R.renderInto(tile(edgeGrid, cs.label), s, true);
  });
})();
