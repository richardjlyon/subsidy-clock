"""Fix 5 guard (robustness spec, 17 Oct 2026): the split between the constraints and
balancing lines must not move before the single release Richard approves.

Today the build trusts Elexon bottom-up constraints for every year from the first one the
backfill covers from 1 January. The daily backfill steps back a week at a time and passes
1 Jan 2023 on 20 Nov 2026 at the latest; 2023 would then switch from REF (GBP 310.5m) to
Elexon with no changelog entry. Balancing is counted net of constraints, so the headline
would not move; the split between the two lines would. The guard states the first Elexon year (2024, today's split) in the
reference file, so the backfill reaching further back changes nothing."""
from datetime import date, timedelta

import polars as pl

from subsidy_engine.money import add_real
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
    extra = {"bottom_up_from": bottom_up_from} if bottom_up_from is not None else {}
    return ReferenceScheme(sid, sid, ["renewables", "low_carbon"], "annual", "s", "https://s",
                           True, df, **extra)


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


def _figures(store, refs):
    model = uk_build.build(store, refs, deflators=_deflators())
    # every line, 2002 to 31 Dec 2024, in 2024 prices. This fixture has no BSUoS line, so
    # it measures the constraints line alone; on the real build the balancing line is net
    # of constraints and the live (master) end-2024 figure does not move either way
    end_2024 = sum(float(add_real(s.annual, _deflators())
                         .filter(pl.col("year") <= 2024)["cost_gbp_2024"].sum())
                   for s in model["schemes"])
    p = model["perspectives"]["renewables"]
    # the renewables perspective's running base and rate (constraints is in it)
    running = (p.get("cumulative_gbp_2024"), p.get("runrate_gbp_per_year_2024"),
               p["cumulative_gbp"], p["runrate_gbp_per_year"])
    return end_2024, running


def _refs():
    from dataclasses import replace
    from pathlib import Path
    from subsidy_engine.reference import load_annual_costs
    live = load_annual_costs(Path(__file__).parent.parent / "reference"
                             / "annual_scheme_costs.yaml")["constraints_history"]
    # the fixture's REF figures, the live file's switch
    hist = replace(_annual("constraints_history", REF), bottom_up_from=live.bottom_up_from)
    return {"constraints_history": hist, "ro": _annual("ro", {2024: 1.0}),
            "fit": _annual("fit", {2024: 1.0})}


def test_constraints_line_to_end_2024_and_its_running_base_do_not_move_when_the_backfill_passes_1_jan_2023(
        tmp_path):
    today = _figures(_store(tmp_path / "today", date(2023, 8, 25)), _refs())
    after = _figures(_store(tmp_path / "after", date(2022, 12, 30)), _refs())
    assert after == today


def test_a_constraints_history_with_no_stated_first_elexon_year_fails_the_build(tmp_path):
    import pytest
    refs = {"constraints_history": _annual("constraints_history", REF),
            "ro": _annual("ro", {2024: 1.0}), "fit": _annual("fit", {2024: 1.0})}
    with pytest.raises(ValueError, match="bottom_up_from"):
        uk_build.build(_store(tmp_path, date(2024, 12, 30)), refs, deflators=_deflators())


def test_the_live_reference_states_2024_todays_split():
    from pathlib import Path
    from subsidy_engine.reference import load_annual_costs
    h = load_annual_costs(Path(__file__).parent.parent / "reference"
                          / "annual_scheme_costs.yaml")["constraints_history"]
    assert h.bottom_up_from == 2024


def _build_with(tmp_path, pin, earliest=date(2023, 8, 25), latest=date(2025, 1, 3)):
    from dataclasses import replace
    refs = _refs()
    refs["constraints_history"] = replace(refs["constraints_history"], bottom_up_from=pin)
    return uk_build.build(_store(tmp_path, earliest, latest), refs, deflators=_deflators())


def test_a_switch_year_written_as_text_fails_naming_the_value(tmp_path):
    import pytest
    with pytest.raises(ValueError, match=r"bottom_up_from '2024' .*whole-number year"):
        _build_with(tmp_path, "2024")


def test_a_switch_year_as_a_fraction_or_a_date_fails_naming_the_value(tmp_path):
    # the fact-checker found 2024.5 and the YAML date 2024-01-01 built silently and put
    # 2024 back on REF
    import pytest
    for i, pin in enumerate((2024.5, "2024-01-01", date(2024, 1, 1))):
        with pytest.raises(ValueError, match=r"bottom_up_from .*2024.* whole-number year"):
            _build_with(tmp_path / str(i), pin)


def test_a_switch_year_with_no_stored_days_fails(tmp_path):
    # (2030 was this test's first value; it now fails earlier, on the first-full-year limit)
    import pytest
    with pytest.raises(ValueError, match=r"bottom_up_from 2024 .*not every day from 1 Jan 2024"):
        _build_with(tmp_path, 2024, latest=date(2023, 12, 31))


def test_a_switch_year_only_partly_held_fails_rather_than_swapping_in_a_part_year(tmp_path):
    # today's data start on 25 Aug 2023: 2023 would replace REF's full year with
    # four months of Elexon (GBP 167.3m on the real data)
    import pytest
    with pytest.raises(ValueError, match=r"bottom_up_from 2023 .*not every day from 1 Jan 2023"):
        _build_with(tmp_path, 2023)


def test_the_pin_2024_still_builds_once_2023_is_fully_held_too(tmp_path):
    model = _build_with(tmp_path, 2024, earliest=date(2022, 12, 30))
    con = next(s for s in model["schemes"] if s.scheme_id == "constraints")
    assert con.annual.filter(pl.col("year") == 2023)["cost_gbp"].item() == REF[2023]


def test_the_pinned_year_is_published_in_breakdown_json(tmp_path):
    # the pages say from which year Elexon replaces REF; they read it from here
    import json
    from subsidy_engine import sitedata
    model = _build_with(tmp_path / "store", 2024)
    ctx = {k: {"value": v, "source": "s", "source_url": "u", "as_of": 2024} for k, v in
           (("households", 28_400_000), ("population", 68_300_000), ("annual_demand_twh", 266))}
    sitedata.build(model, ctx, {}, tmp_path / "site", generated_at="2026-10-17T00:00:00+00:00")
    bd = json.loads((tmp_path / "site" / "breakdown.json").read_text())
    # named so it cannot be confused with each scheme's bottom_up_from (earliest stored day)
    assert bd["elexon_first_year"] == 2024
    assert "bottom_up_from" not in bd


def test_a_switch_year_after_the_first_full_elexon_year_fails_naming_the_setting(tmp_path):
    # the fact-checker found 2025 and 2026 built silently and put 2024 back on REF
    import pytest
    for pin in (2025, 2026, 2030):
        with pytest.raises(ValueError, match=rf"bottom_up_from {pin} .*later than 2024"):
            _build_with(tmp_path / str(pin), pin)


def test_a_switch_year_of_zero_or_below_fails_naming_the_setting(tmp_path):
    import pytest
    for pin in (-1, 0):
        with pytest.raises(ValueError, match=rf"bottom_up_from {pin} "):
            _build_with(tmp_path / str(pin), pin)
