"""Group per-contract CfD recipients into physical stations.

A single wind farm built in phases holds a separate CfD contract per phase
(e.g. Walney Extension Phase 1 and Phase 2), so the per-contract recipient list
reads as two assets. ``group_by_station`` collapses contracts that share a
station while preserving the per-contract breakdown underneath, using the
asset short-name map derived from the LCCC contract register.
"""

import csv
from pathlib import Path


def load_station_map(path):
    """Load the cfd_id -> station short-name map from the reference CSV.

    The CSV (``reference/cfd_stations.csv``) is derived from the LCCC contract
    register via David Turver's asset short-names; it is the route by which
    per-contract CfD units collapse to physical stations.
    """
    with Path(path).open(newline="") as f:
        return {row["cfd_id"]: row["station"] for row in csv.DictReader(f)}


def group_by_station(recipients, station_map):
    """Collapse per-contract recipient rows into per-station rows.

    ``recipients`` is a list of dicts with ``cfd_id``, ``unit_name``,
    ``technology`` and ``cost_gbp``. ``station_map`` maps a ``cfd_id`` to its
    physical-station short name; a contract whose id is absent from the map
    stands alone under its own ``unit_name``. Joining on ``cfd_id`` (not name)
    is exact — phased farms whose unit names differ still collapse correctly.
    Returns station rows sorted by total cost descending, each carrying its
    constituent ``contracts`` (also sorted by cost descending).
    """
    stations = {}
    for r in recipients:
        station = station_map.get(r["cfd_id"], r["unit_name"])
        stations.setdefault(station, []).append(r)

    rows = []
    for station, contracts in stations.items():
        contracts = sorted(contracts, key=lambda c: c["cost_gbp"], reverse=True)
        techs = {c["technology"] for c in contracts}
        rows.append({
            "station": station,
            "technology": next(iter(techs)) if len(techs) == 1 else "Mixed",
            "cost_gbp": sum(c["cost_gbp"] for c in contracts),
            "contracts": contracts,
        })
    rows.sort(key=lambda s: s["cost_gbp"], reverse=True)
    return rows
