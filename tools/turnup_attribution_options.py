"""Attribution options for constraint turn-up: effect on headline and direct hero.

Runs the real build from the local store and reference data (writes nothing),
then restates the headline (combined direct + indirect, 2024 prices) and the
direct hero (renewables perspective, 2024 prices) under each option.

    uv run python tools/turnup_attribution_options.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from subsidy_engine import money, reference  # noqa: E402
from subsidy_engine.store import SnapshotStore  # noqa: E402
from subsidy_engine_uk import build as uk_build  # noqa: E402
from subsidy_engine_uk import stations  # noqa: E402


def run_build():
    r = ROOT / "reference"
    refs = reference.load_annual_costs(r / "annual_scheme_costs.yaml")
    refs.update(reference.load_annual_costs(r / "indirect_annual.yaml"))
    deflators = reference.load_deflators(r / "deflators.yaml")
    m = uk_build.build(
        SnapshotStore(ROOT / "data"), refs, deflators=deflators,
        baselines=reference.load_baselines(r / "baselines.yaml"),
        station_map=stations.load_station_map(r / "cfd_stations.csv"),
        ro_stations=stations.load_ro_stations(r / "ro_stations.csv"),
        bmu_map=stations.load_station_bmus(r / "station_bmu_map.csv"))
    return m, deflators


def real(df: pl.DataFrame, deflators: pl.DataFrame) -> float:
    return float(money.add_real(df.select("year", "cost_gbp"), deflators)["cost_gbp_2024"].sum())


def main() -> int:
    m, defl = run_build()
    by_id = {s.scheme_id: s for s in m["schemes"]}
    tu = by_id.get("constraint_turnup")
    if tu is None:
        print("no constraint_turnup data in the store")
        return 1
    direct = m["perspectives"]["renewables"]["cumulative_gbp_2024"]
    indirect = m["indirect"]["cumulative_gbp_2024"]
    headline = direct + indirect

    capped = tu.annual.select("year", "cost_gbp")
    measured = pl.DataFrame(tu.extras["measured_annual"]).rename({"cost": "cost_gbp"}) \
        .with_columns(pl.col("year").cast(pl.Int64))
    uplift = (by_id["bsuos"].annual.select("year", "cost_gbp")
              .join(capped.rename({"cost_gbp": "tu"}), on="year", how="left")
              .with_columns((pl.col("cost_gbp") + pl.col("tu").fill_null(0.0)).alias("uplift"))
              .select("year", "uplift"))
    yr = (measured.rename({"cost_gbp": "measured"})
          .join(uplift, on="year", how="left")
          .join(capped.rename({"cost_gbp": "capped"}), on="year", how="left")
          .sort("year"))
    print("year  measured(b) £m  BSUoS uplift after wind £m  turn-up line £m  cap binds")
    for r in yr.to_dicts():
        print(f"{r['year']}  {r['measured']/1e6:14.0f}  {r['uplift']/1e6:26.0f}  "
              f"{r['capped']/1e6:15.0f}  {'YES' if r['measured'] > r['capped'] + 1 else ''}")

    tu_capped_real = real(capped, defl)
    tu_measured_real = real(measured, defl)
    excess_real = tu_measured_real - tu_capped_real
    cc = tu.extras["cross_check_cumulative"]
    share = cc["accepted_offers_wind"] / cc["accepted_offers"] if cc["accepted_offers"] else 0.0

    print(f"\nheadline combined_real now £{headline/1e9:.2f}bn; direct hero £{direct/1e9:.2f}bn; "
          f"indirect £{indirect/1e9:.2f}bn")
    print(f"turn-up line (capped) real £{tu_capped_real/1e9:.3f}bn; measured real "
          f"£{tu_measured_real/1e9:.3f}bn; run-rate nominal £{tu.runrate_gbp_per_year/1e6:.0f}m/yr")
    print(f"cross-check: accepted offers in wind-constrained periods are {share:.0%} of "
          f"all system-flagged non-wind offers")
    opts = [
        ("A  Default (built): own line inside indirect layer", 0.0, 0.0),
        ("B  Move to direct, capped at the BSUoS uplift", tu_capped_real, 0.0),
        ("C  Move to direct, full measured figure (uncapped)", tu_measured_real, excess_real),
    ]
    print(f"\n{'option':52} {'direct £bn':>11} {'Δdirect':>8} {'headline £bn':>13} {'Δheadline':>10}")
    for label, d_dir, d_head in opts:
        print(f"{label:52} {(direct+d_dir)/1e9:11.2f} {d_dir/1e9:8.2f} "
              f"{(headline+d_head)/1e9:13.2f} {d_head/1e9:10.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
