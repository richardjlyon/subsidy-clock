/* @ds-bundle: {"format":3,"namespace":"SubsidyClockDesignSystem_829343","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Pill","sourcePath":"components/core/Pill.jsx"},{"name":"ToggleGroup","sourcePath":"components/core/ToggleGroup.jsx"},{"name":"BarRow","sourcePath":"components/data/BarRow.jsx"},{"name":"SchemeDot","sourcePath":"components/data/SchemeDot.jsx"},{"name":"Stat","sourcePath":"components/data/Stat.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"ff6253630b6f","components/core/Button.jsx":"297889aa30af","components/core/Card.jsx":"58d1d82df629","components/core/Pill.jsx":"e758d34dd5e6","components/core/ToggleGroup.jsx":"4c9ccf356066","components/data/BarRow.jsx":"e41fd1e8077a","components/data/SchemeDot.jsx":"6658ac62a12f","components/data/Stat.jsx":"1409b2a02b86","ui_kits/subsidy-clock/App.jsx":"f929f8d8bc87","ui_kits/subsidy-clock/Footer.jsx":"9823c6cba7e1","ui_kits/subsidy-clock/Hero.jsx":"934a2f1cc3b0","ui_kits/subsidy-clock/Ledgers.jsx":"94e53f0f767c","ui_kits/subsidy-clock/Masthead.jsx":"16052866f6be","ui_kits/subsidy-clock/Schemes.jsx":"a66c033504bf","ui_kits/subsidy-clock/SwitchOff.jsx":"45b3523f7769","ui_kits/subsidy-clock/TrendChart.jsx":"d8f6cd993ffe","ui_kits/subsidy-clock/data.js":"d41d112d89d2"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.SubsidyClockDesignSystem_829343 = window.SubsidyClockDesignSystem_829343 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Badge — a small uppercase status label. Used for data freshness,
 * attribution confidence, and the direct/estimated layer marker.
 */
function Badge({
  variant = "default",
  children,
  className = "",
  ...rest
}) {
  const classes = ["sc-badge", variant !== "default" ? `sc-badge--${variant}` : "", className].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("span", _extends({
    className: classes
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Button — the system's action control. Claret-filled primary for the rare
 * real action; outline secondary and quiet ghost for everything else.
 */
function Button({
  variant = "primary",
  size = "md",
  as = "button",
  icon = null,
  children,
  className = "",
  ...rest
}) {
  const Tag = as;
  const classes = ["sc-btn", `sc-btn--${variant}`, size !== "md" ? `sc-btn--${size}` : "", className].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement(Tag, _extends({
    className: classes
  }, rest), icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Card — the ledger surface. A serif title, optional uppercase note and
 * muted intro, then arbitrary content. Depth comes from a hairline border,
 * never a shadow.
 */
function Card({
  title,
  note,
  intro,
  children,
  className = "",
  ...rest
}) {
  return /*#__PURE__*/React.createElement("section", _extends({
    className: ["sc-card", className].filter(Boolean).join(" ")
  }, rest), title && /*#__PURE__*/React.createElement("h2", {
    className: "sc-card__title"
  }, title, note && /*#__PURE__*/React.createElement("span", {
    className: "sc-card__note"
  }, note)), intro && /*#__PURE__*/React.createElement("p", {
    className: "sc-card__intro"
  }, intro), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Pill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pill — a rounded capsule. Clickable by default (share actions, filters);
 * pass `static` for a read-only chip like the "since you opened" counter.
 */
function Pill({
  as = "button",
  isStatic = false,
  icon = null,
  children,
  className = "",
  ...rest
}) {
  const Tag = isStatic ? "span" : as;
  const classes = ["sc-pill", isStatic ? "sc-pill--static" : "", className].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement(Tag, _extends({
    className: classes
  }, rest), icon, children);
}
Object.assign(__ds_scope, { Pill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Pill.jsx", error: String((e && e.message) || e) }); }

// components/core/ToggleGroup.jsx
try { (() => {
/**
 * ToggleGroup — the segmented control used for chart views (Cumulative / By year).
 * Single-select. `value` is the active option id.
 */
function ToggleGroup({
  options = [],
  value,
  onChange,
  ariaLabel = "View"
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "sc-toggle",
    role: "group",
    "aria-label": ariaLabel
  }, options.map(opt => /*#__PURE__*/React.createElement("button", {
    key: opt.id,
    type: "button",
    "aria-pressed": value === opt.id,
    onClick: () => onChange && onChange(opt.id)
  }, opt.label)));
}
Object.assign(__ds_scope, { ToggleGroup });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/ToggleGroup.jsx", error: String((e && e.message) || e) }); }

// components/data/BarRow.jsx
try { (() => {
/**
 * BarRow — a horizontal magnitude bar with a name + amount header.
 * `estimated` switches to the hatched fill that marks indirect costs.
 * Colour the fill with any scheme token via `color`.
 */
function BarRow({
  name,
  amount,
  pct = 0,
  color,
  estimated = false,
  badge = null
}) {
  const fillClasses = ["sc-bar__fill", estimated ? "sc-bar__fill--est" : ""].filter(Boolean).join(" ");
  const fillStyle = {
    width: `${Math.max(0, Math.min(100, pct))}%`
  };
  if (color && !estimated) fillStyle.background = color;
  if (color && estimated) {
    fillStyle.backgroundImage = `repeating-linear-gradient(45deg, ${color} 0, ${color} 2.5px, transparent 2.5px, transparent 6.5px)`;
    fillStyle.borderColor = color;
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "sc-bar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sc-bar__head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-bar__name"
  }, name), badge, /*#__PURE__*/React.createElement("span", {
    className: "sc-bar__amount num"
  }, amount)), /*#__PURE__*/React.createElement("div", {
    className: "sc-bar__track"
  }, /*#__PURE__*/React.createElement("div", {
    className: fillClasses,
    style: fillStyle
  })));
}
Object.assign(__ds_scope, { BarRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/BarRow.jsx", error: String((e && e.message) || e) }); }

// components/data/SchemeDot.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * SchemeDot — the small coloured square that keys a scheme to the chart.
 * `size="chip"` renders the larger 16px square used in explainer headers.
 */
function SchemeDot({
  color,
  size = "dot",
  className = "",
  ...rest
}) {
  const cls = [size === "chip" ? "sc-chip" : "sc-dot", className].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    style: {
      background: color
    },
    "aria-hidden": "true"
  }, rest));
}
Object.assign(__ds_scope, { SchemeDot });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/SchemeDot.jsx", error: String((e && e.message) || e) }); }

// components/data/Stat.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Stat — a single figure with a label beneath. `money` colours it claret;
 * `serif` renders it in Fraunces for the category-figure treatment.
 */
function Stat({
  value,
  label,
  money = false,
  serif = false,
  className = "",
  ...rest
}) {
  const valueClasses = ["sc-stat__value", "num", money ? "sc-stat__value--money" : "", serif ? "sc-stat__value--serif" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("div", _extends({
    className: ["sc-stat", className].filter(Boolean).join(" ")
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: valueClasses
  }, value), /*#__PURE__*/React.createElement("span", {
    className: "sc-stat__label"
  }, label));
}
Object.assign(__ds_scope, { Stat });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Stat.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/App.jsx
try { (() => {
/* App — composes the full Subsidy Clock dashboard. */
function App() {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Masthead, null), /*#__PURE__*/React.createElement("main", {
    className: "container sc-main"
  }, /*#__PURE__*/React.createElement(Hero, null), /*#__PURE__*/React.createElement(Ledgers, null), /*#__PURE__*/React.createElement(SwitchOff, null), /*#__PURE__*/React.createElement(Schemes, null), /*#__PURE__*/React.createElement(TrendChart, null)), /*#__PURE__*/React.createElement(Footer, null));
}
ReactDOM.createRoot(document.getElementById("root")).render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/Footer.jsx
try { (() => {
/* Footer — freshness line and source credit. */
function Footer() {
  const D = window.SC_DATA;
  const gen = new Date(D.GENERATED_AT).toLocaleString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
  return /*#__PURE__*/React.createElement("footer", {
    className: "sc-footer"
  }, /*#__PURE__*/React.createElement("div", {
    className: "container"
  }, /*#__PURE__*/React.createElement("p", {
    className: "sc-footer-links"
  }, "Made by ", /*#__PURE__*/React.createElement("a", {
    href: "#"
  }, "Richard Lyon"), " \xB7 ", /*#__PURE__*/React.createElement("a", {
    href: "#data"
  }, "Data"), " \xB7", /*#__PURE__*/React.createElement("a", {
    href: "#methodology"
  }, " Methodology & sources"), " \xB7 ", /*#__PURE__*/React.createElement("a", {
    href: "#corrections"
  }, "Corrections"), " \xB7", /*#__PURE__*/React.createElement("a", {
    href: "#about"
  }, " About this site")), /*#__PURE__*/React.createElement("p", {
    className: "sc-footer-small"
  }, /*#__PURE__*/React.createElement("span", {
    className: "num"
  }, "Generated ", gen, "."), " Every figure traces to an official source.")));
}
window.Footer = Footer;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/Footer.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/Hero.jsx
try { (() => {
/* Hero — the live headline counter, lead-in, since-opened pill, share row,
   timeframe strip and equivalences. The counter ticks on the real run-rate. */
function Hero() {
  const {
    Pill
  } = window.SubsidyClockDesignSystem_829343;
  const D = window.SC_DATA,
    F = window.SC_FMT;
  const t = D.totals;
  const [value, setValue] = React.useState(() => liveValue());
  const openRef = React.useRef(Date.now());
  const [since, setSince] = React.useState(0);
  function liveValue() {
    const elapsed = (Date.now() - D.GENERATED_AT) / 1000;
    return t.renew_cumulative + elapsed * t.renew_rate_per_sec;
  }
  React.useEffect(() => {
    const id = setInterval(() => {
      setValue(liveValue());
      setSince((Date.now() - openRef.current) / 1000 * t.renew_rate_per_sec);
    }, 120);
    return () => clearInterval(id);
  }, []);

  // Run-rate timeframe projections
  const perHour = t.renew_rate_per_sec * 3600;
  const now = new Date();
  const midnight = new Date(now);
  midnight.setHours(0, 0, 0, 0);
  const todaySoFar = (now - midnight) / 1000 * t.renew_rate_per_sec;
  const yearStart = new Date(now.getFullYear(), 0, 1);
  const yearSoFar = (now - yearStart) / 1000 * t.renew_rate_per_sec;
  return /*#__PURE__*/React.createElement("section", {
    className: "sc-hero",
    "aria-label": "Headline counter"
  }, /*#__PURE__*/React.createElement("p", {
    className: "sc-hero-leadin"
  }, "Subsidising renewable electricity has cost the UK ", /*#__PURE__*/React.createElement("strong", null, F.compact(t.combined_real), " in today\u2019s money"), " since 2002 \u2014 of which this is the measured, direct bill to renewable generators, in the pounds actually paid:"), /*#__PURE__*/React.createElement("p", {
    className: "sc-hero-figure"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-hero-value money num"
  }, F.full(value))), /*#__PURE__*/React.createElement("p", {
    className: "sc-hero-sub"
  }, "paid to renewable generators since ", t.since_year, ", and counting"), /*#__PURE__*/React.createElement(Pill, {
    isStatic: true,
    className: "sc-since"
  }, "Since you opened this page: ", /*#__PURE__*/React.createElement("span", {
    className: "money num"
  }, F.pounds(since))), /*#__PURE__*/React.createElement("div", {
    className: "sc-share-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-share-lead"
  }, "Share this number:"), /*#__PURE__*/React.createElement(Pill, {
    icon: /*#__PURE__*/React.createElement(LinkGlyph, null)
  }, "Copy link"), /*#__PURE__*/React.createElement(Pill, {
    icon: /*#__PURE__*/React.createElement(XGlyph, null)
  }, "Post")), /*#__PURE__*/React.createElement("div", {
    className: "sc-strip",
    "aria-label": "Run-rate estimates over different timeframes"
  }, /*#__PURE__*/React.createElement(StripCell, {
    label: "Every hour",
    value: F.compact(perHour),
    sub: "at the current rate"
  }), /*#__PURE__*/React.createElement(StripCell, {
    label: "Today so far",
    value: F.compact(todaySoFar),
    sub: "since midnight"
  }), /*#__PURE__*/React.createElement(StripCell, {
    label: "This year",
    value: F.compact(yearSoFar),
    sub: "since 1 January"
  }), /*#__PURE__*/React.createElement(StripCell, {
    label: "All-time",
    value: F.compact(t.renew_cumulative_real),
    sub: "in 2024 prices"
  }), /*#__PURE__*/React.createElement(StripCell, {
    label: "Your household",
    value: F.pounds(t.renew_per_household),
    sub: "per year, direct"
  }), /*#__PURE__*/React.createElement(StripCell, {
    label: "Per person",
    value: F.pounds(t.renew_per_person),
    sub: "per year, direct"
  })), /*#__PURE__*/React.createElement("p", {
    className: "sc-strip-caption"
  }, "Timeframe figures are run-rate estimates projected from the current rate. The all-time figure is the full direct cost in 2024 prices; household and per-person figures are at the current run-rate."), /*#__PURE__*/React.createElement("ul", {
    className: "sc-equiv"
  }, /*#__PURE__*/React.createElement("li", null, /*#__PURE__*/React.createElement("span", {
    className: "money num"
  }, F.pounds(t.renew_per_mwh)), " added to every MWh of renewable electricity delivered"), /*#__PURE__*/React.createElement("li", null, /*#__PURE__*/React.createElement("span", {
    className: "money num"
  }, F.compact(t.renew_runrate_year)), " a year at the current run-rate"), /*#__PURE__*/React.createElement("li", null, /*#__PURE__*/React.createElement("span", {
    className: "money num"
  }, F.compact(t.indirect_cumulative)), " more in ", /*#__PURE__*/React.createElement("span", {
    className: "eq-est"
  }, "estimated"), " indirect costs")));
}
function StripCell({
  label,
  value,
  sub
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "sc-strip-cell"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-strip-label"
  }, label), /*#__PURE__*/React.createElement("span", {
    className: "sc-strip-value money num"
  }, value), /*#__PURE__*/React.createElement("span", {
    className: "sc-strip-sub"
  }, sub));
}
function LinkGlyph() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
  }));
}
function XGlyph() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"
  }));
}
window.Hero = Hero;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/Hero.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/Ledgers.jsx
try { (() => {
/* Ledgers — the paired "direct bill" and "indirect bill" category cards. */
function Ledgers() {
  const {
    Card,
    SchemeDot,
    Badge
  } = window.SubsidyClockDesignSystem_829343;
  const D = window.SC_DATA,
    F = window.SC_FMT;
  const directTotal = D.direct.reduce((s, x) => s + x.amount, 0);
  const indirectTotal = D.indirect.reduce((s, x) => s + x.amount, 0);
  return /*#__PURE__*/React.createElement("div", {
    className: "sc-pair"
  }, /*#__PURE__*/React.createElement(Card, {
    title: "The direct bill"
  }, /*#__PURE__*/React.createElement("p", {
    className: "sc-khead"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-kfigure money num"
  }, F.compact(directTotal)), /*#__PURE__*/React.createElement("span", {
    className: "sc-ksub"
  }, "measured \xB7 paid to renewable generators since 2002")), /*#__PURE__*/React.createElement("div", null, D.direct.map(s => /*#__PURE__*/React.createElement("a", {
    key: s.id,
    className: "sc-krow",
    href: "#scheme"
  }, /*#__PURE__*/React.createElement(SchemeDot, {
    color: `var(${s.token})`
  }), /*#__PURE__*/React.createElement("span", {
    className: "sc-krow-nm"
  }, s.name), /*#__PURE__*/React.createElement("span", {
    className: "sc-krow-amt money num"
  }, F.compact(s.amount)), /*#__PURE__*/React.createElement("span", {
    className: "sc-krow-pct num"
  }, Math.round(s.amount / directTotal * 100), "%")))), /*#__PURE__*/React.createElement("p", {
    className: "sc-card-foot"
  }, "Every figure traces to LCCC, Ofgem and Elexon settlement data.")), /*#__PURE__*/React.createElement(Card, {
    title: "The indirect bill",
    note: "estimated"
  }, /*#__PURE__*/React.createElement("p", {
    className: "sc-khead"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-kfigure money num"
  }, F.compact(indirectTotal)), /*#__PURE__*/React.createElement("span", {
    className: "sc-ksub"
  }, "estimated \xB7 costs not attributed to individual generators")), /*#__PURE__*/React.createElement("div", null, D.indirect.map(s => /*#__PURE__*/React.createElement("a", {
    key: s.id,
    className: "sc-krow",
    href: "#scheme"
  }, /*#__PURE__*/React.createElement(SchemeDot, {
    color: `var(${s.token})`
  }), /*#__PURE__*/React.createElement("span", {
    className: "sc-krow-nm"
  }, s.name), /*#__PURE__*/React.createElement(Badge, {
    variant: s.confidence
  }, s.confidence), /*#__PURE__*/React.createElement("span", {
    className: "sc-krow-amt money num"
  }, F.compact(s.amount))))), /*#__PURE__*/React.createElement("p", {
    className: "sc-card-foot"
  }, "Amounts are measured; the share attributed to renewables is an estimate.")));
}
window.Ledgers = Ledgers;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/Ledgers.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/Masthead.jsx
try { (() => {
/* Masthead — deep-claret band with the ticking brand mark and nav. */
function Masthead() {
  return /*#__PURE__*/React.createElement("header", {
    className: "sc-masthead"
  }, /*#__PURE__*/React.createElement("div", {
    className: "container sc-masthead-inner"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "sc-brand"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-brand-tick",
    "aria-hidden": "true"
  }), "The Subsidy Clock"), /*#__PURE__*/React.createElement("p", {
    className: "sc-brand-tag"
  }, "What UK energy subsidies cost, counted live")), /*#__PURE__*/React.createElement("nav", {
    className: "sc-nav"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#data"
  }, "Data"), /*#__PURE__*/React.createElement("a", {
    href: "#methodology"
  }, "Methodology"), /*#__PURE__*/React.createElement("a", {
    href: "#about"
  }, "About"))));
}
window.Masthead = Masthead;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/Masthead.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/Schemes.jsx
try { (() => {
/* Schemes — "By scheme" magnitude bars and "By technology" CfD bars,
   plus the largest-recipients table. */
function Schemes() {
  const {
    Card,
    BarRow,
    Badge
  } = window.SubsidyClockDesignSystem_829343;
  const D = window.SC_DATA,
    F = window.SC_FMT;
  const allDirect = D.direct;
  const maxDirect = Math.max(...allDirect.map(s => s.amount));
  const maxTech = Math.max(...D.byTech.map(t => Math.abs(t.amount)));
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "sc-pair"
  }, /*#__PURE__*/React.createElement(Card, {
    title: "By scheme",
    intro: "Cumulative cost of each direct subsidy scheme."
  }, /*#__PURE__*/React.createElement("div", {
    className: "sc-bars"
  }, allDirect.map(s => /*#__PURE__*/React.createElement(BarRow, {
    key: s.id,
    name: s.name,
    amount: F.compact(s.amount),
    pct: s.amount / maxDirect * 100,
    color: `var(${s.token})`
  })))), /*#__PURE__*/React.createElement(Card, {
    title: "By technology",
    note: "CfD only",
    intro: "Net Contracts for Difference payments by technology. Negative is a net payback."
  }, /*#__PURE__*/React.createElement("div", {
    className: "sc-bars"
  }, D.byTech.map(t => /*#__PURE__*/React.createElement(BarRow, {
    key: t.name,
    name: t.name,
    amount: F.compact(t.amount),
    pct: Math.abs(t.amount) / maxTech * 100,
    color: t.amount < 0 ? "var(--c-cm)" : "var(--c-cfdr)"
  }))))), /*#__PURE__*/React.createElement(Card, {
    title: "Largest recipients",
    intro: "Ranked by cumulative payment, merging CfD per-unit payments and constraint payments by lead party."
  }, /*#__PURE__*/React.createElement("table", {
    className: "sc-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    className: "rank-col"
  }, "#"), /*#__PURE__*/React.createElement("th", null, "Recipient"), /*#__PURE__*/React.createElement("th", null, "Technology"), /*#__PURE__*/React.createElement("th", null, "Scheme"), /*#__PURE__*/React.createElement("th", {
    className: "num-col"
  }, "Cumulative"))), /*#__PURE__*/React.createElement("tbody", null, D.recipients.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: r.name
  }, /*#__PURE__*/React.createElement("td", {
    className: "rank-col num"
  }, i + 1), /*#__PURE__*/React.createElement("td", null, r.name), /*#__PURE__*/React.createElement("td", {
    className: "cell-dim"
  }, r.tech), /*#__PURE__*/React.createElement("td", {
    className: "cell-dim"
  }, r.scheme), /*#__PURE__*/React.createElement("td", {
    className: "num-col money num"
  }, F.compact(r.amount))))))));
}
window.Schemes = Schemes;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/Schemes.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/SwitchOff.jsx
try { (() => {
/* SwitchOff — constraint payments: three stats and the largest recipients. */
function SwitchOff() {
  const {
    Card,
    Stat
  } = window.SubsidyClockDesignSystem_829343;
  const D = window.SC_DATA,
    F = window.SC_FMT;
  const c = D.constraints;
  return /*#__PURE__*/React.createElement(Card, {
    title: "Paid to switch off",
    intro: "Constraint payments to wind farms instructed to reduce output when the grid cannot carry their electricity."
  }, /*#__PURE__*/React.createElement("div", {
    className: "sc-statrow"
  }, /*#__PURE__*/React.createElement(Stat, {
    value: F.compact(c.cumulative),
    label: "cumulative since 2010",
    money: true
  }), /*#__PURE__*/React.createElement(Stat, {
    value: F.compact(c.runrate),
    label: "per year at current run-rate",
    money: true
  }), /*#__PURE__*/React.createElement(Stat, {
    value: F.int(c.curtailed_mwh),
    label: "MWh paid for and not generated"
  })), /*#__PURE__*/React.createElement("h3", {
    className: "sc-subhead"
  }, "Largest recipients ", /*#__PURE__*/React.createElement("span", {
    className: "sc-card__note"
  }, "bottom-up window")), /*#__PURE__*/React.createElement("table", {
    className: "sc-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Lead party"), /*#__PURE__*/React.createElement("th", {
    className: "num-col"
  }, "Paid"), /*#__PURE__*/React.createElement("th", {
    className: "num-col"
  }, "MWh curtailed"))), /*#__PURE__*/React.createElement("tbody", null, D.constraintRecipients.map(r => /*#__PURE__*/React.createElement("tr", {
    key: r.party
  }, /*#__PURE__*/React.createElement("td", null, r.party), /*#__PURE__*/React.createElement("td", {
    className: "num-col money num"
  }, F.compact(r.paid)), /*#__PURE__*/React.createElement("td", {
    className: "num-col cell-dim num"
  }, F.int(r.mwh)))))));
}
window.SwitchOff = SwitchOff;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/SwitchOff.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/TrendChart.jsx
try { (() => {
/* TrendChart — stacked direct (claret) + indirect (slate, hatched) by year,
   toggling between cumulative and annual views. 2024 prices. SVG, responsive. */
function TrendChart() {
  const {
    Card,
    ToggleGroup,
    SchemeDot
  } = window.SubsidyClockDesignSystem_829343;
  const D = window.SC_DATA,
    F = window.SC_FMT;
  const [view, setView] = React.useState("cumulative");
  const {
    years,
    directAnnualReal,
    indirectAnnualReal,
    partialFrom
  } = D.trend;

  // Build series for the active view
  let direct = directAnnualReal.slice();
  let indirect = indirectAnnualReal.slice();
  if (view === "cumulative") {
    let dc = 0,
      ic = 0;
    direct = direct.map(v => dc += v);
    indirect = indirect.map(v => ic += v);
  }
  const totals = years.map((_, i) => direct[i] + indirect[i]);
  const maxV = Math.max(...totals);

  // Geometry
  const W = 1000,
    H = 360,
    padL = 56,
    padR = 16,
    padT = 14,
    padB = 30;
  const plotW = W - padL - padR,
    plotH = H - padT - padB;
  const n = years.length;
  const slot = plotW / n;
  const bw = slot * (view === "cumulative" ? 0.82 : 0.66);
  const y = v => padT + plotH - v / maxV * plotH;

  // Gridlines at nice round £bn
  const stepBn = maxV > 1.8e11 ? 50 : maxV > 9e10 ? 25 : 10;
  const grids = [];
  for (let g = 0; g <= maxV; g += stepBn * 1e9) grids.push(g);
  return /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("div", {
    className: "sc-card-head-row"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "sc-card__title",
    id: "trend"
  }, "The bill since 2002, in today\u2019s money"), /*#__PURE__*/React.createElement(ToggleGroup, {
    value: view,
    onChange: setView,
    ariaLabel: "Chart view",
    options: [{
      id: "cumulative",
      label: "Cumulative"
    }, {
      id: "annual",
      label: "By year"
    }]
  })), /*#__PURE__*/React.createElement("p", {
    className: "sc-card__intro"
  }, view === "cumulative" ? "Running total of direct (measured) and estimated indirect costs, restated to 2024 prices." : "Year-by-year direct and estimated indirect costs, restated to 2024 prices. 2025–26 are incomplete years."), /*#__PURE__*/React.createElement("div", {
    className: "sc-chart"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    role: "img",
    "aria-label": "Subsidy cost over time"
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("pattern", {
    id: "hatch",
    width: "6.5",
    height: "6.5",
    patternTransform: "rotate(45)",
    patternUnits: "userSpaceOnUse"
  }, /*#__PURE__*/React.createElement("rect", {
    width: "6.5",
    height: "6.5",
    fill: "var(--card)"
  }), /*#__PURE__*/React.createElement("rect", {
    width: "2.5",
    height: "6.5",
    fill: "var(--c-ccl)"
  }))), grids.map((g, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("line", {
    className: "sc-grid",
    x1: padL,
    x2: W - padR,
    y1: y(g),
    y2: y(g)
  }), /*#__PURE__*/React.createElement("text", {
    className: "sc-axis",
    x: padL - 8,
    y: y(g) + 3,
    textAnchor: "end"
  }, F.compact(g)))), years.map((yr, i) => {
    const x = padL + i * slot + (slot - bw) / 2;
    const partial = yr >= partialFrom;
    const dh = direct[i] / maxV * plotH;
    const ih = indirect[i] / maxV * plotH;
    const dy = padT + plotH - dh;
    const iy = dy - ih;
    return /*#__PURE__*/React.createElement("g", {
      key: yr,
      opacity: partial ? 0.5 : 1
    }, /*#__PURE__*/React.createElement("rect", {
      x: x,
      y: dy,
      width: bw,
      height: Math.max(0, dh),
      fill: "var(--c-cfdr)",
      rx: "1"
    }), /*#__PURE__*/React.createElement("rect", {
      x: x,
      y: iy,
      width: bw,
      height: Math.max(0, ih),
      fill: "url(#hatch)",
      stroke: "var(--c-ccl)",
      strokeWidth: "0.5",
      rx: "1"
    }), i % 4 === 0 && /*#__PURE__*/React.createElement("text", {
      className: "sc-axis",
      x: x + bw / 2,
      y: H - 10,
      textAnchor: "middle"
    }, yr));
  }))), /*#__PURE__*/React.createElement("div", {
    className: "sc-legend"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-legend-group"
  }, "Direct"), /*#__PURE__*/React.createElement("span", {
    className: "sc-legend-item"
  }, /*#__PURE__*/React.createElement(SchemeDot, {
    color: "var(--c-cfdr)"
  }), " Measured payments"), /*#__PURE__*/React.createElement("span", {
    className: "sc-legend-group"
  }, "Indirect"), /*#__PURE__*/React.createElement("span", {
    className: "sc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-legend-hatch"
  }), " Estimated costs")));
}
window.TrendChart = TrendChart;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/TrendChart.jsx", error: String((e && e.message) || e) }); }

// ui_kits/subsidy-clock/data.js
try { (() => {
/* Subsidy Clock — real figures from the published dataset (2026-06-13).
   Source: richardjlyon/subsidy-clock · site/data/*.json
   All values in nominal £ unless suffixed _real (2024 prices). */

window.SC_DATA = function () {
  const GENERATED_AT = Date.parse("2026-06-13T06:52:28Z");
  const totals = {
    // Headline = renewables, nominal £ (the most conservative reading)
    renew_cumulative: 105478162683,
    renew_rate_per_sec: 387.1051619945,
    renew_runrate_year: 12216109860,
    renew_per_household: 421.25,
    renew_per_person: 176.28,
    renew_per_mwh: 44.62,
    renew_cumulative_real: 128110751975,
    // 2024 prices

    indirect_cumulative: 77808498292,
    indirect_cumulative_real: 95274097078,
    indirect_per_household: 276.43,
    indirect_runrate_year: 8016612420,
    since_year: 2002
  };
  totals.combined_real = totals.renew_cumulative_real + totals.indirect_cumulative_real; // ~223.4bn

  // ---- Direct schemes (renewables perspective), cumulative nominal £ ----
  const direct = [{
    id: "ro",
    name: "Renewables Obligation",
    token: "--c-ro",
    amount: 74590000000,
    cadence: "annual",
    stale: false
  }, {
    id: "fit",
    name: "Feed-in Tariffs",
    token: "--c-fit",
    amount: 18233000000,
    cadence: "annual",
    stale: false
  }, {
    id: "cfdr",
    name: "CfD — renewables",
    token: "--c-cfdr",
    amount: 10202228765,
    cadence: "daily",
    stale: false
  }, {
    id: "con",
    name: "Constraint payments",
    token: "--c-con",
    amount: 2452933918,
    cadence: "daily",
    stale: false
  }];

  // ---- Indirect schemes (attributed to renewables), cumulative nominal £ ----
  const indirect = [{
    id: "tnuos",
    name: "Transmission (TNUoS)",
    token: "--c-tnuos",
    amount: 23698825581,
    confidence: "low"
  }, {
    id: "ccl",
    name: "Climate Change Levy + CPS",
    token: "--c-ccl",
    amount: 22848100000,
    confidence: "medium"
  }, {
    id: "bsuos",
    name: "Balancing (BSUoS)",
    token: "--c-bsuos",
    amount: 12065768949,
    confidence: "low"
  }, {
    id: "ets",
    name: "Emissions trading",
    token: "--c-ets",
    amount: 10579000000,
    confidence: "medium"
  }, {
    id: "cm",
    name: "Capacity Market",
    token: "--c-cm",
    amount: 8616803761,
    confidence: "medium"
  }];

  // ---- CfD by technology ----
  const byTech = [{
    name: "Offshore Wind",
    amount: 9989432237
  }, {
    name: "Onshore Wind",
    amount: 216975239
  }, {
    name: "Solar PV",
    amount: -4178711
  }];

  // ---- Largest recipients (merged CfD + biomass), cumulative £ ----
  const recipients = [{
    name: "Drax (3rd conversion unit)",
    tech: "Biomass conversion",
    scheme: "CfD",
    amount: 1978102649
  }, {
    name: "Walney Extension Phase 1",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 1131947759
  }, {
    name: "Walney Extension Phase 2",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 1119994076
  }, {
    name: "Hornsea Phase 1",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 1059418119
  }, {
    name: "Lynemouth Power Station",
    tech: "Biomass conversion",
    scheme: "CfD",
    amount: 920423250
  }, {
    name: "Burbo Bank Extension",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 874056208
  }, {
    name: "Hornsea Phase 2",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 837136329
  }, {
    name: "Dudgeon Phase 2",
    tech: "Offshore wind",
    scheme: "CfD",
    amount: 799162625
  }];

  // ---- Constraint payments — largest recipients (bottom-up window) ----
  const constraintRecipients = [{
    party: "Moray Offshore Wind West Ltd",
    paid: 12173205,
    mwh: 447648
  }, {
    party: "Moray Offshore Wind East Ltd",
    paid: 8509589,
    mwh: 474227
  }, {
    party: "Seagreen Wind Energy Limited",
    paid: 7347820,
    mwh: 635590
  }, {
    party: "SP Renewables (UK) Limited",
    paid: 5104534,
    mwh: 90547
  }, {
    party: "Viking Energy Wind Farm LLP",
    paid: 3891734,
    mwh: 288824
  }];
  const constraints = {
    cumulative: 2452933918,
    runrate: 309264381,
    curtailed_mwh: 2580852
  };

  // ---- Annual series, 2024 prices (£), for the trend chart ----
  const years = [2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
  const directAnnualReal = [438903566, 693089960, 837030848, 970806045, 1175528255, 1388031212, 1588016241, 1678259385, 1910417775, 2297106579, 3476060732, 4521181333, 5415089303, 6620729980, 7825485658, 9071700318, 10131281647, 11426644091, 11620120368, 10322744792, 8789832623, 10668914181, 11900171916, 2377002346, 966602809];
  const indirectAnnualReal = [1143700131, 1097087084, 974884704, 1280232198, 1401191373, 1299970033, 2304005559, 2272519559, 2022585155, 2166128326, 1828998412, 2711645374, 4110387142, 4840052277, 5143631293, 4369294417, 5466191044, 5554465305, 6817799767, 9952522308, 10197988879, 7822239365, 6914935884, 2529921050, 1051720429];
  const partialFrom = 2025; // 2025–26 are incomplete years

  return {
    GENERATED_AT,
    totals,
    direct,
    indirect,
    byTech,
    recipients,
    constraintRecipients,
    constraints,
    trend: {
      years,
      directAnnualReal,
      indirectAnnualReal,
      partialFrom
    }
  };
}();

/* ---- Formatters ---- */
window.SC_FMT = {
  full(n) {
    const neg = n < 0;
    const s = "£" + Math.round(Math.abs(n)).toLocaleString("en-GB");
    return neg ? "−" + s : s;
  },
  // £105.5bn / £421m / £44.62
  compact(n) {
    const a = Math.abs(n),
      sign = n < 0 ? "−" : "";
    if (a >= 1e9) return sign + "£" + (a / 1e9).toFixed(a >= 1e10 ? 1 : 2).replace(/\.0$/, "") + "bn";
    if (a >= 1e6) return sign + "£" + Math.round(a / 1e6).toLocaleString("en-GB") + "m";
    if (a >= 1e3) return sign + "£" + Math.round(a / 1e3).toLocaleString("en-GB") + "k";
    return sign + "£" + a.toFixed(2);
  },
  pounds(n) {
    return "£" + n.toFixed(2);
  },
  int(n) {
    return Math.round(n).toLocaleString("en-GB");
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/subsidy-clock/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Pill = __ds_scope.Pill;

__ds_ns.ToggleGroup = __ds_scope.ToggleGroup;

__ds_ns.BarRow = __ds_scope.BarRow;

__ds_ns.SchemeDot = __ds_scope.SchemeDot;

__ds_ns.Stat = __ds_scope.Stat;

})();
