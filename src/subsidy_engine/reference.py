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
    attribution_rule: str = ""
    attribution_confidence: str = ""
    year_basis: str = "obligation_apr"  # "calendar" for calendar-year-keyed schemes (CCL, ETS)


def load_annual_costs(path: Path) -> dict[str, ReferenceScheme]:
    raw = yaml.safe_load(Path(path).read_text())
    out: dict[str, ReferenceScheme] = {}
    for scheme_id, s in raw["schemes"].items():
        annual = pl.DataFrame(
            {"year": list(s["annual"].keys()),
             "cost_gbp": [float(v) for v in s["annual"].values()]},
            schema={"year": pl.Int64, "cost_gbp": pl.Float64},
        ).sort("year")
        attribution = s.get("attribution", {})
        out[scheme_id] = ReferenceScheme(
            scheme_id=scheme_id,
            label=s["label"],
            perspectives=list(s.get("perspectives", [])),
            cadence=s["cadence"],
            source=s["source"],
            source_url=s["source_url"],
            verified=bool(s.get("verified", False)),
            annual=annual,
            note=s.get("note", ""),
            attribution_rule=attribution.get("rule", ""),
            attribution_confidence=attribution.get("confidence", ""),
            year_basis=s.get("year_basis", "obligation_apr"),
        )
    return out


def load_ref_crosscheck(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_ref_totals(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_context(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_deflators(path: Path) -> pl.DataFrame:
    """ONS CPIH annual index as (year, index), sorted."""
    raw = yaml.safe_load(Path(path).read_text())
    return pl.DataFrame(
        {"year": list(raw["index"].keys()),
         "index": [float(v) for v in raw["index"].values()]},
        schema={"year": pl.Int64, "index": pl.Float64},
    ).sort("year")


def load_baselines(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_electricity_bill(path: Path) -> pl.DataFrame:
    """Total UK electricity consumer expenditure as (year, total_bill_gbp), sorted."""
    raw = yaml.safe_load(Path(path).read_text())
    return pl.DataFrame(
        {"year": list(raw["bill"].keys()),
         "total_bill_gbp": [float(v) for v in raw["bill"].values()]},
        schema={"year": pl.Int64, "total_bill_gbp": pl.Float64},
    ).sort("year")
