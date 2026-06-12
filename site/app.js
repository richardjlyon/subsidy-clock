/* The Subsidy Clock — dashboard logic. No dependencies. */
'use strict';

(async function () {

  // ---------- data ----------
  let totals, timeseries, breakdown, meta;
  try {
    [totals, timeseries, breakdown, meta] = await Promise.all(
      ['totals', 'timeseries', 'breakdown', 'meta'].map(function (n) {
        return fetch('data/' + n + '.json').then(function (r) {
          if (!r.ok) throw new Error(n + ': HTTP ' + r.status);
          return r.json();
        });
      })
    );
  } catch (err) {
    document.getElementById('hero-sub').textContent = 'Data could not be loaded (' + err.message + ').';
    return;
  }

  var generatedAt = Date.parse(totals.generated_at);
  var openedAt = Date.now();
  var schemesById = {};
  breakdown.schemes.forEach(function (s) { schemesById[s.id] = s; });
  var indirectTotals = totals.indirect || null;

  // Real-terms (2024 £) support: per-scheme real cumulative is the sum of the
  // deflated annual series; run-rates scale by the uniform current-year factor.
  var realCumById = {};
  Object.keys((timeseries && timeseries.schemes) || {}).forEach(function (id) {
    var sum = 0;
    timeseries.schemes[id].annual.forEach(function (a) { sum += a.cost_gbp_2024; });
    realCumById[id] = sum;
  });
  var REAL_RUNRATE_FACTOR = totals.perspectives.renewables.runrate_gbp_per_year
    ? totals.perspectives.renewables.real_2024.runrate_gbp_per_year /
      totals.perspectives.renewables.runrate_gbp_per_year
    : 1;

  // ---------- formatting ----------
  function fmtFull(v) { // £105,432,198,332 — no decimals
    var sign = v < 0 ? '−' : '';
    return sign + '£' + Math.floor(Math.abs(v)).toLocaleString('en-GB');
  }
  function fmtPence(v) { // £43.27
    var sign = v < 0 ? '−' : '';
    return sign + '£' + Math.abs(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtCompact(v) { // £12.3bn
    var sign = v < 0 ? '−' : '';
    var a = Math.abs(v);
    if (a >= 1e9) return sign + '£' + (a / 1e9).toFixed(1) + 'bn';
    if (a >= 1e6) return sign + '£' + (a / 1e6).toFixed(1) + 'm';
    if (a >= 1e3) return sign + '£' + Math.round(a / 1e3) + 'k';
    return sign + '£' + Math.round(a);
  }
  function fmtInt(v) {
    return Math.round(v).toLocaleString('en-GB');
  }
  function fmtDate(iso) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---------- state ----------
  var motionOK = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var rafId;
  var state = { perspective: 'renewables', real: false };

  // display names, explainer slugs and chart colours for the category cards
  var SCHEME_META = {
    ro:              { slug: 'renewables-obligation',    name: 'Renewables Obligation',                color: 'var(--c-ro)' },
    fit:             { slug: 'feed-in-tariffs',          name: 'Feed-in Tariffs',                      color: 'var(--c-fit)' },
    cfd_renewable:   { slug: 'contracts-for-difference', name: 'Contracts for Difference',             color: 'var(--c-cfdr)' },
    cfd_low_carbon:  { slug: 'cfd-nuclear-biomass',      name: 'CfD — nuclear & biomass',              color: 'var(--c-cfdl)' },
    constraints:     { slug: 'constraints',              name: 'Paid to switch off (constraints)',     color: 'var(--c-con)' },
    tnuos:           { slug: 'tnuos',                    name: 'Grid upgrades for renewables (TNUoS)', color: 'var(--c-tnuos)' },
    ccl:             { slug: 'climate-change-levy',      name: 'Climate Change Levy',                  color: 'var(--c-ccl)' },
    bsuos:           { slug: 'bsuos',                    name: 'Balancing the grid (BSUoS)',           color: 'var(--c-bsuos)' },
    ets:             { slug: 'emissions-trading',        name: 'Emissions trading',                    color: 'var(--c-ets)' },
    capacity_market: { slug: 'capacity-market',          name: 'Capacity Market',                      color: 'var(--c-cm)' }
  };

  function persp() { return totals.perspectives[state.perspective]; }
  function pv() { // perspective values on the selected price basis
    var p = persp();
    return state.real ? p.real_2024 : p;
  }
  function iv() { // indirect values on the selected price basis
    if (!indirectTotals) return null;
    return state.real ? indirectTotals.real_2024 : indirectTotals;
  }
  function liveCumulative(t) {
    var p = pv();
    return p.cumulative_gbp + p.rate_gbp_per_sec * (t - generatedAt) / 1000;
  }
  function schemeCumulative(s) {
    return state.real && realCumById[s.id] != null ? realCumById[s.id] : s.cumulative_gbp;
  }
  function schemeRunrate(s) {
    return state.real ? s.runrate_gbp_per_year * REAL_RUNRATE_FACTOR : s.runrate_gbp_per_year;
  }
  function annualCost(a) {
    return state.real ? a.cost_gbp_2024 : a.cost_gbp;
  }

  // ---------- hero (static parts) ----------
  // I1 floor: the combined direct+indirect total in 2024 prices, floored to
  // the nearest £10bn STRICTLY BELOW it (a floor, never a midpoint), so every
  // sentence quoting it understates by construction. One source for the
  // lead-in, the Full-cost chip and the share text - sitedata.py applies the
  // same rule to the factoid sentences (_floor_step_below); they must never
  // disagree.
  function combinedRealFlooredGbp() {
    var combined = totals.perspectives.renewables.real_2024.cumulative_gbp +
                   indirectTotals.real_2024.cumulative_gbp;
    var floored = Math.floor(combined / 1e10) * 1e10;
    return floored === combined ? floored - 1e10 : floored; // exact boundary: step down
  }
  function hasCombinedReal() {
    return !!(indirectTotals && indirectTotals.real_2024 &&
              totals.perspectives.renewables.real_2024);
  }

  function renderHeroStatic() {
    var sinceYear = persp().since_year;
    document.getElementById('hero-value').textContent = fmtFull(liveCumulative(Date.now()));
    if (hasCombinedReal()) {
      document.getElementById('hero-leadin').innerHTML =
        'Supporting renewables has cost Great Britain over ' +
        '<a href="methodology.html#ref-reconciliation"><strong class="money num">£' +
        (combinedRealFlooredGbp() / 1e9) + ' billion</strong></a> in today\u2019s money. ' +
        'This much is measured to the penny:';
    }
    document.getElementById('hero-sub').innerHTML =
      'paid directly to renewable generators <span class="nowrap">since ' + sinceYear +
      '</span><sup class="hero-fn" title="Estimated between official updates: the counter ' +
      'advances at each scheme\u2019s most recent published run-rate.">†</sup>';
    document.getElementById('strip-alltime-since').textContent = 'since ' + sinceYear;
  }

  // ---------- ticking ----------
  function startOfToday(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); }
  function startOfWeek(d) {
    var dow = (d.getDay() + 6) % 7; // Monday = 0
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() - dow).getTime();
  }
  function startOfYear(d) { return new Date(d.getFullYear(), 0, 1).getTime(); }

  var els = {
    heroValue: document.getElementById('hero-value'),
    sinceOpened: document.getElementById('since-opened'),
    now: document.getElementById('strip-now'),
    today: document.getElementById('strip-today'),
    week: document.getElementById('strip-week'),
    year: document.getElementById('strip-year'),
    alltime: document.getElementById('strip-alltime')
  };

  function tick() {
    var t = Date.now();
    var d = new Date(t);
    var rate = pv().rate_gbp_per_sec;
    els.heroValue.textContent = fmtFull(liveCumulative(t));
    els.sinceOpened.textContent = fmtPence(rate * (t - openedAt) / 1000);
    els.now.textContent = fmtPence(rate);
    els.today.textContent = fmtFull(rate * (t - startOfToday(d)) / 1000);
    els.week.textContent = fmtFull(rate * (t - startOfWeek(d)) / 1000);
    els.year.textContent = fmtCompact(rate * (t - startOfYear(d)) / 1000);
    els.alltime.textContent = fmtCompact(liveCumulative(t));
    if (motionOK) {
      rafId = requestAnimationFrame(tick);
    } else {
      rafId = setTimeout(tick, 1000);
    }
  }

  // ---------- equivalences ----------
  function renderEquivalences() {
    var p = pv();
    var eq = meta.context.equivalences;
    var pop = meta.context.population;
    var items = [];
    if (eq && eq.nurse_salary_gbp) {
      var nurses = p.runrate_gbp_per_year / eq.nurse_salary_gbp.value;
      items.push(
        'This year’s run-rate equals the annual salaries of <span class="money num">' +
        fmtInt(Math.round(nurses / 1000) * 1000) + '</span> ' +
        '<span class="eq-src" title="' + esc(eq.nurse_salary_gbp.source + ' — ' + eq.nurse_salary_gbp.description) + '">NHS Band&nbsp;5 nurses</span>'
      );
    }
    if (eq && eq.ghost_hospital_gbp) {
      var hospitals = p.runrate_gbp_per_year / eq.ghost_hospital_gbp.value;
      items.push(
        'or the construction of <span class="money num">' + fmtInt(hospitals) + '</span> ' +
        '<span class="eq-src" title="' + esc(eq.ghost_hospital_gbp.source + ' — ' + eq.ghost_hospital_gbp.description) + '">new mid-sized hospitals</span> each year'
      );
    }
    items.push(
      'That is <span class="money num">' + fmtPence(p.per_mwh_delivered_gbp) +
      '</span> on every MWh of electricity delivered'
    );
    if (pop) {
      items.push(
        'Per person, it is <span class="money num">' + fmtPence(p.per_person_per_year_gbp) + '</span> a year ' +
        '<span class="eq-src" title="' + esc(pop.source + ' — ' + pop.description) + '">(UK population)</span>'
      );
    }
    document.getElementById('equivalences').innerHTML =
      items.map(function (h) { return '<li>' + h + '</li>'; }).join('');
  }

  // ---------- paid to switch off ----------
  function renderSwitchOff() {
    var c = schemesById.constraints;
    if (!c) return;
    document.getElementById('con-cumulative').textContent = fmtCompact(schemeCumulative(c));
    document.getElementById('con-runrate').textContent = fmtCompact(schemeRunrate(c));
    document.getElementById('con-curtailed').textContent = fmtInt(c.curtailed_mwh);
    document.getElementById('con-curtailed-label').textContent =
      c.bottom_up_from
        ? 'MWh paid for and not generated, ' + fmtDate(c.bottom_up_from) + ' – ' + fmtDate(c.bottom_up_to)
        : 'MWh paid for and not generated';
    document.getElementById('con-window').textContent =
      c.bottom_up_from ? fmtDate(c.bottom_up_from) + ' – ' + fmtDate(c.bottom_up_to) : '';
    var rows = (c.by_recipient || []).slice(0, 8).map(function (r) {
      return '<tr><td>' + esc(r.lead_party) + '</td>' +
        '<td class="num-col money">' + fmtCompact(r.cost_gbp) + '</td>' +
        '<td class="num-col cell-dim">' + fmtInt(Math.abs(r.volume_mwh)) + '</td></tr>';
    }).join('');
    document.querySelector('#con-table tbody').innerHTML = rows;
  }

  // ---------- scheme breakdown bars ----------
  // Per-scheme staleness thresholds (days): each source publishes in arrears,
  // so the threshold is set beyond that scheme's normal publication lag.
  var STALE_DAYS = {
    cfd: 21, cfd_renewable: 21, cfd_low_carbon: 21,
    constraints: 3, capacity_market: 75, ro: 730, fit: 730,
    bsuos: 7
  };
  var STALE_FALLBACK_MS = { daily: 2 * 864e5, monthly: 2 * 30.44 * 864e5, annual: 2 * 365.25 * 864e5 };
  function dataCoverageEnd(s) {
    // Monthly series are dated by the first day of the month they cover.
    if (s.cadence === 'monthly') {
      var d = new Date(s.data_to + 'T00:00:00Z');
      return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1);
    }
    return Date.parse(s.data_to);
  }
  function isStale(s) {
    var limitMs = STALE_DAYS[s.id]
      ? STALE_DAYS[s.id] * 864e5
      : (STALE_FALLBACK_MS[s.cadence] || Infinity);
    return generatedAt - dataCoverageEnd(s) > limitMs;
  }

  function renderSchemeBars() {
    var schemes = breakdown.schemes
      .filter(function (s) { return s.perspectives.indexOf(state.perspective) !== -1; })
      .slice()
      .sort(function (a, b) { return schemeCumulative(b) - schemeCumulative(a); });
    var max = Math.max.apply(null, schemes.map(function (s) { return Math.abs(schemeCumulative(s)); }));
    document.getElementById('scheme-bars').innerHTML = schemes.map(function (s) {
      var stale = isStale(s);
      var v = schemeCumulative(s);
      var w = Math.max(0.4, 100 * Math.abs(v) / max);
      return '<div class="bar-row">' +
        '<div class="bar-head">' +
          '<span class="bar-name">' + esc(s.label) + '</span>' +
          '<span class="badge" title="Update cadence and latest data date">' + esc(s.cadence) + ' · to ' + fmtDate(s.data_to) + '</span>' +
          (stale ? '<span class="badge badge-stale" title="Latest data is older than this scheme’s normal publication lag">stale</span>' : '') +
          '<span class="bar-amount money num">' + fmtCompact(v) + '</span>' +
        '</div>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + w.toFixed(2) + '%"></div></div>' +
      '</div>';
    }).join('');
  }

  // ---------- direct / indirect category cards ----------
  function renderCategoryCards() {
    var bySize = function (a, b) { return schemeCumulative(b) - schemeCumulative(a); };
    var direct = breakdown.schemes.filter(function (s) {
      return s.layer === 'direct' && s.perspectives.indexOf(state.perspective) !== -1 && SCHEME_META[s.id];
    }).sort(bySize);
    var indirect = breakdown.schemes.filter(function (s) {
      return s.layer === 'indirect' && SCHEME_META[s.id];
    }).sort(bySize);

    var ind = iv();
    var grand = pv().cumulative_gbp + (ind ? ind.cumulative_gbp : 0);
    function rowHtml(s) {
      var m = SCHEME_META[s.id];
      var v = schemeCumulative(s);
      var pct = grand > 0 ? Math.round(100 * v / grand) : 0;
      return '<a class="krow" href="explainers/' + m.slug + '.html">' +
        '<span class="dot" style="background:' + m.color + '"></span>' +
        '<span class="nm">' + esc(m.name) + '</span>' +
        '<span class="amt money num">' + fmtCompact(v) + '</span>' +
        '<span class="pct num">' + pct + '%</span></a>';
    }

    document.getElementById('direct-card-total').textContent = fmtCompact(pv().cumulative_gbp);
    document.getElementById('direct-card-sub').textContent =
      'paid through electricity bills since ' + persp().since_year +
      ' · adding ' + fmtPence(pv().rate_gbp_per_sec) + ' a second';
    document.getElementById('direct-card-rows').innerHTML = direct.map(rowHtml).join('');

    document.getElementById('indirect-card-total').textContent = ind ? fmtCompact(ind.cumulative_gbp) : '—';
    document.getElementById('indirect-card-sub').textContent = ind ?
      'adding ' + fmtPence(ind.rate_gbp_per_sec) + ' a second at the current run-rate' : '';
    document.getElementById('indirect-card-rows').innerHTML = indirect.map(rowHtml).join('');

    var lc = totals.perspectives.low_carbon;
    if (lc) {
      var delta = lc.cumulative_gbp - totals.perspectives.renewables.cumulative_gbp;
      document.getElementById('direct-card-foot').innerHTML =
        'Under the same schemes, nuclear and biomass received a further ' +
        '<span class="money num">' + fmtCompact(delta) + '</span> — ' +
        '<a href="methodology.html#perspectives">see the methodology page</a>.';
    }
  }

  // ---------- strip extras: household & share-of-bill chips (direct schemes only) ----------
  function renderStripExtras() {
    document.getElementById('strip-household').textContent =
      fmtPence(pv().per_household_per_year_gbp);

    var bill = timeseries.electricity_bill;
    var share = null, year = null;
    if (bill && bill.annual && bill.annual.length) {
      var directBy = {};
      timeseries.perspectives[state.perspective].annual.forEach(function (a) { directBy[a.year] = annualCost(a); });
      // same complete-year rule as renderShareChart; direct subsidy only
      var complete = bill.annual.filter(function (a) { return a.total_bill_gbp > 0; });
      var last = complete[complete.length - 1];
      if (last) {
        year = last.year;
        share = Math.max(0, directBy[year] || 0) / last.total_bill_gbp;
      }
    }
    document.getElementById('strip-share').textContent = share != null ? Math.round(100 * share) + '%' : '\u2014';
    document.getElementById('strip-share-sub').textContent = year != null ? 'of ' + year + ' electricity spend' : '';
  }

  // ---------- technology breakdown (CfD only) ----------
  function renderTechBars() {
    var combined = {};
    ['cfd_renewable', 'cfd_low_carbon'].forEach(function (id) {
      var s = schemesById[id];
      if (!s || !s.by_technology) return;
      s.by_technology.forEach(function (t) {
        if (!combined[t.technology]) combined[t.technology] = { cost: 0, mwh: 0 };
        combined[t.technology].cost += t.cost_gbp;
        combined[t.technology].mwh += t.generation_mwh;
      });
    });
    var rows = Object.keys(combined).map(function (k) {
      return { tech: k, cost: combined[k].cost, mwh: combined[k].mwh };
    }).sort(function (a, b) { return b.cost - a.cost; });
    var max = Math.max.apply(null, rows.map(function (r) { return Math.abs(r.cost); }));
    document.getElementById('tech-bars').innerHTML = rows.map(function (r) {
      var w = Math.max(0.4, 100 * Math.abs(r.cost) / max);
      return '<div class="bar-row">' +
        '<div class="bar-head">' +
          '<span class="bar-name">' + esc(r.tech) + '</span>' +
          '<span class="badge">' + fmtInt(r.mwh / 1000) + ' GWh</span>' +
          '<span class="bar-amount money num">' + fmtCompact(r.cost) + '</span>' +
        '</div>' +
        '<div class="bar-track"><div class="bar-fill' + (r.cost < 0 ? ' neg' : '') + '" style="width:' + w.toFixed(2) + '%"></div></div>' +
      '</div>';
    }).join('');
  }

  // ---------- recipients table ----------
  function renderRecipients() {
    var rows = [];
    ['cfd_renewable', 'cfd_low_carbon'].forEach(function (id) {
      var s = schemesById[id];
      (s && s.by_recipient || []).forEach(function (r) {
        rows.push({ name: r.unit_name, tech: r.technology, scheme: 'CfD', cost: r.cost_gbp, detail: null });
      });
    });
    var c = schemesById.constraints;
    (c && c.by_recipient || []).forEach(function (r) {
      rows.push({
        name: r.lead_party, tech: 'Wind (curtailed)', scheme: 'Constraints', cost: r.cost_gbp,
        detail: fmtInt(Math.abs(r.volume_mwh)) + ' MWh curtailed'
      });
    });
    rows.sort(function (a, b) { return b.cost - a.cost; });
    document.querySelector('#recipients-table tbody').innerHTML =
      rows.slice(0, 15).map(function (r, i) {
        return '<tr>' +
          '<td class="rank-col num">' + (i + 1) + '</td>' +
          '<td>' + esc(r.name) + (r.detail ? ' <span class="cell-dim">(' + esc(r.detail) + ')</span>' : '') + '</td>' +
          '<td class="cell-dim">' + esc(r.tech) + '</td>' +
          '<td class="cell-dim">' + esc(r.scheme) + '</td>' +
          '<td class="num-col money">' + fmtCompact(r.cost) + '</td>' +
        '</tr>';
      }).join('');
  }

  // ---------- trend chart (stacked annual bars, inline SVG) ----------
  var SCHEME_COLOURS = {
    ro: 'var(--c-ro)', fit: 'var(--c-fit)', cfd_renewable: 'var(--c-cfdr)',
    cfd_low_carbon: 'var(--c-cfdl)', constraints: 'var(--c-con)',
    capacity_market: 'var(--c-cm)', ccl: 'var(--c-ccl)', ets: 'var(--c-ets)',
    tnuos: 'var(--c-tnuos)', bsuos: 'var(--c-bsuos)'
  };
  var STACK_ORDER = [
    'ro', 'fit', 'cfd_renewable', 'cfd_low_carbon', 'constraints',
    'capacity_market', 'ccl', 'ets', 'tnuos', 'bsuos'
  ];
  function isIndirectScheme(id) {
    var s = schemesById[id];
    return !!s && s.layer === 'indirect';
  }

  function renderChart() {
    var currentYear = new Date(generatedAt).getUTCFullYear();
    var firstYear = 2002;
    var memberIds = STACK_ORDER.filter(function (id) {
      var s = schemesById[id];
      if (!s || !timeseries.schemes[id]) return false;
      if (s.layer === 'indirect') return true; // estimated indirect costs join every perspective
      return s.perspectives.indexOf(state.perspective) !== -1;
    });

    var years = [];
    for (var y = firstYear; y <= currentYear; y++) years.push(y);

    var valueBySchemeYear = {};
    memberIds.forEach(function (id) {
      var m = {};
      timeseries.schemes[id].annual.forEach(function (a) { m[a.year] = annualCost(a); });
      valueBySchemeYear[id] = m;
    });

    var maxStack = 0, minStack = 0;
    years.forEach(function (yr) {
      var pos = 0, neg = 0;
      memberIds.forEach(function (id) {
        var v = valueBySchemeYear[id][yr] || 0;
        if (v >= 0) pos += v; else neg += v;
      });
      if (pos > maxStack) maxStack = pos;
      if (neg < minStack) minStack = neg;
    });

    // nice tick step: 1/2/5 × 10^n giving 4–7 gridlines
    var rawStep = maxStack > 0 ? maxStack / 5 : 1;
    var mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var step = [1, 2, 5, 10].map(function (m) { return m * mag; })
      .filter(function (s) { return s >= rawStep; })[0] || 10 * mag;
    var yMax = maxStack > 0 ? Math.ceil(maxStack / step) * step : step;
    var yMin = minStack < 0 ? -Math.ceil(-minStack / step * 4) * step / 4 : 0;

    var W = 940, H = 360, mL = 52, mR = 8, mT = 12, mB = 30;
    var plotW = W - mL - mR, plotH = H - mT - mB;
    function yPos(v) { return mT + plotH * (1 - (v - yMin) / (yMax - yMin)); }
    var bandW = plotW / years.length;
    var barW = bandW * 0.72;

    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Annual subsidy cost by scheme, direct and estimated indirect, ' + firstYear + ' to ' + currentYear + '">';

    var indirectIds = memberIds.filter(isIndirectScheme);

    for (var g = 0; g <= yMax; g += step) {
      var gy = yPos(g);
      svg += '<line class="gridline" x1="' + mL + '" y1="' + gy.toFixed(1) + '" x2="' + (W - mR) + '" y2="' + gy.toFixed(1) + '"/>';
      svg += '<text class="axis-label" x="' + (mL - 8) + '" y="' + (gy + 3.5).toFixed(1) + '" text-anchor="end">' +
        (g === 0 ? '£0' : '£' + (g / 1e9) + 'bn') + '</text>';
    }
    var zeroY = yPos(0);
    svg += '<line class="zeroline" x1="' + mL + '" y1="' + zeroY.toFixed(1) + '" x2="' + (W - mR) + '" y2="' + zeroY.toFixed(1) + '"/>';

    years.forEach(function (yr, i) {
      var x = mL + bandW * i + (bandW - barW) / 2;
      var posAcc = 0, negAcc = 0;
      var partial = yr === currentYear ? ' class="partial"' : '';
      memberIds.forEach(function (id) {
        var v = valueBySchemeYear[id][yr] || 0;
        if (v === 0) return;
        var y0, h;
        if (v > 0) { y0 = yPos(posAcc + v); h = yPos(posAcc) - y0; posAcc += v; }
        else { y0 = yPos(negAcc); h = yPos(negAcc + v) - y0; negAcc += v; }
        if (h < 0.1) return;
        var indirect = isIndirectScheme(id);
        svg += '<rect' + partial + ' x="' + x.toFixed(1) + '" y="' + y0.toFixed(1) +
          '" width="' + barW.toFixed(1) + '" height="' + h.toFixed(1) +
          '" fill="' + SCHEME_COLOURS[id] + '">' +
          '<title>' + esc(schemesById[id].label) + (indirect ? ' (indirect, estimated)' : '') +
          ', ' + yr + (yr === currentYear ? ' (partial)' : '') +
          ': ' + fmtCompact(v) + '</title></rect>';
      });
      if (yr % 4 === 2 || yr === currentYear) {
        svg += '<text class="axis-label" x="' + (mL + bandW * i + bandW / 2).toFixed(1) + '" y="' + (H - 10) +
          '" text-anchor="middle">' + yr + (yr === currentYear ? '*' : '') + '</text>';
      }
    });
    svg += '</svg>';

    document.getElementById('trend-chart').innerHTML = svg;
    document.getElementById('trend-note').textContent =
      'Annual cost by scheme, ' + firstYear + '–' + currentYear +
      '. Warm bars are measured direct subsidies; cool blue bars are estimated indirect costs.' +
      ' *' + currentYear + ' is a partial year (data to date).';
    var directIds = memberIds.filter(function (id) { return !isIndirectScheme(id); });
    function legendItem(id) {
      return '<span><span class="swatch" style="background:' + SCHEME_COLOURS[id] + '"></span>' +
        esc(schemesById[id].label) + '</span>';
    }
    document.getElementById('trend-legend').innerHTML =
      '<span class="legend-group">Direct (measured)</span>' + directIds.map(legendItem).join('') +
      '<span class="legend-group">Indirect (estimated)</span>' + indirectIds.map(legendItem).join('');
  }

  // ---------- share-of-bill chart (subsidy stacked under "all other costs") ----------
  function renderShareChart() {
    var section = document.getElementById('share-of-bill');
    var bill = timeseries.electricity_bill;
    if (!bill || !bill.annual || !bill.annual.length || !timeseries.indirect) {
      section.hidden = true;
      return;
    }
    section.hidden = false;

    function billCost(a) { return state.real ? a.total_bill_gbp_2024 : a.total_bill_gbp; }
    var billByYear = {}, directByYear = {}, indirectByYear = {};
    bill.annual.forEach(function (a) { billByYear[a.year] = billCost(a); });
    timeseries.perspectives[state.perspective].annual.forEach(function (a) {
      directByYear[a.year] = annualCost(a);
    });
    timeseries.indirect.annual.forEach(function (a) { indirectByYear[a.year] = annualCost(a); });

    // complete years: present in the bill series (the denominator gates coverage)
    var years = bill.annual.map(function (a) { return a.year; })
      .filter(function (y) { return billByYear[y] > 0; })
      .sort(function (a, b) { return a - b; });
    var firstYear = years[0], lastYear = years[years.length - 1];

    var rows = years.map(function (y) {
      var direct = Math.max(0, directByYear[y] || 0);
      var indirect = Math.max(0, indirectByYear[y] || 0);
      var billV = billByYear[y] || 0;
      return { year: y, direct: direct, indirect: indirect,
               other: Math.max(0, billV - direct - indirect), bill: billV };
    });

    var maxBill = rows.reduce(function (m, r) { return r.bill > m ? r.bill : m; }, 0);
    var rawStep = maxBill > 0 ? maxBill / 5 : 1;
    var mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var step = [1, 2, 5, 10].map(function (m) { return m * mag; })
      .filter(function (s) { return s >= rawStep; })[0] || 10 * mag;
    var yMax = maxBill > 0 ? Math.ceil(maxBill / step) * step : step;

    var W = 940, H = 360, mL = 52, mR = 8, mT = 12, mB = 30;
    var plotW = W - mL - mR, plotH = H - mT - mB;
    function yPos(v) { return mT + plotH * (1 - v / yMax); }
    var bandW = plotW / rows.length, barW = bandW * 0.72;

    var lowCarbon = state.perspective === 'low_carbon';
    var subsidyLabel = lowCarbon ? 'Low-carbon energy' : 'Renewable-energy';

    var DIRECT = 'var(--c-ro)', HATCH = 'var(--c-cm)', OTHER = 'var(--c-other)';
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + (lowCarbon ? 'Low-carbon energy' : 'Renewable') + ' subsidy as a share of the total electricity bill, ' + firstYear + ' to ' + lastYear + '">';
    svg += '<defs><pattern id="share-hatch" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">' +
      '<line x1="0" y1="0" x2="0" y2="5" stroke="' + HATCH + '" stroke-width="1.8"/></pattern></defs>';

    for (var g = 0; g <= yMax; g += step) {
      var gy = yPos(g);
      svg += '<line class="gridline" x1="' + mL + '" y1="' + gy.toFixed(1) + '" x2="' + (W - mR) + '" y2="' + gy.toFixed(1) + '"/>';
      svg += '<text class="axis-label" x="' + (mL - 8) + '" y="' + (gy + 3.5).toFixed(1) +
        '" text-anchor="end">' + (g === 0 ? '£0' : '£' + (g / 1e9) + 'bn') + '</text>';
    }

    rows.forEach(function (r, i) {
      var x = mL + bandW * i + (bandW - barW) / 2;
      var acc = 0;
      [['direct', DIRECT, ' direct subsidy'],
       ['indirect', 'url(#share-hatch)', ' indirect subsidy (estimated)'],
       ['other', OTHER, ' all other costs']].forEach(function (seg) {
        var v = r[seg[0]];
        if (v <= 0) return;
        var y0 = yPos(acc + v), h = yPos(acc) - y0;
        acc += v;
        if (h < 0.1) return;
        var stroke = seg[0] === 'indirect' ? ' stroke="' + HATCH + '" stroke-width="0.7"' : '';
        var pct = r.bill > 0 ? Math.round(100 * v / r.bill) : 0;
        svg += '<rect x="' + x.toFixed(1) + '" y="' + y0.toFixed(1) + '" width="' + barW.toFixed(1) +
          '" height="' + h.toFixed(1) + '" fill="' + seg[1] + '"' + stroke + '>' +
          '<title>' + r.year + seg[2] + ': ' + fmtCompact(v) + ' (' + pct + '% of bill)</title></rect>';
      });
      if (r.year % 4 === 2 || r.year === lastYear) {
        svg += '<text class="axis-label" x="' + (mL + bandW * i + bandW / 2).toFixed(1) +
          '" y="' + (H - 10) + '" text-anchor="middle">' + r.year + '</text>';
      }
    });
    svg += '</svg>';
    document.getElementById('share-chart').innerHTML = svg;

    var last = rows[rows.length - 1];
    var share = last.bill > 0 ? Math.round(100 * (last.direct + last.indirect) / last.bill) : 0;
    document.getElementById('share-caption').textContent =
      last.year + ': ' + subsidyLabel.toLowerCase() + ' subsidies were about ' + share +
      '% of the total UK electricity bill' + (state.real ? ' (2024 prices).' : '.');

    document.getElementById('share-note').textContent =
      subsidyLabel + ' subsidy as a share of total UK electricity consumer expenditure (DUKES 1.3), ' +
      firstYear + '–' + lastYear + '. The subsidy is a conservative lower bound, so the share is too. ' +
      (state.real ? 'Figures in 2024 prices. ' : '') +
      'High-price years (the 2022–23 energy spike) raise the denominator and lower the share even as subsidy rises.';

    document.getElementById('share-legend').innerHTML =
      '<span><span class="swatch" style="background:' + DIRECT + '"></span>Direct subsidy</span>' +
      '<span><span class="swatch swatch-hatch" style="background-image:repeating-linear-gradient(45deg,' +
        HATCH + ' 0,' + HATCH + ' 1.5px,transparent 1.5px,transparent 4px);border-color:' + HATCH + '"></span>Indirect subsidy (estimated)</span>' +
      '<span><span class="swatch" style="background:' + OTHER + '"></span>All other costs</span>';
  }

  // ---------- footer ----------
  function renderFooter() {
    var d = new Date(generatedAt);
    document.getElementById('generated-at').textContent =
      'Figures computed ' + d.toLocaleString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric',
        hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short'
      }) + '.';
    // a warning that is always visible is furniture: only speak when something is stale
    var stale = breakdown.schemes.filter(isStale);
    document.getElementById('freshness').innerHTML = stale.length
      ? '<span class="stale-warning">Data for ' + stale.map(function (s) { return esc(s.label); }).join(', ') +
        ' is older than its normal publication lag \u2014 details on the <a href="methodology.html#freshness">methodology page</a>.</span>'
      : '';
  }

  // ---------- share (hero row): the one share mechanism ----------
  // The viral unit is fact + picture + link. Intents carry the live figure
  // (floored to £0.1bn) and the bare site URL - the clean link a reader
  // trusts; the homepage's own OG tags serve the daily total card.
  // share.js still owns GoatCounter and the copy/track helpers; its attach()
  // per-card component is deliberately unwired (share-UX rework, 2026-06-12).
  var SITE_URL = 'https://subsidyclock.co.uk';
  var SHARE_URL = SITE_URL + '/';

  function svgIcon(d) {
    return '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" aria-hidden="true"><path d="' + d + '"/></svg>';
  }
  var SHARE_ICONS = {
    x:        svgIcon('M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z'),
    whatsapp: svgIcon('M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z'),
    facebook: svgIcon('M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z'),
    linkedin: svgIcon('M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z'),
    native: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M8 1v9M5 3.5 8 1l3 2.5M3 7v7h10V7"/></svg>'
  };

  function shareText() {
    // floored to £0.1bn: "more than" stays strictly true, and the text can
    // never visibly disagree with the daily card's full-precision snapshot.
    // The bracketed full-cost figure is the same I1 real-2024 floor the hero
    // lead-in quotes - 'in today's money' travels with it (integrity rule).
    var bn = Math.floor(liveCumulative(Date.now()) / 1e8) / 10;
    var full = hasCombinedReal()
      ? ' (over £' + (combinedRealFlooredGbp() / 1e9) +
        ' billion in today\u2019s money with estimated indirect costs)'
      : '';
    return 'More than £' + bn.toFixed(1) + ' billion' + full +
      ' — paid to renewable electricity generators by Great Britain’s bill-payers since ' +
      totals.perspectives.renewables.since_year;
  }

  function canShareFiles() {
    try {
      return !!(navigator.canShare &&
        navigator.canShare({ files: [new File([''], 't.png', { type: 'image/png' })] }));
    } catch (e) { return false; }
  }

  function intentUrl(target) {
    var encT = encodeURIComponent(shareText());
    var encU = encodeURIComponent(SHARE_URL);
    if (target === 'x') return 'https://twitter.com/intent/tweet?text=' + encT + '&url=' + encU;
    if (target === 'whatsapp') return 'https://wa.me/?text=' + encT + '%20' + encU;
    if (target === 'facebook') return 'https://www.facebook.com/sharer/sharer.php?u=' + encU;
    return 'https://www.linkedin.com/sharing/share-offsite/?url=' + encU;
  }

  function nativeShare() {
    // fetch the daily card so the OS share sheet carries the picture
    // (the Instagram/iMessage path); fall back to text+url on any failure.
    fetch('share/total.png')
      .then(function (r) { if (!r.ok) throw new Error('' + r.status); return r.blob(); })
      .then(function (b) {
        var payload = { text: shareText(), url: SHARE_URL,
                        files: [new File([b], 'subsidy-clock.png', { type: 'image/png' })] };
        if (!navigator.canShare(payload)) payload = { text: shareText(), url: SHARE_URL };
        return navigator.share(payload);
      })
      .catch(function () {
        if (navigator.share) {
          navigator.share({ text: shareText(), url: SHARE_URL }).catch(function () {});
        }
      });
    SCShare.track('share:hero:native');
  }

  function sharePill(label, icon) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'hero-share-pill';
    b.innerHTML = SHARE_ICONS[icon] + label;
    return b;
  }

  function initHeroShare() {
    SCShare.initTracking();
    var row = document.getElementById('hero-share');
    if (!row) return;
    if (canShareFiles()) {
      var nb = sharePill('Share…', 'native');
      nb.addEventListener('click', nativeShare);
      row.appendChild(nb);
      return;
    }
    [['X', 'x'], ['WhatsApp', 'whatsapp'], ['Facebook', 'facebook'], ['LinkedIn', 'linkedin']]
      .forEach(function (t) {
        var b = sharePill(t[0], t[1]);
        b.addEventListener('click', function () {
          // open synchronously inside the click handler - popup blockers
          window.open(intentUrl(t[1]), '_blank', 'noopener');
          SCShare.track('share:hero:' + t[1]);
        });
        row.appendChild(b);
      });
  }

  // ---------- wiring ----------
  function renderAll() {
    renderHeroStatic();
    renderEquivalences();
    renderSchemeBars();
    renderChart();
    renderShareChart();
    renderCategoryCards();
    renderStripExtras();
  }

  // ---------- first paint ----------
  renderAll();
  renderSwitchOff();
  renderTechBars();
  renderRecipients();
  renderFooter();
  initHeroShare();
  rafId = requestAnimationFrame(tick);

})();
