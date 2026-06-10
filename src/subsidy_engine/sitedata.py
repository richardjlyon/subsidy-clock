"""Builds the JSON files the static dashboard consumes (spec D-1..D-12).
This module is the engine<->dashboard contract."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl


def _annual_records(annual: pl.DataFrame) -> list[dict]:
    return annual.select(
        pl.col("year").cast(pl.Int64), pl.col("cost_gbp").cast(pl.Float64)
    ).to_dicts()


def build(model: dict, ctx: dict, freshness: dict, out_dir: Path | str,
          *, generated_at: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    households = ctx["households"]["value"]
    population = ctx["population"]["value"]
    demand_mwh = ctx["annual_demand_twh"]["value"] * 1_000_000

    perspectives = {}
    for name, p in model["perspectives"].items():
        runrate = p["runrate_gbp_per_year"]
        perspectives[name] = {
            "cumulative_gbp": p["cumulative_gbp"],
            "runrate_gbp_per_year": runrate,
            "rate_gbp_per_sec": p["rate_gbp_per_sec"],
            "per_household_per_year_gbp": round(runrate / households, 2),
            "per_person_per_year_gbp": round(runrate / population, 2),
            "per_mwh_delivered_gbp": round(runrate / demand_mwh, 2),
            "since_year": p["since_year"],
        }

    (out / "totals.json").write_text(json.dumps({
        "generated_at": generated_at,
        "perspectives": perspectives,
    }, indent=1))

    (out / "timeseries.json").write_text(json.dumps({
        "generated_at": generated_at,
        "perspectives": {
            name: {"annual": _annual_records(p["annual"])}
            for name, p in model["perspectives"].items()
        },
        "schemes": {
            s.scheme_id: {"annual": _annual_records(s.annual)}
            for s in model["schemes"]
        },
    }, indent=1))

    (out / "breakdown.json").write_text(json.dumps({
        "generated_at": generated_at,
        "schemes": [
            {
                "id": s.scheme_id,
                "label": s.label,
                "perspectives": s.perspectives,
                "cadence": s.cadence,
                "cumulative_gbp": s.cumulative_gbp,
                "runrate_gbp_per_year": s.runrate_gbp_per_year,
                "data_to": s.data_to.isoformat() if s.data_to else None,
                **{k: v for k, v in s.extras.items()},
            }
            for s in model["schemes"]
        ],
    }, indent=1, default=str))

    (out / "meta.json").write_text(json.dumps({
        "generated_at": generated_at,
        "freshness": freshness,
        "context": ctx,
    }, indent=1))
