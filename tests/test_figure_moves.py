import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "figure_moves.py"


def _site(d: Path, con_2023: float, headline: float) -> Path:
    d.mkdir()
    (d / "timeseries.json").write_text(json.dumps({"schemes": {
        "constraints": {"annual": [{"year": 2023, "cost": con_2023, "cost_real": con_2023 * 1.1},
                                   {"year": 2024, "cost": 5.0, "cost_real": 5.0}]}}}))
    (d / "totals.json").write_text(json.dumps({"generated_at": "x", "perspectives": {
        "renewables": {"cumulative": headline, "real": {"cumulative": headline * 1.2}}}}))
    return d


def _run(a: Path, b: Path) -> str:
    return subprocess.run([sys.executable, str(TOOL), str(a), str(b)],
                          capture_output=True, text=True, check=True).stdout


def test_reports_each_scheme_year_and_headline_that_moves(tmp_path):
    out = _run(_site(tmp_path / "a", 310e6, 100e9), _site(tmp_path / "b", 311e6, 101e9))
    assert "constraints 2023 cash: 310,000,000.00 -> 311,000,000.00 (+1,000,000.00)" in out
    assert "constraints 2024" not in out
    assert "headline renewables cash: 100,000,000,000.00 -> 101,000,000,000.00" in out


def test_moves_under_a_penny_are_not_reported(tmp_path):
    out = _run(_site(tmp_path / "a", 310e6, 100e9), _site(tmp_path / "b", 310e6 + 0.004, 100e9))
    assert "no figure moved by 1p or more" in out
