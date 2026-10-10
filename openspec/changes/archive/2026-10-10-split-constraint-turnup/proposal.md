# split-constraint-turnup

## Why

A constraint costs money twice: NESO pays wind farms to switch off (curtailment)
and pays other plant, mostly gas, to switch on and replace that power (turn-up).
The Clock measures only the first, as its direct `constraints` line. The second
sits unseen inside the indirect `bsuos` line, which is the whole balancing bill
above a 2002-05 baseline, net of the wind payments. So the Clock cannot check
Octopus's Wasted Wind figure (over £1.5bn in 2026 by 5 Oct), and cannot say how
much of the constraint bill goes to the plants switched on. Octopus's number is
now being quoted, so the gap needs closing.

## What Changes

- New daily scheme `constraint_turnup`, measured from Elexon's settlement stacks
  (the same public API the `constraints` line already reads), backfilled to the
  first date Elexon publishes stack data (November 2015). Each day stores:
  - **replacement estimate** (method b, the engine's figure): Octopus's method,
    pricing the switched-off wind volume against that period's accepted offers.
    Tied to the wind volume by construction, and reproducible against Octopus;
  - **accepted offers** (method a, cross-check): accepted offers flagged as
    system actions (`soFlag`) from units that are not wind, by fuel type, in all
    periods, and separately in periods when wind was switched off;
  - **system-flagged wind bids**: Octopus's curtailment definition, kept so the
    curtailment gap can be explained.
- The `bsuos` line becomes balancing above baseline, net of wind constraint
  payments AND net of turn-up. Turn-up becomes its own **indirect** line.
  Indirect total, combined headline and direct hero are unchanged. This is the
  default the brief sets; it does not decide attribution.
- A reconciliation tool comparing Clock curtailment, both turn-up methods,
  Octopus's published figures and NESO's thermal constraint cost, by month.
- CLI: `update constraint_turnup` (in `update all`) and `backfill-turnup`.

## Non-goals

- **No attribution decision.** Moving turn-up into the direct layer, or scaling
  it to a wind-caused share, is Richard's call. The options are tabled with
  numbers; none is built.
- **No site copy.** No `site/` edits, no explainer, no card. The site does not
  yet know the new scheme id (see Impact): wiring it is a follow-on change.
- No corrections entry: no published figure changes.
- No NESO constraint-breakdown ingestion into the engine; the reconciliation
  tool reads it directly.
- No change to the `constraints` line's own method (all wind bids, any flag).

## Capabilities

### New Capabilities

- `constraint-turnup`: measuring constraint turn-up cost daily from primary
  data, splitting it out of the BSUoS line without double counting, and
  reconciling it against Octopus and NESO.

### Modified Capabilities

(none — `openspec/specs/` holds no main specs yet)

## Impact

- Code: new `src/subsidy_engine_uk/schemes/constraint_turnup.py`;
  `subsidy_engine_uk/build.py` (BSUoS netting); `subsidy_engine_uk/cli.py` and
  `subsidy_engine/__main__.py` (commands); new `tools/constraint_reconciliation.py`.
- Data: new store partitions `data/raw/constraint_turnup/daily/<date>`.
- Published outputs on next build: `breakdown.json`/`timeseries.json` gain a
  `constraint_turnup` scheme and the `bsuos` scheme falls by the same amount;
  a new `constraint_turnup.csv`. **Merge blocker:** the site's scheme tables
  (`app.js` `SCHEME_META`/`STACK_ORDER`, sharecards `CHART_STACK`, methodology
  lists) do not know the new id, so the BSUoS card would drop with no matching
  card. Do not merge before Richard decides attribution and the site wiring
  lands with it.
