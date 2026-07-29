from datetime import date

import polars as pl
import pytest

from subsidy_engine_uk.schemes import remit
from subsidy_engine_uk.stations import load_station_bmus
from subsidy_engine_uk import build as uk_build


def _msg(mrid, rev, bmu="T_TEST-1", start="2021-06-08T08:00:00Z",
         end="2021-06-10T12:00:00Z", mw=400.0, normal=1000.0, typ="Planned"):
    return {"mrid": mrid, "revisionNumber": rev, "assetId": bmu,
            "unavailabilityType": typ, "eventStartTime": start,
            "eventEndTime": end, "unavailableCapacity": mw,
            "normalCapacity": normal}


def test_parse_messages_collapses_to_latest_revision():
    df = remit.parse_messages([
        _msg("M-1", 1, mw=400.0),
        _msg("M-1", 3, mw=250.0),   # latest revision wins
        _msg("M-1", 2, mw=300.0),
        _msg("M-2", 1, mw=100.0),
    ])
    assert df.height == 2
    m1 = df.filter(pl.col("mrid") == "M-1")
    assert m1["revision"][0] == 3
    assert m1["unavailable_mw"][0] == 250.0


def test_parse_messages_drops_rows_without_event_times():
    df = remit.parse_messages([
        _msg("M-1", 1),
        {"mrid": "M-2", "revisionNumber": 1, "assetId": "T_TEST-1",
         "eventStartTime": None, "eventEndTime": None},
    ])
    assert df["mrid"].to_list() == ["M-1"]


def test_attach_outages_filters_and_stamps_coverage():
    outages = remit.parse_messages([
        # significant: 2+ days, 40% of capacity
        _msg("BIG", 1, start="2021-06-08T08:00:00Z", end="2021-06-10T12:00:00Z",
             mw=400.0, normal=1000.0, typ="Unplanned"),
        # too short (2 hours)
        _msg("SHORT", 1, start="2021-07-01T08:00:00Z", end="2021-07-01T10:00:00Z",
             mw=900.0, normal=1000.0),
        # too small (5% of capacity)
        _msg("SMALL", 1, start="2021-08-01T00:00:00Z", end="2021-08-09T00:00:00Z",
             mw=50.0, normal=1000.0),
    ])
    detail = [{"station": "Mapped Farm"}, {"station": "Unmapped Farm"}]
    uk_build._attach_outages(detail, {"Mapped Farm": ["T_TEST-1"]}, outages)
    o = detail[0]["outages"]
    assert o["coverage_from"] == remit.COVERAGE_FROM.isoformat()
    assert [w["type"] for w in o["windows"]] == ["Unplanned"]
    assert o["windows"][0] == {"start": "2021-06-08", "end": "2021-06-10",
                               "type": "Unplanned", "mw_lost": 400.0}
    # unmapped station untouched -> renders as unavailable, never zero
    assert "outages" not in detail[1]


def test_load_station_bmus_requires_source(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("station,bmu_id,source_url,note\n"
                 "Farm,T_F-1,https://example/register,ok\n"
                 "Farm,T_F-2,,missing\n")
    with pytest.raises(ValueError, match="T_F-2"):
        load_station_bmus(p)


def test_load_station_bmus_groups_by_station(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("station,bmu_id,source_url,note\n"
                 "Farm,T_F-1,https://example/register,\n"
                 "Farm,T_F-2,https://example/register,\n"
                 "Other,T_O-1,https://example/register,\n")
    assert load_station_bmus(p) == {"Farm": ["T_F-1", "T_F-2"],
                                    "Other": ["T_O-1"]}


def test_reference_station_bmu_map_loads():
    bmus = load_station_bmus("reference/station_bmu_map.csv")
    assert bmus["Hornsea 1"] == ["T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3"]
    # CfD Drax is unit 1 only (LCCC register INV-DRX-001)
    assert bmus["Drax"] == ["T_DRAXX-1"]
    # deliberately unmapped: no registered BM unit
    for absent in ("Clocaenog", "Brenig", "Mynydd", "Sneddon", "Moor House",
                   "Nanclach", "Achlachan", "Drax Power Station"):
        assert absent not in bmus
