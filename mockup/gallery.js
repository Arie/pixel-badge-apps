// gallery.js — contact sheet: every icon and every stat (static + gauge) at once,
// so alignment and icon issues are visible side by side.
(function () {
  const C = window.EnergyConfig, R = window.EnergyRender, PF = window.PixelFont;

  function tile(parent, label) {
    const wrap = document.createElement('div'); wrap.className = 'tile';
    const cap = document.createElement('div'); cap.className = 'cap'; cap.textContent = label;
    const mx = document.createElement('div'); mx.className = 'matrix';
    wrap.appendChild(mx); wrap.appendChild(cap); parent.appendChild(wrap);
    return new window.Matrix(mx);
  }

  // --- Icons (icon at x=0, plus its name in the font for baseline comparison) ---
  const iconGrid = document.getElementById('icons');
  ['SUN', 'HOME', 'SELF', 'GRID', 'BATT', 'BOLT'].forEach(name => {
    const m = tile(iconGrid, name);
    const b = window.Matrix.blank();
    m.icon(b, 0, 0, name, '#cfe');
    PF.drawText(b, 11, 2, name.slice(0, 4), '#7790aa');
    m.paint(b);
  });

  // --- Static (Rotate) row ---
  const staticGrid = document.getElementById('static');
  C.STATS.forEach(s => R.renderInto(tile(staticGrid, s.id + '  ·  ' + C.fmt(s, C.value(s))), s, false));

  // --- Gauge row ---
  const gaugeGrid = document.getElementById('gauge');
  C.STATS.forEach(s => R.renderInto(tile(gaugeGrid, s.id + '  ·  ' + C.fmt(s, C.value(s))), s, true));

  // --- Gauge edge cases (overflow / extremes) ---
  const edgeGrid = document.getElementById('edges');
  const cases = [
    { label: 'USE overflow 19kW', kind: 'power', icon: 'HOME', color: C.COLORS.consumption, max: C.MAX.USE, _v: 19000 },
    { label: 'SOL full 6kW',      kind: 'power', icon: 'SUN', color: C.COLORS.solar, max: C.MAX.SOL, _v: 6000 },
    { label: 'GRID import +8kW',  kind: 'grid', icon: 'GRID', max: C.MAX.GRID, _v: 8000 },
    { label: 'ZEN charge +2400',  kind: 'batpower', icon: 'BOLT', max: C.MAX.ZEN_POWER, _v: 2400 },
    { label: 'HW dischg -800',    kind: 'batpower', icon: 'BOLT', max: C.MAX.HW_POWER, _v: -800 },
    { label: 'SOC low 12%',       kind: 'soc', icon: 'BATT', _v: 12 }
  ];
  // temporarily override value() lookup by stuffing a sample
  cases.forEach(cs => {
    const s = Object.assign({}, cs, { sample: cs._v, id: cs.label, label: cs.label.slice(0, 4) });
    R.renderInto(tile(edgeGrid, cs.label), s, true);
  });
})();
