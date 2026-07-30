# add-interactive-asset-map — verification record

## HANDOFF — state as of 2026-07-29 (machine change)

All build tasks complete; merged to master and pushed (the deploy). Remaining
when work resumes on the new machine:
1. ~~Post-deploy smoke of live /map~~ — DONE 2026-07-30, see below.
2. Delete the now-unused MAPBOX_TOKEN Vercel env var (rollback to the old
   static map is only clean before this). OUTSTANDING — dashboard-only.
3. iOS Safari/FxiOS check on Richard's phone. OUTSTANDING.
4. ~~Nightly Action now includes the `remit` update target~~ — ran clean
   30 July (commit 18266d0); no stale-data warning.
5. Archive this change (`openspec archive add-interactive-asset-map`) once
   1–3 are done.

## Post-deploy smoke of live /map (2026-07-30): PASS

Headless Chromium against https://subsidyclock.co.uk/map, panels opened via
the visually-hidden station list (the keyboard/a11y path, focus + Enter).

- Map boots: MapLibre canvas present, OpenFreeMap basemap + hillshade painted,
  50 markers in two scheme colours, pinned attribution rendered. No JS errors
  and no console errors on load or on any panel open.
- **CfD panel (Hornsea 1):** hero £2.56bn, both tiles (30.0 TWh, £85/MWh),
  diverging quarterly chart, outage strip ("53 planned, 9 unplanned") with the
  pinned 2016-coverage wording, contract table (INV-HOR-001, Live (Post-FIC)).
- **Payback quarters render negative:** the 2021-Q4 to 2022-Q2 bars draw below
  the zero line in the contrasting colour — the case the change exists to show.
- **RO panel (London Array):** hero + pinned basis note ("understates the
  station's receipts"), pinned outages-unavailable line, chart correctly
  suppressed.
- **Enforcement note (Drax Power Station):** Ofgem 2024 note renders with the
  Voluntary Redress Fund figure.
- **Focus management per spec:** opening moves focus to the close control,
  Escape closes and returns focus to the activator. Verified on all three.

## Task 1.1 — tile-source terms (verified 2026-07-29)

**OpenFreeMap (basemap) — PASS.**
https://openfreemap.org/ : commercial use explicitly permitted; no registration,
no API keys, no rate limits on the public instance; operated by Zsolt Ero,
donation-funded, no SLA ("I don't offer SLA guarantees"). Required attribution:
"OpenFreeMap © OpenMapTiles Data from OpenStreetMap" (OpenFreeMap portion
optional). Matches the design's stated risk posture (no SLA, one-line provider
swap if needed).

**AWS Terrain Tiles / Terrarium (terrain) — PASS, with linked attribution.**
https://registry.opendata.aws/terrain-tiles/ : freely accessible S3 buckets
(elevation-tiles-prod, us-east-1; -eu, eu-central-1), no AWS account required;
managed by Mapzen, a Linux Foundation project. Attribution per
https://github.com/tilezen/joerd/blob/master/docs/attribution.md is a compound
multi-source list (for GB coverage chiefly: Copernicus EU-DEM ("produced using
Copernicus data and information funded by the European Union"), "United Kingdom
terrain data © Environment Agency copyright and/or database right 2015", and
USGS SRTM/GMTED2010); the doc requires attribution "in a place that is
reasonable to the medium" — satisfied by a short credit on the map linking to
the full list on the methodology page.

**Decision: terrain GO** — terms permit use; attribution ships as a linked
credit; graceful-fallback requirement unchanged (terrain failure never breaks
the map).

## Task 3 page QA (2026-07-29, desktop Playwright)

Local serve + rebuilt map.json: map boots keyless (positron style), 50 markers,
jewel colours read from the CSS vars, hillshade renders beneath labels, both
pinned attribution strings placed, legend + note intact, zero console errors.
Keyboard path verified: hidden station list button (focus-visible reveal) →
flyTo → popup with correct figures. Boot fallback text pinned via map.json
(tiles.fallback). Page weight: maplibre-gl.js 276 KB gzipped (1.0 MB raw),
css 10 KB gzipped, map.json 10 KB — /map only, immutable-cached under
/assets/vendor/. iOS Safari/FxiOS QA outstanding → folded into the 4.2
post-deploy smoke check.

## Task 7.1 GO/NO-GO — LCCC contract-portfolio join (2026-07-29): GO

Dataset `cfd-contract-portfolio-status` (resource fdaf09d2-8cff-4799-a5b0-
1c59444e492b, 612 rows) carries CFD_ID, Status (enum: Live (Post-FIC) /
Live (Pre-FIC) / Pre-MDD / Pre-Start Date / Terminated), plus allocation
round and max contract capacity. Join measured against the settlement
snapshot: all 82 settlement CfD ids present — 100% coverage, including every
mapped-station contract. 48 terminated contracts in the portfolio.

## Task 7.3 GO/NO-GO — REMIT history depth (2026-07-29): GO

Elexon Insights REMIT (keyless) carries the historical archive, not just
post-migration data: platform-wide events from 2016 (344 in H1-2016; 2014-15
negligible), and per-BMU filtering works via `assetId` (e.g. T_HOWAO-1:
events in 2019, 2021, 2023 — Hornsea 1's whole operating life, including the
2021-22 payback period the chart showcases). The stream endpoint accepts
6-month windows; `latestRevisionOnly=true` handles revision collapse
server-side (still re-collapsed defensively in the engine). coverage_from is
stamped per station regardless.

## Golden-master note (2026-07-29)

The archived harness (`~/Archive/pre-vault/.../golden_master.py`) targets the
AU-branch module layout — its sharecard layer imports `subsidy_engine_uk.cards`
/ `siteconfig`, which do not exist on master — so it cannot run unmodified
here. The gate is applied in substance on this branch: rebuild on unchanged
code, verify the `site/` diff is timestamp churn + documented ≤1e-9 float
jitter only, `git restore -- site/`. Verified clean after task 1.2 (loader
change; no build-output change).
