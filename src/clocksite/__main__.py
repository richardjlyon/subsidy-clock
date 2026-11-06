"""CLI: fetch the bill-already-paid model's results file, build the site's data from it, and
render the share cards."""

from __future__ import annotations

import argparse
from pathlib import Path

from clocksite import cli

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clocksite",
                                     description="The Subsidy Clock website, built from the model's results")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--results", type=Path, default=None,
                        help="the model's results file (default: <root>/results/clock.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-results", help="copy the pinned model's results file into results/")
    p_fetch.add_argument("--source", default=None,
                         help="URL or path of clock.json (default: the source in reference/results_pin.yaml)")
    p_fetch.set_defaults(fn=cli.cmd_fetch_results)

    p_site = sub.add_parser("build-site", help="build dashboard JSON site data")
    p_site.add_argument("--out", type=Path, default=None,
                        help="site folder to write into (default: <root>/site)")
    p_site.set_defaults(fn=cli.cmd_build_site)

    p_cards = sub.add_parser("build-cards", help="render OG share-card PNGs and share stubs")
    p_cards.set_defaults(fn=cli.cmd_build_cards)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
