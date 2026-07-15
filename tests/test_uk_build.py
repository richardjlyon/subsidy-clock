from datetime import date

import polars as pl

from subsidy_engine_uk import build as uk_build


def deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, 136.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def test_baseline_uplift_floors_at_zero_and_nets_subtraction():
    raw = pl.DataFrame({"year": [2003, 2023], "cost_gbp": [60.0, 1000.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    constraints = pl.DataFrame({"year": [2023], "cost_gbp": [100.0]},
                               schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    out = uk_build.baseline_uplift(raw, 100.0, deflators(), subtract=constraints)
    rows = {r["year"]: r["cost_gbp"] for r in out.to_dicts()}
    # baseline index = mean(70,71,72,73) = 71.5
    # 2003: 60 - 100*(71/71.5) = negative -> floored to 0
    assert rows[2003] == 0.0
    # 2023: 1000 - 100*(128/71.5) - 100 = 1000 - 179.02... - 100
    assert abs(rows[2023] - (1000.0 - 100.0 * 128.0 / 71.5 - 100.0)) < 1e-9


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
    model = uk_build.build(store, refs, deflators=deflators(),
                           baselines={"bsuos": {"value": 100.0}, "tnuos": {"value": 100.0}})
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
    baselines = {"bsuos": {"value": 100.0}, "tnuos": {"value": 100.0}}
    model = uk_build.build(store, refs, deflators=deflators(), baselines=baselines)
    by_id = {s.scheme_id: s for s in model["schemes"]}

    # layer assignment
    assert by_id["capacity_market"].layer == "indirect"
    for sid in ("ccl", "ets", "tnuos", "bsuos"):
        assert by_id[sid].layer == "indirect", sid
    for sid in ("constraints", "ro", "fit"):
        assert by_id[sid].layer == "direct", sid

    # ccl/ets pass through as stored
    assert by_id["ccl"].cumulative_gbp == 80.0

    # tnuos: uplift = max(0, 1000 - 100*(128/71.5)) for 2023
    expected_tnuos = 1000.0 - 100.0 * 128.0 / 71.5
    assert abs(by_id["tnuos"].cumulative_gbp - expected_tnuos) < 1e-6

    # bsuos 2023 (history year): max(0, 500 - 100*(128/71.5) - 0 constraints)
    # bsuos 2026 (bottom-up partial year after history): raw 1000,
    #   baseline indexed by latest index (136): 100*136/71.5, constraints 2026 = 100
    bs_annual = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    assert abs(bs_annual[2023] - (500.0 - 100.0 * 128.0 / 71.5)) < 1e-6
    assert abs(bs_annual[2026] - (1000.0 - 100.0 * 136.0 / 71.5 - 100.0)) < 1e-6

    # real columns exist everywhere
    for s in model["schemes"]:
        assert "cost_gbp_2024" in s.annual.columns, s.scheme_id

    # indirect total = sum of the five components
    expected_indirect = (50.0 + 80.0 + 90.0 + expected_tnuos
                         + bs_annual[2023] + bs_annual[2026])
    assert abs(model["indirect"]["cumulative_gbp"] - expected_indirect) < 1e-6

    # direct perspectives unchanged by the indirect components (leakage guard)
    refs_direct_only = {k: refs[k] for k in ("constraints_history", "ro", "fit")}
    model2 = uk_build.build(store, refs_direct_only, deflators=deflators(),
                            baselines=baselines)
    assert (model["perspectives"]["renewables"]["cumulative_gbp"]
            == model2["perspectives"]["renewables"]["cumulative_gbp"])
