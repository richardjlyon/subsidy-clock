"""Share cards (distribution F1): OG-image PNGs and share-stub pages,
regenerated daily from the published site JSON so cards can never
disagree with the dashboard. Conservative-number rule: figures are
renewables-only, nominal, direct-measured unless the card's own label
says otherwise."""

from __future__ import annotations

import json
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
    return f"£{int(v):,}"


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


def compose(template: str, fact: dict, asof: str) -> str:
    html = (template
            .replace("{{FIGURE}}", fact["figure"])
            .replace("{{LABEL}}", fact["label"])
            .replace("{{ASOF}}", asof))
    if "{{" in html:
        raise ValueError("unfilled template token in share card HTML")
    return html
