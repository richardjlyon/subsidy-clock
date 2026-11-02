"""The Clock's findings (reference/clock_findings.yaml; ported from card t_b468cbeb, aios-harness#42).

A finding names which of the shared cost register's own input adjustments the Clock does not take. What must
hold:
- each finding is approved by Richard (who, when, where) and says why;
- it only names the register's own adjustments (decision 0168): an item id the register does not hold for the
  Clock's product stops the build, and the yaml holds no figures;
- applying a finding moves the Clock's line by exactly that adjustment (expected values read from the register's
  rows, an independent file, not from the Clock's code).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from subsidy_engine_uk import inputs
from subsidy_engine_uk import findings as F
from subsidy_engine_uk import register as R

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "reference" / "clock_findings.yaml"


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "clock_findings.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


def _reg():
    return R.load_pinned(ROOT)["register"]


def _one(**over):
    f = {"status": "applied", "reason": "r", "approved": "Richard, 1 Nov 2026",
         "drop": ["clock.CPS.not_counted_2013"]}
    f.update(over)
    return {"findings": {"x": f}}


@pytest.fixture(scope="module")
def model():
    return inputs.assemble_model(ROOT)[0]


def _annual(model, sid):
    s = next(s for s in model["schemes"] if s.scheme_id == sid)
    return {r["year"]: r["cost_gbp"] for r in s.annual.to_dicts()}


def test_a_finding_needs_a_reason_and_richards_approval(tmp_path):
    for missing in ("reason", "approved"):
        doc = _one()
        del doc["findings"]["x"][missing]
        with pytest.raises(F.FindingsError, match=missing):
            F.load(_write(tmp_path, doc), _reg())
    with pytest.raises(F.FindingsError, match="status"):
        F.load(_write(tmp_path, _one(status="awaits_richard")), _reg())
    assert F.load(_write(tmp_path, _one()), _reg()).drop == {"clock.CPS.not_counted_2013"}


def test_unknown_register_item_stops_the_build(tmp_path):
    with pytest.raises(F.FindingsError, match="no_such_item"):
        F.load(_write(tmp_path, _one(drop=["clock.CPS.no_such_item"])), _reg())
    # an item that exists but not for the Clock's product
    with pytest.raises(F.FindingsError, match="no2.CCL.counted_to_31_jul_2015_only"):
        F.load(_write(tmp_path, _one(drop=["no2.CCL.counted_to_31_jul_2015_only"])), _reg())


def test_the_yaml_holds_no_figures():
    doc = yaml.safe_load(FILE.read_text())

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        else:
            yield x
    assert not [v for v in walk(doc) if isinstance(v, (int, float)) and not isinstance(v, bool)]


def test_the_build_records_the_findings_it_applied(model):
    rec = model["findings"]
    assert set(rec["applied"]) == set(yaml.safe_load(FILE.read_text())["findings"])
    assert rec["dropped"] == sorted(F.load(FILE, _reg()).drop)


# ---- step 2: Carbon Price Support counted from 1 April 2013 ----
# Since aios-harness#44 CPS is inside the carbon line's tax collected (the engine's own series, which charges
# CPS from 1 April 2013), not read from the register's CPS line.

def test_cps_is_counted_from_1_april_2013(model):
    reg = _reg()
    cps = reg.series("CPS")
    carbon = next(s for s in model["schemes"] if s.scheme_id == "carbon")
    tax = {p["year"]: p["tax_collected"] for p in carbon.extras["parts"]}
    assert cps[2013] > 0 and tax[2013] >= cps[2013] * 1e6 * 0.99   # GB tax collected holds 2013's CPS
    assert all(tax[y] == 0 for y in range(2002, 2008))


# ---- step 4: FiT scheme years 2019-20 and 2022-23 in their own years ----

def test_fit_scheme_values_sit_in_their_own_scheme_years(model):
    """The live Clock swapped scheme years 2019-20 and 2022-23 (data error). Since aios-harness#45 FiT is valued
    as the levelisation fund (0084): each FiT year is the register's FIT series itself, each scheme year in its
    own year, and nothing else."""
    series = _reg().series("FIT")
    got = _annual(model, "fit")
    for y in range(2010, 2025):
        assert got[y] == pytest.approx(series[y] * 1e6, abs=0.01), (
            f"FiT {y}: {got[y] / 1e6:,.3f}m on the Clock, the levelisation fund for scheme year {y} is "
            f"{series[y]:,.3f}m")


# ---- aios-harness#43 step 1: BSUoS history 2002-16 from the register's primary series (D-09) ----

def _raw(model, sid):
    s = next(s for s in model["schemes"] if s.scheme_id == sid)
    return {int(r["year"]): r["cost"] for r in s.extras["raw_annual"]}


def test_bsuos_history_is_the_registers_primary_series(model):
    """Richard, 1 Nov 2026 (option B): BSUoS history from primary sources (Ofgem, National Grid, NAO) as in the
    shared register, not REF Table 2. Each raw year 2002-16 is the register's BSUOS series itself."""
    # since aios-harness#45 less the generators' share (the register's rb row, taken by name)
    series = F.line(_reg(), "clock_live", "BSUOS", F.load(FILE, _reg()))
    raw = _raw(model, "bsuos")
    for y in range(2002, 2017):
        assert raw[y] == pytest.approx(series[y] * 1e6, abs=0.01), y


def test_no_ref_figures_left_in_the_bsuos_history_file():
    doc = yaml.safe_load((ROOT / "reference" / "indirect_annual.yaml").read_text())["schemes"]["bsuos_history"]
    text = " ".join(str(doc.get(k, "")) for k in ("source", "note"))
    assert "REF" not in text
    series = F.line(_reg(), "clock_live", "BSUOS", F.load(FILE, _reg()))   # what the Clock counts
    for y, v in doc["annual"].items():
        assert v == pytest.approx(series[int(y)] * 1e6, abs=0.01), y


# ---- aios-harness#43 step 1: TNUoS 2002-24 from the register's primary series, calendar years (D-09, D-13) ----

def test_tnuos_is_the_registers_primary_series_on_calendar_years(model):
    """Richard, 1 Nov 2026: primary sources, calendar years. Each raw TNUoS year 2002-24 is the register's
    TNUOS series itself (no Jan-Mar 2013 gap between a calendar 2012 and a charging-year 2013)."""
    # since aios-harness#45 less the generators' share (the register's rb row, taken by name)
    series = F.line(_reg(), "clock_live", "TNUOS", F.load(FILE, _reg()))
    raw = _raw(model, "tnuos")
    for y in range(2002, 2025):
        assert raw[y] == pytest.approx(series[y] * 1e6, abs=0.01), y


def test_no_ref_figures_left_in_the_tnuos_file():
    doc = yaml.safe_load((ROOT / "reference" / "indirect_annual.yaml").read_text())["schemes"]["tnuos"]
    text = " ".join(str(doc.get(k, "")) for k in ("source", "note"))
    assert "REF" not in text
    series = F.line(_reg(), "clock_live", "TNUOS", F.load(FILE, _reg()))   # what the Clock counts
    for y, v in doc["annual"].items():
        assert v == pytest.approx(series[int(y)] * 1e6, abs=0.01), y


# ---- aios-harness#45: take another product's named adjustment ----

def test_take_names_another_products_register_row_or_fails(tmp_path):
    ok = _one(drop=[], take=[["TNUOS", "rb", "rb.TNUOS.generators_share_out"]])
    assert F.load(_write(tmp_path, ok), _reg()).take == [("TNUOS", "rb", "rb.TNUOS.generators_share_out")]
    with pytest.raises(F.FindingsError, match="no_such"):
        F.load(_write(tmp_path, _one(drop=[], take=[["TNUOS", "rb", "rb.TNUOS.no_such"]])), _reg())
    with pytest.raises(F.FindingsError, match="BSUOS"):   # right item, wrong line
        F.load(_write(tmp_path, _one(drop=[], take=[["BSUOS", "rb", "rb.TNUOS.generators_share_out"]])), _reg())


def test_take_moves_the_line_by_exactly_the_register_row(tmp_path):
    reg = _reg()
    sel = F.load(_write(tmp_path, _one(drop=[], take=[["TNUOS", "rb", "rb.TNUOS.generators_share_out"]])), reg)
    got = F.line(reg, "clock_live", "TNUOS", sel)
    base = F.line(reg, "clock_live", "TNUOS", F.Selection())
    gen = reg.adjustments("TNUOS", "rb")["rb.TNUOS.generators_share_out"]
    for y, v in gen.items():
        assert got[y] == pytest.approx(base[y] + v, abs=1e-9), y


# ---- aios-harness#45 step 4: RO mutualisation counted (D-08), on the "received" basis ----

def test_ro_includes_mutualisation_received(model):
    reg = _reg()
    ro, mut = reg.series("RO"), reg.series("RO_MUT")   # Ofgem's figure unrounded (aios-harness#57)
    got = _annual(model, "ro")
    for y in range(2002, 2025):
        assert got[y] == pytest.approx((ro[y] + mut.get(y, 0.0)) * 1e6, abs=0.01), y
    assert sum(mut[y] for y in range(2017, 2022)) == pytest.approx(525.5, abs=0.1)   # received, not billed


# ---- aios-harness#57: Ofgem's and HMRC's figures unrounded (D-07; Richard, 2 Nov 2026: fix everything) ----

def test_ro_is_ofgems_figure_unrounded(model):
    """The live Clock rounded each RO year down to GBP 10m (clock.RO.ofgem_headline_rounded). The best account is
    Ofgem's figure itself: each RO year is the register's RO series plus mutualisation received, nothing taken off."""
    reg = _reg()
    ro, mut = reg.series("RO"), reg.series("RO_MUT")
    got = _annual(model, "ro")
    for y in range(2002, 2025):
        assert got[y] == pytest.approx((ro[y] + mut.get(y, 0.0)) * 1e6, abs=0.01), y


def test_ccl_is_hmrcs_figure_unrounded(model):
    """The live Clock's CCL input was HMRC's Table 1b rounded to GBP 0.1m (clock.CCL.hmrc_rounded_0_1m). Each CCL
    year is now the register's CCL_ELEC series itself."""
    series = _reg().series("CCL_ELEC")
    got = _annual(model, "ccl")
    for y in range(2002, 2025):
        assert got[y] == pytest.approx(series[y] * 1e6, abs=0.01), y
