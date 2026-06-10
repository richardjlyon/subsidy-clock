import json
from datetime import date

import polars as pl

from subsidy_engine import reconcile


def test_matched_day_overall_divergence():
    bottom_up = pl.DataFrame({"date": [date(2025, 1, 1), date(2025, 1, 15)],
                              "cost_gbp": [1.0e6, 1.0e6]})
    # the 2025-06-01 sentinel pushes the settlement-lag cutoff past January
    official = pl.DataFrame({"date": [date(2025, 1, 1), date(2025, 1, 15), date(2025, 6, 1)],
                             "payment_gbp": [1.01e6, 1.01e6, 5.0e6]})
    report = reconcile.cfd_monthly(bottom_up, official)
    assert report["matched_days"] == 2
    assert report["overall"]["bottom_up_gbp"] == 2.0e6
    assert report["overall"]["official_gbp"] == 2.02e6
    assert abs(report["overall"]["divergence_pct"] - (-0.9901)) < 0.001
    assert report["within_tolerance"] is True  # within the 2% tolerance
    assert report["months"][0]["month"] == "2025-01"
    assert report["months"][0]["days_compared"] == 2


def test_breach_outside_tolerance():
    bottom_up = pl.DataFrame({"date": [date(2025, 1, 1)], "cost_gbp": [5.0e6]})
    official = pl.DataFrame({"date": [date(2025, 1, 1), date(2025, 6, 1)],
                             "payment_gbp": [10.0e6, 1.0]})
    report = reconcile.cfd_monthly(bottom_up, official)
    assert report["within_tolerance"] is False


def test_settlement_lag_window_excluded():
    old, recent = date(2025, 1, 1), date(2025, 3, 1)
    bottom_up = pl.DataFrame({"date": [old, recent], "cost_gbp": [2.0e6, 1.0]})
    official = pl.DataFrame({"date": [old, recent], "payment_gbp": [2.0e6, 9.9e6]})
    report = reconcile.cfd_monthly(bottom_up, official)
    # the recent date is within 45 days of the official max -> excluded
    assert report["matched_days"] == 1
    assert report["excluded_recent_days"] == 1
    assert report["within_tolerance"] is True


def test_zero_official_total_yields_null_pct():
    d = date(2025, 1, 1)
    bottom_up = pl.DataFrame({"date": [d], "cost_gbp": [50.0]})
    official = pl.DataFrame({"date": [d, date(2025, 6, 1)],
                             "payment_gbp": [0.0, 0.0]})
    report = reconcile.cfd_monthly(bottom_up, official)
    assert report["overall"]["divergence_pct"] is None
    assert report["months"][0]["divergence_pct"] is None
    assert report["within_tolerance"] is True
    json.dumps(report, allow_nan=False)  # strict-JSON safe


def test_unmatched_months_are_surfaced():
    bottom_up = pl.DataFrame({"date": [date(2025, 1, 1), date(2025, 2, 1)],
                              "cost_gbp": [1.0, 1.0]})
    official = pl.DataFrame({"date": [date(2025, 2, 1), date(2025, 3, 1)],
                             "payment_gbp": [1.0, 1.0]})
    report = reconcile.cfd_monthly(bottom_up, official)
    assert report["bottom_up_only_months"] == ["2025-01"]
    assert report["official_only_months"] == ["2025-03"]


def test_indirect_crosscheck_divergence_and_notes():
    ours = {"capacity_market": 1.0e9, "ccl": 1.5e9, "ets": 2.0e9,
            "bsuos": 1.0e9, "tnuos": 1.0e9}
    ref = {"year": "2023/2024", "source": "REF Table 2", "source_url": "https://ref",
           "components": {"capacity_market": 1.0e9, "ccl": 2.0e9, "ets": 2.6e9,
                          "bsuos": 2.5e9, "tnuos": 2.7e9},
           "notes": {"bsuos": "we net off direct constraints", "tnuos": "",
                     "ccl": "electricity share only", "ets": "auctioned share only"}}
    out = reconcile.indirect_crosscheck(ours, ref, bound_pct=25.0)
    by = {c["component"]: c for c in out["components"]}
    assert by["capacity_market"]["divergence_pct"] == 0.0
    assert by["bsuos"]["divergence_pct"] == -60.0
    # beyond the bound AND a note exists -> explained, not flagged
    assert by["bsuos"]["explained"] is True
    # beyond the bound with NO note -> flagged for the methodology page
    assert by["tnuos"]["explained"] is False
    assert out["unexplained_count"] == 1


def test_indirect_crosscheck_zero_ref_value_needs_note():
    ref = {"year": "2023/2024", "source": "s", "source_url": "https://s",
           "components": {"ccl": 0.0}, "notes": {}}
    out = reconcile.indirect_crosscheck({"ccl": 1.0e9}, ref)
    assert out["components"][0]["divergence_pct"] is None
    assert out["components"][0]["explained"] is False
    assert out["unexplained_count"] == 1
