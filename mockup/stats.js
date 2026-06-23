// stats.js — display config, maxima, and formatting. Single source of truth for
// the mockup; mirrors the on-device app's config + derivation.
(function (global) {
  // HomeWizard-inspired palette, tuned on the real panel.
  const COLORS = {
    consumption: '#5518cc', // purple (deeper)
    solar:       '#2ed640', // green (less blue)
    export:      '#2ed640', // green (back to grid)
    self:        '#4fc3ff', // light blue
    charge:      '#5518cc', // battery charging = drawing power (like consumption) → purple
    discharge:   '#2ed640', // battery discharging = supplying power (like export) → green
    alert:       '#ff2a2a', // blinking-red overflow above rated maximum
    socHigh:     '#2ed640', socMid: '#ff9d3a', socLow: '#ff4d4d'
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
  //   grid     — signed W, gauge anchored by sign (import←left / export→right)
  //   battery  — composite per battery: "HWx NN%" label+SOC + power as the bottom bar
  const STATS = [
    { id: 'USE',  label: 'USE',  icon: 'HOME', kind: 'use',  color: COLORS.consumption, max: MAX.USE },
    { id: 'SOL',  label: 'SOL',  icon: 'SUN',  kind: 'power', color: COLORS.solar, max: MAX.SOL, sample: 3284, hideIdle: true },
    { id: 'SELF', label: 'SELF', icon: 'SELF', kind: 'self',  color: COLORS.self,  max: MAX.SELF, hideIdle: true },
    { id: 'GRID', label: 'GRID', icon: 'GRID', kind: 'grid',  maxPos: MAX.GRID_IMPORT, maxNeg: MAX.GRID_EXPORT, sample: -984 },
    { id: 'HW1',  label: 'HW1',  kind: 'battery', powerMax: MAX.HW_POWER,  weight: 1, socMin: 0,  sampleSoc: 78, samplePower: 250 },
    { id: 'HW2',  label: 'HW2',  kind: 'battery', powerMax: MAX.HW_POWER,  weight: 1, socMin: 0,  sampleSoc: 100, samplePower: 0 },  // idle/full → hidden
    { id: 'ZEN',  label: 'ZEN',  kind: 'battery', powerMax: MAX.ZEN_POWER, weight: 3, socMin: 10, sampleSoc: 41, samplePower: 600 }  // 3x capacity; empty at 10%
  ];

  // Usable SOC: remap the raw % onto each battery's usable range (ZEN is empty
  // at 10%, so 10→0%). Used everywhere SOC is shown.
  function displaySoc(stat) {
    const min = stat.socMin || 0;
    return Math.max(0, Math.min(100, Math.round((stat.sampleSoc - min) / (100 - min) * 100)));
  }
  // Fleet SOC: capacity-weighted average of the usable SOCs (ZEN counts 3x).
  function fleetSoc() {
    const bats = STATS.filter(s => s.kind === 'battery');
    let sum = 0, ws = 0;
    for (const bb of bats) { const w = bb.weight || 1; sum += displaySoc(bb) * w; ws += w; }
    return Math.round(sum / ws);
  }

  // Idle stats (|power| below this) are hidden: batteries always, plus any stat
  // flagged hideIdle (e.g. SOL at night). USE & GRID are always shown.
  const IDLE_W = 10;
  function isActive(stat) {
    if (stat.kind === 'battery') return Math.abs(stat.samplePower) >= IDLE_W;
    if (stat.hideIdle) return Math.abs(value(stat)) >= IDLE_W;
    return true;
  }
  // Shown in place of the individual batteries when they're all idle.
  const BATSUM = { id: 'BAT', label: 'BAT', kind: 'batsummary' };
  function activeStats() {
    const out = STATS.filter(s => s.kind !== 'battery' && isActive(s));
    const bats = STATS.filter(s => s.kind === 'battery' && isActive(s));
    if (bats.length) out.push.apply(out, bats);
    else out.push(BATSUM);
    return out;
  }

  // ---- derivation (mockup sample values mirror the on-device formula) --------
  const SAMPLE = { solar: 3284, grid: -984, batteries: 250 + 0 + 600 };
  function value(stat) {
    if (stat.kind === 'use')  return SAMPLE.solar + SAMPLE.grid - SAMPLE.batteries;
    if (stat.kind === 'self') return SAMPLE.solar - Math.max(0, -SAMPLE.grid);
    if (stat.kind === 'battery') return stat.sampleSoc;
    return stat.sample;
  }

  function colorOf(stat, v) {
    if (stat.kind === 'grid') return v < 0 ? COLORS.export : COLORS.consumption;
    return stat.color;
  }
  function socColor(soc)   { return soc >= 50 ? COLORS.socHigh : soc >= 20 ? COLORS.socMid : COLORS.socLow; }
  function powerColor(w)   { return w >= 0 ? COLORS.charge : COLORS.discharge; } // + = charging
  function isSigned(stat)  { return stat.kind === 'grid'; }

  function fmtPower(v, signed) {
    const a = Math.abs(v), sign = signed ? (v < 0 ? '-' : '+') : '';
    if (a < 1000) return sign + a + 'W';
    const k = a / 1000;                                 // 2 decimals < 10kW, 1 decimal above
    return sign + (k >= 10 ? k.toFixed(1) : k.toFixed(2)) + 'KW';
  }
  // signed battery power; KW preferred (render drops the W if it doesn't fit).
  function fmtBat(v) {
    const a = Math.abs(v), sign = v < 0 ? '-' : '+';
    if (a < 1000) return sign + a + 'W';
    const k = a / 1000;
    return sign + (k >= 10 ? k.toFixed(1) : k.toFixed(2)) + 'KW';
  }
  function fmt(stat, v) {
    if (stat.kind === 'soc') return v + '%';
    return fmtPower(v, isSigned(stat));
  }

  global.EnergyConfig = { COLORS, MAX, MODES, STATS, value, colorOf, socColor, powerColor, isSigned, fmt, fmtPower, fmtBat, isActive, activeStats, BATSUM, displaySoc, fleetSoc };
})(window);
