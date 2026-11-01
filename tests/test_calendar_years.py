"""Calendar-year basis for fixed-period totals (definitions D-13; aios-harness#42 step 6).

Any 2002-24 total is on calendar years. RO and FiT are published by obligation (scheme) year, April to March,
keyed by start year; they are calendarised as the gas-counterfactual engine does (spec section 2):
CY(y) = 0.25 x FY(y-1) + 0.75 x FY(y). Each calendar year is then deflated at its own index. The running totals
the live site shows are not touched. Expected values are worked by hand, not read from the code.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import reference
from subsidy_engine_uk import calendar_years as CY
from subsidy_engine_uk import inputs

ROOT = Path(__file__).resolve().parents[1]


def test_fy_to_cy_is_the_engines_rule():
    fy = {2010: 100.0, 2011: 200.0, 2012: 400.0}
    assert CY.fy_to_cy(fy, range(2009, 2013)) == {2009: 0.0, 2010: 75.0, 2011: 175.0, 2012: 350.0}
    with pytest.raises(ValueError, match="2013"):
        CY.fy_to_cy(fy, range(2012, 2014))   # CY2013 needs FY2013, not yet published


@pytest.fixture(scope="module")
def model():
    return inputs.assemble_model(ROOT)[0]


@pytest.fixture(scope="module")
def deflators():
    return reference.load_deflators(ROOT / "reference" / "deflators.yaml")


def _fy(model, sid):
    s = next(s for s in model["schemes"] if s.scheme_id == sid)
    return {r["year"]: r["cost_gbp"] for r in s.annual.to_dicts()}


def test_ro_and_fit_2002_24_are_calendarised(model, deflators):
    out = CY.period_totals(model, 2002, 2024, deflators=deflators)
    idx = dict(zip(deflators["year"].to_list(), deflators["index"].to_list()))
    base = idx[2024]
    for sid in ("ro", "fit"):
        fy = _fy(model, sid)
        # 2002-24 on calendar years: every scheme year to 2023-24 in full, three quarters of 2024-25
        cash = sum(v for y, v in fy.items() if y <= 2023) + 0.75 * fy[2024]
        assert out["schemes"][sid]["cash"] == pytest.approx(cash, rel=1e-12), sid
        assert out["schemes"][sid]["basis"] == "calendarised from obligation years"
        real = sum((0.25 * fy.get(y - 1, 0.0) + 0.75 * fy.get(y, 0.0)) * base / idx[y]
                   for y in range(2002, 2025))
        assert out["schemes"][sid]["real"] == pytest.approx(real, rel=1e-12), sid


def test_calendar_year_lines_are_taken_as_they_are(model, deflators):
    out = CY.period_totals(model, 2002, 2024, deflators=deflators)
    s = next(s for s in model["schemes"] if s.scheme_id == "cfd_renewable")
    a = s.annual.filter(pl.col("year").is_between(2002, 2024))
    assert out["schemes"]["cfd_renewable"]["cash"] == pytest.approx(float(a["cost_gbp"].sum()), rel=1e-12)
    assert out["schemes"]["cfd_renewable"]["basis"] == "calendar"


def test_headline_blocks_are_the_sum_of_their_lines(model, deflators):
    out = CY.period_totals(model, 2002, 2024, deflators=deflators)
    by = {s.scheme_id: s for s in model["schemes"]}
    ren = [k for k in out["schemes"] if by[k].layer == "direct" and "renewables" in by[k].perspectives]
    ind = [k for k in out["schemes"] if by[k].layer == "indirect"]
    assert "ro" in ren and "fit" in ren and "bsuos" in ind
    for block, ids in (("renewables", ren), ("indirect", ind)):
        for col in ("cash", "real"):
            assert out[block][col] == pytest.approx(sum(out["schemes"][k][col] for k in ids), rel=1e-12)


def test_running_totals_are_not_calendarised(model):
    """The site's running totals keep each line's own year keys: the cut is for fixed-period figures only."""
    s = next(s for s in model["schemes"] if s.scheme_id == "ro")
    assert s.cumulative_gbp == pytest.approx(float(s.annual["cost_gbp"].sum()), rel=1e-12)
