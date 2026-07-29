# add-interactive-asset-map — verification record

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

## Golden-master note (2026-07-29)

The archived harness (`~/Archive/pre-vault/.../golden_master.py`) targets the
AU-branch module layout — its sharecard layer imports `subsidy_engine_uk.cards`
/ `siteconfig`, which do not exist on master — so it cannot run unmodified
here. The gate is applied in substance on this branch: rebuild on unchanged
code, verify the `site/` diff is timestamp churn + documented ≤1e-9 float
jitter only, `git restore -- site/`. Verified clean after task 1.2 (loader
change; no build-output change).
