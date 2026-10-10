"""The Scotland briefing paper is fixed: it must render only from its frozen figures."""
import hashlib, importlib.util, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "site/papers/scotland-2026"


def _tool():
    spec = importlib.util.spec_from_file_location("scotland_claims", ROOT / "tools/scotland_claims.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_published_page_is_exactly_what_the_frozen_figures_render(tmp_path, monkeypatch):
    t = _tool()
    shutil.copy(PAPER / "figures.json", tmp_path / "figures.json")
    monkeypatch.setattr(t, "PAPER", tmp_path)
    t.render()
    assert (tmp_path / "index.html").read_text() == (PAPER / "index.html").read_text()


def test_render_does_not_read_live_site_data(tmp_path, monkeypatch):
    """Hide every live payload: the paper must still render identically."""
    t = _tool()
    shutil.copy(PAPER / "figures.json", tmp_path / "figures.json")
    monkeypatch.setattr(t, "PAPER", tmp_path)
    monkeypatch.setattr(t, "ROOT", ROOT)  # template only
    real_open = open
    def guarded(p, *a, **k):
        assert "site/data" not in str(p), f"paper read live data: {p}"
        return real_open(p, *a, **k)
    monkeypatch.setattr("builtins.open", guarded)
    t.render()
    assert (tmp_path / "index.html").read_text() == (PAPER / "index.html").read_text()


def test_paper_figures_are_the_2025_calendar_year():
    d = json.loads((PAPER / "figures.json").read_text())
    so = d["switch_off_2025"]
    assert so["top_day"]["date"].startswith("2025-")
    assert 0.9 < so["scotland_share"] < 1.0
    assert "window" not in json.dumps(d)          # no rolling 'since' period
