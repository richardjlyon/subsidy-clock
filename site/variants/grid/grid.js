/* Grid variant page: combined totals, meter strip, hero, A/B grid arms. */
(function () {
  'use strict';

  var SCHEMES = {
    ro:              { slug: 'renewables-obligation',   name: 'Renewables Obligation',             color: 'var(--c-ro)' },
    fit:             { slug: 'feed-in-tariffs',         name: 'Feed-in Tariffs',                   color: 'var(--c-fit)' },
    cfd_renewable:   { slug: 'contracts-for-difference', name: 'Contracts for Difference',         color: 'var(--c-cfdr)' },
    cfd_low_carbon:  { slug: 'cfd-nuclear-biomass',     name: 'CfD — nuclear & biomass',      color: 'var(--c-cfdl)' },
    constraints:     { slug: 'constraints',             name: 'Paid to switch off (constraints)',  color: 'var(--c-con)' },
    tnuos:           { slug: 'tnuos',                   name: 'Grid upgrades for renewables (TNUoS)', color: 'var(--c-tnuos)' },
    ccl:             { slug: 'climate-change-levy',     name: 'Climate Change Levy',               color: 'var(--c-ccl)' },
    bsuos:           { slug: 'bsuos',                   name: 'Balancing the grid (BSUoS)',        color: 'var(--c-bsuos)' },
    ets:             { slug: 'emissions-trading',       name: 'Emissions trading',                 color: 'var(--c-ets)' },
    capacity_market: { slug: 'capacity-market',         name: 'Capacity Market',                   color: 'var(--c-cm)' }
  };

  var state = { real: false, arm: null, forced: false };
  var data, D; // loaded JSON bundle; derived constants

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ---- money on the selected basis (combined = low_carbon + indirect; spec §7)
  function basis(block) { return state.real ? block.real_2024 : block; }
  function direct() { return basis(data.totals.perspectives.low_carbon); }
  function indirect() { return basis(data.totals.indirect); }
  function combinedRate() { return direct().rate_gbp_per_sec + indirect().rate_gbp_per_sec; }
  function liveCombined(t) {
    return direct().cumulative_gbp + indirect().cumulative_gbp +
      combinedRate() * (t - D.generatedAt) / 1000;
  }
  function schemeAnnualReal(id) { // 2024-£ cumulative for a scheme
    var sum = 0;
    data.timeseries.schemes[id].annual.forEach(function (a) { sum += a.cost_gbp_2024; });
    return sum;
  }
  function schemeCumulative(s) {
    return state.real ? schemeAnnualReal(s.id) : s.cumulative_gbp;
  }
  function schemeRate(s) { // £/sec now; real basis scales by the same factor as the layer runrate
    var nominal = s.runrate_gbp_per_year / D.secsPerYear;
    if (!state.real) return nominal;
    var layer = s.layer === 'direct' ? data.totals.perspectives.low_carbon : data.totals.indirect;
    return nominal * (layer.real_2024.runrate_gbp_per_year / layer.runrate_gbp_per_year);
  }

  // ---- share of bill, latest complete year (same arithmetic as the main share chart)
  function shareOfBill() {
    var ts = data.timeseries;
    var byYear = function (rows, key) {
      var m = {}; rows.forEach(function (a) { m[a.year] = state.real ? a[key + '_2024'] : a[key]; });
      return m;
    };
    var bill = byYear(ts.electricity_bill.annual, 'total_bill_gbp');
    var dir = byYear(ts.perspectives.low_carbon.annual, 'cost_gbp');
    var ind = byYear(ts.indirect.annual, 'cost_gbp');
    var years = ts.electricity_bill.annual.map(function (a) { return a.year; });
    var y = years[years.length - 1];
    return { year: y, share: (dir[y] + ind[y]) / bill[y] };
  }

  // ---- arm assignment (spec §5)
  function assignArm() {
    var m = location.search.match(/[?&]arm=([ab])\b/);
    if (m) { state.arm = m[1]; state.forced = true; return; }
    var stored = SC.storedArm();
    if (stored === 'a' || stored === 'b') { state.arm = stored; return; }
    state.arm = Math.random() < 0.5 ? 'a' : 'b';
    SC.storeArm(state.arm);
  }
  function armTag() { return state.arm + (state.forced ? '-forced' : ''); }

  // ---- rendering
  function schemesByLayer(layer) {
    return data.breakdown.schemes
      .filter(function (s) { return s.layer === layer && SCHEMES[s.id]; })
      .sort(function (a, b) { return schemeCumulative(b) - schemeCumulative(a); });
  }
  function grandTotal() {
    return direct().cumulative_gbp + indirect().cumulative_gbp;
  }
  function rowHtml(s) {
    var meta = SCHEMES[s.id];
    var pct = Math.round(100 * schemeCumulative(s) / grandTotal());
    return '<a class="krow" href="explainers/' + meta.slug + '.html" data-scheme="' + s.id + '">' +
      '<span class="dot" style="background:' + meta.color + '"></span>' +
      '<span class="nm">' + esc(meta.name) + '</span>' +
      '<span class="amt num">' + SC.fmtCompact(schemeCumulative(s)) + '</span>' +
      '<span class="pct num">' + pct + '%</span></a>';
  }
  function renderArmA() {
    var el = document.getElementById('arm-a');
    el.innerHTML =
      '<div class="kcard"><h2 class="num">' + SC.fmtCompact(direct().cumulative_gbp) + ' direct</h2>' +
      '<div class="ksub">paid through your bill since 2002 · ticking ' +
        SC.fmtRate(direct().rate_gbp_per_sec).slice(1) + '</div>' +
      schemesByLayer('direct').map(rowHtml).join('') + '</div>' +
      '<div class="kcard"><h2 class="num">' + SC.fmtCompact(indirect().cumulative_gbp) + ' indirect</h2>' +
      '<div class="ksub">estimated · ticking ' +
        SC.fmtRate(indirect().rate_gbp_per_sec).slice(1) + '</div>' +
      schemesByLayer('indirect').map(rowHtml).join('') + '</div>';
  }
  function renderArmB() {
    var el = document.getElementById('arm-b');
    el.innerHTML = schemesByLayer('direct').concat(schemesByLayer('indirect'))
      .map(function (s) {
        var meta = SCHEMES[s.id];
        return '<a class="tile" href="explainers/' + meta.slug + '.html" data-scheme="' + s.id + '"' +
          ' style="background:' + meta.color + '">' +
          '<span class="tn">' + esc(meta.name) +
            (s.layer === 'indirect' ? ' · estimated' : '') + '</span>' +
          '<span class="tv num" data-tile-total="' + s.id + '">' +
            SC.fmtCompact(schemeCumulative(s)) + '</span>' +
          '<span class="tr num">' + SC.fmtRate(schemeRate(s)) + '</span></a>';
      }).join('');
  }
  function renderStatic() {
    document.getElementById('cell-rate').textContent = SC.fmtPence(combinedRate()) + '/sec';
    document.getElementById('cell-household').textContent =
      SC.fmtPence(direct().per_household_per_year_gbp + indirect().per_household_per_year_gbp) + '/yr';
    var sb = shareOfBill();
    document.getElementById('cell-share').textContent = Math.round(100 * sb.share) + '% (' + sb.year + ')';
    document.getElementById('hero-sub').innerHTML =
      'cost of UK renewable and low-carbon energy subsidy since 2002 · <b>' +
      SC.fmtCompact(direct().cumulative_gbp) + ' direct</b> on your bill + <b>' +
      SC.fmtCompact(indirect().cumulative_gbp) + ' indirect (estimated)</b>' +
      (state.real ? ' · 2024 prices' : '');
    if (state.arm === 'a') { renderArmA(); } else { renderArmB(); }
    document.getElementById('arm-a').hidden = state.arm !== 'a';
    document.getElementById('arm-b').hidden = state.arm !== 'b';
  }

  var openedAt = Date.now();
  function tick(t) {
    var rate = combinedRate();
    var d = new Date(t);
    var startToday = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    var startYear = new Date(d.getFullYear(), 0, 1).getTime();
    document.getElementById('cell-opened').textContent = SC.fmtPence(rate * (t - openedAt) / 1000);
    document.getElementById('cell-today').textContent = SC.fmtCompact(rate * (t - startToday) / 1000);
    document.getElementById('cell-year').textContent = SC.fmtCompact(rate * (t - startYear) / 1000);
    document.getElementById('hero-total').textContent = SC.fmtFull(liveCombined(t));
  }

  function wireToggle() {
    var bN = document.getElementById('btn-nominal'), bR = document.getElementById('btn-real');
    function set(real) {
      state.real = real;
      bN.setAttribute('aria-pressed', String(!real));
      bR.setAttribute('aria-pressed', String(real));
      renderStatic();
    }
    bN.addEventListener('click', function () { set(false); });
    bR.addEventListener('click', function () { set(true); });
  }

  function wireClicks() {
    document.addEventListener('click', function (e) {
      var link = e.target.closest('[data-scheme]');
      if (link) { SC.track('grid-click/' + armTag() + '/' + SCHEMES[link.dataset.scheme].slug); }
    });
  }

  SC.initTracking();
  SC.loadData().then(function (bundle) {
    data = bundle;
    D = SC.derive(data.totals);
    assignArm();
    SC.track('grid-view/' + armTag());
    renderStatic();
    wireToggle();
    wireClicks();
    SC.startTicker(tick);
  }).catch(function (err) {
    document.getElementById('hero-sub').textContent = 'Could not load data: ' + err.message;
  });
})();
