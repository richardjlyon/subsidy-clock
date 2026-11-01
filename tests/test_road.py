"""The starting level (Richard's ruling C, 1 Nov 2026; re-confirms A1/A2 of 14 Oct): TNUoS and BSUoS count what
each year cost above the engine's no-net-zero road for that year, GO5 (high-voltage grid) and GO4 (balancing),
from the pinned engine release v4-s43 (aios-harness#43). Generators' share included (as live); years signed (below the
road negative, 1 Nov 2026) and BSUoS net of the wind constraint payments counted as their own line (as live).

Expected values come from the engine's export file read directly, not from the Clock's code.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from subsidy_engine import reference
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk import inputs
from subsidy_engine_uk import register as R

ROOT = Path(__file__).resolve().parents[1]


def _export():
    mp = yaml.safe_load((ROOT / "reference/model_pin.yaml").read_text())
    return json.loads((ROOT / mp["clock_export_file"]).read_text())


@pytest.fixture(scope="module")
def model():
    return inputs.assemble_model(ROOT)[0]


def _s(model, sid):
    return next(s for s in model["schemes"] if s.scheme_id == sid)


def _annual(model, sid):
    return {r["year"]: r["cost_gbp"] for r in _s(model, sid).annual.to_dicts()}


def _raw(model, sid):
    return {int(r["year"]): r["cost"] for r in _s(model, sid).extras["raw_annual"]}


def test_road_is_the_engines_go5_and_go4_per_year():
    ex = _export()
    road = R.road_from_engine(ROOT)
    for key, block in (("tnuos", "grid"), ("bsuos", "balancing")):
        assert road[key]["engine_version"] == "v4-s43"
        assert road[key]["carry_forward_from"] == ex["carry_forward"]["from"] == 2025
        for y, row in ex[block]["years"].items():
            assert road[key]["years"][int(y)] == row["central_gbp"], (key, y)


def test_tnuos_counts_each_year_above_the_road(model):
    ex = _export()["grid"]["years"]
    raw, got = _raw(model, "tnuos"), _annual(model, "tnuos")
    for y in range(2002, 2025):
        # signed years (Richard, 1 Nov 2026, as RB): a year below the road counts as negative
        assert got[y] == pytest.approx(raw[y] - ex[str(y)]["central_gbp"], abs=0.01), y


def test_bsuos_counts_each_closed_year_above_the_road_net_of_wind_constraints(model):
    ex = _export()["balancing"]["years"]
    raw, con = _raw(model, "bsuos"), _annual(model, "constraints")
    bs, tu = _annual(model, "bsuos"), _annual(model, "constraint_turnup")
    for y in range(2002, 2025):
        expected = raw[y] - ex[str(y)]["central_gbp"] - con.get(y, 0.0)   # signed years, as RB
        # the turn-up line is split out of the uplift, never more than it and never negative
        assert bs[y] + tu.get(y, 0.0) == pytest.approx(expected, abs=0.01), y
        assert 0.0 <= tu.get(y, 0.0) <= max(0.0, expected) + 0.01, y


def test_some_years_below_the_road_count_as_negative(model):
    assert min(_annual(model, "tnuos")[y] for y in range(2002, 2025)) < 0
    assert min(_annual(model, "bsuos")[y] for y in range(2002, 2025)) < 0


def test_years_after_the_engine_carry_its_last_year_by_cpih(model):
    ex = _export()["balancing"]["years"]
    d = reference.load_deflators(ROOT / "reference" / "deflators.yaml")
    idx = dict(zip(d["year"].to_list(), d["index"].to_list()))
    latest = idx[max(idx)]
    from subsidy_engine_uk.uplift import road_series
    road = dict(zip(*road_series([2026], R.road_from_engine(ROOT)["bsuos"], d).to_dict(as_series=False).values()))
    assert road[2026] == pytest.approx(ex["2025"]["central_gbp"] * idx.get(2026, latest) / idx[2025], rel=1e-12)


def test_the_flat_baselines_are_retired():
    assert not (ROOT / "reference/baselines.yaml").exists()
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
    assert "baselines.yaml" not in src


def test_a_part_year_subtracts_the_road_pro_rated_to_the_data_date(model):
    """Technical fix (Richard, 1 Nov 2026): BSUoS 2026 holds data to its last day only, so the road for 2026
    is pro-rated to the same days ((data_to - 1 Jan + 1) / days in the year), not a full year."""
    from datetime import date
    s = _s(model, "bsuos")
    data_to = s.data_to
    assert data_to.year == 2026 and data_to < date(2026, 12, 31)
    frac = ((data_to - date(2026, 1, 1)).days + 1) / 365
    ex = _export()["balancing"]["years"]
    d = reference.load_deflators(ROOT / "reference" / "deflators.yaml")
    idx = dict(zip(d["year"].to_list(), d["index"].to_list()))
    full = ex["2025"]["central_gbp"] * idx.get(2026, idx[max(idx)]) / idx[2025]
    road = {r["year"]: r["cost"] for r in s.extras["road_annual"]}
    assert road[2026] == pytest.approx(full * frac, rel=1e-12)
    raw = _raw(model, "bsuos")
    tu = _annual(model, "constraint_turnup")
    from subsidy_engine_uk.schemes import constraints as C
    con = {r["year"]: r["cost_gbp"] for r in C.annual_through(
        SnapshotStore(ROOT / "data"), reference.load_annual_costs(
            ROOT / "reference" / "annual_scheme_costs.yaml")["constraints_history"],
        _s(model, "constraints"), data_to).to_dicts()}
    assert _annual(model, "bsuos")[2026] + tu[2026] == pytest.approx(raw[2026] - full * frac - con[2026], abs=0.01)
