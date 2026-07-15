"""CLI: update schemes on their own cadences (F-2), backfill history (F-3),
and build the dashboard's JSON site data."""

from __future__ import annotations

import argparse
from pathlib import Path

# The composition root: the ONE sanctioned subsidy_engine -> subsidy_engine_uk import.
# The enforceable rule is "no module in subsidy_engine EXCEPT __main__.py may import
# subsidy_engine_uk" — greppable in one line. It cannot cycle, because nothing imports
# subsidy_engine.__main__: `python -m subsidy_engine` initialises the subsidy_engine
# package first, then runs this file as "__main__".
from subsidy_engine_uk import cli

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subsidy_engine",
                                     description="UK Subsidy Counter data engine")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="fetch latest data for scheme(s)")
    p_update.add_argument("scheme", choices=["all", "cfd", "constraints", "cm", "bsuos"],
                          nargs="?", default="all")
    p_update.set_defaults(fn=cli.cmd_update)

    p_bf = sub.add_parser("backfill-constraints",
                          help="backfill constraint daily data for a date range")
    p_bf.add_argument("--start", required=True)
    p_bf.add_argument("--end", required=True)
    p_bf.set_defaults(fn=cli.cmd_backfill_constraints)

    p_site = sub.add_parser("build-site", help="build dashboard JSON site data")
    p_site.set_defaults(fn=cli.cmd_build_site)

    p_cards = sub.add_parser("build-cards", help="render OG share-card PNGs and share stubs")
    p_cards.set_defaults(fn=cli.cmd_build_cards)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
