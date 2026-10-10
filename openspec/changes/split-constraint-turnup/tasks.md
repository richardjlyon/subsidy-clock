# split-constraint-turnup — tasks

Tests: `uv run --group dev python -m pytest -q`. Golden master:
`uv run python tools/golden_master.py check`, then `git restore -- site/`.

## 1. Turn-up scheme

- [ ] 1.1 `schemes/constraint_turnup.py`: parse accepted offers (method a) by fuel,
      replacement estimate (method b), system-flagged wind bids; verify with
      `tests/test_constraint_turnup.py` (fixture tests incl. the pro-rata margin)
- [ ] 1.2 Concurrent day fetch with retries, backfill and 3-day update; verify a
      real one-day fetch matches the prototype figures for that day
- [ ] 1.3 CLI `update constraint_turnup` (and in `update all`) and `backfill-turnup`;
      verify `tests/test_cli.py`
- Gate: full suite green

## 2. BSUoS netting

- [ ] 2.1 `build.py`: turn-up indirect scheme capped inside the BSUoS uplift, BSUoS
      net of it, same rule on run-rates; verify the parts-sum-to-raw test in
      `tests/test_bsuos.py` and the headline-unchanged test
- [ ] 2.2 Build-site freshness entry for turn-up; verify build-site runs
- Gate: full suite green; golden-master diff confined to BSUoS/turn-up outputs,
  headline `combined_real` unchanged

## 3. Backfill and reconciliation

- [ ] 3.1 Backfill turn-up from the first Elexon stack date to yesterday; verify
      partition count and empty-day report
- [ ] 3.2 `tools/constraint_reconciliation.py`: monthly table 2024–date vs Octopus
      and NESO; verify it runs against live sources
- [ ] 3.3 `scratch/2026-10-10-constraint-reconciliation.md`: table, gap
      explanations, named totals, verdict, attribution options table
- Gate: full suite green; reconciliation doc written from a real run

## 4. Hand-over (Richard)

- [ ] 4.1 Richard chooses an attribution option (unchecked until he does)
- [ ] 4.2 Site wiring for the new scheme id lands with the merge — MERGE BLOCKER
- [ ] 4.3 memory.md updated; Plane SUBCLK comment if an item exists
