"""The splice module: which years a scheme's bottom-up series replaces its reference
history for, and the fix 5 guard that refuses an unsafe pin (aios-harness#37).

Tests cross the splice module's interface only: a reference history carrying the pin,
the scheme's daily bottom-up data, and the scheme id. No store, no build."""
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine.reference import ReferenceScheme, load_annual_costs
from subsidy_engine_uk import splice

REF = {2022: 227.2e6, 2023: 310.5e6, 2024: 394.3e6, 2025: 382.1e6}
REFERENCE = Path(__file__).parent.parent / "reference"


def _history(pin, values=REF):
    df = pl.DataFrame({"year": list(values), "cost_gbp": list(values.values())},
                      schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    return ReferenceScheme("h", "h", [], "annual", "s", "https://s", True, df,
                           bottom_up_from=pin)


def _daily(earliest, latest=date(2025, 1, 3), missing=(), per_day=1.0e6):
    days = [earliest + timedelta(days=n) for n in range((latest - earliest).days + 1)]
    days = [d for d in days if d not in missing]
    return pl.DataFrame({"date": days, "cost_gbp": [per_day] * len(days)},
                        schema={"date": pl.Date, "cost_gbp": pl.Float64})


def _con(pin, **kw):
    return splice.splice("constraints", _history(pin), _daily(kw.pop("earliest", date(2023, 8, 25)), **kw))


def _year(annual, y):
    return annual.filter(pl.col("year") == y)["cost_gbp"].item()


# --- which years bottom-up replaces

def test_years_from_the_pin_come_from_bottom_up_and_earlier_years_from_the_history():
    annual, held_from, held_to = _con(2024)
    assert _year(annual, 2023) == REF[2023]          # 2023 partly held: stays on REF
    assert _year(annual, 2024) == 366 * 1.0e6        # 2024 from Elexon
    assert _year(annual, 2022) == REF[2022]
    assert (held_from, held_to) == ("2023-08-25", "2025-01-03")


def test_the_pin_2024_still_holds_2023_on_the_history_once_2023_is_fully_held():
    annual, _, _ = _con(2024, earliest=date(2022, 12, 30))
    assert _year(annual, 2023) == REF[2023]


def test_the_backfill_passing_1_jan_2023_moves_no_year():
    today, _, _ = _con(2024, earliest=date(2023, 8, 25))
    after, _, _ = _con(2024, earliest=date(2022, 12, 30))
    assert today.equals(after)


def test_a_part_year_after_the_history_ends_is_kept():
    hist = _history(2024, {2022: 1.0, 2023: 2.0})
    annual, _, _ = splice.splice("constraints", hist, _daily(date(2023, 1, 1), date(2024, 3, 31)))
    assert _year(annual, 2024) == 91 * 1.0e6


# --- the pin must be a year

def test_a_history_with_no_pin_fails_naming_the_setting():
    with pytest.raises(ValueError, match="constraints history states no bottom_up_from"):
        _con(None)


def test_a_pin_written_as_text_fails_naming_the_value():
    with pytest.raises(ValueError, match=r"bottom_up_from '2024' .*whole-number year"):
        _con("2024")


def test_a_pin_as_a_fraction_or_a_date_fails_naming_the_value():
    # the fact-checker found 2024.5 and the YAML date 2024-01-01 built silently and put
    # 2024 back on REF
    for pin in (2024.5, "2024-01-01", date(2024, 1, 1), True):
        with pytest.raises(ValueError, match=r"bottom_up_from .* whole-number year"):
            _con(pin)


def test_a_pin_of_zero_or_below_fails_naming_the_setting():
    for pin in (-1, 0):
        with pytest.raises(ValueError, match=rf"bottom_up_from {pin} "):
            _con(pin)


# --- the pin must be fully held

def test_a_pin_with_no_held_day_on_or_after_it_fails():
    with pytest.raises(ValueError, match=r"bottom_up_from 2024 .*not every day from 1 Jan 2024"):
        _con(2024, latest=date(2023, 12, 31))


def test_a_pin_only_partly_held_fails_rather_than_swapping_in_a_part_year():
    # data from 25 Aug 2023: 2023 would replace REF's full year with four months of Elexon
    with pytest.raises(ValueError, match=r"bottom_up_from 2023 .*not every day from 1 Jan 2023"):
        _con(2023)


def test_pin_2024_with_a_missing_day_says_to_fetch_it_not_to_raise_the_pin():
    with pytest.raises(ValueError, match=r"bottom_up_from 2024 .*first 2024-06-15.*fetch the "
                                         r"missing days .*do not raise the pin") as err:
        _con(2024, missing={date(2024, 6, 15)})
    assert "partial year" in str(err.value)


# --- the live pin: no year at or after it goes back on the history

def test_a_pin_after_the_live_pin_fails_naming_the_setting():
    # the fact-checker found 2025 and 2026 built silently and put 2024 back on REF
    for pin in (2025, 2026, 2030):
        with pytest.raises(ValueError, match=rf"bottom_up_from {pin} .*later than 2024"):
            _con(pin)


def test_a_raised_pin_fails_when_2024_has_a_missing_day():
    # the fact-checker removed 15 Jun 2024 and pinned 2025: calendar 2024 went back on REF
    with pytest.raises(ValueError, match=r"bottom_up_from 2025 .*later than 2024"):
        _con(2025, missing={date(2024, 6, 15)})


def test_a_pin_after_the_live_pin_builds_when_nothing_from_the_live_pin_is_held():
    # unit fixtures hold one day of 2026 and pin 2026
    hist = _history(2026, {2024: 200.0})
    annual, _, _ = splice.splice("constraints", hist, _daily(date(2026, 4, 10), date(2026, 4, 10)))
    assert _year(annual, 2026) == 1.0e6


# --- BSUoS goes through the same guard

def test_bsuos_holds_a_fully_held_year_before_its_pin_on_the_history():
    # the risk the old "first year held from 1 Jan" rule left open: if Jan-Mar 2016 were
    # ever stored, 2016 would have switched from the history to NESO unannounced
    hist = _history(2017, {2015: 1.0, 2016: 2.0})
    annual, held_from, _ = splice.splice("bsuos", hist, _daily(date(2016, 1, 1), date(2017, 12, 31)))
    assert _year(annual, 2016) == 2.0
    assert _year(annual, 2017) == 365 * 1.0e6
    assert held_from == "2016-01-01"


def test_bsuos_errors_name_its_own_reference_file():
    with pytest.raises(ValueError, match=r"bsuos bottom_up_from '2017'.*indirect_annual.yaml"):
        splice.splice("bsuos", _history("2017"), _daily(date(2016, 4, 1)))


def test_bsuos_pin_after_its_live_pin_fails_while_neso_holds_those_years():
    hist = _history(2018, {2016: 2.0, 2017: 3.0})
    with pytest.raises(ValueError, match=r"bsuos bottom_up_from 2018 .*later than 2017"):
        splice.splice("bsuos", hist, _daily(date(2016, 4, 1), date(2018, 3, 31)))


# --- the live pins move with the reference files

def test_the_live_pins_equal_the_pins_in_the_reference_files():
    # a release that moves a pin must move its live pin too, or a pin raised back later
    # would not be refused
    con = load_annual_costs(REFERENCE / "annual_scheme_costs.yaml")["constraints_history"]
    bs = load_annual_costs(REFERENCE / "indirect_annual.yaml")["bsuos_history"]
    assert splice.LIVE_PIN == {"constraints": con.bottom_up_from, "bsuos": bs.bottom_up_from}
    assert splice.LIVE_PIN == {"constraints": 2024, "bsuos": 2017}
