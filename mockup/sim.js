// sim.js — controller: maps D-pad/arrow input to mode + stat and renders each
// mode onto the Matrix. Mirrors the navigation the badge app will use.
(function () {
  const C = window.EnergyConfig;
  const { MODES, STATS } = C;
  const PF = window.PixelFont;
  const matrixEl = document.getElementById('matrix');
  const matrix = new window.Matrix(matrixEl);

  const R = window.EnergyRender;
  let mode = 0, stat = 0, rotTimer = null, tickTimer = null, tickOff = 32;

  function renderStatic() { R.renderInto(matrix, STATS[stat], false); }
  function renderGauge()  { R.renderInto(matrix, STATS[stat], true);  }
  function renderTicker() {
    const b = window.Matrix.blank();
    let x = tickOff, total = 0;
    for (const s of STATS) { const v = C.value(s); x = PF.drawText(b, x, 2, R.tickerSegment(s), C.colorOf(s, v)) + 6; }
    for (const s of STATS) total += PF.textWidth(R.tickerSegment(s)) + 6;
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
