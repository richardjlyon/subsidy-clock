"""The whole build-site run from the model's real results file, written to a temporary folder
(aios-harness#53; from the results file since #140). Everyday runs read the changelog with a
stand-in release date (tests/conftest.py); with --release it fails while the DEPLOY-DATE
placeholder is in, as the real build does."""
import csv
import hashlib
import json
import shutil

import pytest
import yaml

from clocksite import inputs, results
from clocksite.__main__ import ROOT, main

DATA_FILES = ["breakdown.json", "totals.json", "timeseries.json", "meta.json", "map.json",
              "changelog.json", "corrections.json", "scotland.json", "reconciliation.json",
              "combined-annual.csv", "changelog.csv", "corrections.csv", "restatements.csv"]
RESULTS = ROOT / "results" / results.FILE


def test_build_site_writes_every_file_from_the_results_file(tmp_path, real_results):
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


def test_the_loader_reads_every_input_the_site_needs():
    i = inputs.load(ROOT)
    for name in ("equivalences", "coords", "notes", "tiles"):
        assert getattr(i, name) is not None, name


def test_the_results_tables_come_back_with_their_types(real_results):
    assert "total_bill_gbp_2024" in real_results.bill.columns
    assert real_results.deflators.schema["year"].is_integer()
    for s in real_results.model["schemes"]:
        assert s.annual.schema["year"].is_integer() and s.annual.schema["cost_gbp"].is_float(), s.scheme_id


def _copy(tmp_path, *, edit=None, meta=None):
    out = tmp_path / "clock.json"
    if edit is None and meta is None:
        shutil.copy(RESULTS, out)
        shutil.copy(RESULTS.with_name(RESULTS.name + ".sha256"), out.with_name("clock.json.sha256"))
        return out
    doc = json.loads(RESULTS.read_bytes())
    doc["meta"].update(meta or {})
    data = json.dumps(doc).encode()
    out.write_bytes(data + (edit or b""))
    out.with_name("clock.json.sha256").write_text(f"{hashlib.sha256(data).hexdigest()}  clock.json\n")
    return out


def test_a_results_file_from_another_model_version_is_refused(tmp_path, real_results):
    pin = results.load_pin(ROOT)
    path = _copy(tmp_path, meta={"version": "0.0.1"})
    with pytest.raises(results.ResultsRefused, match="version '0.0.1'; the site is pinned to"):
        results.read(path, pin)


def test_a_results_file_changed_after_the_model_wrote_it_is_refused(tmp_path, real_results):
    path = _copy(tmp_path, edit=b" ")
    with pytest.raises(results.ResultsRefused, match="not as the model wrote it"):
        results.read(path, results.load_pin(ROOT))


def test_fetch_refuses_and_writes_nothing_when_the_file_is_not_the_pinned_one(tmp_path, real_results):
    src = _copy(tmp_path, meta={"format": 99})
    out = tmp_path / "results"
    with pytest.raises(results.ResultsRefused, match="format 99"):
        results.fetch(str(src), out, results.load_pin(ROOT))
    assert not out.exists()


def test_the_pin_names_the_model_version_format_and_source():
    pin = yaml.safe_load((ROOT / "reference" / "results_pin.yaml").read_text())
    assert pin["model"] == "model-bill-already-paid"
    assert pin["source"].endswith("/results/clock.json")
