// sim.js — controller: maps D-pad/arrow input to mode + stat and renders each
// mode onto the Matrix. Mirrors the navigation the badge app will use.
(function () {
  const C = window.EnergyConfig;
  const { MODES, STATS } = C;
  const PF = window.PixelFont;
  const matrixEl = document.getElementById('matrix');
  const matrix = new window.Matrix(matrixEl);

  let mode = 0, stat = 0, rotTimer = null, tickTimer = null, tickOff = 32;

  function gauge(b, s, v, col) {
    if (C.isBidir(s)) {
      matrix.barCenter(b, 7, Math.abs(v) / s.max, v >= 0 ? 1 : -1, col);
    } else {
      const frac = s.kind === 'soc' ? v / 100 : v / s.max;
      const overflow = matrix.barLeft(b, 7, frac, col);
      if (overflow) { // value above its rated max — flag both ends white
        PF.setPixel(b, 30, 7, C.COLORS.overflow);
        PF.setPixel(b, 31, 7, C.COLORS.overflow);
      }
    }
  }
  function drawStat(b, s, big) {
    const v = C.value(s), col = C.colorOf(s, v);
    matrix.icon(b, 0, big ? 1 : 0, s.icon, col);
    PF.drawText(b, 10, big ? 1 : 2, C.fmt(s, v), col);
    if (big) gauge(b, s, v, col);
  }
  function tickerSeg(s) { return s.label + ' ' + C.fmt(s, C.value(s)); }

  function renderStatic() { const b = window.Matrix.blank(); drawStat(b, STATS[stat], false); matrix.paint(b); }
  function renderGauge()  { const b = window.Matrix.blank(); drawStat(b, STATS[stat], true);  matrix.paint(b); }
  function renderTicker() {
    const b = window.Matrix.blank();
    let x = tickOff, total = 0;
    for (const s of STATS) { const v = C.value(s); x = PF.drawText(b, x, 2, tickerSeg(s), C.colorOf(s, v)) + 6; }
    for (const s of STATS) total += PF.textWidth(tickerSeg(s)) + 6;
    matrix.paint(b);
    tickOff--; if (tickOff < -total) tickOff = 32;
  }

  function stop() { clearInterval(rotTimer); clearInterval(tickTimer); rotTimer = tickTimer = null; }
  function render() {
    stop();
    if (MODES[mode] === 'Rotate') {
      renderStatic();
      rotTimer = setInterval(() => { stat = (stat + 1) % STATS.length; renderStatic(); readout(); }, 2500);
    } else if (MODES[mode] === 'Ticker') {
      tickOff = 32; tickTimer = setInterval(renderTicker, 90);
    } else renderGauge();
    readout();
  }
  function readout() {
    document.getElementById('modepills').innerHTML =
      MODES.map((m, i) => `<span class="pill ${i === mode ? 'on' : ''}">${m}</span>`).join('');
    const s = STATS[stat], v = C.value(s);
    const scale = s.kind === 'soc' ? '/100%' : s.max ? ' / ' + C.fmt({ kind: 'power' }, s.max) + ' max' : '';
    document.getElementById('readout').innerHTML =
      `Mode <b>${MODES[mode]}</b> &nbsp;•&nbsp; <b>${s.label}</b> ${s.kind === 'soc' ? 'SOC' : s.kind === 'batpower' ? 'power' : ''} = <b>${C.fmt(s, v)}</b>` +
      `<span style="color:#678">${scale}</span>` +
      (MODES[mode] === 'Ticker' ? ' &nbsp;<span style="color:#678">(shows all)</span>' : '');
  }
  function press(k) {
    if (k === 'up')    mode = (mode + MODES.length - 1) % MODES.length;
    if (k === 'down')  mode = (mode + 1) % MODES.length;
    if (k === 'left')  stat = (stat + STATS.length - 1) % STATS.length;
    if (k === 'right') stat = (stat + 1) % STATS.length;
    render();
  }

  document.querySelectorAll('.dpad button').forEach(b => b.onclick = () => press(b.dataset.k));
  matrixEl.addEventListener('keydown', e => {
    const m = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' }[e.key];
    if (m) { e.preventDefault(); press(m); }
  });
  matrixEl.focus();
  render();
})();
