"""Builds the JSON files the static dashboard consumes (spec D-1..D-12 and
phase-2 spec section 5). This module is the engine<->dashboard contract."""

from __future__ import annotations

import json
from datetime import datetime
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


# public CSV filename per scheme id - part of the published URL contract (/data/*.csv)
CSV_NAMES = {
    "cfd_renewable":   "cfd",
    "cfd_low_carbon":  "cfd-nuclear-biomass",
    "ro":              "renewables-obligation",
    "fit":             "feed-in-tariffs",
    "constraints":     "constraints",
    "capacity_market": "capacity-market",
    "ccl":             "climate-change-levy",
    "ets":             "emissions-trading",
    "tnuos":           "tnuos",
    "bsuos":           "bsuos",
}

RESTATEMENT_COLS = ["scheme", "table", "detected_at", "partition",
                    "previous_version", "new_version"]


def _attribution(generated: str) -> str:
    """Two comment lines at the top of every published CSV (share-UX rework).
    Dated from the same generated_at stamp as the JSON. Documented on the
    /data page: skip with pandas comment='#' or R comment.char='#'."""
    return ("# The Subsidy Clock — subsidyclock.co.uk\n"
            '# Licence: CC BY 4.0 (credit "The Subsidy Clock — '
            f'subsidyclock.co.uk") — generated {generated[:10]}\n')


def write_csvs(model: dict, out_dir: Path | str,
               *, restatements: list[dict], generated: str) -> None:
    """Per-scheme annual CSVs, one combined wide table, and the restatement
    log (distribution F4). Values are written from the same model that feeds
    the JSON, so CSVs can never disagree with the dashboard. Every file
    carries an in-file attribution header."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    header = _attribution(generated)

    def write(df: pl.DataFrame, name: str) -> None:
        # fixed 2 dp: measured pennies are kept intact, while estimated and
        # deflated values stop carrying spurious float-tail precision
        (out / name).write_text(header + df.write_csv(float_precision=2))

    combined = None
    for s in model["schemes"]:
        name = CSV_NAMES.get(s.scheme_id, s.scheme_id)
        df = s.annual.sort("year")
        write(df, f"{name}.csv")
        col = df.select(pl.col("year"),
                        pl.col("cost_gbp").alias(f"{s.scheme_id}_gbp"))
        combined = col if combined is None else combined.join(
            col, on="year", how="full", coalesce=True)
    if combined is not None:
        write(combined.sort("year"), "combined-annual.csv")

    rows = [{k: str(r.get(k, "")) for k in RESTATEMENT_COLS} for r in restatements]
    write(pl.DataFrame(rows, schema={k: pl.String for k in RESTATEMENT_COLS}),
          "restatements.csv")


WIDGET_TEMPLATE = Path(__file__).parent / "templates" / "widget.html"


def write_widget(totals: dict, out_path: Path | str) -> None:
    """Render the embeddable widget (distribution F5), stamping the latest
    figure so a JS-blocked iframe still shows a dated number."""
    r = totals["perspectives"]["renewables"]
    d = datetime.fromisoformat(totals["generated_at"])
    asof = f"{d.day} {d.strftime('%B %Y')}"
    html = (WIDGET_TEMPLATE.read_text()
            .replace("{{CUM}}", repr(r["cumulative_gbp"]))
            .replace("{{RATE}}", repr(r["rate_gbp_per_sec"]))
            .replace("{{GENERATED}}", totals["generated_at"])
            .replace("{{FIGURE}}", f"£{int(r['cumulative_gbp']):,}")
            .replace("{{ASOF}}", asof))
    if "{{" in html:
        raise ValueError("unfilled token in widget template")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
