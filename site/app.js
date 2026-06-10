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
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---------- state ----------
  var state = { perspective: 'renewables', framing: 'all_time' };

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
    },
    all_levy: {
      subtitle: function (y) { return 'paid through Great Britain’s electricity levies (including the Capacity Market) by bill-payers since ' + y; },
      copyNoun: 'UK electricity levies',
      schemesNote: 'all-levy perspective'
    }
  };

  function persp() { return totals.perspectives[state.perspective]; }
  function liveCumulative(t) {
    var p = persp();
    return p.cumulative_gbp + p.rate_gbp_per_sec * (t - generatedAt) / 1000;
  }

  // ---------- hero (static parts) ----------
  function renderHeroStatic() {
    var p = persp();
    var unitEl = document.getElementById('hero-unit');
    var valEl = document.getElementById('hero-value');
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
    document.getElementById('hero-sub').textContent =
      PERSPECTIVE_TEXT[state.perspective].subtitle(p.since_year);
    document.getElementById('strip-alltime-since').textContent = 'since ' + p.since_year;
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
    var p = persp();
    var rate = p.rate_gbp_per_sec;
    if (state.framing === 'all_time') {
      els.heroValue.textContent = fmtFull(liveCumulative(t));
    }
    els.sinceOpened.textContent = fmtPence(rate * (t - openedAt) / 1000);
    els.now.textContent = fmtPence(rate);
    els.today.textContent = fmtFull(rate * (t - startOfToday(d)) / 1000);
    els.week.textContent = fmtFull(rate * (t - startOfWeek(d)) / 1000);
    els.year.textContent = fmtCompact(rate * (t - startOfYear(d)) / 1000);
    els.alltime.textContent = fmtCompact(liveCumulative(t));
    requestAnimationFrame(tick);
  }

  // ---------- equivalences ----------
  function renderEquivalences() {
    var p = persp();
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
    document.getElementById('con-cumulative').textContent = fmtCompact(c.cumulative_gbp);
    document.getElementById('con-runrate').textContent = fmtCompact(c.runrate_gbp_per_year);
    document.getElementById('con-curtailed').textContent = fmtInt(c.curtailed_mwh);
    document.getElementById('con-curtailed-label').textContent =
      'MWh paid for and not generated, ' + fmtDate(c.bottom_up_from) + ' – ' + fmtDate(c.bottom_up_to);
    document.getElementById('con-window').textContent =
      fmtDate(c.bottom_up_from) + ' – ' + fmtDate(c.bottom_up_to);
    var rows = (c.by_recipient || []).slice(0, 8).map(function (r) {
      return '<tr><td>' + esc(r.lead_party) + '</td>' +
        '<td class="num-col money">' + fmtCompact(r.cost_gbp) + '</td>' +
        '<td class="num-col cell-dim">' + fmtInt(Math.abs(r.volume_mwh)) + '</td></tr>';
    }).join('');
    document.querySelector('#con-table tbody').innerHTML = rows;
  }

  // ---------- scheme breakdown bars ----------
  var STALE_LIMIT_MS = { daily: 2 * 864e5, monthly: 2 * 30.44 * 864e5, annual: 2 * 365.25 * 864e5 };
  function isStale(s) {
    return generatedAt - Date.parse(s.data_to) > (STALE_LIMIT_MS[s.cadence] || Infinity);
  }

  function renderSchemeBars() {
    var schemes = breakdown.schemes
      .filter(function (s) { return s.perspectives.indexOf(state.perspective) !== -1; })
      .slice()
      .sort(function (a, b) { return b.cumulative_gbp - a.cumulative_gbp; });
    var max = Math.max.apply(null, schemes.map(function (s) { return Math.abs(s.cumulative_gbp); }));
    document.getElementById('schemes-perspective-note').textContent =
      PERSPECTIVE_TEXT[state.perspective].schemesNote;
    document.getElementById('scheme-bars').innerHTML = schemes.map(function (s) {
      var stale = isStale(s);
      var w = Math.max(0.4, 100 * Math.abs(s.cumulative_gbp) / max);
      return '<div class="bar-row">' +
        '<div class="bar-head">' +
          '<span class="bar-name">' + esc(s.label) + '</span>' +
          '<span class="badge" title="Update cadence and latest data date">' + esc(s.cadence) + ' · to ' + fmtDate(s.data_to) + '</span>' +
          (stale ? '<span class="badge badge-stale" title="Latest data is older than twice this scheme’s update cadence">stale</span>' : '') +
          '<span class="bar-amount money num">' + fmtCompact(s.cumulative_gbp) + '</span>' +
        '</div>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + w.toFixed(2) + '%"></div></div>' +
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
    cfd_low_carbon: 'var(--c-cfdl)', constraints: 'var(--c-con)', capacity_market: 'var(--c-cm)'
  };
  var STACK_ORDER = ['ro', 'fit', 'cfd_renewable', 'cfd_low_carbon', 'constraints', 'capacity_market'];

  function renderChart() {
    var currentYear = new Date(generatedAt).getUTCFullYear();
    var firstYear = 2002;
    var memberIds = STACK_ORDER.filter(function (id) {
      var s = schemesById[id];
      return s && s.perspectives.indexOf(state.perspective) !== -1 && timeseries.schemes[id];
    });

    var years = [];
    for (var y = firstYear; y <= currentYear; y++) years.push(y);

    var valueBySchemeYear = {};
    memberIds.forEach(function (id) {
      var m = {};
      timeseries.schemes[id].annual.forEach(function (a) { m[a.year] = a.cost_gbp; });
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
    var rawStep = maxStack / 5;
    var mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var step = [1, 2, 5, 10].map(function (m) { return m * mag; })
      .filter(function (s) { return s >= rawStep; })[0] || 10 * mag;
    var yMax = Math.ceil(maxStack / step) * step;
    var yMin = minStack < 0 ? -Math.ceil(-minStack / step * 4) * step / 4 : 0;

    var W = 940, H = 360, mL = 52, mR = 8, mT = 12, mB = 30;
    var plotW = W - mL - mR, plotH = H - mT - mB;
    function yPos(v) { return mT + plotH * (1 - (v - yMin) / (yMax - yMin)); }
    var bandW = plotW / years.length;
    var barW = bandW * 0.72;

    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Annual subsidy cost by scheme, ' + firstYear + ' to ' + currentYear + '">';

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
        svg += '<rect' + partial + ' x="' + x.toFixed(1) + '" y="' + y0.toFixed(1) +
          '" width="' + barW.toFixed(1) + '" height="' + h.toFixed(1) +
          '" fill="' + SCHEME_COLOURS[id] + '">' +
          '<title>' + esc(schemesById[id].label) + ', ' + yr + (yr === currentYear ? ' (partial)' : '') +
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
      '. *' + currentYear + ' is a partial year (data to date).';
    document.getElementById('trend-legend').innerHTML = memberIds.map(function (id) {
      return '<span><span class="swatch" style="background:' + SCHEME_COLOURS[id] + '"></span>' +
        esc(schemesById[id].label) + '</span>';
    }).join('');
  }

  // ---------- footer ----------
  function renderFooter() {
    var d = new Date(generatedAt);
    document.getElementById('generated-at').textContent =
      'Figures computed ' + d.toLocaleString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric',
        hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short'
      }) + '.';
    var labels = { cfd: 'CfD (LCCC)', constraints: 'Constraints (Elexon)', capacity_market: 'Capacity Market (LCCC)' };
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
    var p = persp();
    var text = fmtFull(liveCumulative(Date.now())) + ' paid in ' +
      PERSPECTIVE_TEXT[state.perspective].copyNoun + ' since ' + p.since_year +
      ' — sources: LCCC, Ofgem, Elexon, REF';
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
  renderSwitchOff();
  renderTechBars();
  renderRecipients();
  renderFooter();
  requestAnimationFrame(tick);

})();
