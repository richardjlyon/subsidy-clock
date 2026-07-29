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
      showPopup(e.features[0].properties.i, e.point);
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
          map.once(REDUCED ? 'idle' : 'moveend', function () {
            showPopup(m.i, map.project([m.k.lon, m.k.lat]));
          });
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
