"""The scheme registry: one entry per scheme with its publishing settings (aios-harness#51).

app.js and the stylesheets keep their own copies of the names, slugs, colours and stack
order; these tests fail if any copy differs from the registry."""
import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from subsidy_engine import schemes, sharecards, sitedata
from subsidy_engine.money import SchemeResult

SITE = Path(__file__).parent.parent / "site"
APP = (SITE / "app.js").read_text()


def _css_colours() -> dict[str, str]:
    """Each --c-* colour as the pages show it: skin-ft.css loads after style.css."""
    out = {}
    for sheet in ("style.css", "skin-ft.css"):
        for var, hexv in re.findall(r"(--c-[\w-]+):\s*(#[0-9a-fA-F]{6})", (SITE / sheet).read_text()):
            out[var] = hexv.lower()
    return out


def test_every_page_that_loads_style_css_loads_skin_ft_css_after_it():
    for page in SITE.rglob("*.html"):
        if "data" in page.parts:
            continue
        text = page.read_text()
        if "style.css" in text:
            assert text.find("skin-ft.css") > text.find("style.css"), page


def test_the_stack_order_in_app_js_is_the_registry_order():
    block = re.search(r"var STACK_ORDER = \[(.*?)\];", APP, re.S).group(1)
    assert re.findall(r"'(\w+)'", block) == [s.id for s in schemes.SCHEMES]


def test_app_js_names_slugs_and_colours_match_the_registry():
    meta = {m[0]: m[1:] for m in re.findall(
        r"(\w+):\s*\{\s*slug:\s*'([^']*)',\s*name:\s*'([^']*)',\s*color:\s*'var\((--c-[\w-]+)\)'",
        APP)}
    block = re.search(r"var SCHEME_COLOURS = \{(.*?)\};", APP, re.S).group(1)
    colour_vars = dict(re.findall(r"(\w+): 'var\((--c-[\w-]+)\)'", block))
    css = _css_colours()
    assert set(meta) == set(colour_vars) == {s.id for s in schemes.SCHEMES}
    for s in schemes.SCHEMES:
        slug, name, var = meta[s.id]
        assert (slug, name) == (s.slug, s.name), s.id
        assert colour_vars[s.id] == var, s.id
        assert css[var] == s.colour, s.id


def test_a_scheme_missing_from_the_registry_fails_naming_it():
    with pytest.raises(ValueError, match="mystery.*not in the scheme registry"):
        schemes.get("mystery")


def _result(sid, layer="direct", perspectives=("renewables",)):
    return SchemeResult(scheme_id=sid, label=sid, perspectives=list(perspectives),
                        cadence="annual", layer=layer, cumulative_gbp=1.0,
                        runrate_gbp_per_year=1.0, data_to=date(2024, 12, 31),
                        annual=pl.DataFrame({"year": [2024], "cost_gbp": [1.0],
                                             "cost_gbp_2024": [1.0]}))


def test_csvs_for_an_unregistered_scheme_fail_rather_than_take_the_scheme_id(tmp_path):
    model = {"schemes": [_result("mystery")]}
    with pytest.raises(ValueError, match="mystery"):
        sitedata.write_csvs(model, tmp_path, restatements=[], generated="2026-11-01T00:00:00+00:00")


def test_chart_members_are_indirect_schemes_and_direct_ones_carrying_renewables():
    breakdown = {"schemes": [
        {"id": "ro", "layer": "direct", "perspectives": ["renewables", "low_carbon"]},
        {"id": "cfd_low_carbon", "layer": "direct", "perspectives": ["low_carbon"]},
        {"id": "bsuos", "layer": "indirect", "perspectives": []}]}
    assert sharecards.chart_members(breakdown) == ["ro", "bsuos"]


def test_the_chart_card_draws_each_scheme_in_its_registry_colour():
    ts = {"schemes": {sid: {"annual": [{"year": 2024, "cost_real": 1.0e9}]}
                      for sid in ("ro", "bsuos")}}
    svg = sharecards.cumulative_svg(ts, ["ro", "bsuos"])
    assert schemes.get("ro").colour in svg and schemes.get("bsuos").colour in svg
