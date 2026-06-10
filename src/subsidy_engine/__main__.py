"""CLI: update schemes on their own cadences (F-2), backfill history (F-3),
and build the dashboard's JSON site data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from subsidy_engine import money, reconcile, reference, sitedata
from subsidy_engine.schemes import capacity_market, cfd, constraints
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
    store = make_store(args.root)
    refs = reference.load_annual_costs(args.root / "reference" / "annual_scheme_costs.yaml")
    ctx = reference.load_context(args.root / "reference" / "context.yaml")
    model = money.build(store, refs)
    freshness = {}
    for scheme_id, table in [("cfd", "generation"), ("constraints", "daily"),
                             ("capacity_market", "payments")]:
        f = store.freshness(scheme_id, table)
        if f:
            freshness[scheme_id] = {k: f.get(k) for k in
                                    ("retrieved_at", "source_date", "source_url", "row_count")}
    out_dir = args.root / "site" / "data"
    sitedata.build(model, ctx, freshness, out_dir,
                   generated_at=datetime.now(timezone.utc).isoformat())

    gen = store.latest("cfd", "generation")
    trk = store.latest("cfd", "tracking")
    if gen is not None and trk is not None:
        import polars as pl
        bottom_up = gen.group_by("date").agg(pl.col("payment_gbp").sum().alias("cost_gbp"))
        report = reconcile.cfd_monthly(bottom_up, trk)
        (out_dir / "reconciliation.json").write_text(json.dumps(report, indent=1, allow_nan=False))
        flag = "OK" if report["within_tolerance"] else "DIVERGENT"
        print(f"[reconciliation] {flag}: max divergence "
              f"{report['max_abs_divergence_pct']}% over {len(report['months'])} months")
    print(f"[ok] site data written to {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subsidy_engine",
                                     description="UK Subsidy Counter data engine")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="fetch latest data for scheme(s)")
    p_update.add_argument("scheme", choices=["all", "cfd", "constraints", "cm"],
                          nargs="?", default="all")
    p_update.set_defaults(fn=cmd_update)

    p_bf = sub.add_parser("backfill-constraints",
                          help="backfill constraint daily data for a date range")
    p_bf.add_argument("--start", required=True)
    p_bf.add_argument("--end", required=True)
    p_bf.set_defaults(fn=cmd_backfill_constraints)

    p_site = sub.add_parser("build-site", help="build dashboard JSON site data")
    p_site.set_defaults(fn=cmd_build_site)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
