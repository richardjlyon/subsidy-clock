import json
import struct

import pytest

from subsidy_engine import sharecards

TOTALS = {
    "generated_at": "2026-06-11T05:45:00+00:00",
    "perspectives": {
        "renewables": {
            "cumulative_gbp": 108_634_210_556.78,
            "runrate_gbp_per_year": 12_172_272_576.69,
            "rate_gbp_per_sec": 385.72,
            "per_household_per_year_gbp": 428.60,
            "since_year": 2002,
            "real_2024": {"cumulative_gbp": 130_000_000_000.0},
        },
        "low_carbon": {"cumulative_gbp": 1.2e11, "since_year": 2002},
    },
    "indirect": {"cumulative_gbp": 77.5e9,
                 "real_2024": {"cumulative_gbp": 90_000_000_000.0}},
}

BREAKDOWN = {
    "schemes": [
        {"id": "ro", "label": "Renewables Obligation", "layer": "direct",
         "cumulative_gbp": 45.0e9},
        {"id": "constraints", "label": "Paid to switch off (constraints)",
         "layer": "direct", "cumulative_gbp": 2.51e9},
        {"id": "bsuos", "label": "Balancing the grid (BSUoS)", "layer": "indirect",
         "cumulative_gbp": 9.9e9},
    ],
}

TIMESERIES = {
    "schemes": {
        "ro": {"annual": [{"year": 2002, "cost_gbp": 0.0}, {"year": 2003, "cost_gbp": 3.1e8}]},
        "constraints": {"annual": [{"year": 2010, "cost_gbp": 1.7e8}]},
        "bsuos": {"annual": [{"year": 2018, "cost_gbp": 4.0e8}]},
    },
}


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "totals.json").write_text(json.dumps(TOTALS))
    (tmp_path / "breakdown.json").write_text(json.dumps(BREAKDOWN))
    (tmp_path / "timeseries.json").write_text(json.dumps(TIMESERIES))
    return tmp_path


def test_fmt_full_groups_and_floors():
    assert sharecards.fmt_full(108_634_210_556.78) == "£108,634,210,556"


def test_fmt_pence():
    assert sharecards.fmt_pence(428.6) == "£428.60"


def test_fmt_asof():
    assert sharecards.fmt_asof("2026-06-11T05:45:00+00:00") == "11 June 2026"


def test_load_facts_headline_set(data_dir):
    facts, asof, datestr = sharecards.load_facts(data_dir)
    assert asof == "11 June 2026"
    assert datestr == "2026-06-11"
    by_slug = {f["slug"]: f for f in facts}
    # the four stubbed dashboard facts
    for slug in ("total", "run-rate", "household", "switch-off"):
        assert by_slug[slug]["stub"], slug
    assert by_slug["total"]["figure"] == "£108,634,210,556"
    # headline facts land on the page top (masthead visible), not a #total anchor
    for slug in ("total", "run-rate", "household"):
        assert by_slug[slug]["anchor"] is None, slug
    assert "since 2002" in by_slug["total"]["label"]
    assert by_slug["household"]["figure"] == "£428.60"
    assert by_slug["switch-off"]["anchor"] == "switch-off"
    # per-scheme explainer cards, keyed by explainer slug
    assert by_slug["renewables-obligation"]["figure"] == "£45,000,000,000"
    assert "since 2003" in by_slug["renewables-obligation"]["label"]  # first non-zero year
    assert not by_slug["renewables-obligation"]["stub"]
    # indirect scheme cards label themselves estimated
    assert "estimated" in by_slug["bsuos"]["label"]
    # generic brand card for non-dashboard pages
    assert by_slug["site"]["figure"] == by_slug["total"]["figure"]
    assert not by_slug["site"]["stub"]
    # constraints explainer reuses switch-off.png: no separate 'constraints' card
    assert "constraints" not in by_slug


def test_compose_substitutes_all_tokens():
    template = "<html>{{FIGURE}}|{{LABEL}}|{{ASOF}}</html>"
    fact = {"slug": "total", "figure": "£1", "label": "paid", "anchor": "total", "stub": True}
    html = sharecards.compose(template, fact, "11 June 2026")
    assert html == "<html>£1|paid|11 June 2026</html>"


def test_compose_rejects_unfilled_tokens():
    with pytest.raises(ValueError):
        sharecards.compose("<html>{{FIGURE}}{{UNKNOWN}}</html>",
                           {"slug": "x", "figure": "£1", "label": "y",
                            "anchor": None, "stub": False},
                           "11 June 2026")


def test_write_stubs(data_dir, tmp_path):
    facts, asof, datestr = sharecards.load_facts(data_dir)
    out = tmp_path / "s"
    sharecards.write_stubs(facts, out, asof, datestr)
    # one stub per stub-flagged fact, none for explainer/site cards
    assert sorted(p.name for p in out.glob("*.html")) == [
        "household.html", "run-rate.html", "switch-off.html", "the-bill.html", "total.html"]
    html = (out / "switch-off.html").read_text()
    # per-fact OG tags with a dated image URL (defeats platform preview caching)
    assert 'property="og:image" content="https://subsidyclock.co.uk/share/switch-off.png?d=2026-06-11"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert 'property="og:url" content="https://subsidyclock.co.uk/s/switch-off"' in html
    # redirect shim: noindex, meta refresh and JS bounce to the dashboard anchor
    assert 'name="robots" content="noindex"' in html
    assert 'url=https://subsidyclock.co.uk/#switch-off' in html
    assert 'location.replace("https://subsidyclock.co.uk/#switch-off")' in html
    # crawler/JS-off fallback carries the dated figure and a link
    assert "£2,510,000,000" in html
    assert "11 June 2026" in html
    # anchorless facts bounce to the bare page so the masthead stays visible
    total = (out / "total.html").read_text()
    assert 'url=https://subsidyclock.co.uk/"' in total
    assert 'location.replace("https://subsidyclock.co.uk/")' in total


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_load_facts_includes_factoids(data_dir, tmp_path):
    (data_dir / "meta.json").write_text(json.dumps({
        "factoids": [
            {"slug": "hinkley", "figure": "4",
             "sentence": "The £220bn+ full cost of subsidising renewables would have built 4 Hinkley Point C-scale nuclear stations, in today's money.",
             "display_html": "...",
             "label": "Hinkley Point C-scale nuclear stations the £220bn+ full renewables cost would have built, in today's money",
             "source_name": "EDF", "source_url": "https://edf"},
        ],
    }))
    facts, asof, datestr = sharecards.load_facts(data_dir)
    by_slug = {f["slug"]: f for f in facts}
    h = by_slug["hinkley"]
    assert h["figure"] == "4"
    assert h["stub"] is True
    assert h["anchor"] is None
    assert h["label"].startswith("Hinkley Point C-scale")
    out = tmp_path / "s"
    sharecards.write_stubs(facts, out, asof, datestr)
    assert (out / "hinkley.html").is_file()


def test_cumulative_svg_stacks_and_is_monotonic():
    timeseries = {"schemes": {
        "ro": {"annual": [{"year": 2002, "cost_gbp": 0.8e9, "cost_gbp_2024": 1.0e9},
                          {"year": 2003, "cost_gbp": 1.7e9, "cost_gbp_2024": 2.0e9}]},
        "bsuos": {"annual": [{"year": 2003, "cost_gbp": 0.4e9, "cost_gbp_2024": 0.5e9}]},
    }}
    svg = sharecards.cumulative_svg(timeseries, ["ro", "bsuos"])
    assert svg.startswith("<svg")
    # 2002: one segment (ro=1bn); 2003: ro=3bn cumulative + bsuos=0.5bn
    assert svg.count("<rect") == 3
    assert "#990f3d" in svg     # ro colour (claret headline)
    assert "#c5dae6" in svg     # bsuos colour (palest sky)


def test_cumulative_svg_uses_real_2024_series():
    # nominal kept tiny: if the svg stacked cost_gbp the £40bn gridline
    # could not exist
    timeseries = {"schemes": {
        "ro": {"annual": [{"year": 2002, "cost_gbp": 1.0e9, "cost_gbp_2024": 60.0e9}]},
    }}
    svg = sharecards.cumulative_svg(timeseries, ["ro"])
    assert "£40bn" in svg


def test_cumulative_svg_excludes_non_member_schemes():
    timeseries = {"schemes": {
        "ro": {"annual": [{"year": 2002, "cost_gbp": 1.0e9, "cost_gbp_2024": 1.1e9}]},
        "cfd_low_carbon": {"annual": [{"year": 2002, "cost_gbp": 9.0e9, "cost_gbp_2024": 9.9e9}]},
    }}
    svg = sharecards.cumulative_svg(timeseries, ["ro"])
    assert svg.count("<rect") == 1
    assert "#855417" not in svg   # cfd_low_carbon colour absent


def test_load_facts_includes_the_bill_chart_fact(data_dir):
    facts, asof, datestr = sharecards.load_facts(data_dir)
    bill = next(f for f in facts if f["slug"] == "the-bill")
    assert bill["stub"] is True
    assert bill["anchor"] == "cost-per-year"
    assert bill["chart"] is True
    # real-basis: 130bn + 90bn combined-real, NOT the nominal 108.6+77.5
    assert bill["figure"] == "£220,000,000,000"
    assert "today’s money" in bill["label"]


def test_render_chart_card_produces_1200x630_png(tmp_path):
    pytest.importorskip("playwright.sync_api")
    timeseries = {"schemes": {
        "ro": {"annual": [{"year": 2002, "cost_gbp": 1.0e9, "cost_gbp_2024": 1.2e9},
                          {"year": 2003, "cost_gbp": 2.0e9, "cost_gbp_2024": 2.3e9}]},
    }}
    fact = {"slug": "the-bill", "chart": True}
    sharecards.render_chart_card(timeseries, ["ro"], fact, "12 June 2026", tmp_path)
    try:
        assert _png_size(tmp_path / "the-bill.png") == (1200, 630)
    except Exception as exc:
        if "playwright install" in str(exc).lower() or "executable" in str(exc).lower():
            pytest.skip(f"chromium unavailable: {exc}")
        raise


def test_render_produces_1200x630_pngs(data_dir, tmp_path):
    pytest.importorskip("playwright.sync_api")
    facts, asof, _ = sharecards.load_facts(data_dir)
    only_total = [f for f in facts if f["slug"] == "total"]
    out = tmp_path / "share"
    try:
        sharecards.render(only_total, asof, out)
    except Exception as exc:  # chromium not installed on this machine
        if "playwright install" in str(exc).lower() or "executable" in str(exc).lower():
            pytest.skip(f"chromium unavailable: {exc}")
        raise
    assert _png_size(out / "total.png") == (1200, 630)


def test_load_facts_includes_headline_card(data_dir):
    (data_dir / "meta.json").write_text(json.dumps(
        {"headline": {"combined_real_gbp": 226_966_081_251.12},
         "factoids": []}))
    facts, _, _ = sharecards.load_facts(data_dir)
    # headline leads the grid and shows the FULL figure (every significant figure)
    assert facts[0]["slug"] == "headline"
    headline = facts[0]
    assert headline["figure"] == sharecards.fmt_full(226_966_081_251.12)  # "£226,966,081,251"
    assert headline["stub"] is True
    assert headline.get("chart") is not True
