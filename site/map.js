/* The Subsidy Clock — recipients map. Mapbox static basemap + jewel SVG markers
   with hover popups. No dependencies. */
'use strict';

(async function () {
  var SVGNS = 'http://www.w3.org/2000/svg';
  var COLOURS = { cfd_renewable: 'var(--jewel-cfd)', ro: 'var(--jewel-ro)' };
  var LABELS = { cfd_renewable: 'CfD renewables', ro: 'Renewables Obligation' };
  var RMAX = 24, RMIN = 3;

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

  var frame = document.getElementById('map-frame');
  var popup = document.getElementById('map-popup');

  var data;
  try {
    data = await fetch('data/map.json').then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  } catch (err) {
    frame.innerHTML = '<p class="table-note">Map data could not be loaded (' + esc(err.message) + ').</p>';
    return;
  }

  var bm = data.basemap;
  var markers = data.markers || [];
  if (!markers.length) { frame.style.display = 'none'; return; }
  var W = bm.width, H = bm.height;
  var costMax = markers.reduce(function (m, k) { return Math.max(m, k.cost); }, 0);

  // basemap image (served by Mapbox per their ToS), behind the SVG overlay.
  // The access token is injected at deploy (site/mapbox-token.js, from the Vercel
  // env var MAPBOX_TOKEN) and appended here — it is never committed to git.
  var token = window.MAPBOX_TOKEN || '';
  var img = document.createElement('img');
  img.className = 'map-base';
  img.src = token ? bm.url + '?access_token=' + token : bm.url;
  img.width = W; img.height = H;
  img.alt = 'Map of Great Britain showing renewable subsidy recipients sized by payment';
  if (!token) {
    img.addEventListener('error', function () {
      var note = document.createElement('p');
      note.className = 'table-note';
      note.textContent = 'Basemap unavailable here (the Mapbox token is set only on the live site). Markers are shown below without it.';
      frame.insertBefore(note, img.nextSibling);
    });
  }
  frame.insertBefore(img, popup);

  // marker overlay; viewBox matches the basemap's logical pixel frame so
  // Web-Mercator-projected (x, y) sit exactly on the coastline
  var svg = '<svg class="map-overlay" viewBox="0 0 ' + W + ' ' + H + '" ' +
    'role="img" aria-label="Recipient bubbles, area proportional to cumulative payment, coloured by scheme">';
  markers.slice().sort(function (a, b) { return b.cost - a.cost; })
    .forEach(function (k, i) {
      var r = costMax > 0 ? RMAX * Math.sqrt(k.cost / costMax) : RMIN;
      if (r < RMIN) r = RMIN;
      svg += '<circle class="map-marker" data-i="' + i + '" tabindex="0" ' +
        'cx="' + k.x.toFixed(1) + '" cy="' + k.y.toFixed(1) + '" r="' + r.toFixed(1) + '" ' +
        'fill="' + (COLOURS[k.scheme] || '#888') + '"></circle>';
    });
  svg += '</svg>';
  // insert overlay between the image and the popup
  popup.insertAdjacentHTML('beforebegin', svg);

  var sorted = markers.slice().sort(function (a, b) { return b.cost - a.cost; });

  function showPopup(i, circle) {
    var k = sorted[i];
    popup.innerHTML =
      '<span class="pop-name"><span class="pop-dot" style="background:' + (COLOURS[k.scheme] || '#888') + '"></span>' +
      esc(k.name) + '</span>' +
      '<span class="pop-cost">' + fmtCompact(k.cost) + '</span>' +
      '<span class="pop-meta"> · ' + esc(LABELS[k.scheme] || k.scheme) + ' · ' + esc(k.technology) + '</span>';
    popup.classList.add('is-visible');
    // position relative to the frame, scaled from logical px to rendered px
    var scale = frame.clientWidth / W;
    var px = k.x * scale, py = k.y * scale;
    var pw = popup.offsetWidth, ph = popup.offsetHeight;
    var left = px + 12, top = py - ph - 8;
    if (left + pw > frame.clientWidth) left = px - pw - 12;
    if (left < 0) left = 4;
    if (top < 0) top = py + 14;
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
    if (circle) circle.classList.add('is-active');
  }
  function hidePopup() {
    popup.classList.remove('is-visible');
    var a = frame.querySelector('.map-marker.is-active');
    if (a) a.classList.remove('is-active');
  }

  var overlay = frame.querySelector('.map-overlay');
  overlay.addEventListener('mouseover', function (e) {
    if (e.target.classList.contains('map-marker')) showPopup(+e.target.getAttribute('data-i'), e.target);
  });
  overlay.addEventListener('mouseout', function (e) {
    if (e.target.classList.contains('map-marker')) hidePopup();
  });
  overlay.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('map-marker')) showPopup(+e.target.getAttribute('data-i'), e.target);
  });
  overlay.addEventListener('focusout', hidePopup);
  // touch: tap toggles
  overlay.addEventListener('click', function (e) {
    if (e.target.classList.contains('map-marker')) showPopup(+e.target.getAttribute('data-i'), e.target);
    else hidePopup();
  });

  function legendItem(id) {
    return '<span><span class="swatch" style="background:' + COLOURS[id] + '"></span>' + LABELS[id] + '</span>';
  }
  document.getElementById('map-legend').innerHTML =
    legendItem('cfd_renewable') + legendItem('ro') +
    '<span class="legend-group">Bubble area ∝ total payment</span>';
})();
