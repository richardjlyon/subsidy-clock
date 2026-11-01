"""Fixed-period totals on calendar years (D-13), for figures such as Report No. 2's 2002-24 totals.

RO and FiT are calendarised from obligation years as the engine does; each calendar year is deflated at its own
index. Built through the same model as the site (cli.assemble_model); writes nothing.

Usage: uv run python tools/period_totals.py [first] [last]      (default 2002 2024)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from subsidy_engine import reference  # noqa: E402
from subsidy_engine_uk import calendar_years  # noqa: E402
from subsidy_engine_uk.cli import assemble_model  # noqa: E402


def main(first: int = 2002, last: int = 2024) -> None:
    deflators = reference.load_deflators(ROOT / "reference" / "deflators.yaml")
    out = calendar_years.period_totals(assemble_model(ROOT)[0], first, last, deflators=deflators)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
