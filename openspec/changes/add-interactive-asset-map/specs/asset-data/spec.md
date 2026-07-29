# asset-data — delta spec

## ADDED Requirements

### Requirement: map.json carries pinned slugs and geographic coordinates
The site build SHALL emit `map.json` markers as `{slug, name, lat, lon, scheme,
technology, cost}` with lat/lon and slug taken from
`reference/station_coords.csv` (slug is a new hand-assigned column). Pixel-space
projection (`x`, `y`) and the Mapbox Static Images URL SHALL be removed.
Tile-source attribution strings SHALL ship engine-pinned in `map.json`. The
build SHALL fail loudly on a mapped station whose coords row lacks a slug, or
on duplicate slugs. Stations absent from the coords file SHALL be dropped from
the map (as today) and reported in the build log.

#### Scenario: Marker shape
- **WHEN** the site build runs
- **THEN** every map.json marker has slug, lat and lon, no marker has x or y,
  and the basemap block contains attribution but no Mapbox URL

#### Scenario: Slug stability
- **WHEN** an upstream data refresh changes a station's published name
- **THEN** the marker's slug (from the reference file) is unchanged and its
  asset JSON path is stable

### Requirement: Per-asset JSON is built for every marker
The site build SHALL emit `site/data/assets/<slug>.json` for every map.json
marker. CfD markers carry: header, hero cumulative payment, stat tiles,
quarterly net-payment series aggregated across the station's contracts by
calendar quarter, per-contract rows (cfd_id, unit_name, latest strike, first
settlement, cumulative paid, status), optional outages, optional enforcement
note, and provenance (pinned source names + data-to date). RO markers carry the
RO-only shape: header, hero buy-out value, pinned understatement note,
provenance — no tiles, no quarters, no contracts. The build SHALL enforce that
each asset JSON's hero value equals its marker's cost.

#### Scenario: Asset JSON reconciles
- **WHEN** the site build completes
- **THEN** for every marker there is an asset JSON whose hero value equals the
  marker's cost, and for CfD markers the contract cumulative values sum to the
  hero value

#### Scenario: Negative quarters survive aggregation
- **WHEN** a station's daily settlement rows net to a negative payment in a
  quarter
- **THEN** the asset JSON's quarters array carries that negative value unclamped

### Requirement: Effective-rate tile suppresses degenerate cases
The effective payment-per-subsidised-MWh tile value SHALL be cumulative payment
÷ cumulative generation, computed only when cumulative payment is positive and
cumulative generation is positive and complete. Otherwise the tile SHALL be
omitted from the JSON with pinned "not shown" wording available to the panel —
never a negative, infinite, or zero-standing-for-unknown rate.

#### Scenario: Payback-dominated asset
- **WHEN** a station's cumulative payment is negative or zero
- **THEN** its asset JSON carries no effective-rate tile and carries the pinned
  not-shown wording

### Requirement: Contract status comes from the LCCC portfolio dataset after join verification
Before any dependent code ships, the join between the LCCC contract-portfolio
dataset's contract ids and settlement `CfD_ID` SHALL be verified and its
coverage recorded in the change. The engine SHALL then fetch the portfolio
dataset, snapshot-store it, and join per-contract status into the asset JSON
contract rows. A contract absent from the portfolio data SHALL carry the pinned
status "unknown", never a guessed status.

#### Scenario: Terminated contract is labelled
- **WHEN** the portfolio dataset marks a contract terminated
- **THEN** the asset JSON contract row carries the pinned terminated status

#### Scenario: Unmatched contract
- **WHEN** a settlement CfD_ID has no portfolio row
- **THEN** its contract row status is the pinned "unknown"

### Requirement: Outage history derives from REMIT via a curated BMU mapping, with stated coverage
Before any dependent code ships, the temporal depth of Elexon REMIT
unavailability history for the mapped BMUs SHALL be measured and recorded in
the change (go/no-go). The engine SHALL fetch REMIT messages for the BMU ids in
`reference/station_bmu_map.csv`, collapse revisions to the latest message per
mRID, aggregate to outage windows `{start, end, type, mw_lost}`, snapshot-store
the result, and stamp each asset's outages block with its `coverage_from` date.
Stations without a mapping SHALL ship no outages block and be rendered
unavailable, not zero. Each mapping row SHALL cite its source.

#### Scenario: Revision collapse
- **WHEN** REMIT fixture messages contain multiple revisions of one mRID
- **THEN** only the latest revision contributes to the outage windows

#### Scenario: Coverage window is stamped
- **WHEN** the earliest REMIT record for a station's BMUs is dated D
- **THEN** the asset JSON's outages block carries coverage_from = D

#### Scenario: Unmapped station ships unavailable
- **WHEN** a mapped station has no row in station_bmu_map.csv
- **THEN** its asset JSON has no outages block

### Requirement: Enforcement notes are curated, source-cited and fact-check-gated
The build SHALL read `reference/enforcement_notes.csv` (station, date, text,
source_url) and pin each note into the matching asset JSON. The build SHALL
fail if a note row lacks a source_url, cites a domain outside the official
allowlist (ofgem.gov.uk, gov.uk, lowcarboncontracts.uk), or names a station not
in the mapped set. Note text SHALL be a close paraphrase of the cited document,
and every row SHALL pass the prepublication fact-check gate before it is
committed. An empty file SHALL be a valid state.

#### Scenario: Note without a source fails the build
- **WHEN** a note row has an empty source_url or a non-allowlisted domain
- **THEN** the build fails loudly naming the offending row

#### Scenario: Empty file is valid
- **WHEN** enforcement_notes.csv contains only the header row
- **THEN** the build succeeds and no asset JSON carries a note
