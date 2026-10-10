(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  function bn(v) { return v >= 1e9 ? '£' + (v / 1e9).toFixed(2) + 'bn' : '£' + Math.round(v / 1e6).toLocaleString('en-GB') + 'm'; }
  function m(v) { return '£' + (v / 1e6).toFixed(v < 1e7 ? 1 : 0) + 'm'; }
  function int(v) { return Math.round(v).toLocaleString('en-GB'); }
  function pct(v) { return (v * 100).toFixed(0) + '%'; }
  function date(iso) { return new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function chart(rows, width) {
    var W = Math.max(320, Math.min(760, width)), H = W < 500 ? 200 : 240, L = 46, B = 22, T = 8, n = rows.length;
    var max = Math.max.apply(null, rows.map(function (r) { return r.scotland + r.rest; }));
    var step = Math.pow(10, Math.floor(Math.log10(max / 1e6))) * 1e6;
    var top = Math.ceil(max / step) * step; if (top / step > 6) { step *= 2; top = Math.ceil(max / step) * step; }
    var bw = (W - L) / n, y = function (v) { return T + (H - T - B) * (1 - v / top); };
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" class="sc-svg">';
    for (var g = 0; g <= top + 1; g += step) {
      s += '<line x1="' + L + '" x2="' + W + '" y1="' + y(g) + '" y2="' + y(g) + '" stroke="var(--line-soft)"/>' +
        '<text x="' + (L - 6) + '" y="' + (y(g) + 4) + '" text-anchor="end" class="sc-ax">£' + Math.round(g / 1e6) + 'm</text>';
    }
    rows.forEach(function (r, i) {
      var x = L + i * bw + bw * 0.12, w = bw * 0.76;
      s += '<rect x="' + x + '" width="' + w + '" y="' + y(r.scotland) + '" height="' + (y(0) - y(r.scotland)) + '" fill="var(--c-con)"><title>' + r.month + ': Scotland ' + m(r.scotland) + ', rest of GB ' + m(r.rest) + '</title></rect>';
      if (r.rest > 0) s += '<rect x="' + x + '" width="' + w + '" y="' + y(r.scotland + r.rest) + '" height="' + (y(r.scotland) - y(r.scotland + r.rest)) + '" fill="var(--faint)"/>';
      if (r.month.slice(5) === '01') s += '<text x="' + (x + w / 2) + '" y="' + (H - 6) + '" text-anchor="middle" class="sc-ax">' + r.month.slice(0, 4) + '</text>';
    });
    return s + '</svg>';
  }

  fetch('data/scotland.json').then(function (r) { return r.json(); }).then(function (d) {
    $('sc-total').textContent = bn(d.scotland_cost);
    $('sc-total-label').textContent = 'paid to Scottish wind farms to switch off since ' + date(d.window.from);
    $('sc-share').textContent = pct(d.scotland_share);
    $('sc-12m').textContent = bn(d.scotland_last12_cost);
    $('sc-from').textContent = date(d.window.from);
    var last = d.monthly[d.monthly.length - 1];
    var months = d.monthly.filter(function (r, i) { return i > 0; });           // first month is part-recorded
    if (last && last.month === d.window.to.slice(0, 7) && d.window.to.slice(8) < '28') months = months.slice(0, -1);
    var draw = function () { $('sc-chart').innerHTML = chart(months, $('sc-chart').clientWidth); };
    draw(); window.addEventListener('resize', draw);

    var w = d.who_pays;
    $('sc-whopays').textContent = 'Scotland uses ' + (w.scotland_consumption_share * 100).toFixed(1) +
      '% of Great Britain’s electricity, so households and businesses in Scotland carry about ' + bn(w.paid_in_scotland) +
      ' of the ' + bn(d.scotland_cost) + '. The other ' + bn(w.paid_elsewhere) + ' falls on bill-payers in England and Wales.';
    var c = $('sc-cons-src'); c.textContent = w.source; c.href = w.source_url;

    if (d.turnup_same_window) {
      $('sc-turnup').textContent = 'Electricity a wind farm is paid not to make still has to come from somewhere, usually a gas station on the other side of the bottleneck, which is paid to generate more. The wind farm keeps what it was paid for the power it did not make, so the replacement is a second purchase of the same electricity. Over the same period that replacement cost an estimated ' +
        bn(d.turnup_same_window.cost) + ' across Great Britain, on top of the switch-off payments. This estimate is for Britain as a whole and is not split by nation.';
    }

    $('sc-table').querySelector('tbody').innerHTML = d.farms.map(function (f) {
      return '<tr><td>' + esc(f.farm) + '</td><td class="num-col">' + m(f.cost) + '</td><td class="num-col">' + int(f.mwh) + '</td></tr>';
    }).join('');
    $('sc-table-note').textContent = 'These ' + d.farms.length + ' farms took ' + pct(d.top_farms_share) + ' of the money; ' +
      d.n_farms_paid + ' Scottish wind farms were paid in all. ' + int(d.scotland_mwh / 1e6 * 10) / 10 + ' million MWh of Scottish wind was paid for and not generated, about £' +
      Math.round(d.scotland_per_mwh) + ' for each MWh. Figures to ' + date(d.window.to) + '.';
  }).catch(function () {
    $('sc-chart').textContent = 'The figures failed to load. Please reload the page.';
  });
})();
