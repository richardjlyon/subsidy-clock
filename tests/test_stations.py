from subsidy_engine.stations import (
    group_by_station,
    load_ro_stations,
    load_station_coords,
    load_station_map,
)


def test_load_station_coords_reads_station_to_latlon_floats(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,lat,lon,source_url\n"
        "Hornsea 1,53.8800,1.6800,https://example/hornsea\n"
        "Drax,53.7380,-0.9998,https://example/drax\n"
    )

    coords = load_station_coords(csv)

    assert coords == {
        "Hornsea 1": (53.88, 1.68),
        "Drax": (53.738, -0.9998),
    }


def test_load_station_coords_skips_blank_and_not_found_rows(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,lat,lon,source_url\n"
        "Hornsea 1,53.8800,1.6800,https://example/hornsea\n"
        "Mystery Farm,,,\n"
        "Unlocatable,NOT FOUND,NOT FOUND,\n"
    )

    coords = load_station_coords(csv)

    assert coords == {"Hornsea 1": (53.88, 1.68)}


def test_load_ro_stations_reads_named_stations_with_buyout_value(tmp_path):
    csv = tmp_path / "ro.csv"
    csv.write_text(
        "station,technology,buyout_gbp\n"
        "Drax Power Station,Biomass,6480000000\n"
        "London Array Offshore Windfarm,Offshore Wind,2920000000\n"
    )

    rows = load_ro_stations(csv)

    assert rows == [
        {"station": "Drax Power Station", "technology": "Biomass", "cost_gbp": 6480000000.0},
        {"station": "London Array Offshore Windfarm", "technology": "Offshore Wind",
         "cost_gbp": 2920000000.0},
    ]


def test_load_station_map_reads_cfd_id_to_station(tmp_path):
    csv = tmp_path / "m.csv"
    csv.write_text(
        "cfd_id,station,unit_name\n"
        "INV-WAL-001,Walney Ext,Walney Extension Phase 1\n"
        "INV-WAL-002,Walney Ext,Walney Extension Phase 2\n"
    )

    m = load_station_map(csv)

    assert m == {"INV-WAL-001": "Walney Ext", "INV-WAL-002": "Walney Ext"}


def test_groups_phased_contracts_into_one_station():
    # Walney Extension Phase 1 and Phase 2 are two CfD contracts, one wind farm.
    # Keyed on cfd_id, not name (names differ by phase; ids are exact).
    recipients = [
        {"cfd_id": "WAL-001", "unit_name": "Walney Extension Offshore Wind Farm Phase 1",
         "technology": "Offshore Wind", "cost_gbp": 300.0},
        {"cfd_id": "WAL-002", "unit_name": "Walney Extension Offshore Wind Farm Phase 2",
         "technology": "Offshore Wind", "cost_gbp": 200.0},
    ]
    station_map = {"WAL-001": "Walney Extension", "WAL-002": "Walney Extension"}

    rows = group_by_station(recipients, station_map)

    assert len(rows) == 1
    row = rows[0]
    assert row["station"] == "Walney Extension"
    assert row["technology"] == "Offshore Wind"
    assert row["cost_gbp"] == 500.0
    # the per-contract phases are preserved, sorted by cost descending
    assert [c["unit_name"] for c in row["contracts"]] == [
        "Walney Extension Offshore Wind Farm Phase 1",
        "Walney Extension Offshore Wind Farm Phase 2",
    ]


def test_unmapped_unit_falls_back_to_its_own_name():
    # cfd_id absent from the map -> the contract stands alone under its unit name.
    recipients = [{"cfd_id": "HOR-XX", "unit_name": "Hornsea Project Two",
                   "technology": "Offshore Wind", "cost_gbp": 100.0}]

    rows = group_by_station(recipients, station_map={})

    assert rows[0]["station"] == "Hornsea Project Two"
    assert [c["unit_name"] for c in rows[0]["contracts"]] == ["Hornsea Project Two"]


def test_stations_sorted_by_total_cost_descending():
    recipients = [
        {"cfd_id": "S-1", "unit_name": "Small A", "technology": "Onshore Wind",
         "cost_gbp": 50.0},
        {"cfd_id": "B-1", "unit_name": "Big P1", "technology": "Offshore Wind",
         "cost_gbp": 300.0},
        {"cfd_id": "B-2", "unit_name": "Big P2", "technology": "Offshore Wind",
         "cost_gbp": 300.0},
    ]
    station_map = {"B-1": "Big", "B-2": "Big"}

    rows = group_by_station(recipients, station_map)

    # Big (600) outranks Small A (50) even though each Big contract alone ties it
    assert [r["station"] for r in rows] == ["Big", "Small A"]


def test_mixed_technology_station_labelled_mixed():
    recipients = [
        {"cfd_id": "C-1", "unit_name": "Combo Wind", "technology": "Offshore Wind",
         "cost_gbp": 10.0},
        {"cfd_id": "C-2", "unit_name": "Combo Solar", "technology": "Solar PV",
         "cost_gbp": 10.0},
    ]
    station_map = {"C-1": "Combo", "C-2": "Combo"}

    rows = group_by_station(recipients, station_map)

    assert rows[0]["technology"] == "Mixed"
