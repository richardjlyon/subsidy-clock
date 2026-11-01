"""The road: what TNUoS and BSUoS count is each year's cost above what the same year would have cost on the
no-net-zero road (Richard's ruling C, 1 Nov 2026, re-confirming A1/A2 of 14 Oct; aios-harness#43).

The road is the pinned engine release's GO5 (high-voltage grid) and GO4 (balancing) per calendar year,
generators' share included (subsidy_engine_uk.register.road_from_engine). A year after the engine's last year
carries that year by CPIH, the rule the export states. Replaced the flat 2002-05 baselines (TNUoS GBP 0.9bn,
BSUoS GBP 0.4bn a year, CPIH-indexed), which came from REF.
"""
from __future__ import annotations

import polars as pl

from subsidy_engine.money import _latest_index


def road_series(years: list[int], road: dict, deflators: pl.DataFrame) -> pl.DataFrame:
    """(year, road) in GBP nominal for each year: the engine's own figure, or for a year after its last
    year that figure carried by CPIH (index(y)/index(last), the latest index for a year with none). A year
    before the engine's first year is an error."""
    series, last = road["years"], road["carry_forward_from"]
    idx = dict(zip(deflators["year"].to_list(), deflators["index"].to_list()))
    latest = _latest_index(deflators)
    out = []
    for y in years:
        if y in series:
            out.append(float(series[y]))
        elif y > last:
            out.append(float(series[last]) * idx.get(y, latest) / idx[last])
        else:
            raise ValueError(f"no engine no-net-zero cost for {y} (engine starts {min(series)})")
    return pl.DataFrame({"year": years, "road": out}, schema={"year": pl.Int64, "road": pl.Float64})


def road_runrate(road: dict, deflators: pl.DataFrame) -> float:
    """The road at today's prices: the engine's last-year figure carried by CPIH to the latest index."""
    last = road["carry_forward_from"]
    idx = dict(zip(deflators["year"].to_list(), deflators["index"].to_list()))
    return float(road["years"][last]) * _latest_index(deflators) / idx[last]


def road_uplift(
    raw_annual: pl.DataFrame,
    road: dict,
    deflators: pl.DataFrame,
    *,
    subtract: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Each year's cost above the road, optionally net of costs already counted elsewhere. SIGNED: a year
    below the road counts as negative, as Reliable Britain does (Richard, 1 Nov 2026; until then each year
    was floored at zero)."""
    df = raw_annual.join(road_series([int(y) for y in raw_annual["year"].to_list()], road, deflators),
                         on="year", how="left")
    if subtract is not None:
        df = (df.join(subtract.rename({"cost_gbp": "sub"}).select("year", "sub"),
                      on="year", how="left")
              .with_columns(pl.col("sub").fill_null(0.0)))
    else:
        df = df.with_columns(pl.lit(0.0).alias("sub"))
    return (df.with_columns(
                (pl.col("cost_gbp") - pl.col("road") - pl.col("sub")).alias("cost_gbp"))
            .select("year", "cost_gbp"))


def road_extras(years: list[int], road: dict, deflators: pl.DataFrame) -> dict:
    """What breakdown.json publishes beside the line: the road subtracted each year, and its source."""
    ser = road_series(years, road, deflators)
    last = road["carry_forward_from"]
    return {"road_annual": [
                {"year": y, "cost": v,
                 "basis": "modelled" if y <= last else f"carried forward from {last} by CPIH"}
                for y, v in zip(ser["year"].to_list(), ser["road"].to_list())],
            "road_source": (f"gas-counterfactual engine {road['engine_version']}, {road['what']}; "
                            "generators' share included")}
