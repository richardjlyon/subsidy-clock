"""The uplift baseline: the part of a system cost above its CPIH-indexed 2002-05 average,
the rule TNUoS and BSUoS are counted by (moved from build.py, aios-harness#38)."""
from __future__ import annotations

import polars as pl

from subsidy_engine.money import _latest_index

BASELINE_YEARS = (2002, 2005)  # inclusive 4-year calendar window (2002,2003,2004,2005) for uplift baselines


def baseline_uplift(
    raw_annual: pl.DataFrame,
    baseline_gbp: float,
    deflators: pl.DataFrame,
    *,
    subtract: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Conservative attribution: cost above the CPIH-indexed 2002-05 baseline,
    optionally net of costs already counted elsewhere, floored at zero."""
    lo, hi = BASELINE_YEARS
    base_idx = float(deflators.filter(
        pl.col("year").is_between(lo, hi))["index"].mean())
    latest = _latest_index(deflators)
    df = raw_annual.join(deflators, on="year", how="left").with_columns(
        (baseline_gbp * pl.col("index").fill_null(latest) / base_idx).alias("baseline"))
    if subtract is not None:
        df = (df.join(subtract.rename({"cost_gbp": "sub"}).select("year", "sub"),
                      on="year", how="left")
              .with_columns(pl.col("sub").fill_null(0.0)))
    else:
        df = df.with_columns(pl.lit(0.0).alias("sub"))
    return (df.with_columns(
                pl.max_horizontal(pl.lit(0.0),
                                  pl.col("cost_gbp") - pl.col("baseline") - pl.col("sub"))
                .alias("cost_gbp"))
            .select("year", "cost_gbp"))
