"""The model's results file, read: the one input the site takes from the bill-already-paid model
(model-bill-already-paid, aios-harness#140).

The site is pinned to one model version and file format (reference/results_pin.yaml). `read`
refuses a results file from any other version or format, and one whose fingerprint (the
.sha256 file the model writes beside it) does not match. `fetch` copies the file and its
fingerprint from the pinned source into results/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import polars as pl
import yaml

FILE = "clock.json"
PIN = Path("reference") / "results_pin.yaml"


class ResultsRefused(ValueError):
    """The results file is not the pinned model's, or not as the model wrote it."""


@dataclass
class SchemeResult:
    """One scheme line, as the model wrote it (billpaid.money.SchemeResult's fields)."""
    scheme_id: str
    label: str
    perspectives: list[str]
    cadence: str
    annual: pl.DataFrame                  # year, cost_gbp[, cost_gbp_2024]
    cumulative_gbp: float
    runrate_gbp_per_year: float
    data_to: date | None
    layer: str = "direct"
    attribution_pct: float = 1.0
    attribution_note: str = ""
    attribution_confidence: str = ""
    extras: dict = field(default_factory=dict)
    # a line priced on other lines (VAT) carries forward with them: {scheme_id: factor}
    carry_with: dict | None = None


@dataclass
class Results:
    meta: dict
    model: dict                 # schemes (SchemeResult), perspectives, indirect, register, findings, ...
    ctx: dict
    deflators: pl.DataFrame
    deflator_info: dict
    bill: pl.DataFrame
    bill_info: dict
    freshness: dict
    restatements: list
    scotland: dict | None
    reconciliation: dict | None


def load_pin(root: Path) -> dict:
    pin = yaml.safe_load((root / PIN).read_text())
    for k in ("model", "version", "format", "source"):
        if k not in pin:
            raise ValueError(f"{PIN} lacks {k!r}")
    return pin


def table(f: dict | None) -> pl.DataFrame | None:
    """A table from the results file, with the columns and types the model held."""
    if f is None:
        return None
    schema = {k: getattr(pl, v) for k, v in f["schema"].items()}
    dates = [k for k, v in f["schema"].items() if v == "Date"]
    rows = [{**r, **{k: date.fromisoformat(r[k]) if r[k] else None for k in dates}} for r in f["rows"]]
    return pl.DataFrame(rows, schema=schema, orient="row") if rows else pl.DataFrame(schema=schema)


def _scheme(d: dict) -> SchemeResult:
    d = dict(d)
    d["annual"] = table(d["annual"])
    d["data_to"] = date.fromisoformat(d["data_to"]) if d["data_to"] else None
    return SchemeResult(**d)


def _block(b: dict) -> dict:
    return {k: table(v) if k == "annual" else v for k, v in b.items()}


def check(data: bytes, fingerprint_text: str, pin: dict) -> dict:
    """The file's meta block, once the file is the pinned model's and as the model wrote it."""
    expected = fingerprint_text.split()[0]
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ResultsRefused(f"results file fingerprint {actual[:12]} does not match its .sha256 "
                             f"({expected[:12]}): not as the model wrote it")
    meta = json.loads(data)["meta"]
    for k in ("model", "version", "format"):
        if meta.get(k) != pin[k]:
            raise ResultsRefused(f"results file is {k} {meta.get(k)!r}; the site is pinned to "
                                 f"{pin[k]!r} ({PIN})")
    return meta


def read(path: Path, pin: dict) -> Results:
    data = path.read_bytes()
    meta = check(data, path.with_name(path.name + ".sha256").read_text(), pin)
    doc = json.loads(data)
    m = doc["model"]
    model = {**m, "schemes": [_scheme(s) for s in m["schemes"]],
             "perspectives": {k: _block(b) for k, b in m["perspectives"].items()},
             "indirect": _block(m["indirect"])}
    return Results(meta=meta, model=model, ctx=doc["context"], deflators=table(doc["deflators"]),
                   deflator_info=doc["deflator_info"], bill=table(doc["bill"]),
                   bill_info=doc["bill_info"], freshness=doc["freshness"],
                   restatements=doc["restatements"], scotland=doc["scotland"],
                   reconciliation=doc["reconciliation"])


def _get(src: str) -> bytes:
    if src.startswith(("https://", "http://")):
        with urllib.request.urlopen(src, timeout=60) as r:
            return r.read()
    return Path(src).read_bytes()


def fetch(source: str, out_dir: Path, pin: dict) -> dict:
    """Copy the results file and its fingerprint from `source` (a URL or a path to the file) into
    out_dir, refusing them unless they pass `check`. Returns the file's meta block."""
    data, fp = _get(source), _get(source + ".sha256").decode()
    meta = check(data, fp, pin)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / (FILE + ".part")
    tmp.write_bytes(data)
    (out_dir / (FILE + ".sha256")).write_text(fp)
    shutil.move(tmp, out_dir / FILE)
    return meta
