"""VAT (Richard, 1 Nov 2026, ruling A; aios-harness#45): 5% VAT on households' share of the counted lines,
as Reliable Britain's NZ11 does, on the extra the Clock counts. Households' share is the engine's domestic share
of electricity (run file, bills[y].netzero_on_household_bill_per_household.domestic_share). The CCL is outside
the base, as in RB: households do not pay it. VAT is its own line in the indirect layer.

Expected values are worked from the engine's file and the model's own lines, not from the VAT code.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from subsidy_engine_uk import inputs

ROOT = Path(__file__).resolve().parents[1]


def _share():
    mp = yaml.safe_load((ROOT / "reference/model_pin.yaml").read_text())
    run = json.loads((ROOT / mp["run_file"]).read_text())
    return {int(y): b["netzero_on_household_bill_per_household"]["domestic_share"]
            for y, b in run["bills"].items()}


@pytest.fixture(scope="module")
def model():
    return inputs.assemble_model(ROOT)[0]


def test_vat_is_5pc_of_households_share_of_the_counted_lines_ccl_out(model):
    by = {s.scheme_id: s for s in model["schemes"]}
    vat = by["vat"]
    assert vat.layer == "indirect"
    base_ids = [s.scheme_id for s in model["schemes"]
                if s.scheme_id not in ("vat", "ccl")
                and (s.layer == "indirect" or "renewables" in s.perspectives)]
    assert "carbon" in base_ids and "ro" in base_ids and "ccl" not in base_ids
    assert sorted(vat.extras["base_lines"]) == sorted(base_ids)
    share = _share()
    got = {r["year"]: r["cost_gbp"] for r in vat.annual.to_dicts()}
    for y in range(2002, 2027):
        base = sum({r["year"]: r["cost_gbp"] for r in by[i].annual.to_dicts()}.get(y, 0.0) for i in base_ids)
        s = share.get(y, share[max(share)])
        assert got[y] == pytest.approx(0.05 * s * base, rel=1e-9, abs=0.01), y
