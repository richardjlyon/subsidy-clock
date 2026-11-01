from dataclasses import replace
from datetime import date

import polars as pl

from subsidy_engine_uk import build as uk_build
from subsidy_engine_uk.uplift import road_uplift


def deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, 136.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def indexed_road(value: float, d: pl.DataFrame) -> dict:
    """A test road equal to a flat 2002-05 level carried by the fixture's index (mean of 2002-05 = 71.5),
    so the hand-worked figures below read as before (aios-harness#43 replaced the flat level with the
    engine's per-year road)."""
    idx = dict(zip(d["year"].to_list(), d["index"].to_list()))
    base = sum(idx[y] for y in range(2002, 2006)) / 4
    return {"years": {y: value * i / base for y, i in idx.items()}, "carry_forward_from": max(idx),
            "engine_version": "test", "what": "test road"}


def road(value: float = 100.0) -> dict:
    return {"tnuos": indexed_road(value, deflators()), "bsuos": indexed_road(value, deflators())}


def test_road_uplift_is_signed_and_nets_subtraction():
    raw = pl.DataFrame({"year": [2003, 2023, 2026], "cost_gbp": [60.0, 1000.0, 500.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    constraints = pl.DataFrame({"year": [2023], "cost_gbp": [100.0]},
                               schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    r = {"years": {2003: 99.0, 2023: 179.0, 2025: 190.0}, "carry_forward_from": 2025}
    rows = {x["year"]: x["cost_gbp"] for x in road_uplift(raw, r, deflators(), subtract=constraints).to_dicts()}
    assert rows[2003] == 60.0 - 99.0               # below the road: negative (signed years, as RB)
    assert rows[2023] == 1000.0 - 179.0 - 100.0    # the road for the year, then the netting
    # 2026: after the engine's last year, 2025 carried by the index (no 2026 index: the latest, 136)
    assert rows[2026] == 500.0 - 190.0 * 136.0 / 136.0


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
            True, hist, bottom_up_from=2026),
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
                           road=road())
    by_id = {s.scheme_id: s for s in model["schemes"]}
    # CfD split: renewable vs low-carbon, no leakage
    assert by_id["cfd_renewable"].cumulative_gbp == 5000.0
    assert by_id["cfd_low_carbon"].cumulative_gbp == 7000.0
    assert "renewables" not in by_id["cfd_low_carbon"].perspectives
    # constraints: partial 2026 bottom-up kept (after history's last year 2025)
    con_annual = by_id["constraints"].annual
    assert 600.0 in con_annual.filter(pl.col("year") == 2026)["cost_gbp"].to_list()
    assert by_id["constraints"].cumulative_gbp == 390e6 + 382e6 + 600.0
    assert by_id["constraints"].extras["held_from"] == "2026-04-10"
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
        "constraints_history": replace(
            _ref("constraints_history", "CH", {2024: 200.0},
                 perspectives=("renewables", "low_carbon")), bottom_up_from=2026),
        "ro": _ref("ro", "RO", {2024: 1000.0},
                   perspectives=("renewables", "low_carbon")),
        "fit": _ref("fit", "FIT", {2024: 500.0},
                    perspectives=("renewables", "low_carbon")),
        "ccl": _ref("ccl", "CCL", {2023: 80.0}),
        "tnuos": _ref("tnuos", "TNUoS", {2023: 1000.0}, conf="low"),
        "bsuos_history": replace(_ref("bsuos_history", "BSUoS hist", {2023: 500.0}, conf="low"),
                                 bottom_up_from=2026),
    }
    roads = road()
    # CM: the net-zero share of 2026 carries forward from 2025 (40%)
    cm_share = {"years": {2025: {"cm_paid_gbp": 100.0, "share": 0.4,
                                 "share_low": 0.1, "share_high": 1.0}},
                "carry_forward_from": 2025, "provenance": {}}
    # carbon (aios-harness#44): one line from the engine, total 90 of which 30 tax collected
    carbon = {"years": {2023: {"total": 90.0, "tax_collected": 30.0, "basis": "modelled"}},
              "engine_version": "test", "provenance": "test"}
    model = uk_build.build(store, refs, deflators=deflators(), road=roads,
                           cm_share=cm_share, carbon=carbon)
    by_id = {s.scheme_id: s for s in model["schemes"]}

    # layer assignment
    assert by_id["capacity_market"].layer == "indirect"
    for sid in ("ccl", "carbon", "tnuos", "bsuos"):
        assert by_id[sid].layer == "indirect", sid
    for sid in ("constraints", "ro", "fit"):
        assert by_id[sid].layer == "direct", sid

    # ccl passes through as stored; carbon is the engine's, with its two parts
    assert by_id["ccl"].cumulative_gbp == 80.0
    assert by_id["carbon"].cumulative_gbp == 90.0
    assert by_id["carbon"].extras["parts"][0]["rest_of_carbon_in_price"] == 60.0
    # the old emissions-trading line can never be counted beside it
    import pytest
    with pytest.raises(ValueError, match="carbon is counted once"):
        uk_build.build(store, refs | {"ets": _ref("ets", "ETS", {2023: 90.0})}, deflators=deflators(),
                       road=roads, cm_share=cm_share, carbon=carbon)

    # tnuos: uplift = max(0, 1000 - 100*(128/71.5)) for 2023
    expected_tnuos = 1000.0 - 100.0 * 128.0 / 71.5
    assert abs(by_id["tnuos"].cumulative_gbp - expected_tnuos) < 1e-6

    # bsuos 2023 (history year): max(0, 500 - 100*(128/71.5) - 0 constraints)
    # bsuos 2026 (bottom-up partial year after history): raw 1000,
    #   baseline indexed by latest index (136): 100*136/71.5, constraints 2026 = 100
    bs_annual = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    assert abs(bs_annual[2023] - (500.0 - 100.0 * 128.0 / 71.5)) < 1e-6
    # the road for 2026 is pro-rated to the BSUoS data's 101 days (to 11 Apr; fix of 1 Nov 2026)
    assert abs(bs_annual[2026] - (1000.0 - 100.0 * 136.0 / 71.5 * 101 / 365 - 100.0)) < 1e-6

    # real columns exist everywhere
    for s in model["schemes"]:
        assert "cost_gbp_2024" in s.annual.columns, s.scheme_id

    # indirect total = sum of the five components
    expected_indirect = (50.0 * 0.4 + 80.0 + 90.0 + expected_tnuos
                         + bs_annual[2023] + bs_annual[2026])
    assert abs(model["indirect"]["cumulative_gbp"] - expected_indirect) < 1e-6

    # direct perspectives unchanged by the indirect components (leakage guard)
    refs_direct_only = {k: refs[k] for k in ("constraints_history", "ro", "fit")}
    model2 = uk_build.build(store, refs_direct_only, deflators=deflators(),
                            road=roads, cm_share=cm_share)
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
            ["renewables", "low_carbon"], "annual", "s", "https://s", True, hist,
            bottom_up_from=2026),
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
