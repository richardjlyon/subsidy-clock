"""The shared cost register in the Clock (decision 0168: one number, one source; card t_af5fbf06, re-made on
the scheme modules for engine release v4-s43 in aios-harness#42).

Every covered subsidy and system-cost series the Clock publishes for a closed year (2002 to `closed_through`) is
read from the shared cost register, pinned by sha256 in reference/register_pin.yaml:

- annual reference lines (RO, FiT, CCL and CPS, ETS, TNUoS, the BSUoS and constraints histories): the yearly
  figure is the register's line for this product (its series plus the input adjustments that hold the Clock's
  current definition, each named in the register);
- daily and monthly lines (CfD, Capacity Market paid, constraints from Elexon, BSUoS from NESO's daily files,
  turn-up): each closed year's days are scaled so the year sums to the register's figure. While the store and
  the register agree (as built), nothing moves; a restated closed year in a feed is reported in
  `register_checks` and the register, not the Clock, takes the correction.

Years after `closed_through` (still filling) come from the Clock's own feeds: an open item for Richard
(definitions D-14). The Capacity Market's net-zero share comes from the pinned engine release (Clock export,
`netzero_gbp`, reference/model_pin.yaml) over the register's CM paid; the hand-copied s32 shares are retired.

Each scheme module scales its own feed: it takes a `ToRegister` (or None in unit tests) and calls it on its
daily or monthly frame before annualising.
"""
from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path

import polars as pl
import yaml

from subsidy_engine import cost_register as CR

PENNY = 0.005           # GBP: a store-register difference below this is float noise, not a restatement


def load_pinned(root: Path) -> dict:
    """{register, product, closed_through, pin}: the register named in reference/register_pin.yaml."""
    pin = yaml.safe_load((root / "reference" / "register_pin.yaml").read_text())
    reg = CR.load(root / pin["file"], pin["sha256"])
    return {"register": reg, "product": pin["product"], "closed_through": int(pin["closed_through"]),
            "pin": pin}


# Clock reference scheme id -> register lines that make it, for this product
REF_LINES = {
    "ro": ("RO",),
    "fit": ("FIT",),
    "ccl": ("CCL_ELEC", "CPS"),
    "ets": ("ETS_POWER",),
    "tnuos": ("TNUOS",),
    "bsuos_history": ("BSUOS",),
    "constraints_history": ("CONSTRAINTS",),
}


def line_values(reg: CR.Register, product: str, lines: tuple[str, ...]) -> dict[int, float]:
    """GBP m by year: the product's line(s) from the register, summed."""
    out: dict[int, float] = {}
    for ln in lines:
        for y, v in reg.line(ln, product).items():
            out[y] = out.get(y, 0.0) + v
    return out


def overlay_refs(refs: dict, pinned: dict) -> dict:
    """Replace every closed year of each covered reference line with the register's figure. Returns
    {scheme_id: {year: (old GBP, new GBP)}} for every year the register changed by more than a penny."""
    reg, product, closed = pinned["register"], pinned["product"], pinned["closed_through"]
    moved: dict[str, dict] = {}
    for sid, lines in REF_LINES.items():
        if sid not in refs:
            continue
        vals = line_values(reg, product, lines)
        ref = refs[sid]
        old = dict(zip(ref.annual["year"].to_list(), ref.annual["cost_gbp"].to_list()))
        for y, v in vals.items():
            if y > closed:
                continue
            if y not in old:
                # after a history's last year the daily feed carries the line (scaled in the build); a gap
                # inside the reference file's own years is an error
                if old and min(old) <= y <= max(old) and abs(v) * 1e6 > PENNY:
                    raise ValueError(f"register {lines} {y} = {v} GBP m but the Clock's {sid} has no {y} figure")
                continue
            new = v * 1e6
            if abs(new - old[y]) > PENNY:
                moved.setdefault(sid, {})[y] = (old[y], new)
            old[y] = new
        ref.annual = pl.DataFrame({"year": list(old), "cost_gbp": list(old.values())},
                                  schema={"year": pl.Int64, "cost_gbp": pl.Float64}).sort("year")
    return moved


def rescale_closed_years(df: pl.DataFrame, values: dict[int, float], closed: int, *, first_year: int = 0,
                         value_col: str = "cost_gbp", checks: dict | None = None, line: str = "") -> pl.DataFrame:
    """Scale each closed year's rows (from `first_year`) so the year sums to the register's GBP m figure."""
    if df is None or not df.height:
        return df
    yr = pl.col("date").dt.year()
    sums = dict(df.group_by(yr.alias("y")).agg(pl.col(value_col).sum()).iter_rows())
    factors = {}
    for y, s in sums.items():
        if y > closed or y < first_year or y not in values:
            continue
        target = values[y] * 1e6
        if abs(target - s) <= PENNY:
            continue
        if s == 0:
            raise ValueError(f"register {line} {y} = {values[y]} GBP m but the Clock's feed holds nothing for {y}")
        factors[y] = target / s
        if checks is not None:
            checks.setdefault(line, {})[str(y)] = {"feed_gbp": s, "register_gbp": target}
    if not factors:
        return df
    f = pl.col("date").dt.year().replace_strict(factors, default=1.0, return_dtype=pl.Float64)
    return df.with_columns((pl.col(value_col) * f).alias(value_col))


class ToRegister:
    """Scales a scheme's daily or monthly feed so each closed year sums to the register's line (0168), and
    records every closed year where the feed differed. One per build; passed to the scheme modules."""

    def __init__(self, pinned: dict) -> None:
        self.pinned = pinned
        self.checks: dict = {}

    def __call__(self, df: pl.DataFrame, lines: tuple[str, ...], *, first_year: int = 0,
                 value_col: str = "cost_gbp") -> pl.DataFrame:
        vals = line_values(self.pinned["register"], self.pinned["product"], lines)
        return rescale_closed_years(df, vals, self.pinned["closed_through"], first_year=first_year,
                                    value_col=value_col, checks=self.checks, line="+".join(lines))

    def report(self) -> dict:
        """What breakdown.json publishes: the register read, and any closed year a feed differed from it."""
        return {"sha256": self.pinned["register"].sha256, "release": self.pinned["pin"].get("release"),
                "product": self.pinned["product"], "closed_through": self.pinned["closed_through"],
                "checks": self.checks}


def cm_share_from_engine(root: Path, pinned: dict) -> dict:
    """The Capacity Market share table the build expects, from the pinned engine release's Clock export
    (netzero_gbp, low, high) over the register's CM paid. Same structure and checks as the retired
    reference/capacity_market_netzero_share.yaml."""
    mp = yaml.safe_load((root / "reference" / "model_pin.yaml").read_text())
    p = root / mp["clock_export_file"]
    if hashlib.sha256(p.read_bytes()).hexdigest() != mp["sha256"]:
        raise ValueError(f"{p}: sha256 is not the model pin's {mp['sha256']}")
    ex = json.loads(p.read_text())
    if ex["meta"]["engine_version"] != mp["engine_version"]:
        raise ValueError(f"{p}: engine_version {ex['meta']['engine_version']} is not the pin's")
    paid = pinned["register"].series("CM_PAID")
    years = {}
    for ys, row in ex["capacity_market"]["years"].items():
        y = int(ys)
        if y not in paid or paid[y] <= 0:
            raise ValueError(f"Capacity Market {y}: no positive CM paid in the register")
        p_gbp = paid[y] * 1e6
        r = {"cm_paid_gbp": p_gbp, "netzero_gbp": row["netzero_gbp"], "netzero_low_gbp": row["netzero_low_gbp"],
             "netzero_high_gbp": row["netzero_high_gbp"], "own_backup_gbp": row["own_backup_gbp"],
             "share": row["netzero_gbp"] / p_gbp, "share_low": row["netzero_low_gbp"] / p_gbp,
             "share_high": row["netzero_high_gbp"] / p_gbp}
        if not (0.0 <= r["share_low"] <= r["share"] <= r["share_high"] <= 1.0 + 1e-9):
            raise ValueError(f"Capacity Market {y}: shares must satisfy 0 <= low <= central <= high <= 1, got "
                             f"{r['share_low']:.4f}/{r['share']:.4f}/{r['share_high']:.4f}")
        years[y] = r
    return {"years": years, "carry_forward_from": int(ex["capacity_market"]["carry_forward_from"]),
            "provenance": {"engine": f"gas-counterfactual {mp['engine_version']}",
                           "commit": mp.get("engine_commit"), "commit_date": mp.get("release_date"),
                           "file": f"{mp['clock_export_file']} (sha256 {mp['sha256'][:12]}...); CM paid from "
                                   f"the shared cost register (sha256 {pinned['register'].sha256[:12]}...)"}}
