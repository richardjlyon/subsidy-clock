/* Grid variant shared helpers: data load, formatting, ticking, Matomo event tracking. */
/* exported SC */
var SC = (function () {
  'use strict';


  // ---- data root resolved from this script's URL, so pages at any depth share it
  var DATA_BASE = (function () {
    var script = document.currentScript;
    if (!script) {
      var ss = document.getElementsByTagName('script');
      script = ss[ss.length - 1];
    }
    return script.src.replace(/[^\/]*$/, '') + '../data/';
  })();

  function fmtFull(v) { // £186,212,345,678 — no decimals
    return '£' + Math.floor(v).toLocaleString('en-GB');
  }
  function fmtPence(v) { // £487.21
    return '£' + v.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtCompact(v) { // £12.3bn / £31.5m / £487
    if (v < 0) return '−' + fmtCompact(-v);
    var a = Math.abs(v);
    if (a >= 1e9) return '£' + (v / 1e9).toFixed(1) + 'bn';
    if (a >= 1e6) return '£' + (v / 1e6).toFixed(1) + 'm';
    if (a >= 1e3) return '£' + Math.round(v).toLocaleString('en-GB');
    return '£' + v.toFixed(2);
  }
  function fmtRate(v) { // +£245/sec | +£6.20/sec
    return '+£' + (v >= 10 ? Math.round(v).toLocaleString('en-GB') : v.toFixed(2)) + '/sec';
  }

  function loadData() { // resolves {totals, breakdown, timeseries}
    return Promise.all(
      ['totals', 'breakdown', 'timeseries'].map(function (n) {
        return fetch(DATA_BASE + n + '.json').then(function (r) {
          if (!r.ok) throw new Error(n + ': HTTP ' + r.status);
          return r.json();
        });
      })
    ).then(function (rs) { return { totals: rs[0], breakdown: rs[1], timeseries: rs[2] }; });
  }

  // ---- derived constants (call once after loadData)
  function derive(totals) {
    var r = totals.perspectives.renewables;
    return {
      generatedAt: Date.parse(totals.generated_at),
      secsPerYear: r.runrate_gbp_per_year / r.rate_gbp_per_sec,
      households: r.runrate_gbp_per_year / r.per_household_per_year_gbp
    };
  }

  // ---- ticking loop with reduced-motion fallback (mirrors site/app.js)
  function startTicker(fn) {
    var motionOK = !(window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    function loop() {
      fn(Date.now());
      if (motionOK) { requestAnimationFrame(loop); } else { setTimeout(loop, 1000); }
    }
    loop();
  }

  // ---- tracking: delegated to the shared share.js component (single tracking owner)
  function initTracking() {
    if (window.SCShare) SCShare.initTracking();
  }
  function track(eventPath) {
    if (window.SCShare) SCShare.track(eventPath);
  }

  return {
    fmtFull: fmtFull, fmtPence: fmtPence, fmtCompact: fmtCompact, fmtRate: fmtRate,
    loadData: loadData, derive: derive, startTicker: startTicker,
    initTracking: initTracking, track: track
  };
})();
