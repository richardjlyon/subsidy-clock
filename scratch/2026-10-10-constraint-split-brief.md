# Brief: split constraint turn-up costs out of balancing, and reconcile with Octopus's Wasted Wind

You are working in the Subsidy Clock repo, `~/AIOS/Projects/subsidy-clock` (live site subsidyclock.co.uk). Read `AGENTS.md` and `memory.md` first. Then read `src/subsidy_engine_uk/schemes/constraints.py`, `src/subsidy_engine_uk/schemes/bsuos.py` and the money model that attributes BSUoS. The Clock's rule: every figure must be defensible to a hostile expert.

## Why

Octopus Energy's Wasted Wind tracker says Britain's constraint bill passed £1.5bn on 5 Oct 2026, beating 2025's £1.47bn; September 2026 alone was £404.3m. That bill has two parts: paying wind farms to switch off (curtailment), and paying other plant, mostly gas, to switch on and replace that power (turn-up). The Clock counts only the first, as its direct `constraints` line: £397m in 2025 and £254m in 2026 to 8 Oct. The turn-up side is buried inside the indirect `bsuos` line, which is NESO's whole balancing bill above a 2002-05 baseline, minus the wind constraint payments. So we can't currently check Octopus's figure, and we can't say how much of the constraint bill goes to gas plants.

## Goal

1. Measure constraint turn-up cost as its own series, daily, from primary data.
2. Take it out of the BSUoS line so nothing is counted twice.
3. Reconcile curtailment plus turn-up against Octopus's Wasted Wind figures and NESO's own constraint-cost publication, and explain every gap.

## Sources

- **Elexon Insights API** (already used by `constraints.py` for wind bids). Octopus's stated method: 'For curtailment, the amount of lost wind energy is measured, as well as the cost of paying wind farms to stop generation. For turn-up, the cost of buying the same amount of energy from other sources is estimated using real energy prices.' (https://wastedwind.energy, methodology by Robin Hawkes). Note that Octopus ESTIMATES turn-up by pricing the lost volume; it does not sum the actual accepted offers. Build both if feasible: (a) actual accepted offers from non-wind units tagged as constraint (system-flagged) actions, and (b) Octopus-style lost wind volume x a replacement price. Then report which one matches Octopus.
- **NESO Constraint Breakdown Costs and Volume**: weekly CSVs by financial year from 2017-18. Costs and volumes split into thermal, voltage and inertia. https://www.neso.energy/data-portal/constraint-breakdown (CKAN id `constraint-breakdown`; the repo already has a CKAN client). Thermal is the category that corresponds to the wind-export bottleneck. Use it as the independent official check, and read its definitions before mapping anything.
- Also see https://www.neso.energy/data-portal/thermal-constraint-costs.

## Constraints

- **Spec first.** This repo uses OpenSpec (`openspec/changes/`). Write the change proposal before code.
- **Don't decide attribution.** If turn-up moves from the indirect layer (BSUoS, partly attributed) to the direct layer (100% attributed), the public headline changes. Not all thermal constraint cost is caused by wind. Write out the options and their effect on `headline.combined_real` and the direct hero, with numbers, and stop for Richard's decision. Default for the build: move turn-up within the indirect layer, so the headline is unchanged, and show the alternatives side by side.
- **No double counting.** Prove with a test that BSUoS minus the wind constraint payments minus turn-up, plus the parts, still sums to the raw BSUoS total.
- **A push to `master` is a publication** (Cloudflare Pages deploys). Do not push, do not touch `site/` copy, and do not edit `corrections.jsonl` without Richard's approval. Work on a branch.
- **Tests:** add focused tests next to `tests/test_constraints.py` and `tests/test_bsuos.py`, and run the full suite.
- **Secrets** (if needed): 1Password `Automation` vault via the `secrets` skill. Never paste keys.

## Deliverables (on a branch, unpushed)

1. OpenSpec change proposal plus the implemented change.
2. A new daily turn-up series in the engine, with backfill as far as the Elexon data allows.
3. `scratch/2026-10-XX-constraint-reconciliation.md`: a monthly table for 2024 to date with these columns: Clock curtailment | Clock turn-up (method a) | turn-up (method b) | Octopus Wasted Wind total | NESO thermal constraint cost. Show the gap for each against Octopus and NESO, and explain each gap (definitions, unit coverage, pricing, timing, revisions). Name the 2025 annual and the 1 Jan to 5 Oct 2026 totals explicitly.
4. A one-paragraph verdict: does Octopus's £1.5bn stand up, and roughly what share of the constraint bill goes to the plants switched on rather than the wind farms switched off?
5. An attribution options table (see Constraints), for Richard to decide.
6. Updated `memory.md`, and a comment on the Plane SUBCLK item if one exists.

Report back with: the branch name, test results (real run output), the verdict paragraph, and the options table. Nothing else.
