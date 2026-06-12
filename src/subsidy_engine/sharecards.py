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

# Hex values mirror the --c-* variables in site/style.css and the stack
# order mirrors STACK_ORDER in site/app.js renderChart - keep all three
# in step (CSS vars are not available inside the card template).
CHART_STACK = [
    ("ro", "#6f2014"), ("fit", "#99412c"), ("cfd_renewable", "#bb6647"),
    ("cfd_low_carbon", "#d48f6b"), ("constraints", "#e7b896"),
    ("capacity_market", "#5f8098"), ("ccl", "#2e4a5e"), ("ets", "#46677e"),
    ("tnuos", "#84a3b8"), ("bsuos", "#b3c8d8"),
]

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


def cumulative_svg(timeseries: dict, member_ids: list[str],
                   width: int = 1072, height: int = 400) -> str:
    """Stacked cumulative bars (the dashboard chart's default view) as a
    static SVG for the chart share card - a deliberate small
    re-implementation of renderChart's cumulative view in site/app.js.
    member_ids restricts the stack to the schemes the dashboard chart
    shows under the renewables perspective (the caller computes it from
    breakdown.json), so the card can never stack schemes the figure it
    accompanies excludes."""
    schemes = timeseries["schemes"]
    member = [(sid, col) for sid, col in CHART_STACK
              if sid in member_ids and sid in schemes]
    years = sorted({a["year"] for sid, _ in member for a in schemes[sid]["annual"]})
    cum: dict[str, dict[int, float]] = {}
    for sid, _ in member:
        by_year = {a["year"]: a["cost_gbp"] for a in schemes[sid]["annual"]}
        run, series = 0.0, {}
        for y in years:
            run += by_year.get(y, 0.0)
            series[y] = run
        cum[sid] = series
    max_stack = max(
        sum(max(cum[sid][y], 0.0) for sid, _ in member) for y in years)
    ml, mr, mt, mb = 70, 6, 8, 34
    plot_w, plot_h = width - ml - mr, height - mt - mb
    band = plot_w / len(years)
    bar = band * 0.74

    def ypos(v: float) -> float:
        return mt + plot_h * (1 - v / max_stack)

    step = 50e9 if max_stack > 120e9 else 20e9
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">']
    g = step
    while g <= max_stack:
        gy = ypos(g)
        parts.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{width - mr}" y2="{gy:.1f}" '
                     'stroke="#e4dfd2" stroke-width="1"/>')
        parts.append(f'<text x="{ml - 8}" y="{gy + 5:.1f}" text-anchor="end" '
                     f'font-size="17" fill="#6e6a5f">£{int(g / 1e9)}bn</text>')
        g += step
    for i, y in enumerate(years):
        x = ml + band * i + (band - bar) / 2
        acc = 0.0
        for sid, col in member:
            v = cum[sid][y]
            if v <= 0:
                continue
            y0 = ypos(acc + v)
            h = ypos(acc) - y0
            acc += v
            if h < 0.1:
                continue
            parts.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bar:.1f}" '
                         f'height="{h:.1f}" fill="{col}"/>')
        if y % 4 == 2 or y == years[-1]:
            parts.append(f'<text x="{ml + band * i + band / 2:.1f}" y="{height - 8}" '
                         f'text-anchor="middle" font-size="17" fill="#6e6a5f">{y}</text>')
    parts.append("</svg>")
    return "".join(parts)


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
        # headline facts carry no anchor: their stubs bounce to the page top
        # so first-time visitors arrive with the masthead visible
        {"slug": "total", "figure": total_figure,
         "label": "paid to renewable electricity generators by Great Britain's "
                  f"bill-payers since {r['since_year']}",
         "anchor": None, "stub": True},
        {"slug": "run-rate", "figure": fmt_full(r["runrate_gbp_per_year"]),
         "label": "a year — the current run-rate of direct subsidy "
                  "to renewable electricity generators",
         "anchor": None, "stub": True},
        {"slug": "household", "figure": fmt_pence(r["per_household_per_year_gbp"]),
         "label": "per household per year in direct subsidy "
                  "to renewable electricity generators",
         "anchor": None, "stub": True},
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
    indirect = totals.get("indirect")
    if indirect:
        combined = r["cumulative_gbp"] + indirect["cumulative_gbp"]
        facts.append({"slug": "the-bill", "figure": fmt_full(combined),
                      "label": "the cumulative cost of direct and estimated indirect "
                               f"support for renewables since {r['since_year']}",
                      "anchor": "cost-per-year", "stub": True, "chart": True})

    # Factoid figures are pre-composed by sitedata.py (floored divisions,
    # deflation) and published in meta.json - reading them here keeps card,
    # stub and dashboard wording identical without re-running the maths.
    meta_path = data / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text())
        for f in meta.get("factoids", []):
            facts.append({"slug": f["slug"], "figure": f["figure"],
                          "label": f["label"], "anchor": None, "stub": True})
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
        target = f"{SITE_URL}/#{fact['anchor']}" if fact["anchor"] else f"{SITE_URL}/"
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
                # chart cards are rendered by render_chart_card
                if fact.get("chart"):
                    continue
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


def render_chart_card(timeseries: dict, member_ids: list[str], fact: dict,
                      asof: str, out_dir: Path | str) -> None:
    """Screenshot the cumulative-bars chart card (the dashboard's default
    view); member_ids is passed through to cumulative_svg."""
    import shutil
    import tempfile

    from playwright.sync_api import sync_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    template = (TEMPLATES / "sharecard-chart.html").read_text()
    html = (template
            .replace("{{TITLE}}", "The bill since 2002")
            .replace("{{SVG}}", cumulative_svg(timeseries, member_ids))
            .replace("{{ASOF}}", asof))
    if "{{" in html:
        raise ValueError("unfilled template token in chart card HTML")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copytree(TEMPLATES / "fonts", tmp / "fonts")
        src = tmp / f"{fact['slug']}.html"
        src.write_text(html)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(src.as_uri(), wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")
            page.screenshot(path=str(out / f"{fact['slug']}.png"))
            browser.close()
