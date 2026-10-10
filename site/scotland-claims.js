(function () {
  'use strict';
  function n(v) { return Math.round(v).toLocaleString('en-GB'); }
  function m(v) { return '£' + Math.round(v / 1e6).toLocaleString('en-GB') + 'm'; }
  function bn(v) { return '£' + (v / 1e9).toFixed(2) + 'bn'; }
  function pc(v, d) { return (v * 100).toFixed(d || 0) + '%'; }
  function gw(mw) { return (mw / 1000).toFixed(1) + ' GW'; }
  function day(iso) { return new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }); }
  function a(url, text) { return '<a href="' + url + '">' + text + '</a>'; }

  function card(i, c) {
    return '<article class="claim">' +
      '<p class="claim-n">' + i + '</p>' +
      '<p class="claim-said"><span class="claim-k">The claim</span>“' + c.claim + '”</p>' +
      '<p class="claim-answer">' + c.answer + '</p>' +
      (c.detail ? '<p class="claim-detail">' + c.detail + '</p>' : '') +
      '<p class="claim-reply"><span class="claim-k">The reply to expect</span>' + c.reply + '</p>' +
      '<p class="claim-rejoin"><span class="claim-k">The answer to it</span>' + c.rejoin + '</p>' +
      '<p class="claim-src"><span class="claim-k">Sources</span>' + c.src.join(' · ') + '</p>' +
      '</article>';
  }

  Promise.all([fetch('data/scotland-claims.json').then(function (r) { return r.json(); }),
               fetch('data/scotland.json').then(function (r) { return r.json(); })]).then(function (x) {
    var d = x[0], s = x[1], q = d.quoted, b = d.border, lf = q.load_factor_2025, sup = q.supply_2025_gwh,
        cap = q.capacity_mw, f = q.firm, sg = d.farms_2025.filter(function (r) { return r.farm === 'Seagreen'; })[0],
        share = d.consumption_share, sub = d.cfd_2025.total + d.switch_off_2025.scotland_cost;
    var desnzLF = a(q.load_factor_2025.url, 'DESNZ load factors 2025'), desnzSup = a(sup.url, 'DESNZ generation and supply 2025'),
        neso = a(b.url, 'NESO demand and flow data 2025'), elexon = a('https://bmrs.elexon.co.uk/', 'Elexon metered output (B1610)'),
        desnzCap = a(cap.url, 'DESNZ installed capacity'), clock = a('#method', 'switch-off payments: method below');
    var rate = (cap.onshore_2025 - cap.onshore_2022) / 3, on2030 = cap.onshore_2025 + 5 * rate;
    var rows = q.targets.map(function (t) { return '<tr><td>' + a(t.url, t.what) + '</td><td>' + t.target + '</td><td>' + t.now_label + '</td></tr>'; }).join('');
    var cards = [
      { claim: 'Scotland generates more renewable electricity than it uses.',
        answer: 'Over a year, yes: Scotland sent ' + (sup.to_england_net / 1000).toFixed(1) + ' TWh more to England than it took back in 2025. Hour by hour, no. In ' + n(b.importing_half_hours) + ' half-hours of 2025 (' + pc(b.importing_share, 1) + ') Scotland could not cover its own demand and was a net importer from England.',
        detail: 'On ' + day(d.calm_day.date) + ' the wind dropped. The ' + d.calm_day.wind_units + ' wind farm units Elexon meters in Scotland averaged ' + n(d.calm_day.wind_mean_mw) + ' MW, and never more than ' + n(d.calm_day.wind_max_mw) + ' MW, against ' + gw(cap.onshore_2025 + cap.offshore_2025) + ' of Scottish wind capacity. Torness and Peterhead supplied ' + n(d.calm_day.firm_mean_mw) + ' MW on average, and Scotland was still a net importer from England in ' + b.calm_day_import_half_hours + ' of 48 half-hours, at up to ' + n(b.calm_day_peak_import_mw) + ' MW.',
        reply: 'Scotland is a net exporter: ' + (sup.to_england_net / 1000).toFixed(1) + ' TWh to England last year.',
        rejoin: 'The yearly surplus is made on windy days. On calm days Scotland relies on a nuclear station due to close in 2030, a gas station, and power from England.',
        src: [desnzSup, neso, elexon] },
      { claim: 'Scotland’s wind fleet is a national asset.',
        answer: 'Scottish offshore wind farms ran at ' + pc(lf.scotland_offshore, 1) + ' of their capacity in 2025. English offshore farms ran at ' + pc(lf.england_offshore, 1) + '.',
        detail: 'The gap is not the wind. Scottish offshore farms were paid to switch off ' + n(d.switch_off_2025.scotland_offshore_gwh) + ' GWh in 2025. Add that to the ' + n(q.generation_2025_gwh.offshore) + ' GWh they generated and they would have run at about ' + pc((q.generation_2025_gwh.offshore + d.switch_off_2025.scotland_offshore_gwh) / (cap.offshore_2025 * 8.76)) + ', close to England’s. Seagreen, the largest, was paid ' + m(sg.paid_to_switch_off) + ' to switch off ' + pc(sg.share_switched_off) + ' of what it could have generated (' + n(sg.switched_off_gwh) + ' of ' + n(sg.switched_off_gwh + sg.metered_gwh) + ' GWh).',
        reply: 'Curtailment is a grid problem. The grid is reserved to Westminster and run by NESO and Ofgem.',
        rejoin: 'Then the farms were approved faster than the grid could take their output. Scottish Ministers approved them (claim 3).',
        src: [desnzLF, elexon, clock] },
      { claim: 'Constraint payments are Westminster’s grid problem.',
        answer: 'Since ' + day(s.window.from) + ', ' + bn(s.scotland_cost) + ' has been paid to Scottish wind farms to switch off: ' + pc(s.scotland_share) + ' of all such payments in Britain.',
        detail: 'Scottish Ministers decide whether onshore power stations over 50 MW, and offshore wind farms in Scottish waters, are built. The most expensive single day was ' + day(d.top_day.date) + ': ' + m(d.top_day.cost) + ' paid to Scottish farms not to generate ' + n(d.top_day.mwh / 1000) + ' GWh.',
        reply: 'Transmission is reserved. Scotland cannot build the lines.',
        rejoin: 'Approving the farms is devolved. Ministers chose how much generation to approve, and the switch-off bill measures how far it ran ahead of the lines.',
        src: [a(q.consent.url, 'Energy Consents Unit'), a(q.consent.offshore_url, 'section 36 offshore consents'), clock] },
      { claim: 'Scotland’s energy props up the rest of the UK.',
        answer: 'In 2025 Scottish wind farms received ' + m(d.cfd_2025.total) + ' in Contracts for Difference top-ups and ' + m(d.switch_off_2025.scotland_cost) + ' to switch off: ' + m(sub) + '.',
        detail: 'Both are charged to suppliers across Great Britain for every unit of electricity they sell. Scotland uses ' + pc(share, 1) + ' of Britain’s electricity, so about ' + m(sub * (1 - share)) + ' (' + pc(1 - share) + ') was paid by bill-payers in England and Wales. Not counted: the Renewables Obligation, the older scheme most Scottish onshore farms are paid under, so the true figure is higher.',
        reply: 'Scottish generators pay the highest grid charges in Europe.',
        rejoin: 'Those charges reflect the cost of carrying Scottish power hundreds of miles south to where it is used. They follow from where the farms were built.',
        src: [a('/data', 'LCCC CfD payments (Clock data)'), clock, a(s.who_pays.source_url, 'DESNZ consumption by nation')] },
      { claim: 'Scotland’s electricity supply is secure.',
        answer: 'Torness, Scotland’s last nuclear station, is due to close in 2030. That leaves Peterhead (gas, ' + n(f.peterhead_mw) + ' MW) as Scotland’s only large nuclear or fossil-fuelled power station.',
        detail: 'The Scottish Government’s stated position: “' + f.nuclear_policy + '” On ' + day(d.calm_day.date) + ' Torness and Peterhead were both running and Scotland still needed power from England.',
        reply: 'Scotland is part of a single British grid. Drawing power from England on a calm day is normal.',
        rejoin: 'Then Scotland’s supply after 2030 depends on gas stations in England, and the claim of energy self-sufficiency falls.',
        src: [a(f.torness_url, 'EDF, December 2024'), a(f.peterhead_url, 'SSE Thermal'), a(f.nuclear_policy_url, 'Scottish Government nuclear policy'), neso] },
      { claim: 'Scotland is on track for its 2030 targets.',
        answer: 'Onshore wind stood at ' + gw(cap.onshore_2025) + ' at the end of 2025, against a 20 GW target for 2030. At the 2022–25 rate of building (' + n(rate) + ' MW a year) it reaches about ' + gw(on2030) + ' by 2030.',
        detail: '<table class="data-table claim-table"><thead><tr><th>Target</th><th>For 2030</th><th>Where it stands</th></tr></thead><tbody>' + rows + '</tbody></table>',
        reply: 'Delivery depends on UK auctions and UK grid investment.',
        rejoin: 'Scottish Ministers set these targets. The one written into law, a 75% cut in emissions by 2030, was repealed in 2024 rather than met.',
        src: [desnzCap].concat(q.targets.map(function (t) { return a(t.url, t.source.split(',')[0] + (t.source.split(',')[1] ? ',' + t.source.split(',')[1] : '')); })) }
    ];
    document.getElementById('claims').innerHTML = cards.map(function (c, i) { return card(i + 1, c); }).join('');
    document.getElementById('claims-note').innerHTML = 'Claims are paraphrased; they are not quotations. Figures checked against their sources on ' + day(d.checked) + '. Totals for Scotland’s generation come from DESNZ, not from adding up metered farms: Elexon meters only the larger farms connected to the national grid, and on our count those farms account for less than DESNZ’s published total. Metered data is used here only for named farms and named days. “Net importer” means power flowing from England into Scotland exceeded Scotland’s exports to Northern Ireland (NESO’s Scotland–England and Moyle flows). All figures: ' + a('data/scotland-claims.json', 'scotland-claims.json') + '.';
  });
})();
