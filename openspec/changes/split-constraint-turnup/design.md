# split-constraint-turnup — design

## Context

See proposal.md for why. Today `build.py` computes BSUoS as
`max(0, raw − indexed_baseline − wind_constraints)` per year, with the same
formula on run-rates. Wind constraints come from `schemes/constraints.py`, which
reads Elexon's `/balancing/settlement/stack/all/bid/{date}/{period}` and counts
every accepted wind bid regardless of `soFlag` (REF's convention).

Octopus's Wasted Wind front end (bundle read 10 Oct 2026) reads the same Elexon
endpoints from the browser: curtailment = system-flagged wind bids; turn-up =
that volume priced by walking the period's offer stack (CADL offers excluded,
unflagged first, then by sequence number, pro-rata at the margin). Replicated
for August 2026 this gives £5.957m / £68.16m against Octopus's published
£5.958m / £68.11m.

## Goals / Non-Goals

Goals: one primary-data turn-up series; BSUoS net of it; parts that provably
sum to the raw total; a reconciliation that explains every gap.
Non-goals: see proposal. In particular the engine figure is not scaled to a
wind-caused share; that is an attribution choice for Richard.

## Decisions

1. **Engine figure = Octopus's replacement estimate (method b).** Richard's
   call, 10 Oct 2026, after the August test. Method (a), all system-flagged
   non-wind offers, came to £109.3m against (b)'s £68.2m, but £51.7m of (a) fell
   in half-hours with no wind switched off: it is voltage and other system
   work, not wind replacement. (b) is tied to the curtailed volume by
   construction and anyone can reproduce it. Its known weakness: 85% of the
   volume it prices comes from unflagged (energy-balancing) offers. Cross-check:
   flagged non-wind offers in wind-constrained half-hours (£57.6m in August)
   are stored daily as `accepted_offers_wind`, so the reconciliation tests the
   estimate every month.
2. **`soFlag` defines turn-up.** The flag marks actions taken for system
   (locational) reasons rather than energy balance. It is broader than thermal
   constraints: voltage and inertia actions are system-flagged too. That is
   why (a) cannot be the engine figure.
3. **Indirect layer, capped inside the uplift.** `turnup_line = min(turnup,
   uplift_after_wind)`, `bsuos = uplift_after_wind − turnup_line`. The cap makes
   the indirect total identical by construction, including in floored years.
   Run-rates use the same rule.
4. **One store row per (day, basis, fuel)**, not per unit: the per-unit detail is
   only needed if turn-up becomes a direct line with recipients; YAGNI. Bases:
   `replacement_estimate`, `accepted_offers`, `accepted_offers_wind`, `wind_bids_so`.
5. **Fetch both stacks per period concurrently** (thread pool; retries with
   exponential backoff, because Elexon throttles bursts; a day that still fails
   is reported and left unwritten, so a rerun picks it up and the series is
   never silently short). The
   existing constraints fetch is sequential; at 100 calls a day that would make
   an eleven-year backfill take many hours. Concurrency keeps it to minutes.
6. **Fuel map from Elexon's current BM unit register** (`/reference/bmunits/all`),
   as `constraints.py` does. Units missing from the register fall in
   `UNMAPPED`; stack rows without an id fall in `NO_ID`.
7. **Partitions per day under `constraint_turnup/daily`**, like constraints, so
   `skip_existing` backfill and the 3-day refresh work the same way.

## Risks / Trade-offs

- [`soFlag` includes non-thermal system actions] → reconciliation against NESO's
  thermal/voltage/inertia split quantifies it; attribution options use it.
- [Historic register gaps: retired units may be missing a fuel type] → kept as
  unclassified/unmapped and reported, never dropped.
- [Data merge: the bot owns `data/`; the pre-commit hook blocks it] → backfilled
  partitions are committed on the branch in their own commit with the
  documented bypass, so they can be dropped or kept at merge.
- [Site does not know the new id] → merge blocker, stated in proposal and tasks.

## Migration Plan

Branch only, unpushed. On approval: Richard picks an attribution option; site
wiring lands in the same push as this engine change; golden master re-baselined
with the diff confined to the BSUoS/turn-up outputs. Rollback = revert the merge.
