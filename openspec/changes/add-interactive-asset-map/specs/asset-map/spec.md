# asset-map — delta spec

## ADDED Requirements

### Requirement: Interactive map replaces the static basemap
The `/map` page SHALL render an interactive MapLibre GL map of Great Britain
(pan/zoom, keyless tile sources, 3D terrain as progressive enhancement) from
vendored, committed library files with their licence committed alongside. No
access token SHALL be required or shipped, and the page SHALL contain no
reference to `mapbox-token.js`. If the map library fails to initialise, the
page SHALL show the engine-pinned fallback text and a link to the recipients
table — never a blank or broken frame. If terrain tiles fail, the map SHALL
continue flat without error. When `prefers-reduced-motion` is set, map
animations SHALL be disabled.

#### Scenario: Map boots without tokens
- **WHEN** /map loads on a supported browser
- **THEN** the interactive map renders with basemap tiles and pinned
  attribution, the page source contains no `mapbox-token.js` script tag, and no
  request is made to any Mapbox endpoint

#### Scenario: Library failure degrades honestly
- **WHEN** the vendored map library throws on initialisation
- **THEN** the page shows the engine-pinned fallback message with a working link
  to the recipients data, and no partial map chrome remains visible

### Requirement: Marker semantics are preserved
The map SHALL show one marker per `map.json` entry (station × scheme — a
station paid under two schemes appears once per scheme, as today), with marker
area proportional to cumulative payment, coloured by scheme, positioned by
lat/lon. Constraint-payment recipients SHALL remain excluded, with the existing
engine-pinned explanation visible on the page.

#### Scenario: Markers match the data
- **WHEN** map.json contains N markers
- **THEN** the map renders exactly N markers, the largest-payment station has
  the largest marker, and each marker's colour matches its scheme's legend entry

### Requirement: Click opens the asset X-ray panel
Activating a marker SHALL open a panel — side panel at desktop widths, bottom
sheet on mobile — populated solely from that asset's
`site/data/assets/<slug>.json`. The panel SHALL contain: the hero value; stat
tiles (when present in the JSON); the quarterly net-payment chart (when
present); the contract table (when present); the outage strip (when present);
the enforcement note (when present); and the provenance footer including the
pinned source names and data-to date. Every string SHALL be placed from
engine-pinned JSON — the page SHALL NOT author wording.

#### Scenario: Panel renders a CfD asset
- **WHEN** a CfD station marker is activated
- **THEN** the panel shows hero payment, generation and payment-per-MWh tiles,
  the quarterly chart, and one contract row per contract, all matching the
  asset JSON values exactly, with the data-to date in the footer

#### Scenario: Keyboard access via the station list
- **WHEN** a user tabs to the visually-hidden station list and activates a
  station's button
- **THEN** the same panel opens populated for that station, focus moves to the
  panel's close control, and dismissing the panel returns focus to the
  activating button

#### Scenario: Mobile bottom sheet
- **WHEN** a marker is tapped on a viewport narrower than the desktop
  breakpoint
- **THEN** the panel opens as a dismissible bottom sheet with the same content

### Requirement: Quarterly chart shows paybacks as negative
The panel chart SHALL be a diverging column chart of quarterly net payments
around a zero baseline: positive quarters above, negative (payback) quarters
below in a visually distinct diverging colour. The palette SHALL pass the CVD
validator in light and dark modes. A visually-hidden table of the quarterly
values SHALL accompany the chart for screen readers.

#### Scenario: Payback quarter renders below the line
- **WHEN** an asset's JSON contains a quarter with negative payment_gbp
- **THEN** that column renders below the zero baseline in the diverging colour,
  and the accessible table row shows the negative value

### Requirement: RO-only assets degrade honestly
For an RO marker, the panel SHALL show the buy-out value as hero, technology,
and the engine-pinned understatement note — which SHALL also state that richer
per-station Ofgem data exists and is not yet shown — and SHALL NOT render
empty tiles, an empty chart, or zeroes standing in for unknowns.

#### Scenario: RO-only panel
- **WHEN** an RO marker is activated
- **THEN** the panel shows hero buy-out value and the pinned basis note
  (including the richer-data statement), with no chart region and no
  generation or payment-per-MWh tiles

### Requirement: Outage and enforcement context is presented neutrally
When the asset JSON carries outage events, the panel SHALL render them as a
compact timeline strip labelled with engine-pinned neutral wording that states
the coverage window (records from the JSON's coverage_from date). When the
station has no BMU mapping, the panel SHALL state outage history is unavailable
(never imply zero outages). When the asset JSON carries an enforcement note,
the panel SHALL render the pinned text verbatim with a link to the cited
official document.

#### Scenario: Coverage window is stated
- **WHEN** an asset JSON carries outages with coverage_from "2023-01-01"
- **THEN** the strip's pinned label includes that date, and no part of the
  panel implies the pre-2023 period was outage-free

#### Scenario: Unmapped station
- **WHEN** an asset JSON has no outages block
- **THEN** the panel shows the engine-pinned "unavailable" wording, not an
  empty timeline and not "no outages"

#### Scenario: Enforcement note renders with its source
- **WHEN** an asset JSON contains an enforcement note
- **THEN** the panel renders the note text verbatim with a working link to the
  official source document
