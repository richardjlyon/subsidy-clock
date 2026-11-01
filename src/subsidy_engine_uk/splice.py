"""The splice: which years a scheme's bottom-up series replaces its reference history for.

Owns the pin (the reference file's ``bottom_up_from``), the live pin, and the fix 5
guard (17 Oct 2026) that refuses an unsafe pin. Constraints and BSUoS both go through
it (aios-harness#37). Terms as in GLOSSARY.md.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

import polars as pl

from subsidy_engine.money import annualise_daily, merge_annual
from subsidy_engine.reference import ReferenceScheme

# The pin live (master) publishes for each scheme. No pin may put a year at or after it
# back on the reference history. Moving a pin is a release decision for Richard, not a
# data update: the live pin moves with it in the same release (a test ties each to its
# reference file), so raising a pin is a two-place edit on purpose.
LIVE_PIN = {"constraints": 2024, "bsuos": 2017}

# How each scheme's errors name its sources, settings file and the fetch that fills a gap
_WORDS = {
    "constraints": {"bu": "Elexon", "ref": "REF", "file": "reference/annual_scheme_costs.yaml",
                    "fetch": "backfill-constraints --start --end"},
    "bsuos": {"bu": "NESO", "ref": "the history", "file": "reference/indirect_annual.yaml",
              "fetch": "update"},
}


def splice(scheme: str, history: ReferenceScheme, daily: pl.DataFrame,
           held: Iterable[str]) -> tuple[pl.DataFrame, str, str]:
    """Join ``history`` (carrying the pin) with ``daily`` (date, cost_gbp; not empty).
    ``held`` is the scheme's held days (ISO); it can include days with no rows in
    ``daily``, e.g. a constraints day Elexon answered with no wind bids (£0). Returns the
    spliced annual series and the first and last day in ``daily`` (ISO). Raises
    ValueError, naming the setting, for an unsafe pin.

    Years from the pin come from bottom-up, as do part years after the history's last
    year (nothing to replace); every other year stays on the history."""
    w = _WORDS[scheme]
    pin = history.bottom_up_from
    if pin is None:
        raise ValueError(f"{scheme} history states no bottom_up_from: the first year "
                         f"{w['bu']} replaces {w['ref']} must be stated in {w['file']}")
    last_history_year = int(history.annual["year"].max())
    _check(scheme, pin, {d for d in held if len(d) == 10}, last_history_year)
    usable = annualise_daily(daily).filter(
        (pl.col("year") >= pin) | (pl.col("year") > last_history_year))
    return (merge_annual(history.annual, usable),
            daily["date"].min().isoformat(), daily["date"].max().isoformat())


def _check(scheme: str, value, held: set[str], last_history_year: int) -> None:
    """The pin must be a whole-number year, and every year from it that replaces a
    history figure must be fully held: every day from 1 January of the pin to the last
    held day, or to 31 December of the history's last year if that is sooner. An earlier
    year being fully held as well is fine: the pin is a decision, not the earliest full
    year."""
    w, live = _WORDS[scheme], LIVE_PIN[scheme]
    name = f"{scheme} bottom_up_from"
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} {value!r} is not a whole-number year: write it as a plain "
                         f"year, e.g. {live}, in {w['file']}")
    if value < 1:
        raise ValueError(f"{name} {value} is not a calendar year: write the first year "
                         f"{w['bu']} replaces {w['ref']}, e.g. {live}, in {w['file']}")
    for y in range(live, min(value, last_history_year + 1)):
        days = (date(y + 1, 1, 1) - date(y, 1, 1)).days
        if all((date(y, 1, 1) + timedelta(days=n)).isoformat() in held for n in range(days)):
            raise ValueError(f"{name} {value} is later than {y}, a year {w['bu']} fully "
                             f"holds and live (master) publishes from {w['bu']}: it would "
                             f"put {y} back on {w['ref']}")
    if value > live:
        # any held day from 1 Jan of the live pin up to the pin year: a raised pin would
        # put those days back on the history, even with a day missing (fact-checker, 9410d658)
        early = sorted(d for d in held if live <= int(d[:4]) < value)
        if early:
            raise ValueError(f"{name} {value} is later than {live} while {w['bu']} holds "
                             f"days from 1 Jan {live} ({len(early)} stored, first "
                             f"{early[0]}): it would put them back on {w['ref']}. Keep the "
                             f"pin at {live} and fetch any missing days")
    first = date(value, 1, 1)
    last = date.fromisoformat(max(held)) if held else None
    if last is None or last < first:
        raise ValueError(f"{name} {value} is not usable: not every day from 1 Jan {value} "
                         f"is stored (no stored day on or after it)")
    end = min(last, date(last_history_year, 12, 31))
    lacking = [d for d in (first + timedelta(days=n) for n in range((end - first).days + 1))
               if d.isoformat() not in held]
    if lacking:
        raise ValueError(f"{name} {value} is not usable: not every day from 1 Jan {value} "
                         f"to {end} is stored ({len(lacking)} lacking, first {lacking[0]}). "
                         f"{w['bu']} would replace {w['ref']} with a partial year: fetch the "
                         f"missing days ({w['fetch']}) and do not raise the pin")
