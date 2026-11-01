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


def test_load_deflators():
    df = reference.load_deflators(REF_DIR / "deflators.yaml")
    assert df.columns == ["year", "index"]
    years = df["year"].to_list()
    assert years[0] == 2002 and years == sorted(years)
    # CPIH roughly doubles 2002 -> 2024
    i2002 = df.filter(df["year"] == 2002)["index"][0]
    i2024 = df.filter(df["year"] == 2024)["index"][0]
    assert 1.4 < i2024 / i2002 < 2.2


def test_load_indirect_annual():
    schemes = reference.load_annual_costs(REF_DIR / "indirect_annual.yaml")
    assert set(schemes) >= {"ccl", "tnuos", "bsuos_history"}
    assert "ets" not in schemes   # carbon comes from the engine (aios-harness#44)
    ccl = schemes["ccl"]
    assert ccl.attribution_rule != ""
    assert ccl.attribution_confidence in ("high", "medium", "low")
    assert ccl.perspectives == []           # indirect: not perspective-split
    years = ccl.annual["year"].to_list()
    assert years == sorted(years)


def test_tnuos_neso_traced_values():
    """TNUoS is on calendar years from the shared cost register (aios-harness#43): each calendar year is
    1/4 of the charging year before plus 3/4 of its own. Pinned against NESO's own anchors: "Final TNUoS
    Tariffs for 2023/24" (GBP 4,416.4m) and "for 2024/25" (MAR Total Revenue GBP 4,188.5m) make calendar
    2024; drift from the cited primary is caught."""
    schemes = reference.load_annual_costs(REF_DIR / "indirect_annual.yaml")
    annual = {r["year"]: r["cost_gbp"] for r in schemes["tnuos"].annual.to_dicts()}
    assert schemes["tnuos"].year_basis == "calendar"
    # NESO prints both to GBP 0.1m, so the weighted sum is known to within GBP 50k
    assert abs(annual[2024] - (0.25 * 4_416_400_000 + 0.75 * 4_188_500_000)) < 50_000


def test_load_ref_crosscheck():
    rc = reference.load_ref_crosscheck(REF_DIR / "ref_crosscheck.yaml")
    # The REF study must still be cited, but NOT necessarily at a ref.org.uk
    # URL: the original blog URL 404'd (checked 2026-09-01, study pulled from
    # the live site), so the citation is now an Internet Archive capture of it.
    # Assert the study is reachable-as-cited, not that the publisher still
    # hosts it — publisher URLs are not stable citations.
    url = rc["source_url"]
    assert url.startswith("https://")
    assert "ref.org.uk" in url
    assert set(rc["components"]) == {"capacity_market", "ccl", "ets", "bsuos", "tnuos"}
    assert all(v > 0 for v in rc["components"].values())


def test_load_electricity_bill():
    df = reference.load_electricity_bill(REF_DIR / "electricity_bill.yaml")
    assert df.columns == ["year", "total_bill_gbp"]
    years = df["year"].to_list()
    assert years[0] == 2002 and years == sorted(years)
    b2002 = df.filter(df["year"] == 2002)["total_bill_gbp"][0]
    b2023 = df.filter(df["year"] == 2023)["total_bill_gbp"][0]
    assert 8e9 < b2002 < 20e9       # ~£14bn
    assert 50e9 < b2023 < 90e9      # ~£71bn (2022-23 price spike)
    assert b2023 > b2002


def test_year_basis_defaults_and_calendar_override():
    direct = reference.load_annual_costs(REF_DIR / "annual_scheme_costs.yaml")
    assert direct["ro"].year_basis == "obligation_apr"   # default
    indirect = reference.load_annual_costs(REF_DIR / "indirect_annual.yaml")
    assert indirect["ccl"].year_basis == "calendar"
    assert indirect["tnuos"].year_basis == "calendar"
