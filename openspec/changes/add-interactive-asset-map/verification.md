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

## Golden-master note (2026-07-29)

The archived harness (`~/Archive/pre-vault/.../golden_master.py`) targets the
AU-branch module layout — its sharecard layer imports `subsidy_engine_uk.cards`
/ `siteconfig`, which do not exist on master — so it cannot run unmodified
here. The gate is applied in substance on this branch: rebuild on unchanged
code, verify the `site/` diff is timestamp churn + documented ≤1e-9 float
jitter only, `git restore -- site/`. Verified clean after task 1.2 (loader
change; no build-output change).
