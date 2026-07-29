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


def load_station_coords(path):
    """Load station -> (lat, lon, slug) from the reference coords CSV.

    The CSV (``reference/station_coords.csv``) has columns ``station,slug,lat,
    lon,source_url`` where ``station`` is the exact ``by_station`` name (the
    join key) and ``slug`` is the hand-pinned stable identifier for the
    station's asset JSON and deep links — assigned once, never derived from the
    (unstable) upstream name. Rows with a blank or non-numeric (e.g.
    ``NOT FOUND``) lat/lon are skipped so an unlocated station simply yields no
    marker. A located row without a slug, or a slug used twice, fails loudly:
    silent slug drift would orphan asset files and deep links.
    """
    coords = {}
    seen = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (TypeError, ValueError):
                continue
            slug = (row.get("slug") or "").strip()
            if not slug:
                raise ValueError(f"station_coords: located row for "
                                 f"{row['station']!r} has no slug")
            if slug in seen:
                raise ValueError(f"station_coords: duplicate slug {slug!r} "
                                 f"({seen[slug]!r} and {row['station']!r})")
            seen[slug] = row["station"]
            coords[row["station"]] = (lat, lon, slug)
    return coords


def load_station_bmus(path):
    """Load station -> [BM unit ids] from the curated reference CSV.

    ``reference/station_bmu_map.csv`` has columns ``station,bmu_id,source_url,
    note`` — one row per BMU, hand-curated against the Elexon BMU register
    (stations may span several BMUs; stations with no registered BM unit are
    simply absent and render as outage-history-unavailable, never zero). A row
    without a source_url fails loudly: an uncited mapping could attribute
    outages to the wrong farm.
    """
    bmus = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            if not (row.get("source_url") or "").strip():
                raise ValueError(f"station_bmu_map: row for {row['station']!r} "
                                 f"({row['bmu_id']!r}) has no source_url")
            bmus.setdefault(row["station"], []).append(row["bmu_id"])
    return bmus


# Enforcement notes may only cite official documents. Editorial prose about a
# named company's regulatory conduct is the highest-risk text on the site.
NOTE_DOMAIN_ALLOWLIST = ("ofgem.gov.uk", "gov.uk", "lowcarboncontracts.uk")


def load_enforcement_notes(path):
    """Load curated asset-level regulatory notes from the reference CSV.

    ``reference/enforcement_notes.csv`` has columns ``station,date,text,
    source_url``. Every row must cite a document on an official domain
    (NOTE_DOMAIN_ALLOWLIST) and its text must be a close paraphrase of that
    document, passed through the prepublication fact-check gate before it is
    committed. An empty file (header only) is a valid state. Returns
    station -> {date, text, source_url}.
    """
    from urllib.parse import urlparse
    notes = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            url = (row.get("source_url") or "").strip()
            host = urlparse(url).hostname or ""
            if not any(host == d or host.endswith("." + d)
                       for d in NOTE_DOMAIN_ALLOWLIST):
                raise ValueError(
                    f"enforcement_notes: row for {row['station']!r} cites "
                    f"{url!r} — not on the official-domain allowlist")
            notes[row["station"]] = {"date": row["date"], "text": row["text"],
                                     "source_url": url}
    return notes


def load_ro_stations(path):
    """Load named RO recipients from the reference CSV, valued at buy-out.

    Returns a list of ``{station, technology, cost}`` dicts, sorted as the
    file is. ``cost`` is the buy-out value (the directly-sourced per-generator
    basis); the RO scheme total additionally includes recycle value, so these
    per-station figures understate the full cost by the recycle element.
    """
    with Path(path).open(newline="") as f:
        return [
            {"station": row["station"], "technology": row["technology"],
             "cost": float(row["buyout_gbp"])}
            for row in csv.DictReader(f)
        ]


def group_by_station(recipients, station_map):
    """Collapse per-contract recipient rows into per-station rows.

    ``recipients`` is a list of dicts with ``cfd_id``, ``unit_name``,
    ``technology`` and ``cost``. ``station_map`` maps a ``cfd_id`` to its
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
        contracts = sorted(contracts, key=lambda c: c["cost"], reverse=True)
        techs = {c["technology"] for c in contracts}
        rows.append({
            "station": station,
            "technology": next(iter(techs)) if len(techs) == 1 else "Mixed",
            "cost": sum(c["cost"] for c in contracts),
            "contracts": contracts,
        })
    rows.sort(key=lambda s: s["cost"], reverse=True)
    return rows
