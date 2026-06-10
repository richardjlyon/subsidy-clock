"""Reconciliation of bottom-up totals against official aggregates (spec F-7).
Divergences are surfaced on the methodology page, never hidden.

The two LCCC series are compared like-for-like: only settlement dates present
in BOTH series are summed (the In-period Tracking snapshot publishes partial
months), and dates within `settlement_lag_days` of the tracking series' last
date are excluded because the per-contract generation ledger reconciles more
slowly than the daily tracking totals."""

from __future__ import annotations

from datetime import timedelta

import polars as pl


def _months(df: pl.DataFrame) -> set[str]:
    return set(df.select(pl.col("date").dt.strftime("%Y-%m")).to_series().to_list())


def cfd_monthly(
    bottom_up_daily: pl.DataFrame,
    official_daily: pl.DataFrame,
    *,
    tolerance_pct: float = 2.0,
    min_official_gbp: float = 1_000_000.0,
    settlement_lag_days: int = 45,
) -> dict:
    bu = bottom_up_daily.select("date", pl.col("cost_gbp").alias("bu"))
    of = official_daily.select("date", pl.col("payment_gbp").alias("of"))
    matched = bu.join(of, on="date", how="inner").sort("date")
    if matched.height:
        cutoff = of["date"].max() - timedelta(days=settlement_lag_days)
        included = matched.filter(pl.col("date") <= cutoff)
    else:
        included = matched
    excluded_recent_days = matched.height - included.height

    overall_bu = float(included["bu"].sum()) if included.height else 0.0
    overall_of = float(included["of"].sum()) if included.height else 0.0
    overall_pct = (
        round((overall_bu - overall_of) / overall_of * 100, 4)
        if abs(overall_of) >= min_official_gbp else None
    )

    months = []
    if included.height:
        monthly = (
            included.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("month"))
            .group_by("month")
            .agg(pl.col("bu").sum(), pl.col("of").sum(), pl.len().alias("days_compared"))
            .sort("month")
        )
        for r in monthly.to_dicts():
            pct = (round((r["bu"] - r["of"]) / r["of"] * 100, 4)
                   if abs(r["of"]) >= min_official_gbp else None)
            months.append({
                "month": r["month"],
                "days_compared": r["days_compared"],
                "bottom_up_gbp": round(r["bu"], 2),
                "official_gbp": round(r["of"], 2),
                "abs_divergence_gbp": round(r["bu"] - r["of"], 2),
                "divergence_pct": pct,
            })

    return {
        "comparison": (
            "Per-contract daily CfD payments (bottom-up) vs LCCC In-period "
            "Tracking daily totals, summed over settlement dates present in "
            "both series"
        ),
        "matched_days": included.height,
        "excluded_recent_days": excluded_recent_days,
        "settlement_lag_days": settlement_lag_days,
        "overall": {
            "bottom_up_gbp": round(overall_bu, 2),
            "official_gbp": round(overall_of, 2),
            "divergence_pct": overall_pct,
        },
        "months": months,
        "bottom_up_only_months": sorted(_months(bu) - _months(of)),
        "official_only_months": sorted(_months(of) - _months(bu)),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": overall_pct is None or abs(overall_pct) <= tolerance_pct,
    }


def indirect_crosscheck(ours: dict[str, float], ref: dict,
                        *, bound_pct: float = 25.0) -> dict:
    """Compare our indirect components against REF's published Table 2 figures.
    Divergence is expected (methods differ by design); beyond the bound it must
    carry an explanation note, which the methodology page displays."""
    components = []
    unexplained = 0
    for name, ref_value in ref["components"].items():
        our_value = float(ours.get(name, 0.0))
        pct = (round((our_value - ref_value) / ref_value * 100, 4)
               if ref_value else None)
        note = (ref.get("notes") or {}).get(name, "")
        beyond = (pct is not None and abs(pct) > bound_pct) or (
            pct is None and our_value != 0.0)
        explained = bool(note) if beyond else True
        if not explained:
            unexplained += 1
        components.append({
            "component": name,
            "ours_gbp": round(our_value, 2),
            "ref_gbp": float(ref_value),
            "divergence_pct": pct,
            "note": note,
            "explained": explained,
        })
    return {
        "comparison_year": ref["year"],
        "ref_source": ref["source"],
        "ref_source_url": ref["source_url"],
        "bound_pct": bound_pct,
        "components": components,
        "unexplained_count": unexplained,
    }
