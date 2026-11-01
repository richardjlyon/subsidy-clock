"""Which published figures moved between two site builds, and by how much.

The evidence for a release: golden_master.py says whether anything moved; this
says what. Compares each scheme's yearly cost (cash and real) in timeseries.json
and each headline cumulative in totals.json; moves under a penny are build noise
(see golden_master.py on polars float sums) and are left out.

Usage: uv run python tools/figure_moves.py <old site/data> <new site/data>
"""
import json
import sys
from pathlib import Path

PENNY = 0.01


def figures(data: Path) -> dict[str, float]:
    out = {}
    ts = json.loads((data / "timeseries.json").read_text())
    for sid, s in ts["schemes"].items():
        for row in s.get("annual", []):
            out[f"{sid} {row['year']} cash"] = row["cost"]
            if "cost_real" in row:
                out[f"{sid} {row['year']} real"] = row["cost_real"]
    totals = json.loads((data / "totals.json").read_text())
    blocks = dict(totals.get("perspectives", {}))
    if "indirect" in totals:
        blocks["indirect"] = totals["indirect"]
    for name, b in blocks.items():
        out[f"headline {name} cash"] = b["cumulative"]
        if "real" in b:
            out[f"headline {name} real"] = b["real"]["cumulative"]
    return out


def main(old: Path, new: Path) -> None:
    a, b = figures(old), figures(new)
    lines = []
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            lines.append(f"{k}: {'added' if k in b else 'removed'}")
        elif abs(b[k] - a[k]) >= PENNY:
            lines.append(f"{k}: {a[k]:,.2f} -> {b[k]:,.2f} ({b[k] - a[k]:+,.2f})")
    print("\n".join(lines) if lines else "no figure moved by 1p or more")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
