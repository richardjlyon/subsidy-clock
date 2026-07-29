# add-interactive-asset-map — tasks

Golden-master note: this change reworks `subsidy_engine/sitedata.py`, so the UK
golden master (`POLARS_MAX_THREADS=1 uv run python '<cowork>/australia/phase1-evidence/golden_master.py' check`,
then `git restore -- site/`, `src/**/__pycache__` purged first) WILL diff on the
map outputs. Every engine gate below means: full suite green AND golden master
run, with any diff confined to the map/asset outputs and the re-baseline
justified in the commit message.

## 1. Phase A — verification and reference data

- [x] 1.1 Verify OpenFreeMap terms and (if terrain survives) AWS Terrain Tiles
      terms/attribution; record citations for the methodology source list.
      Go/no-go on terrain before any terrain code — GO (verification.md)
- [x] 1.2 Add the `slug` column to `reference/station_coords.csv` (hand-assigned,
      unique, stable); loader validation + tests (missing slug fails, duplicate
      fails)
- Gate: `uv run --group dev python -m pytest -q` green; golden master unchanged
  (no build outputs touched yet)

## 2. Phase A — engine map data

- [x] 2.1 Rework `_map_data`: emit slug/lat/lon markers, pinned attribution;
      delete `_web_mercator` and `_mapbox_static_url`; update map builder tests
      (do NOT commit rebuilt `site/data/` yet — schema change ships with the
      page in 4.x)
- Gate: full suite green; golden-master diff confined to map.json and justified

## 3. Phase A — site map page

- [x] 3.1 Vendor MapLibre GL JS + CSS + LICENSE into `site/assets/vendor/` with
      pinned version note and re-vendor procedure; add long-max-age header rule
      for `site/assets/vendor/` to `vercel.json`
- [x] 3.2 Rewrite `site/map.js`: boot MapLibre with OpenFreeMap style, terrain
      enhancement (if 1.1 passed), pinned attribution, pinned boot-failure
      fallback, reduced-motion handling
- [x] 3.3 GeoJSON marker layer: area ∝ cost, scheme colours, zoom-interpolated
      radius, hover tooltip parity with today; visually-hidden focusable
      station list driving the panel (a11y path — canvas circles can't focus)
- Gate: full suite green; manual QA desktop + iOS Safari/FxiOS; page weight
  measured and recorded

## 4. Phase A — ship (ONE push)

- [ ] 4.1 One push containing: rebuilt `map.json` (new schema), rewritten
      map page + vendored library, `site/mapbox-token.js` deletion,
      `scripts/inject-mapbox-token.js` deletion AND `vercel.json` buildCommand
      removal (deploys fail otherwise), updated map.html meta (canonical /map
      unchanged), methodology attribution/privacy wording
- [ ] 4.2 Post-deploy smoke check of live /map; then delete the `MAPBOX_TOKEN`
      Vercel env var (rollback is clean only before this step — noted in ship
      checklist)
- Gate: code + rebuilt data in ONE push; live smoke check passes

## 5. Phase B — engine asset JSON

- [x] 5.1 Per-asset builder in `sitedata.py`: CfD shape (header, hero, tiles
      with degenerate-case suppression, quarterly aggregation unclamped,
      contract rows) and RO-only shape; hero == marker cost enforced in the
      build; provenance block with data-to date
- [x] 5.2 Pin all panel wording in engine JSON with tests (basis notes, £/MWh
      label + not-shown wording, RO understatement + richer-data statement,
      unavailable-outages wording, provenance strings)
- Gate: full suite green; golden-master diff confined to new asset outputs and
  justified

## 6. Phase B — panel and ship (ONE push)

- [x] 6.1 Asset panel (side panel / bottom sheet): header, hero, tiles,
      diverging quarterly SVG chart + visually-hidden table, contract table,
      provenance footer — strings placed from JSON only; focus management per
      spec (into close control, back to activator)
- [x] 6.2 Run the dataviz palette validator on chart colours in light and dark
      modes; fix any FAIL
- [ ] 6.3 Ship: per-asset JSONs + panel code in ONE push; post-deploy smoke
      check (CfD asset, RO asset, payback quarter renders negative)
- Gate: full suite green; one push; live smoke check passes

## 7. Phase C — context layers (each behind go/no-go)

- [x] 7.1 GO/NO-GO: fetch LCCC contract-portfolio dataset; measure CfD_ID join
      coverage against `cfd_stations.csv`; record result in the change. If NO:
      skip 7.2
- [x] 7.2 Portfolio-status fetcher + snapshot store + status join (pinned
      "unknown" fallback) + panel status column; ship data + rendering together
- [x] 7.3 GO/NO-GO: measure REMIT history depth for a sample of mapped BMUs;
      record coverage window in the change; Richard decides ship/cut. If NO:
      skip 7.4–7.5
- [x] 7.4 Curate `reference/station_bmu_map.csv` from the Elexon BMU register,
      one source-cited row per BMU; loader + fixture tests
- [ ] 7.5 REMIT fetcher (latest-revision-per-mRID collapse, window aggregation,
      coverage_from stamp) + outage strip rendering with pinned
      coverage-window wording; ship data + rendering together
- [x] 7.6 Enforcement notes: schema + loader (allowlist, station check,
      fail-loud) + the Drax 2024 row drafted as close paraphrase, passed
      through the prepublication fact-check gate before commit + panel note
      rendering; ship together
- Gate per item: full suite green; golden-master diff confined and justified;
  each layer's data + rendering in one push
