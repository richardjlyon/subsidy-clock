/* The Subsidy Clock — share/cite component (distribution F2+F3).
   NOTE (share-UX rework, 2026-06-12): attach() is currently unwired - the
   per-card menus were removed in favour of the hero share row. The module
   still owns GoatCounter and the copy/track helpers; re-attach per card
   with SCShare.attach(container, fact, asof) if a card needs a menu again.
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

  function canShareFiles() {
    try {
      return !!(navigator.canShare &&
        navigator.canShare({ files: [new File([''], 't.png', { type: 'image/png' })] }));
    } catch (e) { return false; }
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
    '.share-to a.share-item{width:auto;display:inline-block}' +
    '.fact-share-wrap{position:relative;display:inline-block;margin-left:.3rem;vertical-align:baseline}' +
    '.fact-share-btn{background:none;border:0;padding:1px 3px;cursor:pointer;' +
      'color:var(--ink,#23211c);opacity:.5;line-height:1}' +
    '.fact-share-btn:hover,.fact-share-btn:active{opacity:1;color:var(--money-deep,#7a2419)}' +
    '.report-pop{min-width:14rem}' +
    '.report-note{margin:.15rem .6rem .35rem;color:var(--muted,#6e6a5f);font-size:.78rem}';
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
    // deliberately compact (X / WhatsApp / Copy link) - the full intent
    // set lives in buildPop for per-card menus.
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

  // ---- factoid share glyphs (impact I5). One quiet always-visible glyph per
  // equivalence line; native share with the factoid's own card PNG where the
  // device supports file sharing, else a compact X / WhatsApp / Copy-link
  // popover. Events: share:fact:{slug}:{channel}.
  var GLYPH = '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" aria-hidden="true"><path d="M8 1v9M5 3.5 8 1l3 2.5M3 7v7h10V7"/></svg>';

  function factoidNativeShare(fact) {
    fetch(fact.png)
      .then(function (r) { if (!r.ok) throw new Error('' + r.status); return r.blob(); })
      .then(function (b) {
        var payload = { text: fact.sentence, url: fact.url,
                        files: [new File([b], fact.slug + '.png', { type: 'image/png' })] };
        if (!navigator.canShare(payload)) payload = { text: fact.sentence, url: fact.url };
        return navigator.share(payload);
      })
      .catch(function () {
        if (navigator.share) {
          navigator.share({ text: fact.sentence, url: fact.url }).catch(function () {});
        }
      });
    track('share:fact:' + fact.slug + ':native');
  }

  /* Attach a factoid share glyph for `fact` = {slug, sentence, png, url}. */
  function attachFactoid(container, fact) {
    injectStyle();
    var wrap = document.createElement('span');
    wrap.className = 'fact-share-wrap';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fact-share-btn';
    btn.setAttribute('aria-label', 'Share this fact');
    btn.innerHTML = GLYPH;
    wrap.appendChild(btn);
    if (canShareFiles()) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        factoidNativeShare(fact);
      });
    } else {
      var encT = encodeURIComponent(fact.sentence);
      var encU = encodeURIComponent(fact.url);
      var pop = document.createElement('div');
      pop.className = 'share-pop';
      pop.hidden = true;
      pop.innerHTML =
        '<a class="share-item" data-ch="x" target="_blank" rel="noopener" ' +
          'href="https://twitter.com/intent/tweet?text=' + encT + '&url=' + encU + '">X</a>' +
        '<a class="share-item" data-ch="whatsapp" target="_blank" rel="noopener" ' +
          'href="https://wa.me/?text=' + encT + '%20' + encU + '">WhatsApp</a>' +
        '<button data-ch="copy-link">Copy link</button>';
      pop.addEventListener('click', function (e) {
        var ch = e.target.getAttribute && e.target.getAttribute('data-ch');
        if (!ch) return;
        if (ch === 'copy-link') copyText(fact.url, function () { flash(e.target, 'Copied'); });
        track('share:fact:' + fact.slug + ':' + ch);
      });
      wrap.appendChild(pop);
      btn.setAttribute('aria-haspopup', 'true');
      btn.setAttribute('aria-expanded', 'false');
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
    }
    container.appendChild(wrap);
  }

  // ---- report an error (corrections C2). Same quiet register as the factoid
  // glyphs: a dimmed always-visible mark per card heading; compact popover; the
  // mailto carries the figure's context so the reporter supplies only the
  // description. The address is assembled at open time, never in page source.
  var REPORT_GLYPH = '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" aria-hidden="true"><path d="M4 15V2m0 .8h8.5l-2.2 3.1 2.2 3.1H4"/></svg>';

  /* The auto-attached context block. `info` = {id, label, valueEl, version},
     all optional: prose pages pass only {version}. The displayed value is read
     from the DOM at call time so the report carries what the reporter saw. */
  function reportContext(info) {
    var lines = [];
    if (info.id) {
      var displayed = '(chart/table)';
      if (info.valueEl) {
        var el = document.getElementById(info.valueEl);
        if (el && el.textContent.trim()) displayed = el.textContent.trim();
      }
      lines.push('Figure: ' + info.label + ' (' + info.id + ')');
      lines.push('Displayed: ' + displayed);
    }
    if (info.version) lines.push('Data version: ' + info.version);
    lines.push('Page: ' + window.location.href);
    return lines;
  }

  function reportMailto(info) {
    var u = 'richlyon';
    var d = ['fastmail', 'com'].join('.');
    var subject = 'Subsidy Clock — possible error' + (info.label ? ': ' + info.label : '');
    var body = 'What looks wrong:\n[describe the error here]\n\n' +
      'Your evidence or source (optional):\n\n\n' +
      'Name for credit (optional):\n\n\n' +
      '---- attached automatically ----\n' +
      reportContext(info).join('\n');
    return 'mailto:' + u + '@' + d + '?subject=' + encodeURIComponent(subject) +
      '&body=' + encodeURIComponent(body);
  }

  var ISSUES_URL = 'https://github.com/richardjlyon/subsidy-clock/issues/new';
  function reportIssueUrl(info) {
    var title = '[correction] Possible error' + (info.label ? ': ' + info.label : '');
    return ISSUES_URL + '?template=correction.yml&labels=correction' +
      '&title=' + encodeURIComponent(title) +
      '&context=' + encodeURIComponent(reportContext(info).join('\n'));
  }

  /* Attach a quiet report-an-error mark for `info` = {id, label, valueEl, version}. */
  function attachReport(container, info) {
    injectStyle();
    var wrap = document.createElement('span');
    wrap.className = 'fact-share-wrap';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fact-share-btn report-btn';
    btn.setAttribute('aria-label', 'Report an error in this figure');
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = REPORT_GLYPH;
    var pop = document.createElement('div');
    pop.className = 'share-pop report-pop';
    pop.hidden = true;
    wrap.appendChild(btn);
    wrap.appendChild(pop);
    pop.addEventListener('click', function (e) {
      var act = e.target.getAttribute && e.target.getAttribute('data-act');
      if (act === 'report-email') track('correction:submit:email');
      if (act === 'report-github') track('correction:submit:github');
    });
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var opening = pop.hidden;
      closePop();
      if (opening) {
        // rebuilt at open time so the displayed value is current
        pop.innerHTML =
          '<p class="report-note">Spotted an error? The figure’s details attach automatically.</p>' +
          '<a class="share-item" data-act="report-email" href="' + esc(reportMailto(info)) + '">Email a report</a>' +
          '<a class="share-item" data-act="report-github" target="_blank" rel="noopener" href="' +
            esc(reportIssueUrl(info)) + '">Open a GitHub issue</a>' +
          '<a class="share-item" data-act="report-how" href="corrections.html">How corrections work</a>';
        pop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        openPop = pop;
        track('correction:open');
      }
    });
    container.appendChild(wrap);
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
    attachFactoid: attachFactoid, attachReport: attachReport,
    reportMailto: reportMailto, canShareFiles: canShareFiles,
    copyText: copyText, copyFigureText: copyFigureText
  };
})();
