"""The map's inputs: station coordinates and enforcement notes (moved from the model's stations
tests with their loaders, aios-harness#140)."""
import pytest

from clocksite.inputs import load_enforcement_notes, load_station_coords


def test_load_station_coords_reads_station_to_latlon_slug(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,slug,lat,lon,source_url\n"
        "Hornsea 1,hornsea-1,53.8800,1.6800,https://example/hornsea\n"
        "Drax,drax,53.7380,-0.9998,https://example/drax\n"
    )

    coords = load_station_coords(csv)

    assert coords == {
        "Hornsea 1": (53.88, 1.68, "hornsea-1"),
        "Drax": (53.738, -0.9998, "drax"),
    }


def test_load_station_coords_skips_blank_and_not_found_rows(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,slug,lat,lon,source_url\n"
        "Hornsea 1,hornsea-1,53.8800,1.6800,https://example/hornsea\n"
        "Mystery Farm,,,,\n"
        "Unlocatable,,NOT FOUND,NOT FOUND,\n"
    )

    coords = load_station_coords(csv)

    assert coords == {"Hornsea 1": (53.88, 1.68, "hornsea-1")}


def test_load_station_coords_fails_on_located_row_without_slug(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,slug,lat,lon,source_url\n"
        "Hornsea 1,,53.8800,1.6800,https://example/hornsea\n"
    )

    with pytest.raises(ValueError, match="Hornsea 1"):
        load_station_coords(csv)


def test_load_station_coords_fails_on_duplicate_slug(tmp_path):
    csv = tmp_path / "coords.csv"
    csv.write_text(
        "station,slug,lat,lon,source_url\n"
        "Hornsea 1,hornsea-1,53.8800,1.6800,https://example/hornsea\n"
        "Hornsea 2,hornsea-1,53.9000,1.7900,https://example/hornsea2\n"
    )

    with pytest.raises(ValueError, match="hornsea-1"):
        load_station_coords(csv)


def test_load_enforcement_notes_rejects_unofficial_domain(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text('station,date,text,source_url\n'
                 'Farm,2024-08-29,Text.,https://example.com/blog\n')
    with pytest.raises(ValueError, match="allowlist"):
        load_enforcement_notes(p)


def test_load_enforcement_notes_empty_file_is_valid(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text("station,date,text,source_url\n")
    assert load_enforcement_notes(p) == {}


def test_reference_enforcement_notes_load_and_cite_ofgem():
    notes = load_enforcement_notes("reference/enforcement_notes.csv")
    n = notes["Drax Power Station"]
    assert n["source_url"].startswith("https://www.ofgem.gov.uk/")
    # the note must carry Ofgem's balancing findings, not just the redress
    assert "no evidence that ROCs were issued incorrectly" in n["text"]
    assert "would not have affected the level of subsidy" in n["text"]
    assert "£25m" in n["text"]
