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


def load_electricity_bill(path: Path) -> pl.DataFrame:
    """Total UK electricity consumer expenditure as (year, total_bill_gbp), sorted."""
    raw = yaml.safe_load(Path(path).read_text())
    return pl.DataFrame(
        {"year": list(raw["bill"].keys()),
         "total_bill_gbp": [float(v) for v in raw["bill"].values()]},
        schema={"year": pl.Int64, "total_bill_gbp": pl.Float64},
    ).sort("year")


MODEL_PIN = "model_pin.yaml"


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CLOCK_EXPORT_SCHEMA = "clock-export/2"


def load_model_pin(ref_dir: Path) -> dict:
    """reference/model_pin.yaml + the vendored engine export it pins -> every
    counterfactual figure the Clock uses, and nothing else (Richard, 14 Oct 2026).

    The Clock measures what was paid; the only figures in it about what would
    have happened without net zero (the Capacity Market net-zero share, and the
    no-net-zero grid and balancing cost per year) come from ONE source, a
    released export of the gas-counterfactual engine, vendored at
    reference/engine/<version>.json and pinned by version and sha256. A new
    engine release never flows in by itself: the build fails unless the
    vendored file's sha256 and meta.engine_version equal the pin, so updating
    means editing the pin and vendoring the new file on purpose.

    Returns {"pin": {engine_version, sha256, ...}, "cm_share": <_cm_share shape>,
    "counterfactual": {"tnuos": <series>, "bsuos": <series>}}; each series is
    {"years": {year: GBP nominal central}, "low", "high" (same shape),
    "carry_forward_from", "carry_index", "rule", "method", "source_ids",
    "engine_version"} (engine GO5 grid / GO4 balancing, generators' share
    included; one method in both models, Richard 14 Oct 2026)."""
    import json
    ref_dir = Path(ref_dir)
    pin = yaml.safe_load((ref_dir / MODEL_PIN).read_text())
    for k in ("engine_version", "clock_export_file", "sha256", "engine_commit", "release_date"):
        if not pin.get(k):
            raise ValueError(f"{MODEL_PIN}: {k} missing")
    vend = ref_dir.parent / pin["clock_export_file"]
    if not vend.is_file():
        raise ValueError(f"{MODEL_PIN}: pinned file {pin['clock_export_file']} not found")
    got = _sha256(vend)
    if got != pin["sha256"]:
        raise ValueError(f"{MODEL_PIN}: {pin['clock_export_file']} sha256 {got} != pinned "
                         f"{pin['sha256']} (the vendored engine export was changed; re-vendor "
                         "the released file or update the pin on purpose)")
    exp = json.loads(vend.read_text())
    if exp["meta"]["engine_version"] != pin["engine_version"]:
        raise ValueError(f"{MODEL_PIN}: vendored meta.engine_version "
                         f"{exp['meta']['engine_version']} != pinned {pin['engine_version']}")
    if exp["meta"].get("schema") != CLOCK_EXPORT_SCHEMA:
        raise ValueError(f"{MODEL_PIN}: vendored schema {exp['meta'].get('schema')} != "
                         f"{CLOCK_EXPORT_SCHEMA} (the Clock needs the per-year grid and "
                         "balancing series)")
    cm = exp["capacity_market"]
    cm_share = _cm_share({int(y): r for y, r in cm["years"].items()},
                         int(cm["carry_forward_from"]),
                         {"engine": "gas-counterfactual",
                          "engine_version": pin["engine_version"],
                          "commit": exp["meta"].get("run_commit") or pin["engine_commit"],
                          "commit_date": exp["meta"].get("run_date"),
                          "file": exp["meta"]["run_file"],
                          "file_sha256": exp["meta"]["run_sha256"]},
                         pin["clock_export_file"])
    cf = exp["carry_forward"]
    counterfactual = {k: _cf_series(exp[block], cf, pin["engine_version"], pin["clock_export_file"])
                      for k, block in (("tnuos", "grid"), ("bsuos", "balancing"))}
    return {"pin": {"engine_version": pin["engine_version"], "sha256": pin["sha256"],
                    "engine_commit": pin["engine_commit"],
                    "release_date": str(pin["release_date"]),
                    "clock_export_file": pin["clock_export_file"]},
            "cm_share": cm_share, "counterfactual": counterfactual}


def _cf_series(block: dict, carry: dict, version: str, name: str) -> dict:
    """One engine no-net-zero cost series (GBP nominal per calendar year).
    Validates contiguity, positivity and that the carry-forward starts at the
    engine's last year, so a malformed export fails the build."""
    if block.get("gen_share") != "included":
        raise ValueError(f"{name}: series must include generators' share (the Clock has no "
                         f"power-price line), got {block.get('gen_share')}")
    if carry.get("index") != "CPIH":
        raise ValueError(f"{name}: carry-forward index {carry.get('index')} != CPIH")
    rows = {int(y): r for y, r in block["years"].items()}
    ys = sorted(rows)
    if ys != list(range(ys[0], ys[-1] + 1)) or int(carry["from"]) != ys[-1]:
        raise ValueError(f"{name}: years {ys[0]}-{ys[-1]} not contiguous or carry-forward "
                         f"from {carry['from']} is not the last year")
    out = {t: {y: float(rows[y][f"{t}_gbp"]) for y in ys} for t in ("central", "low", "high")}
    if any(v <= 0 for t in out.values() for v in t.values()):
        raise ValueError(f"{name}: non-positive no-net-zero cost")
    return {"years": out["central"], "low": out["low"], "high": out["high"],
            "carry_forward_from": ys[-1], "carry_index": "CPIH", "rule": carry["rule"],
            "method": block["method"], "source_ids": block["source_ids"],
            "engine_version": version}


def _cm_share(raw_years: dict, carry: int, provenance: dict, name: str) -> dict:
    """Per-year Capacity Market share net zero caused, with its low/high range.

    Each row carries cm_paid_gbp, netzero_gbp, netzero_low_gbp, netzero_high_gbp
    and the derived share/share_low/share_high. Validates that every share lies
    in [0, 1] and that low <= central <= high, so a bad row fails the build
    rather than publishing."""
    years: dict[int, dict] = {}
    for y, row in raw_years.items():
        paid = float(row["cm_paid_gbp"])
        if paid <= 0:
            raise ValueError(f"{name} {y}: cm_paid_gbp must be positive")
        r = dict(row)
        r["share"] = float(row["netzero_gbp"]) / paid
        r["share_low"] = float(row["netzero_low_gbp"]) / paid
        r["share_high"] = float(row["netzero_high_gbp"]) / paid
        if not (0.0 <= r["share_low"] <= r["share"] <= r["share_high"] <= 1.0 + 1e-12):
            raise ValueError(f"{name} {y}: shares must satisfy "
                             f"0 <= low <= central <= high <= 1, got "
                             f"{r['share_low']:.4f}/{r['share']:.4f}/{r['share_high']:.4f}")
        years[int(y)] = r
    if carry not in years:
        raise ValueError(f"{name}: carry_forward_from {carry} has no row")
    return {"years": years, "carry_forward_from": carry, "provenance": provenance}
