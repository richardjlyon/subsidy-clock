import json
import math
from datetime import date
from pathlib import Path

import pytest
import yaml

import polars as pl

from subsidy_engine import sitedata
from subsidy_engine.money import SchemeResult

CTX = {
    "households": {"value": 28_400_000, "source": "ONS", "source_url": "https://ons", "as_of": 2023},
    "population": {"value": 68_300_000, "source": "ONS", "source_url": "https://ons", "as_of": 2023},
    "annual_demand_twh": {"value": 266, "source": "DESNZ", "source_url": "https://desnz", "as_of": 2024},
}

EQUIV = yaml.safe_load(Path("reference/equivalences.yaml").read_text())

DEFLATOR_INFO = {"source": "ONS CPIH L522", "source_url": "https://ons", "base_year": 2024}

DEFLATORS = pl.DataFrame(
    {"year": [2012, 2014, 2015, 2022, 2024],
     "index": [96.0, 99.6, 100.0, 120.5, 132.9]},
    schema={"year": pl.Int64, "index": pl.Float64})


def model():
    annual = pl.DataFrame(
        {"year": [2025, 2026], "cost_gbp": [3.0e9, 1.0e9],
         "cost_gbp_2024": [2.9e9, 0.95e9]},
        schema={"year": pl.Int64, "cost_gbp": pl.Float64, "cost_gbp_2024": pl.Float64})
    direct = SchemeResult(
        scheme_id="cfd_renewable", label="CfD - renewables",
        perspectives=["renewables", "low_carbon"], cadence="daily",
        annual=annual, cumulative_gbp=4.0e9, runrate_gbp_per_year=2.0e9,
        data_to=date(2026, 6, 1),
        extras={"by_technology": [], "by_recipient": [], "gross": 4.1e9, "net": 4.0e9},
    )
    indirect = SchemeResult(
        scheme_id="bsuos", label="Balancing costs (BSUoS uplift)",
        perspectives=[], cadence="daily", layer="indirect",
        annual=annual, cumulative_gbp=4.0e9, runrate_gbp_per_year=1.0e9,
        data_to=date(2026, 6, 1),
        attribution_pct=0.4, attribution_note="uplift above baseline",
        attribution_confidence="low",
    )
    block = {"cumulative_gbp": 4.0e9, "runrate_gbp_per_year": 2.0e9,
             "rate_gbp_per_sec": 63.38, "annual": annual, "since_year": 2025,
             "cumulative_gbp_2024": 3.85e9, "runrate_gbp_per_year_2024": 1.94e9,
             "rate_gbp_per_sec_2024": 61.48}
    iblock = dict(block, runrate_gbp_per_year=1.0e9)
    return {"schemes": [direct, indirect],
            "perspectives": {"renewables": dict(block), "low_carbon": dict(block)},
            "indirect": iblock}


def big_model():
    """Model with realistic magnitudes so the £10bn floor is exercised."""
    m = model()
    for p in m["perspectives"].values():
        p["cumulative_gbp_2024"] = 128.0e9
        p["runrate_gbp_per_year"] = 12.2e9
        # real run-rate kept distinct from nominal: the factoids quote today's
        # money, so they must read this, not the as-paid 12.2e9
        p["runrate_gbp_per_year_2024"] = 11.9e9
    m["indirect"]["cumulative_gbp_2024"] = 95.35e9   # combined real = 223.35e9
    return m


def _factoids_by_slug(tmp_path, model, equivalences=EQUIV):
    sitedata.build(model, CTX, {}, tmp_path,
                   generated_at="2026-06-12T07:00:00+00:00",
                   deflator_info=DEFLATOR_INFO, deflators=DEFLATORS,
                   equivalences=equivalences)
    meta = json.loads((tmp_path / "meta.json").read_text())
    return {f["slug"]: f for f in meta["factoids"]}, meta


def test_factoids_floored_figures_and_sentences(tmp_path):
    by_slug, meta = _factoids_by_slug(tmp_path, big_model(),
        [r for r in EQUIV if r["slug"] in ("nurses", "homes", "hinkley")])
    assert set(by_slug) == {"nurses", "homes", "hinkley"}

    # nurses: real 11.9e9 / 39043 = 304,791.6 -> floored to 1,000 -> 304,000
    assert by_slug["nurses"]["figure"] == "304,000"
    assert "304,000 NHS nurses" in by_slug["nurses"]["sentence"]
    assert by_slug["nurses"]["sentence"].startswith("A year of direct UK renewable subsidy")
    assert "in today's money" in by_slug["nurses"]["sentence"]
    assert by_slug["nurses"]["frame"] == "a year of this subsidy pays"
    assert by_slug["nurses"]["figure_label"] == "NHS nurses"

    # combined real 223.35e9 -> £10bn floor strictly below -> £220bn+
    # homes = 220e9 / 393333 = 559,322.0 -> 559,000
    assert by_slug["homes"]["figure"] == "559,000"
    assert by_slug["homes"]["frame"] == "the current £220bn+ full cost would have built"
    assert "£220bn+ full cost" in by_slug["homes"]["sentence"]
    assert "social homes" in by_slug["homes"]["label"]

    # hinkley: 35e9 * 132.9/100 = 46.515e9; 220 / 46.515 = 4.73 -> 4
    assert by_slug["hinkley"]["figure"] == "4"
    assert "4 Hinkley Point C-scale nuclear stations in the UK" in by_slug["hinkley"]["sentence"]

    for f in meta["factoids"]:
        assert f["source_url"], f["slug"]
        assert f["label"] and "{" not in f["label"], f["slug"]
        assert "{" not in f["sentence"] and "{" not in f["frame"], f["slug"]


def test_factoids_exact_floor_steps_down(tmp_path):
    m = big_model()
    m["perspectives"]["renewables"]["cumulative_gbp_2024"] = 130.0e9
    m["indirect"]["cumulative_gbp_2024"] = 100.0e9   # combined exactly 230e9
    by_slug, _ = _factoids_by_slug(tmp_path, m,
        [r for r in EQUIV if r["slug"] == "homes"])
    assert by_slug["homes"]["frame"] == "the current £220bn+ full cost would have built"


def test_factoids_absent_without_equivalences(tmp_path):
    _, meta = _factoids_by_slug(tmp_path, big_model(), [])
    assert meta["factoids"] == []


def test_factoids_reject_baked_figure(tmp_path):
    bad = [{"slug": "x", "unit_gbp": 1e9, "basis": "full", "round_to": 1,
            "figure_label": "things", "frame": "the £220bn would have built",
            "sentence": "The £220bn would have built {n} things.",
            "label": "{n} things", "source": "s", "source_url": "https://s"}]
    with pytest.raises(ValueError, match="baked"):
        _factoids_by_slug(tmp_path, big_model(), bad)


def test_build_writes_all_files(tmp_path):
    freshness = {"cfd": {"retrieved_at": "2026-06-09T06:00:00+00:00",
                         "source_date": None, "source_url": "https://lccc"}}
    sitedata.build(model(), CTX, freshness, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00",
                   deflator_info=DEFLATOR_INFO)
    for name in ("totals.json", "timeseries.json", "breakdown.json", "meta.json"):
        assert (tmp_path / name).is_file(), name

    totals = json.loads((tmp_path / "totals.json").read_text())
    r = totals["perspectives"]["renewables"]
    assert r["cumulative"] == 4.0e9
    import math
    assert r["per_household_per_year"] == math.floor(2.0e9 / 28_400_000 * 100) / 100
    assert r["real"]["cumulative"] == 3.85e9
    assert r["real"]["per_household_per_year"] == math.floor(1.94e9 / 28_400_000 * 100) / 100
    assert "all_levy" not in totals["perspectives"]
    ind = totals["indirect"]
    assert ind["runrate_per_year"] == 1.0e9
    assert ind["real"]["cumulative"] == 3.85e9

    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert ts["schemes"]["bsuos"]["annual"][0] == {
        "year": 2025, "cost": 3.0e9, "cost_real": 2.9e9}

    breakdown = json.loads((tmp_path / "breakdown.json").read_text())
    by_id = {s["id"]: s for s in breakdown["schemes"]}
    assert by_id["cfd_renewable"]["layer"] == "direct"
    b = by_id["bsuos"]
    assert b["layer"] == "indirect"
    assert b["attribution_pct"] == 0.4
    assert b["attribution_confidence"] == "low"
    assert b["attribution_note"] == "uplift above baseline"

    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["deflator"]["base_year"] == 2024


def test_build_writes_electricity_bill(tmp_path):
    bill = pl.DataFrame(
        {"year": [2023, 2024],
         "total_bill_gbp": [71.2e9, 60.0e9],
         "total_bill_gbp_2024": [72.0e9, 60.0e9]},
        schema={"year": pl.Int64, "total_bill_gbp": pl.Float64,
                "total_bill_gbp_2024": pl.Float64})
    sitedata.build(model(), CTX, {}, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00",
                   bill_annual=bill,
                   bill_info={"source": "DUKES 1.3",
                              "source_url": "https://gov.uk/dukes",
                              "verified": True})
    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert ts["electricity_bill"]["annual"][0] == {
        "year": 2023, "total_bill": 71.2e9, "total_bill_real": 72.0e9}
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["bill"]["source_url"] == "https://gov.uk/dukes"


def test_build_without_bill_omits_electricity_bill_block(tmp_path):
    sitedata.build(model(), CTX, {}, tmp_path,
                   generated_at="2026-06-09T07:00:00+00:00")
    ts = json.loads((tmp_path / "timeseries.json").read_text())
    assert "electricity_bill" not in ts


def test_write_csvs(tmp_path):
    sitedata.write_csvs(model(), tmp_path, generated="2026-06-11T05:45:00+00:00",
                        restatements=[
        {"scheme": "bsuos", "table": "daily",
         "detected_at": "2026-06-10T06:31:04+00:00", "partition": "2026-2027",
         "previous_version": "20260610T063012", "new_version": "20260610T063104"}])
    # per-scheme files named by their public slug; attribution carried in-file
    cfd = (tmp_path / "cfd.csv").read_text().splitlines()
    assert cfd[0] == "# The Subsidy Clock — subsidyclock.co.uk"
    assert cfd[1] == ('# Licence: CC BY 4.0 (credit "The Subsidy Clock — '
                      'subsidyclock.co.uk") · contains public sector information '
                      'licensed under OGL v3.0 — generated 2026-06-11 05:45 UTC')
    # third line: measured vs estimated must travel with the file
    assert cfd[2] == ("# Measured payments — derivation: "
                      "subsidyclock.co.uk/explainers/contracts-for-difference")
    assert cfd[3] == "year,cost,cost_real"
    # money columns print at fixed 2 dp - real pennies kept, float noise cut
    assert cfd[4] == "2025,3000000000.00,2900000000.00"
    bsuos = (tmp_path / "bsuos.csv").read_text().splitlines()
    assert bsuos[2] == ("# Estimated share attributed to renewables — method: "
                        "subsidyclock.co.uk/methodology#attr-bsuos")
    # combined annual: one row per year, one column per scheme
    combined = (tmp_path / "combined-annual.csv").read_text().splitlines()
    assert combined[0].startswith("# The Subsidy Clock")
    assert combined[2] == ("# Mixes measured and estimated series — see "
                           "subsidyclock.co.uk/methodology#indirect")
    assert combined[3] == "year,cfd_renewable,bsuos"
    assert combined[4] == "2025,3000000000.00,3000000000.00"
    # restatements published alongside, same header
    rst = (tmp_path / "restatements.csv").read_text().splitlines()
    assert rst[2] == ("# Source revisions log — every restatement the engine "
                      "has recorded: subsidyclock.co.uk/data")
    assert rst[3] == "scheme,table,detected_at,partition,previous_version,new_version"
    assert rst[4].startswith("bsuos,daily,")


def test_write_csvs_pennies_match_store(tmp_path):
    """The published CSV must sum to the scheme's cumulative figure - to the penny."""
    m = model()
    sitedata.write_csvs(m, tmp_path, generated="2026-06-11T05:45:00+00:00",
                        restatements=[])
    rows = [l for l in (tmp_path / "cfd.csv").read_text().splitlines()
            if l and not l.startswith("#")][1:]
    total = sum(float(line.split(",")[1]) for line in rows)
    assert abs(total - m["schemes"][0].cumulative_gbp) < 0.01


def test_write_csvs_no_restatements_writes_header_only(tmp_path):
    sitedata.write_csvs(model(), tmp_path, generated="2026-06-11T05:45:00+00:00",
                        restatements=[])
    rst = (tmp_path / "restatements.csv").read_text().splitlines()
    assert rst[0] == "# The Subsidy Clock — subsidyclock.co.uk"
    assert rst[1].startswith("# Licence: CC BY 4.0")
    assert rst[2].startswith("# Source revisions log")
    assert rst[3] == "scheme,table,detected_at,partition,previous_version,new_version"
    assert len(rst) == 4


def test_factoid_divisions_floor_not_round(tmp_path):
    m = big_model()
    m["perspectives"]["renewables"]["runrate_gbp_per_year_2024"] = 12.4e9
    by_slug, _ = _factoids_by_slug(tmp_path, m,
        [r for r in EQUIV if r["slug"] == "nurses"])
    # 12.4e9 / 39043 = 317,598.5 -> floor 317,000 (round would give 318,000)
    assert by_slug["nurses"]["figure"] == "317,000"


def test_per_unit_floored_and_agrees_across_surfaces(tmp_path):
    sitedata.build(big_model(), CTX, {}, tmp_path,
                   generated_at="2026-06-15T00:00:00+00:00",
                   deflator_info=DEFLATOR_INFO, deflators=DEFLATORS)
    totals = json.loads((tmp_path / "totals.json").read_text())
    r = totals["perspectives"]["renewables"]

    import math
    rr = r["real"]
    # _block derives each per-unit figure from its own basis run-rate
    assert r["per_mwh_delivered"] == math.floor(
        r["runrate_per_year"] / (CTX["annual_demand_twh"]["value"] * 1_000_000) * 100) / 100
    assert rr["per_mwh_delivered"] == math.floor(
        rr["runrate_per_year"] / (CTX["annual_demand_twh"]["value"] * 1_000_000) * 100) / 100
    assert rr["per_person_per_year"] == math.floor(
        rr["runrate_per_year"] / CTX["population"]["value"] * 100) / 100

    # real and nominal per-unit figures are genuinely distinct
    assert rr["per_mwh_delivered"] != r["per_mwh_delivered"]


def test_write_widget_stamps_figure_and_rate(tmp_path):
    totals = {
        "generated_at": "2026-06-11T05:45:00+00:00",
        "perspectives": {"renewables": {
            "cumulative": 108_634_210_556.78,
            "rate_per_sec": 385.72,
            "since_year": 2002,
            "real": {
                "cumulative": 130_000_000_000.0,
                "rate_per_sec": 390.0,
            },
        }},
        "indirect": {
            "cumulative": 78_000_000_000.0,
            "rate_per_sec": 253.0,
            "real": {
                "cumulative": 95_000_000_000.0,
                "rate_per_sec": 244.0,
            },
        },
    }
    out = tmp_path / "widget.html"
    sitedata.write_widget(totals, out)
    html = out.read_text()
    # default = real + combined: 130bn + 95bn = 225bn, 390 + 244 = 634
    assert "£225,000,000,000" in html          # static fallback figure
    assert "11 June 2026" in html               # as-of date always visible
    assert '"rate": 634.0' in html              # ticking parameters
    assert '"cum": 225000000000.0' in html
    assert "plus estimated indirect system costs" in html  # combined descriptor
    assert "{{" not in html                     # no unfilled tokens
    assert "subsidyclock.co.uk" in html         # locked attribution


# ---- corrections log (corrections C4) ----

CORR_VALID = ('{"date": "2026-07-01", "figure": "switch-off", '
              '"figure_label": "Paid to switch off", "was": "£1.62bn", '
              '"now": "£1.59bn", "cause": "Double-counted two settlement days", '
              '"credit": "J. Smith"}')


def _corr_file(tmp_path, lines):
    p = tmp_path / "corrections.jsonl"
    p.write_text("\n".join(lines) + ("\n" if lines else ""))
    return p


def test_load_corrections_missing_file_is_empty(tmp_path):
    assert sitedata.load_corrections(tmp_path / "corrections.jsonl") == []


def test_load_corrections_valid_entry(tmp_path):
    entries = sitedata.load_corrections(_corr_file(tmp_path, [CORR_VALID]))
    assert len(entries) == 1
    assert entries[0]["figure"] == "switch-off"
    assert entries[0]["now"] == "£1.59bn"
    assert entries[0]["credit"] == "J. Smith"


def test_load_corrections_credit_optional(tmp_path):
    line = CORR_VALID.replace(', "credit": "J. Smith"', '')
    entries = sitedata.load_corrections(_corr_file(tmp_path, [line]))
    assert entries[0]["credit"] == ""


def test_load_corrections_missing_field_raises(tmp_path):
    line = CORR_VALID.replace('"cause": "Double-counted two settlement days", ', '')
    with pytest.raises(ValueError, match="cause"):
        sitedata.load_corrections(_corr_file(tmp_path, [line]))


def test_load_corrections_bad_json_raises(tmp_path):
    with pytest.raises(ValueError, match="line 1"):
        sitedata.load_corrections(_corr_file(tmp_path, ["{not json"]))


def test_load_corrections_sorted_oldest_first(tmp_path):
    older = CORR_VALID.replace("2026-07-01", "2026-05-01")
    entries = sitedata.load_corrections(_corr_file(tmp_path, [CORR_VALID, older]))
    assert [e["date"] for e in entries] == ["2026-05-01", "2026-07-01"]


def test_write_corrections_files(tmp_path):
    entries = sitedata.load_corrections(_corr_file(tmp_path, [CORR_VALID]))
    sitedata.write_corrections(entries, tmp_path / "out",
                               generated="2026-06-12T17:00:00+00:00")
    data = json.loads((tmp_path / "out" / "corrections.json").read_text())
    assert data["generated_at"] == "2026-06-12T17:00:00+00:00"
    assert data["corrections"][0]["now"] == "£1.59bn"
    lines = (tmp_path / "out" / "corrections.csv").read_text().splitlines()
    assert lines[0].startswith("# The Subsidy Clock")
    assert lines[1].startswith("# Licence: CC BY 4.0")
    assert lines[2] == ("# Corrections to our own published figures — every "
                        "confirmed error: subsidyclock.co.uk/corrections")
    assert lines[3] == "date,figure,figure_label,was,now,cause,credit"
    assert "£1.59bn" in lines[4]


def test_write_corrections_empty_log(tmp_path):
    sitedata.write_corrections([], tmp_path / "out",
                               generated="2026-06-12T17:00:00+00:00")
    data = json.loads((tmp_path / "out" / "corrections.json").read_text())
    assert data["corrections"] == []
    lines = (tmp_path / "out" / "corrections.csv").read_text().splitlines()
    assert lines[3] == "date,figure,figure_label,was,now,cause,credit"
    assert len(lines) == 4


def test_full_pool_resolves(tmp_path):
    _, meta = _factoids_by_slug(tmp_path, big_model(), EQUIV)
    assert len(meta["factoids"]) == 11
    for f in meta["factoids"]:
        assert int(f["figure"].replace(",", "")) > 0, f["slug"]
        assert f["source_url"].startswith("http"), f["slug"]
        for field in ("frame", "sentence", "label"):
            assert "{" not in f[field], (f["slug"], field)
        assert f["basis"] in ("full", "runrate")


def test_floor2_floors_does_not_round():
    # 45.2477 floors to 45.24 but rounds to 45.25 — proves _floor2 understates
    assert sitedata._floor2(45.2477) == 45.24
    assert sitedata._floor2(45.2477) != round(45.2477, 2)
    # exact-2dp values are unchanged
    assert sitedata._floor2(46.98) == 46.98


def test_meta_publishes_full_combined_real_headline(tmp_path):
    sitedata.build(big_model(), CTX, {}, tmp_path,
                   generated_at="2026-06-15T00:00:00+00:00",
                   deflator_info=DEFLATOR_INFO, deflators=DEFLATORS)
    totals = json.loads((tmp_path / "totals.json").read_text())
    meta = json.loads((tmp_path / "meta.json").read_text())
    combined = (totals["perspectives"]["renewables"]["real"]["cumulative"]
                + totals["indirect"]["real"]["cumulative"])
    # the headline card shows the FULL figure (every significant figure), not a floor
    assert meta["headline"]["combined_real"] == combined


# ---- recipients map (map.json) ----

TILES = {
    "style_url": "https://tiles.example.org/styles/test",
    "center": [-3.05, 54.45], "zoom": 4.9,
    "terrain": {"tiles": "https://terrain.example.org/{z}/{x}/{y}.png",
                "encoding": "terrarium"},
    "attribution": "Test © OpenMapTiles Data from OpenStreetMap",
    "terrain_attribution": "Terrain: test credits",
}


def _map_model():
    cfdr = SchemeResult(
        scheme_id="cfd_renewable", label="CfD - renewables",
        perspectives=["renewables"], cadence="daily",
        annual=pl.DataFrame({"year": [2025], "cost_gbp": [1.0],
                             "cost_gbp_2024": [1.0]}),
        cumulative_gbp=1.0, runrate_gbp_per_year=1.0, data_to=date(2025, 1, 1),
        extras={"by_station": [
            {"station": "Hornsea 1", "technology": "Offshore Wind",
             "cost": 2.5e9},
            {"station": "Drax", "technology": "Biomass Conversion",
             "cost": 1.9e9},
            {"station": "No Coord Farm", "technology": "Onshore Wind",
             "cost": 1.0e9},
        ],
        "station_detail": [
            {"station": "Hornsea 1", "technology": "Offshore Wind",
             "cost": 2.5e9, "generation_mwh": 18e6, "data_to": "2026-07-01",
             "quarters": [
                 {"q": "2020-Q1", "payment_gbp": 1.2e9, "generation_mwh": 9e6},
                 {"q": "2021-Q4", "payment_gbp": -2.0e8, "generation_mwh": 4e6},
                 {"q": "2022-Q1", "payment_gbp": 1.5e9, "generation_mwh": 5e6},
             ],
             "contracts": [
                 {"cfd_id": "HOR-1", "unit_name": "Hornsea P1",
                  "technology": "Offshore Wind", "cumulative_gbp": 2.5e9,
                  "first_settlement": "2019-06-01",
                  "latest_strike_gbp_mwh": 158.0},
             ]},
            # zero generation -> the effective-rate tile must be suppressed
            {"station": "Drax", "technology": "Biomass Conversion",
             "cost": 1.9e9, "generation_mwh": 0.0, "data_to": "2026-07-01",
             "quarters": [
                 {"q": "2024-Q1", "payment_gbp": 1.9e9, "generation_mwh": 0.0},
             ],
             "contracts": [
                 {"cfd_id": "DRX-1", "unit_name": "Drax CfD",
                  "technology": "Biomass Conversion", "cumulative_gbp": 1.9e9,
                  "first_settlement": "2016-01-01",
                  "latest_strike_gbp_mwh": 121.0},
             ]},
        ]},
    )
    ro = SchemeResult(
        scheme_id="ro", label="Renewables Obligation",
        perspectives=["renewables"], cadence="annual",
        annual=pl.DataFrame({"year": [2025], "cost_gbp": [1.0],
                             "cost_gbp_2024": [1.0]}),
        cumulative_gbp=1.0, runrate_gbp_per_year=1.0, data_to=date(2025, 1, 1),
        extras={"by_station": [
            {"station": "Drax Power Station", "technology": "Biomass",
             "cost": 6.4e9},
        ]},
    )
    return {"schemes": [cfdr, ro],
            "perspectives": {"renewables": {}}}


COORDS = {
    "Hornsea 1": (53.88, 1.68, "hornsea-1"),
    "Drax": (53.738, -0.9998, "drax"),
    "Drax Power Station": (53.738, -0.9998, "drax-power-station"),
    # "No Coord Farm" deliberately absent
}


def test_map_data_markers_only_for_stations_with_coords():
    m = sitedata._map_data(_map_model(), COORDS, TILES)
    names = sorted(mk["name"] for mk in m["markers"])
    assert names == ["Drax", "Drax Power Station", "Hornsea 1"]
    assert "No Coord Farm" not in names


def test_map_data_drax_yields_two_markers_one_per_scheme():
    m = sitedata._map_data(_map_model(), COORDS, TILES)
    drax = [mk for mk in m["markers"] if mk["name"].startswith("Drax")]
    schemes = sorted(mk["scheme"] for mk in drax)
    assert schemes == ["cfd_renewable", "ro"]
    # distinct slugs -> distinct asset JSONs; no cross-scheme identity
    slugs = sorted(mk["slug"] for mk in drax)
    assert slugs == ["drax", "drax-power-station"]


def test_map_data_carries_cost_technology_and_scheme():
    m = sitedata._map_data(_map_model(), COORDS, TILES)
    hornsea = next(mk for mk in m["markers"] if mk["name"] == "Hornsea 1")
    assert hornsea["scheme"] == "cfd_renewable"
    assert hornsea["technology"] == "Offshore Wind"
    assert hornsea["cost"] == 2.5e9


def test_map_data_markers_carry_latlon_slug_no_pixels():
    m = sitedata._map_data(_map_model(), COORDS, TILES)
    hornsea = next(mk for mk in m["markers"] if mk["name"] == "Hornsea 1")
    assert (hornsea["lat"], hornsea["lon"]) == (53.88, 1.68)
    assert hornsea["slug"] == "hornsea-1"
    # pixel-space projection is gone: the client projects lat/lon itself
    assert "x" not in hornsea and "y" not in hornsea


def test_map_data_carries_tiles_block_verbatim():
    m = sitedata._map_data(_map_model(), COORDS, TILES)
    t = m["tiles"]
    assert t["style_url"] == TILES["style_url"]
    assert t["attribution"] == TILES["attribution"]
    assert t["terrain_attribution"] == TILES["terrain_attribution"]
    assert t["terrain"]["encoding"] == "terrarium"
    # no Mapbox anywhere, no token machinery
    assert "mapbox" not in json.dumps(m).lower()


def test_build_writes_map_json(tmp_path):
    # use the full model() (proper perspective blocks) but give its
    # cfd_renewable scheme a by_station list so a marker is emitted
    full = model()
    full["schemes"][0].extras["by_station"] = [
        {"station": "Hornsea 1", "technology": "Offshore Wind", "cost": 2.5e9},
    ]
    full["schemes"][0].extras["station_detail"] = [
        {"station": "Hornsea 1", "technology": "Offshore Wind", "cost": 2.5e9,
         "generation_mwh": 18e6, "data_to": "2026-07-01",
         "quarters": [{"q": "2020-Q1", "payment_gbp": 2.5e9,
                       "generation_mwh": 18e6}],
         "contracts": [{"cfd_id": "HOR-1", "unit_name": "Hornsea P1",
                        "technology": "Offshore Wind", "cumulative_gbp": 2.5e9,
                        "first_settlement": "2019-06-01",
                        "latest_strike_gbp_mwh": 158.0}]},
    ]
    sitedata.build(full, CTX, {}, tmp_path,
                   generated_at="2026-06-17T07:00:00+00:00",
                   coords=COORDS, tiles=TILES)
    assert (tmp_path / "map.json").is_file()
    m = json.loads((tmp_path / "map.json").read_text())
    assert m["tiles"]["style_url"] == TILES["style_url"]
    assert len(m["markers"]) >= 1
    # one asset JSON per marker, hero reconciling with its marker
    for mk in m["markers"]:
        a = json.loads((tmp_path / "assets" / (mk["slug"] + ".json")).read_text())
        assert a["hero_gbp"] == mk["cost"]
        assert a["slug"] == mk["slug"]


# ---- per-asset X-ray JSONs (site/data/assets/<slug>.json) ----

def _assets():
    mm = _map_model()
    return sitedata._asset_data(mm, sitedata._map_data(mm, COORDS, TILES))


def test_asset_cfd_carries_quarters_contracts_tiles():
    a = _assets()["hornsea-1"]
    assert a["hero_gbp"] == 2.5e9
    assert a["scheme_label"] == "CfD - renewables"
    # the payback quarter survives aggregation unclamped
    q4 = next(q for q in a["quarters"] if q["q"] == "2021-Q4")
    assert q4["payment_gbp"] == -2.0e8
    assert a["contracts"][0]["cfd_id"] == "HOR-1"
    assert a["contracts"][0]["latest_strike_gbp_mwh"] == 158.0
    assert a["tiles"]["generation_mwh"] == 18e6
    assert a["tiles"]["rate_gbp_per_mwh"] == 2.5e9 / 18e6
    assert a["provenance"]["data_to"] == "2026-07-01"


def test_asset_rate_tile_suppressed_without_positive_generation():
    a = _assets()["drax"]
    assert "tiles" not in a
    assert a["strings"]["rate_not_shown"] == sitedata.ASSET_STRINGS["rate_not_shown"]


def test_asset_ro_degrades_honestly():
    a = _assets()["drax-power-station"]
    assert a["hero_gbp"] == 6.4e9
    assert a["scheme_label"] == "Renewables Obligation"
    # no chart, no contract table, no tiles — and no zeroes standing in
    for absent in ("quarters", "contracts", "tiles"):
        assert absent not in a
    assert a["strings"]["basis"] == sitedata.ASSET_STRINGS["ro_basis"]
    assert a["provenance"]["data_to"] == "2025-01-01"


def test_asset_hero_marker_mismatch_fails_loudly():
    mm = _map_model()
    md = sitedata._map_data(mm, COORDS, TILES)
    for mk in md["markers"]:
        if mk["name"] == "Hornsea 1":
            mk["cost"] += 1e6  # far beyond the float-jitter tolerance
    with pytest.raises(ValueError, match="Hornsea 1"):
        sitedata._asset_data(mm, md)


def test_asset_missing_station_detail_fails_loudly():
    mm = _map_model()
    md = sitedata._map_data(mm, COORDS, TILES)
    mm["schemes"][0].extras.pop("station_detail")
    with pytest.raises(ValueError, match="station_detail"):
        sitedata._asset_data(mm, md)


def test_asset_strings_are_pinned():
    # the pin: the page places these verbatim; changing them is an editorial
    # act and must show up here
    s = sitedata.ASSET_STRINGS
    assert s["rate_label"] == "payment per subsidised MWh"
    assert s["hero_label_cfd"] == "cumulative payments"
    assert s["hero_label_ro"] == "cumulative buy-out value"
    assert s["cfd_basis"].startswith("Payments and generation are LCCC daily")
    assert "paid back" in s["cfd_basis"]
    assert s["ro_basis"].startswith("Valued at Renewables Obligation buy-out only")
    assert "understates" in s["ro_basis"]
    assert "not yet shown" in s["ro_basis"]
    assert s["outages_unavailable"] == ("Outage history is not available for "
                                        "this station.")


def test_build_omits_map_json_without_coords(tmp_path):
    sitedata.build(model(), CTX, {}, tmp_path,
                   generated_at="2026-06-17T07:00:00+00:00")
    assert not (tmp_path / "map.json").exists()
