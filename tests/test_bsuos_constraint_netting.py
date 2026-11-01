"""BSUoS uplift nets only the constraint payments of days the BSUoS data covers (Grok row 7, card t_b468cbeb; ported in aios-harness#42).

The balancing (BSUoS) uplift is the charge above its indexed 2002-05 baseline, less the wind constraint payments
the Clock already counts as their own line. In an open year the constraints feed (Elexon, daily) usually runs some
days ahead of the BSUoS feed (NESO). Netting the constraints of days BSUoS does not yet cover takes those days'
constraint payments out of a BSUoS total that never contained them, so the uplift is understated. The turn-up line
is already cut to the BSUoS window; the netting must be cut the same way.

Expected values are worked by hand from the fixture below, not read from the code.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import polars as pl

from subsidy_engine_uk import build as uk_build
from tests.test_uk_build import _ref, deflators


def _store(tmp_path):
    from subsidy_engine.store import SnapshotStore

    store = SnapshotStore(tmp_path)
    # constraints: one day inside the BSUoS window (10 Apr) and one day after its end (20 Apr), GBP 100 each
    con = pl.DataFrame({
        "date": [date(2026, 4, 10), date(2026, 4, 20)], "bmu": ["T_W-1", "T_W-1"],
        "lead_party": ["W", "W"], "volume_mwh": [-10.0, -10.0], "cost_gbp": [100.0, 100.0],
    })
    store.write("constraints", "daily", con.filter(pl.col("date") == date(2026, 4, 10)),
                source_url="u", partition="2026-04-10")
    store.write("constraints", "daily", con.filter(pl.col("date") == date(2026, 4, 20)),
                source_url="u", partition="2026-04-20")
    # BSUoS: two days, 10 and 11 Apr 2026, GBP 1,000 together; the feed ends on 11 Apr
    bs = pl.DataFrame({"date": [date(2026, 4, 10), date(2026, 4, 11)], "cost_gbp": [600.0, 400.0]},
                      schema={"date": pl.Date, "cost_gbp": pl.Float64})
    store.write("bsuos", "daily", bs, source_url="u", partition="2026-2027")
    return store


def _refs():
    return {
        "constraints_history": replace(
            _ref("constraints_history", "CH", {2024: 200.0}, perspectives=("renewables", "low_carbon")),
            bottom_up_from=2026),
        "ro": _ref("ro", "RO", {2024: 1000.0}, perspectives=("renewables", "low_carbon")),
        "fit": _ref("fit", "FIT", {2024: 500.0}, perspectives=("renewables", "low_carbon")),
        # the BSUoS pin (aios-harness#37): NESO replaces the history from 2026, the fixture's data year
        "bsuos_history": replace(_ref("bsuos_history", "BSUoS hist", {2023: 500.0}, conf="low"),
                                 bottom_up_from=2026),
    }


def test_bsuos_uplift_nets_only_constraint_days_bsuos_covers(tmp_path):
    model = uk_build.build(_store(tmp_path), _refs(), deflators=deflators(),
                           baselines={"bsuos": {"value": 100.0}, "tnuos": {"value": 100.0}})
    by_id = {s.scheme_id: s for s in model["schemes"]}
    # the constraints line itself still counts both days (GBP 200 in 2026)
    con = {r["year"]: r["cost_gbp"] for r in by_id["constraints"].annual.to_dicts()}
    assert con[2026] == 200.0
    # BSUoS 2026: raw 1,000 less the baseline at the latest index (100 x 136 / 71.5) less the constraints of
    # 10 Apr only (GBP 100). The 20 Apr constraint day is after the BSUoS feed ends and must not be netted.
    bs = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    expected = 1000.0 - 100.0 * 136.0 / 71.5 - 100.0
    assert abs(bs[2026] - expected) < 1e-6, (
        f"BSUoS 2026 uplift {bs[2026]:.4f}, expected {expected:.4f}: constraint days after the BSUoS feed's last "
        f"day were netted off a BSUoS total that does not contain them")


def test_closed_years_unchanged_by_the_cut(tmp_path):
    """A year the BSUoS data covers in full nets every constraint day of that year, as before."""
    model = uk_build.build(_store(tmp_path), _refs(), deflators=deflators(),
                           baselines={"bsuos": {"value": 100.0}, "tnuos": {"value": 100.0}})
    by_id = {s.scheme_id: s for s in model["schemes"]}
    bs = {r["year"]: r["cost_gbp"] for r in by_id["bsuos"].annual.to_dicts()}
    # 2024: no BSUoS figure (history is 2023 only), so no uplift row is invented for it
    assert 2023 in bs and abs(bs[2023] - (500.0 - 100.0 * 128.0 / 71.5)) < 1e-6
