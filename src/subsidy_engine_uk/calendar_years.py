"""Fixed-period totals on calendar years (definitions D-13; aios-harness#42).

Any 2002-24 (or other fixed-period) total is on calendar years. RO and FiT are published by obligation (scheme)
year, April to March, keyed by start year; for such a total they are calendarised as the gas-counterfactual engine
does (spec section 2, gascf.subsidies.fy_to_cy): CY(y) = 0.25 x FY(y-1) + 0.75 x FY(y). Each calendar year is
then deflated at its own index. Every other line is already on calendar years and is taken as it is.

The live site shows running totals only, which keep each line's own year keys: nothing here changes them. This
is the cut later Report No. 2 figures are made from (tools/period_totals.py).
"""
from __future__ import annotations

import polars as pl

from subsidy_engine.money import add_real

# Lines whose year key is an April-March obligation (scheme) year: RO and FiT (D-13)
OBLIGATION_YEAR_LINES = ("ro", "fit")


def fy_to_cy(fy: dict[int, float], years) -> dict[int, float]:
    """Time-weight financial years (keyed by start year: 2002 = 2002-03) to calendar years, the engine's rule.
    A missing year counts as zero only before the scheme's first year; otherwise it raises."""
    first = min(fy)
    out = {}
    for y in years:
        a = fy.get(y - 1, 0.0 if y - 1 < first else None)
        b = fy.get(y, 0.0 if y < first else None)
        if a is None or b is None:
            raise ValueError(f"financial year missing for calendar year {y}")
        out[y] = 0.25 * a + 0.75 * b
    return out


def calendar_annual(scheme_id: str, annual: pl.DataFrame, first: int, last: int) -> tuple[pl.DataFrame, str]:
    """The line's calendar years first..last (year, cost_gbp) and the basis it is on."""
    if scheme_id in OBLIGATION_YEAR_LINES:
        fy = dict(zip(annual["year"].to_list(), annual["cost_gbp"].to_list()))
        cy = fy_to_cy(fy, range(max(first, min(fy)), last + 1))
        return (pl.DataFrame({"year": list(cy), "cost_gbp": list(cy.values())},
                             schema={"year": pl.Int64, "cost_gbp": pl.Float64}),
                "calendarised from obligation years")
    return (annual.select("year", "cost_gbp").filter(pl.col("year").is_between(first, last)), "calendar")


def period_totals(model: dict, first: int, last: int, *, deflators: pl.DataFrame) -> dict:
    """Cash and real (2024 prices, each calendar year at its own index) totals for calendar years first..last:
    per line, per direct perspective, and the indirect layer."""
    schemes = {}
    for s in model["schemes"]:
        cy, basis = calendar_annual(s.scheme_id, s.annual, first, last)
        real = add_real(cy, deflators)
        schemes[s.scheme_id] = {"cash": float(cy["cost_gbp"].sum()),
                                "real": float(real["cost_gbp_2024"].sum()), "basis": basis}
    by = {s.scheme_id: s for s in model["schemes"]}

    def block(ids):
        return {"cash": sum(schemes[k]["cash"] for k in ids), "real": sum(schemes[k]["real"] for k in ids)}

    out = {"first": first, "last": last, "schemes": schemes}
    for p in model["perspectives"]:
        out[p] = block([k for k, s in by.items() if s.layer == "direct" and p in s.perspectives])
    out["indirect"] = block([k for k, s in by.items() if s.layer == "indirect"])
    return out
