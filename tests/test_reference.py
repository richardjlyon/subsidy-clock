from pathlib import Path

from subsidy_engine import reference

REF_DIR = Path(__file__).resolve().parents[1] / "reference"


def test_load_annual_costs_shape():
    schemes = reference.load_annual_costs(REF_DIR / "annual_scheme_costs.yaml")
    assert "ro" in schemes and "fit" in schemes and "constraints_history" in schemes
    ro = schemes["ro"]
    assert ro.label == "Renewables Obligation"
    assert ro.source_url.startswith("https://")
    years = ro.annual["year"].to_list()
    assert years == sorted(years)
    assert all(v > 0 for v in ro.annual["cost_gbp"].to_list())


def test_ro_series_spans_scheme_life():
    schemes = reference.load_annual_costs(REF_DIR / "annual_scheme_costs.yaml")
    years = schemes["ro"].annual["year"].to_list()
    assert years[0] == 2002  # F-3: cumulative totals are real, from scheme start


def test_load_context():
    ctx = reference.load_context(REF_DIR / "context.yaml")
    assert 20_000_000 < ctx["households"]["value"] < 40_000_000
    assert "source_url" in ctx["households"]
    assert 100 < ctx["annual_demand_twh"]["value"] < 500
