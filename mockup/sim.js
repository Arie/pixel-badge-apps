// sim.js — the controller: maps D-pad/arrow input to mode + stat, and renders
// each mode onto the Matrix. Mirrors the navigation the badge app will use.
(function () {
  const { MODES, STATS, colorOf, format } = window.EnergyConfig;
  const matrixEl = document.getElementById('matrix');
  const matrix = new window.Matrix(matrixEl);

  let mode = 0, stat = 0, rotTimer = null, tickTimer = null, tickOff = 32;

  const value = s => s.sample; // mockup uses sample data; app reads HA here.

  function renderRotateOrStatic() {
    const b = window.Matrix.blank(), s = STATS[stat], v = value(s), c = colorOf(s, v);
    matrix.icon(b, 0, 0, s.icon, c);
    window.PixelFont.drawText(b, 11, 2, format(s, v), c);
    matrix.paint(b);
  }
  function renderGauge() {
    const b = window.Matrix.blank(), s = STATS[stat], v = value(s), c = colorOf(s, v);
    matrix.icon(b, 0, 1, s.icon, c);
    window.PixelFont.drawText(b, 10, 1, format(s, v), c);
    const len = s.kind === 'soc'
      ? Math.round(v / 100 * 30)
      : Math.min(30, Math.round(Math.abs(v) / 100));
    matrix.bar(b, 1, 7, len, c);
    matrix.paint(b);
  }
  function renderTicker() {
    const b = window.Matrix.blank();
    let x = tickOff, total = 0;
    for (const s of STATS) {
      const v = value(s), seg = s.label + ' ' + format(s, v);
      x = window.PixelFont.drawText(b, x, 2, seg, colorOf(s, v)) + 6;
    }
    for (const s of STATS) total += window.PixelFont.textWidth(s.label + ' ' + format(s, value(s))) + 6;
    matrix.paint(b);
    tickOff--; if (tickOff < -total) tickOff = 32;
  }

  function stop() { clearInterval(rotTimer); clearInterval(tickTimer); rotTimer = tickTimer = null; }
  function render() {
    stop();
    if (MODES[mode] === 'Rotate') {
      renderRotateOrStatic();
      rotTimer = setInterval(() => { stat = (stat + 1) % STATS.length; renderRotateOrStatic(); readout(); }, 2500);
    } else if (MODES[mode] === 'Ticker') {
      tickOff = 32; tickTimer = setInterval(renderTicker, 90);
    } else {
      renderGauge();
    }
    readout();
  }
  function readout() {
    document.getElementById('modepills').innerHTML =
      MODES.map((m, i) => `<span class="pill ${i === mode ? 'on' : ''}">${m}</span>`).join('');
    const s = STATS[stat], v = value(s);
    document.getElementById('readout').innerHTML =
      `Mode <b>${MODES[mode]}</b> &nbsp;•&nbsp; Stat <b>${s.label}</b> = <b>${format(s, v)}</b>` +
      (MODES[mode] === 'Ticker' ? ' &nbsp;<span style="color:#678">(ticker shows all)</span>' : '');
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
