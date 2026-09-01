"""Share-card TEXT layer for the golden master — no Playwright, no PNGs.

Reproduces every text surface cmd_build_cards (subsidy_engine_uk/cli.py)
produces, without screenshotting and without writing inside the repo:

  s/<name>.html    share-stub pages       (sharecards.write_stubs -> tempdir)
  share/cards.json manifest               (sharecards.write_manifest -> tempdir)
  card/<slug>.html composed card HTML     (sharecards.compose — the GBP figures
                                           and labels that get screenshotted)
  chart/svg        cumulative-bars SVG    (sharecards.cumulative_svg, member_ids
                                           computed exactly as cmd_build_cards)
  chart/card.html  composed chart card    (as render_chart_card composes it)

asof is passed as the literal 'PINNED' so the clock-derived date is replaced at
source (no regex pinning needed). versions come from the COMMITTED share PNGs
(png_versions) — never regenerated here; their content hashes feed the ?v=
cache-bust tokens and must stay stable.

Run from the repo root: uv run python tools/sharecard_text.py. Prints ONE JSON
object (surface-name -> text) to stdout; golden_master.py merges it into the
snapshot under 'cards:'-prefixed keys.

History: revived 2026-09-01 from the archived Phase 1 copy, which imported a
superseded API (subsidy_engine_uk.cards, siteconfig.UK, a currency argument to
cumulative_svg). All three are gone; this version tracks the current signatures.
"""
import json
import tempfile
from pathlib import Path

from subsidy_engine import sharecards

TEMPLATES = Path(sharecards.__file__).parent / "templates"


def main() -> None:
    site = Path.cwd() / "site"
    facts, _asof, _datestr = sharecards.load_facts(site / "data")
    versions = sharecards.png_versions(site / "share")

    out: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        stub_dir = tmp / "s"
        sharecards.write_stubs(facts, stub_dir, "PINNED", versions)
        for p in sorted(stub_dir.glob("*.html")):
            out[f"s/{p.name}"] = p.read_text()
        manifest_dir = tmp / "share"
        sharecards.write_manifest(facts, manifest_dir, "PINNED", versions)
        out["share/cards.json"] = (manifest_dir / "cards.json").read_text()

    template = (TEMPLATES / "sharecard.html").read_text()
    for fact in facts:
        if fact.get("chart"):
            continue
        out[f"card/{fact['slug']}.html"] = sharecards.compose(template, fact, "PINNED")

    timeseries = json.loads((site / "data" / "timeseries.json").read_text())
    breakdown = json.loads((site / "data" / "breakdown.json").read_text())
    # mirrors cmd_build_cards (and app.js renderChart memberIds) exactly
    member_ids = [s["id"] for s in breakdown["schemes"]
                  if s["layer"] == "indirect" or "renewables" in s["perspectives"]]
    svg = sharecards.cumulative_svg(timeseries, member_ids)
    out["chart/svg"] = svg

    chart_template = (TEMPLATES / "sharecard-chart.html").read_text()
    # MUST stay line-identical to sharecards.render_chart_card's composition
    # (which we cannot call directly — it screenshots via Playwright). If that
    # function's replace chain or cli.py's title argument changes, re-sync here.
    chart_html = (chart_template
                  .replace("{{TITLE}}", "The bill since 2002, in today’s money")
                  .replace("{{SVG}}", svg)
                  .replace("{{ASOF}}", "PINNED"))
    if "{{" in chart_html:
        raise ValueError("unfilled template token in chart card HTML")
    out["chart/card.html"] = chart_html

    print(json.dumps(out))


if __name__ == "__main__":
    main()
