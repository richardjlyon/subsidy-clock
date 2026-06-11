/* The Subsidy Clock — share/cite component (distribution F2+F3).
   Self-contained: injects its own styles; owns GoatCounter tracking.
   A "fact" is {id, title, anchor, url, png, csv, label, figure()}:
     id     stable card id (event taxonomy share:{id}:{action})
     title  card title for citations
     anchor stable fragment on the dashboard (the public citation contract)
     url    what Copy link / Share to use (a /s/ stub where one exists)
     png    share-image path or null
     csv    data download path or null
     label  plain-text description for Copy figure
     figure() current displayed value as text */
/* exported SCShare */
var SCShare = (function () {
  'use strict';

  // ---- GoatCounter. Set to your code (e.g. "subsidyclock") to enable; "" = silent no-op.
  var GOATCOUNTER_CODE = '';
  var SITE = 'https://subsidyclock.co.uk';

  function initTracking() {
    if (!GOATCOUNTER_CODE) return;
    window.goatcounter = { no_onload: true };
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://gc.zgo.at/count.js';
    s.setAttribute('data-goatcounter', 'https://' + GOATCOUNTER_CODE + '.goatcounter.com/count');
    document.head.appendChild(s);
  }
  function track(eventPath) {
    if (!GOATCOUNTER_CODE) return;
    if (window.goatcounter && window.goatcounter.count) {
      window.goatcounter.count({ path: eventPath, event: true });
    }
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function todayLong() {
    return new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }
  function copyText(text, onDone) {
    function done() { if (onDone) onDone(); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copy this:', text); done(); });
    } else {
      window.prompt('Copy this:', text);
      done();
    }
  }

  // ---- citations (F3). Cite always uses the canonical anchor URL, never a stub.
  function citeUrl(fact) {
    return fact.anchor ? SITE + '/#' + fact.anchor : (fact.url || SITE + '/');
  }
  var SOURCES = 'LCCC/Ofgem/Elexon/NESO';
  function citations(fact) {
    var year = new Date().getFullYear();
    var url = citeUrl(fact);
    var accessed = todayLong();
    var key = 'subsidyclock' + year + fact.id.replace(/-/g, '');
    return [
      { name: 'Plain', text: 'The Subsidy Clock (' + year + '), ‘' + fact.title + '’, ' +
        url.replace('https://', '') + ', data from ' + SOURCES + ', retrieved ' + accessed + '.' },
      { name: 'Harvard', text: 'The Subsidy Clock (' + year + ') ‘' + fact.title +
        '’. Available at: ' + url + ' (Accessed: ' + accessed + ').' },
      { name: 'APA', text: 'The Subsidy Clock. (' + year + '). ' + fact.title +
        '. Retrieved ' + accessed + ', from ' + url },
      { name: 'BibTeX', text: '@misc{' + key + ',\n  title = {' + fact.title + '},\n' +
        '  author = {{The Subsidy Clock}},\n  year = {' + year + '},\n' +
        '  howpublished = {\\url{' + url + '}},\n' +
        '  note = {Data from ' + SOURCES + '; retrieved ' + accessed + '}\n}' }
    ];
  }

  // ---- share intents (F2.6): figure + link, no hashtags, no editorial text
  function intents(fact) {
    var text = fact.figure() + ' — ' + fact.label;
    var url = fact.url || citeUrl(fact);
    var encT = encodeURIComponent(text), encU = encodeURIComponent(url);
    return [
      { name: 'X', href: 'https://twitter.com/intent/tweet?text=' + encT + '&url=' + encU },
      { name: 'LinkedIn', href: 'https://www.linkedin.com/sharing/share-offsite/?url=' + encU },
      { name: 'Facebook', href: 'https://www.facebook.com/sharer/sharer.php?u=' + encU },
      { name: 'WhatsApp', href: 'https://wa.me/?text=' + encT + '%20' + encU },
      { name: 'Bluesky', href: 'https://bsky.app/intent/compose?text=' + encT + '%20' + encU }
    ];
  }

  function copyFigureText(fact, asof) {
    return fact.figure() + ' — ' + fact.label +
      (asof ? ', as of ' + asof : '') + ' · subsidyclock.co.uk';
  }

  // ---- styles, injected once
  var CSS = '' +
    '.share-wrap{position:relative;display:inline-block;margin-top:.35rem}' +
    '.share-btn{background:none;border:1px solid var(--line,#e4dfd2);border-radius:4px;' +
      'color:var(--muted,#6e6a5f);cursor:pointer;font:inherit;font-size:.78rem;' +
      'padding:.15rem .55rem;display:inline-flex;align-items:center;gap:.35rem}' +
    '.share-btn:hover{color:var(--money-deep,#7a2419);border-color:var(--money-deep,#7a2419)}' +
    '.share-pop{position:absolute;bottom:calc(100% + 6px);left:0;z-index:30;min-width:15rem;' +
      'background:var(--card,#fffdf9);border:1px solid var(--line,#e4dfd2);border-radius:6px;' +
      'box-shadow:0 4px 18px rgba(35,33,28,.14);padding:.35rem;font-size:.85rem}' +
    '.share-pop button,.share-pop a.share-item{display:block;width:100%;text-align:left;' +
      'background:none;border:0;border-radius:4px;color:var(--ink,#23211c);cursor:pointer;' +
      'font:inherit;padding:.35rem .6rem;text-decoration:none}' +
    '.share-pop button:hover,.share-pop a.share-item:hover{background:var(--paper,#f7f4ee)}' +
    '.share-cite{border-top:1px solid var(--line-soft,#ece8dc);margin-top:.3rem;padding-top:.3rem}' +
    '.share-cite textarea{width:100%;font-size:.72rem;font-family:inherit;min-height:3.6rem;' +
      'border:1px solid var(--line,#e4dfd2);border-radius:4px;padding:.3rem}' +
    '.share-cite .cite-tabs{display:flex;gap:.25rem;margin-bottom:.3rem}' +
    '.share-cite .cite-tabs button{width:auto;padding:.15rem .5rem;font-size:.72rem;' +
      'border:1px solid var(--line,#e4dfd2)}' +
    '.share-cite .cite-tabs button[aria-pressed="true"]{border-color:var(--money-deep,#7a2419);' +
      'color:var(--money-deep,#7a2419)}' +
    '.share-to{display:flex;flex-wrap:wrap;gap:.15rem;border-top:1px solid var(--line-soft,#ece8dc);' +
      'margin-top:.3rem;padding-top:.3rem}' +
    '.share-to a.share-item{width:auto;display:inline-block}';
  var styleDone = false;
  function injectStyle() {
    if (styleDone) return;
    var st = document.createElement('style');
    st.textContent = CSS;
    document.head.appendChild(st);
    styleDone = true;
  }

  var ICON = '<svg width="11" height="11" viewBox="0 0 16 16" aria-hidden="true" fill="none" ' +
    'stroke="currentColor" stroke-width="1.6"><path d="M6 3H3v10h10v-3M9 2h5v5M14 2 7 9"/></svg>';

  // ---- the menu
  var openPop = null;
  document.addEventListener('click', function (e) {
    if (openPop && !openPop.parentNode.contains(e.target)) closePop();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closePop();
  });
  function closePop() {
    if (!openPop) return;
    openPop.hidden = true;
    var citeBox = openPop.querySelector('.share-cite');
    if (citeBox) citeBox.hidden = true;
    var citeBtn = openPop.querySelector('[data-act="cite"]');
    if (citeBtn) citeBtn.setAttribute('aria-expanded', 'false');
    openPop.previousSibling.setAttribute('aria-expanded', 'false');
    openPop = null;
  }

  function buildPop(fact, asof) {
    var pop = document.createElement('div');
    pop.className = 'share-pop';
    pop.hidden = true;
    var html = '';
    html += '<button data-act="copy-link">Copy link</button>';
    html += '<button data-act="copy-figure">Copy figure</button>';
    if (fact.png) {
      html += '<a class="share-item" data-act="download-image" href="' + esc(fact.png) +
        '" download>Download image</a>';
    }
    if (fact.csv) {
      html += '<a class="share-item" data-act="download-data" href="' + esc(fact.csv) +
        '" download>Download data (CSV)</a>';
    }
    html += '<button data-act="cite" aria-expanded="false">Cite…</button>';
    html += '<div class="share-cite" hidden><div class="cite-tabs"></div>' +
      '<textarea readonly aria-label="Citation"></textarea>' +
      '<button data-act="copy-cite">Copy citation</button></div>';
    html += '<div class="share-to">' + intents(fact).map(function (i) {
      return '<a class="share-item" data-act="share-' + i.name.toLowerCase() + '" href="' +
        esc(i.href) + '" target="_blank" rel="noopener">' + i.name + '</a>';
    }).join('') + '</div>';
    pop.innerHTML = html;

    var cites = citations(fact);
    var citeBox = pop.querySelector('.share-cite');
    var tabs = pop.querySelector('.cite-tabs');
    var ta = pop.querySelector('textarea');
    cites.forEach(function (c, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = c.name;
      b.setAttribute('aria-pressed', i === 0 ? 'true' : 'false');
      b.addEventListener('click', function () {
        tabs.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        ta.value = c.text;
      });
      tabs.appendChild(b);
    });
    ta.value = cites[0].text;

    pop.addEventListener('click', function (e) {
      var act = e.target.getAttribute && e.target.getAttribute('data-act');
      if (!act) return;
      if (act === 'copy-link') {
        copyText(fact.url || (fact.anchor ? SITE + '/#' + fact.anchor : SITE + '/'), function () { flash(e.target, 'Copied'); });
      } else if (act === 'copy-figure') {
        copyText(copyFigureText(fact, asof), function () { flash(e.target, 'Copied'); });
      } else if (act === 'cite') {
        citeBox.hidden = !citeBox.hidden;
        e.target.setAttribute('aria-expanded', String(!citeBox.hidden));
      } else if (act === 'copy-cite') {
        copyText(ta.value, function () { flash(e.target, 'Copied'); });
      }
      // download-image / download-data / share-* are real links: let them act
      track('share:' + fact.id + ':' + act);
    });
    return pop;
  }

  function flash(btn, msg) {
    var old = btn.textContent;
    btn.textContent = msg;
    setTimeout(function () { btn.textContent = old; }, 1400);
  }

  /* Attach a quiet share control for `fact` inside `container`. */
  function attach(container, fact, asof) {
    injectStyle();
    var wrap = document.createElement('div');
    wrap.className = 'share-wrap';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'share-btn';
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = ICON + 'Share';
    var pop = buildPop(fact, asof);
    wrap.appendChild(btn);
    wrap.appendChild(pop);
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var opening = pop.hidden;
      closePop();
      if (opening) {
        pop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        openPop = pop;
      }
    });
    container.appendChild(wrap);
  }

  return {
    initTracking: initTracking, track: track, attach: attach,
    copyText: copyText, copyFigureText: copyFigureText
  };
})();
