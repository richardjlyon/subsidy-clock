from datetime import date

import polars as pl

from subsidy_engine import money

DAILY = pl.DataFrame({
    "date": [date(2025, 1, 1), date(2025, 12, 31), date(2026, 6, 1)],
    "cost_gbp": [365.25, 100.0, 200.0],
})


def test_cumulative_and_annual():
    assert money.cumulative(DAILY) == 665.25
    annual = money.annualise_daily(DAILY)
    assert annual.to_dicts() == [
        {"year": 2025, "cost_gbp": 465.25},
        {"year": 2026, "cost_gbp": 200.0},
    ]


def test_trailing_runrate_scales_to_a_year():
    # window ends at the max date; only the last 365 days count
    rate = money.trailing_runrate(DAILY, window_days=365)
    # 2025-12-31 and 2026-06-01 fall in the window; 2025-01-01 does not
    assert rate == (100.0 + 200.0) * (365.25 / 365)


def test_rate_per_second():
    assert money.rate_per_second(31_557_600.0) == 1.0  # £/yr over seconds/yr


def test_merge_history_prefers_bottom_up_years():
    history = pl.DataFrame({"year": [2024, 2025], "cost_gbp": [390e6, 700e6]},
                           schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    bottom_up = pl.DataFrame({"year": [2025, 2026], "cost_gbp": [650e6, 100e6]},
                             schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    merged = money.merge_annual(history, bottom_up)
    assert merged.to_dicts() == [
        {"year": 2024, "cost_gbp": 390e6},
        {"year": 2025, "cost_gbp": 650e6},   # bottom-up wins on overlap
        {"year": 2026, "cost_gbp": 100e6},
    ]


def test_perspective_totals_are_nested():
    schemes = [
        money.SchemeResult(
            scheme_id="a", label="A", perspectives=["renewables", "low_carbon", "all_levy"],
            cadence="daily", annual=pl.DataFrame({"year": [2026], "cost_gbp": [10.0]}),
            cumulative_gbp=10.0, runrate_gbp_per_year=10.0, data_to=date(2026, 6, 1),
        ),
        money.SchemeResult(
            scheme_id="b", label="B", perspectives=["low_carbon", "all_levy"],
            cadence="daily", annual=pl.DataFrame({"year": [2026], "cost_gbp": [5.0]}),
            cumulative_gbp=5.0, runrate_gbp_per_year=5.0, data_to=date(2026, 6, 1),
        ),
        money.SchemeResult(
            scheme_id="c", label="C", perspectives=["all_levy"],
            cadence="monthly", annual=pl.DataFrame({"year": [2026], "cost_gbp": [2.0]}),
            cumulative_gbp=2.0, runrate_gbp_per_year=2.0, data_to=date(2026, 6, 1),
        ),
    ]
    totals = money.perspective_totals(schemes)
    assert totals["renewables"]["cumulative_gbp"] == 10.0
    assert totals["low_carbon"]["cumulative_gbp"] == 15.0
    assert totals["all_levy"]["cumulative_gbp"] == 17.0
    assert totals["renewables"]["runrate_gbp_per_year"] == 10.0


def test_trailing_runrate_short_coverage_not_understated():
    short = pl.DataFrame({
        "date": [date(2026, 4, 3), date(2026, 6, 1)],  # 60 days inclusive
        "cost_gbp": [30.0, 30.0],
    })
    rate = money.trailing_runrate(short, window_days=365)
    assert rate == 60.0 * (365.25 / 60)  # scaled by covered days, not 365


def test_gross_and_net_cfd():
    df = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 1)],
        "payment_gbp": [100.0, -30.0],
    })
    gross, net = money.gross_net(df, "payment_gbp")
    assert (gross, net) == (100.0, 70.0)


def deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, 136.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def test_add_real_restates_to_2024_prices():
    annual = pl.DataFrame({"year": [2002, 2024], "cost_gbp": [70.0, 132.0]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    out = money.add_real(annual, deflators())
    rows = {r["year"]: r["cost_gbp_2024"] for r in out.to_dicts()}
    assert rows[2002] == 132.0   # 70 * 132/70
    assert rows[2024] == 132.0   # unchanged in base year


def test_add_real_uses_latest_index_for_unknown_years():
    annual = pl.DataFrame({"year": [2026], "cost_gbp": [136.0]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    out = money.add_real(annual, deflators())
    assert out.to_dicts()[0]["cost_gbp_2024"] == 132.0  # 136 * 132/136


def test_baseline_uplift_floors_at_zero_and_nets_subtraction():
    raw = pl.DataFrame({"year": [2003, 2023], "cost_gbp": [60.0, 1000.0]},
                       schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    constraints = pl.DataFrame({"year": [2023], "cost_gbp": [100.0]},
                               schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    out = money.baseline_uplift(raw, 100.0, deflators(), subtract=constraints)
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
            ["renewables", "low_carbon", "all_levy"], "annual", "s", "https://s",
            True, hist),
        "ro": ReferenceScheme("ro", "Renewables Obligation",
                              ["renewables", "low_carbon", "all_levy"], "annual",
                              "s", "https://s", True,
                              pl.DataFrame({"year": [2024], "cost_gbp": [7.0e9]},
                                           schema={"year": pl.Int64, "cost_gbp": pl.Float64})),
        "fit": ReferenceScheme("fit", "Feed-in Tariffs",
                               ["renewables", "low_carbon", "all_levy"], "annual",
                               "s", "https://s", True,
                               pl.DataFrame({"year": [2024], "cost_gbp": [1.8e9]},
                                            schema={"year": pl.Int64, "cost_gbp": pl.Float64})),
    }
    model = money.build(store, refs)
    by_id = {s.scheme_id: s for s in model["schemes"]}
    # CfD split: renewable vs low-carbon, no leakage
    assert by_id["cfd_renewable"].cumulative_gbp == 5000.0
    assert by_id["cfd_low_carbon"].cumulative_gbp == 7000.0
    assert "renewables" not in by_id["cfd_low_carbon"].perspectives
    # constraints: partial 2026 bottom-up kept (after history's last year 2025)
    con_annual = by_id["constraints"].annual.to_dicts()
    assert {"year": 2026, "cost_gbp": 600.0} in con_annual
    assert by_id["constraints"].cumulative_gbp == 390e6 + 382e6 + 600.0
    assert by_id["constraints"].extras["bottom_up_from"] == "2026-04-10"
    # perspective nesting: renewables excludes nuclear CfD, all include constraints+ro+fit
    p = model["perspectives"]
    assert p["renewables"]["cumulative_gbp"] == 5000.0 + (390e6 + 382e6 + 600.0) + 7.0e9 + 1.8e9
    assert p["low_carbon"]["cumulative_gbp"] == p["renewables"]["cumulative_gbp"] + 7000.0
    assert p["all_levy"]["cumulative_gbp"] == p["low_carbon"]["cumulative_gbp"]  # no CM data written
