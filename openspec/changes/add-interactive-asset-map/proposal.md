# add-interactive-asset-map

## Why

The recipients map (`/map`) is a fixed 480×640 static image with hover bubbles — it
locates the money but cannot answer the next question a visitor has: *what is the
history of subsidy to this asset?* The engine already holds that history (LCCC daily
per-contract settlement: payment, generation, strike price — including the negative
payback periods of 2021–22) and ships none of it. An interactive map with a per-asset
"X-ray" panel turns the site's most shareable page into its most useful one, at no new
cost basis: everything shown derives from data the engine already fetches, plus two
structured additions (LCCC contract status, Elexon REMIT outage history) that are
**gated on up-front verification** of their coverage and join keys.

## What Changes

Three phases, one change, strictly ordered:

**Phase A — interactive map.** MapLibre GL JS (vendored, BSD-3-Clause licence
committed, no build step, no token, no usage billing) over a keyless tile source,
with 3D terrain as progressive enhancement. Marker semantics preserved: one marker
per `map.json` entry (station × scheme — Drax remains two markers, one per scheme),
area ∝ cumulative payment, colour by scheme; constraint-payment recipients remain
excluded with the existing engine-pinned explanation. The Mapbox Static Images
dependency and the token machinery (`site/mapbox-token.js`, `MAPBOX_TOKEN`,
`scripts/inject-mapbox-token.js`, **and the `vercel.json` buildCommand that invokes
it**) are removed. The `map.json` schema change (slug + lat/lon replacing pixel x/y)
and the page that reads it land in ONE push.

**Phase B — the asset X-ray panel.** Click/keyboard opens a panel (side panel on
desktop, bottom sheet on mobile): hero cumulative payment; stat tiles (lifetime
subsidised generation, effective payment-per-subsidised-MWh — suppressed, not
zeroed, in degenerate cases); quarterly net-payment chart diverging around zero
(paybacks below the line, unclamped); per-contract table; provenance footer with
data-to date. Engine emits per-asset JSON (`site/data/assets/<slug>.json`),
lazy-loaded; slugs are pinned in reference data for stability. RO-only assets
degrade honestly: buy-out value, technology, engine-pinned understatement note —
no chart, no empty tiles.

**Phase C — context layers, each behind a go/no-go verification task.**
LCCC contract-portfolio status (join key against settlement `CfD_ID` verified
first) as a status column in the contract table. Elexon REMIT outage history
(temporal coverage verified first; the strip states its coverage window — records
from date X, never implying "no outages" before it) via a new hand-curated
station → BMU reference mapping. Curated enforcement notes (e.g. Drax 2024
redress): close-paraphrase of the cited official document only, official-domain
allowlist, each row through the prepublication fact-check gate before it ships.

## Capabilities

### New Capabilities

- `asset-map`: the interactive map page — MapLibre map, markers, terrain, and the
  click-to-open per-asset X-ray panel with chart, tables and provenance.
- `asset-data`: the engine build outputs behind it — per-asset JSON (quarterly
  series, contract rows, outage events, notes), the extended `map.json`, pinned
  slugs, the new reference files (BMU mapping, enforcement notes), and the
  REMIT/contract-status fetchers.

### Modified Capabilities

<!-- none: this branch's openspec/ is freshly initialised; the existing map
     behaviour is captured and superseded inside asset-map -->

## Impact

- **Site**: `site/map.html`, `site/map.js` rewritten; `site/mapbox-token.js`
  deleted; new vendored `site/assets/vendor/maplibre-gl.{js,css}` + LICENSE
  (~800 KB JS, loaded only on /map — the site's first vendored library, flagged
  deliberately); new `site/data/assets/*.json`; long-max-age cache header added
  for `site/assets/vendor/` (versioned filenames).
- **Deploy config**: `vercel.json` buildCommand (currently the token-inject
  script) removed in the same push as the page — otherwise every deploy fails.
- **Engine**: `subsidy_engine/sitedata.py` (map + per-asset builders; pixel
  projection removed), `subsidy_engine_uk` (REMIT fetcher, LCCC portfolio-status
  fetcher, BMU reference loader).
- **Reference data**: slug column pinned into `reference/station_coords.csv`;
  new `reference/station_bmu_map.csv`, `reference/enforcement_notes.csv`
  (hand-curated, each row source-cited).
- **Gates**: full test suite AND the UK golden master on every engine change —
  this change alters `sitedata.py`, so the golden master will diff by design and
  must be consciously re-baselined with justification; code and data land in one
  push; panel strings engine-pinned and test-pinned; chart palette CVD-validated
  in both modes.

## Non-goals

- No live generation, weather layers, wind roses, history/prediction modes.
- No year-by-year deep history beyond the quarterly series; no daily granularity
  or strike-price-history charts.
- No cross-scheme station identity (Drax stays two markers); no expansion of the
  mapped set beyond the existing largest-recipients stations.
- No per-station RO annual ROC detail in this change — the RO panel's pinned
  wording states that richer Ofgem data exists and why it is not yet shown.
- No embed/share-card work for the map.
- No scraped or inferred enforcement data — curated, source-cited, fact-check-gated
  rows only.
