from datetime import date

import polars as pl

from subsidy_engine import reconcile


def test_monthly_divergence():
    bottom_up = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 15)],
        "cost_gbp": [1_000_000.0, 1_000_000.0],
    })
    official = pl.DataFrame({
        "date": [date(2026, 1, 1), date(2026, 1, 15)],
        "payment_gbp": [1_050_000.0, 1_050_000.0],
    })
    report = reconcile.cfd_monthly(bottom_up, official)
    assert len(report["months"]) == 1
    m = report["months"][0]
    assert m["month"] == "2026-01"
    assert m["bottom_up_gbp"] == 2_000_000.0
    assert m["official_gbp"] == 2_100_000.0
    assert abs(m["divergence_pct"] - (-4.7619)) < 0.001
    assert m["abs_divergence_gbp"] == -100_000.0
    assert report["max_abs_divergence_pct"] < 5.0
    assert report["within_tolerance"] is True


def test_divergence_outside_tolerance_is_flagged():
    bottom_up = pl.DataFrame({"date": [date(2026, 1, 1)], "cost_gbp": [500_000.0]})
    official = pl.DataFrame({"date": [date(2026, 1, 1)], "payment_gbp": [1_000_000.0]})
    report = reconcile.cfd_monthly(bottom_up, official, tolerance_pct=5.0)
    assert report["within_tolerance"] is False


def test_zero_official_month_does_not_blow_up():
    bottom_up = pl.DataFrame({"date": [date(2026, 1, 1)], "cost_gbp": [50.0]})
    official = pl.DataFrame({"date": [date(2026, 1, 1)], "payment_gbp": [0.0]})
    report = reconcile.cfd_monthly(bottom_up, official)
    m = report["months"][0]
    assert m["divergence_pct"] is None
    assert m["abs_divergence_gbp"] == 50.0
    assert report["within_tolerance"] is True  # no comparable months -> no breach
    import json
    json.dumps(report, allow_nan=False)  # must be strict-JSON safe


def test_unmatched_months_are_surfaced():
    bottom_up = pl.DataFrame({"date": [date(2026, 1, 1), date(2026, 2, 1)],
                              "cost_gbp": [50.0, 60.0]})
    official = pl.DataFrame({"date": [date(2026, 2, 1), date(2026, 3, 1)],
                             "payment_gbp": [60.0, 70.0]})
    report = reconcile.cfd_monthly(bottom_up, official)
    assert report["bottom_up_only_months"] == ["2026-01"]
    assert report["official_only_months"] == ["2026-03"]
    assert [m["month"] for m in report["months"]] == ["2026-02"]
