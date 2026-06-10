import json
from datetime import date

import polars as pl

from subsidy_engine import sitedata
from subsidy_engine.money import SchemeResult

CTX = {
    "households": {"value": 28_400_000, "source": "ONS", "source_url": "https://ons", "as_of": 2023},
    "population": {"value": 68_300_000, "source": "ONS", "source_url": "https://ons", "as_of": 2023},
    "annual_demand_twh": {"value": 266, "source": "DESNZ", "source_url": "https://desnz", "as_of": 2024},
}


def model():
    annual = pl.DataFrame({"year": [2025, 2026], "cost_gbp": [3.0e9, 1.0e9]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    s = SchemeResult(
        scheme_id="cfd_renewable", label="CfD - renewables",
        perspectives=["renewables", "low_carbon", "all_levy"], cadence="daily",
        annual=annual, cumulative_gbp=4.0e9, runrate_gbp_per_year=2.0e9,
        data_to=date(2026, 6, 1),
        extras={"by_technology": [], "by_recipient": [], "gross_gbp": 4.1e9, "net_gbp": 4.0e9},
    )
    return {"schemes": [s], "perspectives": {
        "renewables": {"cumulative_gbp": 4.0e9, "runrate_gbp_per_year": 2.0e9,
                       "rate_gbp_per_sec": 63.38, "annual": annual, "since_year": 2025},
        "low_carbon": {"cumulative_gbp": 4.0e9, "runrate_gbp_per_year": 2.0e9,
                       "rate_gbp_per_sec": 63.38, "annual": annual, "since_year": 2025},
        "all_levy": {"cumulative_gbp": 4.0e9, "runrate_gbp_per_year": 2.0e9,
                     "rate_gbp_per_sec": 63.38, "annual": annual, "since_year": 2025},
    }}


def test_build_writes_all_files(tmp_path):
    freshness = {"cfd": {"retrieved_at": "2026-06-09T06:00:00+00:00",
                         "source_date": None, "source_url": "https://lccc"}}
    sitedata.build(model(), CTX, freshness, tmp_path, generated_at="2026-06-09T07:00:00+00:00")
    for name in ("totals.json", "timeseries.json", "breakdown.json", "meta.json"):
        assert (tmp_path / name).is_file(), name

    totals = json.loads((tmp_path / "totals.json").read_text())
    r = totals["perspectives"]["renewables"]
    assert r["cumulative_gbp"] == 4.0e9
    assert r["per_household_per_year_gbp"] == round(2.0e9 / 28_400_000, 2)
    assert r["per_mwh_delivered_gbp"] == round(2.0e9 / (266 * 1_000_000), 2)
    assert totals["generated_at"] == "2026-06-09T07:00:00+00:00"

    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert ts["perspectives"]["renewables"]["annual"] == [
        {"year": 2025, "cost_gbp": 3.0e9}, {"year": 2026, "cost_gbp": 1.0e9}]

    breakdown = json.loads((tmp_path / "breakdown.json").read_text())
    assert breakdown["schemes"][0]["id"] == "cfd_renewable"
    assert breakdown["schemes"][0]["gross_gbp"] == 4.1e9

    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["freshness"]["cfd"]["retrieved_at"].startswith("2026-06-09")
    assert "context" in meta
