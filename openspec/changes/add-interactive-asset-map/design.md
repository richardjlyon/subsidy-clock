# add-interactive-asset-map — design

## Context

`site/map.js` today: Mapbox Static Images basemap (token injected at deploy by
`scripts/inject-mapbox-token.js`, which is also `vercel.json`'s buildCommand) + an
SVG overlay of bubbles whose (x, y) are Web-Mercator pixel coordinates pre-projected
by `subsidy_engine/sitedata.py::_map_data`. Hover shows name/scheme/cost. The
engine's snapshot store holds daily per-contract CfD settlement rows (date, cfd_id,
unit_name, technology, generation_mwh, payment_gbp, strike_price_gbp_mwh) and
per-station RO buy-out values (`reference/ro_stations.csv`);
`stations.group_by_station` collapses contracts to physical stations **within CfD
only** — there is no cross-scheme station identity (Drax is two markers, one per
scheme, pinned by test). `reference/station_coords.csv` holds lat/lon for the mapped
set (50 markers). The site is static: Vercel serves committed files; no framework.

## Goals / Non-Goals

**Goals:**
- Pan/zoom map of GB with the existing marker semantics, working on mobile.
- Per-asset panel that makes the full held subsidy history legible in one screen.
- Remove the Mapbox token machinery (one less secret, one less deploy step).
- Keep every gate: engine-pinned wording, one-push code+data, suite green,
  golden master consciously re-baselined.

**Non-Goals:** live/operational data, embed cards, mapped-set expansion,
cross-scheme identity, AU.

## Decisions

1. **MapLibre GL JS, vendored — over Mapbox GL JS or Leaflet.**
   MapLibre is the open-source Mapbox GL fork: same rendering quality, native 3D
   terrain, no token, no per-load billing. Leaflet is lighter but has no terrain
   and poor vector-tile support. Vendored (`site/assets/vendor/`) not CDN'd: the
   site serves committed files and must not grow a runtime third-party dependency
   that can change under us. Vendoring ships the BSD-3-Clause LICENSE alongside,
   pins the version in a README line, and documents the re-vendor procedure —
   security updates are a manual re-vendor, accepted for a leaf-page library.
   ~800 KB JS + CSS, loaded only on /map, behind a long-max-age header for
   `site/assets/vendor/` (versioned filenames) — the site's blanket
   `max-age=0, must-revalidate` would otherwise revalidate it every view.

2. **Keyless tile sources.** Basemap: OpenFreeMap vector tiles (free, keyless,
   commercial use permitted, mandatory attribution, explicitly no SLA) with a
   muted style consistent with the site's skin. Terrain: 3D relief via a raster-dem
   source (AWS Terrain Tiles / Terrarium), enabled as subtle default exaggeration
   with graceful fallback — terrain failure must not break the map; it is garnish,
   not structure, and is the first thing to cut if its terms verification (task
   1.1, completed **before** any terrain code) disappoints. Attribution strings
   for all sources are engine-pinned into `map.json`; the methodology page's
   source list and privacy note gain the tile providers.

3. **`map.json` carries slug + lat/lon; pixel projection dies.** Markers become
   `{slug, name, lat, lon, scheme, technology, cost}`. `_web_mercator` and
   `_mapbox_static_url` are removed. **One-push rule, sharpened**: the schema
   change and the page that reads it land in the same push — the current live
   page dereferences `k.x` and would throw on the new schema. Marker radius stays
   area-∝-cost, computed client-side (unchanged maths), rendered as a MapLibre
   GeoJSON circle layer with zoom-interpolated radius.

4. **Slugs are pinned reference data, not derived at build time.**
   `reference/station_coords.csv` (the file that already defines the mapped set)
   gains a `slug` column, hand-assigned once, unique, stable across data
   refreshes and upstream name changes (station names like "Burbo Offshore
   Windfarm - A (31/01/07)" make derived slugs fragile). The build fails loudly
   on a coords row without a slug or a duplicate slug. Because markers are
   station × scheme, slug is unique per (station, scheme) — the RO and CfD Drax
   markers carry distinct slugs and get independent asset JSONs.

5. **Per-asset JSON, lazy-loaded.** `site/data/assets/<slug>.json`, one per
   marker (~50 files, small), built by a new `sitedata` builder:
   - `header`: name, technology, scheme badge, engine-pinned basis note.
   - `hero`: the marker's cost (CfD cumulative payment, or RO buy-out value with
     its pinned understatement note). Build-enforced invariant: asset hero ==
     marker cost.
   - `tiles` (CfD assets only): lifetime subsidised generation (MWh); effective
     rate = cumulative payment ÷ cumulative generation, engine-pinned label
     "payment per subsidised MWh" (defined on methodology). **Degenerate cases
     suppress the tile** — cumulative payment ≤ 0, or generation null/zero/
     incomplete — with pinned "not shown" wording; never a negative or infinite
     rate, never zero standing in for unknown.
   - `quarters`: `[{q: "2020-Q1", payment_gbp, generation_mwh}]` — daily rows
     aggregated by calendar quarter across the station's contracts (a contract
     starting mid-quarter simply contributes its rows; the series starts at the
     first settlement quarter). Negative net quarters ship unclamped.
   - `contracts`: `[{cfd_id, unit_name, latest_strike_gbp_mwh, first_settlement,
     cumulative_gbp, status}]`. RO markers have no contracts array — their JSON
     is the RO-only shape.
   - `outages`: `[{start, end, type: planned|unplanned, mw_lost}]` plus a
     `coverage_from` date (see decision 8); omitted entirely when the station
     has no BMU mapping (renders as pinned "outage history unavailable").
   - `note`: optional enforcement note `{text, source_url, date}`.
   - `provenance`: pinned source names and the data-to date the panel footer
     renders — a panel of history without an as-of date fails the site's own
     freshness standard.

6. **Quarterly, not annual or daily.** Annual buries the 2021–22 payback quarters
   (the editorially significant feature of the dataset); daily is unreadable at
   panel width. Chart is a diverging column chart around a zero baseline:
   payments above in the scheme colour, paybacks below in the diverging
   counter-colour; palette run through the dataviz validator in light and dark
   modes. `prefers-reduced-motion` disables map animations (flyTo, terrain
   easing) and any chart transitions.

7. **Panel is plain DOM + inline SVG, no chart library.** One diverging bar chart
   and a timeline strip do not justify a dependency. Rendering follows the
   existing site pattern (vanilla JS placing engine-pinned strings from JSON),
   with a visually-hidden `<table>` of the quarterly series for screen readers.
   **Keyboard access mechanism**: MapLibre circle layers are canvas-rendered and
   cannot receive focus, so the page ships a visually-hidden focusable station
   list (one button per marker, ordered by cost) that drives the same panel —
   the honest, cheap a11y path; pointer users hit the canvas layer.

8. **Context fetchers are verification-gated.**
   - *LCCC contract-portfolio status*: the dataset exists on the LCCC data
     portal; whether its contract ids join 1:1 against settlement `CfD_ID` is
     **unverified** — a go/no-go task fetches it and measures join coverage
     against `cfd_stations.csv` before any code builds on it. Parsed to
     `{cfd_id, status}`, snapshot-stored like the other schemes; absent contract
     ⇒ pinned status "unknown".
   - *REMIT outages*: Elexon Insights REMIT is keyless (the engine already uses
     Insights in `elexon.py`), but the platform is recent — **temporal coverage
     is unverified and likely starts well after the 2016– settlement series**.
     Go/no-go task measures actual history depth for our BMUs first. The strip
     always states its coverage window (`coverage_from`) so a 2023-start feed
     never silently implies "no outages before 2023" — that would be zero
     standing in for unknown. Messages are revision-heavy: collapse to the
     latest revision per mRID before aggregating (fixture-tested).
     `reference/station_bmu_map.csv` is hand-curated from the Elexon BMU
     register, one source-cited row per BMU; missing station ⇒ unavailable,
     never a guess.

9. **Enforcement notes are editorial data with the site's strongest guardrails.**
   Hand-maintained `reference/enforcement_notes.csv` (station, date, text,
   source_url). Constraints enforced by the loader: source_url present and on an
   official-domain allowlist (ofgem.gov.uk, gov.uk, lowcarboncontracts.uk);
   station must be in the mapped set; text must be a close paraphrase of the
   cited document — and every row goes through the prepublication fact-check
   gate before it ships (the Drax 2024 settlement is precisely the kind of row
   where "found no evidence of deliberate misreporting; agreed £25m redress"
   must not compress into an overstatement). Empty file is a valid state. No
   fetching, no scraping.

## Risks / Trade-offs

- [Tile source availability: OpenFreeMap is donation-funded, no SLA] → tiles URL
  isolated in one config block; swapping providers is a one-line change plus
  attribution update; failure mode is the pinned fallback text, never a blank
  hero.
- [~800 KB vendored JS on a page that was previously one image] → /map only,
  deferred, long-max-age vendor header; page weight measured and recorded in QA.
- [REMIT coverage too shallow to be useful] → go/no-go verification before
  build; if coverage is post-2023 only, Richard decides whether the strip ships
  with a stated window or the feature is cut — the panel works without it.
- [BMU mapping errors would attribute outages to the wrong farm] → mapping CSV
  source-cited per row, reviewed like other reference data; fixture test pins a
  known mapping.
- [Enforcement notes: libel-adjacent overstatement risk] → decision 9's
  guardrails: official-domain allowlist, close-paraphrase rule, prepublication
  fact-check per row; cutting the feature entirely remains cheap (empty CSV).
- [Effective £/MWh misread as levelised cost] → pinned label, methodology
  definition, degenerate-case suppression.
- [Golden master diffs by design] → the re-baseline is its own reviewed step
  with a written justification, not a silent regeneration.

## Migration Plan

1. **Phase A prep (engine)**: fetcher/reference/test work lands commit-by-commit
   with suite + golden master green; nothing that changes `site/data/` schema
   ships yet.
2. **Phase A ship (one push)**: new `map.json` schema + rebuilt data + rewritten
   page + vendored MapLibre + `vercel.json` buildCommand removal, together.
3. **Phase B ship (one push)**: per-asset JSONs + panel JS/CSS together.
4. **Phase C ship**: each context layer lands only after its go/no-go
   verification, data + rendering together.
5. `MAPBOX_TOKEN` env var deleted after phase A is verified live. **Rollback
   window**: reverting phase A is clean only until the env var is deleted;
   after that, rollback also means restoring the token and buildCommand — noted
   in the ship checklist.
