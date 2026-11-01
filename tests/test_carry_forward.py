"""Per-line carry-forward (Richard, 15 Oct 2026, confirmed 1 Nov; ported from origin/model-pin 1ab8bdd4 in
aios-harness#46). The 14 Oct fixture is the old paper build: it tests the mechanism, not today's figures.

The Clock starts from the published figures (each line counted to its own
latest official data) and carries EACH line forward at its latest annual rate
from THAT line's data end. At the build date of Report No. 1 / Technical Paper
No. 1 (14 Oct 2026) it must equal the paper's "lag added" total (§8.1, Table
10.2) in cash and in 2024 prices to within £0.01bn; and when a line's data_to
moves forward its estimate is replaced by the published data, not added to it.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import money, sitedata
from subsidy_engine.money import SchemeResult

FIX = json.loads((Path(__file__).parent / "data_tp1_lag_2026-10-14.json").read_text())
FACTOR = FIX["cpih_2024"] / FIX["cpih_2025"]          # 2025 index -> 2024 prices
BN = 1e9
CTX = {
    "households": {"value": 28_400_000, "source": "ONS", "source_url": "https://ons", "as_of": 2025},
    "population": {"value": 68_300_000, "source": "ONS", "source_url": "https://ons", "as_of": 2025},
    "annual_demand_twh": {"value": 266, "source": "DESNZ", "source_url": "https://desnz", "as_of": 2024},
}


# the fixture predates the carbon line (aios-harness#44): its ETS line stands in for carbon
_IDS = {"ets": "carbon"}


def _scheme(line: dict, *, data_to: date | None = None, cumulative: float | None = None) -> SchemeResult:
    cum = line["cumulative"] if cumulative is None else cumulative
    sid = _IDS.get(line["id"], line["id"])
    # every field the page contract (#52) requires for this scheme, as placeholders
    extras = {k: [] for k in sitedata.SCHEME_FIELDS[sid][0]}
    return SchemeResult(
        extras=extras,
        scheme_id=sid, label=sid, perspectives=["renewables"],
        cadence="annual", layer=line["layer"],
        annual=pl.DataFrame({"year": [2024], "cost_gbp": [cum], "cost_gbp_2024": [cum]}),
        cumulative_gbp=cum, runrate_gbp_per_year=line["runrate_per_year"],
        data_to=data_to or date.fromisoformat(line["data_to"]))


def _model(schemes: list[SchemeResult], published_real: float) -> dict:
    direct = [s for s in schemes if s.layer == "direct"]
    indirect = [s for s in schemes if s.layer == "indirect"]

    def block(members, real_cum):
        rr = sum(s.runrate_gbp_per_year for s in members)
        return {"cumulative_gbp": sum(s.cumulative_gbp for s in members),
                "cumulative_gbp_2024": real_cum,
                "runrate_gbp_per_year": rr, "rate_gbp_per_sec": money.rate_per_second(rr),
                "runrate_gbp_per_year_2024": rr * FACTOR,
                "rate_gbp_per_sec_2024": money.rate_per_second(rr) * FACTOR,
                "since_year": 2002, "annual": pl.DataFrame({"year": [2024], "cost_gbp": [0.0]})}
    # split the published real headline between the layers in proportion
    # to cash (only the sum is asserted)
    cash_d = sum(s.cumulative_gbp for s in direct)
    cash_all = cash_d + sum(s.cumulative_gbp for s in indirect)
    real_d = published_real * cash_d / cash_all
    return {"schemes": schemes, "real_factor": FACTOR,
            "perspectives": {"renewables": block(direct, real_d)},
            "indirect": block(indirect, published_real - real_d)}


def _live(block: dict, at: datetime) -> float:
    """The site's rule (app.js blockLive): published + sum over lines of
    rate_per_sec x max(0, t - from)."""
    return block["cumulative"] + sum(
        l["rate_per_sec"] * max(0.0, (at - datetime.fromisoformat(l["from"])).total_seconds())
        for l in block["carry_forward"])


def test_estimated_since_is_the_paper_lag_rule_line_by_line():
    # the paper: lag = rate x (build date - data end) / 365.25. The Clock's
    # estimate starts at the end of data_to, so it equals the paper's lag at
    # the end of the build day (00:00 UTC 15 Oct) to the penny.
    end_of_build_day = datetime(2026, 10, 15, tzinfo=timezone.utc)
    for line in FIX["lines"]:
        e = money.estimated_since(line["runrate_per_year"],
                                  date.fromisoformat(line["data_to"]), end_of_build_day)
        assert e == pytest.approx(line["lag"], abs=0.01), line["id"]


def test_clock_at_14_oct_build_equals_paper_lag_added_total(tmp_path):
    build = FIX["build"]                               # 2026-10-14T23:53:17Z
    m = _model([_scheme(l) for l in FIX["lines"]], FIX["combined_real"])
    sitedata.build(m, CTX, {}, tmp_path, generated_at=build)
    totals = json.loads((tmp_path / "totals.json").read_text())
    meta = json.loads((tmp_path / "meta.json").read_text())
    d, i = totals["perspectives"]["renewables"], totals["indirect"]

    # published figures are untouched: the report reads `cumulative`
    assert d["real"]["cumulative"] + i["real"]["cumulative"] == pytest.approx(FIX["combined_real"])
    assert meta["headline"]["combined_real"] == pytest.approx(FIX["combined_real"])

    paper_cash = FIX["combined_nominal"] + FIX["lag_total_nominal"]
    paper_real = FIX["combined_real"] + FIX["lag_total_nominal"] * FACTOR
    assert round(paper_real / BN, 2) == FIX["table_10_2_lag_added_real_bn"]   # Table 10.2: 220.19

    for at in (datetime.fromisoformat(build),                          # the build instant
               datetime(2026, 10, 15, tzinfo=timezone.utc)):            # end of the build day
        cash = _live(d, at) + _live(i, at)
        real = _live(d["real"], at) + _live(i["real"], at)
        assert abs(cash - paper_cash) < 0.01 * BN, at
        assert abs(real - paper_real) < 0.01 * BN, at
    # the stamped running total (hero at the build instant, widget, share cards, factoids)
    assert abs(meta["headline"]["combined_real_running"] - paper_real) < 0.01 * BN
    assert abs(sitedata.running_total(d["real"]) + sitedata.running_total(i["real"])
               - paper_real) < 0.01 * BN
    assert abs(d["estimated_since"] + i["estimated_since"] - FIX["lag_total_nominal"]) < 0.01 * BN

    # per-line fields exposed in breakdown.json
    bd = json.loads((tmp_path / "breakdown.json").read_text())
    for s in bd["schemes"]:
        cf = s["carry_forward"]
        assert set(cf) >= {"published_cumulative", "data_to", "rate_per_year",
                           "rate_per_sec", "estimated_since", "estimated_since_real"}
        assert cf["published_cumulative"] == s["cumulative"]


def test_a_line_whose_data_move_forward_has_its_estimate_replaced_not_added(tmp_path):
    # RO: data to 31 Mar 2025 in build 1. Build 2: Ofgem publishes SY24, so RO
    # data reach 31 Mar 2026 and the published cumulative rises by that year.
    ro = next(l for l in FIX["lines"] if l["id"] == "ro")
    others = [l for l in FIX["lines"] if l["id"] != "ro"]
    at = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)

    def run(ro_scheme, sub):
        m = _model([ro_scheme] + [_scheme(l) for l in others], FIX["combined_real"])
        sitedata.build(m, CTX, {}, tmp_path / sub, generated_at=at.isoformat())
        t = json.loads((tmp_path / sub / "totals.json").read_text())
        d = t["perspectives"]["renewables"]
        line = next(l for l in d["carry_forward"] if l["id"] == "ro")
        return _live(d, at), line, d

    live1, line1, d1 = run(_scheme(ro), "b1")
    # the published year equals what the estimate had assumed for it
    new_to = date(2026, 3, 31)
    year = ro["runrate_per_year"] * (new_to - date(2025, 3, 31)).days / 365.25
    live2, line2, d2 = run(_scheme(ro, data_to=new_to, cumulative=ro["cumulative"] + year), "b2")

    # the estimate now starts at the NEW data end: only 31 Mar 2026 to now
    assert line2["data_to"] == "2026-03-31"
    assert line2["from"] == "2026-04-01T00:00:00+00:00"
    assert line2["estimated_since"] == pytest.approx(
        ro["runrate_per_year"] * (at - datetime(2026, 4, 1, tzinfo=timezone.utc)).total_seconds()
        / money.SECONDS_PER_YEAR)
    assert line2["estimated_since"] < line1["estimated_since"] - year + 1.0
    # published + estimate is unchanged: the year moved from estimate to
    # published, it was not counted twice
    assert live2 == pytest.approx(live1, abs=1.0)
    assert d2["cumulative"] - d1["cumulative"] == pytest.approx(year)
    # and if the published year differs from the estimate, the total moves by
    # exactly the difference (published replaces estimate)
    live3, _, _ = run(_scheme(ro, data_to=new_to, cumulative=ro["cumulative"] + year + 5e8), "b3")
    assert live3 - live1 == pytest.approx(5e8, abs=1.0)


def test_a_line_with_data_past_the_build_carries_nothing():
    to = date(2026, 10, 20)
    assert money.estimated_since(1e9, to, datetime(2026, 10, 15, tzinfo=timezone.utc)) == 0.0
    assert money.estimated_since(1e9, None, datetime(2026, 10, 15, tzinfo=timezone.utc)) == 0.0
    assert money.carry_from(to) == datetime(2026, 10, 21, tzinfo=timezone.utc)
    # one day after the end of data, exactly one day at the rate
    assert money.estimated_since(365.25e6, to, datetime(2026, 10, 22, tzinfo=timezone.utc)) \
        == pytest.approx(1e6)


def test_widget_stamps_running_total(tmp_path):
    m = _model([_scheme(l) for l in FIX["lines"]], FIX["combined_real"])
    sitedata.build(m, CTX, {}, tmp_path, generated_at=FIX["build"])
    totals = json.loads((tmp_path / "totals.json").read_text())
    sitedata.write_widget(totals, tmp_path / "widget.html")
    html = (tmp_path / "widget.html").read_text()
    run = (sitedata.running_total(totals["perspectives"]["renewables"]["real"])
           + sitedata.running_total(totals["indirect"]["real"]))
    assert f"£{int(run):,}" in html
    assert run > FIX["combined_real"] + 19 * BN


# ---- the real build (aios-harness#46) ----

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from subsidy_engine_uk import inputs
    root = Path(__file__).resolve().parents[1]
    inp = inputs.load(root)
    model = inputs.assemble_model(root, inp)[0]
    out = tmp_path_factory.mktemp("site")
    at = "2026-11-01T12:00:00+00:00"
    sitedata.build(model, inp.ctx, {}, out, generated_at=at, deflators=inp.deflators)
    return model, out, datetime.fromisoformat(at)


def test_each_line_carries_from_its_own_data_end_at_its_own_rate(built):
    model, out, at = built
    bd = {s["id"]: s for s in json.loads((out / "breakdown.json").read_text())["schemes"]}
    for s in model["schemes"]:
        cf = bd[s.scheme_id]["carry_forward"]
        assert cf["label"] == "estimated" and cf["published_cumulative"] == s.cumulative_gbp
        if s.carry_with:
            continue
        assert cf["data_to"] == s.data_to.isoformat()
        assert cf["rate_per_year"] == s.runrate_gbp_per_year
        assert cf["estimated_since"] == pytest.approx(
            money.estimated_since(s.runrate_gbp_per_year, s.data_to, at))
    # carbon (engine to 2024) carries from 1 Jan 2025 at the 2024 rate
    c = next(s for s in model["schemes"] if s.scheme_id == "carbon")
    assert bd["carbon"]["carry_forward"]["from"] == "2025-01-01T00:00:00+00:00"
    assert c.runrate_gbp_per_year == {r["year"]: r["cost_gbp"] for r in c.annual.to_dicts()}[2024]
    # the Capacity Market's latest month is counted whole: its estimate starts after it
    cm = bd["capacity_market"]["carry_forward"]["data_to"]
    assert (date.fromisoformat(cm) + timedelta(days=1)).day == 1      # the last day of a month


def test_vat_carries_with_the_lines_it_is_on(built):
    model, out, at = built
    by = {s.scheme_id: s for s in model["schemes"]}
    vat = by["vat"]
    expected = sum(f * money.estimated_since(by[sid].runrate_gbp_per_year, by[sid].data_to, at)
                   for sid, f in vat.carry_with.items())
    bd = {s["id"]: s for s in json.loads((out / "breakdown.json").read_text())["schemes"]}
    assert bd["vat"]["carry_forward"]["estimated_since"] == pytest.approx(expected)
    assert {l["id"] for l in bd["vat"]["carry_forward"]["with_lines"]} == {f"vat:{k}" for k in vat.carry_with}


def test_totals_running_total_is_published_plus_every_lines_estimate(built):
    model, out, at = built
    t = json.loads((out / "totals.json").read_text())
    for b in [*t["perspectives"].values(), t["indirect"]]:
        for blk in (b, b["real"]):
            assert blk["published_cumulative"] == blk["cumulative"]
            assert blk["running_total"] == pytest.approx(
                blk["cumulative"] + sum(l["estimated_since"] for l in blk["carry_forward"]))
            assert _live(blk, at) == pytest.approx(blk["running_total"], rel=1e-12)
    meta = json.loads((out / "meta.json").read_text())
    assert meta["headline"]["combined_real_running"] == pytest.approx(
        t["perspectives"]["renewables"]["real"]["running_total"] + t["indirect"]["real"]["running_total"])
    # per-year series stay published only
    ts = json.loads((out / "timeseries.json").read_text())
    ro = next(s for s in model["schemes"] if s.scheme_id == "ro")
    assert sum(r["cost"] for r in ts["schemes"]["ro"]["annual"]) == pytest.approx(ro.cumulative_gbp)
