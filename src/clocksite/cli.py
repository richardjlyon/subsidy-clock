"""The command implementations behind the clocksite CLI (the parser and ROOT are in
clocksite.__main__, the entry point: `python -m clocksite ...`)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from clocksite import inputs, results, sitedata


def results_path(args: argparse.Namespace) -> Path:
    return args.results or args.root / "results" / results.FILE


def cmd_fetch_results(args: argparse.Namespace) -> int:
    """Copy the pinned model's results file and its fingerprint into results/ (refused unless
    they are the pinned version's, as the model wrote them)."""
    pin = results.load_pin(args.root)
    source = args.source or pin["source"]
    meta = results.fetch(source, results_path(args).parent, pin)
    print(f"[ok] results fetched: {meta['model']} {meta['version']}, generated {meta['generated_at']}, "
          f"commit {meta['commit']}")
    return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    res = results.read(results_path(args), results.load_pin(args.root))
    site = inputs.load(args.root)
    model, ctx = res.model, res.ctx
    out_site = args.out or args.root / "site"
    print(f"[results] {res.meta['model']} {res.meta['version']}, generated {res.meta['generated_at']}")
    out_dir = out_site / "data"
    generated_at = datetime.now(timezone.utc).isoformat()
    sitedata.build(model, ctx, res.freshness, out_dir,
                   generated_at=generated_at,
                   deflator_info=res.deflator_info,
                   bill_annual=res.bill, bill_info=res.bill_info, deflators=res.deflators,
                   coords=site.coords, tiles=site.tiles,
                   notes=site.notes,
                   equivalences=site.equivalences)
    sitedata.write_csvs(model, out_dir, restatements=res.restatements,
                        generated=generated_at)
    changelog = sitedata.load_changelog(args.root / "changelog.jsonl")
    sitedata.write_changelog(changelog, out_dir, generated=generated_at)

    if res.scotland is not None:
        scot = {**res.scotland, "generated_at": generated_at}
        (out_dir / "scotland.json").write_text(json.dumps(scot, indent=1, allow_nan=False))

    totals_json = json.loads((out_dir / "totals.json").read_text())
    sitedata.write_widget(totals_json, out_site / "embed" / "widget.html")

    if res.reconciliation is not None:
        (out_dir / "reconciliation.json").write_text(
            json.dumps(res.reconciliation, indent=1, allow_nan=False))

    print(f"[ok] site data written to {out_dir}")
    return 0


def cmd_build_cards(args: argparse.Namespace) -> int:
    from clocksite import sharecards

    site = args.root / "site"
    facts, asof, datestr = sharecards.load_facts(site / "data")
    sharecards.render([f for f in facts if not f.get("chart")], asof, site / "share")
    timeseries = json.loads((site / "data" / "timeseries.json").read_text())
    breakdown = json.loads((site / "data" / "breakdown.json").read_text())
    member_ids = sharecards.chart_members(breakdown)
    for fact in facts:
        if fact.get("chart"):
            sharecards.render_chart_card(timeseries, member_ids, fact, asof, site / "share")
    versions = sharecards.png_versions(site / "share")
    n_targets = sharecards.verify_stub_targets(facts, site)
    sharecards.write_stubs(facts, site / "s", asof, versions)
    sharecards.write_manifest(facts, site / "share", asof, versions)
    if versions.get("headline"):
        sharecards.stamp_index_og(site / "index.html", versions["headline"])
    # Every other page carrying a share image needs the same cache-buster, or
    # the platforms keep serving whatever they cached the first time a link was
    # shared. The explainers in particular were unstamped, so a corrected
    # figure would never have reached anyone re-sharing them.
    n_stamped = 0
    for page in sorted(site.rglob("*.html")):
        if page.name == "index.html" and page.parent == site:
            continue          # already done, with its strict one-tag check
        if page.parent.name == "s":
            continue          # stubs are written with the token inline
        n_stamped += sharecards.stamp_og_images(page, versions)
    n_stubs = sum(1 for f in facts if f.get("stub"))
    print(f"[ok] {len(facts)} share cards and {n_stubs} share stubs written "
          f"({n_targets} stub targets verified, {n_stamped} og:image tags "
          f"cache-busted, as of {asof})")
    return 0
