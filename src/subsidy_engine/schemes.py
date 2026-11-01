"""The scheme registry: each scheme's publishing settings, in chart stack order
(aios-harness#51). sitedata and sharecards read it; site/app.js (SCHEME_META,
SCHEME_COLOURS, STACK_ORDER) and the stylesheets keep copies that tests/test_schemes.py
holds to it. The engine is UK-only: this lists the UK schemes.

CSV names and methodology anchors are public contracts (published URLs); change them
only as a release decision.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scheme:
    id: str
    name: str            # display name, as on the dashboard and share cards
    slug: str            # explainer page, /explainers/<slug>
    csv: str             # public CSV file, /data/<csv>.csv
    colour: str          # chart colour as the pages show it (site/skin-ft.css)
    anchor: str | None = None       # own attribution-rule anchor on /methodology
    series_note: str | None = None  # CSV third comment line, where the default is wrong


SCHEMES = [
    Scheme("ro", "Renewables Obligation", "renewables-obligation",
           "renewables-obligation", "#990f3d"),
    Scheme("fit", "Feed-in Tariffs", "feed-in-tariffs", "feed-in-tariffs", "#e0a93e"),
    Scheme("cfd_renewable", "Contracts for Difference", "contracts-for-difference",
           "cfd", "#c56b2f"),
    Scheme("cfd_low_carbon", "CfD — nuclear", "cfd-nuclear", "cfd-nuclear", "#9a6a2e"),
    # the constraints explainer is the switch-off dashboard card's page
    Scheme("constraints", "Paid to switch off (constraints)", "constraints",
           "constraints", "#7a3b23"),
    Scheme("capacity_market", "Capacity Market", "capacity-market", "capacity-market",
           "#1b5a8a", anchor="attr-capacity_market",
           # not a renewables share: the part of the levy net zero caused (levy less
           # the backup any system would buy); "share attributed to renewables"
           # contradicted the method
           series_note=("# Estimated: only the part of the Capacity Market net zero "
                        "caused (levy less the backup any system needs) — method: "
                        "subsidyclock.co.uk/methodology#attr-capacity_market\n")),
    Scheme("ccl", "Climate Change Levy", "climate-change-levy", "climate-change-levy",
           "#2e7e86", anchor="attr-ccl"),
    Scheme("ets", "Emissions trading", "emissions-trading", "emissions-trading",
           "#5193b0", anchor="attr-ets"),
    Scheme("tnuos", "Grid upgrades for renewables (TNUoS)", "tnuos", "tnuos", "#8fb8ce",
           anchor="attr-tnuos"),
    Scheme("bsuos", "Balancing the grid (BSUoS)", "bsuos", "bsuos", "#c5dae6",
           anchor="attr-bsuos"),
    Scheme("constraint_turnup", "Paid to switch on (constraint turn-up)",
           "constraint-turnup", "constraint-turnup", "#6b8799",
           anchor="attr-constraint_turnup"),
]

_BY_ID = {s.id: s for s in SCHEMES}


def get(scheme_id: str) -> Scheme:
    """The registry entry; a scheme with none fails the build rather than publish under
    its bare id."""
    try:
        return _BY_ID[scheme_id]
    except KeyError:
        raise ValueError(f"scheme {scheme_id!r} is not in the scheme registry "
                         "(src/subsidy_engine/schemes.py): add it there") from None
