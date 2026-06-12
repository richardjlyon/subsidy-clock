# The Subsidy Clock

**Live at [subsidyclock.co.uk](https://subsidyclock.co.uk)** — a public dashboard measuring, in pounds sterling, the subsidies paid to UK renewable and low-carbon electricity generators since 2002.

Figures are reconstructed bottom-up from official sources — LCCC (Contracts for Difference and Capacity Market), Elexon (constraint payments and balancing costs), Ofgem (Renewables Obligation and Feed-in Tariffs), HMRC, DESNZ and NESO publications, and REF (cross-checks and constraint history) — with full provenance: every data point links to its source URL, retrieval timestamp and content hash.

This repository is the complete system: the data engine, the raw data store, the reference inputs and the static site. It exists to be audited. If you find an error in a published figure, please say so — confirmed errors are corrected and logged in public on the [corrections page](https://subsidyclock.co.uk/corrections), or you can [open an issue](../../issues/new?template=correction.yml).

## What is counted

Two layers, never invisibly blended:

- **Direct subsidies (measured)** — payments traceable to generators in official settlement data: Contracts for Difference (shown as two entries: renewables, and nuclear & biomass), the Renewables Obligation, Feed-in Tariffs, and wind constraint payments. The dashboard's headline counts **renewable generators only**, in nominal pounds — the most conservative reading.
- **Indirect costs (estimated)** — costs that settlement data does not attribute to individual generators: the Capacity Market, Climate Change Levy and Carbon Price Support, emissions trading, transmission charges (TNUoS) and balancing costs (BSUoS). Each carries a published attribution rule and is always marked estimated.

Some figures do combine the layers — the "in today's money" lead-in, the bracketed chip figures, the cumulative chart — but a combined figure always says so, and the estimated share is never folded into the measured headline.

The full derivation, scheme by scheme, is on the [methodology page](https://subsidyclock.co.uk/methodology).

## Quickstart

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest                                # money maths is verified to the penny
uv run python -m subsidy_engine update all   # fetch latest data from all sources
uv run python -m subsidy_engine build-site   # write site/data/*.json and the /data CSVs
cd site && python3 -m http.server
```

Open http://localhost:8000 to view the dashboard. Two further commands:

```sh
uv run python -m subsidy_engine backfill-constraints --start 2024-01-01 --end 2024-03-31
                                             # extend bottom-up constraints history
uv run python -m subsidy_engine build-cards  # render share-card PNGs (needs Playwright Chromium)
```

The raw data store is committed, so the published figures are reproducible from a clone without fetching anything.

## Repository layout

```
src/subsidy_engine/   retrieval (ckan.py, elexon.py, schemes/), money model (money.py),
                      reconciliation (reconcile.py), site data (sitedata.py),
                      share cards (sharecards.py), immutable store (store.py)
reference/            *.yaml reference inputs: buyout prices, CPIH deflators,
                      bill denominator, indirect-cost annuals, REF cross-checks
data/raw/             the Parquet store (see below)
site/                 the static site — no framework, no build step
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
| Transmission (TNUoS) | Indirect | NESO publications | Annual | Published attribution rule |
| Balancing (BSUoS) | Indirect | Elexon BMRS (history: NAO) | Daily | Uplift above baseline, constraints netted to avoid double-counting |

Attribution rules and their confidence levels are quoted in full on the [methodology page](https://subsidyclock.co.uk/methodology#indirect).

## Automation

A GitHub Action (`.github/workflows/update.yml`) runs daily at 05:30 UTC, after LCCC and Elexon publish: it updates all schemes (a failing scheme flags stale data on the site rather than blocking the others), extends the constraints backfill by one week, rebuilds the site data and share cards, commits, and triggers the production deploy.

## Data reuse

Every published series is downloadable as CSV from [subsidyclock.co.uk/data](https://subsidyclock.co.uk/data) under CC BY 4.0, with attribution headers in each file. CSVs are written from the same model that feeds the dashboard, so they cannot disagree with it.
