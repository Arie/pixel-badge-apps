// stats.js — display config and formatting. This is the single source of truth
// for the mockup and mirrors the on-device app's config shape (short label,
// icon, color, kind, + later: HA entity_id).
(function (global) {
  // HomeWizard-inspired palette, brightened so it reads on real LEDs.
  const COLORS = {
    consumption: '#7b3ff2', // purple
    solar:       '#33d96f', // green
    export:      '#33d96f', // green (back to grid)
    self:        '#4fc3ff', // light blue
    socHigh:     '#33d96f', // >= 50%
    socMid:      '#ff9d3a', // 20-50%
    socLow:      '#ff4d4d'  // < 20%
  };

  const MODES = ['Rotate', 'Ticker', 'Gauge'];

  // kind: 'power' (W, one color), 'grid' (signed: -export green / +import purple),
  //       'soc' (%, color by level). label is the SHORT on-matrix tag.
  const STATS = [
    { id: 'USE',   label: 'USE',  icon: 'HOME', kind: 'power', color: COLORS.consumption, sample: 850 },
    { id: 'SOL',   label: 'SOL',  icon: 'SUN',  kind: 'power', color: COLORS.solar,       sample: 2100 },
    { id: 'SELF',  label: 'SELF', icon: 'SELF', kind: 'power', color: COLORS.self,        sample: 1450 },
    { id: 'GRID',  label: 'GRID', icon: 'GRID', kind: 'grid',                              sample: -1250 },
    { id: 'HW1',   label: 'HW1',  icon: 'BATT', kind: 'soc',                               sample: 78 },
    { id: 'HW2',   label: 'HW2',  icon: 'BATT', kind: 'soc',                               sample: 64 },
    { id: 'ZEN',   label: 'ZEN',  icon: 'BATT', kind: 'soc',                               sample: 41 }
  ];

  function colorOf(stat, value) {
    if (stat.kind === 'grid') return value < 0 ? COLORS.export : COLORS.consumption;
    if (stat.kind === 'soc')  return value >= 50 ? COLORS.socHigh : value >= 20 ? COLORS.socMid : COLORS.socLow;
    return stat.color;
  }

  // Compact value text for a 32px-wide matrix.
  function format(stat, value) {
    if (stat.kind === 'soc') return value + '%';
    const a = Math.abs(value);
    const sign = stat.kind === 'grid' ? (value < 0 ? '-' : '+') : '';
    return a >= 1000 ? sign + (a / 1000).toFixed(1) + 'K' : sign + a + 'W';
  }

  global.EnergyConfig = { COLORS, MODES, STATS, colorOf, format };
})(window);
