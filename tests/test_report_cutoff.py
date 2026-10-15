"""The hero's three parts: Report No. 1's total to 31 December 2024, the data
published since, and the estimate since each line's data end (Richard, 15 Oct
2026). They must add up to the counter.

The total to the cut-off is computed in sitedata.to_cutoff by the SAME
calendar allocation as the report's cutoff.py (reports-programme
no1-price-of-support): every line on calendar years; the Renewables
Obligation and Feed-in Tariffs, stored by scheme year (April to March, keyed
by the year it starts), split CY(y) = 0.25 x SY(y-1) + 0.75 x SY(y), each part
keeping its scheme year's conversion to 2024 prices. Summed to 2024 that is
every scheme year before 2024 plus three quarters of scheme year 2024-25.
"""
import json
import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import sitedata
from subsidy_engine.money import SchemeResult

ROOT = Path(__file__).parent.parent
DATA = ROOT / "site" / "data"
BN = 1e9

# Report No. 1 figures.json (reports-programme/no1-price-of-support, build
# 2026-10-14T23:53:17Z), vendored 15 Oct 2026
FIGURES = {
    "combined_real": 188381838031.17795,      # £188.38bn, the report's headline
    "combined_nominal": 152985160233.91,      # £152.99bn cash
    "direct_real": 125190191488.30844,        # £125.19bn
    "direct_nominal": 101968752835.92,
    "indirect_real": 63191646542.86949,
    "indirect_nominal": 51016407397.99,
    "published_since_real": 11879329317.283892,   # £11.88bn, 2025 to each data end
    "combined_real_allyears": 200261167348.45795,
}


def _line(sid, years, cash, real=None):
    cols = {"year": years, "cost_gbp": cash}
    if real is not None:
        cols["cost_gbp_2024"] = real
    return SchemeResult(scheme_id=sid, label=sid, perspectives=["renewables"],
                        cadence="annual", annual=pl.DataFrame(cols),
                        cumulative_gbp=float(sum(cash)), runrate_gbp_per_year=1.0,
                        data_to=date(2025, 3, 31), runrate_gbp_per_year_2024=1.0)


def _calendarise(sy: dict) -> dict:
    """The report's cutoff.calendarise, restated independently."""
    return {y: 0.25 * sy.get(y - 1, 0.0) + 0.75 * sy.get(y, 0.0)
            for y in range(min(sy), max(sy) + 2)}


# ---- the allocation rule ----

def test_scheme_year_line_counts_three_quarters_of_the_cutoff_scheme_year():
    ro = _line("ro", [2022, 2023, 2024], [100.0, 200.0, 400.0], [130.0, 210.0, 400.0])
    assert sitedata.to_cutoff(ro) == pytest.approx(100 + 200 + 0.75 * 400)
    assert sitedata.to_cutoff(ro, "cost_gbp_2024") == pytest.approx(130 + 210 + 0.75 * 400)


def test_scheme_year_rule_is_the_reports_calendarisation():
    sy = {2010: 5.0, 2011: 7.0, 2023: 11.0, 2024: 13.0, 2025: 17.0}
    fit = _line("fit", list(sy), list(sy.values()))
    cal = _calendarise(sy)
    assert sitedata.to_cutoff(fit) == pytest.approx(sum(v for y, v in cal.items() if y <= 2024))


def test_calendar_line_counts_to_the_end_of_2024_and_nothing_after():
    cfd = _line("cfd_renewable", [2023, 2024, 2025, 2026], [1.0, 2.0, 4.0, 8.0])
    assert sitedata.to_cutoff(cfd) == pytest.approx(3.0)


def test_totals_carry_to_cutoff_for_every_block(tmp_path):
    ro = _line("ro", [2023, 2024], [10.0, 20.0], [10.0, 20.0])
    cfd = _line("cfd_renewable", [2024, 2025], [3.0, 4.0], [3.0, 4.0])
    ccl = _line("ccl", [2024], [5.0], [5.0])
    ccl.layer = "indirect"
    from subsidy_engine import money
    model = {"schemes": [ro, cfd, ccl], "real_factor": 1.0,
             "perspectives": {"renewables": money._aggregate([ro, cfd])},
             "indirect": money._aggregate([ccl])}
    ctx = {k: {"value": v} for k, v in
           (("households", 29_000_000), ("population", 68_000_000), ("annual_demand_twh", 266))}
    sitedata.build(model, ctx, {}, tmp_path, generated_at="2026-10-14T00:00:00+00:00")
    t = json.loads((tmp_path / "totals.json").read_text())
    d, i = t["perspectives"]["renewables"], t["indirect"]
    assert t["report_cutoff"] == "2024-12-31"
    assert d["to_cutoff"] == pytest.approx(10 + 0.75 * 20 + 3)
    assert d["real"]["to_cutoff"] == pytest.approx(10 + 0.75 * 20 + 3)
    assert i["to_cutoff"] == pytest.approx(5.0)
    bd = json.loads((tmp_path / "breakdown.json").read_text())
    by = {s["id"]: s for s in bd["schemes"]}
    assert by["ro"]["to_cutoff"] == pytest.approx(25.0)
    assert by["cfd_renewable"]["to_cutoff_real"] == pytest.approx(3.0)
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["headline"]["combined_real_to_cutoff"] == pytest.approx(25 + 3 + 5)


# ---- the built site data equals Report No. 1 ----

def _published():
    return (json.loads((DATA / "totals.json").read_text()),
            json.loads((DATA / "meta.json").read_text()),
            json.loads((DATA / "breakdown.json").read_text()))


def test_site_data_to_end_2024_equals_report_figures():
    t, meta, _ = _published()
    d, i = t["perspectives"]["renewables"], t["indirect"]
    tol = 0.01 * BN
    assert abs(d["real"]["to_cutoff"] + i["real"]["to_cutoff"] - FIGURES["combined_real"]) < tol
    assert abs(d["to_cutoff"] + i["to_cutoff"] - FIGURES["combined_nominal"]) < tol
    assert abs(d["real"]["to_cutoff"] - FIGURES["direct_real"]) < tol
    assert abs(d["to_cutoff"] - FIGURES["direct_nominal"]) < tol
    assert abs(i["real"]["to_cutoff"] - FIGURES["indirect_real"]) < tol
    assert abs(i["to_cutoff"] - FIGURES["indirect_nominal"]) < tol
    assert abs(meta["headline"]["combined_real_to_cutoff"] - FIGURES["combined_real"]) < tol
    assert round(meta["headline"]["combined_real_to_cutoff"] / BN, 1) == 188.4


def test_site_data_published_since_equals_report_figure():
    # holds while the published data are those of Report No. 1's build; a later
    # data refresh moves "published since", never the total to the end of 2024
    t, meta, _ = _published()
    if abs(meta["headline"]["combined_real"] - FIGURES["combined_real_allyears"]) > 0.01 * BN:
        pytest.skip("site data refreshed since Report No. 1's build")
    d, i = t["perspectives"]["renewables"]["real"], t["indirect"]["real"]
    since = d["cumulative"] - d["to_cutoff"] + i["cumulative"] - i["to_cutoff"]
    assert abs(since - FIGURES["published_since_real"]) < 0.01 * BN


def test_per_line_to_cutoff_sums_to_the_blocks():
    t, _, bd = _published()
    for key, members in (("renewables", [s for s in bd["schemes"] if s["layer"] == "direct"
                                         and "renewables" in s["perspectives"]]),
                         ("indirect", [s for s in bd["schemes"] if s["layer"] == "indirect"])):
        blk = t["indirect"] if key == "indirect" else t["perspectives"]["renewables"]
        assert sum(s["to_cutoff"] for s in members) == pytest.approx(blk["to_cutoff"])
        assert sum(s["to_cutoff_real"] for s in members) == pytest.approx(blk["real"]["to_cutoff"])


@pytest.mark.parametrize("real", [True, False])
@pytest.mark.parametrize("combined", [True, False])
def test_three_parts_add_to_the_counter_in_every_switch_state(real, combined):
    t, _, _ = _published()
    d = t["perspectives"]["renewables"]
    blocks = [d] + ([t["indirect"]] if combined else [])
    blocks = [b["real"] if real else b for b in blocks]
    to_cut = sum(b["to_cutoff"] for b in blocks)
    since = sum(b["cumulative"] - b["to_cutoff"] for b in blocks)
    est = sum(b["estimated_since"] for b in blocks)
    running = sum(b["running_total"] for b in blocks)
    assert to_cut > 0 and since > 0 and est > 0
    assert to_cut + since + est == pytest.approx(running, rel=1e-12)


def test_hero_line_reads_the_three_parts_from_data():
    js = (ROOT / "site" / "app.js").read_text()
    body = js[js.index("function heroEstLine"):js.index("function renderHeroStatic")]
    assert "to the end of 2024" in body and "published since" in body
    assert "estimated since then" not in body
    # computed from the data, never a hard-coded figure
    assert not re.search(r"£\s*\d", body)
    assert "to_cutoff" in js[js.index("function heroParts"):js.index("function heroEstLine")]
    assert "\u2014" not in body                    # no em-dashes in the subline
