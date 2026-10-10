"""Constraint bill reconciliation: Clock vs Octopus Wasted Wind vs NESO.

Monthly, January 2024 to date (spec: constraint-turnup, reconciliation).

  Clock curtailment   constraints scheme (all accepted wind bids, any flag)
  Turn-up (a)         system-flagged accepted offers, non-wind units (all periods)
  Turn-up (a, wind)   the same, only periods in which wind was switched off
  Turn-up (b)         Octopus method: curtailed wind volume priced on the
                      period's offer stack (the Clock's published line)
  Octopus curtail     system-flagged wind bids, Clock replication of Octopus
  Octopus             Wasted Wind published monthly totals (live API)
  NESO thermal        NESO Constraint Breakdown, thermal constraints cost

Octopus and NESO are read live; Clock figures come from the local store.

    uv run python tools/constraint_reconciliation.py [--csv out.csv]
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date
from pathlib import Path

import httpx
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from subsidy_engine.store import SnapshotStore  # noqa: E402
from subsidy_engine_uk.schemes import constraint_turnup as tu  # noqa: E402

OCTOPUS = "https://wastedwind.energy/api/summary/{year}"
NESO_PACKAGE = "https://api.neso.energy/api/3/action/package_show?id=constraint-breakdown"
START = date(2024, 1, 1)
UA = {"User-Agent": "subsidyclock.co.uk reconciliation"}


def octopus(client: httpx.Client, years: list[int]) -> pl.DataFrame:
    rows = []
    for y in years:
        for r in client.get(OCTOPUS.format(year=y), headers=UA).raise_for_status().json()["data"]:
            rows.append({"month": f"{y}-{int(r['month']):02d}",
                         "oct_curtail": float(r["bidCost"]),
                         "oct_turnup": float(r["turnUpCost"])})
    return pl.DataFrame(rows).with_columns(
        (pl.col("oct_curtail") + pl.col("oct_turnup")).alias("octopus"))


def neso_thermal(client: httpx.Client) -> pl.DataFrame:
    pkg = client.get(NESO_PACKAGE, headers=UA).raise_for_status().json()["result"]
    frames = []
    for res in pkg["resources"]:
        if (res.get("format") or "").upper() != "CSV":
            continue
        text = client.get(res["url"], headers=UA, follow_redirects=True).raise_for_status().text
        rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
        if not rows or "Thermal constraints cost" not in rows[0]:
            continue
        frames.append(pl.DataFrame({
            "date": [r["Date"][:10] for r in rows],
            "neso_thermal": [float(r["Thermal constraints cost"] or 0) for r in rows],
            "neso_voltage": [float(r.get("Voltage constraints cost") or 0) for r in rows],
        }))
    df = pl.concat(frames).unique("date", keep="last")
    return (df.with_columns(pl.col("date").str.slice(0, 7).alias("month"))
              .group_by("month").agg(pl.col("neso_thermal").sum(),
                                     pl.col("neso_voltage").sum(),
                                     pl.col("date").max().alias("neso_to")))


def clock(store: SnapshotStore) -> pl.DataFrame:
    con = store.read_all_partitions("constraints", "daily")
    cur = (con.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("month"))
              .group_by("month").agg(pl.col("cost_gbp").sum().alias("clock_curtail")))
    t = tu.read(store)
    t = t.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("month"))
    piv = (t.group_by("month", "basis").agg(pl.col("cost_gbp").sum())
             .pivot(on="basis", index="month", values="cost_gbp"))
    days = t.group_by("month").agg(pl.col("date").n_unique().alias("tu_days"))
    out = piv.rename({tu.ACCEPTED: "tu_a", tu.ACCEPTED_WIND: "tu_a_wind",
                      tu.ESTIMATE: "tu_b", tu.WIND_SO: "clock_oct_curtail"})
    out = out.with_columns(pl.col("clock_oct_curtail").abs())
    return cur.join(out, on="month", how="full", coalesce=True).join(
        days, on="month", how="left")


def table(store: SnapshotStore, client: httpx.Client) -> pl.DataFrame:
    today = date.today()
    oc = octopus(client, list(range(START.year, today.year + 1)))
    ne = neso_thermal(client)
    cl = clock(store)
    df = (cl.join(oc, on="month", how="full", coalesce=True)
            .join(ne, on="month", how="full", coalesce=True)
            .filter(pl.col("month") >= START.strftime("%Y-%m"))
            .sort("month").fill_null(0.0))
    return df.with_columns(
        (pl.col("clock_curtail") + pl.col("tu_a")).alias("clock_total_a"),
        (pl.col("clock_curtail") + pl.col("tu_b")).alias("clock_total_b"),
    ).with_columns(
        (pl.col("clock_total_a") - pl.col("octopus")).alias("gap_a_vs_octopus"),
        (pl.col("clock_total_b") - pl.col("octopus")).alias("gap_b_vs_octopus"),
        (pl.col("clock_total_a") - pl.col("neso_thermal")).alias("gap_a_vs_neso"),
        (pl.col("clock_total_b") - pl.col("neso_thermal")).alias("gap_b_vs_neso"),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path)
    args = ap.parse_args()
    with httpx.Client(timeout=120) as client:
        df = table(SnapshotStore(ROOT / "data"), client)
    if args.csv:
        df.write_csv(args.csv)
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=400,
                   float_precision=1):
        money = [c for c in df.columns if c not in ("month", "tu_days", "neso_to")]
        print(df.with_columns([(pl.col(c) / 1e6) for c in money]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
