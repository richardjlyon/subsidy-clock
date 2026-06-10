"""Loaders for versioned reference inputs (spec F-6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
import yaml


@dataclass
class ReferenceScheme:
    scheme_id: str
    label: str
    perspectives: list[str]
    cadence: str
    source: str
    source_url: str
    verified: bool
    annual: pl.DataFrame  # columns: year (Int64), cost_gbp (Float64)
    note: str = ""


def load_annual_costs(path: Path) -> dict[str, ReferenceScheme]:
    raw = yaml.safe_load(Path(path).read_text())
    out: dict[str, ReferenceScheme] = {}
    for scheme_id, s in raw["schemes"].items():
        annual = pl.DataFrame(
            {"year": list(s["annual"].keys()),
             "cost_gbp": [float(v) for v in s["annual"].values()]},
            schema={"year": pl.Int64, "cost_gbp": pl.Float64},
        ).sort("year")
        out[scheme_id] = ReferenceScheme(
            scheme_id=scheme_id,
            label=s["label"],
            perspectives=list(s["perspectives"]),
            cadence=s["cadence"],
            source=s["source"],
            source_url=s["source_url"],
            verified=bool(s.get("verified", False)),
            annual=annual,
            note=s.get("note", ""),
        )
    return out


def load_context(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())
