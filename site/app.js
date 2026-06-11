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
  function renderHeroStatic() {
    var sinceYear = persp().since_year;
    document.getElementById('hero-value').textContent = fmtFull(liveCumulative(Date.now()));
    document.getElementById('hero-sub').textContent =
      'paid to renewable electricity generators by Great Britain\u2019s bill-payers since ' + sinceYear;
    var lc = totals.perspectives.low_carbon;
    if (lc) {
      var delta = lc.cumulative_gbp - totals.perspectives.renewables.cumulative_gbp;
      document.getElementById('hero-delta').innerHTML =
        'Under the same schemes, nuclear and biomass received a further <span class="money num">' +
        fmtCompact(delta) + '</span> \u2014 <a href="methodology.html#perspectives">see the methodology page</a>.';
    }
    // F8: the combined total must register - floored to the nearest \u00a310bn
    // STRICTLY BELOW the combined figure (a floor, never a midpoint), so the
    // sentence understates by construction. No second ticking numeral.
    if (indirectTotals) {
      var combined = totals.perspectives.renewables.cumulative_gbp + indirectTotals.cumulative_gbp;
      var flooredBn = Math.floor(combined / 1e10) * 1e10;
      if (flooredBn === combined) flooredBn -= 1e10; // exact boundary: step down
      document.getElementById('hero-direct-note').innerHTML =
        '<strong>This is the direct bill alone.</strong> Adding estimated indirect costs ' +
        '\u2014 backup, balancing and the grid \u2014 takes the true total above ' +
        '<span class="money num">\u00a3' + (flooredBn / 1e9) + ' billion</span>. ' +
        '<a href="#indirect-bill">The indirect bill \u2193</a>';
    }
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

  // ---------- share/cite (distribution F2): the facts registry ----------
  // Anchors are the public citation contract - never rename without redirect.
  // url: /s/ stubs exist for the four headline facts (per-fact OG preview);
  // other cards share the canonical anchor URL (homepage card preview).
  var SITE_URL = 'https://subsidyclock.co.uk';
  var asofShort = fmtDate(totals.generated_at);
  function stub(slug) { return SITE_URL + '/s/' + slug; }
  function anchorUrl(a) { return SITE_URL + '/#' + a; }

  function shareFacts() {
    var sinceYear = totals.perspectives.renewables.since_year;
    var con = schemesById.constraints;
    var facts = [
      { id: 'total', title: 'The Subsidy Clock', anchor: 'total', url: stub('total'),
        png: 'share/total.png', csv: 'data/combined-annual.csv',
        label: 'paid to renewable electricity generators by Great Britain’s bill-payers since ' + sinceYear,
        figure: function () { return fmtFull(liveCumulative(Date.now())); },
        container: document.querySelector('#total .since-opened') },
      { id: 'direct-bill', title: 'The direct bill', anchor: 'direct-bill',
        url: anchorUrl('direct-bill'), png: null, csv: 'data/combined-annual.csv',
        label: 'direct renewable-energy subsidy since ' + sinceYear,
        figure: function () { return fmtCompact(pv().cumulative_gbp); },
        container: document.getElementById('direct-bill') },
      { id: 'indirect-bill', title: 'The indirect bill (estimated)', anchor: 'indirect-bill',
        url: anchorUrl('indirect-bill'), png: null, csv: 'data/combined-annual.csv',
        label: 'estimated indirect costs of renewables — backup, balancing and the grid',
        figure: function () { var i = iv(); return i ? fmtCompact(i.cumulative_gbp) : '—'; },
        container: document.getElementById('indirect-bill') },
      { id: 'by-scheme', title: 'By scheme', anchor: 'by-scheme',
        url: anchorUrl('by-scheme'), png: null, csv: 'data/combined-annual.csv',
        label: 'cumulative cost of each direct support scheme',
        figure: function () { return fmtCompact(pv().cumulative_gbp); },
        container: document.getElementById('by-scheme') },
      { id: 'by-technology', title: 'By technology (CfD schemes)', anchor: 'by-technology',
        url: anchorUrl('by-technology'), png: null, csv: 'data/cfd.csv',
        label: 'net Contracts for Difference payments by technology',
        figure: function () { var s = schemesById.cfd_renewable; return s ? fmtCompact(schemeCumulative(s)) : '—'; },
        container: document.getElementById('by-technology') },
      { id: 'recipients', title: 'Largest recipients', anchor: 'recipients',
        url: anchorUrl('recipients'), png: null, csv: null,
        label: 'largest recipients of CfD and constraint payments',
        figure: function () { return fmtCompact(pv().cumulative_gbp); },
        container: document.getElementById('recipients') },
      { id: 'cost-per-year', title: 'Cost per year, by scheme', anchor: 'cost-per-year',
        url: anchorUrl('cost-per-year'), png: null, csv: 'data/combined-annual.csv',
        label: 'annual subsidy cost by scheme since 2002',
        figure: function () { return fmtCompact(pv().cumulative_gbp); },
        container: document.getElementById('cost-per-year') },
      { id: 'share-of-bill', title: 'Subsidy as a share of the electricity bill',
        anchor: 'share-of-bill', url: anchorUrl('share-of-bill'), png: null, csv: null,
        label: 'renewable subsidy as a share of total UK electricity expenditure',
        figure: function () { return document.getElementById('strip-share').textContent; },
        container: document.getElementById('share-of-bill') }
    ];
    if (con) {
      facts.push({ id: 'switch-off', title: 'Paid to switch off', anchor: 'switch-off',
        url: stub('switch-off'), png: 'share/switch-off.png', csv: 'data/constraints.csv',
        label: 'paid to wind farms to reduce output when the grid could not carry their electricity',
        figure: function () { return fmtCompact(schemeCumulative(con)); },
        container: document.getElementById('switch-off') });
    }
    return facts;
  }

  function initShare() {
    SCShare.initTracking();
    shareFacts().forEach(function (f) {
      if (f.container) SCShare.attach(f.container, f, asofShort);
    });
  }

  // ---------- copy figure (hero instance of the share component) ----------
  function copyFigure() {
    var text = fmtFull(liveCumulative(Date.now())) +
      ' paid in UK renewable-energy subsidies since ' + persp().since_year +
      ' \u2014 sources: LCCC, Ofgem, Elexon, NESO, HMRC, REF \u00b7 subsidyclock.co.uk';
    var btn = document.getElementById('copy-figure');
    SCShare.copyText(text, function () {
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = 'Copy figure'; }, 1600);
    });
    SCShare.track('share:total:copy-figure');
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

  document.getElementById('copy-figure').addEventListener('click', copyFigure);

  // ---------- first paint ----------
  renderAll();
  renderSwitchOff();
  renderTechBars();
  renderRecipients();
  renderFooter();
  initShare();
  rafId = requestAnimationFrame(tick);

})();
