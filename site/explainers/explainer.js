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

    var rate = s.runrate_per_year / D.secsPerYear;
    var perHousehold = s.runrate_per_year / D.households;

    document.getElementById('x-rate').textContent = '+' + SC.fmtCompact(rate * 86400) + '/day';
    document.getElementById('x-household').textContent = '≈ ' + SC.fmtPence(perHousehold) + '/yr';

    // BASIS. Every figure on this page is nominal — cash as it was paid, each
    // year's pounds unadjusted. The front page shows the same schemes in 2024
    // prices, so the two disagree by the CPIH uplift (BSUoS: £22.8bn here vs
    // £26.3bn there; the Renewables Obligation differs by £17.7bn). Neither is
    // wrong, but an unlabelled figure that contradicts another page is, so the
    // real-terms equivalent is stated here rather than left to be discovered.
    var realCum = null;
    if (data.timeseries && data.timeseries.schemes && data.timeseries.schemes[id]) {
      realCum = 0;
      data.timeseries.schemes[id].annual.forEach(function (a) { realCum += a.cost_real; });
    }
    var basisEl = document.getElementById('x-total-basis');
    if (basisEl && realCum) {
      basisEl.innerHTML = '≈ <span class="num">' + SC.fmtCompact(realCum) +
        '</span> in today\u2019s money';
    }

    // live prose slots: <span data-live="cumulative|runrate|household|rate"></span>
    // turn-up only: what was actually paid on constraint-flagged offers while
    // wind was switched off, and the gas share of it
    var paidMeasured = '', gasShare = '';
    if (s.cross_check_cumulative && s.by_fuel_while_wind_constrained) {
      var paid = s.cross_check_cumulative.accepted_offers_wind, gas = 0;
      s.by_fuel_while_wind_constrained.forEach(function (f) {
        if (f.fuel === 'CCGT' || f.fuel === 'OCGT') gas += f.cost;
      });
      paidMeasured = SC.fmtCompact(paid);
      gasShare = paid > 0 ? Math.round(100 * gas / paid) + '%' : '';
    }
    var liveVals = {
      'paid-measured': paidMeasured,
      'gas-share': gasShare,
      cumulative: SC.fmtCompact(s.cumulative),
      runrate: SC.fmtCompact(s.runrate_per_year),
      household: SC.fmtPence(perHousehold),
      rate: SC.fmtPence(rate),
      // the constraints bottom-up splice date retreats weekly with the
      // nightly backfill, so prose quoting it must read it live
      'held-from': s.held_from
        ? new Date(s.held_from).toLocaleDateString('en-GB',
            { day: 'numeric', month: 'long', year: 'numeric' })
        : ''
    };
    // parts of one line (carbon: tax collected / the rest of the carbon in the price),
    // summed over every year: <span data-live="part:tax_collected"></span>
    if (Array.isArray(s.parts) && s.part_labels) {
      Object.keys(s.part_labels).forEach(function (k) {
        var sum = 0;
        s.parts.forEach(function (row) { sum += row[k] || 0; });
        liveVals['part:' + k] = SC.fmtCompact(sum);
      });
    }
    // REF / Elexon year split: the pin, elexon_first_year in breakdown.json.
    // Accept it only as an integer from 2010 to next year; otherwise the
    // markup's data-fallback text stays
    var pinned = data.breakdown.elexon_first_year;
    if (typeof pinned === 'number' && pinned % 1 === 0 &&
        pinned >= 2010 && pinned <= new Date().getFullYear() + 1) {
      liveVals['elexon-first-year'] = String(pinned);
      liveVals['ref-last-year'] = String(pinned - 1);
    }
    // the whole bracketed note is one live value, so it stays empty (no
    // stray brackets) when the data is missing
    liveVals['bottom-up-note'] = liveVals['held-from']
      ? ' (data held from ' + liveVals['held-from'] + ')' : '';
    Array.prototype.forEach.call(document.querySelectorAll('[data-live]'), function (el) {
      el.textContent = liveVals[el.getAttribute('data-live')] ||
        el.getAttribute('data-fallback') || '';
    });

    // sparkline from the annual series
    // leading zero years are years before the series exists, not years of nil cost
    var annual = data.timeseries.schemes[id].annual.slice();
    while (annual.length > 1 && !annual[0].cost) annual.shift();
    var max = 0;
    annual.forEach(function (a) { if (a.cost > max) max = a.cost; });
    document.getElementById('x-spark').innerHTML = annual.map(function (a) {
      var h = max > 0 ? Math.max(2, Math.round(100 * Math.max(0, a.cost) / max)) : 2;
      return '<i style="height:' + h + '%" title="' + a.year + ': ' + SC.fmtCompact(a.cost) + '"></i>';
    }).join('');

    // published to the line's latest data, plus the estimate since its data end at its
    // latest rate (the front page's per-line carry-forward, aios-harness#46)
    var cf = s.carry_forward;
    var anchor = cf && cf.from ? Date.parse(cf.from) : Date.parse(data.totals.generated_at);
    var cfRate = cf && cf.from ? cf.rate_per_sec : rate;
    SC.startTicker(function (t) {
      document.getElementById('x-total').textContent =
        SC.fmtFull(s.cumulative + cfRate * Math.max(0, t - anchor) / 1000);
    });

    SC.track('explainer-view/' + document.body.getAttribute('data-scheme-slug'));
  }).catch(function (err) {
    document.getElementById('x-total').textContent = '—';
  });
})();
