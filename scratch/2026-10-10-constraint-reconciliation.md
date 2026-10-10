# Constraint bill reconciliation — Clock vs Octopus Wasted Wind vs NESO

10 October 2026. Branch `constraint-turnup-split`, unpushed. All figures £m, nominal, by calendar month. Produced by `uv run python tools/constraint_reconciliation.py` from the local store, using Octopus and NESO data read live on 10 Oct 2026.

## What each column is

- **Clock curtailment**: the Clock's `constraints` line. Every accepted wind bid, whatever its flag (REF's convention).
- **Turn-up (a)**: money actually paid on accepted offers that NESO flagged as system actions (`soFlag`), from every unit that isn't wind, in every half-hour.
- **Turn-up (b)**: Octopus's method, now the Clock's figure. In each half-hour, take the volume of wind switched off for system reasons and price it against that half-hour's accepted offers. Short-duration "CADL" offers are left out; the remaining offers are taken unflagged first, then in acceptance order, with a part-share of whichever offer crosses the line.
- **Octopus total**: Wasted Wind's published monthly curtailment plus turn-up (`wastedwind.energy/api/summary/{year}`).
- **NESO thermal**: NESO's Constraint Breakdown Costs, thermal category, summed by day (CKAN `constraint-breakdown`).
- **Gap columns**: Clock curtailment plus the turn-up method named, minus the comparator.

## Monthly table, January 2024 to date

| Month | Clock curtailment | Turn-up (a) | Turn-up (b) | Octopus total | NESO thermal | Clock (b) − Octopus | Clock (b) − NESO | Clock (a) − Octopus | Clock (a) − NESO |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2024-01 | 33.0 | 54.4 | 45.1 | 76.1 | 95.6 | 2.0 | -17.4 | 11.3 | -8.2 |
| 2024-02 | 33.8 | 49.9 | 49.2 | 81.7 | 93.1 | 1.3 | -10.2 | 2.0 | -9.4 |
| 2024-03 | 29.6 | 66.6 | 47.2 | 74.4 | 93.9 | 2.4 | -17.2 | 21.8 | 2.3 |
| 2024-04 | 33.9 | 88.8 | 59.4 | 90.0 | 98.7 | 3.3 | -5.4 | 32.7 | 24.0 |
| 2024-05 | 5.5 | 56.6 | 13.2 | 18.2 | 46.7 | 0.5 | -28.0 | 43.9 | 15.4 |
| 2024-06 | 29.0 | 69.3 | 55.5 | 82.9 | 117.0 | 1.7 | -32.5 | 15.5 | -18.6 |
| 2024-07 | 11.1 | 41.2 | 22.1 | 32.8 | 46.0 | 0.3 | -12.8 | 19.4 | 6.3 |
| 2024-08 | 68.6 | 83.3 | 119.2 | 185.9 | 198.3 | 1.8 | -10.5 | -34.1 | -46.4 |
| 2024-09 | 32.1 | 49.0 | 59.9 | 91.3 | 92.4 | 0.8 | -0.4 | -10.1 | -11.3 |
| 2024-10 | 47.7 | 71.1 | 114.2 | 160.5 | 189.9 | 1.5 | -28.0 | -41.6 | -71.1 |
| 2024-11 | 29.6 | 51.0 | 98.9 | 128.3 | 166.4 | 0.1 | -38.0 | -47.8 | -85.9 |
| 2024-12 | 56.9 | 48.5 | 151.4 | 208.0 | 244.4 | 0.4 | -36.0 | -102.6 | -139.0 |
| 2025-01 | 10.5 | 37.5 | 67.2 | 77.4 | 117.3 | 0.3 | -39.6 | -29.4 | -69.3 |
| 2025-02 | 32.8 | 50.7 | 142.7 | 175.3 | 217.2 | 0.3 | -41.7 | -91.8 | -133.7 |
| 2025-03 | 24.3 | 45.8 | 111.0 | 134.6 | 175.7 | 0.6 | -40.4 | -64.6 | -105.6 |
| 2025-04 | 9.9 | 48.9 | 24.7 | 31.7 | 47.7 | 2.9 | -13.1 | 27.1 | 11.1 |
| 2025-05 | 21.3 | 100.1 | 44.8 | 64.7 | 85.4 | 1.5 | -19.3 | 56.7 | 36.0 |
| 2025-06 | 54.2 | 109.1 | 115.4 | 165.6 | 190.8 | 3.9 | -21.3 | -2.3 | -27.5 |
| 2025-07 | 21.2 | 51.8 | 43.8 | 64.7 | 92.2 | 0.2 | -27.2 | 8.3 | -19.2 |
| 2025-08 | 40.1 | 88.5 | 84.2 | 123.8 | 148.7 | 0.4 | -24.4 | 4.7 | -20.1 |
| 2025-09 | 54.3 | 80.4 | 110.0 | 161.7 | 195.3 | 2.5 | -31.0 | -27.1 | -60.7 |
| 2025-10 | 55.4 | 83.6 | 138.8 | 193.2 | 220.4 | 1.0 | -26.2 | -54.2 | -81.4 |
| 2025-11 | 35.3 | 72.2 | 105.5 | 140.4 | 177.7 | 0.3 | -37.0 | -33.0 | -70.3 |
| 2025-12 | 38.2 | 42.5 | 95.6 | 133.7 | 162.4 | 0.1 | -28.6 | -53.0 | -81.7 |
| 2026-01 | 28.0 | 38.2 | 138.6 | 166.7 | 210.2 | -0.0 | -43.6 | -100.5 | -144.0 |
| 2026-02 | 15.2 | 44.1 | 87.2 | 101.4 | 136.4 | 1.1 | -34.0 | -42.0 | -77.0 |
| 2026-03 | 47.5 | 88.6 | 185.4 | 232.7 | 288.7 | 0.2 | -55.8 | -96.6 | -152.6 |
| 2026-04 | 37.4 | 88.6 | 131.9 | 166.4 | 197.5 | 2.8 | -28.3 | -40.5 | -71.6 |
| 2026-05 | 10.6 | 116.2 | 82.4 | 92.6 | 130.5 | 0.4 | -37.6 | 34.2 | -3.8 |
| 2026-06 | 25.0 | 127.2 | 89.9 | 110.3 | 181.6 | 4.6 | -66.7 | 41.9 | -29.3 |
| 2026-07 | 21.8 | 163.1 | 84.6 | 104.2 | 166.9 | 2.2 | -60.5 | 80.7 | 18.0 |
| 2026-08 | 6.5 | 109.3 | 68.2 | 74.1 | 141.0 | 0.6 | -66.3 | 41.7 | -25.2 |
| 2026-09 | 54.7 | 136.1 | 349.5 | 404.9 | 474.3 | -0.6 | -70.1 | -214.0 | -283.5 |
| 2026-10 | 7.4 | 43.2 | 93.6 | 88.1 | 102.5 | 12.9 | -1.5 | -37.5 | -51.9 |

October 2026 is a part month: the Clock runs to 9 Oct, NESO to 6 Oct, and Octopus to its last refresh.

## Named totals

| Period | Clock curtailment | Turn-up (a) | Turn-up (b) | Octopus curtailment + (b), Clock replication | Octopus published | NESO thermal |
|---|--:|--:|--:|--:|--:|--:|
| 2024 | 410.8 | 729.5 | 835.2 | 1,230.1 | not checked | 1,482.5 |
| **2025** | 397.4 | 811.1 | 1,083.6 | **1,466.8** | **1,467.0** (383.1 + 1,083.9) | 1,830.9 |
| **1 Jan – 5 Oct 2026** | 254.4 | 934.6 | 1,293.0 | **1,536.2** | **1,541.3** (243.2 + 1,298.1) | 2,018.0 |

Octopus's 2026 published total runs to its latest refresh, a day or so past 5 Oct, which accounts for the £5m difference.

## The gaps, explained

**1. Clock (b) against Octopus: within £5m every complete month; the 2025 total agrees to £0.2m.**
- **Definition (curtailment).** The Clock counts all accepted wind bids; Octopus counts only those flagged as system actions. Clock curtailment is therefore a few £m a month higher: £397.4m against £383.1m in 2025, and £410.8m against £394.9m in 2024. On the replication column, which uses Octopus's own definition, the gap all but disappears.
- **Revisions.** Elexon re-runs settlement for months afterwards, so Octopus's figure for a month may sit on an earlier run than ours. Turn-up gaps per month are a few hundred thousand pounds either way.
- **Timing.** October 2026 (+£12.9m) is a part month whose cut-off dates differ.

**2. Clock (b) against NESO thermal: NESO is higher in every month, by £364m (25%) in 2025 and £482m (31%) in 2026 to 5 Oct.**
- **Scope.** NESO's thermal category covers every action taken for any thermal constraint on the transmission network, not just wind behind a bottleneck. That includes other plant turned down and interconnector trades, on any boundary in Britain.
- **Volume.** NESO's thermal volume was 12,548 GWh in 2025 against 9,864 GWh of wind switched off.
- **Pricing.** NESO values each action at its own cost, and includes "the cost of replacing the energy" on its own basis (NESO, ENCC Transparency Roadmap). That is not the offer-stack walk used in (b).
- **What this means.** NESO thermal is an upper bound for a wind-only bill. That Octopus sits below it means Octopus's figure is not inflated relative to the system operator's own costing.

**3. Turn-up (a) against (b): (a) is no better a measure, and its gap swings with the season.**
- **Summer: (a) above (b).** In May–August, (a) exceeds (b) by up to £79m a month (July 2026: £163m against £85m). The system-action flag also covers voltage and inertia work, which peaks when demand is low. NESO's voltage cost tracks this: £41m in July 2026, against £3m in January 2026.
- **Winter: (a) far below (b).** January 2026 was £38m against £139m. Flagged non-wind offers cover less than half the energy actually lost: 4,255 GWh of flagged turn-up in wind half-hours against 9,864 GWh of wind switched off in 2025. NESO buys the rest through offers flagged as energy balancing, which only (b) prices.
- **Not a check on (b).** Restricting (a) to half-hours with wind switched off (£576m in 2025) gives a measured floor of money paid on constraint-flagged offers. It is not a like-for-like check on (b).
- **Who receives (a).** In 2025, wind half-hours only: gas (CCGT) £465m (81%), NESO trades £97m, biomass £11m.

## Verdict

Octopus's £1.5bn stands up. From Elexon's primary settlement data the Clock reproduces it: £1,536m for 1 Jan to 5 Oct 2026, against Octopus's £1,541m published to a slightly later date, and £1,466.8m for 2025 against Octopus's £1,467.0m. So 2026 has passed 2025's full-year total with three months to run. NESO's own thermal constraint cost for the same 2026 period is higher still, at £2,018m, so the figure is not inflated against the system operator's books. A hostile reader would attack the turn-up half: it is an estimate, pricing the lost wind energy against that half-hour's accepted offers, not a sum of payments to named plants. The money actually paid on constraint-flagged offers to non-wind plant in those half-hours is lower (£650m in 2026 to date), but it covers less than half the energy replaced, so it is a floor, not a contradiction. On Octopus's method, roughly three-quarters of the constraint bill goes to the plants switched on rather than the wind farms switched off: 74% in 2025, and 84% in 2026 to date as turn-up prices rose. Of the turn-up actually paid on flagged offers, about four-fifths goes to gas.

## Attribution options (for Richard to decide)

Run from the full backfill (Nov 2015 to 9 Oct 2026, 3,996 of 3,996 days), using `uv run python tools/turnup_attribution_options.py`. Turn-up is counted to 12 Sep 2026, the end of the BSUoS data, so that turn-up is never taken out of days the BSUoS line does not yet cover. 2024 prices.

| Option | What moves | Direct hero (real) | Headline `combined_real` |
|---|---|--:|--:|
| **A. Default (built)**: turn-up as its own line within indirect costs | BSUoS line −£5.39bn; new turn-up line +£5.39bn | £132.36bn (no change) | £240.18bn (no change) |
| **B.** Move turn-up (b) to direct, 100% | Direct +£5.39bn; indirect −£5.39bn | **£137.75bn** (+£5.39bn, +4.1%) | £240.18bn (no change) |
| **C.** Move only the measured floor to direct: flagged non-wind offers in wind half-hours | Direct +£3.78bn; the rest of (b), £1.61bn, stays indirect | **£136.14bn** (+£3.78bn, +2.9%) | £240.18bn (no change) |

- **The headline cannot move under any option.** Turn-up is carved out of the balancing uplift, which is already counted. In no year did measured turn-up exceed that uplift, so the cap never applied; the largest share was 2024, at £835m of £1,941m. Moving turn-up therefore shifts money between the direct and indirect layers; it never adds any.
- **What the direct hero claims.** Today it is described as payments to renewable generators. Options B and C would add payments that go to gas plants. These are caused by wind, but they are not paid to wind. Either option needs the hero's description changed, not just its number.
- **Wind share.** (b) is tied by construction to the wind volume switched off, so no further wind-share scaling is needed. NESO thermal costs include constraints that have nothing to do with wind, but (b) does not use them.
- **Run-rate.** Turn-up (b) is running at £1.42bn a year nominal. Under B, that moves from the indirect ticker to the direct ticker.

**Recommendation: A for now, B as the target.** B is defensible on causation: the money would not be paid if the wind had not been switched off, and the figure reproduces Octopus to the pound. It only becomes defensible once the hero's wording says "caused by" rather than "paid to"; until then, A keeps every public sentence true.

## How it was done

- **Engine.** `src/subsidy_engine_uk/schemes/constraint_turnup.py`, daily partitions under `data/raw/constraint_turnup/daily`. Backfilled from 1 Nov 2015, the first month for which Elexon publishes stack data, to 9 Oct 2026: 3,996 of 3,996 days, no gaps. Two days failed transiently in one run and were refetched.
- **Replication check.** Octopus's method was reproduced from its front-end code, read 10 Oct 2026. August 2026 replication: curtailment £5.957m against £5.958m, turn-up £68.16m against £68.11m.
- **Sources.** Elexon Insights `/balancing/settlement/stack/all/{bid,offer}/{date}/{period}`; Elexon BM unit register `/reference/bmunits/all`; NESO Constraint Breakdown Costs and Volume, CKAN `constraint-breakdown`, CSVs for 2023-24 to 2026-27; Octopus `wastedwind.energy/api/summary/{year}`.
