"""Scotland claims briefing — computes every derived figure on /scotland-claims.

Writes site/data/scotland-claims.json. Every number on the page comes from here,
either computed from a live official source or quoted from an official table
(the quoted constants carry their source URL and the date they were checked).

    uv run python tools/scotland_claims.py

Sources computed live:
  NESO Historic Demand Data 2025   Scotland -> England flow (SCOTTISH_TRANSFER)
                                   and Northern Ireland flow (MOYLE_FLOW), half-hourly
  Elexon B1610                     metered output of named farms and of
                                   Torness + Peterhead, 2025 / 13 Oct 2025
  Clock store                      switch-off payments per farm (constraints)
                                   and CfD payments per farm (cfd/generation)
"""
from __future__ import annotations

import csv
import re
import io
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from subsidy_engine.store import SnapshotStore  # noqa: E402

ELEXON = "https://data.elexon.co.uk/bmrs/api/v1"
NESO_DEMAND_PKG = "https://api.neso.energy/api/3/action/package_show?id=historic-demand-data"
RANK = {"II": 0, "SF": 1, "R1": 2, "R2": 3, "R3": 4, "RF": 5, "DF": 6}
UA = {"User-Agent": "subsidyclock.co.uk scotland-claims"}
FIRM = ["T_TORN-1", "T_TORN-2", "T_PEHE-1"]
CALM_DAY = "2025-10-13"
CHECKED = "2026-10-10"

# Quoted from official tables. Each carries its source; re-check when DESNZ republishes.
DESNZ_REGIONAL = ("https://www.gov.uk/government/statistics/regional-renewable-statistics")
DESNZ_SUPPLY = ("https://www.gov.uk/government/statistics/energy-trends-september-2026-special-"
                "feature-article-electricity-generation-and-supply-in-scotland-wales-northern-"
                "ireland-and-england-2021-to-2025")
QUOTED = {
    "load_factor_2025": {"scotland_offshore": 0.2354, "england_offshore": 0.4129,
                         "scotland_onshore": 0.2412, "england_onshore": 0.2414,
                         "source": "DESNZ, Regional renewable statistics: load factors 2009-2025, sheet LF 2025",
                         "url": DESNZ_REGIONAL},
    "generation_2025_gwh": {"onshore": 21980, "offshore": 8870,
                            "source": "DESNZ, Regional renewable statistics: generation 2003-2025, sheet GWh 2025",
                            "url": DESNZ_REGIONAL},
    "capacity_mw": {"onshore_2022": 9027, "offshore_2022": 2166,
                    "onshore_2025": 10490, "offshore_2025": 4301,
                    "source": "DESNZ, Regional renewable statistics: installed capacity 2003-2025 (end of year)",
                    "url": DESNZ_REGIONAL},
    "supply_2025_gwh": {"generated": 54015, "consumed": 27997, "to_england_net": 18519,
                        "to_ni_net": 2232,
                        "source": "DESNZ, Electricity generation and supply in Scotland, Wales, Northern Ireland and England, 2004 to 2025, table 1",
                        "url": DESNZ_SUPPLY},
    "targets": [
        {"what": "Onshore wind", "target": "20 GW by 2030", "now_mw": 10490, "now_label": "10.5 GW",
         "source": "Scottish Government, Onshore Wind Policy Statement, December 2022",
         "url": "https://www.gov.scot/publications/onshore-wind-policy-statement-2022/"},
        {"what": "Offshore wind", "target": "8–11 GW by 2030", "now_mw": 4301, "now_label": "4.3 GW",
         "source": "Scottish Government, Offshore Wind Policy Statement, October 2020",
         "url": "https://www.gov.scot/publications/offshore-wind-policy-statement/"},
        {"what": "Hydrogen production", "target": "5 GW by 2030", "now_mw": None, "now_label": "no official figure",
         "source": "Scottish Government, Hydrogen Action Plan, December 2022",
         "url": "https://www.gov.scot/publications/hydrogen-action-plan/"},
        {"what": "Emissions: 75% cut by 2030", "target": "in law since 2019", "now_mw": None,
         "now_label": "repealed November 2024",
         "source": "Climate Change (Emissions Reduction Targets) (Scotland) Act 2024, section 2",
         "url": "https://www.legislation.gov.uk/asp/2024/15/section/2/enacted"},
    ],
    "firm": {"torness_close": "2030", "peterhead_mw": 1180,
             "torness_source": "EDF, 4 December 2024: Heysham 2 and Torness to generate until 2030",
             "torness_url": "https://www.edfenergy.com/media-centre/edf-confirms-boost-uks-clean-power-targets-nuclear-life-extensions",
             "peterhead_source": "SSE Thermal, Peterhead Power Station",
             "peterhead_url": "https://www.ssethermal.com/flexible-generation/operational/peterhead/",
             "nuclear_policy": "We oppose the building of new nuclear stations using current technologies.",
             "nuclear_policy_url": "https://www.gov.scot/policies/nuclear-energy/nuclear-stations/"},
    "consent": {"text": "Scottish Ministers decide applications for onshore generating stations over 50 MW, and for offshore wind in Scottish waters.",
                "url": "https://www.energyconsents.scot/",
                "offshore_url": "https://www.gov.scot/publications/marine-licensing-and-consent-section-36-consent/"},
}

FARMS = {  # farm prefix -> (display name, offshore?)
    "T_SGRWO": ("Seagreen", True), "T_MOWEO": ("Moray East", True), "T_MOWWO": ("Moray West", True),
    "T_VKNGW": ("Viking", False),
}
CFD_SCOTTISH = ["Beatrice", "Neart na Gaoithe", "Moray Offshore Windfarm (East)", "Dorenell",
                "Kype Muir", "Middle Muir", "Nanclach", "Solwaybank", "Sneddon Law", "Bad A Cheo",
                "Coire Na Cloiche", "Tralorg", "Achlachan"]


def get(url: str, client: httpx.Client):
    for attempt in range(6):
        try:
            r = client.get(url, headers=UA, follow_redirects=True)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if attempt == 5:
                raise
    raise RuntimeError(url)


def border(client: httpx.Client) -> dict:
    pkg = get(NESO_DEMAND_PKG, client).json()["result"]["resources"]
    url = next(r["url"] for r in pkg if r["url"].endswith("demanddata_2025.csv"))
    rows = list(csv.DictReader(io.StringIO(get(url, client).text)))
    days: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        own = float(r["SCOTTISH_TRANSFER"]) - float(r["MOYLE_FLOW"] or 0)   # >0: Scotland net exporter, after NI
        days[r["SETTLEMENT_DATE"]].append(own)
    flat = [x for v in days.values() for x in v]
    imp = [x for x in flat if x < 0]
    cd = days[CALM_DAY]
    return {
        "source": "NESO, Historic Demand Data 2025 (SCOTTISH_TRANSFER less MOYLE_FLOW)",
        "url": "https://www.neso.energy/data-portal/historic-demand-data",
        "half_hours": len(flat),
        "importing_half_hours": len(imp),
        "importing_share": round(len(imp) / len(flat), 4),
        "days_net_importer": sum(1 for v in days.values() if sum(v) < 0),
        "imported_gwh": round(-sum(imp) / 2 / 1e3, 1),
        "calm_day_import_half_hours": sum(1 for x in cd if x < 0),
        "calm_day_peak_import_mw": round(-min(cd)),
    }


def b1610(units: list[str], a: str, z: str, client: httpx.Client) -> dict[str, float]:
    q = "&".join(f"bmUnit={u}" for u in units)
    rows = get(f"{ELEXON}/datasets/B1610/stream?from={a}T00:00Z&to={z}T00:00Z&{q}", client).json()
    best: dict = {}
    for r in rows:
        k = (r["bmUnit"], r["settlementDate"], r["settlementPeriod"])
        rk = RANK.get(r["settlementRunType"], -1)
        if k not in best or rk > best[k][0]:
            best[k] = (rk, float(r["quantity"]))
    return best


def farm_units(client: httpx.Client) -> tuple[dict[str, list[str]], dict[str, float]]:
    reg = get(f"{ELEXON}/reference/bmunits/all", client).json()
    units, cap = defaultdict(list), {}
    for u in reg:
        b = u.get("elexonBmUnit") or ""
        for f in FARMS:
            if b.startswith(f + "-"):
                units[f].append(b)
                cap[b] = float(u.get("generationCapacity") or 0)
    return units, cap


def zones_all() -> dict[str, str]:
    return {r["bmu"]: r["nation"] for r in csv.DictReader(open(ROOT / "reference/bmu_zone.csv"))}


def main() -> None:
    client = httpx.Client(timeout=180)
    store = SnapshotStore(ROOT / "data")
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "checked": CHECKED,
                 "quoted": QUOTED}
    out["border"] = border(client)

    # Calm day: wind fleet, wind output, Torness + Peterhead, from the Grid Margin-style B1610 read
    scot = json.load(open(ROOT / "site/data/scotland.json"))
    units, cap = farm_units(client)
    months = [(f"2025-{m:02d}-01", f"2025-{m + 1:02d}-01" if m < 12 else "2026-01-01") for m in range(1, 13)]
    jobs = [(units[f], a, z) for f in FARMS for a, z in months]
    met: dict[str, float] = defaultdict(float)
    with ThreadPoolExecutor(6) as ex:
        for best in ex.map(lambda j: b1610(*j, client), jobs):
            for (b, _, _), (_, v) in best.items():
                met[b] += v
    con = store.read_all_partitions("constraints", "daily").filter(pl.col("date").dt.year() == 2025)
    farms = []
    for f, (name, off) in FARMS.items():
        us = units[f]
        mw = sum(cap[u] for u in us)
        gwh = sum(met[u] for u in us) / 1e3
        c = con.filter(pl.col("bmu").is_in(us))
        off_gwh = -c["volume_mwh"].sum() / 1e3
        farms.append({"farm": name, "offshore": off, "capacity_mw": round(mw),
                      "metered_gwh": round(gwh), "switched_off_gwh": round(off_gwh),
                      "paid_to_switch_off": round(c["cost_gbp"].sum()),
                      # share of what the farm could have made that it was paid not to make;
                      # needs no capacity figure (Elexon's registered capacities are not nameplate)
                      "share_switched_off": round(off_gwh / (gwh + off_gwh), 3)})
    out["farms_2025"] = farms

    fw = b1610(FIRM, CALM_DAY, "2025-10-14", client)
    firm_mw = sum(v for _, v in fw.values()) * 2 / 48
    sw = [b for b, z in zones_all().items() if z == "Scotland"]
    per_hh: dict = defaultdict(float)
    for i in range(0, len(sw), 40):
        for (b, dd, sp), (_, v) in b1610(sw[i:i + 40], CALM_DAY, "2025-10-14", client).items():
            per_hh[sp] += v * 2
    out["calm_day"] = {"date": CALM_DAY, "firm_mean_mw": round(firm_mw),
                       "wind_mean_mw": round(sum(per_hh.values()) / 48),
                       "wind_max_mw": round(max(per_hh.values())), "wind_units": len(sw)}

    # CfD subsidy to Scottish farms, 2025 — from the Clock's own CfD store
    cfd = store.read_all_partitions("cfd", "generation").filter(pl.col("date").dt.year() == 2025)
    pat = "|".join(re.escape(n) for n in CFD_SCOTTISH)
    sc = cfd.filter(pl.col("unit_name").str.contains(pat))
    by = (sc.with_columns(pl.col("unit_name").str.replace(r"(?i)\s*(Offshore Wind Farm Limited)?\s*\(?Phase.*$", "").alias("farm"))
          .group_by("farm").agg(pl.col("payment_gbp").sum()).sort("payment_gbp", descending=True))
    out["cfd_2025"] = {"total": round(sc["payment_gbp"].sum()),
                       "farms": [{"farm": r[0].strip(), "paid": round(r[1])} for r in by.iter_rows()],
                       "source": "LCCC, Contracts for Difference generation and payments (the Clock's CfD series)"}
    sc_share = scot["who_pays"]["scotland_consumption_share"] if "who_pays" in scot else None
    out["switch_off"] = {k: scot[k] for k in ("gb_cost", "scotland_cost", "scotland_share", "window")}
    out["consumption_share"] = sc_share
    scot_units = set(json.load(open(ROOT / "site/data/scotland.json"))["zone_units"]) if "zone_units" in scot else None
    zones = {r["bmu"]: r["nation"] for r in csv.DictReader(open(ROOT / "reference/bmu_zone.csv"))}
    sc_con = con.filter(pl.col("bmu").replace_strict(zones, default="?") == "Scotland")
    out["switch_off_2025"] = {"scotland_cost": round(sc_con["cost_gbp"].sum()),
                              "scotland_gwh": round(-sc_con["volume_mwh"].sum() / 1e3)}
    allc = store.read_all_partitions("constraints", "daily")
    allc = allc.filter(pl.col("bmu").replace_strict(zones, default="?") == "Scotland")
    top = allc.group_by("date").agg(pl.col("cost_gbp").sum(), (-pl.col("volume_mwh").sum()).alias("mwh")).sort("cost_gbp", descending=True).row(0)
    offp = ("T_ABRBO", "T_BEATO", "T_INCWO", "T_MOWEO", "T_MOWWO", "T_NNGAO", "T_SGRWO")
    out["switch_off_2025"]["scotland_offshore_gwh"] = round(
        -sc_con.filter(pl.col("bmu").str.slice(0, 7).is_in(offp))["volume_mwh"].sum() / 1e3)
    out["top_day"] = {"date": top[0].isoformat(), "cost": round(top[1]), "mwh": round(top[2])}
    (ROOT / "site/data/scotland-claims.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("border", "farms_2025", "calm_day", "cfd_2025")}, indent=1)[:4000])


if __name__ == "__main__":
    main()
