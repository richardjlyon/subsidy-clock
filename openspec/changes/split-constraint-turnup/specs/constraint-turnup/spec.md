## Purpose

Measure what NESO pays plant to switch ON to replace constrained power, as its own
daily series from primary data, so that the constraint bill can be split between
the plants switched off and the plants switched on without counting anything twice.

## ADDED Requirements

### Requirement: Turn-up is estimated daily by Octopus's replacement method
The engine SHALL store, per day, a replacement estimate: for each period, the
volume of system-flagged wind bids priced by walking that period's accepted offers
(excluding short-duration CADL-flagged offers), unflagged offers first, then in
acceptance sequence, taking a pro-rata share of the offer that crosses the volume.
This is the engine's turn-up figure. It SHALL also store the cost and volume of
system-flagged wind bids.

#### Scenario: Partial offer at the margin
- **WHEN** 15 MWh of wind is switched off and the walk reaches a 10 MWh offer at
  £80 then a 10 MWh offer at £100
- **THEN** the estimate is 10 x 80 + 5 x 100 = £1,300 for 15 MWh

### Requirement: Accepted offers are stored as a cross-check
The engine SHALL store, per day, the cost and volume of accepted offers (positive
volume) flagged as system actions (`soFlag` true) from every BM unit whose
registered fuel type is not WIND, grouped by fuel type, both across all periods
and restricted to periods in which wind was switched off. Cost SHALL be volume x
original offer price. Units with no fuel type, units missing from the register,
rows with no id and NESO trades SHALL each be labelled, never dropped. These
SHALL NOT enter any published total.

#### Scenario: Gas offer counted, wind and energy offers excluded
- **WHEN** a period's offer stack holds a system-flagged CCGT offer, a
  system-flagged wind offer and an unflagged CCGT offer
- **THEN** only the system-flagged CCGT offer is counted, under fuel CCGT

#### Scenario: Wind-constrained periods only
- **WHEN** the same CCGT offer is accepted in a period with wind switched off
  and in one without
- **THEN** both count in the all-periods figure and only the first in the
  wind-constrained figure

### Requirement: Turn-up is netted out of BSUoS without double counting
The build SHALL publish turn-up (replacement-estimate basis) as its own indirect-layer
scheme and SHALL reduce the BSUoS scheme by the same amount, so that for every
year BSUoS residual + turn-up line + wind constraint payments + indexed baseline
equals raw BSUoS whenever no zero-floor binds. Where the BSUoS uplift is smaller
than measured turn-up, the turn-up line SHALL be capped at the uplift so the
indirect total never rises. The indirect total, the direct total and the combined
headline SHALL be unchanged by this change.

#### Scenario: Parts sum to raw
- **WHEN** raw BSUoS is 1,000, the indexed baseline 190, wind constraint payments
  100 and turn-up 300 in a year
- **THEN** the turn-up line is 300, BSUoS residual is 410, and
  410 + 300 + 100 + 190 = 1,000

#### Scenario: Headline unchanged
- **WHEN** the site build runs with and without turn-up data in the store
- **THEN** the indirect total and combined real total are equal in both runs

### Requirement: Backfill and daily update
The engine SHALL provide a backfill command over a date range and include
turn-up in `update all`, refetching the last few days as settlement firms up. A
day with no published stack data SHALL be stored as empty, not as failure.

#### Scenario: Transient failure does not leave a hole
- **WHEN** one day's fetch fails after all retries during a backfill
- **THEN** the backfill continues, reports that day, writes no partition for it,
  and exits non-zero

#### Scenario: Update all includes turn-up
- **WHEN** `update all` runs
- **THEN** turn-up is refreshed, and a turn-up failure does not block other schemes

### Requirement: Reconciliation against Octopus and NESO
A tool SHALL produce a monthly table from 2024 to date with Clock curtailment,
turn-up (accepted offers), turn-up (replacement estimate), Octopus Wasted Wind
total and NESO thermal constraint cost, and the gap of each against Octopus and
NESO, reading Octopus and NESO figures from their live publications.

#### Scenario: Monthly table produced
- **WHEN** the tool runs with turn-up data in the store
- **THEN** it prints one row per month from January 2024 with all five columns
  and the named annual totals for 2025 and 1 Jan to 5 Oct 2026
