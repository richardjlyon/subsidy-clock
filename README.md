# Subsidy Counter

A public dashboard measuring, in pounds sterling, the subsidies paid to UK renewable and low-carbon electricity generators since 2002. Figures are reconstructed bottom-up from official sources — LCCC (Contracts for Difference and Capacity Market), Elexon (wind constraint payments), Ofgem (Renewables Obligation and Feed-in Tariffs), and REF (constraint history) — with full provenance: every data point links to its source URL, retrieval timestamp, and content hash.

## Quickstart

```sh
uv sync
uv run pytest
uv run python -m subsidy_engine update all
uv run python -m subsidy_engine backfill-constraints --start 2024-01-01 --end 2024-03-31
uv run python -m subsidy_engine build-site
cd site && python3 -m http.server
```

Open http://localhost:8000 to view the dashboard.

## Data layout

```
data/raw/{scheme}/{table}/{partition}/{retrieved-at}/data.parquet
data/raw/{scheme}/{table}/{partition}/{retrieved-at}/manifest.json
```

`manifest.json` records: `source_url`, `retrieved_at`, `sha256` (content hash of the parquet file), and `row_count`. When a source revises history, the change is appended to `restatements.jsonl` alongside the old and new manifests. Nothing is ever deleted.

## Schemes

| Scheme | Source | Cadence | Method |
|---|---|---|---|
| CfD | LCCC data portal | Daily | Bottom-up: per-contract generation × (strike price − reference price) |
| Wind constraints | Elexon BMRS | Daily | Bottom-up from settlement stack; pre-2024 history from REF annual totals |
| Capacity Market | LCCC data portal | Monthly | Bottom-up: obligation volumes × auction clearing prices |
| Renewables Obligation | Ofgem annual reports | Annual | Official annual totals (ROCs presented × worth of a ROC) |
| Feed-in Tariffs | Ofgem annual reports | Annual | Official annual totals from FIT annual reports |

## Deployment

Enable the GitHub Action (`.github/workflows/update.yml`) for a daily update at 05:30 UTC, after LCCC and Elexon publish. Serve `site/` via GitHub Pages or any static host.

## Further reading

- [Functional specification](docs/2026-06-09-subsidy-tracker-functional-spec.md)
- [Methodology and sources](site/methodology.html)
