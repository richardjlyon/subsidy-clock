# The Subsidy Clock

**Live at [subsidyclock.co.uk](https://subsidyclock.co.uk)** — a public dashboard measuring, in pounds sterling, the subsidies paid to UK renewable and low-carbon electricity generators since 2002.

Figures are reconstructed bottom-up from official sources — LCCC (Contracts for Difference and Capacity Market), Elexon (constraint payments), NESO (balancing costs and transmission charges), Ofgem (Renewables Obligation and Feed-in Tariffs), HMRC, DESNZ, the NAO and REF (cross-checks and constraint history) — with full provenance: every retrieved data point links to its source URL, retrieval timestamp and content hash.

This repository is the complete system: the data engine, the raw data store, the reference inputs and the static site. It exists to be audited. If you find an error in a published figure, please say so — confirmed errors are corrected and logged in public on the [corrections page](https://subsidyclock.co.uk/corrections), or you can [open an issue](../../issues/new?template=correction.yml).

## What is counted

Two layers, never invisibly blended:

- **Direct subsidies (measured)** — payments traceable to generators in official settlement data: Contracts for Difference (renewables, including biomass), the Renewables Obligation, Feed-in Tariffs, and wind constraint payments. The dashboard's headline counts **renewable generators**, in nominal pounds. Biomass holds renewable contracts and counts towards the UK's renewable targets, so it is in the headline; the only CfD generation classed as non-renewable is nuclear (low-carbon but not renewable), which is tracked separately and appears once Hinkley Point C generates.
- **Indirect costs (estimated)** — costs that settlement data does not attribute to individual generators: the Capacity Market, Climate Change Levy and Carbon Price Support, emissions trading, transmission charges (TNUoS) and balancing costs (BSUoS). Each carries a published attribution rule and is always marked estimated. Some early years of the network and balancing series rest on a secondary tabulation pending confirmation against the primary source; this is disclosed in each scheme's source notes.

Some figures do combine the layers — the "in today's money" lead-in, the bracketed chip figures, the cumulative chart — but a combined figure always says so, and the estimated share is never folded into the measured headline.

The full derivation, scheme by scheme, with every attribution rule and its confidence level, is on the [methodology page](https://subsidyclock.co.uk/methodology).

## On the site

Beyond the headline counter and the per-scheme breakdown, the dashboard shows:

- **Largest recipients** — CfD contracts grouped into physical stations (multi-phase wind farms expand to their individual contracts), named Renewables Obligation generators on a buy-out basis, and constraint payments by Balancing Mechanism lead party.
- **[Where the money lands](https://subsidyclock.co.uk/map)** — the same recipients plotted on a map of Great Britain, each bubble sized by cumulative payment and coloured by scheme.
- **Cost over time**, in real (2024) and nominal terms, and subsidy as a share of the electricity bill.

The station groupings, the per-station Renewables Obligation allocation and the transmission-charge series are derived from public datasets compiled by David Turver, each traced to its underlying primary (the LCCC contract register, Ofgem ROC data, NESO charging statements) and cited there.

## Quickstart

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest                                # the money model is verified to the penny
uv run python -m subsidy_engine update all   # fetch latest data from all sources
uv run python -m subsidy_engine build-site   # write site/data/*.json and the /data CSVs
cd site && python3 -m http.server
```

Open http://localhost:8000 to view the dashboard. (The deployed site uses clean URLs, so multi-page links have no `.html`; with `http.server` either add the `.html` suffix or run `npx serve site`, which matches production.) Two further commands:

```sh
uv run python -m subsidy_engine backfill-constraints --start 2024-01-01 --end 2024-03-31
                                             # extend bottom-up constraints history
uv run python -m subsidy_engine build-cards  # render share-card PNGs (needs Playwright Chromium)
```

The raw data store is committed, so **every published figure is reproducible from a clone with no network access**. The one exception is the map's basemap image, which is fetched live from Mapbox and needs an access token (see Deployment); the map's underlying data, like all figures, reproduces offline.

## Repository layout

```
src/subsidy_engine/   retrieval (ckan.py, elexon.py, schemes/), money model (money.py),
                      reconciliation (reconcile.py), reference loaders (reference.py),
                      station/recipient mapping (stations.py), site data (sitedata.py),
                      share cards (sharecards.py), immutable store (store.py)
reference/            reference inputs: CPIH deflators, buy-out prices, bill denominator,
                      indirect-cost annuals and REF cross-checks (*.yaml); CfD→station and
                      named-RO mappings, station coordinates (*.csv); the map basemap config
data/raw/             the Parquet store (see below)
scripts/              deploy-time helper(s), e.g. Mapbox token injection
site/                 the static site — no framework, no bundler
tests/                pytest suite
```

## Data integrity

```
data/raw/{scheme}/{table}/{partition}/{retrieved-at}/data.parquet
data/raw/{scheme}/{table}/{partition}/{retrieved-at}/manifest.json
```

`manifest.json` records `source_url`, `retrieved_at`, `sha256` (content hash of the table's canonical CSV serialisation) and `row_count`. The store is append-only:

- **Nothing is ever deleted.** When a source revises history, the new version is stored alongside the old and the change is logged in `restatements.jsonl` — published at [/data](https://subsidyclock.co.uk/data) as `restatements.csv`.
- **Our own mistakes are logged the same way.** Confirmed errors in published figures go to `corrections.jsonl`, published at [/corrections](https://subsidyclock.co.uk/corrections). A published figure is never silently edited.
- **Reconciliation guards run at build time.** Bottom-up totals are checked against official aggregates and REF's published series; the build fails loudly if they drift out of tolerance.

## Schemes

| Scheme | Layer | Source | Cadence | Method |
|---|---|---|---|---|
| Contracts for Difference | Direct | LCCC data portal | Daily | Per-contract generation × (strike − reference price), paybacks netted |
| Wind constraints | Direct | Elexon BMRS | Daily | Settlement bid stacks; earlier years from REF annual totals |
| Renewables Obligation | Direct | Ofgem annual reports | Annual | ROCs presented × (buy-out price + recycle value) |
| Feed-in Tariffs | Direct | Ofgem annual reports | Annual | Official levelisation totals |
| Capacity Market | Indirect | LCCC data portal | Monthly | Obligation volumes × auction clearing prices |
| CCL & Carbon Price Support | Indirect | HMRC bulletin | Annual | Electricity share of receipts |
| Emissions trading (UK/EU ETS) | Indirect | DESNZ trust statement | Annual | Power-sector share of auction revenue |
| Transmission (TNUoS) | Indirect | NESO charging statements | Annual | Uplift above pre-renewables baseline, floored at zero |
| Balancing (BSUoS) | Indirect | NESO data portal (history: NAO) | Daily | Uplift above baseline, constraints netted to avoid double-counting |

Attribution rules and their confidence levels are quoted in full on the [methodology page](https://subsidyclock.co.uk/methodology#indirect).

## Automation

A GitHub Action (`.github/workflows/update.yml`) runs daily at 05:30 UTC, after LCCC and Elexon publish: it updates all schemes (a failing scheme flags stale data on the site rather than blocking the others), extends the constraints backfill by one week, rebuilds the site data and share cards, commits, and triggers the production deploy via a Vercel deploy hook.

## Deployment

The site is static and hosted on Vercel (serving `site/`). The only build-time step is `scripts/inject-mapbox-token.js`, which writes the Mapbox access token from the `MAPBOX_TOKEN` environment variable into a git-ignored file the map page reads at runtime. The token is a public, domain-restricted client token; **it is never committed to the repository**. Everything except the map's basemap image is independent of it.

## Data reuse

Every published series is downloadable as CSV from [subsidyclock.co.uk/data](https://subsidyclock.co.uk/data) under CC BY 4.0, with attribution headers in each file. CSVs are written from the same model that feeds the dashboard, so they cannot disagree with it.

## Licence

- **Code** (engine, site, tests): [MIT](LICENSE).
- **Published data** (the JSON and CSV series this engine produces): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), credit "The Subsidy Clock — subsidyclock.co.uk".
- **Upstream official data** (LCCC, Elexon, NESO, Ofgem, HMRC, DESNZ, NAO): subject to the source bodies' own terms, generally the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
