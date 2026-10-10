import polars as pl
import pytest
from datetime import date

from subsidy_engine_uk import scotland

ZONES = {
    "T_SCOT-1": {"nation": "Scotland", "farm": "Glen"},
    "T_SCOT-2": {"nation": "Scotland", "farm": "Glen"},
    "T_ENG-1": {"nation": "England & Wales", "farm": "Fen"},
}


def _df(rows):
    return pl.DataFrame(rows, schema={"date": pl.Date, "bmu": pl.String,
                                      "cost_gbp": pl.Float64, "volume_mwh": pl.Float64},
                        orient="row")


def _build(df, **kw):
    return scotland.build_payload(df, ZONES, scot_twh=20.0, gb_twh=250.0,
                                  consumption_source="s", consumption_url="u",
                                  generated_at="t", **kw)


def test_splits_by_nation_and_groups_units_into_farms():
    p = _build(_df([(date(2026, 1, 1), "T_SCOT-1", 600.0, -10.0),
                    (date(2026, 1, 1), "T_SCOT-2", 300.0, -5.0),
                    (date(2026, 1, 2), "T_ENG-1", 100.0, -2.0)]))
    assert p["gb_cost"] == 1000.0
    assert p["scotland_cost"] == 900.0
    assert p["scotland_share"] == 0.9
    assert p["scotland_mwh"] == 15
    assert p["farms"] == [{"farm": "Glen", "cost": 900.0, "mwh": 15,
                           "units": ["T_SCOT-1", "T_SCOT-2"]}]
    assert p["who_pays"]["paid_in_scotland"] == pytest.approx(900 * 20 / 250)
    assert p["who_pays"]["paid_in_scotland"] + p["who_pays"]["paid_elsewhere"] == pytest.approx(900)
    assert p["monthly"] == [{"month": "2026-01", "scotland": 900, "rest": 100}]


def test_unplaced_units_fail_the_build():
    with pytest.raises(ValueError, match="build_bmu_zone"):
        _build(_df([(date(2026, 1, 1), "T_SCOT-1", 100.0, -1.0),
                    (date(2026, 1, 1), "T_NEW-1", 50.0, -1.0)]))


def test_turnup_is_windowed_to_the_constraint_record():
    tu = pl.DataFrame({"date": [date(2025, 12, 31), date(2026, 1, 1)], "cost_gbp": [7.0, 3.0]})
    p = _build(_df([(date(2026, 1, 1), "T_SCOT-1", 1.0, -1.0)]), turnup_daily=tu)
    assert p["turnup_same_window"]["cost"] == 3.0


def test_reference_file_places_every_unit_with_a_source():
    from pathlib import Path
    zones = scotland.load_bmu_zones(Path(__file__).parents[1] / "reference" / "bmu_zone.csv")
    assert sum(z["nation"] == "Scotland" for z in zones.values()) > 100
    assert {z["zone"] for z in zones.values() if z["nation"] == "Scotland"} == {"_N", "_P"}
