"""VAT on households' share of the counted lines (Richard, 1 Nov 2026, ruling A; aios-harness#45).

As Reliable Britain's NZ11: 5% VAT on the domestic share of each year's cost. RB applies it to both bills and
counts the difference; the Clock counts only the extra, so the VAT here is 5% x domestic share x the extra the
Clock counts. The base is every line the headline counts (the renewables view's direct lines and the indirect
lines) except the Climate Change Levy, which households do not pay (RB leaves its NZ8 out of NZ11 too).
Domestic share: the engine's (run file, bills[y].netzero_on_household_bill_per_household.domestic_share, GB);
a year after the engine's last carries its last share.
"""
from __future__ import annotations

from datetime import date

import polars as pl

from subsidy_engine.money import SchemeResult

RATE = 0.05
NOT_IN_BASE = ("ccl",)   # households pay no Climate Change Levy


def base_lines(schemes: list[SchemeResult]) -> list[SchemeResult]:
    return [s for s in schemes if s.scheme_id not in NOT_IN_BASE
            and (s.layer == "indirect" or "renewables" in s.perspectives)]


def result(schemes: list[SchemeResult], share: dict | None) -> list[SchemeResult]:
    if not share:
        return []
    base = base_lines(schemes)
    years = sorted({int(y) for s in base for y in s.annual["year"].to_list()})
    last = max(share["years"])

    def sh(y: int) -> float:
        return share["years"].get(y, share["years"][last] if y > last else None)

    by_year: dict[int, float] = {}
    for s in base:
        for y, v in zip(s.annual["year"].to_list(), s.annual["cost_gbp"].to_list()):
            by_year[int(y)] = by_year.get(int(y), 0.0) + float(v)
    if any(sh(y) is None for y in years):
        raise ValueError(f"VAT: no domestic share for {[y for y in years if sh(y) is None]}")
    annual = pl.DataFrame({"year": years, "cost_gbp": [RATE * sh(y) * by_year[y] for y in years]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    runrate = RATE * sh(max(years)) * sum(s.runrate_gbp_per_year for s in base)
    data_to = max((s.data_to for s in base if s.data_to), default=date(max(years), 12, 31))
    return [SchemeResult(
        scheme_id="vat", label="VAT on households' share",
        perspectives=[], cadence="annual", layer="indirect",
        annual=annual, cumulative_gbp=float(annual["cost_gbp"].sum()),
        runrate_gbp_per_year=runrate, data_to=data_to,
        attribution_pct=1.0,
        attribution_note=(
            "5% VAT on households' share of the costs counted above (the Climate Change Levy apart, which "
            "households do not pay), as Reliable Britain counts it. Households' share is the engine's domestic "
            "share of electricity each year."),
        attribution_confidence="medium",
        extras={"base_lines": [s.scheme_id for s in base], "rate": RATE,
                "domestic_share": [{"year": y, "share": sh(y),
                                    "basis": "engine" if y <= last else f"carried forward from {last}"}
                                   for y in years],
                "source": f"gas-counterfactual engine {share['engine_version']}: {share['provenance']}",
                "source_url": None, "verified": False},
    )]
