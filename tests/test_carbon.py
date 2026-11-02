"""Carbon: the full carbon effect on the electricity price, as Reliable Britain counts it (Richard, 1 Nov 2026,
0022 confirmed for the Clock; aios-harness#44). One line, read from the pinned engine release v4-s43 (its run
file's carbon_crosscheck: carbon in the wholesale price, NZ1c, and the tax collected on power), holding two
parts: the tax collected by the Treasury and the rest of the carbon in the price. It replaces the Clock's ETS
line and the Carbon Price Support inside its CCL line, and is never counted next to them.

Expected values are read from the engine's file directly, not from the Clock's code.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
import yaml

from subsidy_engine import reference
from subsidy_engine_uk import inputs
from subsidy_engine_uk import register as R

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path("/srv/aios/projects/model-gas-counterfactual")


def _run():
    mp = yaml.safe_load((ROOT / "reference/model_pin.yaml").read_text())
    return json.loads((ROOT / mp["run_file"]).read_text())


@pytest.fixture(scope="module")
def model():
    return inputs.assemble_model(ROOT)[0]


def _s(model, sid):
    return next((s for s in model["schemes"] if s.scheme_id == sid), None)


def _real(v, y, idx):
    return v * idx[2024] / idx[y]


def test_one_carbon_line_replaces_ets_and_cps(model):
    assert _s(model, "ets") is None
    c = _s(model, "carbon")
    assert c.layer == "indirect" and c.perspectives == []
    assert c.data_to == date(2024, 12, 31)
    # the CCL line is the levy alone: the register's CCL_ELEC series, no CPS in it (unrounded since #57)
    reg = R.load_pinned(ROOT)["register"]
    ccl = {r["year"]: r["cost_gbp"] for r in _s(model, "ccl").annual.to_dicts()}
    for y, v in reg.series("CCL_ELEC").items():
        if y <= 2024:
            assert ccl[y] == pytest.approx(v * 1e6, abs=0.01), y


def test_carbon_line_is_the_engines_nz1c_with_its_two_parts(model):
    cc = _run()["carbon_crosscheck"]
    c = _s(model, "carbon")
    annual = {r["year"]: r["cost_gbp"] for r in c.annual.to_dicts()}
    parts = {p["year"]: p for p in c.extras["parts"]}
    assert sorted(annual) == list(range(2002, 2025))
    for y in range(2002, 2025):
        row = cc[str(y)]
        assert annual[y] == pytest.approx(row["in_wholesale_gbp_m"] * 1e6, abs=0.01), y
        assert parts[y]["tax_collected"] == pytest.approx(row["collected_gbp_m"] * 1e6, abs=0.01), y
        assert parts[y]["tax_collected"] + parts[y]["rest_of_carbon_in_price"] == pytest.approx(annual[y], abs=0.01)


def test_2002_24_matches_reliable_britain_in_2024_prices(model):
    """RB: GBP 82.9bn = 23.7bn tax collected + 59.2bn the rest (2024 prices, GB)."""
    d = reference.load_deflators(ROOT / "reference" / "deflators.yaml")
    idx = dict(zip(d["year"].to_list(), d["index"].to_list()))
    c = _s(model, "carbon")
    real = {r["year"]: r["cost_gbp_2024"] for r in c.annual.to_dicts()}
    parts = {p["year"]: p for p in c.extras["parts"]}
    total = sum(real[y] for y in range(2002, 2025)) / 1e9
    tax = sum(_real(parts[y]["tax_collected"], y, idx) for y in range(2002, 2025)) / 1e9
    assert round(total, 1) == 82.9
    assert round(tax, 1) == 23.7
    assert round(total - tax, 1) == 59.2


def test_free_allowance_years_count_with_a_note(model):
    c = _s(model, "carbon")
    annual = {r["year"]: r["cost_gbp"] for r in c.annual.to_dicts()}
    assert all(annual[y] > 0 for y in range(2005, 2013))
    note = c.extras["data_note"].lower()
    assert "free" in note and "bills" in note


def test_run_file_pin_refuses_other_bytes(tmp_path):
    root = tmp_path / "root"
    shutil.copytree(ROOT / "reference", root / "reference")
    mp = yaml.safe_load((root / "reference/model_pin.yaml").read_text())
    p = root / mp["run_file"]
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="sha256"):
        R.carbon_from_engine(root)


def test_engine_counts_each_uk_ets_auction_once_in_its_own_calendar_year():
    """#44 check (from #42 step 3): the engine's tax collected sums 2021-24 auctions by their own date, so
    January-March 2024 is in 2024 only (the old Clock line counted it in 2023 and 2024)."""
    f = ENGINE / "data/raw/s36/ets/ukets-auctions-2021-24.csv"
    if not f.is_file():
        pytest.skip(f"engine raw data not reachable: {f}")
    rows = list(csv.DictReader(f.open()))
    assert max(Counter(r["date"] for r in rows).values()) == 1
    y2024 = sum(float(r["revenue_gbp"]) for r in rows if r["date"].startswith("2024"))
    assert y2024 == pytest.approx(2_564_090_000, abs=1)   # DESNZ's printed calendar-2024 total
