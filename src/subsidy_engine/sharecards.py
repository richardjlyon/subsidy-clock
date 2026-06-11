"""Share cards (distribution F1): OG-image PNGs and share-stub pages,
regenerated daily from the published site JSON so cards can never
disagree with the dashboard. Conservative-number rule: figures are
renewables-only, nominal, direct-measured unless the card's own label
says otherwise."""

from __future__ import annotations

import html as _html
import json
import math
from datetime import datetime
from pathlib import Path

TEMPLATES = Path(__file__).parent / "templates"
SITE_URL = "https://subsidyclock.co.uk"

# explainer slug + display name per scheme id (mirrors SCHEME_META in site/app.js)
EXPLAINERS = {
    "ro":              ("renewables-obligation",    "Renewables Obligation"),
    "fit":             ("feed-in-tariffs",          "Feed-in Tariffs"),
    "cfd_renewable":   ("contracts-for-difference", "Contracts for Difference"),
    "cfd_low_carbon":  ("cfd-nuclear-biomass",      "CfD — nuclear & biomass"),
    "capacity_market": ("capacity-market",          "Capacity Market"),
    "ccl":             ("climate-change-levy",      "Climate Change Levy"),
    "bsuos":           ("bsuos",                    "Balancing the grid (BSUoS)"),
    "ets":             ("emissions-trading",        "Emissions trading"),
    "tnuos":           ("tnuos",                    "Grid upgrades for renewables (TNUoS)"),
    # constraints explainer reuses the switch-off dashboard card
}


def fmt_full(v: float) -> str:
    return f"£{math.floor(v):,}"


def fmt_pence(v: float) -> str:
    return f"£{v:,.2f}"


def fmt_asof(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def _first_year(timeseries: dict, scheme_id: str) -> int | None:
    annual = timeseries.get("schemes", {}).get(scheme_id, {}).get("annual", [])
    years = [a["year"] for a in annual if a.get("cost_gbp")]
    return min(years) if years else None


def load_facts(data_dir: Path | str) -> tuple[list[dict], str, str]:
    """Returns (facts, asof_display, asof_date). Each fact:
    {slug, figure, label, anchor, stub} — stub=True gets a /s/ share page."""
    data = Path(data_dir)
    totals = json.loads((data / "totals.json").read_text())
    breakdown = json.loads((data / "breakdown.json").read_text())
    timeseries = json.loads((data / "timeseries.json").read_text())
    r = totals["perspectives"]["renewables"]
    asof = fmt_asof(totals["generated_at"])
    datestr = datetime.fromisoformat(totals["generated_at"]).strftime("%Y-%m-%d")

    total_figure = fmt_full(r["cumulative_gbp"])
    facts = [
        {"slug": "total", "figure": total_figure,
         "label": "paid to renewable electricity generators by Great Britain's "
                  f"bill-payers since {r['since_year']}",
         "anchor": "total", "stub": True},
        {"slug": "run-rate", "figure": fmt_full(r["runrate_gbp_per_year"]),
         "label": "a year — the current run-rate of direct subsidy "
                  "to renewable electricity generators",
         "anchor": "total", "stub": True},
        {"slug": "household", "figure": fmt_pence(r["per_household_per_year_gbp"]),
         "label": "per household per year in direct subsidy "
                  "to renewable electricity generators",
         "anchor": "total", "stub": True},
        {"slug": "site", "figure": total_figure,
         "label": "the running total of direct UK renewable-energy subsidy "
                  f"since {r['since_year']}, counted live",
         "anchor": None, "stub": False},
    ]

    by_id = {s["id"]: s for s in breakdown["schemes"]}
    if "constraints" in by_id:
        con = by_id["constraints"]
        first = _first_year(timeseries, "constraints")
        facts.append({"slug": "switch-off", "figure": fmt_full(con["cumulative_gbp"]),
                      "label": "paid to wind farms to reduce output when the grid "
                               f"could not carry their electricity, since {first or 2010}",
                      "anchor": "switch-off", "stub": True})

    for scheme_id, (slug, name) in EXPLAINERS.items():
        s = by_id.get(scheme_id)
        if not s:
            continue
        first = _first_year(timeseries, scheme_id)
        since = f" since {first}" if first else ""
        estimated = ", estimated" if s["layer"] == "indirect" else ""
        facts.append({"slug": slug, "figure": fmt_full(s["cumulative_gbp"]),
                      "label": f"{name} — cumulative cost{since}{estimated}",
                      "anchor": None, "stub": False})
    return facts, asof, datestr


# NOTE: substituted with str.format() - any literal braces added later
# (e.g. a <style> block) must be escaped as {{ and }}.
STUB_TEMPLATE = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex">
<title>{title} — The Subsidy Clock</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Subsidy Clock">
<meta property="og:url" content="{stub_url}">
<meta property="og:image" content="{image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{site_url}/">
<meta http-equiv="refresh" content="0;url={target}">
</head>
<body>
<p>{figure} {label} (as of {asof}) — <a href="{target}">The Subsidy Clock</a>.</p>
<script>location.replace({target_js});</script>
</body>
</html>
"""


def write_stubs(facts: list[dict], out_dir: Path | str, asof: str, datestr: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for fact in facts:
        if not fact.get("stub"):
            continue
        target = f"{SITE_URL}/#{fact['anchor']}"
        html = STUB_TEMPLATE.format(
            title=_html.escape(f"{fact['figure']} {fact['label']}"),
            description=_html.escape(f"As of {asof}. Every figure traces to an official source."),
            stub_url=f"{SITE_URL}/s/{fact['slug']}",
            image_url=f"{SITE_URL}/share/{fact['slug']}.png?d={datestr}",
            site_url=SITE_URL,
            target=target,
            target_js=json.dumps(target),
            figure=fact["figure"],
            label=_html.escape(fact["label"]),
            asof=asof,
        )
        (out / f"{fact['slug']}.html").write_text(html)


def render(facts: list[dict], asof: str, out_dir: Path | str) -> None:
    """Screenshot one 1200x630 PNG per fact. Chromium renders a composed copy
    of the template from a temp dir (file:// URL so the vendored fonts load)."""
    import shutil
    import tempfile

    from playwright.sync_api import sync_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    template = (TEMPLATES / "sharecard.html").read_text()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copytree(TEMPLATES / "fonts", tmp / "fonts")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            for fact in facts:
                src = tmp / f"{fact['slug']}.html"
                src.write_text(compose(template, fact, asof))
                page.goto(src.as_uri(), wait_until="networkidle")
                page.evaluate("() => document.fonts.ready")
                page.screenshot(path=str(out / f"{fact['slug']}.png"))
            browser.close()


def compose(template: str, fact: dict, asof: str) -> str:
    html = (template
            .replace("{{FIGURE}}", fact["figure"])
            .replace("{{LABEL}}", fact["label"])
            .replace("{{ASOF}}", asof))
    if "{{" in html:
        raise ValueError("unfilled template token in share card HTML")
    return html
