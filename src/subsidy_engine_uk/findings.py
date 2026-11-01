"""Which of the shared cost register's named adjustments the Clock does not take (aios-harness#42; the
mechanism ported from card t_b468cbeb, cut down to what the approved fixes need).

The register holds the live Clock's definition of each input as named input adjustments for product
`clock_live`. Some of those hold a live error. reference/clock_findings.yaml lists each fix Richard approved
that removes one: by item id only (`drop`). Every figure still comes from the register (decision 0168); this
module and that file hold none.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from subsidy_engine import cost_register as CR

STATUSES = ("applied",)


class FindingsError(ValueError):
    pass


@dataclass
class Selection:
    applied: list[str] = field(default_factory=list)
    drop: set[str] = field(default_factory=set)

    def record(self) -> dict:
        """What breakdown.json publishes: the findings applied and the register adjustments they drop."""
        return {"applied": list(self.applied), "dropped": sorted(self.drop)}


def _register_items(reg: CR.Register) -> dict[str, set[str]]:
    """item_id -> {product} for every input adjustment row."""
    out: dict[str, set[str]] = {}
    for r in reg.rows:
        if r["row_type"] == "input_adjustment":
            out.setdefault(r["item_id"], set()).update(r["applies_to"].split(";"))
    return out


def load(path: Path | str, reg: CR.Register, *, product: str = "clock_live") -> Selection:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    items = _register_items(reg)
    sel = Selection()
    for fid, f in (doc.get("findings") or {}).items():
        if f.get("status") not in STATUSES:
            raise FindingsError(f"{fid}: status {f.get('status')!r} is not one of {STATUSES}; only a fix "
                                f"Richard approved goes in this file")
        for key in ("reason", "approved"):
            if not f.get(key):
                raise FindingsError(f"{fid} gives no {key}")
        for item in f.get("drop") or []:
            if product not in items.get(item, ()):
                raise FindingsError(f"{fid}: the register has no input adjustment {item!r} for {product}")
            sel.drop.add(item)
        sel.applied.append(fid)
    return sel


def line(reg: CR.Register, product: str, line_id: str, sel: Selection | None) -> dict[int, float]:
    """The product's register line, less the adjustments the Clock does not take. With no selection, exactly
    reg.line(line_id, product)."""
    if sel is None or not sel.drop:
        return reg.line(line_id, product)
    out = reg.series(line_id)
    for item, vals in reg.adjustments(line_id, product).items():
        if item in sel.drop:
            continue
        for y, v in vals.items():
            if y not in out:
                raise FindingsError(f"{item}: {y} has no {line_id} series row")
            out[y] += v
    return out
