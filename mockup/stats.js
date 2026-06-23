// stats.js — display config, maxima, and formatting. Single source of truth for
// the mockup; mirrors the on-device app's config + derivation.
(function (global) {
  // HomeWizard-inspired palette, brightened so it reads on real LEDs.
  const COLORS = {
    consumption: '#7b3ff2', // purple
    solar:       '#33d96f', // green
    export:      '#33d96f', // green (back to grid)
    self:        '#4fc3ff', // light blue
    charge:      '#7b3ff2', // battery charging = drawing power (like consumption) → purple
    discharge:   '#33d96f', // battery discharging = supplying power (like export) → green
    alert:       '#ff2a2a', // blinking-red overflow above rated maximum
    socHigh:     '#33d96f', socMid: '#ff9d3a', socLow: '#ff4d4d'
  };

  // Gauge maxima (W) — full-scale value for each bar. Tuned to the install.
  const MAX = {
    USE:  17250, // home grid connection rated power; > this = solar+battery boost
    SOL:  6000,  // solar inverter rated power
    SELF: 6000,  // bounded by solar
    GRID_IMPORT: 17250, // grid connection rating (import side)
    GRID_EXPORT: 6000,  // solar inverter max; > this = batteries boosting export → overflow
    HW_POWER:  800,  // HomeWizard plug-in battery, each way
    ZEN_POWER: 2400, // Zendure AC2400+, each way
    SOC: 100
  };

  const MODES = ['Rotate', 'Ticker', 'Gauge'];

  // kinds:
  //   power    — W, unidirectional gauge (left→right), one colour
  //   use      — derived consumption = solar + grid + Σbattery (purple), can overflow MAX.USE
  //   self     — derived self-use = solar - export (light blue)
  //   grid     — signed W, bidirectional gauge: export(green) ↔ import(purple)
  //   soc      — battery state of charge %, unidirectional 0..100 gauge, colour by level
  //   batpower — signed battery power, bidirectional gauge: charge(green) ↔ discharge(amber)
  const STATS = [
    { id: 'USE',  label: 'USE',  icon: 'HOME', kind: 'use',     color: COLORS.consumption, max: MAX.USE },
    { id: 'SOL',  label: 'SOL',  icon: 'SUN',  kind: 'power',   color: COLORS.solar, max: MAX.SOL, sample: 3284 },
    { id: 'SELF', label: 'SELF', icon: 'SELF', kind: 'self',    color: COLORS.self,  max: MAX.SELF },
    { id: 'GRID', label: 'GRID', icon: 'GRID', kind: 'grid', maxPos: MAX.GRID_IMPORT, maxNeg: MAX.GRID_EXPORT, sample: -2761 },
    { id: 'HW1',  label: 'HW1',  icon: 'BATT', kind: 'soc',      sample: 78 },
    { id: 'HW1P', label: 'HW1',  icon: 'BOLT', kind: 'batpower', max: MAX.HW_POWER,  sample: 250 },
    { id: 'HW2',  label: 'HW2',  icon: 'BATT', kind: 'soc',      sample: 64 },
    { id: 'HW2P', label: 'HW2',  icon: 'BOLT', kind: 'batpower', max: MAX.HW_POWER,  sample: -180 },
    { id: 'ZEN',  label: 'ZEN',  icon: 'BATT', kind: 'soc',      sample: 41 },
    { id: 'ZENP', label: 'ZEN',  icon: 'BOLT', kind: 'batpower', max: MAX.ZEN_POWER, sample: 600 }
  ];

  // ---- derivation (mockup sample values mirror the on-device formula) --------
  const SAMPLE = { solar: 3284, grid: -2761, batteries: 250 - 180 + 600 };
  function value(stat) {
    if (stat.kind === 'use')  return SAMPLE.solar + SAMPLE.grid + SAMPLE.batteries;
    if (stat.kind === 'self') return SAMPLE.solar - Math.max(0, -SAMPLE.grid);
    return stat.sample;
  }

  function colorOf(stat, v) {
    if (stat.kind === 'grid')     return v < 0 ? COLORS.export : COLORS.consumption;
    if (stat.kind === 'soc')      return v >= 50 ? COLORS.socHigh : v >= 20 ? COLORS.socMid : COLORS.socLow;
    if (stat.kind === 'batpower') return v >= 0 ? COLORS.charge : COLORS.discharge;
    return stat.color;
  }
  function isSigned(stat) { return stat.kind === 'grid' || stat.kind === 'batpower'; }
  function isBidir(stat)  { return stat.kind === 'grid' || stat.kind === 'batpower'; }

  function fmt(stat, v) {
    if (stat.kind === 'soc') return v + '%';
    const a = Math.abs(v), sign = isSigned(stat) ? (v < 0 ? '-' : '+') : '';
    if (a < 1000) return sign + a + 'W';
    const k = a / 1000;                              // drop the decimal at >=10kW to fit
    return sign + (k >= 10 ? Math.round(k) : k.toFixed(1)) + 'KW';
  }

  global.EnergyConfig = { COLORS, MAX, MODES, STATS, value, colorOf, isSigned, isBidir, fmt };
})(window);
