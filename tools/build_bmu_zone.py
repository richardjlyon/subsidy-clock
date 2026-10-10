"""Regenerate reference/bmu_zone.csv: which grid zone (and so which nation)
every Elexon WIND balancing-mechanism unit sits in.

Elexon fills gspGroupId only for embedded units, so most transmission wind
farms have it blank. Every unit does carry a transmissionLossFactor, and the
loss factor is set per zone, so a unit's zone is the zone whose embedded units
share its loss factor. _P (North Scotland) and _N (South Scotland) are the two
Scottish zones.

    uv run python tools/build_bmu_zone.py

Farm names are tidied from bmUnitName; FARM_NAMES below overrides the ones
Elexon registers as bare codes. Re-run when new farms connect: the site build
fails if Scottish-zone constraint payments land on a unit missing from the file.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import httpx

URL = "https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all"
OUT = Path(__file__).resolve().parents[1] / "reference" / "bmu_zone.csv"

ZONE_NAMES = {
    "_A": "Eastern", "_B": "East Midlands", "_C": "London", "_D": "Merseyside & N Wales",
    "_E": "West Midlands", "_F": "North Eastern", "_G": "North Western",
    "_H": "Southern", "_J": "South Eastern", "_K": "South Wales", "_L": "South Western",
    "_M": "Yorkshire", "_N": "South Scotland", "_P": "North Scotland",
}
SCOTLAND = {"_N", "_P"}

# Elexon names a few units by code only. Each override is confirmed by a
# sibling unit's name or the unit's own lead-party name in the same register;
# any other code-only unit keeps its code rather than a guessed name.
FARM_NAMES = {
    "WHILW": "Whitelee",            # T_WHILW-2 is "Whitelee Extension"
    "BLLA": "Black Law",            # T_BLLA-2 is "Black Law Windfarm Extension"
    "INCWO": "Inch Cape",           # lead party Inch CAPE Offshore Ltd
    "ABRBO": "Aberdeen Offshore",   # lead party Aberdeen Offshore Wind Farm
    "KILBW": "Kilbraur",            # lead party Kilbraur Wind Energy Ltd
    "MILWW": "Millennium",          # lead party Millennium Wind Energy Ltd
    "HBHDW": "Harburnhead",         # unit name HARBURNHEADWF
    "SANQW": "Sanquhar",            # unit name SANQUHAR
    "NNGAO": "Neart na Gaoithe",    # register misspells it "Neart Na Gaiothe"
    "DUNGW": "Dunmaglass",          # register misspells it "Dunmglass"
}


def farm_key(bmu: str) -> str:
    """T_MOWEO-2 -> MOWEO, so a farm's units group together. Supplier
    aggregate units (2__..., C__...) are each their own key."""
    m = re.match(r"^(?:T_|E_)(.+?)(?:-\d+)?$", bmu)
    return m.group(1) if m else bmu


_CODE = re.compile(r"^(?:[TE2C]_|T-)|^[A-Z0-9_]+(?:-\d+)?$")
_TAIL = re.compile(
    r"(\s+(?:offshore\s+)?(?:wind\s*farm|windfarm|owf|wf|generator|bmu|unit|osp\w*|repower"
    r"|wind energy limited|limited|module|offshore wind|wind)\d*"
    r"|\s+(?:i{1,3}|iv|one|two|\d+[a-c]?)|[-\s]+\d+|\s+extension|\s+ext)\s*$", re.I)


def farm_name(key: str, unit_names: list[str]) -> str:
    """The farm's name from its first unit's registered name, with unit and
    phase suffixes stripped. Code-only names fall back to FARM_NAMES or the code."""
    if key in FARM_NAMES:
        return FARM_NAMES[key]
    for n in unit_names:
        if not n or _CODE.match(n.strip()):
            continue
        n = re.sub(r"\s+", " ", n).strip()
        prev = None
        while prev != n:
            prev, n = n, _TAIL.sub("", n).strip()
        n = re.sub(r"(?<=[a-z])1$", "", n)          # "Seagreen1"
        return n.title() if n.isupper() else n
    return key


def main() -> int:
    units = httpx.get(URL, timeout=60).json()
    by_tlf: dict[str, Counter] = defaultdict(Counter)
    for u in units:
        if u.get("gspGroupId") and u.get("transmissionLossFactor") is not None:
            by_tlf[u["transmissionLossFactor"]][u["gspGroupId"]] += 1
    tlf_zone = {t: c.most_common(1)[0][0] for t, c in by_tlf.items()}

    wind = [u for u in units if u.get("fuelType") == "WIND" and u.get("elexonBmUnit")]
    names: dict[str, list[str]] = defaultdict(list)
    for u in sorted(wind, key=lambda u: u["elexonBmUnit"]):
        names[farm_key(u["elexonBmUnit"])].append(u.get("bmUnitName") or "")

    rows, seen = [], set()
    for u in sorted(wind, key=lambda u: u["elexonBmUnit"]):
        bmu = u["elexonBmUnit"]
        if bmu in seen:
            continue
        seen.add(bmu)
        if u.get("gspGroupId"):
            zone, basis = u["gspGroupId"], "gspGroupId"
        else:
            zone, basis = tlf_zone.get(u.get("transmissionLossFactor")), "loss-factor zone"
        if zone is None:
            raise SystemExit(f"{bmu}: no zone from gspGroupId or loss factor")
        nation = "Scotland" if zone in SCOTLAND else "England & Wales"
        key = farm_key(bmu)
        rows.append({
            "bmu": bmu, "farm": farm_name(key, names[key]), "zone": zone,
            "zone_name": ZONE_NAMES.get(zone, zone), "nation": nation, "basis": basis,
            "capacity_mw": u.get("generationCapacity") or "", "source_url": URL,
        })
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    n_scot = sum(r["nation"] == "Scotland" for r in rows)
    print(f"[ok] {len(rows)} wind units, {n_scot} in Scotland -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
