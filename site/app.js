/* The Subsidy Counter — dashboard logic. No dependencies. */
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
  var state = { perspective: 'renewables', framing: 'all_time', real: false };

  var PERSPECTIVE_TEXT = {
    renewables: {
      subtitle: function (y) { return 'paid to renewable electricity generators by Great Britain’s bill-payers since ' + y; },
      copyNoun: 'UK renewable-energy subsidies',
      schemesNote: 'renewables perspective'
    },
    low_carbon: {
      subtitle: function (y) { return 'paid to low-carbon electricity generators (including nuclear and biomass) by Great Britain’s bill-payers since ' + y; },
      copyNoun: 'UK low-carbon electricity subsidies',
      schemesNote: 'low-carbon perspective'
    }
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
  function liveIndirect(t) {
    var v = iv();
    if (!v) return null;
    return v.cumulative_gbp + v.rate_gbp_per_sec * (t - generatedAt) / 1000;
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
    var p = pv();
    var ind = iv();
    var sinceYear = persp().since_year;
    var unitEl = document.getElementById('hero-unit');
    var valEl = document.getElementById('hero-value');
    var combVal = document.getElementById('hero-combined-value');
    var fnEl = document.querySelector('.hero-fn');
    var footEl = document.querySelector('.hero-footnote');
    var isLive = state.framing === 'all_time';
    fnEl.style.visibility = isLive ? 'visible' : 'hidden';
    footEl.style.visibility = isLive ? 'visible' : 'hidden';
    if (state.framing === 'all_time') {
      valEl.textContent = fmtFull(liveCumulative(Date.now()));
      unitEl.textContent = '';
    } else if (state.framing === 'runrate') {
      valEl.textContent = fmtFull(p.runrate_gbp_per_year);
      unitEl.textContent = 'per year at the current run-rate';
    } else if (state.framing === 'household') {
      valEl.textContent = fmtPence(p.per_household_per_year_gbp);
      unitEl.textContent = 'per household per year';
    } else {
      valEl.textContent = fmtPence(p.per_mwh_delivered_gbp);
      unitEl.textContent = 'per MWh of electricity delivered';
    }
    document.getElementById('hero-combined').hidden = !ind;
    if (ind) {
      if (state.framing === 'all_time') {
        combVal.textContent = fmtFull(liveCumulative(Date.now()) + liveIndirect(Date.now()));
      } else if (state.framing === 'runrate') {
        combVal.textContent = fmtFull(p.runrate_gbp_per_year + ind.runrate_gbp_per_year);
      } else if (state.framing === 'household') {
        combVal.textContent = fmtPence(p.per_household_per_year_gbp + ind.per_household_per_year_gbp);
      } else {
        combVal.textContent = fmtPence(p.per_mwh_delivered_gbp + ind.per_mwh_delivered_gbp);
      }
    }
    document.getElementById('real-tag').hidden = !state.real;
    document.getElementById('hero-sub').textContent =
      PERSPECTIVE_TEXT[state.perspective].subtitle(sinceYear);
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
    heroCombined: document.getElementById('hero-combined-value'),
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
    if (state.framing === 'all_time') {
      els.heroValue.textContent = fmtFull(liveCumulative(t));
      var indLive = liveIndirect(t);
      if (indLive != null) {
        els.heroCombined.textContent = fmtFull(liveCumulative(t) + indLive);
      }
    }
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
    document.getElementById('schemes-perspective-note').textContent =
      PERSPECTIVE_TEXT[state.perspective].schemesNote;
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

  // ---------- the indirect bill ----------
  var INDIRECT_EXTRA_NOTE = {
    capacity_market: 'Previously shown in this dashboard’s all-levy total.'
  };

  function renderIndirectBars() {
    var comps = breakdown.schemes
      .filter(function (s) { return s.layer === 'indirect'; })
      .slice()
      .sort(function (a, b) { return schemeCumulative(b) - schemeCumulative(a); });
    var section = document.getElementById('indirect-bill');
    if (!comps.length) { section.hidden = true; return; }
    section.hidden = false;
    var max = Math.max.apply(null, comps.map(function (s) { return Math.abs(schemeCumulative(s)); }));
    document.getElementById('indirect-bars').innerHTML = comps.map(function (s) {
      var stale = isStale(s);
      var v = schemeCumulative(s);
      var w = Math.max(0.4, 100 * Math.abs(v) / max);
      // The stored note's leading housekeeping sentence is methodology detail;
      // the dashboard shows the factual attribution rule.
      var note = String(s.attribution_note || '')
        .replace(/^Raw totals stored; attribution happens in the money model\.\s*/, '');
      if (s.attribution_pct < 1) {
        note = Math.round(s.attribution_pct * 100) + '% of the raw cost attributed. ' + note;
      }
      if (INDIRECT_EXTRA_NOTE[s.id]) {
        if (note && !/[.!?]$/.test(note)) note += '.';
        note += ' ' + INDIRECT_EXTRA_NOTE[s.id];
      }
      var conf = String(s.attribution_confidence || 'low');
      return '<div class="bar-row">' +
        '<div class="bar-head">' +
          '<span class="bar-name">' + esc(s.label) + '</span>' +
          '<span class="badge" title="Update cadence and latest data date">' + esc(s.cadence) + ' · to ' + fmtDate(s.data_to) + '</span>' +
          (stale ? '<span class="badge badge-stale" title="Latest data is older than this scheme’s normal publication lag">stale</span>' : '') +
          '<span class="badge badge-conf-high" title="How well the underlying amount is measured">amount: high</span>' +
          '<span class="badge badge-conf-' + esc(conf) + '" title="How firmly this cost is attributable to renewables">attribution: ' + esc(conf) + '</span>' +
          '<span class="bar-amount money num">' + fmtCompact(v) + '</span>' +
        '</div>' +
        '<div class="bar-track"><div class="bar-fill bar-fill-indirect" style="width:' + w.toFixed(2) + '%"></div></div>' +
        '<p class="attr-note"><span class="num">' + fmtCompact(schemeRunrate(s)) + '</span> per year at the current run-rate. ' + esc(note) + '</p>' +
      '</div>';
    }).join('');
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

    // hatched fills for the indirect (estimated) layer
    var indirectIds = memberIds.filter(isIndirectScheme);
    svg += '<defs>' + indirectIds.map(function (id) {
      return '<pattern id="hatch-' + id + '" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">' +
        '<line x1="0" y1="0" x2="0" y2="5" stroke="' + SCHEME_COLOURS[id] + '" stroke-width="1.8"/>' +
      '</pattern>';
    }).join('') + '</defs>';

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
        var fill = indirect ? 'url(#hatch-' + id + ')' : SCHEME_COLOURS[id];
        var stroke = indirect ? ' stroke="' + SCHEME_COLOURS[id] + '" stroke-width="0.7"' : '';
        svg += '<rect' + partial + ' x="' + x.toFixed(1) + '" y="' + y0.toFixed(1) +
          '" width="' + barW.toFixed(1) + '" height="' + h.toFixed(1) +
          '" fill="' + fill + '"' + stroke + '>' +
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
      'Annual cost by scheme for the selected perspective, ' + firstYear + '–' + currentYear +
      '. Solid bars are direct subsidies; hatched bars are estimated indirect costs.' +
      (state.real ? ' Figures in 2024 prices.' : '') +
      ' *' + currentYear + ' is a partial year (data to date).';
    var directIds = memberIds.filter(function (id) { return !isIndirectScheme(id); });
    function legendItem(id) {
      var col = SCHEME_COLOURS[id];
      var swatch = isIndirectScheme(id)
        ? '<span class="swatch swatch-hatch" style="background-image:repeating-linear-gradient(45deg,' + col + ' 0,' + col + ' 1.5px,transparent 1.5px,transparent 4px);border-color:' + col + '"></span>'
        : '<span class="swatch" style="background:' + col + '"></span>';
      return '<span>' + swatch + esc(schemesById[id].label) + '</span>';
    }
    document.getElementById('trend-legend').innerHTML =
      '<span class="legend-group">Direct</span>' + directIds.map(legendItem).join('') +
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

    var DIRECT = 'var(--c-ro)', HATCH = 'var(--c-cfdr)', OTHER = 'var(--c-other)';
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Renewable subsidy as a share of the total electricity bill, ' + firstYear + ' to ' + lastYear + '">';
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
      last.year + ': renewable-energy subsidies were about ' + share +
      '% of the total UK electricity bill' + (state.real ? ' (2024 prices).' : '.');

    document.getElementById('share-note').textContent =
      'Renewable-energy subsidy as a share of total UK electricity consumer expenditure (DUKES 1.3), ' +
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
    var labels = { cfd: 'CfD (LCCC)', constraints: 'Constraints (Elexon)', capacity_market: 'Capacity Market (LCCC)', bsuos: 'BSUoS (NESO)' };
    document.getElementById('freshness').innerHTML =
      Object.keys(meta.freshness).map(function (k) {
        var f = meta.freshness[k];
        return '<span><a href="' + esc(f.source_url) + '">' + esc(labels[k] || k) + '</a>' +
          ' retrieved ' + fmtDate(f.retrieved_at) +
          ' · <span class="num">' + fmtInt(f.row_count) + '</span> rows</span>';
      }).join('');
  }

  // ---------- copy figure ----------
  function copyFigure() {
    var t = Date.now();
    var indLive = liveIndirect(t);
    var text = fmtFull(liveCumulative(t)) + ' paid in ' +
      PERSPECTIVE_TEXT[state.perspective].copyNoun + ' since ' + persp().since_year +
      (state.real ? ' (2024 prices)' : '') +
      (indLive != null ? ', plus an estimated ' + fmtFull(indLive) + ' in indirect costs' : '') +
      ' — sources: LCCC, Ofgem, Elexon, NESO, HMRC, REF';
    var btn = document.getElementById('copy-figure');
    function done() {
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = 'Copy figure'; }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copy this figure:', text); });
    } else {
      window.prompt('Copy this figure:', text);
    }
  }

  // ---------- wiring ----------
  function renderPerspective() {
    renderHeroStatic();
    renderEquivalences();
    renderSchemeBars();
    renderChart();
    renderShareChart();
  }

  function renderBasis() {
    document.querySelectorAll('.nominal-tag').forEach(function (el) { el.hidden = !state.real; });
    renderPerspective();
    renderIndirectBars();
    renderSwitchOff();
  }

  document.getElementById('perspective-switch').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-perspective]');
    if (!btn || btn.dataset.perspective === state.perspective) return;
    state.perspective = btn.dataset.perspective;
    this.querySelectorAll('button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });
    renderPerspective();
  });

  document.getElementById('real-switch').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-basis]');
    if (!btn) return;
    var real = btn.dataset.basis === 'real';
    if (real === state.real) return;
    state.real = real;
    this.querySelectorAll('button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });
    renderBasis();
  });

  document.getElementById('framing-switch').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-framing]');
    if (!btn || btn.dataset.framing === state.framing) return;
    state.framing = btn.dataset.framing;
    this.querySelectorAll('button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });
    renderHeroStatic();
  });

  document.getElementById('copy-figure').addEventListener('click', copyFigure);

  // ---------- first paint ----------
  renderPerspective();
  renderIndirectBars();
  renderSwitchOff();
  renderTechBars();
  renderRecipients();
  renderFooter();
  rafId = requestAnimationFrame(tick);

})();
