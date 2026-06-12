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

    // share/cite control — lives under the identity strip
    var slug = document.body.getAttribute('data-scheme-slug');
    var CSV_BY_ID = {
      cfd_renewable: 'cfd.csv', cfd_low_carbon: 'cfd-nuclear-biomass.csv',
      ro: 'renewables-obligation.csv', fit: 'feed-in-tariffs.csv',
      constraints: 'constraints.csv', capacity_market: 'capacity-market.csv',
      ccl: 'climate-change-levy.csv', ets: 'emissions-trading.csv',
      tnuos: 'tnuos.csv', bsuos: 'bsuos.csv'
    };
    var pngSlug = slug === 'constraints' ? 'switch-off' : slug;
    var asofShort = new Date(data.totals.generated_at).toLocaleDateString('en-GB',
      { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    SCShare.attach(document.querySelector('.xstrip'), {
      id: slug,
      title: document.querySelector('h1').textContent,
      anchor: null,
      url: 'https://subsidyclock.co.uk/explainers/' + slug,
      png: '../share/' + pngSlug + '.png',
      csv: CSV_BY_ID[id] ? '../data/' + CSV_BY_ID[id] : null,
      label: document.querySelector('h1').textContent + ' — cumulative cost',
      figure: function () { return document.getElementById('x-total').textContent; }
    }, asofShort);
  }).catch(function (err) {
    document.getElementById('x-total').textContent = '—';
  });
})();
