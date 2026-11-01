"""Carbon in the electricity price (aios-harness#44; Richard, 1 Nov 2026: 0022 for the Clock, as Reliable
Britain counts it). One line: each year's carbon in the GB wholesale price (the engine's NZ1c), with its two
parts, the tax collected by the Treasury (Carbon Price Support plus UK ETS auction receipts on power) and the
rest of the carbon in the price. It replaces the old emissions-trading line and the Carbon Price Support that
sat inside the CCL line; it is never counted next to them. Read from the pinned engine release
(subsidy_engine_uk.register.carbon_from_engine)."""
from __future__ import annotations

from datetime import date

import polars as pl

from subsidy_engine.money import SchemeResult

DATA_NOTE = (
    "2005-2012: generators were given most of their emission allowances free and paid little for them, but "
    "the carbon price still set the price of power, so the cost still reached bills. Those years count, as in "
    "Reliable Britain.")


def result(carbon: dict | None) -> list[SchemeResult]:
    if not carbon:
        return []
    years = sorted(carbon["years"])
    rows = carbon["years"]
    annual = pl.DataFrame({"year": years, "cost_gbp": [rows[y]["total"] for y in years]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    last = years[-1]
    return [SchemeResult(
        scheme_id="carbon", label="Carbon in the electricity price",
        perspectives=[], cadence="annual", layer="indirect",
        annual=annual,
        cumulative_gbp=float(annual["cost_gbp"].sum()),
        runrate_gbp_per_year=float(rows[last]["total"]),
        data_to=date(last, 12, 31),
        attribution_pct=1.0,
        attribution_note=(
            "The whole carbon effect on the electricity price: each year's carbon cost in the wholesale price "
            "of power in Great Britain, as the gas-counterfactual engine models it. Part of it is tax collected "
            "by the Treasury (Carbon Price Support and the power sector's share of UK emissions-trading auction "
            "receipts); the rest is carbon in the price that no one collected as tax."),
        attribution_confidence="medium",
        extras={
            "parts": [{"year": y, "tax_collected": rows[y]["tax_collected"],
                       "rest_of_carbon_in_price": rows[y]["total"] - rows[y]["tax_collected"],
                       "basis": rows[y]["basis"]} for y in years],
            "part_labels": {"tax_collected": "tax collected by the Treasury",
                            "rest_of_carbon_in_price": "the rest of the carbon in the price"},
            "geography": "GB",
            "data_note": DATA_NOTE,
            "source": f"gas-counterfactual engine {carbon['engine_version']}: {carbon['provenance']}",
            "source_url": None,
            "verified": False,
        },
    )]
