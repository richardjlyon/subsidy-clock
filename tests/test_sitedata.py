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

DEFLATOR_INFO = {"source": "ONS CPIH L522", "source_url": "https://ons", "base_year": 2024}


def model():
    annual = pl.DataFrame(
        {"year": [2025, 2026], "cost_gbp": [3.0e9, 1.0e9],
         "cost_gbp_2024": [2.9e9, 0.95e9]},
        schema={"year": pl.Int64, "cost_gbp": pl.Float64, "cost_gbp_2024": pl.Float64})
    direct = SchemeResult(
        scheme_id="cfd_renewable", label="CfD - renewables",
        perspectives=["renewables", "low_carbon"], cadence="daily",
        annual=annual, cumulative_gbp=4.0e9, runrate_gbp_per_year=2.0e9,
        data_to=date(2026, 6, 1),
        extras={"by_technology": [], "by_recipient": [], "gross_gbp": 4.1e9, "net_gbp": 4.0e9},
    )
    indirect = SchemeResult(
        scheme_id="bsuos", label="Balancing costs (BSUoS uplift)",
        perspectives=[], cadence="daily", layer="indirect",
        annual=annual, cumulative_gbp=4.0e9, runrate_gbp_per_year=1.0e9,
        data_to=date(2026, 6, 1),
        attribution_pct=0.4, attribution_note="uplift above baseline",
        attribution_confidence="low",
    )
    block = {"cumulative_gbp": 4.0e9, "runrate_gbp_per_year": 2.0e9,
             "rate_gbp_per_sec": 63.38, "annual": annual, "since_year": 2025,
             "cumulative_gbp_2024": 3.85e9, "runrate_gbp_per_year_2024": 1.94e9,
             "rate_gbp_per_sec_2024": 61.48}
    iblock = dict(block, runrate_gbp_per_year=1.0e9)
    return {"schemes": [direct, indirect],
            "perspectives": {"renewables": dict(block), "low_carbon": dict(block)},
            "indirect": iblock}


def test_build_writes_all_files(tmp_path):
    freshness = {"cfd": {"retrieved_at": "2026-06-09T06:00:00+00:00",
                         "source_date": None, "source_url": "https://lccc"}}
    sitedata.build(model(), CTX, freshness, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00",
                   deflator_info=DEFLATOR_INFO)
    for name in ("totals.json", "timeseries.json", "breakdown.json", "meta.json"):
        assert (tmp_path / name).is_file(), name

    totals = json.loads((tmp_path / "totals.json").read_text())
    r = totals["perspectives"]["renewables"]
    assert r["cumulative_gbp"] == 4.0e9
    assert r["per_household_per_year_gbp"] == round(2.0e9 / 28_400_000, 2)
    assert r["real_2024"]["cumulative_gbp"] == 3.85e9
    assert r["real_2024"]["per_household_per_year_gbp"] == round(1.94e9 / 28_400_000, 2)
    assert "all_levy" not in totals["perspectives"]
    ind = totals["indirect"]
    assert ind["runrate_gbp_per_year"] == 1.0e9
    assert ind["real_2024"]["cumulative_gbp"] == 3.85e9

    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert ts["schemes"]["bsuos"]["annual"][0] == {
        "year": 2025, "cost_gbp": 3.0e9, "cost_gbp_2024": 2.9e9}

    breakdown = json.loads((tmp_path / "breakdown.json").read_text())
    by_id = {s["id"]: s for s in breakdown["schemes"]}
    assert by_id["cfd_renewable"]["layer"] == "direct"
    b = by_id["bsuos"]
    assert b["layer"] == "indirect"
    assert b["attribution_pct"] == 0.4
    assert b["attribution_confidence"] == "low"
    assert b["attribution_note"] == "uplift above baseline"

    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["deflator"]["base_year"] == 2024


def test_build_writes_electricity_bill(tmp_path):
    bill = pl.DataFrame(
        {"year": [2023, 2024],
         "total_bill_gbp": [71.2e9, 60.0e9],
         "total_bill_gbp_2024": [72.0e9, 60.0e9]},
        schema={"year": pl.Int64, "total_bill_gbp": pl.Float64,
                "total_bill_gbp_2024": pl.Float64})
    sitedata.build(model(), CTX, {}, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00",
                   bill_annual=bill,
                   bill_info={"source": "DUKES 1.3",
                              "source_url": "https://gov.uk/dukes",
                              "verified": True})
    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert ts["electricity_bill"]["annual"][0] == {
        "year": 2023, "total_bill_gbp": 71.2e9, "total_bill_gbp_2024": 72.0e9}
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["bill"]["source_url"] == "https://gov.uk/dukes"


def test_build_without_bill_omits_electricity_bill_block(tmp_path):
    sitedata.build(model(), CTX, {}, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00")
    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert "electricity_bill" not in ts


def test_write_csvs(tmp_path):
    sitedata.write_csvs(model(), tmp_path, restatements=[
        {"scheme": "bsuos", "table": "daily",
         "detected_at": "2026-06-10T06:31:04+00:00", "partition": "2026-2027",
         "previous_version": "20260610T063012", "new_version": "20260610T063104"}])
    # per-scheme files named by their public slug
    cfd = (tmp_path / "cfd.csv").read_text().splitlines()
    assert cfd[0] == "year,cost_gbp,cost_gbp_2024"
    assert cfd[1] == "2025,3.0e9,2.9e9" or cfd[1].startswith("2025,3000000000")
    assert (tmp_path / "bsuos.csv").is_file()
    # combined annual: one row per year, one column per scheme
    combined = (tmp_path / "combined-annual.csv").read_text().splitlines()
    assert combined[0] == "year,cfd_renewable_gbp,bsuos_gbp"
    assert combined[1].startswith("2025,")
    # restatements published alongside
    rst = (tmp_path / "restatements.csv").read_text().splitlines()
    assert rst[0] == "scheme,table,detected_at,partition,previous_version,new_version"
    assert rst[1].startswith("bsuos,daily,")


def test_write_csvs_pennies_match_store(tmp_path):
    """The published CSV must sum to the scheme's cumulative figure - to the penny."""
    m = model()
    sitedata.write_csvs(m, tmp_path, restatements=[])
    total = 0.0
    for line in (tmp_path / "cfd.csv").read_text().splitlines()[1:]:
        total += float(line.split(",")[1])
    assert abs(total - m["schemes"][0].cumulative_gbp) < 0.01


def test_write_csvs_no_restatements_writes_header_only(tmp_path):
    sitedata.write_csvs(model(), tmp_path, restatements=[])
    rst = (tmp_path / "restatements.csv").read_text().splitlines()
    assert rst == ["scheme,table,detected_at,partition,previous_version,new_version"]
