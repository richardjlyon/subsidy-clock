"""Reconciliation of bottom-up totals against official aggregates (spec F-7).
Divergences are surfaced on the methodology page, never hidden."""

from __future__ import annotations

import polars as pl


def cfd_monthly(bottom_up_daily: pl.DataFrame, official_daily: pl.DataFrame,
                *, tolerance_pct: float = 5.0,
                min_official_gbp: float = 1_000_000.0) -> dict:
    bu = (bottom_up_daily
          .group_by(pl.col("date").dt.strftime("%Y-%m").alias("month"))
          .agg(pl.col("cost_gbp").sum().alias("bottom_up_gbp")))
    of = (official_daily
          .group_by(pl.col("date").dt.strftime("%Y-%m").alias("month"))
          .agg(pl.col("payment_gbp").sum().alias("official_gbp")))
    joined = bu.join(of, on="month", how="inner").sort("month")
    months = []
    for r in joined.to_dicts():
        bu_val = r["bottom_up_gbp"]
        of_val = r["official_gbp"]
        abs_div = round(bu_val - of_val, 2)
        if abs(of_val) >= min_official_gbp:
            pct = round((bu_val - of_val) / of_val * 100, 4)
        else:
            pct = None
        months.append({
            "month": r["month"],
            "bottom_up_gbp": round(bu_val, 2),
            "official_gbp": round(of_val, 2),
            "divergence_pct": pct,
            "abs_divergence_gbp": abs_div,
        })
    comparable_pcts = [abs(m["divergence_pct"]) for m in months
                       if m["divergence_pct"] is not None]
    max_abs = max(comparable_pcts, default=0.0)
    return {
        "comparison": "Per-contract daily CfD payments (bottom-up) vs LCCC In-period Tracking daily totals",
        "months": months,
        "max_abs_divergence_pct": round(max_abs, 4),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": max_abs <= tolerance_pct,
        "bottom_up_only_months": sorted(set(bu["month"].to_list()) - set(of["month"].to_list())),
        "official_only_months": sorted(set(of["month"].to_list()) - set(bu["month"].to_list())),
    }
