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

STATUSES = ("applied", "ruled")


class FindingsError(ValueError):
    pass


@dataclass
class Selection:
    applied: list[str] = field(default_factory=list)
    drop: set[str] = field(default_factory=set)
    take: list[tuple[str, str, str]] = field(default_factory=list)   # (line, product, item_id)

    def record(self) -> dict:
        """What breakdown.json publishes: the findings applied, the register adjustments they drop, and
        those they take from another product's rows."""
        return {"applied": list(self.applied), "dropped": sorted(self.drop),
                "taken": [list(t) for t in self.take]}


def _register_items(reg: CR.Register) -> dict[str, set[str]]:
    """item_id -> {product} for every input adjustment row."""
    out: dict[str, set[str]] = {}
    for r in reg.rows:
        if r["row_type"] == "input_adjustment":
            out.setdefault(r["item_id"], set()).update(r["applies_to"].split(";"))
    return out


def _register_line_items(reg: CR.Register) -> set[tuple[str, str, str]]:
    """(line, product, item_id) for every input adjustment row."""
    return {(r["line_id"], p, r["item_id"]) for r in reg.rows if r["row_type"] == "input_adjustment"
            for p in r["applies_to"].split(";")}


def load(path: Path | str, reg: CR.Register, *, product: str = "clock_live") -> Selection:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    items = _register_items(reg)
    line_items = _register_line_items(reg)
    sel = Selection()
    for fid, f in (doc.get("findings") or {}).items():
        if f.get("status") not in STATUSES:
            raise FindingsError(f"{fid}: status {f.get('status')!r} is not one of {STATUSES}; only a fix or ruling "
                                f"Richard approved goes in this file")
        for key in ("reason", "approved"):
            if not f.get(key):
                raise FindingsError(f"{fid} gives no {key}")
        for item in f.get("drop") or []:
            if product not in items.get(item, ()):
                raise FindingsError(f"{fid}: the register has no input adjustment {item!r} for {product}")
            sel.drop.add(item)
        # take: another product's named adjustment, applied to the Clock's line as the register holds it
        for t in f.get("take") or []:
            ln, prod, item = t
            if (ln, prod, item) not in line_items:
                raise FindingsError(f"{fid}: the register has no {ln} input adjustment {item!r} for {prod}")
            if prod == product:
                raise FindingsError(f"{fid}: {item!r} already applies to {product}; take is for another "
                                    f"product's rows")
            sel.take.append((ln, prod, item))
        sel.applied.append(fid)
    return sel


def line(reg: CR.Register, product: str, line_id: str, sel: Selection | None) -> dict[int, float]:
    """The product's register line, less the adjustments the Clock does not take, plus those it takes from
    another product's rows. With no selection, exactly reg.line(line_id, product)."""
    if sel is None or not (sel.drop or sel.take):
        return reg.line(line_id, product)
    out = reg.series(line_id)
    for item, vals in reg.adjustments(line_id, product).items():
        if item in sel.drop:
            continue
        for y, v in vals.items():
            if y not in out:
                raise FindingsError(f"{item}: {y} has no {line_id} series row")
            out[y] += v
    for ln, prod, item in sel.take:
        if ln != line_id:
            continue
        for y, v in reg.adjustments(ln, prod)[item].items():
            if y not in out:
                raise FindingsError(f"{item}: {y} has no {line_id} series row")
            out[y] += v
    return out
