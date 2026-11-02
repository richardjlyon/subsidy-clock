"""The whole build-site run on the repository's own data, written to a temporary folder
(aios-harness#53). Everyday runs read the changelog with a stand-in release date
(tests/conftest.py); with --release it fails while the DEPLOY-DATE placeholder is in, as the
real build does."""
import csv
import json

from subsidy_engine.__main__ import ROOT, main
from subsidy_engine_uk import inputs

DATA_FILES = ["breakdown.json", "totals.json", "timeseries.json", "meta.json", "map.json",
              "changelog.json", "corrections.json", "scotland.json", "reconciliation.json",
              "combined-annual.csv", "changelog.csv", "corrections.csv", "restatements.csv"]


def test_build_site_writes_every_file_on_the_real_data(tmp_path):
    published = (ROOT / "site" / "data" / "breakdown.json").read_bytes()
    assert main(["build-site", "--out", str(tmp_path)]) == 0
    data = tmp_path / "data"
    for name in DATA_FILES:
        assert (data / name).is_file(), name
    for f in data.glob("*.json"):
        json.loads(f.read_text())
    for f in data.glob("*.csv"):
        assert list(csv.reader(f.open())), f.name
    assert json.loads((data / "breakdown.json").read_text())["schemes"]
    assert list((data / "assets").glob("*.json"))
    assert "<" in (tmp_path / "embed" / "widget.html").read_text()
    # the repository's published site is untouched
    assert (ROOT / "site" / "data" / "breakdown.json").read_bytes() == published


def test_the_loader_reads_every_reference_input_a_build_needs():
    i = inputs.load(ROOT)
    for name in ("refs", "deflators", "deflator_info", "road", "station_map",
                 "ro_stations", "bmu_map", "ctx", "equivalences", "bill", "bill_info",
                 "coords", "notes", "tiles", "bmu_zones", "pinned"):
        assert getattr(i, name) is not None, name
    assert "total_bill_gbp_2024" in i.bill.columns
