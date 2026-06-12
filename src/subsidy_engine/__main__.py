"""CLI: update schemes on their own cadences (F-2), backfill history (F-3),
and build the dashboard's JSON site data."""

from __future__ import annotations

import argparse
import json
import sys
import yaml
from datetime import date, datetime, timezone
from pathlib import Path

from subsidy_engine import money, reconcile, reference, sitedata
from subsidy_engine.schemes import bsuos, capacity_market, cfd, constraints
from subsidy_engine.store import SnapshotStore

ROOT = Path(__file__).resolve().parents[2]


def make_store(root: Path) -> SnapshotStore:
    return SnapshotStore(root / "data")


def cmd_update(args: argparse.Namespace) -> int:
    store = make_store(args.root)
    failures = []
    targets = {
        "cfd": lambda: cfd.update(store),
        "constraints": lambda: constraints.update(store),
        "cm": lambda: capacity_market.update(store),
        "bsuos": lambda: bsuos.update(store),
    }
    chosen = targets if args.scheme == "all" else {args.scheme: targets[args.scheme]}
    for name, fn in chosen.items():
        try:
            fn()
            print(f"[ok] {name} updated")
        except Exception as exc:  # F-8: failures visible, one scheme never blocks another
            failures.append(name)
            print(f"[FAIL] {name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def cmd_backfill_constraints(args: argparse.Namespace) -> int:
    store = make_store(args.root)
    constraints.backfill(store, date.fromisoformat(args.start), date.fromisoformat(args.end))
    return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    import polars as pl

    store = make_store(args.root)
    refs = reference.load_annual_costs(args.root / "reference" / "annual_scheme_costs.yaml")
    refs.update(reference.load_annual_costs(args.root / "reference" / "indirect_annual.yaml"))
    ctx = reference.load_context(args.root / "reference" / "context.yaml")
    deflators = reference.load_deflators(args.root / "reference" / "deflators.yaml")
    bill_raw = reference.load_electricity_bill(args.root / "reference" / "electricity_bill.yaml")
    bill = (money.add_real(bill_raw.rename({"total_bill_gbp": "cost_gbp"}), deflators)
            .rename({"cost_gbp": "total_bill_gbp", "cost_gbp_2024": "total_bill_gbp_2024"}))
    bill_yaml = yaml.safe_load((args.root / "reference" / "electricity_bill.yaml").read_text())
    bill_info = {"source": bill_yaml["source"], "source_url": bill_yaml["source_url"],
                 "verified": bill_yaml.get("verified", False)}
    baselines = reference.load_baselines(args.root / "reference" / "baselines.yaml")
    model = money.build(store, refs, deflators=deflators, baselines=baselines)
    freshness = {}
    for scheme_id, table in [("cfd", "generation"), ("constraints", "daily"),
                              ("capacity_market", "payments"), ("bsuos", "daily")]:
        f = store.freshness(scheme_id, table)
        if f:
            freshness[scheme_id] = {k: f.get(k) for k in
                                    ("retrieved_at", "source_date", "source_url", "row_count")}
    out_dir = args.root / "site" / "data"
    # provenance only - load_deflators already parsed the index above
    deflator_yaml = yaml.safe_load((args.root / "reference" / "deflators.yaml").read_text())
    deflator_info = {"source": deflator_yaml["source"],
                     "source_url": deflator_yaml["source_url"],
                     "base_year": deflator_yaml["base_year"],
                     "verified": deflator_yaml.get("verified", False)}
    generated_at = datetime.now(timezone.utc).isoformat()
    sitedata.build(model, ctx, freshness, out_dir,
                   generated_at=generated_at,
                   deflator_info=deflator_info,
                   bill_annual=bill, bill_info=bill_info, deflators=deflators)
    sitedata.write_csvs(model, out_dir, restatements=store.all_restatements(),
                        generated=generated_at)

    totals_json = json.loads((out_dir / "totals.json").read_text())
    sitedata.write_widget(totals_json, args.root / "site" / "embed" / "widget.html")

    gen = store.latest("cfd", "generation")
    trk = store.latest("cfd", "tracking")
    if gen is not None and trk is not None:
        bottom_up = gen.group_by("date").agg(pl.col("payment_gbp").sum().alias("cost_gbp"))
        report = reconcile.cfd_monthly(bottom_up, trk)
        (out_dir / "reconciliation.json").write_text(json.dumps(report, indent=1, allow_nan=False))
        flag = "OK" if report["within_tolerance"] else "DIVERGENT"
        pct = report["overall"]["divergence_pct"]
        print(f"[reconciliation] {flag}: overall divergence {pct}% over "
              f"{report['matched_days']} matched days "
              f"({report['excluded_recent_days']} recent days excluded)")

    crosscheck_path = args.root / "reference" / "ref_crosscheck.yaml"
    if crosscheck_path.is_file():
        ref_cc = reference.load_ref_crosscheck(crosscheck_path)
        cc_year = int(ref_cc["year"][:4])
        ours = {}
        for s in model["schemes"]:
            if s.layer == "indirect":
                row = s.annual.filter(pl.col("year") == cc_year)
                ours[s.scheme_id] = float(row["cost_gbp"][0]) if row.height else 0.0
        cc = reconcile.indirect_crosscheck(ours, ref_cc)
        (out_dir / "indirect_crosscheck.json").write_text(
            json.dumps(cc, indent=1, allow_nan=False))
        print(f"[crosscheck] {len(cc['components'])} components vs REF {cc['comparison_year']}; "
              f"{cc['unexplained_count']} unexplained beyond ±{cc['bound_pct']}%")

    ref_totals_path = args.root / "reference" / "ref_totals.yaml"
    if ref_totals_path.is_file():
        ref_t = reference.load_ref_totals(ref_totals_path)
        thru = int(ref_t["ours_through_year"])
        comp: dict[str, float] = {}
        real_total = 0.0
        for s in model["schemes"]:
            cut = s.annual.filter(pl.col("year") <= thru)
            nom = float(cut["cost_gbp"].sum()) if cut.height else 0.0
            if "cost_gbp_2024" in cut.columns and cut.height:
                real_total += float(cut["cost_gbp_2024"].sum())
            key = "cfd" if s.scheme_id in ("cfd_renewable", "cfd_low_carbon") else s.scheme_id
            comp[key] = comp.get(key, 0.0) + nom
        unmapped = set(comp) - set(ref_t["components"])
        if unmapped:
            raise SystemExit(f"[ref-reconciliation] schemes not in REF table: {sorted(unmapped)}")
        recon = reconcile.ref_reconciliation(comp, real_total, ref_t)
        (out_dir / "ref_reconciliation.json").write_text(
            json.dumps(recon, indent=1, allow_nan=False))
        print(f"[ref-reconciliation] ours £{recon['ours_total_gbp']/1e9:.1f}bn vs "
              f"REF £{recon['ref_total_gbp']/1e9:.1f}bn to {thru}; "
              f"stricter choices remove £{recon['stricter_gap_gbp']/1e9:.1f}bn "
              f"against the £{recon['gap_gbp']/1e9:.1f}bn gap")

    print(f"[ok] site data written to {out_dir}")
    return 0


def cmd_build_cards(args: argparse.Namespace) -> int:
    from subsidy_engine import sharecards

    site = args.root / "site"
    facts, asof, datestr = sharecards.load_facts(site / "data")
    sharecards.render([f for f in facts if not f.get("chart")], asof, site / "share")
    timeseries = json.loads((site / "data" / "timeseries.json").read_text())
    breakdown = json.loads((site / "data" / "breakdown.json").read_text())
    # mirrors app.js renderChart memberIds — renewables perspective:
    # indirect-layer schemes always join; direct schemes only when they
    # carry the renewables perspective (so the card excludes what the
    # /s/the-bill figure excludes, e.g. cfd_low_carbon).
    member_ids = [s["id"] for s in breakdown["schemes"]
                  if s["layer"] == "indirect" or "renewables" in s["perspectives"]]
    for fact in facts:
        if fact.get("chart"):
            sharecards.render_chart_card(timeseries, member_ids, fact, asof, site / "share")
    sharecards.write_stubs(facts, site / "s", asof, datestr)
    n_stubs = sum(1 for f in facts if f.get("stub"))
    print(f"[ok] {len(facts)} share cards and {n_stubs} share stubs written (as of {asof})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subsidy_engine",
                                     description="UK Subsidy Counter data engine")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="fetch latest data for scheme(s)")
    p_update.add_argument("scheme", choices=["all", "cfd", "constraints", "cm", "bsuos"],
                          nargs="?", default="all")
    p_update.set_defaults(fn=cmd_update)

    p_bf = sub.add_parser("backfill-constraints",
                          help="backfill constraint daily data for a date range")
    p_bf.add_argument("--start", required=True)
    p_bf.add_argument("--end", required=True)
    p_bf.set_defaults(fn=cmd_backfill_constraints)

    p_site = sub.add_parser("build-site", help="build dashboard JSON site data")
    p_site.set_defaults(fn=cmd_build_site)

    p_cards = sub.add_parser("build-cards", help="render OG share-card PNGs and share stubs")
    p_cards.set_defaults(fn=cmd_build_cards)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
