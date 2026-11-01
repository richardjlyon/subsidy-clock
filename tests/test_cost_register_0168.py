"""Decision 0168 (one number, one source), point 6: the Clock reads every covered subsidy and system-cost series
for a closed year from the shared cost register, and from nowhere else (card t_af5fbf06; re-made on the
scheme modules for engine release v4-s43, aios-harness#42).

How it is proved: the model is assembled against a copy of the pinned register with ONE row moved by GBP 1m;
the Clock's own figure for that line and year must move by exactly GBP 1m. A line read from the Clock's own
reference file or feed instead does not move, and the test fails on the figure.
"""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import pytest

from subsidy_engine import cost_register as CR
from subsidy_engine_uk import cli
from subsidy_engine_uk import register as R

ROOT = Path(__file__).resolve().parents[1]
HOME = Path("/srv/aios/projects/report-series/shared-cost-register")
ENGINE = Path("/srv/aios/projects/model-gas-counterfactual")


def _moved(tmp_path: Path, line: str, year: int, by: float = 1.0) -> CR.Register:
    pin = R.load_pinned(ROOT)
    text = pin["register"].path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    hit = [r for r in rows if r["line_id"] == line and r["item_id"] == line and int(r["year"]) == year]
    assert len(hit) == 1, (line, year)
    hit[0]["cash_gbp_m"] = repr(float(hit[0]["cash_gbp_m"]) + by)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    p = tmp_path / "moved.csv"
    p.write_text(out.getvalue(), encoding="utf-8")
    return CR.load(p, hashlib.sha256(p.read_bytes()).hexdigest())


def _scheme(model, sid):
    return next(s for s in model["schemes"] if s.scheme_id == sid)


def _annual(model, sid, year, raw=False):
    s = _scheme(model, sid)
    if raw:
        return {int(r["year"]): r["cost"] for r in s.extras["raw_annual"]}[year]
    return {r["year"]: r["cost_gbp"] for r in s.annual.to_dicts()}[year]


@pytest.fixture(scope="module")
def base_model():
    return cli.assemble_model(ROOT)[0]


# (register line, year, Clock scheme, read the raw (gross) annual?)
COVERED = [
    ("RO", 2020, "ro", False),
    ("FIT", 2020, "fit", False),
    ("CCL_ELEC", 2020, "ccl", False),
    ("CPS", 2020, "ccl", False),
    ("ETS_POWER", 2020, "ets", False),
    ("TNUOS", 2020, "tnuos", True),
    ("BSUOS", 2010, "bsuos", True),          # from the Clock's history
    ("BSUOS", 2020, "bsuos", True),          # from NESO's daily files
    ("CONSTRAINTS", 2015, "constraints", False),   # REF history
    ("CONSTRAINTS", 2024, "constraints", False),   # Elexon daily (fix 5 guard year)
    ("TURNUP", 2020, "constraint_turnup", False),
    ("CFD", 2020, "cfd_renewable", False),
    ("CM_PAID", 2020, "capacity_market", True),
]


@pytest.mark.parametrize("line,year,sid,raw", COVERED, ids=[f"{c[0]}-{c[1]}" for c in COVERED])
def test_covered_series_is_read_from_the_register(monkeypatch, tmp_path, base_model, line, year, sid, raw):
    moved = _moved(tmp_path, line, year)
    real = R.load_pinned

    def pinned(root):
        p = real(root)
        p["register"] = moved
        return p

    monkeypatch.setattr(R, "load_pinned", pinned)
    model = cli.assemble_model(ROOT)[0]
    delta = _annual(model, sid, year, raw) - _annual(base_model, sid, year, raw)
    assert delta == pytest.approx(1e6, abs=0.01), (
        f"{line} {year}: the register row moved by GBP 1m but the Clock's {sid} {year} moved by GBP {delta:,.2f}: "
        f"this series is read from somewhere other than the register (0168)")


def test_every_closed_year_of_every_covered_line_is_the_registers(base_model):
    pin = R.load_pinned(ROOT)
    reg, prod, closed = pin["register"], pin["product"], pin["closed_through"]
    checks = {
        "ro": (("RO",), False), "fit": (("FIT",), False), "ccl": (("CCL_ELEC", "CPS"), False),
        "ets": (("ETS_POWER",), False), "tnuos": (("TNUOS",), True), "bsuos": (("BSUOS",), True),
        "constraints": (("CONSTRAINTS",), False), "constraint_turnup": (("TURNUP",), False),
        "cfd_renewable": (("CFD",), False), "capacity_market": (("CM_PAID",), True),
    }
    n = 0
    # the Clock's line is the register's line less the adjustments reference/clock_findings.yaml drops
    from subsidy_engine_uk import findings as F
    sel = F.load(ROOT / "reference" / "clock_findings.yaml", reg, product=prod)
    for sid, (lines, raw) in checks.items():
        vals = R.line_values(reg, prod, lines, sel)
        s = _scheme(base_model, sid)
        got = ({int(r["year"]): r["cost"] for r in s.extras["raw_annual"]} if raw else
               {r["year"]: r["cost_gbp"] for r in s.annual.to_dicts()})
        for y, v in vals.items():
            if y <= closed and y in got:
                assert got[y] == pytest.approx(v * 1e6, abs=0.01), (sid, y)
                n += 1
    assert n > 150


def test_register_pin_refuses_other_bytes(tmp_path):
    pin = R.load_pinned(ROOT)
    assert pin["register"].sha256 == pin["pin"]["sha256"]
    p = tmp_path / "x.csv"
    p.write_bytes(pin["register"].path.read_bytes() + b"\n")
    with pytest.raises(CR.RegisterError, match="not the pinned register"):
        CR.load(p, pin["pin"]["sha256"])


def test_vendored_register_is_the_register_homes_file():
    pin = R.load_pinned(ROOT)
    home = HOME / Path(pin["pin"]["file"]).name
    if not home.is_file():
        pytest.skip(f"register home not reachable from here: {home}")
    assert hashlib.sha256(home.read_bytes()).hexdigest() == pin["pin"]["sha256"]


def test_pins_name_v4_s43():
    pin = R.load_pinned(ROOT)
    assert pin["pin"]["release"] == "v4-s43"
    assert pin["pin"]["sha256"] == "e38ae577d255e3cb6e350d8b4c4483d58c7903766d65ad879c49b7b6c3adf5b8"
    assert pin["product"] == "clock_live"
    import yaml
    mp = yaml.safe_load((ROOT / "reference/model_pin.yaml").read_text())
    assert mp["engine_version"] == "v4-s43"
    assert mp["sha256"] == "e1cf23af9fd6129cc7e4b1dc7b1a5b058c9f20d0e1a64077d6817decea3828cf"
    assert mp["engine_commit"] == "8a5b0e1a070b561a4a964e55c5d29fbc6d03274b"


def test_vendored_engine_export_is_the_engine_release_file():
    import yaml
    mp = yaml.safe_load((ROOT / "reference/model_pin.yaml").read_text())
    src = ENGINE / "out" / "clock" / Path(mp["clock_export_file"]).name
    if not src.is_file():
        pytest.skip(f"engine not reachable from here: {src}")
    assert hashlib.sha256(src.read_bytes()).hexdigest() == mp["sha256"]


def test_engine_pin_refuses_other_bytes(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / "root"
    shutil.copytree(ROOT / "reference", root / "reference")
    p = root / "reference/engine/v4-s43.json"
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="sha256"):
        R.cm_share_from_engine(root, R.load_pinned(root))


def test_s32_cm_hand_copy_is_retired():
    assert not (ROOT / "reference/capacity_market_netzero_share.yaml").exists()
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
    assert "load_cm_netzero_share(" not in src.replace("def load_cm_netzero_share(", "")
