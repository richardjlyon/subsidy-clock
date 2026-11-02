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
    # constraints history only: the first year Elexon bottom-up replaces this history
    # (fix 5 guard: stated, so the backfill reaching further back moves no annual total and
    # not the constraints and balancing split; curtailed MWh, recipients and scotland.json
    # still move as days are added)
    bottom_up_from: int | None = None


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
            bottom_up_from=s.get("bottom_up_from"),
        )
    return out


def load_ref_crosscheck(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_ref_totals(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_context(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_deflators(path: Path) -> pl.DataFrame:
    """ONS CPIH as (year, index, current), sorted.

    `index` is the annual average; a year ONS has not yet averaged takes the mean of its published months
    (`months`), so its money is priced at the months it was paid in. `current` (the same on every row) is the
    latest published month, or the latest annual index when no months are held: the price level of today's
    money (aios-harness#57; Richard, 2 Nov 2026: best account)."""
    raw = yaml.safe_load(Path(path).read_text())
    index = {int(y): float(v) for y, v in raw["index"].items()}
    months = {int(y): [float(v) for v in vs] for y, vs in (raw.get("months") or {}).items()}
    for y, vs in months.items():
        if y in index:
            raise ValueError(f"{path}: {y} has both an annual index and months")
        index[y] = sum(vs) / len(vs)
    current = months[max(months)][-1] if months else index[max(index)]
    years = sorted(index)
    return pl.DataFrame(
        {"year": years, "index": [index[y] for y in years], "current": [current] * len(years)},
        schema={"year": pl.Int64, "index": pl.Float64, "current": pl.Float64},
    )


def load_electricity_bill(path: Path) -> pl.DataFrame:
    """Total UK electricity consumer expenditure as (year, total_bill_gbp), sorted."""
    raw = yaml.safe_load(Path(path).read_text())
    return pl.DataFrame(
        {"year": list(raw["bill"].keys()),
         "total_bill_gbp": [float(v) for v in raw["bill"].values()]},
        schema={"year": pl.Int64, "total_bill_gbp": pl.Float64},
    ).sort("year")


def load_cm_netzero_share(path: Path) -> dict:
    """reference/capacity_market_netzero_share.yaml -> the per-year Capacity
    Market share net zero caused, with its low/high range and provenance.

    Returns {"years": {year: row}, "carry_forward_from": int, "provenance": {...}}
    where each row carries cm_paid_gbp, netzero_gbp, netzero_low_gbp,
    netzero_high_gbp and the derived share/share_low/share_high. Validates
    that every share lies in [0, 1] and that low <= central <= high, so a
    mistyped row fails the build rather than publishing."""
    raw = yaml.safe_load(Path(path).read_text())
    years: dict[int, dict] = {}
    for y, row in raw["years"].items():
        paid = float(row["cm_paid_gbp"])
        if paid <= 0:
            raise ValueError(f"{Path(path).name} {y}: cm_paid_gbp must be positive")
        r = dict(row)
        r["share"] = float(row["netzero_gbp"]) / paid
        r["share_low"] = float(row["netzero_low_gbp"]) / paid
        r["share_high"] = float(row["netzero_high_gbp"]) / paid
        if not (0.0 <= r["share_low"] <= r["share"] <= r["share_high"] <= 1.0 + 1e-12):
            raise ValueError(f"{Path(path).name} {y}: shares must satisfy "
                             f"0 <= low <= central <= high <= 1, got "
                             f"{r['share_low']:.4f}/{r['share']:.4f}/{r['share_high']:.4f}")
        years[int(y)] = r
    carry = int(raw["carry_forward_from"])
    if carry not in years:
        raise ValueError(f"{Path(path).name}: carry_forward_from {carry} has no row")
    return {"years": years, "carry_forward_from": carry,
            "provenance": raw.get("provenance") or {}}
