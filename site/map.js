/* The Subsidy Clock — recipients map. Interactive MapLibre GL map (vendored,
   keyless tiles, engine-pinned attribution) with one circle marker per
   station × scheme, area proportional to cumulative payment. Strings that
   matter ship in data/map.json; this file places them. */
'use strict';

(async function () {
  var COLOUR_VARS = { cfd_renewable: '--jewel-cfd', ro: '--jewel-ro' };
  var LABELS = { cfd_renewable: 'CfD renewables', ro: 'Renewables Obligation' };
  var RMAX = 22, RMIN = 4;   // px at the initial zoom, scaled with zoom below
  var REDUCED = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function fmtCompact(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return '£' + (a / 1e9).toFixed(2) + 'bn';
    if (a >= 1e6) return '£' + (a / 1e6).toFixed(0) + 'm';
    if (a >= 1e3) return '£' + Math.round(a / 1e3) + 'k';
    return '£' + Math.round(a);
  }
  function cssVar(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name).trim() || '#888';
  }

  var frame = document.getElementById('map-frame');
  var popup = document.getElementById('map-popup');
  var panel = document.getElementById('asset-panel');
  var panelBody = document.getElementById('asset-panel-body');
  var panelClose = document.getElementById('asset-panel-close');

  function fmtGen(mwh) {
    if (mwh >= 1e6) return (mwh / 1e6).toFixed(1) + ' TWh';
    if (mwh >= 1e3) return Math.round(mwh / 1e3) + ' GWh';
    return Math.round(mwh) + ' MWh';
  }
  function fmtDate(iso) {
    if (!iso) return '';
    var d = new Date(iso + 'T00:00:00Z');
    return d.toLocaleDateString('en-GB',
      { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
  }

  /* diverging quarterly columns around a zero baseline: payments up
     (--xray-pos), paybacks down (--xray-neg), plus an accessible table of the
     same values. Sign is encoded twice: colour AND side of the baseline. */
  function chartSVG(quarters) {
    var W = 360, H = 120, PAD = 14;
    var posMax = 0, negMax = 0;
    quarters.forEach(function (q) {
      if (q.payment_gbp >= 0) posMax = Math.max(posMax, q.payment_gbp);
      else negMax = Math.max(negMax, -q.payment_gbp);
    });
    var span = posMax + negMax || 1;
    var y0 = PAD + (H - 2 * PAD) * (posMax / span);
    var bw = W / quarters.length;
    var s = '<svg viewBox="0 0 ' + W + ' ' + (H + 14) + '" role="img" ' +
      'aria-label="Net payment by quarter, paybacks below the zero line">';
    quarters.forEach(function (q, i) {
      var h = Math.abs(q.payment_gbp) / span * (H - 2 * PAD);
      if (h > 0 && h < 1) h = 1;
      var y = q.payment_gbp >= 0 ? y0 - h : y0;
      s += '<rect x="' + (i * bw + 0.5).toFixed(1) + '" y="' + y.toFixed(1) +
        '" width="' + Math.max(bw - 1, 0.5).toFixed(1) + '" height="' + h.toFixed(1) +
        '" fill="var(' + (q.payment_gbp >= 0 ? '--xray-pos' : '--xray-neg') + ')">' +
        '<title>' + esc(q.q) + ': ' + (q.payment_gbp < 0 ? '−' : '') +
        fmtCompact(q.payment_gbp) + '</title></rect>';
      if (/Q1$/.test(q.q) && bw * i > 8) {
        s += '<text x="' + (i * bw).toFixed(1) + '" y="' + (H + 11) +
          '" font-size="8.5" fill="#5b6572">' + esc(q.q.slice(0, 4)) + '</text>';
      }
    });
    s += '<line x1="0" x2="' + W + '" y1="' + y0.toFixed(1) + '" y2="' +
      y0.toFixed(1) + '" stroke="#5b6572" stroke-width="1"/></svg>';
    return s;
  }

  function chartTable(quarters) {
    var t = '<table class="sr-table"><caption>Net payment by quarter</caption>' +
      '<thead><tr><th scope="col">Quarter</th><th scope="col">Net payment £</th>' +
      '<th scope="col">Generation MWh</th></tr></thead><tbody>';
    quarters.forEach(function (q) {
      t += '<tr><td>' + esc(q.q) + '</td><td>' + Math.round(q.payment_gbp) +
        '</td><td>' + Math.round(q.generation_mwh) + '</td></tr>';
    });
    return t + '</tbody></table>';
  }

  var assetCache = {};
  var panelInvoker = null;

  function renderPanel(a) {
    var col = (a.scheme === 'cfd_renewable') ? colours.cfd_renewable : colours.ro;
    var h = '<div class="asset-head">' +
      '<p class="asset-name" id="asset-panel-name"><span class="pop-dot" ' +
      'style="background:' + col + '"></span>' + esc(a.name) + '</p>' +
      '<p class="asset-meta">' + esc(a.scheme_label) + ' · ' +
      esc(a.technology) + '</p></div>' +
      '<p class="asset-hero"><span class="v">' + (a.hero_gbp < 0 ? '−' : '') +
      fmtCompact(a.hero_gbp) + '</span><span class="l">' +
      esc(a.hero_label) + '</span></p>';
    if (a.tiles) {
      h += '<div class="asset-tiles">' +
        '<div class="tile"><span class="v">' + fmtGen(a.tiles.generation_mwh) +
        '</span><span class="l">subsidised generation</span></div>' +
        '<div class="tile"><span class="v">£' +
        Math.round(a.tiles.rate_gbp_per_mwh) + '/MWh</span><span class="l">' +
        esc(a.tiles.rate_label) + '</span></div></div>';
    }
    if (a.strings.rate_not_shown) {
      h += '<p class="asset-note">' + esc(a.strings.rate_not_shown) + '</p>';
    }
    if (a.quarters && a.quarters.length) {
      h += '<p class="asset-chart-title">Net payment by quarter</p>' +
        '<div class="asset-chart">' + chartSVG(a.quarters) + '</div>' +
        chartTable(a.quarters);
    }
    if (a.contracts && a.contracts.length) {
      h += '<table class="asset-contracts"><thead><tr><th scope="col">Contract</th>' +
        '<th scope="col">Since</th><th class="num" scope="col">Strike £/MWh</th>' +
        '<th class="num" scope="col">Paid</th></tr></thead><tbody>';
      a.contracts.forEach(function (c) {
        h += '<tr><td>' + esc(c.cfd_id) + '</td>' +
          '<td>' + (c.first_settlement ? esc(c.first_settlement.slice(0, 4)) : '—') + '</td>' +
          '<td class="num">' + (c.latest_strike_gbp_mwh != null
            ? c.latest_strike_gbp_mwh.toFixed(2) : '—') + '</td>' +
          '<td class="num">' + (c.cumulative_gbp < 0 ? '−' : '') +
          fmtCompact(c.cumulative_gbp) + '</td></tr>';
      });
      h += '</tbody></table>';
    }
    h += '<p class="asset-note">' + esc(a.strings.basis) + '</p>';
    h += '<p class="asset-note">' + esc(a.strings.outages_unavailable) + '</p>';
    h += '<p class="asset-prov">' + esc(a.provenance.source) +
      (a.provenance.data_to
        ? ' Data to ' + esc(fmtDate(a.provenance.data_to)) + '.' : '') + '</p>';
    panelBody.innerHTML = h;
  }

  function openPanel(slug, invoker) {
    panelInvoker = invoker || document.activeElement;
    var got = assetCache[slug]
      ? Promise.resolve(assetCache[slug])
      : fetch('data/assets/' + encodeURIComponent(slug) + '.json')
          .then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
          })
          .then(function (a) { assetCache[slug] = a; return a; });
    got.then(function (a) {
      renderPanel(a);
      panel.hidden = false;
      panelClose.focus();
    }).catch(function () {
      panelBody.innerHTML = '<p class="asset-note">Asset detail could not be ' +
        'loaded. <a href="/data">See the data tables</a>.</p>';
      panel.hidden = false;
      panelClose.focus();
    });
  }
  function closePanel() {
    panel.hidden = true;
    if (panelInvoker && panelInvoker.focus) panelInvoker.focus();
    panelInvoker = null;
  }
  panelClose.addEventListener('click', closePanel);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !panel.hidden) closePanel();
  });

  var data;
  try {
    data = await fetch('data/map.json').then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  } catch (err) {
    frame.innerHTML = '<p class="table-note">Map data could not be loaded (' +
      esc(err.message) + '). <a href="/data">See the data tables</a>.</p>';
    return;
  }

  var tiles = data.tiles;
  var markers = data.markers || [];
  if (!markers.length) { frame.style.display = 'none'; return; }

  // pinned fallback for any boot failure past this point (old browser, no
  // WebGL, vendored lib broken) — never a blank or half-drawn frame
  function fallback() {
    frame.innerHTML = '<p class="table-note">' + esc(tiles.fallback) +
      ' <a href="/data">See the data tables</a>.</p>';
  }
  if (typeof maplibregl === 'undefined') { fallback(); return; }
  // no-WebGL browsers: the Map constructor throws — caught below

  var costMax = markers.reduce(function (m, k) { return Math.max(m, k.cost); }, 0);
  var colours = {
    cfd_renewable: cssVar(COLOUR_VARS.cfd_renewable),
    ro: cssVar(COLOUR_VARS.ro),
  };

  var map;
  try {
    map = new maplibregl.Map({
      container: 'map-canvas',
      style: tiles.style_url,
      center: tiles.center,
      zoom: tiles.zoom,
      minZoom: 3.5,
      maxZoom: 14,
      attributionControl: false,
      fadeDuration: REDUCED ? 0 : 300,
    });
    map.addControl(new maplibregl.AttributionControl({
      compact: true,
      // engine-pinned strings from data/map.json — placed, not authored
      customAttribution: [tiles.attribution, tiles.terrain_attribution],
    }));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  } catch (err) {
    fallback();
    return;
  }
  map.on('error', function (e) {
    // a failed style load leaves a blank frame — degrade to the pinned text.
    // Tile-level errors (transient) don't unset the map.
    if (!map.isStyleLoaded() && e && e.error && /style/i.test(String(e.error))) {
      fallback();
    }
  });

  map.on('load', function () {
    // 3D terrain — garnish, not structure: any failure leaves the map flat
    if (tiles.terrain && !REDUCED) {
      try {
        map.addSource('terrain', {
          type: 'raster-dem',
          tiles: [tiles.terrain.tiles],
          encoding: tiles.terrain.encoding,
          tileSize: tiles.terrain.tile_size || 256,
          maxzoom: tiles.terrain.max_zoom || 15,
        });
        map.setTerrain({ source: 'terrain',
                         exaggeration: tiles.terrain.exaggeration || 1.3 });
        // visible relief at flat pitch (3D terrain only shows when tilted);
        // slotted beneath the style's first label layer so place names stay crisp
        var firstSymbol = (map.getStyle().layers.find(function (l) {
          return l.type === 'symbol';
        }) || {}).id;
        map.addLayer({
          id: 'hillshade', type: 'hillshade', source: 'terrain',
          paint: { 'hillshade-exaggeration': 0.35,
                   'hillshade-shadow-color': '#5a5040' },
        }, firstSymbol);
        map.on('error', function (e) {
          if (e && e.sourceId === 'terrain') {
            try { map.setTerrain(null); } catch (_) { /* already flat */ }
          }
        });
      } catch (err) { /* flat map is fine */ }
    }

    // one circle per marker, area ∝ cumulative payment (r ∝ √cost)
    var features = markers.map(function (k, i) {
      var r = costMax > 0 ? RMAX * Math.sqrt(k.cost / costMax) : RMIN;
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [k.lon, k.lat] },
        properties: { i: i, r0: Math.max(r, RMIN), scheme: k.scheme },
      };
    });
    map.addSource('recipients', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: features },
    });
    map.addLayer({
      id: 'recipients',
      type: 'circle',
      source: 'recipients',
      paint: {
        'circle-radius': ['interpolate', ['exponential', 1.6], ['zoom'],
          4, ['*', ['get', 'r0'], 0.9],
          10, ['*', ['get', 'r0'], 3]],
        'circle-color': ['match', ['get', 'scheme'],
          'cfd_renewable', colours.cfd_renewable,
          'ro', colours.ro, '#888'],
        'circle-opacity': 0.85,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1,
      },
    });

    function showPopup(i, pt) {
      var k = markers[i];
      popup.innerHTML =
        '<span class="pop-name"><span class="pop-dot" style="background:' +
        (colours[k.scheme] || '#888') + '"></span>' + esc(k.name) + '</span>' +
        '<span class="pop-cost">' + fmtCompact(k.cost) + '</span>' +
        '<span class="pop-meta"> · ' + esc(LABELS[k.scheme] || k.scheme) +
        ' · ' + esc(k.technology) + '</span>';
      popup.classList.add('is-visible');
      var pw = popup.offsetWidth, ph = popup.offsetHeight;
      var left = pt.x + 12, top = pt.y - ph - 8;
      if (left + pw > frame.clientWidth) left = pt.x - pw - 12;
      if (left < 0) left = 4;
      if (top < 0) top = pt.y + 14;
      popup.style.left = left + 'px';
      popup.style.top = top + 'px';
    }
    function hidePopup() { popup.classList.remove('is-visible'); }

    map.on('mousemove', 'recipients', function (e) {
      map.getCanvas().style.cursor = 'pointer';
      showPopup(e.features[0].properties.i, e.point);
    });
    map.on('mouseleave', 'recipients', function () {
      map.getCanvas().style.cursor = '';
      hidePopup();
    });
    map.on('click', 'recipients', function (e) {
      hidePopup();
      openPanel(markers[e.features[0].properties.i].slug, map.getCanvas());
    });
    map.on('click', function (e) {
      var hits = map.queryRenderedFeatures(e.point, { layers: ['recipients'] });
      if (!hits.length) hidePopup();
    });

    // keyboard path: canvas circles can't take focus, so a visually-hidden
    // list of stations (cost order) drives the same popup
    var list = document.getElementById('map-station-list');
    markers.slice().map(function (k, i) { return { k: k, i: i }; })
      .sort(function (a, b) { return b.k.cost - a.k.cost; })
      .forEach(function (m) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = m.k.name + ', ' + (LABELS[m.k.scheme] || m.k.scheme) +
          ', ' + fmtCompact(m.k.cost);
        b.addEventListener('click', function () {
          var move = { center: [m.k.lon, m.k.lat], zoom: 8 };
          if (REDUCED) map.jumpTo(move); else map.flyTo(move);
          openPanel(m.k.slug, b);
        });
        list.appendChild(b);
      });
  });

  function legendItem(id) {
    return '<span><span class="swatch" style="background:' + colours[id] +
      '"></span>' + LABELS[id] + '</span>';
  }
  document.getElementById('map-legend').innerHTML =
    legendItem('cfd_renewable') + legendItem('ro') +
    '<span class="legend-group">Bubble area ∝ total payment</span>';
})();
