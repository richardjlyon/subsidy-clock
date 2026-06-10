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


def test_gross_and_net_cfd():
    df = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 1)],
        "payment_gbp": [100.0, -30.0],
    })
    gross, net = money.gross_net(df, "payment_gbp")
    assert (gross, net) == (100.0, 70.0)
