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


def test_perspective_totals_are_nested_and_direct_only():
    schemes = [
        money.SchemeResult(
            scheme_id="a", label="A", perspectives=["renewables", "low_carbon"],
            cadence="daily", annual=pl.DataFrame({"year": [2026], "cost_gbp": [10.0]}),
            cumulative_gbp=10.0, runrate_gbp_per_year=10.0, data_to=date(2026, 6, 1),
        ),
        money.SchemeResult(
            scheme_id="b", label="B", perspectives=["low_carbon"],
            cadence="daily", annual=pl.DataFrame({"year": [2026], "cost_gbp": [5.0]}),
            cumulative_gbp=5.0, runrate_gbp_per_year=5.0, data_to=date(2026, 6, 1),
        ),
        money.SchemeResult(   # indirect scheme must NOT appear in any perspective
            scheme_id="c", label="C", perspectives=[], layer="indirect",
            cadence="monthly", annual=pl.DataFrame({"year": [2026], "cost_gbp": [2.0]}),
            cumulative_gbp=2.0, runrate_gbp_per_year=2.0, data_to=date(2026, 6, 1),
        ),
    ]
    totals = money.perspective_totals(schemes)
    assert set(totals) == {"renewables", "low_carbon"}
    assert totals["renewables"]["cumulative_gbp"] == 10.0
    assert totals["low_carbon"]["cumulative_gbp"] == 15.0
    indirect = money.layer_total(schemes, "indirect")
    assert indirect["cumulative_gbp"] == 2.0


def test_no_indirect_leakage_into_direct_totals():
    direct = money.SchemeResult(
        scheme_id="d", label="D", perspectives=["renewables", "low_carbon"],
        cadence="daily", annual=pl.DataFrame({"year": [2026], "cost_gbp": [7.0]}),
        cumulative_gbp=7.0, runrate_gbp_per_year=7.0, data_to=date(2026, 6, 1),
    )
    indirect = money.SchemeResult(
        scheme_id="i", label="I", perspectives=[], layer="indirect",
        cadence="annual", annual=pl.DataFrame({"year": [2026], "cost_gbp": [99.0]}),
        cumulative_gbp=99.0, runrate_gbp_per_year=99.0, data_to=date(2026, 6, 1),
    )
    with_ind = money.perspective_totals([direct, indirect])
    without = money.perspective_totals([direct])
    # polars DataFrames don't support == for dict equality; compare separately
    for p in with_ind:
        assert {k: v for k, v in with_ind[p].items() if k != "annual"} == \
               {k: v for k, v in without[p].items() if k != "annual"}
        assert with_ind[p]["annual"].equals(without[p]["annual"])


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


def test_annual_to_result_data_to_honours_year_basis():
    import polars as pl
    from datetime import date
    from subsidy_engine import money
    from subsidy_engine.reference import ReferenceScheme

    annual = pl.DataFrame({"year": [2023, 2024], "cost_gbp": [1.0e9, 2.0e9]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})

    def mk(year_basis):
        return ReferenceScheme(
            scheme_id="x", label="X", perspectives=[], cadence="annual",
            source="s", source_url="u", verified=True, annual=annual,
            year_basis=year_basis)

    cal = money.annual_to_result("x", mk("calendar"), layer="indirect")
    assert cal.data_to == date(2024, 12, 31)
    obl = money.annual_to_result("x", mk("obligation_apr"), layer="direct")
    assert obl.data_to == date(2025, 3, 31)
