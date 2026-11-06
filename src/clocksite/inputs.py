"""The website's own inputs: the map's station coordinates and tiles, the enforcement notes
beside it, and the equivalences the factoids use. Everything else the site shows comes from
the model's results file (clocksite.results; aios-harness#140). The two loaders are moved
unchanged from the model's stations module."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SiteInputs:
    equivalences: list
    coords: dict
    notes: dict
    tiles: dict


def load(root: Path) -> SiteInputs:
    ref = root / "reference"
    return SiteInputs(
        equivalences=yaml.safe_load((ref / "equivalences.yaml").read_text()),
        coords=load_station_coords(ref / "station_coords.csv"),
        notes=load_enforcement_notes(ref / "enforcement_notes.csv"),
        tiles=json.loads((ref / "map_tiles.json").read_text()),
    )


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
