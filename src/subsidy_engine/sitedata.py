"""Builds the JSON files the static dashboard consumes (spec D-1..D-12 and
phase-2 spec section 5). This module is the engine<->dashboard contract."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl


def _annual_records(annual: pl.DataFrame) -> list[dict]:
    cols = [pl.col("year").cast(pl.Int64), pl.col("cost_gbp").cast(pl.Float64)]
    if "cost_gbp_2024" in annual.columns:
        cols.append(pl.col("cost_gbp_2024").cast(pl.Float64))
    return annual.select(cols).to_dicts()


def _money_block(p: dict, households: int, population: int, demand_mwh: float) -> dict:
    runrate = p["runrate_gbp_per_year"]
    block = {
        "cumulative_gbp": p["cumulative_gbp"],
        "runrate_gbp_per_year": runrate,
        "rate_gbp_per_sec": p["rate_gbp_per_sec"],
        "per_household_per_year_gbp": round(runrate / households, 2),
        "per_person_per_year_gbp": round(runrate / population, 2),
        "per_mwh_delivered_gbp": round(runrate / demand_mwh, 2),
        "since_year": p["since_year"],
    }
    if "cumulative_gbp_2024" in p:
        real_run = p["runrate_gbp_per_year_2024"]
        block["real_2024"] = {
            "cumulative_gbp": p["cumulative_gbp_2024"],
            "runrate_gbp_per_year": real_run,
            "rate_gbp_per_sec": p["rate_gbp_per_sec_2024"],
            "per_household_per_year_gbp": round(real_run / households, 2),
            "per_person_per_year_gbp": round(real_run / population, 2),
            "per_mwh_delivered_gbp": round(real_run / demand_mwh, 2),
        }
    return block


def build(model: dict, ctx: dict, freshness: dict, out_dir: Path | str,
          *, generated_at: str, deflator_info: dict | None = None,
          bill_annual: pl.DataFrame | None = None,
          bill_info: dict | None = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    households = ctx["households"]["value"]
    population = ctx["population"]["value"]
    demand_mwh = ctx["annual_demand_twh"]["value"] * 1_000_000

    totals: dict = {
        "generated_at": generated_at,
        "perspectives": {
            name: _money_block(p, households, population, demand_mwh)
            for name, p in model["perspectives"].items()
        },
    }
    if "indirect" in model:
        totals["indirect"] = _money_block(
            model["indirect"], households, population, demand_mwh)
    (out / "totals.json").write_text(json.dumps(totals, indent=1, allow_nan=False))

    ts: dict = {
        "generated_at": generated_at,
        "perspectives": {
            name: {"annual": _annual_records(p["annual"])}
            for name, p in model["perspectives"].items()
        },
        "indirect": ({"annual": _annual_records(model["indirect"]["annual"])}
                     if "indirect" in model else None),
        "schemes": {
            s.scheme_id: {"annual": _annual_records(s.annual)}
            for s in model["schemes"]
        },
    }
    if bill_annual is not None:
        ts["electricity_bill"] = {"annual": bill_annual.select(
            pl.col("year").cast(pl.Int64),
            pl.col("total_bill_gbp").cast(pl.Float64),
            pl.col("total_bill_gbp_2024").cast(pl.Float64),
        ).to_dicts()}
    (out / "timeseries.json").write_text(json.dumps(ts, indent=1, allow_nan=False))

    (out / "breakdown.json").write_text(json.dumps({
        "generated_at": generated_at,
        "schemes": [
            {
                "id": s.scheme_id,
                "label": s.label,
                "perspectives": s.perspectives,
                "cadence": s.cadence,
                "layer": s.layer,
                "attribution_pct": s.attribution_pct,
                "attribution_note": s.attribution_note,
                "attribution_confidence": s.attribution_confidence,
                "cumulative_gbp": s.cumulative_gbp,
                "runrate_gbp_per_year": s.runrate_gbp_per_year,
                "data_to": s.data_to.isoformat() if s.data_to else None,
                **{k: v for k, v in s.extras.items()},
            }
            for s in model["schemes"]
        ],
    }, indent=1, default=str, allow_nan=False))

    (out / "meta.json").write_text(json.dumps({
        "generated_at": generated_at,
        "freshness": freshness,
        "context": ctx,
        "deflator": deflator_info,
        "bill": bill_info,
    }, indent=1, allow_nan=False))
