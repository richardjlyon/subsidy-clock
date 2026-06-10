from datetime import date

import polars as pl

from subsidy_engine import reconcile


def test_monthly_divergence():
    bottom_up = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 15)],
        "cost_gbp": [100.0, 100.0],
    })
    official = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 15)],
        "payment_gbp": [105.0, 105.0],
    })
    report = reconcile.cfd_monthly(bottom_up, official)
    assert len(report["months"]) == 1
    m = report["months"][0]
    assert m["month"] == "2026-01"
    assert m["bottom_up_gbp"] == 200.0
    assert m["official_gbp"] == 210.0
    assert abs(m["divergence_pct"] - (-4.7619)) < 0.001
    assert report["max_abs_divergence_pct"] < 5.0
    assert report["within_tolerance"] is True


def test_divergence_outside_tolerance_is_flagged():
    bottom_up = pl.DataFrame({"date": [date(2026, 1, 1)], "cost_gbp": [50.0]})
    official = pl.DataFrame({"date": [date(2026, 1, 1)], "payment_gbp": [100.0]})
    report = reconcile.cfd_monthly(bottom_up, official, tolerance_pct=5.0)
    assert report["within_tolerance"] is False
