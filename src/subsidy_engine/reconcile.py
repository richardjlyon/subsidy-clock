"""Reconciliation of bottom-up totals against official aggregates (spec F-7).
Divergences are surfaced on the methodology page, never hidden."""

from __future__ import annotations

import polars as pl


def cfd_monthly(bottom_up_daily: pl.DataFrame, official_daily: pl.DataFrame,
                *, tolerance_pct: float = 5.0) -> dict:
    bu = (bottom_up_daily
          .group_by(pl.col("date").dt.strftime("%Y-%m").alias("month"))
          .agg(pl.col("cost_gbp").sum().alias("bottom_up_gbp")))
    of = (official_daily
          .group_by(pl.col("date").dt.strftime("%Y-%m").alias("month"))
          .agg(pl.col("payment_gbp").sum().alias("official_gbp")))
    joined = (bu.join(of, on="month", how="inner")
              .with_columns(
                  ((pl.col("bottom_up_gbp") - pl.col("official_gbp"))
                   / pl.col("official_gbp") * 100).alias("divergence_pct"))
              .sort("month"))
    months = [
        {"month": r["month"],
         "bottom_up_gbp": round(r["bottom_up_gbp"], 2),
         "official_gbp": round(r["official_gbp"], 2),
         "divergence_pct": round(r["divergence_pct"], 4)}
        for r in joined.to_dicts()
    ]
    max_abs = max((abs(m["divergence_pct"]) for m in months), default=0.0)
    return {
        "comparison": "Per-contract daily CfD payments (bottom-up) vs LCCC In-period Tracking daily totals",
        "months": months,
        "max_abs_divergence_pct": round(max_abs, 4),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": max_abs <= tolerance_pct,
    }
