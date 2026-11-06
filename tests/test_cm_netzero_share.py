"""Capacity Market: only the part net zero caused is counted (change of
13 October 2026). Pins that the published line is the net-zero share, that the
headline is the sum of its parts, and that the public change-log entry for the
change validates. (The share itself is tested in model-bill-already-paid,
aios-harness#140.)"""
from pathlib import Path

import pytest

from clocksite import sitedata


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
    # the shares published beside the line (site/data is rebuilt only at release, so the committed
    # build may carry an older engine's shares than the pin; the pin is tested in test_cost_register_0168)
    shares = {r["year"]: r["share"] for r in cm["netzero_share"]}
    raw = {r["year"]: r["cost"] for r in cm["raw_annual"]}
    counted = {r["year"]: r["cost"] for r in ts["schemes"]["capacity_market"]["annual"]}
    assert raw.keys() == counted.keys() == shares.keys()
    for y, paid in raw.items():
        assert counted[y] == pytest.approx(paid * shares[y], rel=1e-9), y
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
