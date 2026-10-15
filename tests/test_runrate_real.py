"""Real run-rate and per-household figures, each line from its own year
(Richard, 15 Oct 2026; Technical Paper No. 1 §4.3).

Each line's run-rate is converted to 2024 prices from the year of the
mid-point of the twelve months ending at its data_to (years past the CPIH
series take the latest index), and the real run-rate, per-second,
per-household and per-MWh figures sum the lines. At the 14 Oct 2026 build this
must give Report No. 1's figures.json values: run-rate £18.83bn, £649.42 a
household, £596.79 a second. The superseded rule (whole cash run-rate x CPIH
2024/2025 in one step) gave £18.36bn / £633.16; it must not come back.

The carry-forward estimate is NOT converted this way: money after a line's
data end is converted at the latest index (paper §8.1), checked in
test_carry_forward.py and again here.
"""
import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import money, sitedata
from subsidy_engine.money import SchemeResult
from subsidy_engine.reference import load_deflators

HERE = Path(__file__).parent
FIX = json.loads((HERE / "data_tp1_lag_2026-10-14.json").read_text())
DEFL = load_deflators(HERE.parent / "reference" / "deflators.yaml")
BN = 1e9

# Report No. 1 figures.json (reports-programme/no1-price-of-support, build
# 2026-10-14T23:53:17Z), vendored 15 Oct 2026
FIGURES = {
    "runrate_total_real": 18833324150.70956,
    "direct_runrate_real": 12349264479.197556,
    "indirect_runrate_real": 6484059671.512006,
    "full_per_household_real": 649.42,
    "direct_per_household_real": 425.84,
    "combined_rate_per_sec_real": 596.7920295177568,
    "direct_rate_per_sec_real": 391.3245772554806,
    "households": 29_000_000,
    # the superseded single-conversion figures (the live Clock until the 16 Oct 2026 release)
    "runrate_total_real_clock_rule": 18361790421.601887,
    "full_per_household_real_clock_rule": 633.16,
}
PER_LINE_REAL = {   # figures.json scheme_<id>_runrate_real
    "cfd_renewable": 2469797213.6806226, "constraints": 335467265.5169334,
    "capacity_market": 489212087.75446415, "ro": 7700000000.0, "fit": 1844000000.0,
    "ccl": 446200000.0, "ets": 882834732.0, "tnuos": 1886113232.0900002,
    "constraint_turnup": 1538820931.3669002, "bsuos": 1240878688.300641,
}
CTX = {
    "households": {"value": FIGURES["households"], "source": "ONS", "source_url": "https://ons", "as_of": 2025},
    "population": {"value": 68_300_000, "source": "ONS", "source_url": "https://ons", "as_of": 2025},
    "annual_demand_twh": {"value": 266, "source": "DESNZ", "source_url": "https://desnz", "as_of": 2024},
}


def _schemes() -> list[SchemeResult]:
    out = []
    for line in FIX["lines"]:
        to = date.fromisoformat(line["data_to"])
        rr = line["runrate_per_year"]
        out.append(SchemeResult(
            scheme_id=line["id"], label=line["id"], perspectives=["renewables"],
            cadence="annual", layer=line["layer"],
            annual=pl.DataFrame({"year": [2024], "cost_gbp": [line["cumulative"]],
                                 "cost_gbp_2024": [line["cumulative"]]}),
            cumulative_gbp=line["cumulative"], runrate_gbp_per_year=rr, data_to=to,
            runrate_gbp_per_year_2024=rr * money.runrate_real_factor(to, DEFL)))
    return out


def _model(schemes):
    direct = [s for s in schemes if s.layer == "direct"]
    indirect = [s for s in schemes if s.layer == "indirect"]
    return {"schemes": schemes, "real_factor": money.latest_real_factor(DEFL),
            "perspectives": {"renewables": money._aggregate(direct)},
            "indirect": money._aggregate(indirect)}


def test_each_line_from_its_own_year_matches_figures_json():
    assert {l["id"] for l in FIX["lines"]} == set(PER_LINE_REAL)
    for s in _schemes():
        assert s.runrate_gbp_per_year_2024 == pytest.approx(PER_LINE_REAL[s.scheme_id], abs=1.0), s.scheme_id
    # lines already in 2024 money are not converted again
    years = {l["id"]: money.runrate_year(date.fromisoformat(l["data_to"])) for l in FIX["lines"]}
    assert years["ro"] == years["fit"] == years["ccl"] == years["tnuos"] == 2024
    assert years["cfd_renewable"] == years["bsuos"] == 2026


def test_clock_runrate_household_and_per_second_equal_figures_json(tmp_path):
    sitedata.build(_model(_schemes()), CTX, {}, tmp_path, generated_at=FIX["build"])
    t = json.loads((tmp_path / "totals.json").read_text())
    d, i = t["perspectives"]["renewables"]["real"], t["indirect"]["real"]

    runrate = d["runrate_per_year"] + i["runrate_per_year"]
    assert abs(runrate - FIGURES["runrate_total_real"]) < 0.01 * BN
    assert round(runrate / BN, 2) == 18.83
    assert abs(d["runrate_per_year"] - FIGURES["direct_runrate_real"]) < 0.01 * BN
    assert abs(i["runrate_per_year"] - FIGURES["indirect_runrate_real"]) < 0.01 * BN

    # the hero strip's household figure is the two floored blocks summed
    hh = d["per_household_per_year"] + i["per_household_per_year"]
    assert abs(hh - FIGURES["full_per_household_real"]) < 1.0
    assert round(hh) == 649
    # the Clock floors each block to the penny (425.83); figures.json rounds (425.84)
    assert abs(d["per_household_per_year"] - FIGURES["direct_per_household_real"]) < 0.02

    rate = d["rate_per_sec"] + i["rate_per_sec"]
    assert abs(rate - FIGURES["combined_rate_per_sec_real"]) < 0.01
    assert abs(d["rate_per_sec"] - FIGURES["direct_rate_per_sec_real"]) < 0.01

    # per MWh follows the same run-rate
    assert d["per_mwh_delivered"] == pytest.approx(d["runrate_per_year"] / 266e6, abs=0.01)

    # breakdown.json carries each line's real run-rate (the cards read it)
    bd = json.loads((tmp_path / "breakdown.json").read_text())
    for s in bd["schemes"]:
        assert s["runrate_per_year_real"] == pytest.approx(PER_LINE_REAL[s["id"]], abs=1.0)


def test_the_single_conversion_rule_does_not_come_back(tmp_path):
    sitedata.build(_model(_schemes()), CTX, {}, tmp_path, generated_at=FIX["build"])
    t = json.loads((tmp_path / "totals.json").read_text())
    d, i = t["perspectives"]["renewables"], t["indirect"]
    cash = d["runrate_per_year"] + i["runrate_per_year"]
    one_step = cash * money.latest_real_factor(DEFL)
    assert one_step == pytest.approx(FIGURES["runrate_total_real_clock_rule"], abs=1.0)
    real = d["real"]["runrate_per_year"] + i["real"]["runrate_per_year"]
    assert real - one_step > 0.4 * BN                    # £18.83bn, not £18.36bn
    hh = d["real"]["per_household_per_year"] + i["real"]["per_household_per_year"]
    assert hh - FIGURES["full_per_household_real_clock_rule"] > 15   # £649, not £633


def test_carry_forward_stays_at_the_latest_index(tmp_path):
    # paper §8.1: the estimate since each line's data end is cash converted at
    # the 2025 index, whatever year the line's run-rate belongs to
    sitedata.build(_model(_schemes()), CTX, {}, tmp_path, generated_at=FIX["build"])
    t = json.loads((tmp_path / "totals.json").read_text())
    factor = FIX["cpih_2024"] / FIX["cpih_2025"]
    for blk in (t["perspectives"]["renewables"], t["indirect"]):
        assert blk["real"]["estimated_since"] == pytest.approx(blk["estimated_since"] * factor)
        for cash, real in zip(blk["carry_forward"], blk["real"]["carry_forward"]):
            assert real["rate_per_sec"] == pytest.approx(cash["rate_per_sec"] * factor)


def test_build_sets_each_lines_real_runrate():
    # uk build stamps runrate_gbp_per_year_2024 on every line from its own year;
    # an older model without it falls back to the latest index
    blk = money._aggregate([SchemeResult(
        scheme_id="x", label="x", perspectives=["renewables"], cadence="annual",
        annual=pl.DataFrame({"year": [2024], "cost_gbp": [1.0]}),
        cumulative_gbp=1.0, runrate_gbp_per_year=1.0, data_to=date(2024, 12, 31))])
    assert "runrate_gbp_per_year_2024" not in blk
    assert money.runrate_real_factor(None, DEFL) == money.latest_real_factor(DEFL)
    assert money.runrate_real_factor(date(2030, 6, 30), DEFL) == money.latest_real_factor(DEFL)
    assert money.runrate_real_factor(date(2025, 3, 31), DEFL) == 1.0
