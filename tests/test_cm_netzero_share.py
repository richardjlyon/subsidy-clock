"""Capacity Market: only the part net zero caused is counted (change of
13 October 2026). Pins the per-year share, the carry-forward of the last
modelled year, that the headline is the sum of its parts, and that the
public change-log entry for the change validates."""
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import reference, sitedata
from subsidy_engine_uk import build as uk_build

REF = Path("reference/capacity_market_netzero_share.yaml")


def deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, 136.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def _ref(scheme_id):
    from subsidy_engine.reference import ReferenceScheme
    annual = pl.DataFrame({"year": [2024], "cost_gbp": [1.0]},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    return ReferenceScheme(scheme_id, scheme_id, ["renewables", "low_carbon"], "annual",
                           "s", "https://s", True, annual, attribution_rule="r",
                           attribution_confidence="medium")


def _share_table(rows: dict[int, tuple[float, float, float, float]], carry: int) -> dict:
    """rows: year -> (cm_paid, netzero, low, high)."""
    years = {}
    for y, (paid, nz, lo, hi) in rows.items():
        years[y] = {"cm_paid_gbp": paid, "netzero_gbp": nz,
                    "netzero_low_gbp": lo, "netzero_high_gbp": hi,
                    "share": nz / paid, "share_low": lo / paid, "share_high": hi / paid}
    return {"years": years, "carry_forward_from": carry, "provenance": {}}


def _build_cm(tmp_path, payments: dict[date, float], cm_share):
    from subsidy_engine.store import SnapshotStore
    store = SnapshotStore(tmp_path)
    cm = pl.DataFrame({"date": list(payments), "auction": ["T-4"] * len(payments),
                       "payment_gbp": list(payments.values())},
                      schema={"date": pl.Date, "auction": pl.String, "payment_gbp": pl.Float64})
    store.write("capacity_market", "payments", cm, source_url="u", date_col="date")
    refs = {k: _ref(k) for k in ("constraints_history", "ro", "fit")}
    model = uk_build.build(store, refs, deflators=deflators(), baselines={},
                           cm_share=cm_share)
    return model, {s.scheme_id: s for s in model["schemes"]}["capacity_market"]


def test_per_year_share_applied_to_each_month(tmp_path):
    share = _share_table({2024: (300.0, 75.0, 30.0, 300.0),     # 25%
                          2025: (200.0, 100.0, 20.0, 200.0)},   # 50%
                         carry=2025)
    _, cm = _build_cm(tmp_path, {date(2024, 1, 1): 100.0, date(2024, 6, 1): 200.0,
                                 date(2025, 3, 1): 120.0, date(2025, 9, 1): 80.0}, share)
    annual = {r["year"]: r["cost_gbp"] for r in cm.annual.to_dicts()}
    assert annual == pytest.approx({2024: 75.0, 2025: 100.0})
    assert cm.cumulative_gbp == pytest.approx(175.0)
    assert cm.attribution_pct == pytest.approx(175.0 / 500.0)
    # the raw levy is still published beside the counted part
    assert {r["year"]: r["cost"] for r in cm.extras["raw_annual"]} == {2024: 300.0, 2025: 200.0}
    # the range: low and high are the same rule with the low/high shares
    assert cm.extras["range"]["low"]["cumulative"] == pytest.approx(30.0 + 20.0)
    assert cm.extras["range"]["high"]["cumulative"] == pytest.approx(500.0)
    # run-rate is the 12 months to the latest month (Oct 2024-Sep 2025) of
    # the COUNTED series: only the two 2025 months, at the 2025 share
    assert cm.runrate_gbp_per_year == pytest.approx(0.5 * (120.0 + 80.0))


def test_years_after_the_model_carry_the_last_share_forward(tmp_path):
    share = _share_table({2025: (200.0, 50.0, 10.0, 200.0)}, carry=2025)    # 25%
    _, cm = _build_cm(tmp_path, {date(2025, 1, 1): 200.0, date(2026, 1, 1): 40.0,
                                 date(2027, 1, 1): 60.0}, share)
    annual = {r["year"]: r["cost_gbp"] for r in cm.annual.to_dicts()}
    assert annual[2026] == pytest.approx(10.0)
    assert annual[2027] == pytest.approx(15.0)
    basis = {r["year"]: r["basis"] for r in cm.extras["netzero_share"]}
    assert basis == {2025: "modelled", 2026: "carried forward from 2025",
                     2027: "carried forward from 2025"}


def test_a_stale_share_fails_the_build(tmp_path):
    """The share was computed against the engine's CM total; if LCCC restates
    the year by more than 2% the share no longer applies."""
    share = _share_table({2025: (200.0, 50.0, 10.0, 200.0)}, carry=2025)
    with pytest.raises(ValueError, match="rerun the gas-counterfactual engine"):
        _build_cm(tmp_path, {date(2025, 1, 1): 210.0}, share)


def test_a_year_before_the_model_is_an_error_not_full_levy(tmp_path):
    share = _share_table({2025: (200.0, 50.0, 10.0, 200.0)}, carry=2025)
    with pytest.raises(ValueError, match="no net-zero share"):
        _build_cm(tmp_path, {date(2024, 1, 1): 10.0, date(2025, 1, 1): 200.0}, share)


def test_cm_data_without_a_share_table_fails_rather_than_counting_in_full(tmp_path):
    with pytest.raises(ValueError, match="net-zero share"):
        _build_cm(tmp_path, {date(2025, 1, 1): 200.0}, None)


# ---- the committed reference file and the published data ----

def test_reference_file_shares_match_the_engine_and_2025_carries():
    cm = reference.load_cm_netzero_share(REF)
    assert sorted(cm["years"]) == list(range(2016, 2026))
    assert cm["carry_forward_from"] == 2025
    y25 = cm["years"][2025]
    # Richard's decision: 2026 onward uses 396.33 / 1431.46
    assert y25["share"] == pytest.approx(396.333094 / 1431.463285, rel=1e-6)
    assert cm["provenance"]["commit"].startswith("e0bfd73")
    for y, r in cm["years"].items():
        assert 0.0 <= r["share_low"] <= r["share"] <= r["share_high"] == pytest.approx(1.0), y
    assert all(cm["years"][y]["share"] < 0.5 for y in range(2017, 2026))


def test_reference_file_rejects_an_impossible_share(tmp_path):
    p = tmp_path / "cm.yaml"
    p.write_text("carry_forward_from: 2025\nyears:\n  2025: {cm_paid_gbp: 100, netzero_gbp: 120, "
                 "netzero_low_gbp: 10, netzero_high_gbp: 100}\n")
    with pytest.raises(ValueError, match="shares must satisfy"):
        reference.load_cm_netzero_share(p)


def _published():
    import json
    d = Path("site/data")
    return (json.loads((d / "breakdown.json").read_text()),
            json.loads((d / "totals.json").read_text()),
            json.loads((d / "timeseries.json").read_text()),
            json.loads((d / "meta.json").read_text()))


def test_published_cm_line_is_the_netzero_share_not_the_full_levy():
    bd, _, ts, _ = _published()
    cm = next(s for s in bd["schemes"] if s["id"] == "capacity_market")
    ref = reference.load_cm_netzero_share(REF)
    raw = {r["year"]: r["cost"] for r in cm["raw_annual"]}
    counted = {r["year"]: r["cost"] for r in ts["schemes"]["capacity_market"]["annual"]}
    assert raw.keys() == counted.keys()
    for y, paid in raw.items():
        s = ref["years"].get(y, ref["years"][ref["carry_forward_from"]])["share"]
        assert counted[y] == pytest.approx(paid * s, rel=1e-9), y
    assert cm["cumulative"] < 0.5 * sum(raw.values())   # not the full levy
    assert "counted in full" not in cm["attribution_note"]


def test_headline_equals_the_sum_of_its_parts():
    bd, totals, ts, meta = _published()
    direct = totals["perspectives"]["renewables"]
    ind = totals["indirect"]
    indirect_parts = [s for s in bd["schemes"] if s["layer"] == "indirect"]
    assert sum(s["cumulative"] for s in indirect_parts) == pytest.approx(ind["cumulative"], rel=1e-9)
    real_parts = sum(a["cost_real"] for s in indirect_parts
                     for a in ts["schemes"][s["id"]]["annual"])
    assert real_parts == pytest.approx(ind["real"]["cumulative"], rel=1e-9)
    assert meta["headline"]["combined_real"] == pytest.approx(
        direct["real"]["cumulative"] + ind["real"]["cumulative"], rel=1e-12)


def test_changelog_entry_for_the_cm_change_validates():
    entries = sitedata.load_changelog("changelog.jsonl")
    cm = [e for e in entries if e["figure"] == "capacity_market" and e["date"] == "2026-10-13"]
    assert len(cm) == 1
    e = cm[0]
    assert e["kind"] == "change"          # a deliberate method change, not a correction
    assert e["credit"] == "Richard Lyon"
    assert len(e["cause"]) >= 3
    text = " ".join(e["cause"]).lower()
    for must in ("floor", "2025 share", "backup", "not yet published"):
        assert must in text, must
