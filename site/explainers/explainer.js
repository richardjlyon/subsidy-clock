/* Explainer page: identity strip ticking, sparkline, live prose slots, view event. */
(function () {
  'use strict';
  var id = document.body.getAttribute('data-scheme-id');

  SC.initTracking();
  SC.loadData().then(function (data) {
    var D = SC.derive(data.totals);
    var s = null;
    data.breakdown.schemes.forEach(function (x) { if (x.id === id) s = x; });
    if (!s) return;

    var rate = s.runrate_gbp_per_year / D.secsPerYear;
    var perHousehold = s.runrate_gbp_per_year / D.households;

    document.getElementById('x-rate').textContent = '+' + SC.fmtPence(rate) + '/sec';
    document.getElementById('x-household').textContent = '≈ ' + SC.fmtPence(perHousehold) + '/yr';

    // live prose slots: <span data-live="cumulative|runrate|household|rate"></span>
    var liveVals = {
      cumulative: SC.fmtCompact(s.cumulative_gbp),
      runrate: SC.fmtCompact(s.runrate_gbp_per_year),
      household: SC.fmtPence(perHousehold),
      rate: SC.fmtPence(rate)
    };
    Array.prototype.forEach.call(document.querySelectorAll('[data-live]'), function (el) {
      el.textContent = liveVals[el.getAttribute('data-live')] || '';
    });

    // sparkline from the annual series
    var annual = data.timeseries.schemes[id].annual;
    var max = 0;
    annual.forEach(function (a) { if (a.cost_gbp > max) max = a.cost_gbp; });
    document.getElementById('x-spark').innerHTML = annual.map(function (a) {
      var h = max > 0 ? Math.max(2, Math.round(100 * Math.max(0, a.cost_gbp) / max)) : 2;
      return '<i style="height:' + h + '%" title="' + a.year + ': ' + SC.fmtCompact(a.cost_gbp) + '"></i>';
    }).join('');

    var anchor = Date.parse(data.totals.generated_at);
    SC.startTicker(function (t) {
      document.getElementById('x-total').textContent =
        SC.fmtFull(s.cumulative_gbp + rate * (t - anchor) / 1000);
    });

    SC.track('explainer-view/' + document.body.getAttribute('data-scheme-slug'));
  }).catch(function (err) {
    document.getElementById('x-total').textContent = '—';
  });
})();
