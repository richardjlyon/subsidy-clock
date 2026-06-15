# The Subsidy Clock — Design System

A design system for **The Subsidy Clock** ([subsidyclock.co.uk](https://subsidyclock.co.uk)) —
a public, sourced dashboard that counts, in pounds sterling, the subsidies paid to UK
renewable and low-carbon electricity generators since 2002. It is a one-person work of
data journalism by Richard Lyon (author of *The Energy Trap*), built to be **audited**:
every figure traces to an official source with a URL, timestamp and content hash.

The product is a single surface — a long-scroll dashboard with a live ticking counter,
breakdown cards, magnitude bars, ranked recipient tables, a stacked time-series chart,
plus a set of plain "explainer" pages. There is no app, no login, no marketing site.
The whole feel is a **public ledger**: warm paper, ink, hairline rules, and one claret
accent reserved for money.

## Sources

This system was reverse-engineered from the project's own static site (no framework, no
build step). If you have access, read these to do a better job:

- **GitHub:** `richardjlyon/subsidy-clock` — https://github.com/richardjlyon/subsidy-clock
  (branch `master`). The site lives in `site/`: `index.html`, `style.css`, `app.js`,
  `share.js`, the `explainers/` pages, and the published data in `site/data/*.json`.
- **Live site:** https://subsidyclock.co.uk
- **Imported into this project:** the real data snapshot under `site/data/` (totals,
  breakdown, timeseries, meta) and `site/explainers/explainer.css` — used to ground the
  UI kit in true figures (2026-06-13).

Explore the repository further to build production-faithful work.

---

## Content fundamentals

**Voice: plain, exact, civic, slightly adversarial toward official spin.** The site's
thesis is that an unaudited cost is hidden in plain sight, so the writing is calm and
precise rather than outraged — it lets the numbers carry the weight.

- **Tone** — measured, evidentiary, sceptical. *"Renewables are cheap. That is the
  official story… The subsidy bill tells a different one."* Claims are always hedged to
  their evidence: *"a labelled estimate between data releases. The totals beneath it are not."*
- **Person** — direct second person to the reader: **"your bill", "your household",
  "your taxes", "Since you opened this page"**. First person singular for the author's
  voice on About ("Built and self-funded by Richard Lyon… I want to know"). Never "we".
- **Casing** — sentence case everywhere except small UI labels, which are UPPERCASE with
  wide tracking ("EVERY HOUR", "LARGEST RECIPIENTS"). Headlines are sentence case in serif.
- **British English & money** — pounds sterling, British digit grouping
  (`£105,478,162,683`), no pence in headline figures, pence shown for unit costs (`26p`).
  Figures are **nominal** unless explicitly *"in today's money"* (2024 prices).
- **The measured / estimated firewall** — the single most important content rule.
  **Direct (measured)** figures and **indirect (estimated)** figures are *never invisibly
  blended*. Any combined figure says so; estimated costs always carry the word
  **estimated** and a published attribution rule. The headline counts the most
  conservative reading (renewables only, nominal).
- **Provenance everywhere** — *"Every figure traces to an official source."* Sources are
  named inline (LCCC, Elexon, Ofgem, HMRC, DESNZ, NESO, REF). Errors are corrected in
  public, never silently edited.
- **No emoji. No exclamation. No hype.** Numbers are the rhetoric.
- **Example microcopy:** "Paid to switch off" · "What UK energy subsidies cost, counted
  live" · "MWh paid for and not generated" · "Negative values are net paybacks".

---

## Visual foundations

The aesthetic is a **printed ledger / broadsheet**. It is deliberately un-dashboard-like:
no glassmorphism, no gradients-as-decoration, no drop shadows, no rounded-rectangle-with-
coloured-left-border cards.

- **Paper & ink** — background is warm off-white `#f7f4ee` carrying a faint **dot grid**
  (`radial-gradient` 1px dots on a 26px lattice) for a printed-ledger texture. Cards are a
  warmer `#fffdf9`. Text is near-black ink `#23211c`, with `--muted` and `--faint` for
  secondary and tertiary.
- **One accent** — claret `#99311f` (`--money`) and deep claret `#7a2419`. Claret is
  **never decorative**; it means *money*. The masthead band, links and figure headings use
  deep claret. Everything else is paper, ink and grey.
- **Two data ramps** — **warm claret ramp** for the DIRECT (measured) layer
  (`--c-ro → --c-con`), **cool slate-blue ramp** for the INDIRECT (estimated) layer
  (`--c-cm → --c-bsuos`). *Warm = on record, cool = inferred.* Estimated series are also
  **hatched** (45° repeating lines) so they read as estimates even in greyscale.
- **Type** — **Fraunces** (variable optical-size serif, 400–700) for the brand, headings
  and big category figures; **IBM Plex Sans** (400–600) for body, UI and labels; **IBM
  Plex Mono** for provenance (hashes, timestamps). Every figure is **tabular + lining
  numerals** so columns align and the ticking counter never reflows. Headline counter:
  `clamp(2.05rem, 8.6vw, 5.4rem)`, weight 600, letter-spacing −0.015em.
- **Backgrounds** — flat paper + dot grid only. The masthead is a solid deep-claret band
  with a subtle top darkening gradient and a 1px cream inset hairline at its base (a
  "double-rule ledger finish"). No imagery, no full-bleed photos, no illustration.
- **Cards & surfaces** — depth comes from a **1px hairline border** (`--line #e4dfd2`) on
  the warm card fill — **never a shadow** (`--shadow-card: none`). Inner dividers use the
  softer `--line-soft`. Radii: 14px primary cards, 10px strips/inner cards, 6px bar fills
  & small controls, 4px badges/dots, 2px the brand tick, 999px pills.
- **Borders & rules** — hairlines do all the structural work: table rows, strip cells,
  category rows are separated by 1px soft rules, like ruled ledger paper.
- **Animation** — almost none. The only motion is the **brand tick**: a claret-cream
  square that blinks once every 2s (`steps(1)`), the clock ticking. Honours
  `prefers-reduced-motion`. Hover/press are colour shifts, not transforms — links and pills
  move toward claret on hover; the primary button lightens claret→`--money` on hover and
  nudges 0.5px on press. No bounces, no easing showcases, no skeleton shimmer.
- **Transparency & blur** — none. This is opaque paper. The only alpha is in the masthead's
  cream nav links (rgba cream on claret) and the dot-grid texture.
- **Imagery vibe** — there is no photography or illustration. The "imagery" is the data
  itself: bars, the stacked chart, coloured scheme squares. Colour temperature is warm
  (claret/amber) for measured, cool (slate) for estimated.
- **Layout** — single centred column, `max-width: 1060px` (prose pages 760px), 20px
  gutters. Sections are cards stacked vertically; some pair two cards in a 2-up grid that
  collapses to 1-up under 900px. Left-aligned reading, centred hero.

---

## Iconography

**Minimal and text-first.** The Subsidy Clock has no icon font, no icon library, and no
emoji. Its visual vocabulary is type, rules and colour — not pictograms.

- **The brand mark** is the only "logo": a single small square (`--c-con` cream-amber)
  that blinks on a 2s tick beside the serif wordmark. There is **no raster logo or
  favicon** in the source — the mark is pure CSS and is reproduced here in
  `guidelines/brand-mark.card.html`. (If a raster lockup is ever needed, it should be
  generated from that CSS, not drawn afresh.)
- **Coloured scheme squares** (`SchemeDot` / `.sc-dot`, `.sc-chip`) are the primary
  iconographic device — an 11px (legend) or 16px (header) square in the scheme's ramp
  colour, keying each subsidy to its bars and chart series. This is the system's "icon set".
- **A few tiny inline UI SVGs** appear only for share actions (copy-link, post-to-X) in
  the hero share row — thin 1.5–2px stroke, `currentColor`, 12–13px. Recreated in
  `ui_kits/subsidy-clock/Hero.jsx` (`LinkGlyph`, `XGlyph`). If you need more UI glyphs,
  match that weight; **Lucide** (2px stroke, rounded caps) is the closest CDN match and a
  safe substitute — flag any addition, since the source uses essentially none.
- **Dotted underlines** mark "hover for source" cues; **uppercase tracked labels** and
  **hairline/solid badges** do the work that icons would in a typical dashboard.
- **No unicode-as-icon, no emoji, ever.** A check mark `✓` (in `--ok` green) is the one
  glyph used, for "verified to the penny".

> **Asset note:** because the product ships no logo files, illustrations, or photographs,
> there is no `assets/` binary folder. The reproducible brand mark and scheme-square
> vocabulary live in the foundation cards under `guidelines/`.

---

## Fonts

Fraunces and IBM Plex Sans/Mono **are the real brand fonts** (the live site links the same
Google Fonts families) — there is no substitution. They load via `@import` in
`tokens/fonts.css`. If you need fully self-hosted `.woff2` binaries for offline/production
use, drop them into `assets/fonts/` and swap the `@import` for `@font-face` rules.

---

## Index / manifest

**Foundations (CSS — consumers link `styles.css`):**
- `styles.css` — root entry, `@import` lines only
- `tokens/fonts.css` · `colors.css` · `typography.css` · `spacing.css` · `base.css`
- `components/components.css` — class styles for the React primitives

**Components** (`window.SubsidyClockDesignSystem_829343.*`):
- `components/core/` — `Button`, `ToggleGroup`, `Badge`, `Pill`, `Card`
- `components/data/` — `Stat`, `BarRow`, `SchemeDot`

**Foundation cards** (Design System tab) — `guidelines/*.card.html`
(Type ×4, Colors ×5, Spacing ×3, Brand ×2).

**UI kit** — `ui_kits/subsidy-clock/` — the live dashboard recreation (`index.html` +
JSX screens + real data). See its `README.md`.

**Other:**
- `site/data/` — imported real dataset (totals, breakdown, timeseries, meta)
- `SKILL.md` — Agent-Skills wrapper
- `readme.md` — this file
