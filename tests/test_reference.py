import yaml
import pytest
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
    assert set(schemes) >= {"ccl", "ets", "tnuos", "bsuos_history"}
    ccl = schemes["ccl"]
    assert ccl.attribution_rule != ""
    assert ccl.attribution_confidence in ("high", "medium", "low")
    assert ccl.perspectives == []           # indirect: not perspective-split
    years = ccl.annual["year"].to_list()
    assert years == sorted(years)


def test_tnuos_neso_traced_values():
    """TNUoS 2013-2024 from the National Grid / NESO charging statements themselves (v4-s35,
    T9: the engine's primary series; until v4-s35 via David Turver's workbook, which differs
    for 2013, 2014, 2018 and 2022). Pins the adopted values so drift from the primary is
    caught."""
    schemes = reference.load_annual_costs(REF_DIR / "indirect_annual.yaml")
    annual = {r["year"]: r["cost_gbp"] for r in schemes["tnuos"].annual.to_dicts()}
    expected = {
        2013: 2_153_000_000, 2014: 2_477_300_000, 2015: 2_636_700_000,
        2016: 2_708_700_000, 2017: 2_631_500_000, 2018: 2_670_000_000,
        2019: 2_837_400_000, 2020: 2_843_000_000, 2021: 3_318_000_000,
        2022: 3_594_252_621, 2023: 4_416_417_554, 2024: 4_188_500_000,
    }
    for yr, val in expected.items():
        assert annual[yr] == val, (yr, annual[yr])
    # 2021 was 3,594m (the 2022 row copied down) until 14 Oct 2026 (fix F1): NESO Final TNUoS
    # Tariffs 2021/22, https://www.neso.energy/document/186176/download, "Total revenue to be
    # collected is £3,318m"
    assert annual[2021] != annual[2022]


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


def test_load_counterfactual_series_from_the_pinned_engine_release():
    cf = reference.load_model_pin(REF_DIR)["counterfactual"]
    for key in ("bsuos", "tnuos"):
        c = cf[key]
        assert c["source_ids"] and c["carry_index"] == "CPIH"
        assert sorted(c["years"]) == list(range(2002, c["carry_forward_from"] + 1))
        assert all(v > 0 for v in c["years"].values())
    # engine v4-s35 GO5 / GO4 (generators' share included), GBP nominal: 2002-05 means sit near
    # G0 (GBP 987.4m since v4-s35's BETTA final Table 2.3; 982.3m before) and B0 (GBP 520.9m)
    g = sum(cf["tnuos"]["years"][y] for y in range(2002, 2006)) / 4
    b = sum(cf["bsuos"]["years"][y] for y in range(2002, 2006)) / 4
    assert 0.95e9 < g < 1.02e9
    assert 0.45e9 < b < 0.53e9
    # grid 2024: control index carry (1.93bn) + the WHOLE renewal allowance on the RAV
    # roll-forward (0.43bn) since v4-s35 (T3/T4); was 2.0-2.2bn with half on an annuity
    assert 2.3e9 < cf["tnuos"]["years"][2024] < 2.45e9


def test_year_basis_defaults_and_calendar_override():
    direct = reference.load_annual_costs(REF_DIR / "annual_scheme_costs.yaml")
    assert direct["ro"].year_basis == "obligation_apr"   # default
    indirect = reference.load_annual_costs(REF_DIR / "indirect_annual.yaml")
    assert indirect["ccl"].year_basis == "calendar"
    assert indirect["ets"].year_basis == "calendar"


def test_ccl_counts_electricity_levy_only_while_renewables_were_exempt():
    """Richard, 14 Oct 2026 (D2): the electricity CCL is counted only to 31 July 2015 (Finance
    (No. 2) Act 2015 s.49 ended the renewable exemption from 1 Aug 2015); Carbon Price Support in
    full. The two parts are stored separately and annual is their sum."""
    raw = yaml.safe_load((REF_DIR / "indirect_annual.yaml").read_text())["schemes"]["ccl"]
    el = raw["components"]["electricity_ccl_to_jul_2015"]
    cps = raw["components"]["carbon_price_support"]
    assert set(el) == set(cps) == set(raw["annual"])
    for y, v in raw["annual"].items():
        assert v == el[y] + cps[y], y
        if y > 2015:
            assert el[y] == 0, y
        if y < 2013:
            assert cps[y] == 0, y
    assert el[2015] == 189_100_000          # 7/12 of HMRC Table 1b 2015 (324.25m), rounded down
    assert el[2014] == 257_500_000 and cps[2014] == 893_000_000
    assert "to July 2015" in raw["label"] and "Carbon Price Support" in raw["label"]
    assert "1 August 2015" in raw["attribution"]["rule"]


def test_tnuos_and_bsuos_history_have_no_secondary_source():
    """T9 (v4-s35, Richard's rule: no secondary source in a line): every TNUoS and BSUoS history
    year is the gas-counterfactual engine's primary series; REF Table 2 is gone."""
    import yaml
    raw = yaml.safe_load((REF_DIR / "indirect_annual.yaml").read_text())["schemes"]
    for k in ("tnuos", "bsuos_history"):
        s = raw[k]
        assert s["verified"] is True
        assert "REF April 2025 study Table 2 total-charge column" not in s["source"]
        assert "per REF April 2025" not in s["source"]
        assert min(s["annual"]) == 2001
    t, b = raw["tnuos"]["annual"], raw["bsuos_history"]["annual"]
    # engine primaries (gascf.grid.tnuos_fy / baseline_fy_nominal; balancing.bsuos_fy / baseline_fy)
    assert t[2005] == 1_025_612_192 and t[2007] == 1_298_720_000 and t[2012] == 1_948_000_000
    assert b[2002] == 503_428_871 and b[2005] == 642_000_000 and b[2014] == 989_800_000
    assert b[2016] == 1_302_861_986


def test_counterfactual_range_labels_and_crossing_years_pass_through():
    """T1 (v4-s35): the range ends are labelled by net-zero cost, and the balancing range's
    crossing years (2002-04 and 2020) are carried from the pinned engine release."""
    cf = reference.load_model_pin(REF_DIR)["counterfactual"]
    assert "NET ZERO's cost" in cf["tnuos"]["range_labels"]
    assert cf["bsuos"]["crossing_years"] == [2002, 2003, 2004, 2020]
    assert cf["tnuos"]["crossing_years"] == []
