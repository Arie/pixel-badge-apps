// sim.js — interactive preview. Single gauge view: auto-advances through the
// stats; LEFT/RIGHT step manually (and pause auto-advance briefly).
(function () {
  const C = window.EnergyConfig, R = window.EnergyRender;
  const matrixEl = document.getElementById('matrix');
  const matrix = new window.Matrix(matrixEl);
  const STATS = C.activeStats();    // idle batteries / solar filtered out; BAT summary if all idle

  let stat = 0, paused_until = 0;

  function render() {
    R.renderInto(matrix, STATS[stat]);
    readout();
  }
  function readout() {
    const s = STATS[stat];
    const val = s.kind === 'battery'
      ? s.sampleSoc + '% SOC · ' + C.fmtPower(s.samplePower, true) + ' power'
      : C.fmt(s, C.value(s));
    document.getElementById('readout').innerHTML =
      'Stat <b>' + s.label + '</b> = <b>' + val + '</b>' +
      '<br><span style="color:#678">auto-advancing · ◀ ▶ to step</span>';
    const pills = document.getElementById('modepills');
    if (pills) pills.innerHTML = STATS.map((x, i) =>
      '<span class="pill ' + (i === stat ? 'on' : '') + '">' + x.id + '</span>').join('');
  }
  function step(d) {
    stat = (stat + d + STATS.length) % STATS.length;
    paused_until = Date.now() + 6000;     // pause auto-advance after manual nav
    render();
  }

  document.querySelectorAll('.dpad button').forEach(btn => btn.onclick = () => {
    const k = btn.dataset.k;
    if (k === 'left') step(-1);
    else if (k === 'right') step(1);
  });
  matrixEl.setAttribute('tabindex', '0');
  matrixEl.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); step(1); }
  });

  render();
  setInterval(() => { window.Blink.on = !window.Blink.on; render(); }, 450);   // blink for overflow
  setInterval(() => {                                                           // auto-advance
    if (Date.now() > paused_until) { stat = (stat + 1) % STATS.length; render(); }
  }, 2500);
})();
