from datetime import date

import polars as pl

from subsidy_engine_uk import build as uk_build
from tests.cf_helpers import cf_series, indexed


def deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, 136.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def _cf100():
    idx = dict(zip(deflators()["year"].to_list(), deflators()["index"].to_list()))
    ser = indexed(100.0, idx, 71.5)
    return {"bsuos": cf_series(ser), "tnuos": cf_series(ser)}


def test_counterfactual_uplift_is_signed_and_nets_subtraction():
    """T2 (Richard, 14 Oct 2026): per-year excess is SIGNED (was floored at zero each year
    until v4-s35); only the line's whole-period total is floored (`floor_line_total`)."""
    raw = pl.DataFrame({"year": [2003, 2023], "cost_gbp": [60.0, 1000.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    constraints = pl.DataFrame({"year": [2023], "cost_gbp": [100.0]},
                               schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    cf = cf_series({2002: 95.0, 2003: 99.0, 2004: 101.0, 2005: 105.0, 2023: 180.0})
    out = uk_build.counterfactual_uplift(raw, cf, deflators(), subtract=constraints)
    rows = {r["year"]: r["cost_gbp"] for r in out.to_dicts()}
    # 2003: 60 - 99 = -39, kept negative
    assert rows[2003] == -39.0
    # 2023: 1000 - 180 (the engine's own figure for the year) - 100
    assert abs(rows[2023] - (1000.0 - 180.0 - 100.0)) < 1e-9


def test_counterfactual_carries_last_engine_year_by_cpih():
    """Years after the engine's last year carry it by CPIH (index(y)/index(last)); a year
    without an index (the run-rate's year) uses the latest index; a year before the engine's
    first year is an error, never a silent zero."""
    cf = cf_series({2023: 128.0, 2024: 132.0})
    s = uk_build.counterfactual_series([2023, 2024, 2025, 2026], cf, deflators())
    got = dict(zip(s["year"].to_list(), s["cf"].to_list()))
    assert got[2023] == 128.0 and got[2024] == 132.0
    assert abs(got[2025] - 132.0 * 136.0 / 132.0) < 1e-9
    assert abs(got[2026] - 132.0 * 136.0 / 132.0) < 1e-9          # no 2026 index: latest
    assert abs(uk_build.counterfactual_runrate(cf, deflators()) - 136.0) < 1e-9
    import pytest
    with pytest.raises(ValueError, match="engine starts 2023"):
        uk_build.counterfactual_series([2022], cf, deflators())


def test_build_integration(tmp_path):
    from subsidy_engine.reference import ReferenceScheme
    from subsidy_engine.store import SnapshotStore

    store = SnapshotStore(tmp_path)
    gen = pl.DataFrame({
        "date": [date(2026, 4, 10), date(2026, 4, 10)],
        "cfd_id": ["AR1-A", "INV-N"],
        "unit_name": ["Wind Farm A", "Nuke N"],
        "technology": ["Offshore Wind", "Nuclear"],
        "generation_mwh": [100.0, 200.0],
        "payment_gbp": [5000.0, 7000.0],
        "strike_price_gbp_mwh": [100.0, 130.0],
        "is_renewable": [True, False],
    })
    store.write("cfd", "generation", gen, source_url="u", date_col="date")
    con = pl.DataFrame({
        "date": [date(2026, 4, 10)], "bmu": ["T_W-1"], "lead_party": ["W"],
        "volume_mwh": [-10.0], "cost_gbp": [600.0],
    })
    store.write("constraints", "daily", con, source_url="u", partition="2026-04-10")
    hist = pl.DataFrame({"year": [2024, 2025], "cost_gbp": [390e6, 382e6]},
                        schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    refs = {
        "constraints_history": ReferenceScheme(
            "constraints_history", "Wind constraints history",
            ["renewables", "low_carbon"], "annual", "s", "https://s",
            True, hist),
        "ro": ReferenceScheme("ro", "Renewables Obligation",
                              ["renewables", "low_carbon"], "annual",
                              "s", "https://s", True,
                              pl.DataFrame({"year": [2024], "cost_gbp": [7.0e9]},
                                           schema={"year": pl.Int64, "cost_gbp": pl.Float64})),
        "fit": ReferenceScheme("fit", "Feed-in Tariffs",
                               ["renewables", "low_carbon"], "annual",
                               "s", "https://s", True,
                               pl.DataFrame({"year": [2024], "cost_gbp": [1.8e9]},
                                            schema={"year": pl.Int64, "cost_gbp": pl.Float64})),
    }
    model = uk_build.build(store, refs, deflators=deflators(), counterfactual=_cf100())
    by_id = {s.scheme_id: s for s in model["schemes"]}
    # CfD split: renewable vs low-carbon, no leakage
    assert by_id["cfd_renewable"].cumulative_gbp == 5000.0
    assert by_id["cfd_low_carbon"].cumulative_gbp == 7000.0
    assert "renewables" not in by_id["cfd_low_carbon"].perspectives
    # constraints: partial 2026 bottom-up kept (after history's last year 2025)
    con_annual = by_id["constraints"].annual
    assert 600.0 in con_annual.filter(pl.col("year") == 2026)["cost_gbp"].to_list()
    assert by_id["constraints"].cumulative_gbp == 390e6 + 382e6 + 600.0
    assert by_id["constraints"].extras["bottom_up_from"] == "2026-04-10"
    # perspective nesting: renewables excludes nuclear CfD, low_carbon includes it
    p = model["perspectives"]
    assert set(p) == {"renewables", "low_carbon"}
    assert p["renewables"]["cumulative_gbp"] == 5000.0 + (390e6 + 382e6 + 600.0) + 7.0e9 + 1.8e9
    assert p["low_carbon"]["cumulative_gbp"] == p["renewables"]["cumulative_gbp"] + 7000.0


def _ref(scheme_id, label, annual_map, *, perspectives=(), rule="r", conf="medium"):
    from subsidy_engine.reference import ReferenceScheme
    annual = pl.DataFrame(
        {"year": list(annual_map.keys()),
         "cost_gbp": [float(v) for v in annual_map.values()]},
        schema={"year": pl.Int64, "cost_gbp": pl.Float64}).sort("year")
    return ReferenceScheme(scheme_id, label, list(perspectives), "annual",
                           "s", "https://s", True, annual,
                           attribution_rule=rule, attribution_confidence=conf)


def test_build_indirect_layer(tmp_path):
    from subsidy_engine.store import SnapshotStore

    store = SnapshotStore(tmp_path)
    # direct constraints: bottom-up day in 2026 + history
    con = pl.DataFrame({
        "date": [date(2026, 4, 10)], "bmu": ["T_W-1"], "lead_party": ["W"],
        "volume_mwh": [-10.0], "cost_gbp": [100.0],
    })
    store.write("constraints", "daily", con, source_url="u", partition="2026-04-10")
    # bsuos bottom-up: one fiscal-year partition with two days in 2026
    bs = pl.DataFrame({"date": [date(2026, 4, 10), date(2026, 4, 11)],
                       "cost_gbp": [600.0, 400.0]},
                      schema={"date": pl.Date, "cost_gbp": pl.Float64})
    store.write("bsuos", "daily", bs, source_url="u", partition="2026-2027")
    # CM monthly payments
    cm = pl.DataFrame({"date": [date(2026, 1, 1)], "auction": ["T-4"],
                       "payment_gbp": [50.0]})
    store.write("capacity_market", "payments", cm, source_url="u", date_col="date")

    refs = {
        "constraints_history": _ref("constraints_history", "CH", {2024: 200.0},
                                    perspectives=("renewables", "low_carbon")),
        "ro": _ref("ro", "RO", {2024: 1000.0},
                   perspectives=("renewables", "low_carbon")),
        "fit": _ref("fit", "FIT", {2024: 500.0},
                    perspectives=("renewables", "low_carbon")),
        "ccl": _ref("ccl", "CCL", {2023: 80.0}),
        "ets": _ref("ets", "ETS", {2023: 90.0}),
        "tnuos": _ref("tnuos", "TNUoS", {2023: 1000.0}, conf="low"),
        "bsuos_history": _ref("bsuos_history", "BSUoS hist", {2023: 500.0}, conf="low"),
    }
    # engine no-net-zero costs equal to the old 100-at-2002-05 CPIH-carried example, so the
    # worked figures below are unchanged; 2026 carries 2025 forward by CPIH
    cfs = _cf100()
    # CM: the net-zero share of 2026 carries forward from 2025 (40%)
    cm_share = {"years": {2025: {"cm_paid_gbp": 100.0, "share": 0.4,
                                 "share_low": 0.1, "share_high": 1.0}},
                "carry_forward_from": 2025, "provenance": {}}
    model = uk_build.build(store, refs, deflators=deflators(), counterfactual=cfs,
                           cm_share=cm_share)
    by_id = {s.scheme_id: s for s in model["schemes"]}

    # layer assignment
    assert by_id["capacity_market"].layer == "indirect"
    for sid in ("ccl", "ets", "tnuos", "bsuos"):
        assert by_id[sid].layer == "indirect", sid
    for sid in ("constraints", "ro", "fit"):
        assert by_id[sid].layer == "direct", sid

    # ccl/ets pass through as stored
    assert by_id["ccl"].cumulative_gbp == 80.0

    # tnuos: uplift = max(0, 1000 - engine 2023 figure 100*(128/71.5))
    expected_tnuos = 1000.0 - 100.0 * 128.0 / 71.5
    assert abs(by_id["tnuos"].cumulative_gbp - expected_tnuos) < 1e-6

    # bsuos 2023 (history year): max(0, 500 - 100*(128/71.5) - 0 constraints)
    # bsuos 2026 (bottom-up partial year after history): raw 1000,
    #   engine 2025 figure carried by CPIH to the latest index (136): 100*136/71.5, constraints 2026 = 100
    # (T11: the BSUoS data end 11 Apr 2026, so the 2026 no-net-zero cost is pro-rated to
    # 101/365 of the year; the full year was subtracted until v4-s35)
    bs_annual = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    assert abs(bs_annual[2023] - (500.0 - 100.0 * 128.0 / 71.5)) < 1e-6
    assert abs(bs_annual[2026] - (1000.0 - 100.0 * 136.0 / 71.5 * 101 / 365 - 100.0)) < 1e-6

    # real columns exist everywhere
    for s in model["schemes"]:
        assert "cost_gbp_2024" in s.annual.columns, s.scheme_id

    # real run-rate: each line from its own year, blocks sum the lines
    # (Richard, 15 Oct 2026); not the cash total x the latest index
    import pytest
    from subsidy_engine.money import runrate_real_factor, latest_real_factor
    for s in model["schemes"]:
        assert s.runrate_gbp_per_year_2024 == pytest.approx(
            s.runrate_gbp_per_year * runrate_real_factor(s.data_to, deflators())), s.scheme_id
    ind = model["indirect"]
    assert ind["runrate_gbp_per_year_2024"] == pytest.approx(
        sum(s.runrate_gbp_per_year_2024 for s in model["schemes"] if s.layer == "indirect"))
    assert ind["runrate_gbp_per_year_2024"] != pytest.approx(
        ind["runrate_gbp_per_year"] * latest_real_factor(deflators()))
    assert model["real_factor"] == latest_real_factor(deflators())   # carry-forward's factor
    # indirect total = sum of the five components
    expected_indirect = (50.0 * 0.4 + 80.0 + 90.0 + expected_tnuos
                         + bs_annual[2023] + bs_annual[2026])
    assert abs(model["indirect"]["cumulative_gbp"] - expected_indirect) < 1e-6

    # direct perspectives unchanged by the indirect components (leakage guard)
    refs_direct_only = {k: refs[k] for k in ("constraints_history", "ro", "fit")}
    model2 = uk_build.build(store, refs_direct_only, deflators=deflators(),
                            counterfactual=cfs, cm_share=cm_share)
    assert (model["perspectives"]["renewables"]["cumulative_gbp"]
            == model2["perspectives"]["renewables"]["cumulative_gbp"])


def test_station_detail_quarters_contracts_and_negative_quarter(tmp_path):
    from subsidy_engine.reference import ReferenceScheme
    from subsidy_engine.store import SnapshotStore

    store = SnapshotStore(tmp_path)
    gen = pl.DataFrame({
        "date": [date(2021, 1, 10), date(2021, 2, 10),
                 date(2021, 10, 5), date(2021, 10, 6), date(2022, 1, 3)],
        "cfd_id": ["W-1", "W-1", "W-1", "W-2", "W-1"],
        "unit_name": ["Farm P1", "Farm P1", "Farm P1", "Farm P2", "Farm P1"],
        "technology": ["Offshore Wind"] * 5,
        "generation_mwh": [10.0, 20.0, 30.0, 40.0, 15.0],
        "payment_gbp": [100.0, 200.0, 50.0, 400.0, -75.0],
        "strike_price_gbp_mwh": [150.0, 151.0, 152.0, 140.0, 153.0],
        "is_renewable": [True] * 5,
    })
    store.write("cfd", "generation", gen, source_url="u", date_col="date")
    hist = pl.DataFrame({"year": [2024], "cost_gbp": [390e6]},
                        schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    annual = pl.DataFrame({"year": [2024], "cost_gbp": [1.0e9]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    refs = {
        "constraints_history": ReferenceScheme(
            "constraints_history", "Wind constraints history",
            ["renewables", "low_carbon"], "annual", "s", "https://s", True, hist),
        "ro": ReferenceScheme("ro", "Renewables Obligation",
                              ["renewables", "low_carbon"], "annual",
                              "s", "https://s", True, annual),
        "fit": ReferenceScheme("fit", "Feed-in Tariffs",
                               ["renewables", "low_carbon"], "annual",
                               "s", "https://s", True, annual),
    }
    model = uk_build.build(store, refs, deflators=deflators(),
                           station_map={"W-1": "Farm", "W-2": "Farm"})
    by_id = {s.scheme_id: s for s in model["schemes"]}
    detail = by_id["cfd_renewable"].extras["station_detail"]

    assert [d["station"] for d in detail] == ["Farm"]
    farm = detail[0]
    # calendar-quarter aggregation across both contracts; the negative 2022-Q1
    # (payback) passes through unclamped
    assert farm["quarters"] == [
        {"q": "2021-Q1", "payment_gbp": 300.0, "generation_mwh": 30.0},
        {"q": "2021-Q4", "payment_gbp": 450.0, "generation_mwh": 70.0},
        {"q": "2022-Q1", "payment_gbp": -75.0, "generation_mwh": 15.0},
    ]
    # per-contract rows: first settlement and the latest strike by date
    c = {r["cfd_id"]: r for r in farm["contracts"]}
    assert c["W-1"]["first_settlement"] == "2021-01-10"
    assert c["W-1"]["latest_strike_gbp_mwh"] == 153.0
    assert c["W-2"]["first_settlement"] == "2021-10-06"
    assert c["W-2"]["latest_strike_gbp_mwh"] == 140.0
    # station totals reconcile with the contract sum
    assert farm["cost"] == 675.0
    assert c["W-1"]["cumulative_gbp"] + c["W-2"]["cumulative_gbp"] == 675.0
    assert farm["generation_mwh"] == 115.0
    assert farm["data_to"] == "2022-01-03"


def test_fy_start_to_calendar_weights_and_first_year():
    """F2 (14 Oct 2026): FY-keyed TNUoS/BSUoS history to calendar years by the engine's rule
    CY(y) = 0.25 FY(y-1) + 0.75 FY(y); the first stored year takes FY(y) alone."""
    fy = pl.DataFrame({"year": [2002, 2003, 2004], "cost_gbp": [100.0, 200.0, 400.0]},
                      schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    cy = {r["year"]: r["cost_gbp"] for r in uk_build.fy_start_to_calendar(fy).to_dicts()}
    assert cy == {2002: 100.0, 2003: 175.0, 2004: 350.0}


def test_tnuos_and_bsuos_history_go_to_calendar_years_in_the_build(tmp_path):
    """The build subtracts the engine's calendar-year no-net-zero cost from a calendar-year
    actual: TNUoS (stored by charging year) and pre-2017 BSUoS history are converted first."""
    from subsidy_engine.store import SnapshotStore
    store = SnapshotStore(tmp_path / "store")
    refs = {
        "constraints_history": _ref("constraints_history", "CH", {2024: 0.0},
                                    perspectives=("renewables", "low_carbon")),
        "ro": _ref("ro", "RO", {2024: 0.0}, perspectives=("renewables", "low_carbon")),
        "fit": _ref("fit", "FIT", {2024: 0.0}, perspectives=("renewables", "low_carbon")),
        "tnuos": _ref("tnuos", "TNUoS", {2022: 800.0, 2023: 1000.0}, conf="low"),
        "bsuos_history": _ref("bsuos_history", "BSUoS hist", {2022: 400.0, 2023: 600.0}, conf="low"),
    }
    cf = cf_series({2022: 0.0, 2023: 0.0, 2024: 0.0, 2025: 0.0})
    model = uk_build.build(store, refs, deflators=deflators(),
                           counterfactual={"tnuos": cf, "bsuos": cf},
                           cm_share={"years": {}, "carry_forward_from": 2025, "provenance": {}})
    by_id = {s.scheme_id: s for s in model["schemes"]}
    tn = {r["year"]: r["cost_gbp"] for r in by_id["tnuos"].annual.to_dicts()}
    assert tn == {2022: 800.0, 2023: 0.25 * 800.0 + 0.75 * 1000.0}
    assert by_id["tnuos"].extras["raw_annual_fy"][1]["cost"] == 1000.0
    bs = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    assert bs[2023] == 0.25 * 400.0 + 0.75 * 600.0


def test_floor_line_total_floors_only_the_whole_period():
    """T2: a negative year stays negative when the line's total is positive; if the total
    (2024 prices) is negative the line counts nothing."""
    pos = pl.DataFrame({"year": [2003, 2023], "cost_gbp": [-39.0, 720.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    out, binds = uk_build.floor_line_total(pos, deflators())
    assert not binds and out["cost_gbp"].to_list() == [-39.0, 720.0]
    neg = pos.with_columns(pl.Series("cost_gbp", [-900.0, 100.0]))
    out, binds = uk_build.floor_line_total(neg, deflators())
    assert binds and out["cost_gbp"].to_list() == [0.0, 0.0]


def test_counterfactual_part_year_pro_rates_only_data_to_year():
    """T11: the no-net-zero cost of the year data_to falls in is scaled by the share of the
    year covered; a 31 Dec data_to leaves it whole."""
    raw = pl.DataFrame({"year": [2025, 2026], "cost_gbp": [500.0, 500.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    cf = cf_series({2025: 365.0})
    out = uk_build.counterfactual_uplift(raw, cf, deflators(), data_to=date(2026, 3, 31))
    rows = {r["year"]: r["cost_gbp"] for r in out.to_dicts()}
    assert abs(rows[2025] - (500.0 - 365.0)) < 1e-9
    assert abs(rows[2026] - (500.0 - 365.0 * 90 / 365)) < 1e-9
    full = uk_build.counterfactual_uplift(raw, cf, deflators(), data_to=date(2026, 12, 31))
    assert abs({r["year"]: r["cost_gbp"] for r in full.to_dicts()}[2026] - 135.0) < 1e-9
    assert uk_build.part_year_fraction(date(2024, 12, 31)) == 1.0


def test_grid_and_balancing_lines_are_called_costs_not_support():
    """T14 (Richard, 14 Oct 2026): the grid and balancing lines are costs of net zero."""
    from pathlib import Path
    from subsidy_engine import reference
    refs = reference.load_annual_costs(Path(__file__).resolve().parents[1] / "reference" / "indirect_annual.yaml")
    assert refs["tnuos"].label == "Extra grid costs of net zero (TNUoS)"
    assert uk_build.BSUOS_LABEL == "Extra balancing costs of net zero (BSUoS)"
    for k in ("tnuos", "bsuos_history"):
        assert "costs of net zero, not payments to generators" in " ".join(refs[k].attribution_rule.split())
