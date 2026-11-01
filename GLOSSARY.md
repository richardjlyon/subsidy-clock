# The Subsidy Clock

What renewable electricity support costs Britain, in pounds, built from published data and reference histories.

## Language

### Sources and joining them

**Reference history**:
Curated annual cost figures for a scheme from published studies (REF, NAO), used for years the fetched data does not cover.
_Avoid_: REF data (REF is one source of it), history

**Bottom-up**:
Annual cost built from fetched daily or settlement data (Elexon, NESO, LCCC).
_Avoid_: live data, actuals

**Splice**:
The join of a scheme's reference history and its bottom-up series: which years each supplies.
_Avoid_: merge, blend

**Pin**:
The first year a scheme's bottom-up series replaces its reference history, stated in the reference files. Moving it is a release decision.
_Avoid_: first full year, cut-over, bottom_up_from (overloaded)

**Live pin**:
The pin that live (master) publishes. A pin may not put a year at or after the live pin back on the reference history.
_Avoid_: FIRST_FULL_ELEXON_YEAR, floor

**Held days**:
The days for which a scheme's bottom-up data is stored. Their first and last day are its **held window**.
_Avoid_: coverage, bottom_up_from / bottom_up_to

**Fully held**:
A year whose every day is a held day, up to the last held day or the end of the reference history, whichever is sooner.
_Avoid_: complete, full year
