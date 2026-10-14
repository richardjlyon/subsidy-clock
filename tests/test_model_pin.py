"""The model pin (Richard Lyon, 14 Oct 2026): every counterfactual figure the Clock uses (the
Capacity Market net-zero share, the no-net-zero grid and balancing cost per year) comes from ONE released
export of the gas-counterfactual engine, vendored under reference/engine/ and pinned by version and
sha256 in reference/model_pin.yaml. Drift is detected; it is never applied automatically.

(a) the vendored file's sha256 equals the pin; (b) its meta.engine_version equals the pin;
(c) nothing else under reference/ defines a counterfactual figure; (d) the build output carries
model_pin, so downstream reports can check which engine release they were built on."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from subsidy_engine import reference

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
PIN = yaml.safe_load((REF / "model_pin.yaml").read_text())
VENDORED = ROOT / PIN["clock_export_file"]

# keys that state a counterfactual figure (what would have happened without net zero)
CF_KEY = re.compile(r"baseline|netzero|net_zero|counterfactual|own_backup", re.I)
RETIRED = ("baselines.yaml", "capacity_market_netzero_share.yaml")
# a stray counterfactual file anywhere under reference/ (outside reference/engine/) must fail (c)
STRAY_NAME = re.compile(r"counterfactual|netzero|net_zero|baseline", re.I)


def test_a_vendored_file_sha256_equals_the_pin():
    assert VENDORED.is_file(), PIN["clock_export_file"]
    assert VENDORED.parent == REF / "engine"
    assert hashlib.sha256(VENDORED.read_bytes()).hexdigest() == PIN["sha256"]


def test_b_vendored_engine_version_equals_the_pin():
    meta = json.loads(VENDORED.read_text())["meta"]
    assert meta["engine_version"] == PIN["engine_version"]
    assert VENDORED.stem == PIN["engine_version"]
    assert meta["commit"] == PIN["engine_commit"]


def test_a_b_loader_refuses_a_tampered_or_mismatched_file(tmp_path):
    (tmp_path / "reference" / "engine").mkdir(parents=True)
    vend = tmp_path / PIN["clock_export_file"]
    raw = bytearray(VENDORED.read_bytes())
    raw[-3] ^= 0x01                                  # one flipped bit
    vend.write_bytes(bytes(raw))
    (tmp_path / "reference" / "model_pin.yaml").write_text(yaml.safe_dump(PIN))
    with pytest.raises(ValueError, match="sha256"):
        reference.load_model_pin(tmp_path / "reference")
    vend.write_bytes(VENDORED.read_bytes())
    bad = dict(PIN, engine_version="v4-s99")
    (tmp_path / "reference" / "model_pin.yaml").write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="engine_version"):
        reference.load_model_pin(tmp_path / "reference")


def test_a_b_loader_refuses_an_old_schema_export(tmp_path):
    """A release without per-year grid/balancing series (clock-export/1, e.g. v4-s32) cannot be
    pinned: the Clock would have no counterfactual to subtract."""
    (tmp_path / "reference" / "engine").mkdir(parents=True)
    exp = json.loads(VENDORED.read_text())
    exp["meta"]["schema"] = "clock-export/1"
    for k in ("grid", "balancing", "carry_forward"):
        exp.pop(k)
    vend = tmp_path / PIN["clock_export_file"]
    vend.write_text(json.dumps(exp))
    pin = dict(PIN, sha256=hashlib.sha256(vend.read_bytes()).hexdigest())
    (tmp_path / "reference" / "model_pin.yaml").write_text(yaml.safe_dump(pin))
    with pytest.raises(ValueError, match="schema"):
        reference.load_model_pin(tmp_path / "reference")


def _walk_keys(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{path}/{k}", str(k)
            yield from _walk_keys(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_keys(v, f"{path}[{i}]")


def test_c_no_other_reference_file_defines_counterfactual_figures():
    for name in RETIRED:
        hits = [p for p in ROOT.rglob(name) if ".venv" not in p.parts and "scratch" not in p.parts]
        assert not hits, f"retired file is back: {hits} (counterfactual figures live only in the pin)"
    stray = [str(p.relative_to(ROOT)) for p in REF.rglob("*")
             if p.is_file() and p.parent != REF / "engine" and STRAY_NAME.search(p.name)]
    assert not stray, f"stray counterfactual file outside reference/engine/: {stray}"
    vendored = sorted(p.name for p in (REF / "engine").iterdir() if p.is_file())
    assert vendored == [VENDORED.name], f"reference/engine/ must hold only the pinned file: {vendored}"
    offenders = []
    for p in sorted(REF.rglob("*")):
        if not p.is_file() or p.parent == REF / "engine" or p.name == "model_pin.yaml":
            continue
        if p.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(p.read_text())
        elif p.suffix == ".json":
            data = json.loads(p.read_text())
        else:
            continue
        offenders += [f"{p.relative_to(ROOT)}:{path}" for path, k in _walk_keys(data) if CF_KEY.search(k)]
    assert not offenders, "counterfactual figures outside reference/engine/: " + ", ".join(offenders)


def test_c_pin_supplies_the_counterfactual_series_and_cm_share():
    pinned = reference.load_model_pin(REF)
    exp = json.loads(VENDORED.read_text())
    assert exp["meta"]["schema"] == reference.CLOCK_EXPORT_SCHEMA
    for k, block in (("tnuos", "grid"), ("bsuos", "balancing")):
        cf = pinned["counterfactual"][k]
        assert cf["years"] == {int(y): r["central_gbp"] for y, r in exp[block]["years"].items()}
        assert cf["low"] == {int(y): r["low_gbp"] for y, r in exp[block]["years"].items()}
        assert cf["high"] == {int(y): r["high_gbp"] for y, r in exp[block]["years"].items()}
        assert cf["carry_forward_from"] == exp["carry_forward"]["from"] == max(cf["years"])
        assert exp[block]["gen_share"] == "included"
        assert cf["engine_version"] == PIN["engine_version"]
    assert "baselines" not in pinned          # the scalar CPIH-carried baselines are retired
    assert sorted(pinned["cm_share"]["years"]) == sorted(int(y) for y in exp["capacity_market"]["years"])
    assert pinned["pin"] == {"engine_version": PIN["engine_version"], "sha256": PIN["sha256"],
                             "engine_commit": PIN["engine_commit"],
                             "release_date": str(PIN["release_date"]),
                             "clock_export_file": PIN["clock_export_file"]}


def test_d_build_output_carries_model_pin(tmp_path):
    """The real build-site command, on the real store and reference data, into a scratch root."""
    from subsidy_engine.__main__ import main
    for name in ("data", "reference", "changelog.jsonl"):
        (tmp_path / name).symlink_to(ROOT / name)
    (tmp_path / "site" / "embed").mkdir(parents=True)
    assert main(["--root", str(tmp_path), "build-site"]) == 0
    want = {"engine_version": PIN["engine_version"], "sha256": PIN["sha256"]}
    out = tmp_path / "site" / "data"
    assert json.loads((out / "breakdown.json").read_text())["model_pin"] == want
    assert json.loads((out / "meta.json").read_text())["model_pin"] == want
    bd = json.loads((out / "breakdown.json").read_text())
    by = {s["id"]: s for s in bd["schemes"]}
    pinned = reference.load_model_pin(REF)
    for k in ("tnuos", "bsuos"):
        cf = pinned["counterfactual"][k]
        rows = {r["year"]: r for r in by[k]["counterfactual_annual"]}
        for y, v in cf["years"].items():
            if y in rows:
                assert rows[y]["cost"] == v and rows[y]["basis"] == "modelled", (k, y)
        later = [y for y in rows if y > cf["carry_forward_from"]]
        assert all("carried forward" in rows[y]["basis"] for y in later), (k, later)
        assert PIN["engine_version"] in by[k]["counterfactual_source"]
        # the published rule text states the figure and rule the build used, not hand-typed ones
        note = by[k]["attribution_note"]
        assert "{" not in note and PIN["engine_version"] in note
        assert f"Years after {cf['carry_forward_from']}" in note and "CPIH" in note
        assert "baseline_gbp_nominal" not in by[k]
    assert by["capacity_market"]["share_provenance"]["engine_version"] == PIN["engine_version"]
