"""Fix 5 guard, wired into the build (robustness spec, 17 Oct 2026; aios-harness#37).

The guard itself (which years bottom-up replaces, and which pins are refused) is tested
through the splice module's interface in test_splice.py. Here: that build() goes through
it for constraints and BSUoS, and what breakdown.json publishes."""
import json
from dataclasses import replace
from datetime import date, timedelta

import polars as pl
import pytest

from subsidy_engine import sitedata
from subsidy_engine.reference import ReferenceScheme
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk import build as uk_build

REF = {2022: 227.2e6, 2023: 310.5e6, 2024: 394.3e6, 2025: 382.1e6}


def _deflators():
    return pl.DataFrame({"year": [2022, 2023, 2024, 2025], "index": [120.5, 128.6, 132.9, 138.0]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def _annual(sid, values, bottom_up_from=None):
    df = pl.DataFrame({"year": list(values), "cost_gbp": list(values.values())},
                      schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    return ReferenceScheme(sid, sid, ["renewables", "low_carbon"], "annual", "s", "https://s",
                           True, df, bottom_up_from=bottom_up_from)


def _store(path, earliest, latest=date(2025, 1, 3)):
    store = SnapshotStore(path)
    d = earliest
    while d <= latest:
        store.write("constraints", "daily",
                    pl.DataFrame({"date": [d], "bmu": ["T_W-1"], "lead_party": ["W"],
                                  "volume_mwh": [-1.0], "cost_gbp": [1.0e6]}),
                    source_url="u", partition=d.isoformat())
        d += timedelta(days=1)
    return store


def _refs(pin=2024):
    return {"constraints_history": _annual("constraints_history", REF, pin),
            "ro": _annual("ro", {2024: 1.0}), "fit": _annual("fit", {2024: 1.0})}


def _breakdown(model, tmp_path):
    ctx = {k: {"value": v, "source": "s", "source_url": "u", "as_of": 2024} for k, v in
           (("households", 28_400_000), ("population", 68_300_000), ("annual_demand_twh", 266))}
    sitedata.build(model, ctx, {}, tmp_path / "site", generated_at="2026-10-17T00:00:00+00:00")
    return json.loads((tmp_path / "site" / "breakdown.json").read_text())


def test_the_build_refuses_a_partly_held_constraints_pin(tmp_path):
    with pytest.raises(ValueError, match=r"constraints bottom_up_from 2023 .*not every day"):
        uk_build.build(_store(tmp_path, date(2023, 8, 25)), _refs(2023), deflators=_deflators())


def test_the_build_refuses_a_bsuos_history_with_no_pin(tmp_path):
    store = _store(tmp_path, date(2023, 8, 25))
    store.write("bsuos", "daily", pl.DataFrame(
        {"date": [date(2024, 12, 30)], "cost_gbp": [1.0]},
        schema={"date": pl.Date, "cost_gbp": pl.Float64}), source_url="u", partition="2024-2025")
    refs = _refs() | {"bsuos_history": _annual("bsuos_history", {2016: 1.0})}
    with pytest.raises(ValueError, match="bsuos history states no bottom_up_from"):
        uk_build.build(store, refs, deflators=_deflators(), baselines={"bsuos": {"value": 0.1}})


def test_the_pinned_year_and_the_held_window_are_published_in_breakdown_json(tmp_path):
    # the pages say from which year Elexon replaces REF and from which day data is held
    bd = _breakdown(uk_build.build(_store(tmp_path / "store", date(2023, 8, 25)), _refs(),
                                   deflators=_deflators()), tmp_path)
    assert bd["elexon_first_year"] == 2024
    con = next(s for s in bd["schemes"] if s["id"] == "constraints")
    assert (con["held_from"], con["held_to"]) == ("2023-08-25", "2025-01-03")
    assert "bottom_up_from" not in con and "bottom_up_from" not in bd


def test_with_no_elexon_data_the_elexon_year_is_not_published(tmp_path):
    # nothing from Elexon is used then, so publishing 2024 would be false
    bd = _breakdown(uk_build.build(SnapshotStore(tmp_path / "store"), _refs(),
                                   deflators=_deflators()), tmp_path)
    assert "elexon_first_year" not in bd
